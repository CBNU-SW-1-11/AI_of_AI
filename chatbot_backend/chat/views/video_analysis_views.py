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


class VideoAnalysisView(APIView):
    """영상 분석 상태 확인 및 시작 - backend_videochat 방식"""
    permission_classes = [AllowAny]
    
    def get(self, request, video_id):
        try:
            video = Video.objects.get(id=video_id)
            
            # 상태 동기화 수행 (파일과 DB 상태 일치 확인)
            video_analysis_service.sync_video_status_with_files(video_id)
            
            # 동기화 후 최신 상태로 다시 가져오기
            video.refresh_from_db()
            
            # 진행률 정보 추출
            progress_info = {
                'analysis_progress': video.analysis_progress,
                'analysis_message': video.analysis_message or ''
            }
            
            # 분석 상태 결정 (더 정확한 판단)
            actual_analysis_status = video.analysis_status
            if video.analysis_status == 'completed' and not video.analysis_json_path:
                actual_analysis_status = 'failed'
                print(f"⚠️ 영상 {video_id}: analysis_status는 completed이지만 analysis_json_path가 없음")
            
            return Response({
                'video_id': video.id,
                'filename': video.filename,
                'original_name': video.original_name,
                'analysis_status': actual_analysis_status,  # 실제 상태 사용
                'is_analyzed': video.is_analyzed,
                'duration': video.duration,
                'progress': progress_info,  # 프론트엔드가 기대하는 구조로 변경
                'uploaded_at': video.uploaded_at,
                'file_size': video.file_size,
                'analysis_json_path': video.analysis_json_path,
                'frame_images_path': video.frame_images_path
            })
        except Video.DoesNotExist:
            return Response({
                'error': '영상을 찾을 수 없습니다'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'영상 분석 조회 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, video_id):
        """영상 분석 시작"""
        try:
            video = Video.objects.get(id=video_id)
            
            # 이미 분석 중이거나 완료된 경우
            if video.analysis_status == 'pending':
                return Response({
                    'message': '이미 분석이 진행 중입니다.',
                    'status': 'pending'
                })
            elif video.analysis_status == 'completed':
                return Response({
                    'message': '이미 분석이 완료되었습니다.',
                    'status': 'completed'
                })
            
            # 분석 상태를 pending으로 변경
            video.analysis_status = 'pending'
            video.save()
            
            # 백그라운드에서 영상 분석 시작
            def analyze_video_background():
                try:
                    print(f"🎬 백그라운드 영상 분석 시작: {video.id}")
                    analysis_result = video_analysis_service.analyze_video(video.file_path, video.id)
                    if analysis_result:
                        print(f"✅ 영상 분석 완료: {video.id}")
                        # Video 모델 업데이트
                        video.analysis_status = 'completed'
                        video.is_analyzed = True
                        video.save()
                    else:
                        print(f"❌ 영상 분석 실패: {video.id}")
                        video.analysis_status = 'failed'
                        video.save()
                except Exception as e:
                    print(f"❌ 백그라운드 분석 오류: {e}")
                    video.analysis_status = 'failed'
                    video.save()
            
            # 별도 스레드에서 분석 실행
            analysis_thread = threading.Thread(target=analyze_video_background)
            analysis_thread.daemon = True
            analysis_thread.start()
            
            return Response({
                'message': '영상 분석을 시작했습니다.',
                'status': 'pending'
            })
            
        except Video.DoesNotExist:
            return Response({
                'error': '영상을 찾을 수 없습니다'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'영상 분석 시작 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VideoSummaryView(APIView):
    """영상 요약 기능"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            video_id = request.data.get('video_id')
            summary_type = request.data.get('summary_type', 'comprehensive')  # comprehensive, brief, detailed
            
            logger.info(f"📝 영상 요약 요청: 비디오={video_id}, 타입={summary_type}")
            
            if not video_id:
                return Response({'error': '비디오 ID가 필요합니다.'}, status=400)
            
            try:
                video = Video.objects.get(id=video_id)
            except Video.DoesNotExist:
                return Response({'error': '비디오를 찾을 수 없습니다.'}, status=404)
            
            # 영상 요약 생성
            summary_result = self._generate_video_summary(video, summary_type)
            
            return Response({
                'video_id': video_id,
                'video_name': video.original_name,
                'summary_type': summary_type,
                'summary_result': summary_result,
                'analysis_type': 'video_summary'
            })
            
        except Exception as e:
            logger.error(f"❌ 영상 요약 오류: {e}")
            return Response({'error': str(e)}, status=500)
    
    def _generate_video_summary(self, video, summary_type):
        """영상 요약 생성"""
        try:
            # 분석 결과 JSON 파일 읽기
            if not video.analysis_json_path:
                return {
                    'summary': '분석 결과가 없습니다. 영상 분석을 먼저 완료해주세요.',
                    'key_events': [],
                    'statistics': {},
                    'duration': video.duration,
                    'frame_count': 0
                }
            
            json_path = os.path.join(settings.MEDIA_ROOT, video.analysis_json_path)
            if not os.path.exists(json_path):
                return {
                    'summary': '분석 결과 파일을 찾을 수 없습니다.',
                    'key_events': [],
                    'statistics': {},
                    'duration': video.duration,
                    'frame_count': 0
                }
            
            with open(json_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            # 기본 통계 수집
            statistics = self._collect_video_statistics(video, analysis_data)
            
            # 키 이벤트 추출
            key_events = self._extract_key_events(analysis_data)
            
            # 요약 타입에 따른 처리
            if summary_type == 'brief':
                summary_text = self._generate_brief_summary(statistics, key_events)
            elif summary_type == 'detailed':
                summary_text = self._generate_detailed_summary(statistics, key_events, analysis_data)
            else:  # comprehensive
                summary_text = self._generate_comprehensive_summary(statistics, key_events, analysis_data)
            
            return {
                'summary': summary_text,
                'key_events': key_events,
                'statistics': statistics,
                'duration': video.duration,
                'frame_count': len(analysis_data.get('frame_results', [])),
                'summary_type': summary_type
            }
            
        except Exception as e:
            logger.error(f"❌ 영상 요약 생성 오류: {e}")
            return {
                'summary': f'요약 생성 중 오류가 발생했습니다: {str(e)}',
                'key_events': [],
                'statistics': {},
                'duration': video.duration,
                'frame_count': 0
            }
    
    def _collect_video_statistics(self, video, analysis_data):
        """영상 통계 수집 - 💡핵심 인사이트 포함"""
        try:
            video_summary = analysis_data.get('video_summary', {})
            frame_results = analysis_data.get('frame_results', [])
            
            # 기본 통계
            stats = {
                'total_duration': video.duration,
                'total_frames': len(frame_results),
                'total_detections': video_summary.get('total_detections', 0),
                'unique_persons': video_summary.get('unique_persons', 0),
                'quality_score': video_summary.get('quality_assessment', {}).get('overall_score', 0),
                'scene_diversity': video_summary.get('scene_diversity', {}).get('diversity_score', 0)
            }
            
            # 시간대별 활동 분석
            temporal_analysis = video_summary.get('temporal_analysis', {})
            stats.update({
                'peak_time': temporal_analysis.get('peak_time_seconds', 0),
                'peak_person_count': temporal_analysis.get('peak_person_count', 0),
                'average_person_count': temporal_analysis.get('average_person_count', 0)
            })
            
            # 장면 특성 분석
            scene_distribution = video_summary.get('scene_diversity', {})
            stats.update({
                'scene_types': scene_distribution.get('scene_type_distribution', {}),
                'activity_levels': scene_distribution.get('activity_level_distribution', {}),
                'lighting_types': scene_distribution.get('lighting_distribution', {})
            })
            
            # 💡 핵심 인사이트 생성
            stats['key_insights'] = self._generate_key_insights_for_summary(stats, frame_results)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 통계 수집 오류: {e}")
            return {}
    
    def _generate_key_insights_for_summary(self, stats, frame_results):
        """💡 핵심 인사이트 생성 (영상 요약용)"""
        insights = []
        
        try:
            # 1. 인원 구성 인사이트
            person_count = stats.get('unique_persons', 0)
            peak_count = stats.get('peak_person_count', 0)
            
            if person_count > 0:
                if peak_count > 5:
                    insights.append(f"다수 인원 등장 (최대 {peak_count}명 동시 등장)")
                elif peak_count > 2:
                    insights.append(f"소규모 그룹 활동 ({peak_count}명)")
                else:
                    insights.append(f"소수 인원 영상 ({person_count}명)")
            
            # 2. 영상 길이 인사이트
            duration = stats.get('total_duration', 0)
            if duration > 300:  # 5분 이상
                insights.append(f"긴 영상 ({duration/60:.1f}분)")
            elif duration > 60:
                insights.append(f"중간 길이 영상 ({duration/60:.1f}분)")
            else:
                insights.append(f"짧은 영상 ({duration:.0f}초)")
            
            # 3. 품질 인사이트
            quality_score = stats.get('quality_score', 0)
            if quality_score > 0.8:
                insights.append(f"높은 품질 (점수: {quality_score:.2f})")
            elif quality_score > 0.6:
                insights.append(f"양호한 품질 (점수: {quality_score:.2f})")
            elif quality_score > 0:
                insights.append(f"보통 품질 (점수: {quality_score:.2f})")
            
            # 4. 장면 다양성 인사이트
            scene_types = stats.get('scene_types', {})
            if len(scene_types) > 3:
                insights.append(f"다양한 장면 포함 ({len(scene_types)}가지 장소)")
            elif len(scene_types) > 0:
                main_scenes = list(scene_types.keys())[:2]
                insights.append(f"주요 장소: {', '.join(main_scenes)}")
            
            # 5. 활동 수준 인사이트
            activity_levels = stats.get('activity_levels', {})
            if 'high' in activity_levels:
                insights.append(f"활발한 활동 감지")
            elif 'medium' in activity_levels:
                insights.append(f"중간 수준 활동")
            
            return insights[:5]  # 최대 5개 인사이트
            
        except Exception as e:
            logger.error(f"❌ 핵심 인사이트 생성 오류: {e}")
            return ["영상 분석 완료"]
    
    def _extract_key_events(self, analysis_data):
        """키 이벤트 추출"""
        try:
            key_events = []
            frame_results = analysis_data.get('frame_results', [])
            
            # 사람 수가 많은 장면들을 키 이벤트로 선정
            for frame in frame_results:
                person_count = len(frame.get('persons', []))
                if person_count >= 2:  # 2명 이상이 있는 장면
                    key_events.append({
                        'timestamp': frame.get('timestamp', 0),
                        'description': f"{person_count}명이 감지된 장면",
                        'person_count': person_count,
                        'scene_type': frame.get('scene_attributes', {}).get('scene_type', 'unknown'),
                        'activity_level': frame.get('scene_attributes', {}).get('activity_level', 'medium')
                    })
            
            # 시간순으로 정렬
            key_events.sort(key=lambda x: x['timestamp'])
            
            return key_events[:10]  # 상위 10개만 반환
            
        except Exception as e:
            logger.error(f"❌ 키 이벤트 추출 오류: {e}")
            return []
    
    def _generate_brief_summary(self, statistics, key_events):
        """간단 요약 (1-2문장, 💡핵심만 강조)"""
        try:
            duration = statistics.get('total_duration', 0)
            duration_min = duration / 60
            person_count = statistics.get('unique_persons', 0)
            key_insights = statistics.get('key_insights', [])
            
            # 가장 중요한 핵심 1개 + 기본 정보
            main_insight = key_insights[0] if key_insights else "영상 분석 완료"
            
            return f"💡 {main_insight}. 영상 길이 {duration_min:.1f}분, 총 {person_count}명 등장."
            
        except Exception as e:
            logger.error(f"❌ 간단 요약 생성 오류: {e}")
            return "요약 생성 중 오류가 발생했습니다."
    
    def _generate_detailed_summary(self, statistics, key_events, analysis_data):
        """상세 요약 (문단 형식, 💡핵심 3개 + 주요 이벤트)"""
        try:
            duration = statistics.get('total_duration', 0)
            duration_min = duration / 60
            person_count = statistics.get('unique_persons', 0)
            peak_count = statistics.get('peak_person_count', 0)
            key_insights = statistics.get('key_insights', [])
            
            parts = [
                f"📹 이 영상은 {duration_min:.1f}분 길이로, 총 {person_count}명이 등장합니다.",
                "\n💡 핵심 포인트:",
                *[f"  • {insight}" for insight in key_insights[:3]]
            ]
            
            # 주요 이벤트 3개
            if key_events:
                parts.append("\n⏱️ 주요 장면:")
                for i, event in enumerate(key_events[:3], 1):
                    timestamp = event.get('timestamp', 0)
                    time_str = f"{int(timestamp//60)}:{int(timestamp%60):02d}"
                    desc = event.get('description', '장면')[:50]
                    parts.append(f"  {i}. [{time_str}] {desc}")
            
            # 품질 정보
            quality_score = statistics.get('quality_score', 0)
            if quality_score > 0:
                quality_status = "우수" if quality_score > 0.8 else "양호" if quality_score > 0.6 else "보통"
                parts.append(f"\n🎯 영상 품질: {quality_status} ({quality_score:.2f}/1.0)")
            
            # 장면 유형
            scene_types = statistics.get('scene_types', {})
            if scene_types:
                scene_list = [f"{k}({v})" for k, v in list(scene_types.items())[:3]]
                parts.append(f"\n🎬 장면 유형: {', '.join(scene_list)}")
            
            return "\n".join(parts)
            
        except Exception as e:
            logger.error(f"❌ 상세 요약 생성 오류: {e}")
            return "상세 요약 생성 중 오류가 발생했습니다."
    
    def _generate_comprehensive_summary(self, statistics, key_events, analysis_data):
        """종합 요약 (전체 분석, 💡핵심 5개 + 모든 이벤트 + 통계)"""
        try:
            duration = statistics.get('total_duration', 0)
            duration_min = duration / 60
            person_count = statistics.get('unique_persons', 0)
            peak_count = statistics.get('peak_person_count', 0)
            key_insights = statistics.get('key_insights', [])
            
            parts = [
                f"📹 영상 정보",
                f"  • 길이: {duration_min:.1f}분",
                f"  • 등장 인원: {person_count}명",
                f"  • 분석 프레임: {statistics.get('total_frames', 0)}개",
                f"  • 총 감지 객체: {statistics.get('total_detections', 0)}개",
                "\n💡 핵심 인사이트 (전체)"
            ]
            
            # 전체 핵심 인사이트 (최대 5개)
            parts.extend([f"  • {insight}" for insight in key_insights[:5]])
            
            # 주요 이벤트 전체 (최대 8개)
            if key_events:
                parts.append("\n⏱️ 주요 이벤트 타임라인:")
                for i, event in enumerate(key_events[:8], 1):
                    timestamp = event.get('timestamp', 0)
                    time_str = f"{int(timestamp//60)}:{int(timestamp%60):02d}"
                    desc = event.get('description', '장면')[:60]
                    person_cnt = event.get('person_count', 0)
                    activity = event.get('activity_level', 'medium')
                    emoji = "🔴" if activity == 'high' else "🟡" if activity == 'medium' else "🟢"
                    parts.append(f"  {emoji} {i}. [{time_str}] {desc} ({person_cnt}명)")
            
            # 상세 통계
            parts.append("\n📊 상세 통계:")
            parts.append(f"  • 최대 동시 인원: {peak_count}명")
            parts.append(f"  • 평균 동시 인원: {statistics.get('average_person_count', 0):.1f}명")
            
            # 품질 정보
            quality_score = statistics.get('quality_score', 0)
            if quality_score > 0:
                quality_status = "우수" if quality_score > 0.8 else "양호" if quality_score > 0.6 else "보통"
                parts.append(f"  • 영상 품질: {quality_status} ({quality_score:.2f}/1.0)")
            
            # 장면 분석
            scene_types = statistics.get('scene_types', {})
            if scene_types:
                scene_list = ', '.join([f"{k}({v})" for k, v in list(scene_types.items())[:5]])
                parts.append(f"  • 장면 유형: {scene_list}")
            
            activity_levels = statistics.get('activity_levels', {})
            if activity_levels:
                activity_list = ', '.join([f"{k}({v})" for k, v in activity_levels.items()])
                parts.append(f"  • 활동 수준: {activity_list}")
            
            lighting_types = statistics.get('lighting_types', {})
            if lighting_types:
                lighting_list = ', '.join([f"{k}({v})" for k, v in lighting_types.items()])
                parts.append(f"  • 조명 상태: {lighting_list}")
            
            # 다양성 점수
            diversity = statistics.get('scene_diversity', 0)
            if diversity > 0:
                parts.append(f"  • 장면 다양성: {diversity:.2f}/1.0")
            
            return "\n".join(parts)
            
        except Exception as e:
            logger.error(f"❌ 종합 요약 생성 오류: {e}")
            return "종합 요약 생성 중 오류가 발생했습니다."

class VideoHighlightView(APIView):
    """영상 하이라이트 자동 추출"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            video_id = request.data.get('video_id')
            highlight_criteria = request.data.get('criteria', {})
            
            logger.info(f"🎬 하이라이트 추출 요청: 비디오={video_id}, 기준={highlight_criteria}")
            
            if not video_id:
                return Response({'error': '비디오 ID가 필요합니다.'}, status=400)
            
            try:
                video = Video.objects.get(id=video_id)
            except Video.DoesNotExist:
                return Response({'error': '비디오를 찾을 수 없습니다.'}, status=404)
            
            # 하이라이트 추출
            highlights = self._extract_highlights(video, highlight_criteria)
            
            return Response({
                'video_id': video_id,
                'video_name': video.original_name,
                'highlights': highlights,
                'total_highlights': len(highlights),
                'analysis_type': 'video_highlights'
            })
            
        except Exception as e:
            logger.error(f"❌ 하이라이트 추출 오류: {e}")
            return Response({'error': str(e)}, status=500)
    
    def _extract_highlights(self, video, criteria):
        """하이라이트 추출"""
        try:
            # 분석 결과 JSON 파일 읽기
            if not video.analysis_json_path:
                return []
            
            json_path = os.path.join(settings.MEDIA_ROOT, video.analysis_json_path)
            if not os.path.exists(json_path):
                return []
            
            with open(json_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            frame_results = analysis_data.get('frame_results', [])
            if not frame_results:
                return []
            
            # 프레임별 점수 계산
            scored_frames = self._score_frames(frame_results, criteria)
            
            # 하이라이트 생성
            highlights = self._create_highlights(scored_frames, criteria)
            
            return highlights
            
        except Exception as e:
            logger.error(f"❌ 하이라이트 추출 오류: {e}")
            return []
    
    def _score_frames(self, frame_results, criteria):
        """프레임별 점수 계산"""
        try:
            scored_frames = []
            
            for frame in frame_results:
                score = 0.0
                
                # 사람 수 점수 (더 많은 사람 = 더 높은 점수)
                person_count = len(frame.get('persons', []))
                if person_count > 0:
                    score += person_count * 0.5
                
                # 품질 점수
                quality_score = self._get_quality_score(frame)
                score += quality_score * 0.3
                
                # 활동 수준 점수
                activity_level = frame.get('scene_attributes', {}).get('activity_level', 'medium')
                if activity_level == 'high':
                    score += 1.0
                elif activity_level == 'medium':
                    score += 0.5
                
                # 장면 다양성 점수
                scene_type = frame.get('scene_attributes', {}).get('scene_type', 'unknown')
                if scene_type in ['detailed', 'complex']:
                    score += 0.3
                
                # 신뢰도 점수
                avg_confidence = self._get_average_confidence(frame)
                score += avg_confidence * 0.2
                
                scored_frames.append({
                    'frame': frame,
                    'frame_id': frame.get('image_id', 0),
                    'timestamp': frame.get('timestamp', 0),
                    'score': score
                })
            
            # 점수순으로 정렬
            scored_frames.sort(key=lambda x: x['score'], reverse=True)
            
            return scored_frames
            
        except Exception as e:
            logger.error(f"❌ 프레임 점수 계산 오류: {e}")
            return []
    
    def _get_quality_score(self, frame):
        """프레임 품질 점수 계산"""
        try:
            # 간단한 품질 점수 계산 (실제로는 더 복잡한 알고리즘 사용 가능)
            persons = frame.get('persons', [])
            if not persons:
                return 0.0
            
            # 평균 신뢰도 기반 품질 점수
            confidences = [person.get('confidence', 0) for person in persons]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return avg_confidence
            
        except Exception as e:
            logger.error(f"❌ 품질 점수 계산 오류: {e}")
            return 0.0
    
    def _get_average_confidence(self, frame):
        """평균 신뢰도 계산"""
        try:
            persons = frame.get('persons', [])
            if not persons:
                return 0.0
            
            confidences = [person.get('confidence', 0) for person in persons]
            return sum(confidences) / len(confidences) if confidences else 0
            
        except Exception as e:
            logger.error(f"❌ 평균 신뢰도 계산 오류: {e}")
            return 0.0
    
    def _create_highlights(self, scored_frames, criteria):
        """하이라이트 생성"""
        try:
            highlights = []
            min_score = criteria.get('min_score', 2.0)  # 최소 점수
            max_highlights = criteria.get('max_highlights', 10)  # 최대 하이라이트 수
            
            # 점수 기준 필터링
            filtered_frames = [f for f in scored_frames if f['score'] >= min_score]
            
            # 시간 간격을 고려한 하이라이트 선택
            selected_highlights = []
            last_timestamp = -10  # 최소 10초 간격
            
            for frame_data in filtered_frames[:max_highlights * 2]:  # 여유분을 두고 선택
                if frame_data['timestamp'] - last_timestamp >= 10:  # 10초 이상 간격
                    selected_highlights.append(frame_data)
                    last_timestamp = frame_data['timestamp']
                    
                    if len(selected_highlights) >= max_highlights:
                        break
            
            # 하이라이트 정보 생성
            for i, frame_data in enumerate(selected_highlights):
                frame = frame_data['frame']
                highlight = {
                    'id': i + 1,
                    'timestamp': frame_data['timestamp'],
                    'frame_id': frame_data['frame_id'],
                    'score': frame_data['score'],
                    'description': self._generate_highlight_description(frame),
                    'person_count': len(frame.get('persons', [])),
                    'thumbnail_url': f'/api/frame/{frame.get("video_id", 0)}/{frame_data["frame_id"]}/',
                    'significance': self._get_significance_level(frame_data['score']),
                    'scene_type': frame.get('scene_attributes', {}).get('scene_type', 'unknown'),
                    'activity_level': frame.get('scene_attributes', {}).get('activity_level', 'medium')
                }
                highlights.append(highlight)
            
            return highlights
            
        except Exception as e:
            logger.error(f"❌ 하이라이트 생성 오류: {e}")
            return []
    
    def _generate_highlight_description(self, frame):
        """하이라이트 설명 생성"""
        try:
            persons = frame.get('persons', [])
            person_count = len(persons)
            
            if person_count == 0:
                return "주요 장면"
            elif person_count == 1:
                return "1명이 등장하는 장면"
            elif person_count <= 3:
                return f"{person_count}명이 등장하는 장면"
            else:
                return f"{person_count}명이 등장하는 활발한 장면"
                
        except Exception as e:
            logger.error(f"❌ 하이라이트 설명 생성 오류: {e}")
            return "주요 장면"
    
    def _get_significance_level(self, score):
        """중요도 레벨 반환"""
        try:
            if score >= 4.0:
                return "매우 높음"
            elif score >= 3.0:
                return "높음"
            elif score >= 2.0:
                return "보통"
            else:
                return "낮음"
                
        except Exception as e:
            logger.error(f"❌ 중요도 레벨 계산 오류: {e}")
            return "보통"
    
    def _handle_special_commands(self, message, video_id):
        """특별 명령어 처리 (AI별 개별 답변 생성)"""
        try:
            message_lower = message.lower().strip()
            print(f"🔍 특별 명령어 검사: '{message_lower}'")
            
            # 영상 요약 명령어
            if any(keyword in message_lower for keyword in ['요약', 'summary', '영상 요약', '영상 요약해줘', '영상 하이라이트 알려줘', '간단한 요약', '상세한 요약']):
                print(f"✅ 영상 요약 명령어 감지: '{message_lower}'")
                return self._handle_ai_generated_response(video_id, 'video_summary', message_lower)
            
            # 영상 하이라이트 명령어
            elif any(keyword in message_lower for keyword in ['하이라이트', 'highlight', '주요 장면', '중요한 장면']):
                return self._handle_ai_generated_response(video_id, 'video_highlights', message_lower)
            
            # 사람 찾기 명령어
            elif any(keyword in message_lower for keyword in ['사람 찾아줘', '사람 찾기', '인물 검색', '사람 검색']):
                return self._handle_ai_generated_response(video_id, 'person_search', message_lower)
            
            # 영상 간 검색 명령어
            elif any(keyword in message_lower for keyword in ['비가오는 밤', '비 오는 밤', '밤에 촬영', '어두운 영상', '비 오는 날']):
                return self._handle_ai_generated_response(video_id, 'inter_video_search', {'query': message_lower})
            
            # 영상 내 검색 명령어
            elif any(keyword in message_lower for keyword in ['주황색 상의', '주황 옷', '주황색 옷', '주황 상의', '오렌지 옷']):
                return self._handle_ai_generated_response(video_id, 'intra_video_search', {'query': message_lower})
            
            # 시간대별 분석 명령어
            elif any(keyword in message_lower for keyword in ['성비 분포', '성별 분포', '남녀 비율', '시간대별', '3시', '5시']):
                time_range = {'start': 180, 'end': 300}  # 기본값: 3분-5분
                return self._handle_ai_generated_response(video_id, 'temporal_analysis', {'time_range': time_range})
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 특별 명령어 처리 오류: {e}")
            return None
    
    def _handle_ai_generated_response(self, video_id, query_type, query_data=None):
        """AI별 개별 답변 생성 및 통합"""
        try:
            logger.info(f"🤖 AI 응답 생성 시작: video_id={video_id}, query_type={query_type}")
            
            # AI 응답 생성
            ai_responses = ai_response_generator.generate_responses(video_id, query_type, query_data)
            
            if not ai_responses:
                return "❌ AI 응답 생성에 실패했습니다."
            
            # 개별 AI 답변들
            individual_responses = ai_responses.get('individual', {})
            optimal_response = ai_responses.get('optimal', '')
            
            # 통합 응답 생성
            response_text = f"## 🎯 AI 통합 분석 결과\n\n{optimal_response}\n\n"
            
            # 각 AI별 답변 추가
            response_text += "## 📊 각 AI별 개별 분석\n\n"
            for ai_name, response in individual_responses.items():
                ai_display_name = {
                    'gpt': 'GPT-4o',
                    'claude': 'Claude-3.5-Sonnet', 
                    'mixtral': 'Mixtral-8x7B',
                    'gemini': 'Gemini-2.5-Flash'
                }.get(ai_name, ai_name.upper())
                
                response_text += f"### {ai_display_name}\n{response}\n\n"
            
            logger.info(f"✅ AI 응답 생성 완료: {len(response_text)}자")
            return response_text
            
        except Exception as e:
            logger.error(f"❌ AI 응답 생성 실패: {e}")
            return f"❌ AI 응답 생성 중 오류가 발생했습니다: {str(e)}"
    
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

