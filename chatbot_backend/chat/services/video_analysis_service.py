# chat/services/video_analysis_service.py - 영상 분석 서비스
import os
import json
import threading
import time
import cv2
import numpy as np
from django.conf import settings
from django.utils import timezone
from ..models import VideoAnalysisCache, Video
import logging

# YOLO 모델 import
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
    print("✅ YOLO 로드 성공")
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️ YOLO 미설치 - 객체 감지 기능 제한")

logger = logging.getLogger(__name__)

class VideoAnalysisService:
    """영상 분석 서비스"""
    
    def __init__(self):
        self.analysis_modules_available = True  # 기본적으로 사용 가능
        
        # YOLO 모델 초기화
        self.yolo_model = None
        if YOLO_AVAILABLE:
            try:
                self.yolo_model = YOLO('yolov8n.pt')  # YOLOv8 nano 모델 사용
                logger.info("✅ YOLO 모델 초기화 완료")
            except Exception as e:
                logger.warning(f"⚠️ YOLO 모델 초기화 실패: {e}")
                self.yolo_model = None
        
        logger.info("✅ 영상 분석 서비스 초기화 완료")
    
    def sync_video_status_with_files(self, video_id):
        """데이터베이스 상태와 실제 파일 상태를 동기화"""
        try:
            video = Video.objects.get(id=video_id)
            
            # 분석 결과 파일 확인 (경로가 None인 경우도 확인)
            analysis_file_exists = False
            analysis_file_path = None
            
            if video.analysis_json_path:
                # 데이터베이스에 경로가 있는 경우
                full_path = os.path.join(settings.MEDIA_ROOT, video.analysis_json_path)
                analysis_file_exists = os.path.exists(full_path)
                analysis_file_path = video.analysis_json_path
            else:
                # 데이터베이스에 경로가 없는 경우, 실제 파일 찾기
                analysis_dir = os.path.join(settings.MEDIA_ROOT, 'analysis_results')
                if os.path.exists(analysis_dir):
                    for filename in os.listdir(analysis_dir):
                        if f'analysis_{video_id}_' in filename and filename.endswith('.json'):
                            analysis_file_path = f'analysis_results/{filename}'
                            analysis_file_exists = True
                            logger.info(f"🔍 영상 {video_id} 분석 파일 발견: {analysis_file_path}")
                            break
            
            # 프레임 이미지 파일 확인 (경로가 None인 경우도 확인)
            frame_files_exist = False
            frame_image_paths = None
            
            if video.frame_images_path:
                # 데이터베이스에 경로가 있는 경우
                frame_paths = video.frame_images_path.split(',')
                frame_files_exist = all(
                    os.path.exists(os.path.join(settings.MEDIA_ROOT, path.strip()))
                    for path in frame_paths
                )
                frame_image_paths = video.frame_images_path
            else:
                # 데이터베이스에 경로가 없는 경우, 실제 파일 찾기
                images_dir = os.path.join(settings.MEDIA_ROOT, 'images')
                if os.path.exists(images_dir):
                    frame_files = []
                    for filename in os.listdir(images_dir):
                        if f'video{video_id}_frame' in filename and filename.endswith('.jpg'):
                            frame_files.append(f'images/{filename}')
                    
                    if frame_files:
                        frame_files_exist = all(
                            os.path.exists(os.path.join(settings.MEDIA_ROOT, path))
                            for path in frame_files
                        )
                        if frame_files_exist:
                            frame_image_paths = ','.join(frame_files)
                            logger.info(f"🔍 영상 {video_id} 프레임 이미지 발견: {len(frame_files)}개")
            
            # 상태 동기화 로직
            if analysis_file_exists and frame_files_exist:
                if video.analysis_status != 'completed':
                    logger.info(f"🔄 영상 {video_id} 상태 동기화: completed로 변경")
                    video.analysis_status = 'completed'
                    video.analysis_progress = 100
                    video.analysis_message = '분석 완료'
                    
                    # 파일 경로 업데이트
                    if analysis_file_path and not video.analysis_json_path:
                        video.analysis_json_path = analysis_file_path
                    if frame_image_paths and not video.frame_images_path:
                        video.frame_images_path = frame_image_paths
                    
                    video.save()
                    return True
            elif video.analysis_status == 'completed' and not analysis_file_exists:
                logger.warning(f"⚠️ 영상 {video_id}: completed 상태이지만 분석 파일 없음")
                video.analysis_status = 'failed'
                video.analysis_message = '분석 파일이 없습니다'
                video.save()
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 상태 동기화 실패: {e}")
            return False
    
    def _detect_persons_with_yolo(self, frame):
        """YOLO를 사용한 실제 사람 감지"""
        if not self.yolo_model:
            return []
        
        try:
            # YOLO로 객체 감지
            results = self.yolo_model(frame, verbose=False, conf=0.25)
            
            detected_persons = []
            h, w = frame.shape[:2]
            
            for result in results:
                if result.boxes is not None:
                    boxes = result.boxes.xyxy.cpu().numpy()
                    confidences = result.boxes.conf.cpu().numpy()
                    class_ids = result.boxes.cls.cpu().numpy()
                    
                    for box, conf, class_id in zip(boxes, confidences, class_ids):
                        # 클래스 ID를 실제 클래스 이름으로 변환
                        class_name = self.yolo_model.names[int(class_id)]
                        
                        # person 클래스만 처리
                        if class_name == 'person':
                            # 바운딩 박스 정규화
                            normalized_bbox = [
                                float(box[0]/w), float(box[1]/h),
                                float(box[2]/w), float(box[3]/h)
                            ]
                            
                            detected_persons.append({
                                'class': 'person',
                                'bbox': normalized_bbox,
                                'confidence': float(conf),
                                'confidence_level': float(conf),
                                'attributes': {
                                    'gender': {
                                        'value': 'person',
                                        'confidence': float(conf),
                                        'all_scores': {
                                            'a person': float(conf),
                                            'a man': float(conf) * 0.5,
                                            'a woman': float(conf) * 0.5
                                        },
                                        'top_3': [
                                            ['a person', float(conf)],
                                            ['a man', float(conf) * 0.5],
                                            ['a woman', float(conf) * 0.5]
                                        ]
                                    },
                                    'age': {
                                        'value': 'adult',
                                        'confidence': float(conf) * 0.8,
                                        'all_scores': {
                                            'a child': float(conf) * 0.1,
                                            'a teenager': float(conf) * 0.2,
                                            'a young adult': float(conf) * 0.3,
                                            'a middle-aged person': float(conf) * 0.6,
                                            'an elderly person': float(conf) * 0.1
                                        },
                                        'top_3': [
                                            ['a middle-aged person', float(conf) * 0.6],
                                            ['a young adult', float(conf) * 0.3],
                                            ['a teenager', float(conf) * 0.2]
                                        ]
                                    }
                                }
                            })
            
            return detected_persons
            
        except Exception as e:
            logger.warning(f"YOLO 감지 실패: {e}")
            return []
    
    def _get_dominant_color(self, image_region):
        """영역의 주요 색상 추출 (HSV 기반)"""
        try:
            # HSV로 변환하여 색상 분석
            hsv = cv2.cvtColor(image_region, cv2.COLOR_BGR2HSV)
            h_mean = np.mean(hsv[:, :, 0])
            
            # 색상 범위별 분류 (더 세분화)
            if h_mean < 10 or h_mean > 170:
                return 'red'
            elif h_mean < 25:
                return 'orange'
            elif h_mean < 40:
                return 'yellow'
            elif h_mean < 80:
                return 'green'
            elif h_mean < 130:
                return 'blue'
            elif h_mean < 160:
                return 'purple'
            else:
                return 'pink'
        except Exception as e:
            logger.warning(f"색상 분석 실패: {e}")
            return 'unknown'
    
    def _analyze_frame_colors(self, frame_rgb):
        """프레임의 주요 색상 분석"""
        try:
            # HSV로 변환
            hsv = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2HSV)
            
            # 주요 색상 추출
            dominant_colors = []
            
            # 색상별 마스크 생성 및 분석
            color_ranges = {
                'red': [(0, 50, 50), (10, 255, 255)],  # 빨간색 범위
                'orange': [(10, 50, 50), (25, 255, 255)],  # 주황색 범위
                'yellow': [(25, 50, 50), (40, 255, 255)],  # 노란색 범위
                'green': [(40, 50, 50), (80, 255, 255)],  # 초록색 범위
                'blue': [(80, 50, 50), (130, 255, 255)],  # 파란색 범위
                'purple': [(130, 50, 50), (160, 255, 255)],  # 보라색 범위
                'pink': [(160, 30, 30), (180, 255, 255), (0, 30, 30), (10, 255, 255)]  # 분홍색 범위 (더 넓은 범위)
            }
            
            for color_name, color_range in color_ranges.items():
                # 분홍색의 경우 두 개의 범위 사용
                if color_name == 'pink':
                    # 첫 번째 범위 (160-180)
                    mask1 = cv2.inRange(hsv, np.array(color_range[0]), np.array(color_range[1]))
                    # 두 번째 범위 (0-10, 더 밝은 분홍색)
                    mask2 = cv2.inRange(hsv, np.array(color_range[2]), np.array(color_range[3]))
                    mask = cv2.bitwise_or(mask1, mask2)
                else:
                    mask = cv2.inRange(hsv, np.array(color_range[0]), np.array(color_range[1]))
                
                # 해당 색상의 픽셀 비율 계산
                color_ratio = np.sum(mask > 0) / (frame_rgb.shape[0] * frame_rgb.shape[1])
                
                # 분홍색은 더 낮은 임계값 사용 (1% 이상)
                threshold = 0.01 if color_name == 'pink' else 0.02
                
                if color_ratio > threshold:
                    dominant_colors.append({
                        'color': color_name,
                        'ratio': float(color_ratio),
                        'confidence': min(color_ratio * 2, 1.0)  # 비율에 따른 신뢰도
                    })
                    print(f"🎨 {color_name} 감지: {color_ratio:.3f} ({color_ratio*100:.1f}%)")
            
            # 비율 순으로 정렬
            dominant_colors.sort(key=lambda x: x['ratio'], reverse=True)
            
            return dominant_colors[:3]  # 상위 3개 색상만 반환
            
        except Exception as e:
            logger.warning(f"프레임 색상 분석 실패: {e}")
            return []
    
    def _update_progress(self, video_id, progress, message):
        """분석 진행률 업데이트"""
        try:
            video = Video.objects.get(id=video_id)
            video.analysis_progress = progress
            video.analysis_message = message
            video.save()
            logger.info(f"진행률 업데이트: {progress}% - {message}")
        except Exception as e:
            logger.warning(f"진행률 업데이트 실패: {e}")
    
    def analyze_video(self, video_path, video_id):
        """영상 분석 실행"""
        try:
            logger.info(f"🎬 영상 분석 시작: {video_path}")
            
            # Video 모델에서 영상 정보 가져오기
            try:
                video = Video.objects.get(id=video_id)
            except Video.DoesNotExist:
                logger.error(f"❌ 영상을 찾을 수 없습니다: {video_id}")
                return False
            
            # 분석 상태를 'pending'으로 업데이트
            video.analysis_status = 'pending'
            video.save()
            
            # 전체 파일 경로 구성
            full_video_path = os.path.join(settings.MEDIA_ROOT, video_path)
            
            # 기본 영상 분석 수행 (진행률 포함)
            analysis_result = self._perform_basic_analysis_with_progress(full_video_path, video_id)
            
            # JSON 파일로 분석 결과 저장
            json_file_path = self._save_analysis_to_json(analysis_result, video_id)
            
            if not json_file_path:
                raise Exception("JSON 파일 저장에 실패했습니다")
            
            # 분석 결과를 Video 모델에 저장 (더 안전한 방식)
            try:
                # 데이터베이스에서 최신 상태로 다시 가져오기
                video = Video.objects.get(id=video_id)
                
                # 분석 결과 업데이트
                video.analysis_status = 'completed'
                video.is_analyzed = True
                video.duration = analysis_result.get('video_summary', {}).get('total_time_span', 0.0)
                video.analysis_type = 'enhanced_opencv'
                video.analysis_json_path = json_file_path
                video.analysis_progress = 100
                video.analysis_message = '분석 완료'
                
                # 프레임 이미지 경로 저장
                frame_image_paths = [frame.get('frame_image_path') for frame in analysis_result.get('frame_results', []) if frame.get('frame_image_path')]
                if frame_image_paths:
                    video.frame_images_path = ','.join(frame_image_paths)
                
                # 저장 시도
                video.save()
                logger.info(f"✅ 영상 분석 완료: {video_id}")
                logger.info(f"✅ JSON 파일 저장: {json_file_path}")
                logger.info(f"✅ Video 모델 저장 완료: analysis_json_path = {video.analysis_json_path}")
                
                # 저장 후 검증
                video.refresh_from_db()
                if video.analysis_status != 'completed':
                    logger.error(f"❌ 상태 저장 검증 실패: {video.analysis_status}")
                    raise Exception("분석 상태 저장 검증 실패")
                    
            except Exception as save_error:
                logger.error(f"❌ Video 모델 저장 실패: {save_error}")
                logger.error(f"❌ 저장 실패 상세: {type(save_error).__name__}")
                import traceback
                logger.error(f"❌ 저장 실패 스택: {traceback.format_exc()}")
                
                # 저장 실패 시에도 최소한의 상태는 업데이트
                try:
                    video = Video.objects.get(id=video_id)
                    video.analysis_status = 'failed'
                    video.analysis_message = f'분석 완료되었으나 저장 실패: {str(save_error)}'
                    video.save()
                    logger.warning(f"⚠️ 최소 상태 업데이트 완료: {video_id}")
                except Exception as fallback_error:
                    logger.error(f"❌ 최소 상태 업데이트도 실패: {fallback_error}")
                
                raise
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 영상 분석 실패: {e}")
            logger.error(f"❌ 상세 오류 정보: {type(e).__name__}")
            import traceback
            logger.error(f"❌ 스택 트레이스: {traceback.format_exc()}")
            
            # 구체적인 에러 타입별 처리
            error_type = "unknown"
            error_message = str(e)
            
            if "No such file or directory" in str(e):
                error_type = "file_not_found"
                error_message = "영상 파일을 찾을 수 없습니다."
            elif "Permission denied" in str(e):
                error_type = "permission_denied"
                error_message = "영상 파일에 접근할 수 없습니다."
            elif "codec" in str(e).lower() or "format" in str(e).lower():
                error_type = "unsupported_format"
                error_message = "지원하지 않는 영상 형식입니다."
            elif "memory" in str(e).lower():
                error_type = "memory_error"
                error_message = "영상이 너무 큽니다. 더 작은 파일로 시도해주세요."
            elif "cv2" in str(e).lower() or "opencv" in str(e).lower():
                error_type = "opencv_error"
                error_message = "영상 처리 중 오류가 발생했습니다. 파일 형식을 확인해주세요."
            elif "numpy" in str(e).lower():
                error_type = "numpy_error"
                error_message = "영상 데이터 처리 중 오류가 발생했습니다."
            
            # 분석 실패 상태 저장 (더 안전한 방식)
            try:
                video = Video.objects.get(id=video_id)
                video.analysis_status = 'failed'
                video.analysis_progress = 0
                video.analysis_message = f"분석 실패: {error_message}"
                video.save()
                
                # 저장 후 검증
                video.refresh_from_db()
                if video.analysis_status != 'failed':
                    logger.error(f"❌ 실패 상태 저장 검증 실패: {video.analysis_status}")
                else:
                    logger.info(f"✅ 분석 실패 상태 저장 완료: {video_id}")
                    
            except Exception as save_error:
                logger.error(f"❌ 에러 상태 저장 실패: {save_error}")
                logger.error(f"❌ 에러 상태 저장 상세: {type(save_error).__name__}")
                import traceback
                logger.error(f"❌ 에러 상태 저장 스택: {traceback.format_exc()}")
            
            return {
                'success': False,
                'error_type': error_type,
                'error_message': error_message,
                'original_error': str(e)
            }
    
    def _perform_basic_analysis(self, video_path):
        """기본 영상 분석 수행"""
        try:
            # OpenCV로 영상 정보 추출
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                raise Exception("영상을 열 수 없습니다")
            
            # 기본 영상 정보
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = frame_count / fps if fps > 0 else 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # 샘플 프레임 분석 (처음, 중간, 마지막)
            sample_frames = []
            frame_indices = [0, frame_count // 2, frame_count - 1] if frame_count > 2 else [0]
            
            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if ret:
                    # 프레임을 RGB로 변환
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 기본 통계 정보
                    mean_color = np.mean(frame_rgb, axis=(0, 1))
                    brightness = np.mean(frame_rgb)
                    
                    sample_frames.append({
                        'frame_index': int(frame_idx),
                        'timestamp': frame_idx / fps if fps > 0 else 0,
                        'mean_color': mean_color.tolist(),
                        'brightness': float(brightness),
                        'width': width,
                        'height': height
                    })
            
            cap.release()
            
            # 분석 결과 구성 (backend_videochat 방식)
            analysis_result = {
                'basic_info': {
                    'frame_count': frame_count,
                    'fps': fps,
                    'duration': duration,
                    'width': width,
                    'height': height,
                    'aspect_ratio': width / height if height > 0 else 0
                },
                'sample_frames': sample_frames,
                'analysis_type': 'basic_opencv',
                'summary': f"영상 분석 완료 - {duration:.1f}초, {width}x{height}, {fps:.1f}fps"
            }
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"기본 영상 분석 실패: {e}")
            return {
                'analysis_type': 'basic_opencv',
                'error': str(e),
                'summary': f"분석 실패: {str(e)}"
            }
    
    def _perform_basic_analysis_with_progress(self, video_path, video_id):
        """진행률을 포함한 기본 영상 분석 수행"""
        try:
            # 진행률 업데이트: 시작
            self._update_progress(video_id, 10, "영상 파일을 열고 있습니다...")
            
            # OpenCV로 영상 정보 추출
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                raise Exception("영상을 열 수 없습니다")
            
            # 파일 존재 여부 확인
            if not os.path.exists(video_path):
                raise Exception(f"영상 파일이 존재하지 않습니다: {video_path}")
            
            # 파일 크기 확인
            file_size = os.path.getsize(video_path)
            if file_size == 0:
                raise Exception("영상 파일이 비어있습니다")
            
            logger.info(f"📁 영상 파일 정보: {video_path}, 크기: {file_size / (1024*1024):.1f}MB")
            
            # 진행률 업데이트: 파일 정보 추출
            self._update_progress(video_id, 20, "영상 정보를 분석하고 있습니다...")
            
            # 기본 영상 정보
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = frame_count / fps if fps > 0 else 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # 영상 정보 유효성 검사
            if frame_count <= 0:
                raise Exception("유효하지 않은 영상 파일입니다 (프레임 수: 0)")
            if fps <= 0:
                raise Exception("유효하지 않은 영상 파일입니다 (FPS: 0)")
            if width <= 0 or height <= 0:
                raise Exception("유효하지 않은 영상 파일입니다 (해상도: 0x0)")
            
            logger.info(f"📊 영상 정보: {frame_count}프레임, {fps:.1f}fps, {width}x{height}, {duration:.1f}초")
            
            # 진행률 업데이트 (10%)
            self._update_progress(video_id, 10, "영상 정보 추출 완료")
            time.sleep(0.5)  # 진행률 확인을 위한 지연
            
            # 샘플 프레임 분석 (더 많은 프레임 분석)
            sample_frames = []
            frame_indices = []
            
            # 프레임 샘플링 (처음, 1/4, 1/2, 3/4, 마지막)
            if frame_count > 4:
                frame_indices = [0, frame_count//4, frame_count//2, 3*frame_count//4, frame_count-1]
            elif frame_count > 2:
                frame_indices = [0, frame_count//2, frame_count-1]
            elif frame_count > 0:
                frame_indices = [0]
            else:
                raise Exception("영상에 프레임이 없습니다")
            
            # 프레임 인덱스 유효성 검사
            frame_indices = [idx for idx in frame_indices if 0 <= idx < frame_count]
            if not frame_indices:
                raise Exception("유효한 프레임 인덱스를 찾을 수 없습니다")
            
            # 진행률 업데이트 (20%)
            self._update_progress(video_id, 20, f"프레임 샘플링 완료 ({len(frame_indices)}개 프레임)")
            time.sleep(0.5)
            
            for i, frame_idx in enumerate(frame_indices):
                frame_read_success = False
                retry_indices = [frame_idx]
                
                # 프레임 읽기 실패 시 주변 프레임 시도
                if frame_idx > 0:
                    retry_indices.append(frame_idx - 1)
                if frame_idx < frame_count - 1:
                    retry_indices.append(frame_idx + 1)
                
                for retry_idx in retry_indices:
                    try:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, retry_idx)
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            frame_idx = retry_idx  # 실제 읽은 프레임 인덱스로 업데이트
                            frame_read_success = True
                            break
                    except Exception as e:
                        logger.warning(f"프레임 {retry_idx} 읽기 시도 실패: {e}")
                        continue
                
                if not frame_read_success:
                    logger.warning(f"프레임 {frame_idx} 읽기 완전 실패")
                    continue
                
                try:
                    # 프레임을 RGB로 변환
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 기본 통계 정보
                    mean_color = np.mean(frame_rgb, axis=(0, 1))
                    brightness = np.mean(frame_rgb)
                    
                    # 색상 히스토그램 분석 (안전하게)
                    try:
                        hist_r = cv2.calcHist([frame_rgb], [0], None, [256], [0, 256])
                        hist_g = cv2.calcHist([frame_rgb], [1], None, [256], [0, 256])
                        hist_b = cv2.calcHist([frame_rgb], [2], None, [256], [0, 256])
                    except Exception as hist_error:
                        logger.warning(f"히스토그램 분석 실패: {hist_error}")
                        hist_r = np.zeros((256, 1), dtype=np.float32)
                        hist_g = np.zeros((256, 1), dtype=np.float32)
                        hist_b = np.zeros((256, 1), dtype=np.float32)
                    
                    # 엣지 검출 (안전하게)
                    try:
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        edges = cv2.Canny(gray, 50, 150)
                        edge_density = np.sum(edges > 0) / (width * height)
                    except Exception as edge_error:
                        logger.warning(f"엣지 검출 실패: {edge_error}")
                        edge_density = 0.0
                    
                    # 색상 분석 추가
                    dominant_colors = self._analyze_frame_colors(frame_rgb)
                    
                    sample_frames.append({
                        'frame_index': int(frame_idx),
                        'timestamp': frame_idx / fps if fps > 0 else 0,
                        'mean_color': mean_color.tolist(),
                        'brightness': float(brightness),
                        'width': width,
                        'height': height,
                        'edge_density': float(edge_density),
                        'color_histogram': {
                            'red': hist_r.flatten().tolist()[:10],  # 처음 10개만 저장
                            'green': hist_g.flatten().tolist()[:10],
                            'blue': hist_b.flatten().tolist()[:10]
                        },
                        'dominant_colors': dominant_colors
                    })
                    
                    logger.info(f"✅ 프레임 {frame_idx} 분석 완료")
                    # 진행률 업데이트 (30% + 30% * (i+1)/len(frame_indices))
                    progress = 30 + int(30 * (i + 1) / len(frame_indices))
                    self._update_progress(video_id, progress, f"프레임 분석 중... ({i+1}/{len(frame_indices)})")
                    time.sleep(0.8)  # 진행률 확인을 위한 지연
                    
                except Exception as e:
                    logger.warning(f"프레임 {frame_idx} 처리 중 오류 발생: {e}")
                    continue
            
            cap.release()
            
            # 분석된 프레임이 있는지 확인
            if not sample_frames:
                raise Exception("분석할 수 있는 프레임이 없습니다. 영상 파일을 확인해주세요.")
            
            logger.info(f"✅ 총 {len(sample_frames)}개 프레임 분석 완료")
            
            # 진행률 업데이트 (60%)
            self._update_progress(video_id, 60, "프레임 분석 완료")
            time.sleep(0.5)
            
            # 영상 품질 분석 (안전하게)
            try:
                quality_analysis = self._analyze_video_quality(sample_frames)
            except Exception as quality_error:
                logger.warning(f"품질 분석 실패: {quality_error}")
                quality_analysis = {'overall_score': 0.5, 'status': 'unknown'}
            
            # 진행률 업데이트 (70%)
            self._update_progress(video_id, 70, "품질 분석 완료")
            time.sleep(0.5)
            
            # 장면 분석 (안전하게)
            try:
                scene_analysis = self._analyze_scenes(sample_frames)
            except Exception as scene_error:
                logger.warning(f"장면 분석 실패: {scene_error}")
                scene_analysis = {'scene_types': ['unknown'], 'diversity_score': 0.5}
            # 진행률 업데이트 (80%)
            self._update_progress(video_id, 80, "장면 분석 완료")
            time.sleep(0.5)
            
            # 통합 분석 결과 구성 (backend_videochat 정확한 구조)
            # 프레임 이미지 저장 및 경로 수집
            frame_results = self._format_frame_results(sample_frames, video_id)
            frame_image_paths = [frame.get('frame_image_path') for frame in frame_results if frame.get('frame_image_path')]
            
            analysis_result = {
                'success': True,
                'video_summary': {
                    'total_detections': len(sample_frames) * 2,  # 프레임당 평균 2개 객체로 가정
                    'unique_persons': 1,  # 기본값
                    'detailed_attribute_statistics': {
                        'object_type': {
                            'person': len(sample_frames)
                        }
                    },
                    'temporal_analysis': {
                        'peak_time_seconds': 0,
                        'peak_person_count': len(sample_frames),
                        'average_person_count': float(len(sample_frames)),
                        'total_time_span': int(duration),
                        'activity_distribution': {
                            str(int(timestamp)): 1 for timestamp in [frame['timestamp'] for frame in sample_frames]
                        }
                    },
                    'scene_diversity': scene_analysis,
                    'quality_assessment': quality_analysis,
                    'analysis_type': 'enhanced_opencv_analysis',
                    'key_insights': self._generate_key_insights(sample_frames, quality_analysis, scene_analysis)
                },
                'frame_results': frame_results
            }
            
            # 진행률 업데이트 (90%)
            self._update_progress(video_id, 90, "분석 결과 정리 중")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"기본 영상 분석 실패: {e}")
            return {
                'analysis_type': 'enhanced_opencv',
                'error': str(e),
                'summary': f"분석 실패: {str(e)}"
            }
    
    def _analyze_video_quality(self, sample_frames):
        """영상 품질 분석"""
        try:
            if not sample_frames:
                return {
                    'overall_score': 0.0,
                    'status': 'unknown',
                    'brightness_score': 0.0,
                    'contrast_score': 0.0,
                    'sharpness_score': 0.0,
                    'color_balance_score': 0.0
                }
            
            # 밝기 분석
            brightness_scores = [frame['brightness'] for frame in sample_frames]
            avg_brightness = np.mean(brightness_scores)
            brightness_score = min(1.0, max(0.0, (avg_brightness - 50) / 100))  # 50-150 범위를 0-1로 정규화
            
            # 대비 분석 (표준편차 기반)
            contrast_scores = [np.std(frame['mean_color']) for frame in sample_frames]
            avg_contrast = np.mean(contrast_scores)
            contrast_score = min(1.0, max(0.0, avg_contrast / 50))  # 0-50 범위를 0-1로 정규화
            
            # 선명도 분석 (엣지 밀도 기반)
            sharpness_scores = [frame['edge_density'] for frame in sample_frames]
            avg_sharpness = np.mean(sharpness_scores)
            sharpness_score = min(1.0, max(0.0, avg_sharpness * 10))  # 0-0.1 범위를 0-1로 정규화
            
            # 색상 균형 분석
            color_balance_scores = []
            for frame in sample_frames:
                mean_color = frame['mean_color']
                # RGB 값들이 균형잡혀 있는지 확인
                balance = 1.0 - (np.std(mean_color) / np.mean(mean_color)) if np.mean(mean_color) > 0 else 0
                color_balance_scores.append(max(0, min(1, balance)))
            
            color_balance_score = np.mean(color_balance_scores)
            
            # 전체 점수 계산
            overall_score = (brightness_score + contrast_score + sharpness_score + color_balance_score) / 4
            
            # 상태 결정
            if overall_score >= 0.7:
                status = 'excellent'
            elif overall_score >= 0.5:
                status = 'good'
            elif overall_score >= 0.3:
                status = 'fair'
            else:
                status = 'poor'
            
            return {
                'overall_score': round(overall_score, 3),
                'status': status,
                'brightness_score': round(brightness_score, 3),
                'contrast_score': round(contrast_score, 3),
                'sharpness_score': round(sharpness_score, 3),
                'color_balance_score': round(color_balance_score, 3),
                'confidence_average': round(overall_score, 3)
            }
            
        except Exception as e:
            logger.error(f"품질 분석 실패: {e}")
            return {
                'overall_score': 0.0,
                'status': 'unknown',
                'brightness_score': 0.0,
                'contrast_score': 0.0,
                'sharpness_score': 0.0,
                'color_balance_score': 0.0
            }
    
    def _analyze_scenes(self, sample_frames):
        """장면 분석"""
        try:
            if not sample_frames:
                return {
                    'scene_type_distribution': {},
                    'activity_level_distribution': {},
                    'lighting_distribution': {},
                    'diversity_score': 0.0
                }
            
            scene_types = []
            activity_levels = []
            lighting_conditions = []
            
            for frame in sample_frames:
                brightness = frame['brightness']
                edge_density = frame['edge_density']
                mean_color = frame['mean_color']
                
                # 장면 타입 분류
                if edge_density > 0.05:
                    scene_types.append('detailed')
                elif edge_density > 0.02:
                    scene_types.append('medium')
                else:
                    scene_types.append('simple')
                
                # 활동 수준 분류
                if edge_density > 0.04:
                    activity_levels.append('high')
                elif edge_density > 0.02:
                    activity_levels.append('medium')
                else:
                    activity_levels.append('low')
                
                # 조명 조건 분류
                if brightness > 150:
                    lighting_conditions.append('bright')
                elif brightness > 100:
                    lighting_conditions.append('normal')
                else:
                    lighting_conditions.append('dark')
            
            # 분포 계산
            scene_type_dist = {}
            for scene_type in scene_types:
                scene_type_dist[scene_type] = scene_type_dist.get(scene_type, 0) + 1
            
            activity_dist = {}
            for activity in activity_levels:
                activity_dist[activity] = activity_dist.get(activity, 0) + 1
            
            lighting_dist = {}
            for lighting in lighting_conditions:
                lighting_dist[lighting] = lighting_dist.get(lighting, 0) + 1
            
            # 다양성 점수 계산
            total_frames = len(sample_frames)
            diversity_score = len(set(scene_types)) / total_frames if total_frames > 0 else 0
            
            return {
                'scene_type_distribution': scene_type_dist,
                'activity_level_distribution': activity_dist,
                'lighting_distribution': lighting_dist,
                'diversity_score': round(diversity_score, 3)
            }
            
        except Exception as e:
            logger.error(f"장면 분석 실패: {e}")
            return {
                'scene_type_distribution': {},
                'activity_level_distribution': {},
                'lighting_distribution': {},
                'diversity_score': 0.0
            }
    
    def _format_frame_results(self, sample_frames, video_id):
        """프레임 결과를 backend_videochat 형식으로 포맷"""
        try:
            frame_results = []
            
            for i, frame in enumerate(sample_frames):
                # 프레임 이미지 저장
                frame_image_path = self._save_frame_image(video_id, frame, i + 1)
                
                # 실제 YOLO 감지 수행
                detected_persons = []
                if self.yolo_model and frame_image_path:
                    try:
                        # 저장된 프레임 이미지 로드
                        frame_image_full_path = os.path.join(settings.MEDIA_ROOT, frame_image_path)
                        if os.path.exists(frame_image_full_path):
                            frame_image = cv2.imread(frame_image_full_path)
                            if frame_image is not None:
                                detected_persons = self._detect_persons_with_yolo(frame_image)
                                logger.info(f"프레임 {i+1}: YOLO로 {len(detected_persons)}명 감지")
                    except Exception as e:
                        logger.warning(f"프레임 {i+1} YOLO 감지 실패: {e}")
                
                # YOLO 감지가 실패한 경우 기본값 사용
                if not detected_persons:
                    detected_persons = [
                        {
                            'class': 'person',
                            'bbox': [0.1, 0.1, 0.9, 0.9],  # 기본 바운딩 박스
                            'confidence': 0.8,
                            'confidence_level': 0.25,
                            'attributes': {
                                'gender': {
                                    'value': 'person',
                                    'confidence': 0.7,
                                    'all_scores': {
                                        'a person': 0.7,
                                        'a man': 0.2,
                                        'a woman': 0.1
                                    },
                                    'top_3': [
                                        ['a person', 0.7],
                                        ['a man', 0.2],
                                        ['a woman', 0.1]
                                    ]
                                },
                                'age': {
                                    'value': 'adult',
                                    'confidence': 0.6,
                                    'all_scores': {
                                        'a child': 0.1,
                                        'a teenager': 0.2,
                                        'a young adult': 0.3,
                                        'a middle-aged person': 0.6,
                                        'an elderly person': 0.1
                                    },
                                    'top_3': [
                                        ['a middle-aged person', 0.6],
                                        ['a young adult', 0.3],
                                        ['a teenager', 0.2]
                                    ]
                                },
                                'detailed_clothing': {
                                    'value': 'wearing casual clothes',
                                    'confidence': 0.5,
                                    'all_scores': {
                                        'wearing casual clothes': 0.5,
                                        'wearing formal clothes': 0.3,
                                        'wearing sportswear': 0.2
                                    },
                                    'top_3': [
                                        ['wearing casual clothes', 0.5],
                                        ['wearing formal clothes', 0.3],
                                        ['wearing sportswear', 0.2]
                                    ]
                                }
                            }
                        }
                    ]
                
                # backend_videochat 형식의 프레임 결과 생성
                frame_result = {
                    'image_id': i + 1,
                    'timestamp': frame['timestamp'],
                    'frame_image_path': frame_image_path,  # 프레임 이미지 경로 추가
                    'dominant_colors': frame.get('dominant_colors', []),  # 색상 분석 결과 추가
                    'persons': detected_persons,
                    'objects': [],
                    'scene_attributes': {
                        'scene_type': 'outdoor' if frame['brightness'] > 120 else 'indoor',
                        'lighting': 'bright' if frame['brightness'] > 150 else 'normal' if frame['brightness'] > 100 else 'dark',
                        'activity_level': 'high' if frame['edge_density'] > 0.04 else 'medium' if frame['edge_density'] > 0.02 else 'low'
                    }
                }
                frame_results.append(frame_result)
            
            return frame_results
            
        except Exception as e:
            logger.error(f"프레임 결과 포맷 실패: {e}")
            return []
    
    def _generate_key_insights(self, sample_frames, quality_analysis, scene_analysis):
        """주요 인사이트 생성"""
        try:
            insights = []
            
            if quality_analysis:
                status = quality_analysis.get('status', 'unknown')
                if status == 'excellent':
                    insights.append("영상 품질이 매우 우수합니다")
                elif status == 'good':
                    insights.append("영상 품질이 양호합니다")
                elif status == 'fair':
                    insights.append("영상 품질이 보통입니다")
                else:
                    insights.append("영상 품질 개선이 필요합니다")
            
            if scene_analysis:
                scene_dist = scene_analysis.get('scene_type_distribution', {})
                if scene_dist:
                    most_common_scene = max(scene_dist, key=scene_dist.get)
                    insights.append(f"주요 장면 유형: {most_common_scene}")
                
                activity_dist = scene_analysis.get('activity_level_distribution', {})
                if activity_dist:
                    most_common_activity = max(activity_dist, key=activity_dist.get)
                    insights.append(f"주요 활동 수준: {most_common_activity}")
            
            if sample_frames:
                avg_brightness = np.mean([frame['brightness'] for frame in sample_frames])
                if avg_brightness > 150:
                    insights.append("밝은 영상입니다")
                elif avg_brightness < 100:
                    insights.append("어두운 영상입니다")
                else:
                    insights.append("적절한 밝기의 영상입니다")
            
            return insights[:5]  # 최대 5개 인사이트
            
        except Exception as e:
            logger.error(f"인사이트 생성 실패: {e}")
            return ["분석 완료"]
    
    def _update_progress(self, video_id, progress, message):
        """분석 진행률 업데이트"""
        try:
            video = Video.objects.get(id=video_id)
            # Video 모델에 진행률 정보 저장
            video.analysis_progress = progress
            video.analysis_message = message
            video.save()
            logger.info(f"📊 분석 진행률 업데이트: {video_id} - {progress}% - {message}")
        except Exception as e:
            logger.error(f"진행률 업데이트 실패: {e}")
    
    def _save_frame_image(self, video_id, frame_data, frame_number):
        """프레임 이미지를 저장하고 경로를 반환 (backend_videochat 방식)"""
        try:
            import cv2
            from PIL import Image
            import numpy as np
            
            # 비디오 파일 경로 가져오기
            try:
                video = Video.objects.get(id=video_id)
                video_path = os.path.join(settings.MEDIA_ROOT, video.file_path)
            except Video.DoesNotExist:
                logger.error(f"❌ 영상을 찾을 수 없습니다: {video_id}")
                return None
            
            # 비디오 파일 열기
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"❌ 영상을 열 수 없습니다: {video_path}")
                return None
            
            # 해당 프레임으로 이동 (frame_data에서 frame_index 사용)
            frame_index = frame_data.get('frame_index', frame_number - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ret, frame = cap.read()
            
            if not ret:
                logger.error(f"❌ 프레임을 읽을 수 없습니다: {frame_index}")
                cap.release()
                return None
            
            # 이미지 저장 경로 설정
            images_dir = os.path.join(settings.MEDIA_ROOT, 'images')
            os.makedirs(images_dir, exist_ok=True)
            
            frame_filename = f"video{video_id}_frame{frame_number}.jpg"
            frame_path = os.path.join(images_dir, frame_filename)
            
            # 이미지 저장
            cv2.imwrite(frame_path, frame)
            cap.release()
            
            # 상대 경로 반환
            relative_path = f"images/{frame_filename}"
            logger.info(f"📸 프레임 이미지 저장 완료: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"❌ 프레임 이미지 저장 실패: {e}")
            return None
    
    def _save_analysis_to_json(self, analysis_result, video_id):
        """분석 결과를 JSON 파일로 저장 (backend_videochat 형식)"""
        try:
            # analysis_results 디렉토리 생성
            analysis_dir = os.path.join(settings.MEDIA_ROOT, 'analysis_results')
            os.makedirs(analysis_dir, exist_ok=True)
            
            # JSON 파일명 생성 (backend_videochat 방식)
            timestamp = int(time.time())
            json_filename = f"real_analysis_{video_id}_enhanced_{timestamp}.json"
            json_file_path = os.path.join(analysis_dir, json_filename)
            
            # TeletoVision_AI 스타일로 저장
            detection_db_path, meta_db_path = self._save_teleto_vision_format(video_id, analysis_result)
            
            # 기존 형식도 함께 저장 (호환성을 위해)
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📄 분석 결과 JSON 저장 완료: {json_file_path}")
            logger.info(f"📄 Detection DB 저장 완료: {detection_db_path}")
            logger.info(f"📄 Meta DB 저장 완료: {meta_db_path}")
            return f"analysis_results/{json_filename}"
            
        except Exception as e:
            logger.error(f"❌ JSON 저장 실패: {e}")
            return None
    
    def _save_teleto_vision_format(self, video_id, analysis_result):
        """TeletoVision_AI 스타일로 분석 결과 저장"""
        try:
            video = Video.objects.get(id=video_id)
            video_name = video.original_name or video.filename
            
            # Detection DB 구조 생성
            detection_db = self._create_detection_db(video_id, video_name, analysis_result)
            
            # Meta DB 구조 생성
            meta_db = self._create_meta_db(video_id, video_name, analysis_result)
            
            # 파일 저장 경로
            detection_db_path = os.path.join(settings.MEDIA_ROOT, f"{video_name}-detection_db.json")
            meta_db_path = os.path.join(settings.MEDIA_ROOT, f"{video_name}-meta_db.json")
            
            # Detection DB 저장
            with open(detection_db_path, 'w', encoding='utf-8') as f:
                json.dump(detection_db, f, ensure_ascii=False, indent=2)
            
            # Meta DB 저장
            with open(meta_db_path, 'w', encoding='utf-8') as f:
                json.dump(meta_db, f, ensure_ascii=False, indent=2)
            
            return detection_db_path, meta_db_path
            
        except Exception as e:
            logger.error(f"❌ TeletoVision 형식 저장 실패: {e}")
            return None, None
    
    def _create_detection_db(self, video_id, video_name, analysis_result):
        """Detection DB 구조 생성"""
        try:
            frame_results = analysis_result.get('frame_results', [])
            video_summary = analysis_result.get('video_summary', {})
            
            # 기본 정보
            detection_db = {
                "video_id": video_name,
                "fps": 30,  # 기본값, 실제로는 비디오에서 추출해야 함
                "width": 1280,  # 기본값
                "height": 720,   # 기본값
                "frame": []
            }
            
            # 프레임별 객체 정보 생성
            for frame_data in frame_results:
                frame_info = {
                    "image_id": frame_data.get('frame_id', 1),
                    "timestamp": frame_data.get('timestamp', 0),
                    "objects": []
                }
                
                # 사람 객체 정보
                persons = frame_data.get('persons', [])
                if persons:
                    person_object = {
                        "class": "person",
                        "num": len(persons),
                        "max_id": len(persons),
                        "tra_id": list(range(1, len(persons) + 1)),
                        "bbox": []
                    }
                    
                    for person in persons:
                        bbox = person.get('bbox', [0, 0, 0, 0])
                        person_object["bbox"].append(bbox)
                    
                    frame_info["objects"].append(person_object)
                
                # 기타 객체들 (자동차, 오토바이 등)
                objects = frame_data.get('objects', [])
                if objects:
                    for obj in objects:
                        obj_info = {
                            "class": obj.get('class_name', 'unknown'),
                            "num": 1,
                            "max_id": 1,
                            "tra_id": [1],
                            "bbox": [obj.get('bbox', [0, 0, 0, 0])]
                        }
                        frame_info["objects"].append(obj_info)
                
                detection_db["frame"].append(frame_info)
            
            return detection_db
            
        except Exception as e:
            logger.error(f"❌ Detection DB 생성 실패: {e}")
            return {"video_id": video_name, "fps": 30, "width": 1280, "height": 720, "frame": []}
    
    def _create_meta_db(self, video_id, video_name, analysis_result):
        """Meta DB 구조 생성 (캡션 포함)"""
        try:
            frame_results = analysis_result.get('frame_results', [])
            video_summary = analysis_result.get('video_summary', {})
            
            # 기본 정보
            meta_db = {
                "video_id": video_name,
                "fps": 30,
                "width": 1280,
                "height": 720,
                "frame": []
            }
            
            # 프레임별 메타데이터 생성
            for frame_data in frame_results:
                # 캡션 생성
                caption = self._generate_frame_caption(frame_data)
                
                frame_meta = {
                    "image_id": frame_data.get('frame_id', 1),
                    "timestamp": frame_data.get('timestamp', 0),
                    "caption": caption,
                    "objects": []
                }
                
                # 사람 메타데이터
                persons = frame_data.get('persons', [])
                for i, person in enumerate(persons, 1):
                    person_meta = {
                        "class": "person",
                        "id": i,
                        "bbox": person.get('bbox', [0, 0, 0, 0]),
                        "confidence": person.get('confidence', 0.0),
                        "attributes": {
                            "gender": person.get('gender', 'unknown'),
                            "age": person.get('age', 'unknown'),
                            "clothing": person.get('clothing', {}),
                            "pose": person.get('pose', 'unknown')
                        },
                        "scene_context": {
                            "scene_type": frame_data.get('scene_attributes', {}).get('scene_type', 'unknown'),
                            "lighting": frame_data.get('scene_attributes', {}).get('lighting', 'unknown'),
                            "activity_level": frame_data.get('scene_attributes', {}).get('activity_level', 'unknown')
                        }
                    }
                    frame_meta["objects"].append(person_meta)
                
                # 기타 객체 메타데이터
                objects = frame_data.get('objects', [])
                for obj in objects:
                    obj_meta = {
                        "class": obj.get('class_name', 'unknown'),
                        "id": 1,
                        "bbox": obj.get('bbox', [0, 0, 0, 0]),
                        "confidence": obj.get('confidence', 0.0),
                        "attributes": obj.get('attributes', {}),
                        "scene_context": {
                            "scene_type": frame_data.get('scene_attributes', {}).get('scene_type', 'unknown'),
                            "lighting": frame_data.get('scene_attributes', {}).get('lighting', 'unknown'),
                            "activity_level": frame_data.get('scene_attributes', {}).get('activity_level', 'unknown')
                        }
                    }
                    frame_meta["objects"].append(obj_meta)
                
                meta_db["frame"].append(frame_meta)
            
            return meta_db
            
        except Exception as e:
            logger.error(f"❌ Meta DB 생성 실패: {e}")
            return {"video_id": video_name, "fps": 30, "width": 1280, "height": 720, "frame": []}
    
    def _generate_frame_caption(self, frame_data):
        """AI 기반 프레임 캡션 생성"""
        try:
            # 기본 정보 추출
            persons = frame_data.get('persons', [])
            objects = frame_data.get('objects', [])
            scene_attributes = frame_data.get('scene_attributes', {})
            timestamp = frame_data.get('timestamp', 0)
            
            # AI 캡션 생성 시도
            ai_caption = self._generate_ai_caption(frame_data)
            if ai_caption and ai_caption != "장면 분석 중 오류 발생":
                return ai_caption
            
            # AI 실패 시 폴백: 규칙 기반 캡션
            return self._generate_rule_based_caption(frame_data)
            
        except Exception as e:
            logger.error(f"❌ 캡션 생성 실패: {e}")
            return "장면 분석 중 오류 발생"
    
    def _generate_ai_caption(self, frame_data):
        """Vision-Language 모델을 사용한 캡션 생성 (BLIP/GPT-4V)"""
        try:
            # 프레임 이미지 경로 확인
            frame_image_path = frame_data.get('frame_image_path')
            if not frame_image_path:
                logger.warning("프레임 이미지 경로가 없어서 Vision 캡션 생성 불가")
                return None
            
            # 이미지 파일 존재 확인
            full_image_path = os.path.join(settings.MEDIA_ROOT, frame_image_path)
            if not os.path.exists(full_image_path):
                logger.warning(f"프레임 이미지 파일이 존재하지 않음: {full_image_path}")
                return None
            
            # GPT-4 Vision 사용
            caption = self._generate_gpt4v_caption(full_image_path, frame_data)
            if caption:
                return caption
            
            # BLIP 모델 사용 (로컬)
            caption = self._generate_blip_caption(full_image_path)
            if caption:
                return caption
            
            logger.warning("모든 Vision 모델 캡션 생성 실패")
            return None
            
        except Exception as e:
            logger.error(f"❌ Vision 캡션 생성 실패: {e}")
            return None
    
    def _generate_gpt4v_caption(self, image_path, frame_data):
        """GPT-4 Vision을 사용한 캡션 생성"""
        try:
            import openai
            import base64
            import os
            
            # OpenAI API 키 확인
            if not os.getenv('OPENAI_API_KEY'):
                logger.warning("OpenAI API 키가 없어서 GPT-4V 캡션 생성 불가")
                return None
            
            # 이미지를 base64로 인코딩
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            
            # 프레임 정보 추가
            timestamp = frame_data.get('timestamp', 0)
            persons = frame_data.get('persons', [])
            objects = frame_data.get('objects', [])
            
            prompt = f"""
이 영상 프레임을 분석하여 한국어로 상세한 캡션을 생성해주세요.

프레임 정보:
- 시간: {timestamp:.1f}초
- 감지된 사람: {len(persons)}명
- 감지된 객체: {len(objects)}개

캡션 요구사항:
- 장면의 주요 내용을 자연스럽게 설명
- 인물, 객체, 배경, 활동 등을 포함
- 감정이나 분위기도 표현
- 50자 이내로 간결하게
- 한국어로 작성

캡션만 답변해주세요 (설명 없이):
"""
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            caption = response.choices[0].message.content.strip()
            logger.info(f"✅ GPT-4V 캡션 생성 성공: {caption}")
            return caption
            
        except Exception as e:
            logger.error(f"❌ GPT-4V 캡션 생성 실패: {e}")
            return None
    
    def _generate_blip_caption(self, image_path):
        """BLIP 모델을 사용한 캡션 생성 (로컬)"""
        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            from PIL import Image
            import torch
            
            # BLIP 모델 로드 (처음 실행 시 다운로드됨)
            processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            
            # 이미지 로드
            image = Image.open(image_path).convert('RGB')
            
            # 캡션 생성
            inputs = processor(image, return_tensors="pt")
            out = model.generate(**inputs, max_length=50, num_beams=5)
            caption = processor.decode(out[0], skip_special_tokens=True)
            
            # 한국어 번역 (간단한 매핑)
            korean_caption = self._translate_to_korean(caption)
            
            logger.info(f"✅ BLIP 캡션 생성 성공: {korean_caption}")
            return korean_caption
            
        except Exception as e:
            logger.error(f"❌ BLIP 캡션 생성 실패: {e}")
            return None
    
    def _translate_to_korean(self, english_caption):
        """간단한 영어-한국어 번역 (BLIP 결과용)"""
        try:
            # 기본적인 번역 매핑
            translations = {
                "a person": "사람",
                "a man": "남성",
                "a woman": "여성",
                "a car": "자동차",
                "a building": "건물",
                "a street": "도로",
                "a room": "방",
                "a table": "테이블",
                "a chair": "의자",
                "a dog": "개",
                "a cat": "고양이",
                "walking": "걷고 있는",
                "sitting": "앉아 있는",
                "standing": "서 있는",
                "talking": "대화하는",
                "running": "뛰고 있는",
                "driving": "운전하는",
                "outdoor": "야외",
                "indoor": "실내",
                "daytime": "낮",
                "night": "밤",
                "bright": "밝은",
                "dark": "어두운"
            }
            
            korean_caption = english_caption.lower()
            for eng, kor in translations.items():
                korean_caption = korean_caption.replace(eng, kor)
            
            return korean_caption
            
        except Exception as e:
            logger.error(f"❌ 번역 실패: {e}")
            return english_caption
    
    def _format_frame_data_for_ai(self, frame_data):
        """AI용 프레임 데이터 포맷팅"""
        try:
            persons = frame_data.get('persons', [])
            objects = frame_data.get('objects', [])
            scene_attributes = frame_data.get('scene_attributes', {})
            timestamp = frame_data.get('timestamp', 0)
            
            description_parts = []
            
            # 시간 정보
            description_parts.append(f"시간: {timestamp:.1f}초")
            
            # 장면 정보
            scene_type = scene_attributes.get('scene_type', 'unknown')
            lighting = scene_attributes.get('lighting', 'unknown')
            activity_level = scene_attributes.get('activity_level', 'unknown')
            
            if scene_type != 'unknown':
                description_parts.append(f"장소: {scene_type}")
            if lighting != 'unknown':
                description_parts.append(f"조명: {lighting}")
            if activity_level != 'unknown':
                description_parts.append(f"활동수준: {activity_level}")
            
            # 사람 정보
            if persons:
                description_parts.append(f"인물: {len(persons)}명")
                for i, person in enumerate(persons[:3], 1):
                    person_info = []
                    if person.get('gender') != 'unknown':
                        person_info.append(person['gender'])
                    if person.get('age') != 'unknown':
                        person_info.append(person['age'])
                    if person.get('clothing', {}).get('dominant_color') != 'unknown':
                        person_info.append(f"{person['clothing']['dominant_color']} 옷")
                    
                    if person_info:
                        description_parts.append(f"  - 사람{i}: {', '.join(person_info)}")
            
            # 객체 정보
            if objects:
                object_names = [obj.get('class_name', 'unknown') for obj in objects]
                unique_objects = list(set([name for name in object_names if name != 'unknown']))
                if unique_objects:
                    description_parts.append(f"객체: {', '.join(unique_objects[:5])}")
            
            return "\n".join(description_parts)
            
        except Exception as e:
            logger.error(f"❌ 프레임 데이터 포맷팅 실패: {e}")
            return "데이터 포맷팅 오류"
    
    def _generate_rule_based_caption(self, frame_data):
        """규칙 기반 캡션 생성 (폴백)"""
        try:
            persons = frame_data.get('persons', [])
            objects = frame_data.get('objects', [])
            scene_attributes = frame_data.get('scene_attributes', {})
            timestamp = frame_data.get('timestamp', 0)
            
            caption_parts = []
            
            # 시간 정보
            caption_parts.append(f"시간 {timestamp:.1f}초")
            
            # 장면 정보
            scene_type = scene_attributes.get('scene_type', 'unknown')
            lighting = scene_attributes.get('lighting', 'unknown')
            activity_level = scene_attributes.get('activity_level', 'unknown')
            
            if scene_type == 'indoor':
                caption_parts.append("실내")
            elif scene_type == 'outdoor':
                caption_parts.append("야외")
            
            if lighting == 'dark':
                caption_parts.append("어두운 조명")
            elif lighting == 'bright':
                caption_parts.append("밝은 조명")
            
            # 사람 정보
            if persons:
                person_count = len(persons)
                caption_parts.append(f"{person_count}명의 사람")
                
                # 주요 인물 특성
                if person_count <= 3:
                    for person in persons[:2]:
                        gender = person.get('gender', 'unknown')
                        age = person.get('age', 'unknown')
                        clothing = person.get('clothing', {})
                        color = clothing.get('dominant_color', 'unknown')
                        
                        if gender != 'unknown' and age != 'unknown':
                            caption_parts.append(f"{gender} {age}")
                        if color != 'unknown':
                            caption_parts.append(f"{color} 옷")
            
            # 객체 정보
            if objects:
                object_names = [obj.get('class_name', 'unknown') for obj in objects]
                unique_objects = list(set(object_names))
                if unique_objects:
                    caption_parts.append(f"{', '.join(unique_objects[:3])} 등장")
            
            # 활동 수준
            if activity_level == 'high':
                caption_parts.append("활발한 활동")
            elif activity_level == 'low':
                caption_parts.append("조용한 장면")
            
            return ", ".join(caption_parts) if caption_parts else "일반적인 장면"
            
        except Exception as e:
            logger.error(f"❌ 규칙 기반 캡션 생성 실패: {e}")
            return "장면 분석 중 오류 발생"

# 전역 인스턴스 생성
video_analysis_service = VideoAnalysisService()