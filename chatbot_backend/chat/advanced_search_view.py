from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from chat.models import Video
from django.conf import settings
import json
import os
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class InterVideoSearchView(APIView):
    """영상 간 검색 (비가오는 밤 영상 찾기 등)"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            query = request.data.get('query', '')
            search_criteria = request.data.get('criteria', {})
            
            logger.info(f"🔍 영상 간 검색 요청: 쿼리='{query}', 기준={search_criteria}")
            
            if not query:
                return Response({'error': '검색 쿼리가 필요합니다.'}, status=400)
            
            # 모든 분석 완료된 영상 가져오기
            videos = Video.objects.filter(analysis_status='completed')
            
            if not videos.exists():
                return Response({
                    'query': query,
                    'results': [],
                    'total_results': 0,
                    'message': '분석 완료된 영상이 없습니다.'
                })
            
            # 검색 결과 생성
            search_results = self._perform_inter_video_search(videos, query, search_criteria)
            
            return Response({
                'query': query,
                'search_type': 'inter_video',
                'results': search_results,
                'total_results': len(search_results),
                'analysis_type': 'inter_video_search'
            })
            
        except Exception as e:
            logger.error(f"❌ 영상 간 검색 오류: {e}")
            return Response({'error': str(e)}, status=500)
    
    def _perform_inter_video_search(self, videos, query, criteria):
        """영상 간 검색 수행"""
        results = []
        query_lower = query.lower()
        
        for video in videos:
            try:
                # TeletoVision 형식 파일 찾기
                detection_db_path = os.path.join(settings.MEDIA_ROOT, f"{video.original_name}-detection_db.json")
                meta_db_path = os.path.join(settings.MEDIA_ROOT, f"{video.original_name}-meta_db.json")
                
                if not os.path.exists(detection_db_path) or not os.path.exists(meta_db_path):
                    continue
                
                # Detection DB와 Meta DB 읽기
                with open(detection_db_path, 'r', encoding='utf-8') as f:
                    detection_db = json.load(f)
                
                with open(meta_db_path, 'r', encoding='utf-8') as f:
                    meta_db = json.load(f)
                
                # 검색 점수 계산
                relevance_score = self._calculate_inter_video_score(detection_db, meta_db, query_lower, criteria)
                
                if relevance_score > 0.1:
                    result = {
                        'video_id': video.id,
                        'video_name': video.original_name,
                        'filename': video.filename,
                        'relevance_score': relevance_score,
                        'duration': video.duration,
                        'uploaded_at': video.uploaded_at,
                        'matched_scenes': self._find_matching_scenes(meta_db, query_lower),
                        'summary': self._generate_inter_video_summary(detection_db, meta_db, query_lower)
                    }
                    results.append(result)
                    
            except Exception as e:
                logger.warning(f"영상 {video.id} 검색 중 오류: {e}")
                continue
        
        # 관련도 순으로 정렬
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:10]
    
    def _calculate_inter_video_score(self, detection_db, meta_db, query_lower, criteria):
        """영상 간 검색 점수 계산"""
        score = 0.0
        
        # 비가오는 밤 검색
        if any(keyword in query_lower for keyword in ['비', 'rain', '밤', 'night', '어두운', 'dark']):
            score += self._calculate_weather_time_score(meta_db, 'rainy_night')
        
        # 시간대 검색
        if any(keyword in query_lower for keyword in ['오전', 'morning', '오후', 'afternoon', '저녁', 'evening']):
            score += self._calculate_time_score(meta_db, query_lower)
        
        # 객체 검색
        if any(keyword in query_lower for keyword in ['자동차', 'car', '사람', 'person', '오토바이', 'motorcycle']):
            score += self._calculate_object_score(detection_db, query_lower)
        
        # 색상 검색
        colors = ['빨간', '파란', '노란', '초록', '검은', '흰', '주황', '보라']
        if any(color in query_lower for color in colors):
            score += self._calculate_color_score(meta_db, query_lower)
        
        return min(score, 1.0)
    
    def _calculate_weather_time_score(self, meta_db, condition):
        """날씨/시간 조건 점수 계산"""
        score = 0.0
        frames = meta_db.get('frame', [])
        
        for frame in frames:
            scene_context = frame.get('objects', [{}])[0].get('scene_context', {}) if frame.get('objects') else {}
            lighting = scene_context.get('lighting', '').lower()
            
            if condition == 'rainy_night':
                if 'dark' in lighting:
                    score += 0.3
                # 비 관련 키워드는 실제로는 날씨 데이터가 필요하지만, 여기서는 조명으로 추정
                if 'dark' in lighting:
                    score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_time_score(self, meta_db, query_lower):
        """시간대 점수 계산"""
        score = 0.0
        frames = meta_db.get('frame', [])
        
        for frame in frames:
            timestamp = frame.get('timestamp', 0)
            # 시간대 추정 (실제로는 메타데이터에서 시간 정보를 가져와야 함)
            if '오전' in query_lower or 'morning' in query_lower:
                if 6 <= timestamp % 24 <= 12:
                    score += 0.2
            elif '오후' in query_lower or 'afternoon' in query_lower:
                if 12 <= timestamp % 24 <= 18:
                    score += 0.2
            elif '저녁' in query_lower or 'evening' in query_lower:
                if 18 <= timestamp % 24 <= 22:
                    score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_object_score(self, detection_db, query_lower):
        """객체 검색 점수 계산"""
        score = 0.0
        frames = detection_db.get('frame', [])
        
        for frame in frames:
            objects = frame.get('objects', [])
            for obj in objects:
                class_name = obj.get('class', '').lower()
                if '자동차' in query_lower or 'car' in query_lower:
                    if 'car' in class_name:
                        score += 0.3
                elif '사람' in query_lower or 'person' in query_lower:
                    if 'person' in class_name:
                        score += 0.2
                elif '오토바이' in query_lower or 'motorcycle' in query_lower:
                    if 'motorcycle' in class_name:
                        score += 0.3
        
        return min(score, 1.0)
    
    def _calculate_color_score(self, meta_db, query_lower):
        """색상 검색 점수 계산"""
        score = 0.0
        frames = meta_db.get('frame', [])
        
        for frame in frames:
            objects = frame.get('objects', [])
            for obj in objects:
                attributes = obj.get('attributes', {})
                clothing = attributes.get('clothing', {})
                dominant_color = clothing.get('dominant_color', '').lower()
                
                if any(color in query_lower for color in ['빨간', 'red']):
                    if 'red' in dominant_color:
                        score += 0.3
                elif any(color in query_lower for color in ['파란', 'blue']):
                    if 'blue' in dominant_color:
                        score += 0.3
                elif any(color in query_lower for color in ['주황', 'orange']):
                    if 'orange' in dominant_color:
                        score += 0.3
        
        return min(score, 1.0)
    
    def _find_matching_scenes(self, meta_db, query_lower):
        """매칭되는 장면 찾기"""
        matching_scenes = []
        frames = meta_db.get('frame', [])
        
        for frame in frames:
            timestamp = frame.get('timestamp', 0)
            objects = frame.get('objects', [])
            
            for obj in objects:
                if obj.get('class') == 'person':
                    attributes = obj.get('attributes', {})
                    clothing = attributes.get('clothing', {})
                    dominant_color = clothing.get('dominant_color', '').lower()
                    
                    if any(keyword in query_lower for keyword in ['주황', 'orange']):
                        if 'orange' in dominant_color:
                            matching_scenes.append({
                                'timestamp': timestamp,
                                'description': f"주황색 옷을 입은 사람 발견",
                                'confidence': obj.get('confidence', 0.0)
                            })
        
        return matching_scenes[:5]
    
    def _generate_inter_video_summary(self, detection_db, meta_db, query_lower):
        """영상 간 검색 결과 요약 생성"""
        frames = detection_db.get('frame', [])
        total_frames = len(frames)
        
        summary_parts = []
        
        # 기본 정보
        summary_parts.append(f"총 프레임: {total_frames}개")
        
        # 객체 통계
        total_persons = sum(
            sum(obj.get('num', 0) for obj in frame.get('objects', []) if obj.get('class') == 'person')
            for frame in frames
        )
        if total_persons > 0:
            summary_parts.append(f"감지된 사람: {total_persons}명")
        
        # 시간대 정보
        if any(keyword in query_lower for keyword in ['밤', 'night', '어두운', 'dark']):
            dark_frames = sum(
                1 for frame in meta_db.get('frame', [])
                if any(
                    obj.get('scene_context', {}).get('lighting', '').lower() == 'dark'
                    for obj in frame.get('objects', [])
                )
            )
            if dark_frames > 0:
                summary_parts.append(f"어두운 장면: {dark_frames}개")
        
        return " | ".join(summary_parts) if summary_parts else "관련 정보 없음"


class IntraVideoSearchView(APIView):
    """영상 내 검색 (주황색 상의 남성 추적 등)"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            video_id = request.data.get('video_id')
            query = request.data.get('query', '')
            search_criteria = request.data.get('criteria', {})
            
            logger.info(f"🔍 영상 내 검색 요청: 비디오={video_id}, 쿼리='{query}'")
            
            if not video_id or not query:
                return Response({'error': '비디오 ID와 검색 쿼리가 필요합니다.'}, status=400)
            
            try:
                video = Video.objects.get(id=video_id)
            except Video.DoesNotExist:
                return Response({'error': '비디오를 찾을 수 없습니다.'}, status=404)
            
            # TeletoVision 형식 파일 찾기
            detection_db_path = os.path.join(settings.MEDIA_ROOT, f"{video.original_name}-detection_db.json")
            meta_db_path = os.path.join(settings.MEDIA_ROOT, f"{video.original_name}-meta_db.json")
            
            if not os.path.exists(detection_db_path) or not os.path.exists(meta_db_path):
                return Response({'error': '분석 결과 파일을 찾을 수 없습니다.'}, status=404)
            
            # Detection DB와 Meta DB 읽기
            with open(detection_db_path, 'r', encoding='utf-8') as f:
                detection_db = json.load(f)
            
            with open(meta_db_path, 'r', encoding='utf-8') as f:
                meta_db = json.load(f)
            
            # 영상 내 검색 수행
            search_results = self._perform_intra_video_search(detection_db, meta_db, query, search_criteria)
            
            return Response({
                'video_id': video_id,
                'video_name': video.original_name,
                'query': query,
                'search_type': 'intra_video',
                'results': search_results,
                'total_results': len(search_results),
                'analysis_type': 'intra_video_search'
            })
            
        except Exception as e:
            logger.error(f"❌ 영상 내 검색 오류: {e}")
            return Response({'error': str(e)}, status=500)
    
    def _perform_intra_video_search(self, detection_db, meta_db, query, criteria):
        """🔥 영상 내 검색 수행 (하이브리드 분석 결과 지원)"""
        results = []
        query_lower = query.lower()
        
        frames = meta_db.get('frame', [])
        
        for frame in frames:
            timestamp = frame.get('timestamp', 0)
            objects = frame.get('objects', [])
            
            for obj in objects:
                if obj.get('class') == 'person':
                    # 조건에 맞는지 확인
                    if self._matches_person_criteria(obj, query_lower, criteria):
                        # 🔥 하이브리드 분석 결과 포함
                        result = {
                            'timestamp': timestamp,
                            'frame_id': frame.get('image_id', 1),
                            'person_id': obj.get('id', 1),
                            'bbox': obj.get('bbox', [0, 0, 0, 0]),
                            'confidence': obj.get('confidence', 0.0),
                            'attributes': obj.get('attributes', {}),
                            'clothing_colors': obj.get('clothing_colors', {}),  # 추가
                            'scene_context': obj.get('scene_context', {}),
                            'description': self._generate_person_description(obj, query_lower),
                            'analysis_source': obj.get('analysis_source', 'unknown')  # 추가
                        }
                        results.append(result)
        
        # 시간순으로 정렬
        results.sort(key=lambda x: x['timestamp'])
        
        logger.info(f"🔍 검색 결과: '{query}' → {len(results)}개 발견")
        
        return results
    
    def _matches_person_criteria(self, person_obj, query_lower, criteria):
        """🔥 사람 객체가 검색 조건에 맞는지 확인 (하이브리드 분석 결과 지원)"""
        attributes = person_obj.get('attributes', {})
        
        # 🔥 하이브리드 분석의 clothing_colors 필드 우선 사용
        clothing_colors = person_obj.get('clothing_colors', {})
        upper_color = clothing_colors.get('upper', '').lower()
        lower_color = clothing_colors.get('lower', '').lower()
        
        # 폴백: 기존 clothing 필드도 확인
        clothing = attributes.get('clothing', {})
        if not upper_color or upper_color == 'unknown':
            upper_color = clothing.get('upper_color', clothing.get('dominant_color', '')).lower()
        if not lower_color or lower_color == 'unknown':
            lower_color = clothing.get('lower_color', '').lower()
        
        # 색상 검색 (모든 색상 지원)
        color_keywords = {
            '빨강': ['red', '빨간', '빨강'],
            '주황': ['orange', '주황', '주황색'],
            '노랑': ['yellow', '노란', '노랑'],
            '초록': ['green', '초록', '녹색'],
            '파랑': ['blue', '파란', '파랑', '청색'],
            '보라': ['purple', '보라', '자주'],
            '분홍': ['pink', '분홍', '핑크'],
            '검정': ['black', '검은', '검정'],
            '하양': ['white', '흰', '하양', '백색'],
            '회색': ['gray', 'grey', '회색']
        }
        
        for color_name, keywords in color_keywords.items():
            if any(kw in query_lower for kw in keywords):
                target_color = keywords[0]  # 영어 색상명
                if target_color in upper_color or target_color in lower_color:
                    return True
        
        # 성별 검색
        if any(keyword in query_lower for keyword in ['남성', '남자', 'man', 'male']):
            gender = attributes.get('gender', '').lower()
            if 'man' in gender or 'male' in gender:
                return True
        
        if any(keyword in query_lower for keyword in ['여성', '여자', 'woman', 'female']):
            gender = attributes.get('gender', '').lower()
            if 'woman' in gender or 'female' in gender:
                return True
        
        # 나이 검색
        if any(keyword in query_lower for keyword in ['성인', 'adult', '어린이', 'child', '청소년', 'teenager']):
            age = attributes.get('age', '').lower()
            if 'adult' in query_lower and 'adult' in age:
                return True
            elif 'child' in query_lower and 'child' in age:
                return True
            elif 'teenager' in query_lower and 'teenager' in age:
                return True
        
        return False
    
    def _generate_person_description(self, person_obj, query_lower):
        """🔥 사람 객체 설명 생성 (하이브리드 분석 결과 지원)"""
        attributes = person_obj.get('attributes', {})
        
        # 🔥 하이브리드 분석 결과 사용
        clothing_colors = person_obj.get('clothing_colors', {})
        upper_color = clothing_colors.get('upper', 'unknown')
        lower_color = clothing_colors.get('lower', 'unknown')
        
        # 성별/나이 정보
        gender = attributes.get('gender', 'unknown')
        age = attributes.get('age', 'unknown')
        estimated_age = attributes.get('estimated_age', 0)
        emotion = attributes.get('emotion', 'neutral')
        
        # 분석 소스
        analysis_source = person_obj.get('analysis_source', 'unknown')
        
        description_parts = []
        
        # 색상 정보 추가 (한국어로 변환)
        color_map = {
            'red': '빨간색', 'orange': '주황색', 'yellow': '노란색',
            'green': '초록색', 'blue': '파란색', 'purple': '보라색',
            'pink': '분홍색', 'black': '검은색', 'white': '흰색', 'gray': '회색'
        }
        
        if upper_color and upper_color != 'unknown':
            color_kr = color_map.get(upper_color, upper_color)
            description_parts.append(f"{color_kr} 상의")
        
        if lower_color and lower_color != 'unknown':
            color_kr = color_map.get(lower_color, lower_color)
            description_parts.append(f"{color_kr} 하의")
        
        # 성별 정보
        if gender and gender != 'unknown':
            gender_kr = '남성' if 'man' in gender or 'male' in gender else '여성' if 'woman' in gender or 'female' in gender else gender
            description_parts.append(gender_kr)
        
        # 나이 정보
        if estimated_age and estimated_age > 0:
            description_parts.append(f"{estimated_age}세")
        elif age and age != 'unknown':
            age_kr = {
                'child': '어린이', 'teenager': '청소년',
                'young_adult': '청년', 'middle_aged': '중년',
                'elderly': '노인'
            }.get(age, age)
            description_parts.append(age_kr)
        
        # 감정 정보 (옵션)
        if emotion and emotion != 'neutral' and emotion != 'unknown':
            emotion_kr = {
                'happy': '행복', 'sad': '슬픔', 'angry': '화남',
                'fear': '두려움', 'surprise': '놀람', 'disgust': '혐오'
            }.get(emotion, emotion)
            description_parts.append(f"({emotion_kr})")
        
        # 분석 출처 표시
        source_note = {
            'DeepFace': '✓AI분석',
            'GPT-4V': '✓GPT분석',
            'fallback': ''
        }.get(analysis_source, '')
        
        desc = ', '.join(description_parts) if description_parts else "사람"
        return f"{desc} {source_note}".strip()


class TemporalAnalysisView(APIView):
    """시간대별 분석 (3:00-5:00 성비 분포 등)"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            video_id = request.data.get('video_id')
            time_range = request.data.get('time_range', {})
            analysis_type = request.data.get('analysis_type', 'gender_distribution')
            
            logger.info(f"📊 시간대별 분석 요청: 비디오={video_id}, 범위={time_range}, 타입={analysis_type}")
            
            if not video_id:
                return Response({'error': '비디오 ID가 필요합니다.'}, status=400)
            
            try:
                video = Video.objects.get(id=video_id)
            except Video.DoesNotExist:
                return Response({'error': '비디오를 찾을 수 없습니다.'}, status=404)
            
            # TeletoVision 형식 파일 찾기
            meta_db_path = os.path.join(settings.MEDIA_ROOT, f"{video.original_name}-meta_db.json")
            
            if not os.path.exists(meta_db_path):
                return Response({'error': '분석 결과 파일을 찾을 수 없습니다.'}, status=404)
            
            # Meta DB 읽기
            with open(meta_db_path, 'r', encoding='utf-8') as f:
                meta_db = json.load(f)
            
            # 시간대별 분석 수행
            analysis_result = self._perform_temporal_analysis(meta_db, time_range, analysis_type)
            
            return Response({
                'video_id': video_id,
                'video_name': video.original_name,
                'time_range': time_range,
                'analysis_type': analysis_type,
                'result': analysis_result,
                'analysis_type': 'temporal_analysis'
            })
            
        except Exception as e:
            logger.error(f"❌ 시간대별 분석 오류: {e}")
            return Response({'error': str(e)}, status=500)
    
    def _perform_temporal_analysis(self, meta_db, time_range, analysis_type):
        """시간대별 분석 수행"""
        start_time = time_range.get('start', 0)  # 초 단위
        end_time = time_range.get('end', 0)      # 초 단위
        
        frames = meta_db.get('frame', [])
        
        # 시간 범위 내 프레임 필터링
        filtered_frames = [
            frame for frame in frames
            if start_time <= frame.get('timestamp', 0) <= end_time
        ]
        
        if analysis_type == 'gender_distribution':
            return self._analyze_gender_distribution(filtered_frames)
        elif analysis_type == 'age_distribution':
            return self._analyze_age_distribution(filtered_frames)
        elif analysis_type == 'activity_pattern':
            return self._analyze_activity_pattern(filtered_frames)
        else:
            return {'error': '지원하지 않는 분석 타입입니다.'}
    
    def _analyze_gender_distribution(self, frames):
        """성비 분포 분석 - 개선된 버전 (색상 정보 포함)"""
        gender_count = {'male': 0, 'female': 0, 'unknown': 0}
        total_persons = 0
        
        # 의상 색상 분포 수집 (상의/하의 분리)
        upper_clothing_colors = {}
        lower_clothing_colors = {}
        
        # 신뢰도 정보
        confidence_scores = []
        
        for frame in frames:
            objects = frame.get('objects', [])
            for obj in objects:
                if obj.get('class') == 'person':
                    attributes = obj.get('attributes', {})
                    
                    # 성별 정보
                    gender = attributes.get('gender', 'unknown').lower()
                    if 'man' in gender or 'male' in gender:
                        gender_count['male'] += 1
                    elif 'woman' in gender or 'female' in gender:
                        gender_count['female'] += 1
                    else:
                        gender_count['unknown'] += 1
                    total_persons += 1
                    
                    # 신뢰도 정보
                    confidence = obj.get('confidence', 0)
                    if confidence > 0:
                        confidence_scores.append(confidence)
                    
                    # 의상 색상 정보
                    clothing = attributes.get('clothing', {})
                    if isinstance(clothing, dict):
                        dominant_color = clothing.get('dominant_color', 'unknown')
                        if dominant_color and dominant_color != 'unknown':
                            # 상의 색상으로 간주
                            upper_clothing_colors[dominant_color] = upper_clothing_colors.get(dominant_color, 0) + 1
                        
                        # 하의 색상 (있는 경우)
                        lower_color = clothing.get('lower_color', 'unknown')
                        if lower_color and lower_color != 'unknown':
                            lower_clothing_colors[lower_color] = lower_clothing_colors.get(lower_color, 0) + 1
        
        # 비율 계산
        if total_persons > 0:
            gender_ratio = {
                'male': round(gender_count['male'] / total_persons * 100, 1),
                'female': round(gender_count['female'] / total_persons * 100, 1),
                'unknown': round(gender_count['unknown'] / total_persons * 100, 1)
            }
        else:
            gender_ratio = {'male': 0, 'female': 0, 'unknown': 0}
        
        # 평균 신뢰도
        avg_confidence = round(sum(confidence_scores) / len(confidence_scores), 3) if confidence_scores else 0.0
        
        # 정확도 안내 메시지
        if gender_count['unknown'] > total_persons * 0.8:
            accuracy_note = '⚠️ 미상 비율이 높습니다. 영상 해상도나 각도를 확인하세요.'
        elif avg_confidence > 0.7:
            accuracy_note = '✓ 신뢰할 수 있는 분석 결과'
        else:
            accuracy_note = 'ℹ️ 보통 신뢰도'
        
        return {
            'total_persons': total_persons,
            'gender_count': gender_count,
            'gender_ratio': gender_ratio,
            'upper_clothing_colors': dict(sorted(upper_clothing_colors.items(), key=lambda x: x[1], reverse=True)),
            'lower_clothing_colors': dict(sorted(lower_clothing_colors.items(), key=lambda x: x[1], reverse=True)),
            'average_confidence': avg_confidence,
            'accuracy_note': accuracy_note,
            'data_source': '영상 분석 결과 (메타데이터)',
            'analysis_summary': f"총 {total_persons}명 중 남성 {gender_ratio['male']}%, 여성 {gender_ratio['female']}% {accuracy_note}"
        }
    
    def _analyze_age_distribution(self, frames):
        """나이 분포 분석"""
        age_count = {'child': 0, 'teenager': 0, 'adult': 0, 'elderly': 0, 'unknown': 0}
        total_persons = 0
        
        for frame in frames:
            objects = frame.get('objects', [])
            for obj in objects:
                if obj.get('class') == 'person':
                    age = obj.get('attributes', {}).get('age', 'unknown').lower()
                    if 'child' in age:
                        age_count['child'] += 1
                    elif 'teenager' in age:
                        age_count['teenager'] += 1
                    elif 'adult' in age:
                        age_count['adult'] += 1
                    elif 'elderly' in age:
                        age_count['elderly'] += 1
                    else:
                        age_count['unknown'] += 1
                    total_persons += 1
        
        return {
            'total_persons': total_persons,
            'age_count': age_count,
            'analysis_summary': f"총 {total_persons}명의 나이 분포 분석 완료"
        }
    
    def _analyze_activity_pattern(self, frames):
        """활동 패턴 분석"""
        activity_levels = {'low': 0, 'medium': 0, 'high': 0, 'unknown': 0}
        
        for frame in frames:
            objects = frame.get('objects', [])
            for obj in objects:
                scene_context = obj.get('scene_context', {})
                activity_level = scene_context.get('activity_level', 'unknown').lower()
                if activity_level in activity_levels:
                    activity_levels[activity_level] += 1
        
        return {
            'activity_levels': activity_levels,
            'analysis_summary': f"활동 패턴 분석 완료"
        }
