from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse, Http404
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import requests
import hmac
import hashlib
import uuid
import os

from chat.serializers import UserSerializer, VideoChatSessionSerializer, VideoChatMessageSerializer, VideoAnalysisCacheSerializer
from chat.models import VideoChatSession, VideoChatMessage, VideoAnalysisCache, Video, User, SocialAccount
from ..utils.chatbot import ChatBot, chatbots
from ..utils.file_utils import process_uploaded_file, summarize_content
from ..services.optimal_response import collect_multi_llm_responses, format_optimal_response
from ..services.video_analysis_service import video_analysis_service
from ..enhanced_video_chat_handler import get_video_chat_handler


class VideoChatView(APIView):
    """영상 채팅 뷰 - 다중 AI 응답 및 통합"""
    permission_classes = [AllowAny]  # 임시로 AllowAny로 변경
    
    def get(self, request, video_id=None):
        """채팅 세션 목록 조회"""
        try:
            print(f"🔍 VideoChatView GET 요청 - video_id: {video_id}")
            
            # 사용자 정보 처리 (인증되지 않은 경우 기본 사용자 사용)
            user = None
            if hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
            else:
                # 기본 사용자 생성 또는 가져오기
                from chat.models import User
                user, created = User.objects.get_or_create(
                    username='anonymous',
                    defaults={'email': 'anonymous@example.com'}
                )
                print(f"✅ 기본 사용자 생성/가져오기: {user.username}")
            
            if video_id:
                # 특정 영상의 채팅 세션 조회
                sessions = VideoChatSession.objects.filter(
                    user=user, 
                    video_id=video_id,
                    is_active=True
                ).order_by('-created_at')
            else:
                # 사용자의 모든 채팅 세션 조회
                sessions = VideoChatSession.objects.filter(
                    user=user,
                    is_active=True
                ).order_by('-created_at')
            
            serializer = VideoChatSessionSerializer(sessions, many=True)
            return Response({
                'sessions': serializer.data,
                'total_count': sessions.count()
            })
            
        except Exception as e:
            return Response({
                'error': f'채팅 세션 조회 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, video_id):
        """영상 채팅 메시지 전송"""
        try:
            print(f"🔍 VideoChatView POST 요청 - video_id: {video_id}")
            # Django WSGIRequest에서 JSON 데이터 파싱
            import json
            if hasattr(request, 'data'):
                message = request.data.get('message')
            else:
                body = request.body.decode('utf-8')
                data = json.loads(body)
                message = data.get('message')
            print(f"📝 메시지: {message}")
            
            if not message:
                return Response({
                    'error': '메시지가 필요합니다'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 영상 분석 상태 확인 (Video 모델에서 직접 확인)
            try:
                video = Video.objects.get(id=video_id)
                if video.analysis_status == 'pending':
                    return Response({
                        'error': '영상 분석이 진행 중입니다. 잠시 후 다시 시도해주세요.',
                        'status': 'analyzing'
                    }, status=status.HTTP_202_ACCEPTED)
                elif video.analysis_status == 'failed':
                    return Response({
                        'error': '영상 분석에 실패했습니다. 다른 영상을 업로드해주세요.',
                        'status': 'failed'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except Video.DoesNotExist:
                return Response({
                    'error': '영상을 찾을 수 없습니다'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # 사용자 정보 처리 (인증되지 않은 경우 기본 사용자 사용)
            user = request.user if request.user.is_authenticated else None
            if not user:
                # 기본 사용자 생성 또는 가져오기
                from chat.models import User
                user, created = User.objects.get_or_create(
                    username='anonymous',
                    defaults={'email': 'anonymous@example.com'}
                )
            
            # 채팅 세션 가져오기 또는 생성
            session, created = VideoChatSession.objects.get_or_create(
                user=user,
                video_id=video_id,
                is_active=True,
                defaults={
                    'video_title': f"Video {video_id}",
                    'video_analysis_data': {}
                }
            )
            
            # 사용자 메시지 저장
            user_message = VideoChatMessage.objects.create(
                session=session,
                message_type='user',
                content=message
            )
            
            # 🎯 개선된 핸들러 사용
            print(f"🔍 개선된 영상 채팅 핸들러 사용: '{message}'")
            handler = get_video_chat_handler(video_id, video)
            chat_result = handler.process_message(message)
            
            # AI 개별 응답 저장
            individual_messages = []
            print(f"🔍 chat_result['individual_responses']: {chat_result.get('individual_responses')}")
            if chat_result.get('individual_responses'):
                print(f"✅ 개별 응답 {len(chat_result['individual_responses'])}개 발견")
                for ai_name, ai_content in chat_result['individual_responses'].items():
                    print(f"  - {ai_name}: {ai_content[:100] if ai_content else 'None'}...")
                    ai_message = VideoChatMessage.objects.create(
                        session=session,
                        message_type='ai',
                        content=ai_content,
                        ai_model=ai_name,
                        parent_message=user_message
                    )
                    individual_messages.append(ai_message)
            else:
                print(f"⚠️ individual_responses가 비어있습니다!")
            
            # 통합 응답 저장
            optimal_response = chat_result.get('answer', '')
            optimal_message = None
            if optimal_response:
                optimal_message = VideoChatMessage.objects.create(
                    session=session,
                    message_type='ai_optimal',
                    content=optimal_response,
                    ai_model='optimal',
                    parent_message=user_message
                )
            
            # 프레임 정보 구성
            relevant_frames = []
            if chat_result.get('frames'):
                # 메타 DB에서 전체 프레임 정보 가져오기 (영상별 동적 경로)
                meta_db_filename = f"{video.original_name or video.filename}-meta_db.json"
                meta_db_path = os.path.join(settings.MEDIA_ROOT, meta_db_filename)
                all_frames = []
                if os.path.exists(meta_db_path):
                    try:
                        with open(meta_db_path, 'r', encoding='utf-8') as f:
                            meta_data = json.load(f)
                            all_frames = meta_data.get('frame', [])
                    except Exception as meta_error:
                        logger.warning(f"메타 DB 로드 실패({meta_db_path}): {meta_error}")
                else:
                    logger.warning(f"메타 DB 파일이 존재하지 않습니다: {meta_db_path}")
                
                for idx, frame in enumerate(chat_result['frames']):
                    meta_frame = None
                    if all_frames:
                        # timestamp 기준으로 메타 프레임 찾기
                        for candidate in all_frames:
                            if abs(candidate.get('timestamp', 0) - frame.get('timestamp', 0)) < 0.1:
                                meta_frame = candidate
                                break
                    
                    # 이미지 경로와 ID 결정
                    image_id = frame.get('image_id')
                    if not image_id and meta_frame:
                        image_id = meta_frame.get('image_id')
                    if not image_id:
                        image_id = idx + 1
                    
                    frame_image_path = frame.get('frame_image_path')
                    if not frame_image_path and meta_frame:
                        frame_image_path = meta_frame.get('frame_image_path')
                    if not frame_image_path:
                        frame_image_path = f"images/video{video_id}_frame{image_id}.jpg"
                    frame_image_path = frame_image_path.lstrip('/')
                    
                    raw_objects = frame.get('objects', []) or []
                    persons = frame.get('persons')
                    if persons is None:
                        persons = [obj for obj in raw_objects if obj.get('class') == 'person']
                    
                    other_objects = frame.get('detected_other_objects')
                    if other_objects is None:
                        other_objects = [obj for obj in raw_objects if obj.get('class') != 'person']
                    
                    frame_info = {
                        'image_id': image_id,
                        'timestamp': frame.get('timestamp', 0),
                        'image_url': f"/media/{frame_image_path}",
                        'caption': frame.get('caption', ''),
                        'relevance_score': frame.get('match_score', 1.0),
                        'persons': persons[:3] if persons else [],
                        'objects': other_objects,
                        'scene_attributes': {
                            'scene_type': 'unknown',
                            'lighting': 'unknown',
                            'activity_level': 'unknown'
                        }
                    }
                    relevant_frames.append(frame_info)
            
            # 응답 데이터 구성 (프론트엔드 형식에 맞춤)
            response_data = {
                'session_id': str(session.id),
                'user_message': {
                    'id': str(user_message.id),
                    'content': message,
                    'created_at': user_message.created_at.isoformat()
                },
                'ai_responses': {
                    'individual': [
                        {
                            'id': str(msg.id),
                            'model': msg.ai_model,
                            'content': msg.content,
                            'created_at': msg.created_at.isoformat()
                        } for msg in individual_messages
                    ],
                    'optimal': {
                        'id': str(optimal_message.id) if optimal_message else None,
                        'model': 'optimal',
                        'content': optimal_response,
                        'created_at': optimal_message.created_at.isoformat() if optimal_message else None
                    } if optimal_response else None
                },
                'relevant_frames': relevant_frames,
                'is_video_related': chat_result.get('is_video_related', True)
            }
            
            print(f"✅ 응답 생성 완료:")
            print(f"   - 개별 AI: {len(individual_messages)}개")
            print(f"   - 통합 응답: {'있음' if optimal_response else '없음'}")
            print(f"   - 관련 프레임: {len(relevant_frames)}개")
            
            return Response(response_data)
            
        except Exception as e:
            import traceback
            print(f"❌ 오류 발생: {e}")
            print(f"❌ 상세: {traceback.format_exc()}")
            return Response({
                'error': f'채팅 처리 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 영상 분석 데이터 가져오기 (Video 모델에서 직접)
            analysis_data = {
                'original_name': video.original_name,
                'file_size': video.file_size,
                'uploaded_at': video.uploaded_at.isoformat(),
                'analysis_status': video.analysis_status,
                'duration': video.duration,
                'is_analyzed': video.is_analyzed
            }
            
            # JSON 분석 결과 로드 (기존 + TeletoVision_AI 스타일)
            analysis_json_data = None
            teleto_vision_data = {}
            
            # 1. 기존 분석 JSON 로드
            if video.analysis_json_path:
                try:
                    json_path = os.path.join(settings.MEDIA_ROOT, video.analysis_json_path)
                    print(f"🔍 기존 JSON 파일 경로: {json_path}")
                    print(f"🔍 파일 존재 여부: {os.path.exists(json_path)}")
                    
                    with open(json_path, 'r', encoding='utf-8') as f:
                        analysis_json_data = json.load(f)
                    print(f"✅ 기존 JSON 분석 결과 로드 성공: {json_path}")
                    print(f"📊 기존 JSON 데이터 키: {list(analysis_json_data.keys())}")
                    if 'frame_results' in analysis_json_data:
                        print(f"📊 frame_results 개수: {len(analysis_json_data['frame_results'])}")
                        if analysis_json_data['frame_results']:
                            print(f"📊 첫 번째 프레임: {analysis_json_data['frame_results'][0]}")
                except Exception as e:
                    print(f"❌ 기존 JSON 분석 결과 로드 실패: {e}")
                    import traceback
                    print(f"❌ 상세 오류: {traceback.format_exc()}")
            else:
                print("❌ analysis_json_path가 없습니다.")
            
            # 2. TeletoVision_AI 스타일 JSON 로드
            try:
                video_name = video.original_name or video.filename
                detection_db_path = os.path.join(settings.MEDIA_ROOT, f"{video_name}-detection_db.json")
                meta_db_path = os.path.join(settings.MEDIA_ROOT, f"{video_name}-meta_db.json")
                
                print(f"🔍 TeletoVision detection_db 경로: {detection_db_path}")
                print(f"🔍 TeletoVision meta_db 경로: {meta_db_path}")
                
                # detection_db.json 로드
                if os.path.exists(detection_db_path):
                    with open(detection_db_path, 'r', encoding='utf-8') as f:
                        teleto_vision_data['detection_db'] = json.load(f)
                    print(f"✅ TeletoVision detection_db 로드 성공: {len(teleto_vision_data['detection_db'])}개 프레임")
                else:
                    print(f"❌ TeletoVision detection_db 파일 없음: {detection_db_path}")
                
                # meta_db.json 로드
                if os.path.exists(meta_db_path):
                    with open(meta_db_path, 'r', encoding='utf-8') as f:
                        teleto_vision_data['meta_db'] = json.load(f)
                    print(f"✅ TeletoVision meta_db 로드 성공: {len(teleto_vision_data['meta_db'].get('frame', []))}개 프레임")
                    if teleto_vision_data['meta_db'].get('frame'):
                        first_frame = teleto_vision_data['meta_db']['frame'][0]
                        print(f"📊 첫 번째 meta 프레임 키: {list(first_frame.keys())}")
                else:
                    print(f"❌ TeletoVision meta_db 파일 없음: {meta_db_path}")
                    
            except Exception as e:
                print(f"❌ TeletoVision JSON 로드 실패: {e}")
                import traceback
                print(f"❌ 상세 오류: {traceback.format_exc()}")
                teleto_vision_data = {}
                print(f"❌ video.analysis_json_path: {video.analysis_json_path}")
            
            # 프레임 검색 및 이미지 URL 생성
            print(f"🔍 프레임 검색 시작 - analysis_json_data: {analysis_json_data is not None}")
            if analysis_json_data:
                print(f"📊 frame_results 존재: {'frame_results' in analysis_json_data}")
                if 'frame_results' in analysis_json_data:
                    print(f"📊 frame_results 개수: {len(analysis_json_data['frame_results'])}")
            else:
                print("❌ analysis_json_data가 None입니다!")
                print(f"❌ video.analysis_json_path: {video.analysis_json_path}")
                print(f"❌ video.analysis_status: {video.analysis_status}")
                print(f"❌ video.is_analyzed: {video.is_analyzed}")
            
            # 대화 맥락 가져오기
            session_id = f"video_{video_id}_user_{user.id}"
            context_prompt = conversation_memory.generate_context_prompt(session_id, message)
            
            # 프레임 검색 (의도 기반)
            relevant_frames = self._find_relevant_frames(message, analysis_json_data, video_id)
            print(f"🔍 검색된 프레임 수: {len(relevant_frames)}")
            if relevant_frames:
                print(f"📸 첫 번째 프레임: {relevant_frames[0]}")
                print(f"📸 모든 프레임 정보:")
                for i, frame in enumerate(relevant_frames):
                    print(f"  프레임 {i+1}: {frame}")
            else:
                print("❌ 검색된 프레임이 없습니다!")
                print(f"❌ analysis_json_data keys: {list(analysis_json_data.keys()) if analysis_json_data else 'None'}")
                if analysis_json_data and 'frame_results' in analysis_json_data:
                    print(f"❌ frame_results 개수: {len(analysis_json_data['frame_results'])}")
                    if analysis_json_data['frame_results']:
                        print(f"❌ 첫 번째 frame_result: {analysis_json_data['frame_results'][0]}")
            
            # 다중 AI 응답 생성
            ai_responses = {}
            individual_messages = []
            
            # 기본 채팅 시스템과 동일한 AI 모델 초기화
            try:
                # 전역 chatbots 변수 사용 (이미 초기화되어 있음)
                print(f"✅ 사용 가능한 AI 모델: {list(chatbots.keys())}")
            except Exception as e:
                print(f"⚠️ AI 모델 초기화 실패: {e}")
                # 전역 chatbots 변수는 이미 초기화되어 있으므로 덮어쓰지 않음
            
            # AI 모델 확인
            print(f"🤖 사용 가능한 AI 모델: {list(chatbots.keys()) if chatbots else 'None'}")
            
            # AI 모델이 없는 경우 기본 응답 (프레임 정보 포함)
            if not chatbots:
                print("⚠️ 사용 가능한 AI 모델이 없습니다. 기본 응답을 생성합니다.")
                
                # 프레임 정보를 포함한 더 나은 응답 생성
                if relevant_frames:
                    frame_count = len(relevant_frames)
                    default_response = f"영상에서 '{message}'와 관련된 {frame_count}개의 프레임을 찾았습니다!\n\n"
                    
                    for i, frame in enumerate(relevant_frames, 1):
                        default_response += f"📸 프레임 {i}:\n"
                        default_response += f"   ⏰ 시간: {frame['timestamp']:.1f}초\n"
                        default_response += f"   🎯 관련도: {frame['relevance_score']}점\n"
                        
                        if frame['persons'] and len(frame['persons']) > 0:
                            default_response += f"   👤 사람 {len(frame['persons'])}명 감지\n"
                        
                        if frame['objects'] and len(frame['objects']) > 0:
                            default_response += f"   📦 객체 {len(frame['objects'])}개 감지\n"
                        
                        scene_attrs = frame.get('scene_attributes', {})
                        if scene_attrs:
                            scene_type = scene_attrs.get('scene_type', 'unknown')
                            lighting = scene_attrs.get('lighting', 'unknown')
                            activity = scene_attrs.get('activity_level', 'unknown')
                            default_response += f"   🏞️ 장면: {scene_type}, 조명: {lighting}, 활동: {activity}\n"
                        
                        default_response += "\n"
                    
                    default_response += "💡 AI 모델이 활성화되면 더 자세한 분석을 제공할 수 있습니다."
                else:
                    default_response = f"죄송합니다. '{message}'와 관련된 프레임을 찾을 수 없습니다.\n\n"
                    default_response += "다른 키워드로 시도해보세요:\n"
                    default_response += "• 사람, 자동차, 동물, 음식, 옷, 건물, 자연, 물체"
                
                ai_responses = {
                    'default': default_response
                }
            else:
                # 각 AI 모델에 질문 전송
                for bot_name, chatbot in chatbots.items():
                    if bot_name == 'optimal':
                        continue  # optimal은 나중에 처리
                    
                    try:
                        # 색상 검색 모드 확인
                        is_color_search = any(keyword in message.lower() for keyword in ['빨간색', '파란색', '노란색', '초록색', '보라색', '분홍색', '검은색', '흰색', '회색', '주황색', '갈색', '옷'])
                        
                        # 간소화된 영상 정보 프롬프트 생성
                        video_context = f"""
영상: {analysis_data.get('original_name', 'Unknown')} ({analysis_data.get('file_size', 0) / (1024*1024):.1f}MB)
분석: {len(analysis_json_data.get('frame_results', []))}개 프레임, {analysis_json_data.get('video_summary', {}).get('total_detections', 0)}개 객체
품질: {analysis_json_data.get('video_summary', {}).get('quality_assessment', {}).get('overall_score', 0):.2f}
"""
                        
                        # 간소화된 프레임 정보
                        frame_context = ""
                        if relevant_frames:
                            frame_context = f"\n관련 프레임 {len(relevant_frames)}개:\n"
                            for i, frame in enumerate(relevant_frames[:2], 1):  # 최대 2개만
                                frame_context += f"프레임 {i}: {frame['timestamp']:.1f}초, 사람 {len(frame.get('persons', []))}명\n"
                        else:
                            frame_context = "\n관련 프레임 없음\n"
                        
                        enhanced_message = f"""{video_context}{frame_context}

사용자 질문: "{message}"

위 정보를 바탕으로 친근하게 답변해주세요."""
                        
                        # 간소화된 AI 프롬프트
                        ai_prompt = enhanced_message
                        
                        # AI별 특성화된 프롬프트로 응답 생성
                        ai_response = chatbot.chat(ai_prompt)
                        ai_responses[bot_name] = ai_response
                        
                        # 개별 AI 응답 저장
                        ai_message = VideoChatMessage.objects.create(
                            session=session,
                            message_type='ai',
                            content=ai_response,
                            ai_model=bot_name,
                            parent_message=user_message
                        )
                        individual_messages.append(ai_message)
                        
                    except Exception as e:
                        print(f"AI {bot_name} 응답 생성 실패: {str(e)}")
                        continue
            
            # 통합 응답 생성 (기본 채팅 시스템과 동일한 방식)
            optimal_response = ""
            if ai_responses and len(ai_responses) > 1:
                try:
                    # 기본 채팅 시스템의 generate_optimal_response 사용
                    optimal_response = generate_optimal_response(ai_responses, message, os.getenv('OPENAI_API_KEY'))
                    
                    # 프레임 정보 추가 (더 자세한 정보 포함)
                    if relevant_frames:
                        frame_summary = f"\n\n📸 관련 프레임 {len(relevant_frames)}개 발견:\n"
                        for i, frame in enumerate(relevant_frames, 1):
                            frame_summary += f"• 프레임 {i}: {frame['timestamp']:.1f}초 (관련도 {frame['relevance_score']:.2f}점)\n"
                            
                            # 프레임별 세부 정보 추가
                            if frame.get('persons'):
                                frame_summary += f"  👤 사람 {len(frame['persons'])}명 감지됨!\n"
                                # 각 사람의 상세 정보 추가
                                for j, person in enumerate(frame['persons'], 1):
                                    confidence = person.get('confidence', 0)
                                    frame_summary += f"    사람 {j}: 신뢰도 {confidence:.2f}\n"
                                    # 속성 정보 추가
                                    attrs = person.get('attributes', {})
                                    if 'gender' in attrs:
                                        gender_info = attrs['gender']
                                        frame_summary += f"      성별: {gender_info.get('value', 'unknown')}\n"
                                    if 'age' in attrs:
                                        age_info = attrs['age']
                                        frame_summary += f"      나이: {age_info.get('value', 'unknown')}\n"
                            if frame.get('objects'):
                                frame_summary += f"  📦 객체 {len(frame['objects'])}개 감지\n"
                            
                            scene_attrs = frame.get('scene_attributes', {})
                            if scene_attrs:
                                scene_type = scene_attrs.get('scene_type', 'unknown')
                                lighting = scene_attrs.get('lighting', 'unknown')
                                frame_summary += f"  🏞️ 장면: {scene_type}, 조명: {lighting}\n"
                        
                        frame_summary += "\n💡 위 프레임들을 참고하여 영상에서 해당 내용을 확인해보세요."
                        optimal_response += frame_summary
                    
                    # 통합 응답 저장
                    optimal_message = VideoChatMessage.objects.create(
                        session=session,
                        message_type='ai_optimal',
                        content=optimal_response,
                        ai_model='optimal',
                        parent_message=user_message
                    )
                    
                except Exception as e:
                    print(f"통합 응답 생성 실패: {str(e)}")
                    optimal_response = f"통합 응답 생성 중 오류가 발생했습니다: {str(e)}"
            elif ai_responses and len(ai_responses) == 1:
                # AI 응답이 하나만 있는 경우
                optimal_response = list(ai_responses.values())[0]
            
            # 응답 품질 평가
            evaluation_results = {}
            if ai_responses and len(ai_responses) > 1:
                try:
                    evaluation_results = evaluation_metrics.evaluate_summary_quality(
                        ai_responses, reference=optimal_response
                    )
                    print(f"✅ 응답 품질 평가 완료: {len(evaluation_results)}개 AI")
                except Exception as e:
                    print(f"❌ 응답 품질 평가 실패: {e}")
            
            # 대화 맥락 업데이트
            try:
                conversation_memory.add_context(
                    session_id=session_id,
                    user_message=message,
                    ai_responses=ai_responses,
                    video_context={
                        'video_id': video_id,
                        'video_name': video.original_name,
                        'relevant_frames_count': len(relevant_frames)
                    }
                )
                print(f"✅ 대화 맥락 업데이트 완료")
            except Exception as e:
                print(f"❌ 대화 맥락 업데이트 실패: {e}")
            
            # 응답 데이터 구성
            response_data = {
                'session_id': str(session.id),
                'user_message': {
                    'id': str(user_message.id),
                    'content': message,
                    'created_at': user_message.created_at
                },
                'ai_responses': {
                    'individual': [
                        {
                            'id': str(msg.id),
                            'model': msg.ai_model,
                            'content': msg.content,
                            'created_at': msg.created_at
                        } for msg in individual_messages
                    ],
                    'optimal': {
                        'content': optimal_response,
                        'created_at': individual_messages[0].created_at if individual_messages else None
                    } if optimal_response else None
                },
                'relevant_frames': relevant_frames,  # 관련 프레임 정보 추가
                'evaluation_results': evaluation_results,  # 품질 평가 결과
                'context_info': {
                    'session_id': session_id,
                    'context_length': len(conversation_memory.get_context(session_id).get('conversations', []))
                }
            }
            
            # 디버깅: relevant_frames 확인
            print(f"🔍 응답 생성 시 relevant_frames: {len(relevant_frames)}")
            if relevant_frames:
                print(f"📸 첫 번째 프레임: {relevant_frames[0]}")
            else:
                print("❌ relevant_frames가 비어있음!")
            
            print(f"📤 응답에 포함될 프레임 수: {len(relevant_frames)}")
            if relevant_frames:
                print(f"📸 첫 번째 프레임: {relevant_frames[0]}")
            
            return Response(response_data)
            
        except Exception as e:
            import traceback
            print(f"❌ VideoChatView POST 오류: {str(e)}")
            print(f"❌ 오류 상세: {traceback.format_exc()}")
            return Response({
                'error': f'채팅 처리 중 오류 발생: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _classify_intent(self, message):
        """사용자 메시지의 의도를 분류"""
        try:
            message_lower = message.lower()
            
            # 의도별 키워드 정의
            intent_keywords = {
                'video_summary': ['요약', 'summary', '간단', '상세', '하이라이트', 'highlight', '정리'],
                'video_search': ['찾아', '검색', 'search', '보여', '어디', '언제', '누가'],
                'person_search': ['사람', 'person', 'people', 'human', '남성', '여성', '성별'],
                'color_search': ['빨간색', '파란색', '노란색', '초록색', '보라색', '분홍색', '검은색', '흰색', '회색', '주황색', '갈색', '색깔', '색상', '옷', '입은', '착용'],
                'temporal_analysis': ['시간', '분', '초', '언제', '몇시', '성비', '인원', '통계'],
                'inter_video_search': ['비오는', '밤', '낮', '날씨', '조명', '영상간', '다른영상'],
                'general_chat': ['안녕', 'hello', 'hi', '고마워', '감사', '도움', '질문']
            }
            
            # 의도 점수 계산
            intent_scores = {}
            for intent, keywords in intent_keywords.items():
                score = sum(1 for keyword in keywords if keyword in message_lower)
                if score > 0:
                    intent_scores[intent] = score
            
            # 가장 높은 점수의 의도 선택
            if intent_scores:
                detected_intent = max(intent_scores, key=intent_scores.get)
                confidence = intent_scores[detected_intent] / len(message_lower.split())
                print(f"🎯 의도 분류: {detected_intent} (신뢰도: {confidence:.2f})")
                return detected_intent, confidence
            else:
                print("🎯 의도 분류: general_chat (기본값)")
                return 'general_chat', 0.0
                
        except Exception as e:
            print(f"❌ 의도 분류 중 오류: {e}")
            return 'general_chat', 0.0

    def _parse_time_range(self, message):
        """메시지에서 시간 범위를 파싱"""
        try:
            import re
            
            # 시간 패턴 매칭 (예: "3:00~5:00", "3분~5분", "180초~300초")
            time_patterns = [
                r'(\d+):(\d+)~(\d+):(\d+)',  # 3:00~5:00
                r'(\d+)분~(\d+)분',          # 3분~5분
                r'(\d+)초~(\d+)초',          # 180초~300초
            ]
            
            for pattern in time_patterns:
                match = re.search(pattern, message)
                if match:
                    groups = match.groups()
                    if len(groups) == 4:  # 3:00~5:00 형식
                        start_min, start_sec, end_min, end_sec = map(int, groups)
                        start_time = start_min * 60 + start_sec
                        end_time = end_min * 60 + end_sec
                        return start_time, end_time
                    elif len(groups) == 2:  # 분 또는 초 형식
                        start_val, end_val = map(int, groups)
                        if '분' in message:
                            start_time = start_val * 60
                            end_time = end_val * 60
                        else:  # 초
                            start_time = start_val
                            end_time = end_val
                        return start_time, end_time
            
            return None
            
        except Exception as e:
            print(f"❌ 시간 범위 파싱 중 오류: {e}")
            return None

    def _find_relevant_frames(self, message, analysis_json_data, video_id):
        """사용자 메시지에 따라 관련 프레임을 찾아서 이미지 URL과 함께 반환 (의도 기반)"""
        try:
            if not analysis_json_data or 'frame_results' not in analysis_json_data:
                print("❌ 분석 데이터 또는 프레임 결과가 없습니다.")
                return []
            
            relevant_frames = []
            message_lower = message.lower()
            
            # 프레임 결과에서 매칭되는 프레임 찾기
            frame_results = analysis_json_data.get('frame_results', [])
            print(f"🔍 검색할 프레임 수: {len(frame_results)}")
            
            # 의도 분류
            intent, confidence = self._classify_intent(message)
            print(f"🎯 검색 의도: {intent}")
            
            # 색상 기반 검색
            color_keywords = {
                '빨간색': ['red', '빨강', '빨간색'],
                '파란색': ['blue', '파랑', '파란색'],
                '노란색': ['yellow', '노랑', '노란색'],
                '초록색': ['green', '녹색', '초록색'],
                '보라색': ['purple', '자주색', '보라색'],
                '분홍색': ['pink', '핑크', '분홍색'],
                '검은색': ['black', '검정', '검은색'],
                '흰색': ['white', '하양', '흰색'],
                '회색': ['gray', 'grey', '회색'],
                '주황색': ['orange', '오렌지', '주황색'],
                '갈색': ['brown', '브라운', '갈색'],
                '옷': ['clothing', 'clothes', 'dress', 'shirt', 'pants', 'jacket']
            }
            
            # 의도 기반 프레임 검색
            if intent == 'color_search':
                print("🎨 색상 검색 모드")
                detected_colors = []
                for color_korean, color_terms in color_keywords.items():
                    if any(term in message_lower for term in color_terms):
                        detected_colors.append(color_korean)
                        print(f"🎨 색상 검색 감지: {color_korean}")
                
                if detected_colors:
                    print(f"🎨 색상 검색 모드: {detected_colors}")
                    print(f"🔍 검색할 프레임 수: {len(frame_results)}")
                    for frame in frame_results:
                        persons = frame.get('persons', [])
                        
                        # 색상 분석 결과 확인
                        dominant_colors = frame.get('dominant_colors', [])
                        color_match_found = False
                        
                        # 요청된 색상과 매칭되는지 확인 (더 유연한 매칭)
                        for detected_color in detected_colors:
                            for color_info in dominant_colors:
                                color_name = color_info.get('color', '').lower()
                                detected_color_lower = detected_color.lower()
                                
                                # 색상 키워드 매핑을 통한 매칭
                                color_mapping = {
                                    '분홍색': 'pink', '핑크': 'pink',
                                    '빨간색': 'red', '빨강': 'red',
                                    '파란색': 'blue', '파랑': 'blue',
                                    '노란색': 'yellow', '노랑': 'yellow',
                                    '초록색': 'green', '녹색': 'green',
                                    '보라색': 'purple', '자주색': 'purple',
                                    '검은색': 'black', '검정': 'black',
                                    '흰색': 'white', '하양': 'white',
                                    '회색': 'gray', 'grey': 'gray',
                                    '주황색': 'orange', '오렌지': 'orange',
                                    '갈색': 'brown', '브라운': 'brown'
                                }
                                
                                # 매핑된 색상으로 비교
                                mapped_color = color_mapping.get(detected_color_lower, detected_color_lower)
                                
                                # 더 유연한 색상 매칭 (색상이 없어도 일단 포함)
                                if (mapped_color == color_name or 
                                    detected_color_lower == color_name or 
                                    detected_color_lower in color_name or 
                                    color_name in detected_color_lower or
                                    len(dominant_colors) == 0):  # 색상 정보가 없어도 포함
                                    color_match_found = True
                                    print(f"✅ 색상 매칭 발견: {detected_color} -> {color_info}")
                                    break
                            if color_match_found:
                                break
                        
                        # 디버깅을 위한 로그 추가
                        print(f"🔍 프레임 {frame.get('image_id', 0)} 색상 분석:")
                        print(f"  - 요청된 색상: {detected_colors}")
                        print(f"  - 감지된 색상: {[c.get('color', '') for c in dominant_colors]}")
                        print(f"  - 매칭 결과: {color_match_found}")
                        
                        # 색상 검색의 경우 색상 매칭이 된 프레임만 포함
                        if color_match_found:
                            frame_image_path = frame.get('frame_image_path', '')
                            actual_image_path = None
                            if frame_image_path:
                                # 실제 파일 시스템 경로 생성
                                import os
                                from django.conf import settings
                                actual_image_path = os.path.join(settings.MEDIA_ROOT, frame_image_path)
                                if os.path.exists(actual_image_path):
                                    print(f"✅ 실제 이미지 파일 존재: {actual_image_path}")
                                else:
                                    print(f"❌ 실제 이미지 파일 없음: {actual_image_path}")
                            
                            frame_info = {
                                'image_id': frame.get('image_id', 0),
                                'timestamp': frame.get('timestamp', 0),
                                'frame_image_path': frame_image_path,
                                'image_url': f'/media/{frame_image_path}',
                                'actual_image_path': actual_image_path,  # 실제 파일 경로 추가
                                'persons': persons,
                                'objects': frame.get('objects', []),
                                'scene_attributes': frame.get('scene_attributes', {}),
                                'dominant_colors': dominant_colors,  # 색상 분석 결과 추가
                                'relevance_score': 2,  # 색상 매칭 시 높은 점수
                                'color_search_info': {
                                    'requested_colors': detected_colors,
                                    'color_info_available': len(dominant_colors) > 0,
                                    'color_match_found': color_match_found,
                                    'actual_image_available': actual_image_path is not None,
                                    'message': f"색상 분석 결과: {dominant_colors} | 요청하신 색상: {', '.join(detected_colors)}"
                                }
                            }
                            relevant_frames.append(frame_info)
                            print(f"✅ 프레임 {frame_info['image_id']} 추가 (색상 매칭 성공)")
                        else:
                            print(f"❌ 프레임 {frame.get('image_id', 0)}: 색상 매칭 실패 - {detected_colors} vs {dominant_colors}")
                
                else:
                    print("🎨 색상 키워드 감지 실패 - 일반 검색으로 전환")
                    # 색상 키워드가 감지되지 않으면 모든 프레임 포함
                    for frame in frame_results:
                        persons = frame.get('persons', [])
                        if persons:  # 사람이 있는 프레임만
                            frame_info = {
                                'image_id': frame.get('image_id', 0),
                                'timestamp': frame.get('timestamp', 0),
                                'frame_image_path': frame.get('frame_image_path', ''),
                                'image_url': f'/media/{frame.get("frame_image_path", "")}',
                                'persons': persons,
                                'objects': frame.get('objects', []),
                                'scene_attributes': frame.get('scene_attributes', {}),
                                'relevance_score': len(persons)
                            }
                            relevant_frames.append(frame_info)
                            print(f"✅ 프레임 {frame_info['image_id']} 추가 (일반 검색, 사람 {len(persons)}명)")
            
            elif intent == 'person_search':
                print("👤 사람 검색 모드")
                print(f"🔍 검색할 프레임 수: {len(frame_results)}")
                for frame in frame_results:
                    persons = frame.get('persons', [])
                    print(f"🔍 프레임 {frame.get('image_id', 0)}: persons = {persons}")
                    # 사람이 감지된 프레임만 포함
                    if persons and len(persons) > 0:
                        frame_info = {
                            'image_id': frame.get('image_id', 0),
                            'timestamp': frame.get('timestamp', 0),
                            'frame_image_path': frame.get('frame_image_path', ''),
                            'image_url': f'/media/{frame.get("frame_image_path", "")}',
                            'persons': persons,
                            'objects': frame.get('objects', []),
                            'scene_attributes': frame.get('scene_attributes', {}),
                            'relevance_score': len(persons) * 2  # 사람 수에 비례한 점수
                        }
                        relevant_frames.append(frame_info)
                        print(f"✅ 프레임 {frame_info['image_id']} 추가 (사람 {len(persons)}명 감지)")
                        print(f"✅ 프레임 상세 정보: {frame_info}")
                    else:
                        print(f"❌ 프레임 {frame.get('image_id', 0)}: 사람 감지 안됨")
            
            elif intent == 'video_summary':
                print("📋 요약 모드 - 주요 프레임 선택")
                # 활동 수준이 높은 프레임 우선 선택
                frame_scores = []
                for frame in frame_results:
                    scene_attrs = frame.get('scene_attributes', {})
                    activity_level = scene_attrs.get('activity_level', 'low')
                    person_count = len(frame.get('persons', []))
                    
                    score = 0
                    if activity_level == 'high':
                        score += 3
                    elif activity_level == 'medium':
                        score += 2
                    else:
                        score += 1
                    
                    score += min(person_count, 3)  # 사람 수에 따른 점수
                    frame_scores.append((frame, score))
                
                # 점수 순으로 정렬하여 상위 프레임 선택
                frame_scores.sort(key=lambda x: x[1], reverse=True)
                for frame, score in frame_scores[:3]:
                    frame_info = {
                        'image_id': frame.get('image_id', 0),
                        'timestamp': frame.get('timestamp', 0),
                        'frame_image_path': frame.get('frame_image_path', ''),
                        'image_url': f'/media/{frame.get("frame_image_path", "")}',
                        'persons': frame.get('persons', []),
                        'objects': frame.get('objects', []),
                        'scene_attributes': frame.get('scene_attributes', {}),
                        'relevance_score': score
                    }
                    relevant_frames.append(frame_info)
                    print(f"✅ 프레임 {frame_info['image_id']} 추가 (요약용, 점수: {score})")
            
            elif intent == 'temporal_analysis':
                print("⏰ 시간대 분석 모드")
                # 시간 범위 파싱
                time_range = self._parse_time_range(message)
                if time_range:
                    start_time, end_time = time_range
                    print(f"⏰ 시간 범위: {start_time}초 ~ {end_time}초")
                    for frame in frame_results:
                        timestamp = frame.get('timestamp', 0)
                        if start_time <= timestamp <= end_time:
                            frame_info = {
                                'image_id': frame.get('image_id', 0),
                                'timestamp': frame.get('timestamp', 0),
                                'frame_image_path': frame.get('frame_image_path', ''),
                                'image_url': f'/media/{frame.get("frame_image_path", "")}',
                                'persons': frame.get('persons', []),
                                'objects': frame.get('objects', []),
                                'scene_attributes': frame.get('scene_attributes', {}),
                                'relevance_score': 1
                            }
                            relevant_frames.append(frame_info)
                            print(f"✅ 프레임 {frame_info['image_id']} 추가 (시간대: {timestamp}초)")
                else:
                    # 시간 범위를 파싱할 수 없는 경우 전체 프레임
                    relevant_frames = [{
                        'image_id': frame.get('image_id', 0),
                        'timestamp': frame.get('timestamp', 0),
                        'frame_image_path': frame.get('frame_image_path', ''),
                        'image_url': f'/media/{frame.get("frame_image_path", "")}',
                        'persons': frame.get('persons', []),
                        'objects': frame.get('objects', []),
                        'scene_attributes': frame.get('scene_attributes', {}),
                        'relevance_score': 1
                    } for frame in frame_results]
                    print(f"✅ 시간 범위 파싱 실패 - 전체 프레임 {len(relevant_frames)}개 선택")
            
            else:
                print("📋 일반 검색 모드")
                # 처음 2개 프레임 선택
                for frame in frame_results[:2]:
                    frame_info = {
                        'image_id': frame.get('image_id', 0),
                        'timestamp': frame.get('timestamp', 0),
                        'frame_image_path': frame.get('frame_image_path', ''),
                        'image_url': f'/media/{frame.get("frame_image_path", "")}',
                        'persons': frame.get('persons', []),
                        'objects': frame.get('objects', []),
                        'scene_attributes': frame.get('scene_attributes', {}),
                        'relevance_score': 1
                    }
                    relevant_frames.append(frame_info)
                    print(f"✅ 프레임 {frame_info['image_id']} 추가 (일반 검색)")
            
            # 관련도 점수순으로 정렬하고 상위 3개만 반환
            relevant_frames.sort(key=lambda x: x['relevance_score'], reverse=True)
            result = relevant_frames[:3]
            print(f"🎯 최종 선택된 프레임 수: {len(result)}")
            print(f"🎯 최종 프레임 상세: {result}")
            return result
            
        except Exception as e:
            print(f"❌ 프레임 검색 실패: {e}")
            return []
    
    def _handle_special_commands(self, message, video_id):
        """특별 명령어 처리 (요약, 하이라이트)"""
        try:
            message_lower = message.lower().strip()
            
            # 영상 요약 명령어
            if any(keyword in message_lower for keyword in ['요약', 'summary', '영상 요약', '영상 요약해줘', '영상 하이라이트 알려줘']):
                return self._handle_video_summary_command(message_lower, video_id)
            
            # 영상 하이라이트 명령어
            elif any(keyword in message_lower for keyword in ['하이라이트', 'highlight', '주요 장면', '중요한 장면']):
                return self._handle_video_highlight_command(message_lower, video_id)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 특별 명령어 처리 오류: {e}")
            return None
    
    def _handle_video_summary_command(self, message, video_id):
        """영상 요약 명령어 처리"""
        try:
            # 요약 타입 결정
            summary_type = 'comprehensive'
            if '간단' in message or 'brief' in message:
                summary_type = 'brief'
            elif '상세' in message or 'detailed' in message:
                summary_type = 'detailed'
            
            # VideoSummaryView 인스턴스 생성 및 요약 생성
            summary_view = VideoSummaryView()
            summary_result = summary_view._generate_video_summary(
                Video.objects.get(id=video_id), 
                summary_type
            )
            
            if summary_result and summary_result.get('summary'):
                return f"📝 **영상 요약** ({summary_type})\n\n{summary_result['summary']}"
            else:
                return "❌ 영상 요약을 생성할 수 없습니다. 영상 분석이 완료되었는지 확인해주세요."
                
        except Exception as e:
            logger.error(f"❌ 영상 요약 명령어 처리 오류: {e}")
            return f"❌ 영상 요약 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _handle_video_highlight_command(self, message, video_id):
        """영상 하이라이트 명령어 처리"""
        try:
            # 하이라이트 기준 설정
            criteria = {
                'min_score': 2.0,
                'max_highlights': 5
            }
            
            if '많이' in message or 'more' in message:
                criteria['max_highlights'] = 10
            elif '적게' in message or 'few' in message:
                criteria['max_highlights'] = 3
            
            # VideoHighlightView 인스턴스 생성 및 하이라이트 추출
            highlight_view = VideoHighlightView()
            highlights = highlight_view._extract_highlights(
                Video.objects.get(id=video_id), 
                criteria
            )
            
            if highlights:
                highlight_text = "🎬 **영상 하이라이트**\n\n"
                for i, highlight in enumerate(highlights, 1):
                    highlight_text += f"{i}. **{highlight['timestamp']:.1f}초** - {highlight['description']}\n"
                    highlight_text += f"   - 중요도: {highlight['significance']} (점수: {highlight['score']:.1f})\n"
                    highlight_text += f"   - 인원: {highlight['person_count']}명, 장면: {highlight['scene_type']}\n\n"
                
                return highlight_text
            else:
                return "❌ 하이라이트를 찾을 수 없습니다. 영상 분석이 완료되었는지 확인해주세요."
                
        except Exception as e:
            logger.error(f"❌ 영상 하이라이트 명령어 처리 오류: {e}")
            return f"❌ 영상 하이라이트 생성 중 오류가 발생했습니다: {str(e)}"

