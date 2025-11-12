"""
개선된 영상 채팅 핸들러
- Ollama 캡션 기반 답변
- 다중 AI 모델 (GPT, Claude, Mixtral) 통합
- 색상 2중 검증 (캡션 + 추출된 색상)
- 영상/일반 질문 자동 구분
"""

import os
import json
import logging
import ollama
from django.conf import settings

logger = logging.getLogger(__name__)


def get_chatbots():
    """chatbots 전역 변수를 가져오는 헬퍼 함수 (lazy import)"""
    try:
        from ..utils.chatbot import chatbots
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
            video_name = self.video.original_name or self.video.filename
            meta_db_path = os.path.join(settings.MEDIA_ROOT, f"{video_name}-meta_db.json")
            
            if os.path.exists(meta_db_path):
                with open(meta_db_path, 'r', encoding='utf-8') as f:
                    self.meta_db = json.load(f)
                self.frames = self.meta_db.get('frame', [])
                logger.info(f"✅ Meta DB 로드 성공: {len(self.frames)}개 프레임")
            else:
                logger.warning(f"❌ Meta DB 파일 없음: {meta_db_path}")
        
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
        """키워드로 프레임 검색 (캡션 기반)"""
        found_frames = []
        
        for frame in self.frames:
            caption = frame.get('caption', '').lower()
            
            # 키워드 중 하나라도 캡션에 있으면 매칭 (점수 기반)
            match_score = 0
            for keyword in keywords:
                if keyword.lower() in caption:
                    match_score += 1
            
            # 적어도 하나 이상의 키워드가 매칭되면 추가
            if match_score > 0:
                frame_with_score = frame.copy()
                frame_with_score['match_score'] = match_score
                found_frames.append(frame_with_score)
        
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
            
            # 1. 캡션에서 색상 검색 (우선 순위 높음)
            if any(word in caption for word in synonyms):
                match_score += caption_weight
            
            # 2. 추출된 색상 정보 확인 (보조)
            objects = frame.get('objects', [])
            for obj in objects:
                if obj.get('class') == 'person':
                    clothing_colors = obj.get('clothing_colors', {})
                    upper_color = (clothing_colors.get('upper') or '').lower()
                    lower_color = (clothing_colors.get('lower') or '').lower()
                    if any(word in upper_color for word in synonyms) or any(word in lower_color for word in synonyms):
                        match_score += color_weight
                        break
            
            if match_score > 0:
                frame_with_score = frame.copy()
                frame_with_score['match_score'] = match_score
                found_frames.append(frame_with_score)
        
        # 캡션 매칭 우선, 이후 점수 순 정렬
        found_frames.sort(key=lambda x: (x.get('match_score', 0), x.get('timestamp', 0)), reverse=True)
        
        # 중복 타임스탬프 제거 후 상위 5개만 반환
        unique_frames = []
        seen_timestamps = set()
        for frame in found_frames:
            ts_key = round(frame.get('timestamp', 2))
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
    
    def generate_answer_with_multi_ai(self, message, context_frames=None, include_video_context=True):
        """다중 AI 모델로 답변 생성 및 통합"""
        try:
            # 컨텍스트 구성
            if include_video_context:
                context = f"영상 정보:\n"
                context += f"- 총 프레임 수: {len(self.frames)}개\n"
                context += f"- 영상 길이: {self.video.duration}초\n\n"
            else:
                context = ""
            
            if context_frames:
                context += f"관련 프레임 ({len(context_frames)}개):\n"
                for i, frame in enumerate(context_frames[:5], 1):  # 최대 5개만
                    timestamp = frame.get('timestamp', 0)
                    caption = frame.get('caption', '')
                    context += f"{i}. [{timestamp:.1f}s] {caption[:200]}\n"
            else:
                # 전체 요약
                context += "영상 주요 내용:\n"
                for i, frame in enumerate(self.frames[::max(1, len(self.frames)//5)], 1):  # 샘플 5개
                    timestamp = frame.get('timestamp', 0)
                    caption = frame.get('caption', '')
                    context += f"- [{timestamp:.1f}s] {caption[:150]}\n"
            
            # AI 질문 구성
            if include_video_context:
                ai_prompt = f"""다음 영상 정보를 바탕으로 사용자의 질문에 한국어로 간결하게 답변해주세요.

{context}

사용자 질문: {message}

답변 요구사항:
1. 핵심만 간결하게 답변 (최대 3-4문장)
2. 질문에 직접적으로 답변
3. 불필요한 설명 생략
4. 한국어로 작성"""
            else:
                ai_prompt = f"""사용자의 질문에 한국어로 간결하고 친근하게 답변해주세요.

사용자 질문: {message}

답변 요구사항:
1. 핵심만 간결하게 답변 (최대 2-3문장)
2. 친근한 톤 유지
3. 불필요한 설명 생략
4. 한국어로 작성"""
            
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
                for model_key in priority_model_keys:
                    if model_key in chatbots:
                        try:
                            bot = chatbots[model_key]
                            response = bot.chat(ai_prompt)
                            ai_responses[model_key] = response
                            logger.info(f"✅ {model_key} 답변 생성 완료")
                        except Exception as e:
                            logger.warning(f"⚠️ {model_key} 답변 생성 실패: {e}")
                    else:
                        logger.warning(f"⚠️ {model_key} 모델을 chatbots에서 찾을 수 없음")
            
            # Ollama를 백업으로 추가 (무료)
            try:
                response = ollama.chat(
                    model='llama3.2:latest',
                    messages=[{
                        'role': 'user',
                        'content': ai_prompt
                    }],
                    options={
                        'temperature': 0.7,
                        'num_predict': 500
                    }
                )
                # Ollama는 항상 포함 (무료이므로)
                # ai_responses['ollama'] = response['message']['content'].strip()
                # logger.info(f"✅ Ollama 답변 생성 완료")
            except Exception as e:
                logger.warning(f"⚠️ Ollama 답변 생성 실패: {e}")
            
            # 응답이 없으면 Ollama만 사용
            if not ai_responses:
                logger.warning("⚠️ 모든 AI 모델 실패, Ollama로 재시도")
                response = ollama.chat(
                    model='llama3.2:latest',
                    messages=[{'role': 'user', 'content': ai_prompt}],
                    options={'temperature': 0.7, 'num_predict': 500}
                )
                ollama_answer = response['message']['content'].strip()
                return {
                    'integrated': ollama_answer,
                    'individual': {'ollama': ollama_answer}
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
            return "죄송합니다. 답변 생성 중 오류가 발생했습니다."
    
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
            
            integration_prompt = f"""다음은 여러 AI 모델이 동일한 질문에 대해 답변한 내용입니다.
핵심만 간결하게 통합하여 답변해주세요.

질문: {original_question}

{responses_text}

통합 답변 요구사항:
1. 핵심 내용만 간결하게 통합 (최대 3-4문장)
2. 질문에 직접적으로 답변
3. 불필요한 설명 생략
4. 한국어로 작성

통합 답변:"""
            
            # HCX-DASH-001 사용
            if hcx_bot:
                try:
                    integrated = hcx_bot.chat(integration_prompt)
                    logger.info(f"✅ HCX-DASH-001 통합 답변 생성 완료")
                except Exception as e:
                    logger.warning(f"⚠️ HCX-DASH-001 실패, Ollama로 대체: {e}")
                    response = ollama.chat(
                        model='llama3.2:latest',
                        messages=[{'role': 'user', 'content': integration_prompt}],
                        options={'temperature': 0.5, 'num_predict': 800}
                    )
                    integrated = response['message']['content'].strip()
            else:
                # HCX-DASH-001이 없으면 Ollama 사용
                logger.warning("⚠️ HCX-DASH-001 없음, Ollama 사용")
                response = ollama.chat(
                    model='llama3.2:latest',
                    messages=[{'role': 'user', 'content': integration_prompt}],
                    options={'temperature': 0.5, 'num_predict': 800}
                )
                integrated = response['message']['content'].strip()
            
            # 각 AI 분석 추가
            integrated += "\n\n---\n**각 AI 분석:**\n"
            for model_name in ai_responses.keys():
                integrated += f"- {model_name.upper()}\n"
            
            return integrated
            
        except Exception as e:
            logger.error(f"❌ 통합 답변 생성 실패: {e}")
            # 실패 시 첫 번째 응답 반환
            return list(ai_responses.values())[0]
    
    def handle_general_question(self, message):
        """일반 질문 처리 (영상 무관)"""
        try:
            response = ollama.chat(
                model='llama3.2:latest',
                messages=[{
                    'role': 'user',
                    'content': message
                }],
                options={
                    'temperature': 0.7,
                    'num_predict': 500
                }
            )
            
            return response['message']['content'].strip()
            
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
            stopwords = ['보여줘', '알려줘', '있나요', '나와', '등장', '장면', '나오는', '하는', '이', '가', '을', '를', '에', '의']
            keywords = [word for word in message.split() if len(word) > 1 and word not in stopwords]
            
            # 특수 패턴 매칭 (더 정확한 검색)
            import re
            # "모자쓴 사람" -> "hat", "cap", "모자"
            if '모자' in message:
                keywords.extend(['hat', 'cap', 'beanie'])
            # "기타 치는" -> "guitar"
            if '기타' in message:
                keywords.extend(['guitar'])
            # "커피" -> "coffee", "cup"
            if '커피' in message:
                keywords.extend(['coffee', 'cup'])
            
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

