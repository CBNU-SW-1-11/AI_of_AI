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


class VideoUploadView(APIView):
    """영상 업로드 뷰 - 독립적인 영상 처리"""
    permission_classes = [AllowAny]  # 임시로 AllowAny로 변경
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request):
        try:
            import os
            import uuid
            import time
            from django.core.files.storage import default_storage
            from django.conf import settings
            
            # 업로드된 파일 확인 (backend_videochat 방식)
            if 'video' not in request.FILES:
                return Response({
                    'error': '비디오 파일이 없습니다'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            video_file = request.FILES['video']
            
            # 파일 확장자 검증 (backend_videochat 방식)
            if not video_file.name.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                return Response({
                    'error': '지원하지 않는 파일 형식입니다. MP4, AVI, MOV, MKV, WEBM 형식만 지원됩니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 파일 크기 검증 (50MB 제한)
            max_size = 50 * 1024 * 1024  # 50MB
            if video_file.size > max_size:
                return Response({
                    'error': f'파일 크기가 너무 큽니다. 최대 50MB까지 업로드 가능합니다. (현재: {video_file.size / (1024*1024):.1f}MB)'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 파일명 길이 검증
            if len(video_file.name) > 200:
                return Response({
                    'error': '파일명이 너무 깁니다. 200자 이하로 제한됩니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 고유한 파일명 생성 (backend_videochat 방식)
            timestamp = int(time.time())
            filename = f"upload_{timestamp}_{video_file.name}"
            
            # 파일 저장 (backend_videochat 방식)
            from django.core.files.base import ContentFile
            file_path = default_storage.save(
                f'uploads/{filename}',
                ContentFile(video_file.read())
            )
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            
            # 파일 저장 검증
            if not os.path.exists(full_path):
                return Response({
                    'error': '파일 저장에 실패했습니다. 다시 시도해주세요.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 파일 크기 재검증 (실제 저장된 파일)
            actual_size = os.path.getsize(full_path)
            if actual_size == 0:
                return Response({
                    'error': '빈 파일이 업로드되었습니다. 유효한 영상 파일을 선택해주세요.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create Video model instance (backend_videochat 방식)
            video = Video.objects.create(
                filename=filename,
                original_name=video_file.name,
                file_path=file_path,
                file_size=video_file.size,
                file=file_path,  # file 필드도 저장
                analysis_status='pending'
            )
            
            # 백그라운드에서 영상 분석 시작
            def analyze_video_background():
                try:
                    print(f"🎬 백그라운드 영상 분석 시작: {video.id}")
                    
                    # 파일 존재 여부 재확인
                    if not os.path.exists(full_path):
                        print(f"❌ 영상 파일이 존재하지 않음: {full_path}")
                        video.analysis_status = 'failed'
                        video.analysis_message = '영상 파일을 찾을 수 없습니다.'
                        video.save()
                        return
                    
                    analysis_result = video_analysis_service.analyze_video(file_path, video.id)
                    if analysis_result and analysis_result is not True:
                        # 분석 결과가 딕셔너리인 경우 (오류 정보 포함)
                        if isinstance(analysis_result, dict) and not analysis_result.get('success', True):
                            print(f"❌ 영상 분석 실패: {video.id} - {analysis_result.get('error_message', 'Unknown error')}")
                            video.analysis_status = 'failed'
                            video.analysis_message = analysis_result.get('error_message', '분석 중 오류가 발생했습니다.')
                        else:
                            print(f"✅ 영상 분석 완료: {video.id}")
                            video.analysis_status = 'completed'
                            video.is_analyzed = True
                    else:
                        print(f"❌ 영상 분석 실패: {video.id}")
                        video.analysis_status = 'failed'
                        video.analysis_message = '분석 중 오류가 발생했습니다.'
                    
                    video.save()
                except Exception as e:
                    print(f"❌ 백그라운드 분석 오류: {e}")
                    video.analysis_status = 'failed'
                    video.analysis_message = f'분석 중 오류가 발생했습니다: {str(e)}'
                    video.save()
            
            # 별도 스레드에서 분석 실행
            analysis_thread = threading.Thread(target=analyze_video_background)
            analysis_thread.daemon = True
            analysis_thread.start()
            
            return Response({
                'success': True,
                'video_id': video.id,
                'filename': filename,
                'message': f'비디오 "{video_file.name}"이 성공적으로 업로드되었습니다.'
            })
                
        except Exception as e:
            return Response({
                'error': f'영상 업로드 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VideoListView(APIView):
    """비디오 목록 조회 - backend_videochat 방식"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            videos = Video.objects.all()
            video_list = []
            
            for video in videos:
                # 상태 동기화 수행 (파일과 DB 상태 일치 확인)
                video_analysis_service.sync_video_status_with_files(video.id)
                
                # 동기화 후 최신 상태로 다시 가져오기
                video.refresh_from_db()
                
                # 분석 상태 결정 (더 정확한 판단)
                actual_analysis_status = video.analysis_status
                if video.analysis_status == 'completed' and not video.analysis_json_path:
                    actual_analysis_status = 'failed'
                    print(f"⚠️ 영상 {video.id}: analysis_status는 completed이지만 analysis_json_path가 없음")
                
                video_data = {
                    'id': video.id,
                    'filename': video.filename,
                    'original_name': video.original_name,
                    'duration': video.duration,
                    'is_analyzed': video.is_analyzed,
                    'analysis_status': actual_analysis_status,  # 실제 상태 사용
                    'uploaded_at': video.uploaded_at,
                    'file_size': video.file_size,
                    'analysis_progress': video.analysis_progress,  # 진행률 정보 추가
                    'analysis_message': video.analysis_message or ''  # 분석 메시지 추가
                }
                video_list.append(video_data)
            
            return Response({
                'videos': video_list,
                'count': len(video_list)
            })
            
        except Exception as e:
            return Response({
                'error': f'비디오 목록 조회 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VideoDeleteView(APIView):
    """영상 삭제 API"""
    permission_classes = [AllowAny]
    
    def delete(self, request, video_id):
        try:
            video = Video.objects.get(id=video_id)
            
            # 파일 삭제
            if video.file and os.path.exists(video.file.path):
                try:
                    os.remove(video.file.path)
                    logger.info(f"✅ 영상 파일 삭제: {video.file.path}")
                except Exception as e:
                    logger.warning(f"영상 파일 삭제 실패: {e}")
            
            # 분석 결과 파일 삭제
            if video.analysis_json_path:
                json_path = os.path.join(settings.MEDIA_ROOT, video.analysis_json_path)
                if os.path.exists(json_path):
                    try:
                        os.remove(json_path)
                        logger.info(f"✅ 분석 결과 파일 삭제: {json_path}")
                    except Exception as e:
                        logger.warning(f"분석 결과 파일 삭제 실패: {e}")
            
            # 프레임 이미지 파일 삭제
            if video.frame_images_path:
                frame_paths = video.frame_images_path.split(',')
                for path in frame_paths:
                    full_path = os.path.join(settings.MEDIA_ROOT, path.strip())
                    if os.path.exists(full_path):
                        try:
                            os.remove(full_path)
                        except Exception as e:
                            logger.warning(f"프레임 이미지 삭제 실패: {e}")
            
            # DB에서 삭제
            video_name = video.original_name
            video.delete()
            
            logger.info(f"✅ 영상 삭제 완료: {video_name} (ID: {video_id})")
            
            return Response({
                'message': f'영상 "{video_name}"이(가) 삭제되었습니다.',
                'video_id': video_id
            })
            
        except Video.DoesNotExist:
            return Response({
                'error': '영상을 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"❌ 영상 삭제 오류: {e}")
            return Response({
                'error': f'영상 삭제 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VideoRenameView(APIView):
    """영상 이름 변경 API"""
    permission_classes = [AllowAny]
    
    def post(self, request, video_id):
        try:
            video = Video.objects.get(id=video_id)
            new_name = request.data.get('original_name', '').strip()
            
            if not new_name:
                return Response({
                    'error': '새 이름을 입력해주세요.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            old_name = video.original_name
            video.original_name = new_name
            video.save()
            
            logger.info(f"✅ 영상 이름 변경: {old_name} → {new_name} (ID: {video_id})")
            
            return Response({
                'message': f'영상 이름이 "{new_name}"(으)로 변경되었습니다.',
                'video_id': video_id,
                'new_name': new_name
            })
            
        except Video.DoesNotExist:
            return Response({
                'error': '영상을 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"❌ 영상 이름 변경 오류: {e}")
            return Response({
                'error': f'영상 이름 변경 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FrameImageView(APIView):
    """프레임 이미지 서빙"""
    permission_classes = [AllowAny]
    
    def get(self, request, video_id, frame_number):
        try:
            from django.conf import settings
            # 프레임 이미지 경로 생성
            frame_filename = f"video{video_id}_frame{frame_number}.jpg"
            frame_path = os.path.join(settings.MEDIA_ROOT, 'images', frame_filename)
            
            # 파일이 존재하는지 확인
            if not os.path.exists(frame_path):
                raise Http404("프레임 이미지를 찾을 수 없습니다")
            
            # 이미지 파일 읽기
            with open(frame_path, 'rb') as f:
                image_data = f.read()
            
            # HTTP 응답으로 이미지 반환
            response = HttpResponse(image_data, content_type='image/jpeg')
            response['Content-Disposition'] = f'inline; filename="{frame_filename}"'
            return response
            
        except Exception as e:
            return Response({
                'error': f'프레임 이미지 로드 실패: {str(e)}'
            }, status=status.HTTP_404_NOT_FOUND)

