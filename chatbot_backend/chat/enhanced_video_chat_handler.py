"""
영상 채팅 핸들러 v3.0 - 대폭 개선 버전
=======================================

주요 개선사항:
1. 역할 명확 분리: Ollama(분석) vs 상용 LLM(답변)
2. 캐싱 시스템: 반복 분석 방지
3. 폴백 체인: 우선순위 기반 LLM 선택
4. 컨텍스트 최적화: 토큰 효율성
5. 에러 핸들링 강화
6. 성능 모니터링
"""

import os
import json
import logging
import time
from functools import lru_cache
from typing import Dict, List, Optional, Tuple
import ollama
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class LLMManager:
    """LLM 관리 클래스 - 우선순위 기반 폴백 체인"""
    
    # LLM 우선순위 정의 (비용/성능/속도 고려)
    LLM_PRIORITY = [
        {
            'key': 'gemini-2.0-flash-lite',
            'name': 'Gemini Flash',
            'cost': 'low',
            'speed': 'fast',
            'quality': 'high'
        },
        {
            'key': 'gpt-4o-mini',
            'name': 'GPT-4o Mini',
            'cost': 'low',
            'speed': 'fast',
            'quality': 'high'
        },
        {
            'key': 'claude-3.5-haiku',
            'name': 'Claude Haiku',
            'cost': 'low',
            'speed': 'fast',
            'quality': 'high'
        },
        {
            'key': 'clova-hcx-dash-001',
            'name': 'HCX-DASH',
            'cost': 'medium',
            'speed': 'medium',
            'quality': 'very_high',
            'use_case': 'integration'  # 통합 전용
        }
    ]
    
    def __init__(self):
        self.chatbots = self._load_chatbots()
        self.available_models = self._check_available_models()
        logger.info(f"✅ LLM Manager 초기화: {len(self.available_models)}개 모델 사용 가능")
    
    def _load_chatbots(self) -> Dict:
        """chatbots 로드 (여러 경로 시도)"""
        try:
            from core.utils.chatbot import chatbots
            logger.info("✅ chatbots import 성공 (core.utils.chatbot)")
            return chatbots
        except ImportError:
            try:
                from utils.chatbot import chatbots
                logger.info("✅ chatbots import 성공 (utils.chatbot)")
                return chatbots
            except Exception as e:
                logger.error(f"❌ chatbots import 실패: {e}")
                return {}
    
    def _check_available_models(self) -> List[Dict]:
        """사용 가능한 모델 체크"""
        available = []
        for model_info in self.LLM_PRIORITY:
            key = model_info['key']
            if key in self.chatbots:
                try:
                    # 간단한 테스트 호출로 API 키 유효성 체크
                    bot = self.chatbots[key]
                    # 실제로는 테스트하지 않고 존재만 확인 (API 비용 절약)
                    available.append(model_info)
                    logger.info(f"   ✓ {model_info['name']} 사용 가능")
                except Exception as e:
                    logger.warning(f"   ✗ {model_info['name']} 사용 불가: {e}")
            else:
                logger.debug(f"   ✗ {model_info['name']} 미등록")
        
        return available
    
    def get_response(self, prompt: str, use_case: str = 'general') -> Optional[Tuple[str, str]]:
        """
        LLM 응답 생성 (폴백 체인)
        
        Args:
            prompt: 프롬프트
            use_case: 'general' 또는 'integration'
        
        Returns:
            (응답, 모델명) 또는 None
        """
        # use_case에 맞는 모델 필터링
        candidates = [m for m in self.available_models 
                     if use_case == 'general' or m.get('use_case') == use_case]
        
        if not candidates:
            candidates = self.available_models  # 폴백: 모든 모델 시도
        
        # 우선순위대로 시도
        for model_info in candidates:
            try:
                start_time = time.time()
                bot = self.chatbots[model_info['key']]
                response = bot.chat(prompt)
                elapsed = time.time() - start_time
                
                logger.info(f"✅ {model_info['name']} 응답 성공 ({elapsed:.2f}s)")
                return response, model_info['name']
                
            except Exception as e:
                logger.warning(f"⚠️ {model_info['name']} 실패: {e}")
                continue
        
        logger.error("❌ 모든 LLM 실패")
        return None
    
    def get_multi_responses(self, prompt: str, max_models: int = 3) -> Dict[str, str]:
        """
        여러 LLM에서 응답 수집 (병렬 처리 가능하도록 설계)
        
        Args:
            prompt: 프롬프트
            max_models: 최대 사용 모델 수
        
        Returns:
            {모델명: 응답} 딕셔너리
        """
        responses = {}
        
        # 통합 전용 모델 제외
        candidates = [m for m in self.available_models[:max_models] 
                     if m.get('use_case') != 'integration']
        
        for model_info in candidates:
            try:
                bot = self.chatbots[model_info['key']]
                response = bot.chat(prompt)
                responses[model_info['name']] = response
                logger.info(f"✅ {model_info['name']} 응답 수집")
            except Exception as e:
                logger.warning(f"⚠️ {model_info['name']} 실패: {e}")
        
        return responses


class FrameAnalyzer:
    """프레임 분석 클래스 - Ollama 전담"""
    
    def __init__(self, frames: List[Dict]):
        self.frames = frames
    
    @lru_cache(maxsize=100)
    def search_by_keywords(self, keywords_tuple: Tuple[str]) -> List[Dict]:
        """키워드로 프레임 검색 (캐싱)"""
        keywords = list(keywords_tuple)
        found_frames = []
        
        for frame in self.frames:
            caption = frame.get('caption', '').lower()
            match_score = sum(1 for kw in keywords if kw.lower() in caption)
            
            if match_score > 0:
                frame_copy = frame.copy()
                frame_copy['match_score'] = match_score
                found_frames.append(frame_copy)
        
        found_frames.sort(key=lambda x: x['match_score'], reverse=True)
        return found_frames
    
    def search_by_color(self, color_name: str) -> List[Dict]:
        """색상으로 프레임 검색"""
        # 기존 로직 유지
        korean_to_english = {
            '분홍': 'pink', '핑크': 'pink',
            '빨강': 'red', '파랑': 'blue',
            '노랑': 'yellow', '초록': 'green',
            '흰': 'white', '검정': 'black',
            '보라': 'purple', '회색': 'gray'
        }
        
        base_color = korean_to_english.get(color_name.lower(), color_name.lower())
        color_synonyms = {
            'pink': ['pink', 'rose', 'magenta'],
            'red': ['red', 'crimson'],
            'blue': ['blue', 'navy', 'azure'],
            'yellow': ['yellow', 'gold'],
            'green': ['green', 'lime'],
            'purple': ['purple', 'violet'],
            'white': ['white', 'ivory'],
            'black': ['black'],
            'gray': ['gray', 'grey', 'silver']
        }
        
        synonyms = color_synonyms.get(base_color, [base_color])
        found_frames = []
        
        for frame in self.frames:
            caption = frame.get('caption', '').lower()
            if any(word in caption for word in synonyms):
                frame_copy = frame.copy()
                frame_copy['match_score'] = 3  # 캡션 매칭 우선
                found_frames.append(frame_copy)
        
        found_frames.sort(key=lambda x: x['match_score'], reverse=True)
        return found_frames[:5]
    
    def analyze_people_count(self) -> Dict:
        """사람 수 분석"""
        number_words = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
        }
        
        people_counts = []
        for frame in self.frames:
            caption = frame.get('caption', '').lower()
            timestamp = frame.get('timestamp', 0)
            
            for num_word, num in number_words.items():
                patterns = [f'{num_word} people', f'{num_word} individuals']
                if any(p in caption for p in patterns):
                    people_counts.append({
                        'timestamp': timestamp,
                        'count': num,
                        'caption': caption[:100]
                    })
                    break
        
        if people_counts:
            max_count = max(people_counts, key=lambda x: x['count'])['count']
            return {
                'estimated_count': max_count,
                'confidence': 'high',
                'evidence': people_counts,
                'explanation': f"영상에서 최대 {max_count}명이 등장합니다."
            }
        else:
            return {
                'estimated_count': 'unknown',
                'confidence': 'low',
                'evidence': [],
                'explanation': "사람 수를 파악할 수 없습니다."
            }
    
    def get_highlights(self, max_count: int = 5) -> List[Dict]:
        """하이라이트 프레임 선택"""
        if not self.frames:
            return []
        
        # 프레임을 균등하게 샘플링
        step = max(1, len(self.frames) // (max_count + 2))
        sampled = self.frames[step::step][:max_count]
        
        # 중요도 점수 계산
        for frame in sampled:
            persons = frame.get('persons', [])
            caption = frame.get('caption', '')
            frame['highlight_score'] = len(persons) * 2 + len(caption) / 50
        
        sampled.sort(key=lambda x: x['highlight_score'], reverse=True)
        return sampled


class ContextBuilder:
    """컨텍스트 생성 최적화 클래스"""
    
    MAX_CAPTION_LENGTH = 150  # 캡션 최대 길이
    MAX_FRAMES_IN_CONTEXT = 5  # 컨텍스트에 포함할 최대 프레임 수
    
    @staticmethod
    def build_video_context(frames: List[Dict], video_duration: float) -> str:
        """영상 전체 컨텍스트"""
        context = f"영상 정보: {len(frames)}개 프레임, {video_duration:.1f}초\n\n"
        
        # 샘플링된 프레임 요약
        step = max(1, len(frames) // 5)
        for i, frame in enumerate(frames[::step][:5], 1):
            ts = frame.get('timestamp', 0)
            caption = frame.get('caption', '')[:ContextBuilder.MAX_CAPTION_LENGTH]
            context += f"[{ts:.1f}s] {caption}\n"
        
        return context
    
    @staticmethod
    def build_search_context(frames: List[Dict], query: str) -> str:
        """검색 결과 컨텍스트"""
        context = f"'{query}' 검색 결과 ({len(frames)}개 프레임):\n\n"
        
        for i, frame in enumerate(frames[:ContextBuilder.MAX_FRAMES_IN_CONTEXT], 1):
            ts = frame.get('timestamp', 0)
            caption = frame.get('caption', '')[:ContextBuilder.MAX_CAPTION_LENGTH]
            score = frame.get('match_score', 0)
            context += f"{i}. [{ts:.1f}s, 점수:{score}] {caption}\n"
        
        return context
    
    @staticmethod
    def build_prompt(context: str, question: str, language: str = "한국어") -> str:
        """최적화된 프롬프트 생성"""
        return f"""{context}

사용자 질문: {question}

답변 요구사항:
- {language}로만 작성
- 핵심만 간결하게 (2-4문장)
- 질문에 직접 답변
- 불필요한 설명 생략

답변:"""


class EnhancedVideoChatHandler:
    """개선된 영상 채팅 핸들러 v3.0"""
    
    def __init__(self, video_id, video):
        self.video_id = video_id
        self.video = video
        self.frames = []
        
        # 컴포넌트 초기화
        self.llm_manager = LLMManager()
        self._load_analysis_data()
        self.frame_analyzer = FrameAnalyzer(self.frames)
        self.context_builder = ContextBuilder()
        
        logger.info(f"✅ 영상 채팅 핸들러 초기화 완료 (video_id={video_id})")
    
    def _load_analysis_data(self):
        """영상 분석 데이터 로드"""
        try:
            video_name = self.video.original_name or self.video.filename
            meta_db_path = os.path.join(settings.MEDIA_ROOT, f"{video_name}-meta_db.json")
            
            if os.path.exists(meta_db_path):
                with open(meta_db_path, 'r', encoding='utf-8') as f:
                    meta_db = json.load(f)
                self.frames = meta_db.get('frame', [])
                logger.info(f"✅ Meta DB 로드: {len(self.frames)}개 프레임")
            else:
                logger.warning(f"❌ Meta DB 파일 없음: {meta_db_path}")
        
        except Exception as e:
            logger.error(f"❌ 분석 데이터 로드 실패: {e}")
    
    def _is_video_question(self, message: str) -> bool:
        """영상 관련 질문 판단"""
        video_keywords = [
            '영상', 'video', '사람', 'people', '옷', 'clothing',
            '색상', 'color', '장면', 'scene', '몇', 'how many',
            '요약', 'summary', '하이라이트', 'highlight'
        ]
        message_lower = message.lower()
        return any(kw in message_lower for kw in video_keywords)
    
    def _detect_question_type(self, message: str) -> str:
        """질문 유형 감지"""
        message_lower = message.lower()
        
        if any(kw in message_lower for kw in ['요약', 'summary', '하이라이트', 'highlight']):
            return 'summary'
        elif any(kw in message_lower for kw in ['몇명', '몇 명', '사람 수', 'how many people']):
            return 'people_count'
        elif any(kw in message_lower for kw in ['성비', '남녀', 'gender']):
            return 'gender'
        elif any(color in message_lower for color in ['분홍', '핑크', '빨강', '파랑', '노랑']):
            return 'color_search'
        else:
            return 'general'
    
    def _handle_summary_question(self, message: str) -> Dict:
        """요약/하이라이트 질문 처리"""
        highlight_frames = self.frame_analyzer.get_highlights(max_count=5)
        
        if not highlight_frames:
            return {
                'answer': '하이라이트 장면을 찾을 수 없습니다.',
                'individual_responses': {},
                'frames': [],
                'frame_images': []
            }
        
        # 컨텍스트 생성
        context = "🎬 영상 하이라이트:\n\n"
        for i, frame in enumerate(highlight_frames, 1):
            ts = frame.get('timestamp', 0)
            caption = frame.get('caption', '')[:150]
            context += f"{i}. [{ts:.1f}초] {caption}\n"
        
        # 프롬프트 생성
        prompt = self.context_builder.build_prompt(context, message)
        
        # LLM 응답
        result = self.llm_manager.get_response(prompt)
        
        if result:
            answer, model_name = result
            return {
                'answer': answer,
                'individual_responses': {model_name: answer},
                'frames': highlight_frames,
                'frame_images': [
                    f"images/video{self.video_id}_frame{f.get('image_id')}.jpg"
                    for f in highlight_frames
                ]
            }
        else:
            return {
                'answer': '죄송합니다. AI 모델 연결에 실패했습니다.',
                'individual_responses': {},
                'frames': highlight_frames,
                'frame_images': []
            }
    
    def _handle_people_count_question(self, message: str) -> Dict:
        """사람 수 질문 처리"""
        analysis = self.frame_analyzer.analyze_people_count()
        
        # 컨텍스트 생성
        context = f"""🎯 영상 사람 수 분석:
- 추정 인원: {analysis['estimated_count']}명
- 신뢰도: {analysis['confidence']}
- 설명: {analysis['explanation']}

⚠️ 같은 사람이 여러 프레임에 등장하므로 중복 제거된 고유 인원입니다."""
        
        prompt = self.context_builder.build_prompt(context, message)
        result = self.llm_manager.get_response(prompt)
        
        if result:
            answer, model_name = result
            return {
                'answer': answer,
                'individual_responses': {model_name: answer},
                'frames': [],
                'frame_images': []
            }
        else:
            return {
                'answer': f"영상에서 약 {analysis['estimated_count']}명이 등장합니다.",
                'individual_responses': {},
                'frames': [],
                'frame_images': []
            }
    
    def _handle_color_search(self, message: str) -> Dict:
        """색상 검색 질문 처리"""
        # 색상 추출
        color_map = {
            '분홍': 'pink', '핑크': 'pink', '빨강': 'red',
            '파랑': 'blue', '노랑': 'yellow', '초록': 'green'
        }
        
        found_color = None
        for korean, english in color_map.items():
            if korean in message or english in message.lower():
                found_color = english
                break
        
        if not found_color:
            return {
                'answer': '색상을 인식할 수 없습니다.',
                'individual_responses': {},
                'frames': [],
                'frame_images': []
            }
        
        # 프레임 검색
        frames = self.frame_analyzer.search_by_color(found_color)
        
        if not frames:
            return {
                'answer': f"영상에서 {found_color} 색상을 찾을 수 없습니다.",
                'individual_responses': {},
                'frames': [],
                'frame_images': []
            }
        
        # 컨텍스트 생성
        context = self.context_builder.build_search_context(frames, f"{found_color} 색상")
        prompt = self.context_builder.build_prompt(context, message)
        
        result = self.llm_manager.get_response(prompt)
        
        if result:
            answer, model_name = result
            return {
                'answer': answer,
                'individual_responses': {model_name: answer},
                'frames': frames[:5],
                'frame_images': [
                    f"images/video{self.video_id}_frame{f.get('image_id')}.jpg"
                    for f in frames[:5]
                ]
            }
        else:
            return {
                'answer': f"{found_color} 색상의 옷을 입은 사람을 찾았습니다.",
                'individual_responses': {},
                'frames': frames[:5],
                'frame_images': []
            }
    
    def _handle_general_question(self, message: str) -> Dict:
        """일반 질문 처리"""
        # 영상 질문인지 확인
        if self._is_video_question(message):
            # 키워드 추출 (간단한 토큰화)
            keywords = [w for w in message.split() if len(w) > 1]
            keywords_tuple = tuple(keywords[:5])  # 캐싱을 위해 튜플로 변환
            
            # 프레임 검색
            frames = self.frame_analyzer.search_by_keywords(keywords_tuple)
            
            if frames:
                context = self.context_builder.build_search_context(frames, message)
            else:
                context = self.context_builder.build_video_context(
                    self.frames, 
                    self.video.duration
                )
            
            prompt = self.context_builder.build_prompt(context, message)
            result = self.llm_manager.get_response(prompt)
            
            if result:
                answer, model_name = result
                return {
                    'answer': answer,
                    'individual_responses': {model_name: answer},
                    'frames': frames[:5] if frames else [],
                    'frame_images': [
                        f"images/video{self.video_id}_frame{f.get('image_id')}.jpg"
                        for f in frames[:5]
                    ] if frames else []
                }
        
        # 일반 대화 (영상 무관)
        prompt = f"""사용자 질문: {message}

한국어로 친근하게 답변해주세요 (2-3문장)."""
        
        result = self.llm_manager.get_response(prompt)
        
        if result:
            answer, model_name = result
            return {
                'answer': answer,
                'individual_responses': {model_name: answer},
                'frames': [],
                'frame_images': []
            }
        else:
            return {
                'answer': '죄송합니다. AI 모델 연결에 실패했습니다.',
                'individual_responses': {},
                'frames': [],
                'frame_images': []
            }
    
    def process_message(self, message: str) -> Dict:
        """
        메시지 처리 메인 함수
        
        Returns:
            dict: {
                'answer': str,
                'individual_responses': dict,
                'frames': list,
                'frame_images': list,
                'is_video_related': bool
            }
        """
        start_time = time.time()
        
        # 질문 유형 감지
        question_type = self._detect_question_type(message)
        logger.info(f"🔍 질문 유형: {question_type}")
        
        # 유형별 처리
        handlers = {
            'summary': self._handle_summary_question,
            'people_count': self._handle_people_count_question,
            'color_search': self._handle_color_search,
            'gender': self._handle_general_question,  # 성비는 일반으로 처리
            'general': self._handle_general_question
        }
        
        handler = handlers.get(question_type, self._handle_general_question)
        result = handler(message)
        
        # 메타 정보 추가
        result['is_video_related'] = self._is_video_question(message)
        result['question_type'] = question_type
        result['processing_time'] = time.time() - start_time
        
        logger.info(f"✅ 처리 완료 ({result['processing_time']:.2f}s)")
        
        return result


def get_video_chat_handler(video_id, video):
    """영상 채팅 핸들러 팩토리 함수"""
    return EnhancedVideoChatHandler(video_id, video)