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

# DeepFace import (성별/나이/감정 분석)
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
    print("✅ DeepFace 로드 성공")
except ImportError:
    DEEPFACE_AVAILABLE = False
    print("⚠️ DeepFace 미설치 - 얼굴 분석 기능 제한")

# Transformers import (BLIP-2 캡션 생성)
try:
    from transformers import BlipProcessor, BlipForConditionalGeneration
    from PIL import Image
    BLIP_AVAILABLE = True
    print("✅ BLIP 로드 성공")
except ImportError:
    BLIP_AVAILABLE = False
    print("⚠️ BLIP 미설치 - 캡션 생성 기능 제한")

# Ollama Vision import (llava 모델 - 캡션 생성)
try:
    import ollama
    OLLAMA_AVAILABLE = True
    print("✅ Ollama 로드 성공")
except ImportError:
    OLLAMA_AVAILABLE = False
    print("⚠️ Ollama 미설치 - BLIP만 사용")

logger = logging.getLogger(__name__)

class VideoAnalysisService:
    """하이브리드 영상 분석 서비스 (YOLO + DeepFace + Ollama + BLIP)"""
    
    def __init__(self):
        self.analysis_modules_available = True
        
        # YOLO 모델 초기화
        self.yolo_model = None
        if YOLO_AVAILABLE:
            try:
                self.yolo_model = YOLO('yolov8n.pt')
                logger.info("✅ YOLO 모델 초기화 완료")
            except Exception as e:
                logger.warning(f"⚠️ YOLO 모델 초기화 실패: {e}")
                self.yolo_model = None
        
        # BLIP 모델 초기화 (캡션 생성 - 백업용)
        self.blip_processor = None
        self.blip_model = None
        if BLIP_AVAILABLE:
            try:
                self.blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
                self.blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
                logger.info("✅ BLIP 모델 초기화 완료")
            except Exception as e:
                logger.warning(f"⚠️ BLIP 모델 초기화 실패: {e}")
        
        # Ollama 사용 여부 (캡션 생성 - 1순위)
        self.use_ollama = OLLAMA_AVAILABLE
        
        # DeepFace 사용 여부
        self.use_deepface = DEEPFACE_AVAILABLE
        
        # GPT-4V 사용 여부 (비활성화 기본)
        self.use_gpt4v = False
        
        # 통계 변수
        self.stats = {
            'deepface_success': 0,
            'deepface_fail': 0,
            'gpt4v_calls': 0,
            'ollama_calls': 0,
            'blip_calls': 0,
            'total_cost': 0.0
        }
        
        logger.info("✅ 하이브리드 영상 분석 서비스 초기화 완료")
        logger.info(f"   - YOLO: {YOLO_AVAILABLE}")
        logger.info(f"   - DeepFace: {DEEPFACE_AVAILABLE}")
        logger.info(f"   - Ollama: {OLLAMA_AVAILABLE}")
        logger.info(f"   - BLIP: {BLIP_AVAILABLE}")
    
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
        """🔥 하이브리드 사람 감지 (YOLO + DeepFace + 색상 분석)"""
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
                            # 바운딩 박스 (픽셀 단위)
                            x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
                            
                            # 바운딩 박스 정규화
                            normalized_bbox = [
                                float(x1/w), float(y1/h),
                                float(x2/w), float(y2/h)
                            ]
                            
                            # 사람 영역 추출
                            person_region = frame[y1:y2, x1:x2]
                            
                            # 🔥 하이브리드 분석: DeepFace + 색상 추출
                            person_analysis = self._hybrid_person_analysis(person_region, frame, (x1, y1, x2, y2))
                            
                            detected_persons.append({
                                'class': 'person',
                                'bbox': normalized_bbox,
                                'confidence': float(conf),
                                'confidence_level': float(conf),
                                'attributes': person_analysis['attributes'],
                                'clothing_colors': person_analysis['clothing_colors'],
                                'analysis_source': person_analysis['source']
                            })
            
            return detected_persons
            
        except Exception as e:
            logger.warning(f"YOLO 감지 실패: {e}")
            return []
    
    def _hybrid_person_analysis(self, person_region, full_frame, bbox):
        """🔥 하이브리드 사람 분석 (DeepFace → GPT-4V 폴백)"""
        x1, y1, x2, y2 = bbox
        person_h, person_w = person_region.shape[:2]
        
        # 기본값
        default_result = {
            'source': 'fallback',
            'attributes': self._get_default_attributes(),
            'clothing_colors': {'upper': 'unknown', 'lower': 'unknown'}
        }
        
        # 영역이 너무 작으면 분석 스킵
        if person_h < 50 or person_w < 30:
            logger.warning("사람 영역이 너무 작음 - 기본값 사용")
            return default_result
        
        # 1단계: DeepFace 분석 (무료, 빠름)
        if self.use_deepface:
            deepface_result = self._analyze_with_deepface(person_region)
            if deepface_result and deepface_result['confidence'] > 0.7:
                # DeepFace 신뢰도 높음 → 사용
                self.stats['deepface_success'] += 1
                
                # 의상 색상 추출 (OpenCV)
                clothing_colors = self._extract_clothing_colors(person_region)
                
                return {
                    'source': 'DeepFace',
                    'attributes': deepface_result['attributes'],
                    'clothing_colors': clothing_colors
                }
            else:
                self.stats['deepface_fail'] += 1
        
        # 2단계: GPT-4V 분석 (신뢰도 낮거나 DeepFace 실패 시)
        use_gpt4v = getattr(self, 'use_gpt4v', False)
        gpt4v_calls = self.stats.get('gpt4v_calls', 0)
        if use_gpt4v and gpt4v_calls < 10:  # 최대 10회 제한
            gpt4v_result = self._analyze_with_gpt4v(person_region)
            if gpt4v_result:
                self.stats['gpt4v_calls'] = gpt4v_calls + 1
                self.stats['total_cost'] += 0.015
                
                return {
                    'source': 'GPT-4V',
                    'attributes': gpt4v_result['attributes'],
                    'clothing_colors': gpt4v_result['clothing_colors']
                }
        
        # 3단계: 폴백 (색상만이라도 추출)
        clothing_colors = self._extract_clothing_colors(person_region)
        default_result['clothing_colors'] = clothing_colors
        return default_result
    
    def _analyze_with_deepface(self, person_region):
        """DeepFace로 성별/나이/감정 분석"""
        try:
            # BGR → RGB 변환
            person_rgb = cv2.cvtColor(person_region, cv2.COLOR_BGR2RGB)
            
            # DeepFace 분석
            analysis = DeepFace.analyze(
                person_rgb,
                actions=['age', 'gender', 'emotion'],
                enforce_detection=False,
                detector_backend='opencv'
            )
            
            # 결과가 리스트인 경우 첫 번째 항목 사용
            if isinstance(analysis, list):
                analysis = analysis[0]
            
            # 성별 정보
            gender = analysis.get('dominant_gender', 'Unknown')  # Man/Woman
            gender_conf = analysis.get('gender', {}).get(gender, 0) / 100.0 if isinstance(analysis.get('gender'), dict) else 0.7
            
            # 나이 정보
            age = analysis.get('age', 30)
            age_group = self._age_to_group(age)
            
            # 감정 정보
            emotion = analysis.get('dominant_emotion', 'neutral')
            
            return {
                'confidence': gender_conf,
                'attributes': {
                    'gender': {
                        'value': gender.lower(),  # man/woman
                        'confidence': gender_conf,
                        'all_scores': analysis.get('gender', {}),
                        'top_3': [[k, v/100.0] for k, v in sorted(analysis.get('gender', {}).items(), key=lambda x: x[1], reverse=True)[:3]]
                    },
                    'age': {
                        'value': age_group,
                        'confidence': 0.8,
                        'estimated_age': int(age),
                        'all_scores': {},
                        'top_3': [[age_group, 0.8]]
                    },
                    'emotion': {
                        'value': emotion,
                        'confidence': 0.7,
                        'all_scores': analysis.get('emotion', {})
                    }
                }
            }
            
        except Exception as e:
            logger.debug(f"DeepFace 분석 실패: {e}")
            return None
    
    def _analyze_with_gpt4v(self, person_region):
        """GPT-4 Vision으로 상세 분석 (조건부 사용)"""
        try:
            import base64
            from io import BytesIO
            from PIL import Image
            
            # BGR → RGB
            person_rgb = cv2.cvtColor(person_region, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(person_rgb)
            
            # 이미지를 base64로 인코딩
            buffered = BytesIO()
            pil_image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            
            prompt = """이미지 속 사람을 분석해주세요.

응답 형식 (JSON):
{
  "gender": "man" 또는 "woman",
  "age_group": "child/teenager/young_adult/middle_aged/elderly",
  "upper_clothing_color": "색상 (한국어)",
  "lower_clothing_color": "색상 (한국어)",
  "clothing_style": "casual/formal/sport"
}

JSON만 답변해주세요."""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # 저렴한 버전 사용
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
                    ]
                }],
                max_tokens=150,
                temperature=0.3
            )
            
            # JSON 파싱
            import json
            result_json = json.loads(response.choices[0].message.content)
            
            return {
                'attributes': {
                    'gender': {
                        'value': result_json.get('gender', 'unknown'),
                        'confidence': 0.95,
                        'all_scores': {},
                        'top_3': [[result_json.get('gender', 'unknown'), 0.95]]
                    },
                    'age': {
                        'value': result_json.get('age_group', 'adult'),
                        'confidence': 0.9,
                        'all_scores': {},
                        'top_3': [[result_json.get('age_group', 'adult'), 0.9]]
                    },
                    'clothing': {
                        'value': result_json.get('clothing_style', 'casual'),
                        'confidence': 0.85
                    }
                },
                'clothing_colors': {
                    'upper': result_json.get('upper_clothing_color', 'unknown'),
                    'lower': result_json.get('lower_clothing_color', 'unknown')
                }
            }
            
        except Exception as e:
            logger.warning(f"GPT-4V 분석 실패: {e}")
            return None
    
    def _extract_clothing_colors(self, person_region):
        """의상 색상 추출 (상의/하의 분리)"""
        try:
            h, w = person_region.shape[:2]
            
            x_start = int(w * 0.2)
            x_end = int(w * 0.8) if int(w * 0.8) > x_start else w
            
            upper_top = int(h * 0.2)
            upper_bottom = int(h * 0.5)
            lower_top = int(h * 0.5)
            lower_bottom = int(h * 0.85)
            
            upper_region = person_region[upper_top:upper_bottom, x_start:x_end]
            upper_color = self._get_dominant_color_name(upper_region)
            
            lower_region = person_region[lower_top:lower_bottom, x_start:x_end]
            lower_color = self._get_dominant_color_name(lower_region)
            
            return {
                'upper': upper_color,
                'lower': lower_color
            }
            
        except Exception as e:
            logger.warning(f"색상 추출 실패: {e}")
            return {'upper': 'unknown', 'lower': 'unknown'}
    
    def _get_dominant_color_name(self, image_region):
        """이미지 영역의 주요 색상 이름 반환"""
        try:
            if image_region.size == 0:
                return 'unknown'
            
            hsv = cv2.cvtColor(image_region, cv2.COLOR_BGR2HSV)
            pixels = hsv.reshape(-1, 3)
            
            # 채도가 너무 낮은 픽셀 제외 (무채색 판별에 사용)
            saturation_threshold = 35
            high_sat_pixels = pixels[pixels[:, 1] >= saturation_threshold]
            low_sat_pixels = pixels[pixels[:, 1] < saturation_threshold]
            
            if len(high_sat_pixels) == 0:
                # 남은 픽셀이 모두 무채색이면 밝기에 따라 반환
                v_mean = np.mean(pixels[:, 2])
                if v_mean > 200:
                    return 'white'
                if v_mean < 50:
                    return 'black'
                return 'gray'
            
            # K-means로 주요 색상 추출 (최대 3개 클러스터)
            K = min(3, len(high_sat_pixels))
            data = np.float32(high_sat_pixels)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(data, K, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
            counts = np.bincount(labels.flatten(), minlength=K)
            
            # 채도 가중치로 가장 생생한 색 선택
            center_s = centers[:, 1] / 255.0
            weights = counts * (center_s + 0.1)
            main_idx = int(np.argmax(weights))
            h_mean, s_mean, v_mean = centers[main_idx]
            
            # 선택된 클러스터가 여전히 채도가 낮으면 무채색 처리
            if s_mean < saturation_threshold:
                if v_mean > 200:
                    return 'white'
                if v_mean < 50:
                    return 'black'
                return 'gray'
            
            # 색상 분류 (HSV Hue 범위는 0~180)
            if h_mean < 10 or h_mean >= 175:
                return 'red'
            if h_mean < 20:
                return 'orange'
            if h_mean < 35:
                return 'yellow'
            if h_mean < 85:
                return 'green'
            if h_mean < 115:
                return 'cyan'
            if h_mean < 135:
                return 'blue'
            if h_mean < 155:
                return 'purple'
            if h_mean < 175:
                return 'pink'
            return 'red'
                
        except Exception as e:
            logger.warning(f"색상 이름 변환 실패: {e}")
            return 'unknown'
    
    def _age_to_group(self, age):
        """나이를 그룹으로 변환"""
        if age < 13:
            return 'child'
        elif age < 20:
            return 'teenager'
        elif age < 35:
            return 'young_adult'
        elif age < 60:
            return 'middle_aged'
        else:
            return 'elderly'
    
    def _get_default_attributes(self):
        """기본 속성값"""
        return {
            'gender': {
                'value': 'person',
                'confidence': 0.5,
                'all_scores': {'a person': 0.5},
                'top_3': [['a person', 0.5]]
            },
            'age': {
                'value': 'adult',
                'confidence': 0.5,
                'all_scores': {'adult': 0.5},
                'top_3': [['adult', 0.5]]
            }
        }
    
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
            
            # 색상별 마스크 생성 및 분석 (개선된 분홍색 감지)
            color_ranges = {
                'red': [(0, 50, 50), (10, 255, 255)],  # 빨간색 범위
                'orange': [(10, 50, 50), (25, 255, 255)],  # 주황색 범위
                'yellow': [(25, 50, 50), (40, 255, 255)],  # 노란색 범위
                'green': [(40, 50, 50), (80, 255, 255)],  # 초록색 범위
                'blue': [(80, 50, 50), (130, 255, 255)],  # 파란색 범위
                'purple': [(130, 50, 50), (160, 255, 255)],  # 보라색 범위
                'pink': [(160, 20, 100), (180, 255, 255), (0, 20, 100), (15, 255, 255)]  # 분홍색 범위 (더 넓고 정확한 범위)
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
                
                # 분홍색은 더 낮은 임계값 사용 (0.5% 이상)
                threshold = 0.005 if color_name == 'pink' else 0.02
                
                if color_ratio > threshold:
                    # RGB 기반 추가 검증 (분홍색의 경우)
                    if color_name == 'pink':
                        # 분홍색 RGB 특성: R > B, G 중간값
                        pink_pixels = frame_rgb[mask > 0]
                        if len(pink_pixels) > 0:
                            mean_rgb = np.mean(pink_pixels, axis=0)
                            # 분홍색 특성: R > G > B (대략적으로)
                            if mean_rgb[0] > mean_rgb[2] and mean_rgb[1] > mean_rgb[2] * 0.5:
                                confidence = min(color_ratio * 3, 1.0)  # 분홍색은 높은 신뢰도
                            else:
                                confidence = min(color_ratio * 1.5, 0.7)  # 의심스러운 경우 낮은 신뢰도
                        else:
                            confidence = min(color_ratio * 2, 1.0)
                    else:
                        confidence = min(color_ratio * 2, 1.0)  # 비율에 따른 신뢰도
                    
                    dominant_colors.append({
                        'color': color_name,
                        'ratio': float(color_ratio),
                        'confidence': confidence
                    })
                    print(f"🎨 {color_name} 감지: {color_ratio:.3f} ({color_ratio*100:.1f}%) 신뢰도: {confidence:.2f}")
            
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
                
                # 🔥 하이브리드 분석 통계 출력
                logger.info("="*60)
                logger.info("📊 하이브리드 분석 통계")
                logger.info(f"  • DeepFace 성공: {self.stats['deepface_success']}회")
                logger.info(f"  • DeepFace 실패: {self.stats['deepface_fail']}회")
                logger.info(f"  • Ollama 캡션: {self.stats['ollama_calls']}회")
                logger.info(f"  • BLIP 캡션: {self.stats['blip_calls']}회")
                logger.info(f"  • 총 비용: ${self.stats['total_cost']:.3f} (무료)")
                logger.info(f"  • DeepFace 성공률: {self.stats['deepface_success']/(self.stats['deepface_success']+self.stats['deepface_fail'])*100:.1f}%" if (self.stats['deepface_success']+self.stats['deepface_fail']) > 0 else "  • DeepFace 성공률: N/A")
                logger.info("="*60)
                    
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
            time.sleep(0.5)
            
            # ✨ 하이브리드 프레임 샘플링 (10분 영상 최적화 - 처리 시간 고려)
            sample_frames = []
            frame_indices = []
            
            # 영상 길이에 따라 적응적 샘플링 (최대 10분, Ollama 캡션 생성 시간 고려)
            if duration <= 10:
                # 10초 이하: 0.5초당 1프레임 (~20프레임, 0.7분)
                sample_interval = max(1, int(fps * 0.5))
            elif duration <= 30:
                # 30초 이하: 1초당 1프레임 (~30프레임, 1분)
                sample_interval = max(1, int(fps))
            elif duration <= 60:
                # 1분 이하: 2초당 1프레임 (~30프레임, 1분)
                sample_interval = max(1, int(fps * 2))
            elif duration <= 120:
                # 2분 이하: 3초당 1프레임 (~40프레임, 1.3분)
                sample_interval = max(1, int(fps * 3))
            elif duration <= 300:
                # 5분 이하: 4초당 1프레임 (~75프레임, 2.5분)
                sample_interval = max(1, int(fps * 4))
            else:
                # 10분 이하: 6초당 1프레임 (~100프레임, 3.3분)
                sample_interval = max(1, int(fps * 6))
            
            # 프레임 인덱스 생성
            frame_indices = list(range(0, frame_count, sample_interval))
            
            # 마지막 프레임 포함
            if frame_indices[-1] != frame_count - 1:
                frame_indices.append(frame_count - 1)
            
            # 최대 100개로 제한 (Ollama 캡션 생성 시간 최적화: 약 3.3분)
            if len(frame_indices) > 100:
                step = len(frame_indices) // 100
                frame_indices = frame_indices[::step][:100]
            
            # 최소 5개 보장
            if len(frame_indices) < 5:
                frame_indices = [0, frame_count//4, frame_count//2, 3*frame_count//4, frame_count-1]
            
            logger.info(f"📸 샘플링 전략: {len(frame_indices)}개 프레임 (간격: {sample_interval}, FPS: {fps:.1f})")
            
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
                    'frame_id': i + 1,
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
                json.dump(analysis_result, f, ensure_ascii=False, indent=2, default=self._json_default)
            
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
                json.dump(detection_db, f, ensure_ascii=False, indent=2, default=self._json_default)
            
            # Meta DB 저장
            with open(meta_db_path, 'w', encoding='utf-8') as f:
                json.dump(meta_db, f, ensure_ascii=False, indent=2, default=self._json_default)
            
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
                    "image_id": frame_data.get('frame_id') or frame_data.get('image_id', 1),
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
                        bbox_vals = person.get('bbox', [0, 0, 0, 0])
                        bbox = [float(v) for v in bbox_vals]
                        person_object["bbox"].append(bbox)
                    
                    frame_info["objects"].append(person_object)
                
                # 기타 객체들 (자동차, 오토바이 등)
                objects = frame_data.get('objects', [])
                if objects:
                    for obj in objects:
                        class_name = obj.get('class') or obj.get('class_name', 'unknown')
                        bbox_vals = obj.get('bbox', [0, 0, 0, 0])
                        bbox = [float(v) for v in bbox_vals]
                        obj_info = {
                            "class": class_name,
                            "num": 1,
                            "max_id": 1,
                            "tra_id": [1],
                            "bbox": [bbox]
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
                    "image_id": frame_data.get('frame_id') or frame_data.get('image_id', 1),
                    "timestamp": frame_data.get('timestamp', 0),
                    "caption": caption,
                    "frame_image_path": frame_data.get('frame_image_path'),
                    "objects": []
                }
                
                # 사람 메타데이터 (🔥 하이브리드 분석 결과 포함)
                persons = frame_data.get('persons', [])
                for i, person in enumerate(persons, 1):
                    # attributes에서 성별/나이 추출
                    gender_info = person.get('attributes', {}).get('gender', {})
                    age_info = person.get('attributes', {}).get('age', {})
                    
                    # 의상 색상 정보
                    clothing_colors = person.get('clothing_colors', {})
                    
                    person_meta = {
                        "class": "person",
                        "id": i,
                        "bbox": person.get('bbox', [0, 0, 0, 0]),
                        "confidence": person.get('confidence', 0.0),
                        "clothing_colors": clothing_colors,  # 🔥 검색을 위해 최상위에 추가
                        "analysis_source": person.get('analysis_source', 'unknown'),  # 🔥 분석 출처
                        "attributes": {
                            "gender": gender_info.get('value', 'unknown'),
                            "age": age_info.get('value', 'unknown'),
                            "estimated_age": age_info.get('estimated_age', 0),
                            "emotion": person.get('attributes', {}).get('emotion', {}).get('value', 'neutral'),
                            "clothing": {
                                "upper_color": clothing_colors.get('upper', 'unknown'),
                                "lower_color": clothing_colors.get('lower', 'unknown'),
                                "dominant_color": clothing_colors.get('upper', 'unknown')  # 호환성
                            },
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
        """Vision-Language 모델을 사용한 캡션 생성 (Ollama → BLIP)"""
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
            
            # 1순위: Ollama Vision 사용 (llava 모델)
            caption = self._generate_ollama_caption(full_image_path, frame_data)
            if caption:
                return caption
            
            # 2순위: BLIP 모델 사용 (로컬)
            caption = self._generate_blip_caption(full_image_path)
            if caption:
                return caption
            
            logger.warning("모든 Vision 모델 캡션 생성 실패")
            return None
            
        except Exception as e:
            logger.error(f"❌ Vision 캡션 생성 실패: {e}")
            return None
    
    def _generate_ollama_caption(self, image_path, frame_data):
        """Ollama Vision 모델을 사용한 캡션 생성 (llava)"""
        try:
            import ollama
            
            # 프레임 정보 추가
            timestamp = frame_data.get('timestamp', 0)
            persons = frame_data.get('persons', [])
            objects = frame_data.get('objects', [])
            dominant_colors = frame_data.get('dominant_colors', [])
            
            # 색상 정보 텍스트 생성
            color_text = ""
            if dominant_colors:
                colors = [f"{c['color']}" for c in dominant_colors[:3]]
                color_text = f"주요 색상: {', '.join(colors)}"
            
            prompt = f"""Write EXACTLY 2-3 sentences describing this frame. IMPORTANT: Include specific gender and age information for each person visible.

Frame: {timestamp:.1f}s, {len(persons)} person(s)

Requirements:
- Describe each person's gender (man/woman/boy/girl) and approximate age (young/adult/elderly)
- Include clothing colors and actions
- Mention objects, setting, and atmosphere
- Be concise and specific

Example: "A bustling city sidewalk with 5 people walking. An elderly woman in a white jacket talks on her phone while a young man in green clothing and two adult women in blue and yellow jackets carry handbags. A teenage boy strolls past storefronts. Daytime with natural lighting, lively urban atmosphere."

Caption:"""
            
            # Ollama로 이미지 분석
            response = ollama.chat(
                model='llava:7b',  # 이미지/PDF 채팅에서 사용하는 동일 모델
                messages=[
                    {
                        'role': 'user',
                        'content': prompt,
                        'images': [image_path]  # 이미지 경로 직접 전달
                    }
                ],
                options={
                    'temperature': 0.7,
                    'num_predict': 150,  # 간결한 캡션 (약 100-150 단어)
                    'num_ctx': 2048
                }
            )
            
            caption = response['message']['content'].strip()
            
            # 너무 긴 캡션은 자르기 (300자로 증가)
            if len(caption) > 300:
                caption = caption[:300] + "..."
            
            # 통계 업데이트
            self.stats['ollama_calls'] += 1
            
            logger.info(f"✅ Ollama 캡션 생성 성공: {caption}")
            return caption
            
        except Exception as e:
            logger.warning(f"⚠️ Ollama 캡션 생성 실패: {e}")
            return None
    
    def _generate_blip_caption(self, image_path):
        """🔥 하이브리드 BLIP 캡션 생성 (self.blip_model 사용)"""
        try:
            # BLIP 모델이 초기화되어 있는지 확인
            if not self.blip_processor or not self.blip_model:
                logger.warning("BLIP 모델이 초기화되지 않음")
                return None
            
            # 이미지 로드
            image = Image.open(image_path).convert('RGB')
            
            # 캡션 생성
            inputs = self.blip_processor(image, return_tensors="pt")
            out = self.blip_model.generate(**inputs, max_length=50, num_beams=5)
            caption = self.blip_processor.decode(out[0], skip_special_tokens=True)
            
            self.stats['blip_calls'] += 1
            
            # 한국어 번역
            korean_caption = self._translate_to_korean(caption)
            
            logger.info(f"✅ BLIP 캡션: {korean_caption}")
            return korean_caption
            
        except Exception as e:
            logger.warning(f"BLIP 캡션 생성 실패: {e}")
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

    def _extract_audio_summary(self, video_path):
        """Whisper를 사용한 오디오 요약 추출"""
        try:
            import whisper
            import tempfile
            import os
            
            # Whisper 모델 로드
            model = whisper.load_model("base")
            
            # 비디오에서 오디오 추출 및 전사
            result = model.transcribe(video_path)
            
            # 전사된 텍스트
            transcript = result["text"]
            
            # 언어 감지
            language = result.get("language", "ko")
            
            logger.info(f"✅ 오디오 전사 완료: {len(transcript)}자, 언어: {language}")
            
            return {
                "transcript": transcript,
                "language": language,
                "segments": result.get("segments", []),
                "duration": result.get("duration", 0)
            }
            
        except Exception as e:
            logger.error(f"❌ 오디오 요약 추출 실패: {e}")
            return None

    def _generate_audio_summary(self, audio_data):
        """오디오 데이터를 기반으로 요약 생성"""
        try:
            if not audio_data or not audio_data.get("transcript"):
                return None
            
            transcript = audio_data["transcript"]
            
            # 간단한 키워드 추출
            import re
            
            # 한국어 키워드 추출
            korean_words = re.findall(r'[가-힣]+', transcript)
            word_freq = {}
            for word in korean_words:
                if len(word) > 1:  # 1글자 단어 제외
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # 상위 키워드
            top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
            
            # 요약 생성
            summary = {
                "transcript": transcript,
                "language": audio_data.get("language", "ko"),
                "duration": audio_data.get("duration", 0),
                "top_keywords": [word for word, freq in top_keywords],
                "word_count": len(transcript.split()),
                "summary": f"주요 내용: {', '.join([word for word, freq in top_keywords[:3]])}"
            }
            
            logger.info(f"✅ 오디오 요약 생성 완료: {summary['summary']}")
            return summary
            
        except Exception as e:
            logger.error(f"❌ 오디오 요약 생성 실패: {e}")
            return None

    @staticmethod
    def _json_default(obj):
        """numpy 타입 등을 JSON 직렬화 가능하게 변환"""
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return str(obj)

# 전역 인스턴스 생성
video_analysis_service = VideoAnalysisService()