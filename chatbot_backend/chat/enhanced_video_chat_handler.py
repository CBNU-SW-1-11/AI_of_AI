"""
개선된 영상 채팅 핸들러 (버그 수정 버전)
- Ollama 캡션 기반 답변
- 다중 AI 모델 (GPT, Claude, Mixtral) 통합
- 색상 2중 검증 (캡션 + 추출된 색상)
- 영상/일반 질문 자동 구분
- chatbots import 문제 해결
- Ollama 한국어 응답 강제
"""

import os
import json
import logging
import re
import ollama
from django.conf import settings

logger = logging.getLogger(__name__)


def get_chatbots():
    """chatbots 전역 변수를 가져오는 헬퍼 함수 (lazy import)"""
    try:
        from .utils.chatbot import chatbots
        logger.info("✅ chatbots import 성공")
        return chatbots
    except Exception as e:
        logger.warning(f"⚠️ chatbots import 실패: {e}")
        return {}


class EnhancedVideoChatHandler:
    """개선된 영상 채팅 핸들러"""
    
    def __init__(self, video_id, video):
        self.video_id = video_id
        self.video = video
        self.meta_db = None
        self.detection_db = None
        self.frames = []
        self._load_analysis_data()
    
    def _load_analysis_data(self):
        """영상 분석 데이터 로드"""
        try:
            # Meta DB 로드 (Ollama 캡션 포함)
            # 1순위: analysis_json_path에서 원본 파일명 추출
            meta_db_path = None
            media_dir = settings.MEDIA_ROOT
            
            if self.video.analysis_json_path:
                analysis_file = os.path.join(media_dir, self.video.analysis_json_path)
                if os.path.exists(analysis_file):
                    try:
                        with open(analysis_file, 'r', encoding='utf-8') as f:
                            analysis_data = json.load(f)
                            # video_summary에서 원본 파일명 찾기
                            video_id_in_json = analysis_data.get('video_summary', {}).get('video_id')
                            if video_id_in_json:
                                test_path = os.path.join(media_dir, f"{video_id_in_json}-meta_db.json")
                                if os.path.exists(test_path):
                                    meta_db_path = test_path
                                    logger.info(f"✅ analysis_json에서 원본 파일명 추출 성공: {video_id_in_json}")
                    except Exception as e:
                        logger.warning(f"⚠️ analysis_json 파싱 실패: {e}")
            
            # 2순위: filename에서 타임스탬프 제거하여 원본 파일명 추출
            if not meta_db_path and self.video.filename:
                # filename 형식: upload_{timestamp}_{original_filename}
                # 예: upload_1762940209_upload_1758152157_test2.mp4
                filename_base = os.path.splitext(self.video.filename)[0]
                
                # upload_로 시작하는 경우 타임스탬프 부분 제거 시도
                if filename_base.startswith('upload_'):
                    # 여러 패턴 시도
                    # 패턴 1: upload_{timestamp}_upload_{original} -> upload_{original} (확장자 포함/제외 모두)
                    if '_upload_' in filename_base:
                        parts = filename_base.split('_upload_', 1)
                        if len(parts) == 2:
                            # 확장자 포함 버전 먼저 시도 (Meta DB는 원본 파일명에 확장자 포함)
                            possible_original_with_ext = f"upload_{parts[1]}.mp4"
                            test_path = os.path.join(media_dir, f"{possible_original_with_ext}-meta_db.json")
                            if os.path.exists(test_path):
                                meta_db_path = test_path
                                logger.info(f"✅ filename에서 원본 파일명 추출 성공 (패턴1-확장자포함): {possible_original_with_ext}")
                            
                            # 확장자 제외 버전
                            possible_original_no_ext = f"upload_{parts[1]}"
                            test_path = os.path.join(media_dir, f"{possible_original_no_ext}-meta_db.json")
                            if os.path.exists(test_path):
                                meta_db_path = test_path
                                logger.info(f"✅ filename에서 원본 파일명 추출 성공 (패턴1-확장자제외): {possible_original_no_ext}")
                            
                            # 확장자 포함 버전 (원본 파일명에 .mp4가 포함된 경우)
                            if not meta_db_path:
                                possible_original_with_ext = f"upload_{parts[1]}.mp4"
                                test_path = os.path.join(media_dir, f"{possible_original_with_ext}-meta_db.json")
                                if os.path.exists(test_path):
                                    meta_db_path = test_path
                                    logger.info(f"✅ filename에서 원본 파일명 추출 성공 (패턴1-확장자포함): {possible_original_with_ext}")
                    
                    # 패턴 2: upload_{timestamp}_{original} -> {original}
                    if not meta_db_path:
                        parts = filename_base.split('_', 2)  # 최대 2번만 split
                        if len(parts) >= 3:
                            # 마지막 부분이 원본 파일명일 가능성
                            possible_original = parts[2]
                            # 확장자 제외
                            test_path = os.path.join(media_dir, f"{possible_original}-meta_db.json")
                            if os.path.exists(test_path):
                                meta_db_path = test_path
                                logger.info(f"✅ filename에서 원본 파일명 추출 성공 (패턴2-확장자제외): {possible_original}")
                            # 확장자 포함
                            if not meta_db_path:
                                test_path = os.path.join(media_dir, f"{possible_original}.mp4-meta_db.json")
                                if os.path.exists(test_path):
                                    meta_db_path = test_path
                                    logger.info(f"✅ filename에서 원본 파일명 추출 성공 (패턴2-확장자포함): {possible_original}.mp4")
                
                # 전체 filename도 시도 (확장자 제외/포함)
                if not meta_db_path:
                    test_path = os.path.join(media_dir, f"{filename_base}-meta_db.json")
                    if os.path.exists(test_path):
                        meta_db_path = test_path
                        logger.info(f"✅ filename 전체로 Meta DB 발견 (확장자제외): {filename_base}")
                    else:
                        # 확장자 포함
                        test_path = os.path.join(media_dir, f"{self.video.filename}-meta_db.json")
                        if os.path.exists(test_path):
                            meta_db_path = test_path
                            logger.info(f"✅ filename 전체로 Meta DB 발견 (확장자포함): {self.video.filename}")
            
            # 3순위: original_name 시도 (이름 변경 전 원본일 수 있음)
            if not meta_db_path and self.video.original_name:
                original_base = os.path.splitext(self.video.original_name)[0]
                test_path = os.path.join(media_dir, f"{original_base}-meta_db.json")
                if os.path.exists(test_path):
                    meta_db_path = test_path
                    logger.info(f"✅ original_name으로 Meta DB 발견: {original_base}")
            
            # 4순위: media 디렉토리에서 모든 meta_db 파일 검색 (video_id 기반)
            if not meta_db_path:
                logger.warning(f"⚠️ 일반 경로에서 Meta DB 파일을 찾지 못함. media 디렉토리 전체 검색 시도: {self.video_id}")
                if os.path.exists(media_dir):
                    # 모든 meta_db.json 파일 검색
                    import glob
                    meta_db_files = glob.glob(os.path.join(media_dir, "*-meta_db.json"))
                    # 가장 최근 파일 사용 (분석이 가장 최근에 완료된 것)
                    if meta_db_files:
                        # 파일 수정 시간으로 정렬
                        meta_db_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                        # 일단 첫 번째 파일 사용 (나중에 더 정확한 매칭 로직 추가 가능)
                        meta_db_path = meta_db_files[0]
                        logger.warning(f"⚠️ 가장 최근 Meta DB 파일 사용: {os.path.basename(meta_db_path)}")
            
            if meta_db_path and os.path.exists(meta_db_path):
                with open(meta_db_path, 'r', encoding='utf-8') as f:
                    self.meta_db = json.load(f)
                self.frames = self.meta_db.get('frame', [])
                logger.info(f"✅ Meta DB 로드 성공: {len(self.frames)}개 프레임, 파일: {os.path.basename(meta_db_path)}")
            else:
                logger.warning(f"❌ Meta DB 파일을 찾을 수 없음. video_id: {self.video_id}, filename: {self.video.filename}, original_name: {self.video.original_name}")
        
        except Exception as e:
            logger.error(f"❌ 분석 데이터 로드 실패: {e}")
    
    def is_video_related_question(self, message):
        """영상 관련 질문인지 판단"""
        video_keywords = [
            '영상', 'video', '동영상', '비디오',
            '사람', 'people', 'person', '남자', '여자', 'man', 'woman',
            '옷', 'clothing', 'shirt', 'jacket', '색상', 'color',
            '배경', 'background', 'scene', '장면',
            '몇', 'how many', 'count', '개수',
            '있', 'is there', 'are there',
            '찾', 'find', 'search',
            '쇼핑몰', 'mall', 'shopping',
            '거리', 'street', '밤', 'night', '낮', 'day',
            '전화', 'phone', '걷', 'walk',
            '요약', 'summary', 'summarize'
        ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in video_keywords)
    
    def search_frames_by_keywords(self, keywords):
        """키워드로 프레임 검색 (캡션 + 객체 정보 기반)"""
        found_frames = []
        
        for frame in self.frames:
            caption = frame.get('caption', '').lower()
            match_score = 0
            matched_keywords = []
            matched_objects = []
            
            # 1. 캡션에서 키워드 검색
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in caption:
                    match_score += 2  # 캡션 매칭 시 2점
                    matched_keywords.append(keyword)
            
            # 2. 객체 정보에서 키워드 검색 (더 높은 점수)
            objects = frame.get('objects', [])
            for obj in objects:
                obj_class = obj.get('class', '').lower()
                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    # 정확히 일치하거나 포함되는 경우
                    if keyword_lower == obj_class or keyword_lower in obj_class or obj_class in keyword_lower:
                        match_score += 3  # 객체 매칭 시 3점 (캡션보다 우선)
                        if obj_class not in matched_objects:
                            matched_objects.append(obj_class)
                        if keyword not in matched_keywords:
                            matched_keywords.append(keyword)
                        logger.info(f"  🎯 객체 매칭 발견: '{keyword}' -> '{obj_class}' (프레임 {frame.get('image_id', 0)})")
            
            # 적어도 하나 이상의 키워드가 매칭되면 추가
            if match_score > 0:
                frame_with_score = frame.copy()
                frame_with_score['match_score'] = match_score
                found_frames.append(frame_with_score)
                if matched_objects:
                    logger.info(f"✅ 프레임 {frame.get('image_id', 0)} 추가: 객체 매칭 {matched_objects}, 점수: {match_score}")
        
        # 매칭 점수로 정렬 (높은 순)
        found_frames.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        return found_frames
    
    def search_frames_by_color(self, color_name):
        """색상으로 프레임 검색 (캡션 우선 + 색상 추출 보조)"""
        if not color_name:
            return []
        
        found_frames = []
        color_name_lower = color_name.lower()
        
        # 한국어 → 영어 기본 색상 매핑
        korean_to_english = {
            '분홍색': 'pink',
            '핑크': 'pink',
            '보라색': 'purple',
            '보라': 'purple',
            '자주색': 'purple',
            '자홍색': 'purple',
            '파란색': 'blue',
            '파랑': 'blue',
            '푸른색': 'blue',
            '남색': 'blue',
            '하늘색': 'blue',
            '초록색': 'green',
            '초록': 'green',
            '녹색': 'green',
            '연두색': 'green',
            '노란색': 'yellow',
            '노랑': 'yellow',
            '황색': 'yellow',
            '주황색': 'orange',
            '주황': 'orange',
            '오렌지': 'orange',
            '빨간색': 'red',
            '빨강': 'red',
            '적색': 'red',
            '흰색': 'white',
            '하얀색': 'white',
            '검은색': 'black',
            '까만색': 'black',
            '회색': 'gray',
            '그레이': 'gray',
            '은색': 'gray',
            '은빛': 'gray'
        }
        
        base_color = korean_to_english.get(color_name_lower, color_name_lower)
        
        # 색상 동의어 매핑 (pink -> rose, fuchsia 등)
        color_synonyms = {
            'pink': ['pink', 'rose', 'fuchsia', 'magenta', 'rosy'],
            'red': ['red', 'crimson', 'scarlet'],
            'orange': ['orange', 'amber', 'tangerine'],
            'yellow': ['yellow', 'gold', 'golden'],
            'green': ['green', 'lime', 'emerald'],
            'blue': ['blue', 'navy', 'azure', 'teal'],
            'purple': ['purple', 'violet', 'lavender'],
            'white': ['white', 'ivory'],
            'black': ['black'],
            'gray': ['gray', 'grey', 'silver']
        }
        synonyms = color_synonyms.get(base_color, [base_color])
        
        # 원본 검색어(한국어 포함)를 보조 키워드로 추가
        if color_name_lower not in synonyms:
            synonyms.append(color_name_lower)
        
        for frame in self.frames:
            match_score = 0
            caption = frame.get('caption', '').lower()
            caption_weight = 3  # Ollama 캡션 우선 가중치
            color_weight = 1    # 색상 추출 보조 가중치
            explicit_weight = 2  # 명시적 언급 가중치 (예: "green clothing")
            
            # 1. 캡션에서 색상 검색 (우선 순위 높음)
            if any(word in caption for word in synonyms):
                match_score += caption_weight
                
                # 명시적 언급 확인 (예: "green clothing", "in green", "wearing green")
                for word in synonyms:
                    if f"{word} clothing" in caption or f"in {word}" in caption or f"wearing {word}" in caption:
                        match_score += explicit_weight
                        break
            
            # 2. 추출된 색상 정보 확인 (보조)
            objects = frame.get('objects', [])
            green_person_count = 0  # 초록색 옷을 입은 사람 수
            for obj in objects:
                if obj.get('class') == 'person':
                    clothing_colors = obj.get('clothing_colors', {})
                    upper_color = (clothing_colors.get('upper') or '').lower()
                    lower_color = (clothing_colors.get('lower') or '').lower()
                    attrs = obj.get('attributes', {})
                    clothing = attrs.get('clothing', {})
                    dominant_color = (clothing.get('dominant_color') or '').lower()
                    
                    # 상의가 초록색이거나 dominant_color가 초록색인 경우
                    if any(word in upper_color for word in synonyms) or any(word in dominant_color for word in synonyms):
                        match_score += color_weight
                        green_person_count += 1
            
            # 초록색 옷을 입은 사람 수에 따른 추가 점수 (최대 3점)
            if green_person_count > 0:
                match_score += min(green_person_count, 3)
            
            if match_score > 0:
                frame_with_score = frame.copy()
                frame_with_score['match_score'] = match_score
                frame_with_score['green_person_count'] = green_person_count
                found_frames.append(frame_with_score)
        
        # 점수 순 정렬 (높은 점수 우선), 점수가 같으면 타임스탬프 순 (빠른 시간 우선)
        found_frames.sort(key=lambda x: (x.get('match_score', 0), -x.get('timestamp', 0)), reverse=True)
        
        # 중복 타임스탬프 제거 후 상위 5개만 반환
        unique_frames = []
        seen_timestamps = set()
        for frame in found_frames:
            ts_key = round(frame.get('timestamp', 0), 2)
            if ts_key in seen_timestamps:
                continue
            unique_frames.append(frame)
            seen_timestamps.add(ts_key)
            if len(unique_frames) >= 5:
                break
        
        return unique_frames
    
    def analyze_people_count(self):
        """영상 전체의 고유한 사람 수 분석 (프레임별 중복 고려)"""
        import re
        
        # 각 프레임에서 명시적으로 언급된 사람 수 추출
        people_counts = []
        
        number_words = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
        }
        
        for frame in self.frames:
            caption = frame.get('caption', '').lower()
            timestamp = frame.get('timestamp', 0)
            
            # "five people", "three individuals", "two men" 등의 패턴 찾기
            for num_word, num in number_words.items():
                patterns = [
                    f'{num_word} people',
                    f'{num_word} individuals',
                    f'{num_word} men',
                    f'{num_word} women',
                    f'{num_word} persons'
                ]
                
                for pattern in patterns:
                    if pattern in caption:
                        people_counts.append({
                            'timestamp': timestamp,
                            'count': num,
                            'caption_excerpt': caption[:100]
                        })
                        break
                
                if people_counts and people_counts[-1]['timestamp'] == timestamp:
                    break
        
        # 최대 사람 수를 기준으로 판단 (같은 사람들이 여러 프레임에 등장)
        if people_counts:
            max_count_info = max(people_counts, key=lambda x: x['count'])
            max_count = max_count_info['count']
            
            return {
                'estimated_count': max_count,
                'confidence': 'high',
                'evidence': people_counts,
                'explanation': f"프레임 분석 결과, 한 장면에서 최대 {max_count}명이 등장합니다. 영상 전체에서는 같은 사람들이 여러 프레임에 나타나므로, 고유한 사람 수는 약 {max_count}명 정도로 추정됩니다."
            }
        else:
            # 명시적 언급이 없으면 "group", "people" 등으로 추정
            group_count = sum(1 for f in self.frames if 'group' in f.get('caption', '').lower() or 'people' in f.get('caption', '').lower())
            
            if group_count > 0:
                return {
                    'estimated_count': '3-5',
                    'confidence': 'medium',
                    'evidence': [],
                    'explanation': f"영상에서 여러 명의 사람들이 그룹으로 등장하지만, 정확한 숫자는 명시되지 않았습니다. 대략 3-5명 정도로 추정됩니다."
                }
            else:
                return {
                    'estimated_count': 'unknown',
                    'confidence': 'low',
                    'evidence': [],
                    'explanation': "영상 분석에서 사람 수를 명확히 파악할 수 없습니다."
                }
    
    def analyze_gender_ratio(self):
        """영상 전체의 성비 분석"""
        import re
        
        # 성별 키워드 매핑
        gender_keywords = {
            'man': 'male', 'men': 'male', 'male': 'male',
            'woman': 'female', 'women': 'female', 'female': 'female',
            'boy': 'male', 'boys': 'male',
            'girl': 'female', 'girls': 'female'
        }
        
        # 연령대 키워드
        age_keywords = {
            'young': 'young', 'teen': 'young', 'teenage': 'young',
            'adult': 'adult', 'middle-aged': 'adult',
            'elderly': 'elderly', 'old': 'elderly', 'senior': 'elderly'
        }
        
        male_count = 0
        female_count = 0
        unknown_count = 0
        
        gender_evidence = []
        
        for frame in self.frames:
            caption = frame.get('caption', '').lower()
            timestamp = frame.get('timestamp', 0)
            
            # 성별 키워드 찾기
            frame_males = 0
            frame_females = 0
            
            for keyword, gender in gender_keywords.items():
                matches = re.findall(rf'\b{keyword}\b', caption)
                if matches:
                    for match in matches:
                        if gender == 'male':
                            frame_males += 1
                        else:
                            frame_females += 1
            
            if frame_males > 0 or frame_females > 0:
                gender_evidence.append({
                    'timestamp': timestamp,
                    'males': frame_males,
                    'females': frame_females,
                    'caption_excerpt': caption[:100]
                })
        
        # 전체 성별 카운트
        total_males = sum(ev['males'] for ev in gender_evidence)
        total_females = sum(ev['females'] for ev in gender_evidence)
        
        if total_males > 0 or total_females > 0:
            total_people = total_males + total_females
            male_ratio = (total_males / total_people) * 100 if total_people > 0 else 0
            female_ratio = (total_females / total_people) * 100 if total_people > 0 else 0
            
            return {
                'male_count': total_males,
                'female_count': total_females,
                'total_gendered': total_people,
                'male_ratio': round(male_ratio, 1),
                'female_ratio': round(female_ratio, 1),
                'confidence': 'medium' if len(gender_evidence) > 2 else 'low',
                'evidence': gender_evidence,
                'explanation': f"영상에서 성별이 명시된 인물: 남성 {total_males}명, 여성 {total_females}명 (남성 {male_ratio:.1f}%, 여성 {female_ratio:.1f}%)"
            }
        else:
            return {
                'male_count': 0,
                'female_count': 0,
                'total_gendered': 0,
                'male_ratio': 0,
                'female_ratio': 0,
                'confidence': 'low',
                'evidence': [],
                'explanation': "영상 분석에서 성별 정보를 명확히 파악할 수 없습니다. 캡션에 성별이 명시되지 않았습니다."
            }
    
    def _call_ollama_korean(self, prompt, max_tokens=500):
        """Ollama 호출 (한국어 강제)"""
        try:
            # 한국어 응답 강제를 위한 시스템 프롬프트 추가
            korean_system_prompt = """당신은 한국어로만 답변하는 AI 어시스턴트입니다. 
모든 답변은 반드시 한국어로 작성해야 합니다.
영어, 프랑스어, 베트남어 등 다른 언어를 절대 사용하지 마세요.
간결하고 명확한 한국어로만 답변하세요."""
            
            response = ollama.chat(
                model='llama3.2:latest',
                messages=[
                    {
                        'role': 'system',
                        'content': korean_system_prompt
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                options={
                    'temperature': 0.3,  # 낮은 온도로 일관성 향상
                    'num_predict': max_tokens
                }
            )
            
            return response['message']['content'].strip()
            
        except Exception as e:
            logger.error(f"❌ Ollama 호출 실패: {e}")
            return None
    
    def generate_answer_with_multi_ai(self, message, context_frames=None, include_video_context=True):
        """다중 AI 모델로 답변 생성 및 통합"""
        try:
            # 컨텍스트 구성
            if include_video_context:
                context = f"영상 정보:\n"
                # 프레임 수와 영상 길이 정보는 제외 (불필요한 정보)
            else:
                context = ""
            
            if context_frames:
                context += f"관련 프레임 ({len(context_frames)}개):\n"
                for i, frame in enumerate(context_frames[:5], 1):  # 최대 5개만
                    timestamp = frame.get('timestamp', 0)
                    caption = frame.get('caption', '')
                    # child/children 키워드가 있으면 전체 캡션 포함, 없으면 300자로 제한
                    if 'child' in caption.lower() or 'children' in caption.lower() or 'kid' in caption.lower():
                        context += f"{i}. [{timestamp:.1f}s] {caption}\n"
                    else:
                        context += f"{i}. [{timestamp:.1f}s] {caption[:300]}\n"
                    
                    # 객체 정보 추가 (YOLO로 감지된 객체들)
                    objects = frame.get('objects', [])
                    if objects:
                        # person이 아닌 객체들만 명시적으로 나열
                        other_objects = [obj for obj in objects if obj.get('class', '').lower() != 'person']
                        if other_objects:
                            object_names = [obj.get('class', 'unknown') for obj in other_objects]
                            # 중복 제거
                            unique_objects = list(set(object_names))
                            if unique_objects:
                                context += f"   감지된 객체: {', '.join(unique_objects)}\n"
            else:
                # 전체 요약
                context += "영상 주요 내용:\n"
                for i, frame in enumerate(self.frames[::max(1, len(self.frames)//5)], 1):  # 샘플 5개
                    timestamp = frame.get('timestamp', 0)
                    caption = frame.get('caption', '')
                    context += f"- [{timestamp:.1f}s] {caption[:150]}\n"
            
            # AI 질문 구성
            # 요약 질문인지 확인
            is_summary_question = '요약' in message.lower() or 'summary' in message.lower() or '정리' in message.lower()
            
            if include_video_context:
                if is_summary_question:
                    # 요약 질문일 때는 색상 등 세부 정보를 최대한 생략
                    ai_prompt = f"""다음 영상 정보를 바탕으로 사용자의 질문에 한국어로 간결하고 자연스럽게 답변해주세요.

⚠️ 중요: 반드시 아래 제공된 영상 정보만을 기반으로 답변해야 합니다. 영상에 없는 내용은 추측하지 마세요.

{context}

사용자 질문: {message}

답변 요구사항:
1. 핵심만 간결하게 답변 (최대 3-4문장)
2. 질문에 직접적으로 답변
3. 반드시 위에 제공된 영상 정보만을 기반으로 답변 (영상에 없는 내용은 "없습니다" 또는 "보이지 않습니다"라고 답변)
4. 불필요한 설명 생략 (프레임 수, 영상 길이 등 기술적 정보는 언급하지 마세요)
5. ⚠️ 색상, 옷의 색깔, 의상의 색상 등 시각적 세부 정보는 절대 언급하지 마세요. 예를 들어 "초록색 옷", "녹색 의상", "색상의 옷" 같은 표현은 사용하지 마세요.
6. 영상의 전체적인 분위기, 장소, 사람들의 활동에 집중하세요
7. 인물에 대해 언급할 때는 "어린이도 여러 번 등장", "어린이도 등장" 같은 표현 대신 "다양한 연령대의 사람들", "어린이와 성인들이 함께" 같은 자연스러운 표현을 사용하세요
8. 영상과 무관한 일반적인 답변 금지
9. 반드시 한국어로만 작성"""
                else:
                    ai_prompt = f"""다음 영상 정보를 바탕으로 사용자의 질문에 한국어로 간결하게 답변해주세요.

⚠️ 중요: 반드시 아래 제공된 영상 정보만을 기반으로 답변해야 합니다. 영상에 없는 내용은 추측하지 마세요.

{context}

사용자 질문: {message}

답변 요구사항:
1. 핵심만 간결하게 답변 (최대 3-4문장)
2. 질문에 직접적으로 답변
3. 반드시 위에 제공된 영상 정보만을 기반으로 답변 (영상에 없는 내용은 "없습니다" 또는 "보이지 않습니다"라고 답변)
4. 불필요한 설명 생략 (프레임 수, 영상 길이 등 기술적 정보는 언급하지 마세요)
5. 영상과 무관한 일반적인 답변 금지
6. 반드시 한국어로만 작성"""
            else:
                ai_prompt = f"""사용자의 질문에 한국어로 간결하고 친근하게 답변해주세요.

사용자 질문: {message}

답변 요구사항:
1. 핵심만 간결하게 답변 (최대 2-3문장)
2. 친근한 톤 유지
3. 불필요한 설명 생략
4. 반드시 한국어로만 작성"""
            
            # 다중 AI 응답 생성
            ai_responses = {}
            
            # chatbots 가져오기 (lazy import)
            chatbots = get_chatbots()
            
            # 우선순위 AI 모델 선택 (chatbots의 키 이름)
            priority_model_keys = [
                'gpt-4o-mini',           # GPT-4o Mini
                'gemini-2.0-flash-lite', # Gemini 2.0 Flash Lite
                'claude-3.5-haiku'       # Claude 3.5 Haiku
            ]
            
            # chatbots에서 지정된 모델 찾아서 답변 생성
            if chatbots:
                logger.info(f"✅ chatbots 사용 가능, 모델 수: {len(chatbots)}")
                logger.info(f"   가능한 모델: {list(chatbots.keys())}")
                
                for model_key in priority_model_keys:
                    if model_key in chatbots:
                        try:
                            bot = chatbots[model_key]
                            response = bot.chat(ai_prompt)
                            
                            # 부적절한 응답 필터링 (영상 정보 부재 메시지 및 불필요한 기술 정보)
                            blocked_patterns = [
                                "죄송하지만 제공된 영상 정보는 실제 영상이 아니라 텍스트 설명일 뿐입니다",
                                "제공된 영상 정보는 실제 영상이 아니라",
                                "텍스트 설명일 뿐입니다",
                                "실제 영상이 아니라 텍스트",
                                "지금 있는 곳이 어디인지",
                                "알려주시면",
                                "궁금한데",
                                "무슨 게임이나 영화",
                                "질문하신 내용에 따라"
                            ]
                            
                            # 영상과 무관한 일반적인 답변 패턴 (Gemini 등이 자주 사용)
                            irrelevant_patterns = [
                                "질문하신 내용에 따라",
                                "지금 있는 곳이",
                                "알려주시면",
                                "무슨 게임이나 영화",
                                "궁금한데",
                                "응!",
                                "나올 수 있지"
                            ]
                            
                            # 불필요한 기술 정보 제거 (프레임 수, 영상 길이 등)
                            unwanted_patterns = [
                                "프레임으로 구성되어 있으며",
                                "초의 짧은 길이",
                                "프레임 수",
                                "영상 길이",
                                "초의 길이",
                                "개 프레임",
                                "프레임으로 구성"
                            ]
                            
                            response_str = str(response) if response else ""
                            is_blocked = any(pattern in response_str for pattern in blocked_patterns)
                            
                            # 영상과 무관한 답변 검증 (영상 컨텍스트가 있는데 일반적인 답변인 경우)
                            if include_video_context and context:
                                is_irrelevant = any(pattern in response_str for pattern in irrelevant_patterns)
                                # 영상 정보가 제공되었는데 답변에 영상 관련 키워드가 거의 없는 경우
                                video_keywords = ["영상", "프레임", "장면", "포착", "등장", "나타", "보여", "보이"]
                                has_video_context = any(keyword in response_str for keyword in video_keywords)
                                
                                if is_irrelevant and not has_video_context:
                                    logger.warning(f"⚠️ {model_key} 응답 차단: 영상과 무관한 일반적인 답변")
                                    continue
                            
                            if is_blocked:
                                logger.warning(f"⚠️ {model_key} 응답 차단: 부적절한 메시지 포함")
                                continue
                            
                            # 불필요한 기술 정보 제거
                            for pattern in unwanted_patterns:
                                if pattern in response_str:
                                    # 해당 패턴이 포함된 문장 제거
                                    # 패턴 주변의 문장 제거 (문장 단위로 제거)
                                    # 예: "6개의 프레임으로 구성되어 있으며, 0.0초의 짧은 길이입니다."
                                    response_str = re.sub(
                                        r'[^.]{0,30}' + re.escape(pattern) + r'[^.]{0,30}[.]?',
                                        '',
                                        response_str,
                                        flags=re.IGNORECASE
                                    )
                                    # 연속된 공백 정리
                                    response_str = re.sub(r'\s+', ' ', response_str)
                                    logger.info(f"🔧 {model_key} 응답에서 불필요한 기술 정보 제거: {pattern}")
                            
                            response = response_str.strip()
                            
                            ai_responses[model_key] = response
                            logger.info(f"✅ {model_key} 답변 생성 완료")
                        except Exception as e:
                            logger.warning(f"⚠️ {model_key} 답변 생성 실패: {e}")
                    else:
                        logger.warning(f"⚠️ {model_key} 모델을 chatbots에서 찾을 수 없음")
            else:
                logger.warning("⚠️ chatbots를 가져올 수 없음, Ollama만 사용")
            
            # Ollama를 백업으로 사용 (한국어 강제)
            ollama_answer = self._call_ollama_korean(ai_prompt)
            
            # 응답이 없으면 Ollama만 사용
            if not ai_responses:
                logger.warning("⚠️ 모든 AI 모델 실패, Ollama로 재시도")
                if ollama_answer:
                    return {
                    'integrated': ollama_answer,
                    'individual': {'ollama': ollama_answer}
                }
                else:
                    return {
                        'integrated': "죄송합니다. 답변 생성 중 오류가 발생했습니다.",
                        'individual': {}
                    }
            
            # 응답이 1개만 있으면 그대로 반환
            if len(ai_responses) == 1:
                single_answer = list(ai_responses.values())[0]
                return {
                    'integrated': single_answer,
                    'individual': ai_responses
                }
            
            # 다중 응답 통합
            integrated_answer = self._integrate_multi_ai_responses(ai_responses, message)
            
            # 개별 응답 + 통합 응답 반환
            return {
                'integrated': integrated_answer,
                'individual': ai_responses
            }
            
        except Exception as e:
            logger.error(f"❌ 답변 생성 실패: {e}")
            return {
                'integrated': "죄송합니다. 답변 생성 중 오류가 발생했습니다.",
                'individual': {}
            }
    
    def _integrate_multi_ai_responses(self, ai_responses, original_question):
        """다중 AI 응답 통합 (HCX-DASH-001 사용)"""
        try:
            # 각 AI의 응답을 정리
            responses_text = ""
            for model_name, response in ai_responses.items():
                responses_text += f"### {model_name.upper()}:\n{response}\n\n"
            
            # HCX-DASH-001로 통합 답변 생성
            chatbots = get_chatbots()
            hcx_bot = None
            
            # HCX-DASH-001 찾기 (정확한 키 이름)
            hcx_model_keys = ['clova-hcx-dash-001', 'HCX-DASH-001', 'hcx-dash-001']
            for key in hcx_model_keys:
                if key in chatbots:
                    hcx_bot = chatbots[key]
                    logger.info(f"✅ HCX-DASH-001 모델 발견: {key}")
                    break
            
            # 요약 질문인지 확인
            is_summary_question = '요약' in original_question.lower() or 'summary' in original_question.lower() or '정리' in original_question.lower()
            
            if is_summary_question:
                integration_prompt = f"""다음은 여러 AI 모델이 동일한 질문에 대해 답변한 내용입니다.
핵심만 간결하고 자연스럽게 통합하여 답변해주세요.

⚠️ 중요: 영상 정보를 기반으로 한 답변만 통합하세요. 영상과 무관한 일반적인 답변은 제외하세요.

질문: {original_question}

{responses_text}

통합 답변 요구사항:
1. 핵심 내용만 간결하게 통합 (최대 3-4문장)
2. 질문에 직접적으로 답변
3. 영상 정보를 기반으로 한 답변만 포함 (영상과 무관한 일반적인 답변은 제외)
4. 불필요한 설명 생략 (프레임 수, 영상 길이, 초 단위 등 기술적 정보는 절대 언급하지 마세요)
5. ⚠️ 색상, 옷의 색깔, 의상의 색상 등 시각적 세부 정보는 절대 언급하지 마세요. 예를 들어 "초록색 옷", "녹색 의상", "색상의 옷", "여러 사람의 초록색 의상" 같은 표현은 완전히 제거하세요.
6. 영상의 전체적인 분위기, 장소, 사람들의 활동에 집중하세요
7. 인물에 대해 언급할 때는 "어린이도 여러 번 등장", "어린이도 등장" 같은 표현 대신 "다양한 연령대의 사람들", "어린이와 성인들이 함께" 같은 자연스러운 표현을 사용하세요
8. 반드시 한국어로만 작성"""
            else:
                integration_prompt = f"""다음은 여러 AI 모델이 동일한 질문에 대해 답변한 내용입니다.
핵심만 간결하게 통합하여 답변해주세요.

⚠️ 중요: 영상 정보를 기반으로 한 답변만 통합하세요. 영상과 무관한 일반적인 답변은 제외하세요.

질문: {original_question}

{responses_text}

통합 답변 요구사항:
1. 핵심 내용만 간결하게 통합 (최대 3-4문장)
2. 질문에 직접적으로 답변
3. 영상 정보를 기반으로 한 답변만 포함 (영상과 무관한 일반적인 답변은 제외)
4. 불필요한 설명 생략 (프레임 수, 영상 길이, 초 단위 등 기술적 정보는 절대 언급하지 마세요)
5. 반드시 한국어로만 작성"""
            
            # HCX-DASH-001 사용
            if hcx_bot:
                try:
                    integrated = hcx_bot.chat(integration_prompt)
                    logger.info(f"✅ HCX-DASH-001 통합 답변 생성 완료")
                except Exception as e:
                    logger.warning(f"⚠️ HCX-DASH-001 실패, Ollama로 대체: {e}")
                    integrated = self._call_ollama_korean(integration_prompt, max_tokens=800)
            else:
                # HCX-DASH-001이 없으면 Ollama 사용
                logger.warning("⚠️ HCX-DASH-001 없음, Ollama 사용")
                integrated = self._call_ollama_korean(integration_prompt, max_tokens=800)
            
            # 통합 응답에서도 불필요한 기술 정보 및 영상과 무관한 답변 제거
            if integrated:
                unwanted_patterns = [
                    "프레임으로 구성되어 있으며",
                    "초의 짧은 길이",
                    "프레임 수",
                    "영상 길이",
                    "초의 길이",
                    "개 프레임",
                    "프레임으로 구성"
                ]
                
                irrelevant_patterns = [
                    "질문하신 내용에 따라",
                    "지금 있는 곳이",
                    "알려주시면",
                    "무슨 게임이나 영화",
                    "궁금한데",
                    "응!",
                    "나올 수 있지"
                ]
                
                integrated_str = str(integrated)
                
                # 영상과 무관한 답변 제거
                for pattern in irrelevant_patterns:
                    if pattern in integrated_str:
                        integrated_str = re.sub(
                            r'[^.]{0,30}' + re.escape(pattern) + r'[^.]{0,30}[.]?',
                            '',
                            integrated_str,
                            flags=re.IGNORECASE
                        )
                        logger.info(f"🔧 통합 응답에서 영상과 무관한 답변 제거: {pattern}")
                
                # 불필요한 기술 정보 제거
                for pattern in unwanted_patterns:
                    if pattern in integrated_str:
                        integrated_str = re.sub(
                            r'[^.]{0,30}' + re.escape(pattern) + r'[^.]{0,30}[.]?',
                            '',
                            integrated_str,
                            flags=re.IGNORECASE
                        )
                        # 연속된 공백 정리
                        integrated_str = re.sub(r'\s+', ' ', integrated_str)
                        logger.info(f"🔧 통합 응답에서 불필요한 기술 정보 제거: {pattern}")
                
                integrated = integrated_str.strip()
            
            # 각 AI 분석 추가
            if integrated:
                integrated += "\n\n---\n**각 AI 분석:**\n"
            for model_name in ai_responses.keys():
                integrated += f"- {model_name.upper()}\n"
            else:
                # Ollama도 실패하면 첫 번째 응답 반환
                integrated = list(ai_responses.values())[0]
            
            return integrated
            
        except Exception as e:
            logger.error(f"❌ 통합 답변 생성 실패: {e}")
            # 실패 시 첫 번째 응답 반환
            return list(ai_responses.values())[0]
    
    def handle_general_question(self, message):
        """일반 질문 처리 (영상 무관)"""
        try:
            answer = self._call_ollama_korean(message)
            return answer if answer else "죄송합니다. 답변 생성 중 오류가 발생했습니다."
            
        except Exception as e:
            logger.error(f"❌ 일반 질문 처리 실패: {e}")
            return "죄송합니다. 답변 생성 중 오류가 발생했습니다."
    
    def process_message(self, message):
        """
        메시지 처리 메인 함수
        
        Returns:
            dict: {
                'answer': str,  # 통합 답변
                'individual_responses': dict,  # 각 AI 개별 답변
                'frames': list,  # 관련 프레임 정보
                'frame_images': list,  # 프레임 이미지 경로
                'is_video_related': bool
            }
        """
        result = {
            'answer': '',
            'individual_responses': {},
            'frames': [],
            'frame_images': [],
            'is_video_related': False
        }
        
        # 1. 영상 관련 질문인지 확인
        if not self.is_video_related_question(message):
            # 일반 질문도 다중 AI로 처리 (영상 컨텍스트 제외)
            ai_result = self.generate_answer_with_multi_ai(message, None, include_video_context=False)
            if isinstance(ai_result, dict):
                result['answer'] = ai_result.get('integrated', '')
                result['individual_responses'] = ai_result.get('individual', {})
            else:
                result['answer'] = ai_result
            result['is_video_related'] = False
            return result
        
        result['is_video_related'] = True
        
        # 2. 하이라이트/요약 질문인지 확인
        highlight_keywords = ['하이라이트', 'highlight', '주요 장면', '핵심 장면', '중요한 장면']
        summary_keywords = ['요약', 'summary', '정리']
        
        is_highlight_question = any(keyword in message.lower() for keyword in highlight_keywords)
        is_summary_question = any(keyword in message.lower() for keyword in summary_keywords)
        
        if is_highlight_question or is_summary_question:
            # 하이라이트 프레임 선택 (다양성 기반)
            highlight_frames = []
            
            # 전체 프레임을 5-7개 구간으로 나눠서 대표 프레임 선택
            if len(self.frames) > 0:
                num_highlights = min(7, len(self.frames))  # 최대 7개
                step = max(1, len(self.frames) // num_highlights)
                
                for i in range(0, len(self.frames), step):
                    if len(highlight_frames) < num_highlights:
                        frame = self.frames[i]
                        # 사람이 많거나 캡션이 긴 프레임 우선
                        persons = frame.get('persons', [])
                        caption = frame.get('caption', '')
                        frame_copy = frame.copy()
                        frame_copy['highlight_score'] = len(persons) + len(caption) / 10
                        highlight_frames.append(frame_copy)
                
                # 점수 순으로 정렬하여 상위 5개 선택
                highlight_frames.sort(key=lambda x: x.get('highlight_score', 0), reverse=True)
                highlight_frames = highlight_frames[:5]
                
                # 타임스탬프 순으로 재정렬
                highlight_frames.sort(key=lambda x: x.get('timestamp', 0))
            
            if highlight_frames:
                result['frames'] = highlight_frames
                result['frame_images'] = [
                    frame.get('frame_image_path') or f"images/video{self.video_id}_frame{frame.get('image_id')}.jpg"
                    for frame in highlight_frames
                ]
                
                # 하이라이트 컨텍스트 생성
                highlight_context = f"""🎬 영상 하이라이트 장면 ({len(highlight_frames)}개):

"""
                for i, frame in enumerate(highlight_frames, 1):
                    timestamp = frame.get('timestamp', 0)
                    caption = frame.get('caption', '')
                    persons = frame.get('persons', [])
                    highlight_context += f"{i}. [{timestamp:.1f}초] {caption[:150]}\n"
                    highlight_context += f"   - 등장 인물: {len(persons)}명\n\n"
                
                highlight_context += f"\n질문: {message}\n"
                
                # 다중 AI로 답변 생성
                ai_result = self.generate_answer_with_multi_ai(highlight_context, highlight_frames)
                if isinstance(ai_result, dict):
                    result['answer'] = ai_result.get('integrated', '')
                    result['individual_responses'] = ai_result.get('individual', {})
                else:
                    result['answer'] = ai_result
            else:
                result['answer'] = "하이라이트 장면을 찾을 수 없습니다."
            
            return result
        
        # 3. 사람 수 질문인지 확인
        people_count_keywords = ['몇명', '몇 명', '사람 수', '인원', 'how many people', 'how many person']
        is_people_count_question = any(keyword in message.lower() for keyword in people_count_keywords)
        
        if is_people_count_question:
            # 사람 수 분석
            count_analysis = self.analyze_people_count()
            
            # 증거 프레임 찾기 (최대 카운트가 나온 프레임)
            evidence_frames = []
            if count_analysis['evidence']:
                max_count = count_analysis['estimated_count']
                for evidence in count_analysis['evidence']:
                    if evidence['count'] == max_count:
                        # 해당 타임스탬프의 프레임 찾기
                        for frame in self.frames:
                            if frame.get('timestamp') == evidence['timestamp']:
                                evidence_frames.append(frame)
                                break
            
            if evidence_frames:
                result['frames'] = evidence_frames
                result['frame_images'] = [
                    frame.get('frame_image_path') or f"images/video{self.video_id}_frame{frame.get('image_id')}.jpg"
                    for frame in evidence_frames
                ]
            
            # 개선된 컨텍스트로 AI 답변 생성
            enhanced_context = f"""🎯 중요: 영상 전체의 고유한 사람 수를 계산해주세요. 같은 사람들이 여러 프레임에 반복 등장하므로 중복 카운팅하지 마세요!

영상 전체 사람 수 분석 결과:
- 추정 인원: {count_analysis['estimated_count']}명
- 신뢰도: {count_analysis['confidence']}
- 핵심 근거: {count_analysis['explanation']}

프레임별 명시된 인원 수:
"""
            if count_analysis['evidence']:
                for i, ev in enumerate(count_analysis['evidence'][:5], 1):
                    enhanced_context += f"{i}. [{ev['timestamp']:.1f}초] {ev['count']}명 명시적으로 언급됨\n"
                
                max_count = max([ev['count'] for ev in count_analysis['evidence']])
                enhanced_context += f"\n✅ 결론: 한 장면에서 최대 {max_count}명이 등장하며, 이는 같은 사람들이 다른 프레임에도 나타나므로 영상 전체의 고유한 사람 수는 약 {max_count}명입니다.\n"
            
            enhanced_context += f"\n⚠️ 주의: 각 프레임의 사람 수를 합산하지 말고, 영상 전체의 고유한 인원을 답변하세요.\n"
            enhanced_context += f"\n원래 질문: {message}"
            
            # 다중 AI로 답변 생성 (개선된 컨텍스트 포함)
            ai_result = self.generate_answer_with_multi_ai(enhanced_context, evidence_frames if evidence_frames else None)
            if isinstance(ai_result, dict):
                result['answer'] = ai_result.get('integrated', '')
                result['individual_responses'] = ai_result.get('individual', {})
            else:
                result['answer'] = ai_result
            
            return result
        
        # 4. 성비 질문인지 확인
        gender_ratio_keywords = ['성비', '남녀비', '성별', '남성', '여성', '남자', '여자', 'gender ratio', 'male female']
        is_gender_ratio_question = any(keyword in message.lower() for keyword in gender_ratio_keywords)
        
        if is_gender_ratio_question:
            # 성비 분석
            gender_analysis = self.analyze_gender_ratio()
            
            # 증거 프레임 찾기
            evidence_frames = []
            if gender_analysis['evidence']:
                for evidence in gender_analysis['evidence'][:3]:  # 최대 3개
                    for frame in self.frames:
                        if frame.get('timestamp') == evidence['timestamp']:
                            evidence_frames.append(frame)
                            break
            
            if evidence_frames:
                result['frames'] = evidence_frames
                result['frame_images'] = [
                    frame.get('frame_image_path') or f"images/video{self.video_id}_frame{frame.get('image_id')}.jpg"
                    for frame in evidence_frames
                ]
            
            # 개선된 컨텍스트로 AI 답변 생성
            enhanced_context = f"""🎯 중요: 영상의 성비(남녀 비율)를 분석해주세요!

영상 성비 분석 결과:
- 남성: {gender_analysis['male_count']}명 ({gender_analysis['male_ratio']:.1f}%)
- 여성: {gender_analysis['female_count']}명 ({gender_analysis['female_ratio']:.1f}%)
- 성별 명시된 총 인원: {gender_analysis['total_gendered']}명
- 신뢰도: {gender_analysis['confidence']}
- 분석 근거: {gender_analysis['explanation']}

프레임별 성별 정보:
"""
            if gender_analysis['evidence']:
                for i, ev in enumerate(gender_analysis['evidence'][:5], 1):
                    enhanced_context += f"{i}. [{ev['timestamp']:.1f}초] 남성 {ev['males']}명, 여성 {ev['females']}명\n"
            
            enhanced_context += f"\n⚠️ 주의: 성별이 명시되지 않은 인물도 있을 수 있으므로, 전체 인원 수와 차이가 날 수 있습니다.\n"
            enhanced_context += f"\n원래 질문: {message}"
            
            # 다중 AI로 답변 생성
            ai_result = self.generate_answer_with_multi_ai(enhanced_context, evidence_frames if evidence_frames else None)
            if isinstance(ai_result, dict):
                result['answer'] = ai_result.get('integrated', '')
                result['individual_responses'] = ai_result.get('individual', {})
            else:
                result['answer'] = ai_result
            
            return result
        
        # 5. 색상 검색 질문인지 확인
        color_keywords = {
            '분홍': 'pink', '핑크': 'pink', 'pink': 'pink',
            '빨강': 'red', '빨간': 'red', 'red': 'red',
            '파랑': 'blue', '파란': 'blue', 'blue': 'blue',
            '노랑': 'yellow', '노란': 'yellow', 'yellow': 'yellow',
            '초록': 'green', '녹색': 'green', 'green': 'green',
            '하양': 'white', '흰': 'white', 'white': 'white',
            '검정': 'black', '검은': 'black', 'black': 'black',
            '주황': 'orange', '오렌지': 'orange', 'orange': 'orange',
            '보라': 'purple', 'purple': 'purple',
            '회색': 'gray', 'gray': 'gray', 'grey': 'gray'
        }
        
        found_color = None
        for korean, english in color_keywords.items():
            if korean in message.lower():
                found_color = english
                break
        
        if found_color:
            # 색상 기반 검색
            context_frames = self.search_frames_by_color(found_color)
            
            if context_frames:
                result['frames'] = context_frames[:10]  # 최대 10개
                result['frame_images'] = [
                    frame.get('frame_image_path') or f"images/video{self.video_id}_frame{frame.get('image_id')}.jpg"
                    for frame in context_frames[:10]
                ]
                
                # 답변 생성 (다중 AI)
                ai_result = self.generate_answer_with_multi_ai(message, context_frames)
                if isinstance(ai_result, dict):
                    result['answer'] = ai_result.get('integrated', '')
                    result['individual_responses'] = ai_result.get('individual', {})
                else:
                    result['answer'] = ai_result
            else:
                result['answer'] = f"영상에서 {found_color} 색상의 옷을 입은 사람을 찾을 수 없습니다."
        
        else:
            # 일반 영상 질문 (키워드 검색)
            # 의미 있는 키워드만 추출 (불용어 제거)
            import re
            message_lower = message.lower()
            stopwords = ['보여줘', '알려줘', '있나요', '나와', '등장', '장면', '나오는', '하는', '이', '가', '을', '를', '에', '의', '찾아줘', '찾아', '프레임은', '프레임']
            
            # 한국어 단어 추출
            korean_words = re.findall(r'[가-힣]+', message)
            keywords = []
            for word in korean_words:
                # 조사 제거
                cleaned = re.sub(r'[이가을를에의]$', '', word)
                if cleaned and cleaned not in stopwords and len(cleaned) > 1:
                    keywords.append(cleaned)
            
            # 영어 단어 추출
            english_words = re.findall(r'[a-zA-Z]+', message_lower)
            for word in english_words:
                if word not in stopwords and len(word) > 1:
                    keywords.append(word)
            
            # 한국어 -> 영어 객체명 매핑
            korean_to_english_objects = {
                # 사람/동물
                '사람': ['person', 'people', 'human'],
                '어린이': ['child', 'children', 'kid', 'kids'],
                '아이': ['child', 'children', 'kid', 'kids'],
                '아동': ['child', 'children', 'kid', 'kids'],
                '노인': ['elderly', 'old person', 'senior'],
                '강아지': ['dog', 'puppy'],
                '개': ['dog'],
                '고양이': ['cat', 'kitten'],
                '소': ['cow', 'cattle'],
                '동물': ['animal', 'dog', 'cat', 'cow', 'bird'],
                
                # 차량
                '자동차': ['car', 'vehicle', 'automobile'],
                '차': ['car', 'vehicle'],
                '차량': ['vehicle', 'car', 'bus'],
                '트럭': ['truck', 'lorry'],
                '버스': ['bus'],
                '오토바이': ['motorcycle', 'motorbike', 'bike'],
                '자전거': ['bicycle', 'bike'],
                
                # 가방/소지품
                '가방': ['bag', 'backpack', 'handbag', 'purse'],
                '백팩': ['backpack', 'rucksack'],
                '핸드백': ['handbag', 'purse'],
                '서류가방': ['briefcase'],
                '지갑': ['wallet', 'purse'],
                '우산': ['umbrella'],
                '양산': ['umbrella', 'parasol'],
                '수하물': ['suitcase', 'luggage', 'baggage'],
                '여행가방': ['suitcase', 'luggage'],
                
                # 가구
                '의자': ['chair', 'seat'],
                '벤치': ['bench', 'seat'],
                '테이블': ['table', 'desk'],
                '식탁': ['dining table', 'table'],
                '침대': ['bed'],
                '소파': ['sofa', 'couch'],
                
                # 전자제품
                '텔레비전': ['tv', 'television'],
                '티비': ['tv', 'television'],
                'TV': ['tv', 'television'],
                '노트북': ['laptop', 'notebook'],
                '컴퓨터': ['computer', 'laptop', 'pc'],
                '스마트폰': ['cell phone', 'mobile phone', 'phone'],
                '핸드폰': ['cell phone', 'mobile phone', 'phone'],
                '전화기': ['phone', 'telephone'],
                
                # 음식/식기
                '병': ['bottle'],
                '컵': ['cup', 'mug'],
                '잔': ['cup', 'glass'],
                '접시': ['plate', 'dish'],
                '포크': ['fork'],
                '나이프': ['knife'],
                '숟가락': ['spoon'],
                
                # 기타
                '마스코트': ['mascot', 'character', 'costume'],
                '캐릭터': ['character', 'mascot', 'costume'],
                '인형': ['teddy bear', 'doll', 'toy'],
                '곰인형': ['teddy bear', 'bear'],
                '신호등': ['traffic light', 'traffic signal'],
                '표지판': ['sign', 'signboard'],
                '넥타이': ['tie', 'neckite', 'neck tie'],
                '서핑보드': ['surfboard'],
                '보드': ['surfboard', 'skateboard'],
                '사자': ['lion'],
                '경찰': ['police', 'officer'],
            }
            
            for korean, english_list in korean_to_english_objects.items():
                if korean in message:
                    keywords.extend(english_list)
                    logger.info(f"  ✅ 한국어 '{korean}' -> 영어 키워드 추가: {english_list}")
            
            # 특수 패턴 매칭
            if '모자' in message:
                keywords.extend(['hat', 'cap', 'beanie'])
            if '기타' in message:
                keywords.extend(['guitar'])
            if '커피' in message:
                keywords.extend(['coffee', 'cup'])
            if '어린이' in message or '아이' in message or '아동' in message:
                keywords.extend(['child', 'children', 'kid', 'kids'])
            
            if keywords:
                context_frames = self.search_frames_by_keywords(keywords[:5])  # 최대 5개 키워드
                
                if context_frames:
                    result['frames'] = context_frames[:10]
                    result['frame_images'] = [
                        frame.get('frame_image_path') or f"images/video{self.video_id}_frame{frame.get('image_id')}.jpg"
                        for frame in context_frames[:10]
                    ]
                
                # 답변 생성 (다중 AI)
                ai_result = self.generate_answer_with_multi_ai(message, context_frames if context_frames else None)
                if isinstance(ai_result, dict):
                    result['answer'] = ai_result.get('integrated', '')
                    result['individual_responses'] = ai_result.get('individual', {})
                else:
                    result['answer'] = ai_result
            else:
                # 전체 영상 요약 질문
                ai_result = self.generate_answer_with_multi_ai(message, None)
                if isinstance(ai_result, dict):
                    result['answer'] = ai_result.get('integrated', '')
                    result['individual_responses'] = ai_result.get('individual', {})
                else:
                    result['answer'] = ai_result
        
        return result


def get_video_chat_handler(video_id, video):
    """영상 채팅 핸들러 팩토리 함수"""
    return EnhancedVideoChatHandler(video_id, video)