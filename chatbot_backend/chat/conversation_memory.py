"""
대화 맥락 유지 시스템
사용자와의 대화 기록을 저장하고 맥락을 유지하여 더 자연스러운 대화 지원
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

class ConversationMemory:
    """대화 맥락을 유지하는 메모리 클래스"""
    
    def __init__(self, max_context_length: int = 10, cache_timeout: int = 3600):
        self.max_context_length = max_context_length
        self.cache_timeout = cache_timeout
    
    def add_context(self, session_id: str, user_message: str, ai_responses: Dict[str, str], 
                   video_context: Dict[str, Any] = None) -> None:
        """대화 맥락 추가"""
        try:
            # 기존 맥락 가져오기
            context = self.get_context(session_id)
            
            # 새로운 대화 추가
            conversation_entry = {
                'timestamp': datetime.now().isoformat(),
                'user_message': user_message,
                'ai_responses': ai_responses,
                'video_context': video_context or {},
                'intent': self._extract_intent(user_message),
                'entities': self._extract_entities(user_message)
            }
            
            context['conversations'].append(conversation_entry)
            
            # 최대 길이 제한
            if len(context['conversations']) > self.max_context_length:
                context['conversations'] = context['conversations'][-self.max_context_length:]
            
            # 캐시에 저장
            cache.set(f"conversation_context_{session_id}", context, self.cache_timeout)
            
            logger.info(f"✅ 대화 맥락 추가: {session_id}, 총 {len(context['conversations'])}개 대화")
            
        except Exception as e:
            logger.error(f"❌ 대화 맥락 추가 실패: {e}")
    
    def get_context(self, session_id: str) -> Dict[str, Any]:
        """대화 맥락 가져오기"""
        try:
            context = cache.get(f"conversation_context_{session_id}")
            
            if not context:
                context = {
                    'session_id': session_id,
                    'created_at': datetime.now().isoformat(),
                    'conversations': [],
                    'user_preferences': {},
                    'video_history': [],
                    'search_history': []
                }
            
            return context
            
        except Exception as e:
            logger.error(f"❌ 대화 맥락 가져오기 실패: {e}")
            return {
                'session_id': session_id,
                'created_at': datetime.now().isoformat(),
                'conversations': [],
                'user_preferences': {},
                'video_history': [],
                'search_history': []
            }
    
    def get_relevant_context(self, session_id: str, current_message: str, 
                           context_type: str = 'all') -> Dict[str, Any]:
        """현재 메시지와 관련된 맥락 가져오기"""
        try:
            context = self.get_context(session_id)
            current_intent = self._extract_intent(current_message)
            current_entities = self._extract_entities(current_message)
            
            relevant_context = {
                'recent_conversations': [],
                'related_videos': [],
                'user_preferences': context.get('user_preferences', {}),
                'search_patterns': []
            }
            
            # 최근 대화 중 관련성 높은 것들 선택
            for conv in context.get('conversations', [])[-5:]:  # 최근 5개 대화만
                relevance_score = self._calculate_relevance(
                    conv, current_intent, current_entities
                )
                
                if relevance_score > 0.3:  # 임계값 이상
                    relevant_context['recent_conversations'].append({
                        'conversation': conv,
                        'relevance_score': relevance_score
                    })
            
            # 관련성 순으로 정렬
            relevant_context['recent_conversations'].sort(
                key=lambda x: x['relevance_score'], reverse=True
            )
            
            # 비디오 히스토리
            relevant_context['related_videos'] = context.get('video_history', [])[-3:]
            
            # 검색 패턴
            relevant_context['search_patterns'] = context.get('search_history', [])[-3:]
            
            logger.info(f"✅ 관련 맥락 추출: {len(relevant_context['recent_conversations'])}개 대화")
            return relevant_context
            
        except Exception as e:
            logger.error(f"❌ 관련 맥락 가져오기 실패: {e}")
            return {}
    
    def update_user_preferences(self, session_id: str, preferences: Dict[str, Any]) -> None:
        """사용자 선호도 업데이트"""
        try:
            context = self.get_context(session_id)
            context['user_preferences'].update(preferences)
            
            cache.set(f"conversation_context_{session_id}", context, self.cache_timeout)
            
            logger.info(f"✅ 사용자 선호도 업데이트: {preferences}")
            
        except Exception as e:
            logger.error(f"❌ 사용자 선호도 업데이트 실패: {e}")
    
    def add_video_history(self, session_id: str, video_info: Dict[str, Any]) -> None:
        """비디오 히스토리 추가"""
        try:
            context = self.get_context(session_id)
            
            video_entry = {
                'video_id': video_info.get('video_id'),
                'video_name': video_info.get('video_name'),
                'timestamp': datetime.now().isoformat(),
                'actions': video_info.get('actions', [])
            }
            
            context['video_history'].append(video_entry)
            
            # 최대 10개 비디오 히스토리 유지
            if len(context['video_history']) > 10:
                context['video_history'] = context['video_history'][-10:]
            
            cache.set(f"conversation_context_{session_id}", context, self.cache_timeout)
            
            logger.info(f"✅ 비디오 히스토리 추가: {video_info.get('video_name')}")
            
        except Exception as e:
            logger.error(f"❌ 비디오 히스토리 추가 실패: {e}")
    
    def add_search_history(self, session_id: str, search_query: str, search_results: Dict[str, Any]) -> None:
        """검색 히스토리 추가"""
        try:
            context = self.get_context(session_id)
            
            search_entry = {
                'query': search_query,
                'timestamp': datetime.now().isoformat(),
                'results_count': len(search_results.get('results', [])),
                'search_type': search_results.get('search_type', 'general')
            }
            
            context['search_history'].append(search_entry)
            
            # 최대 20개 검색 히스토리 유지
            if len(context['search_history']) > 20:
                context['search_history'] = context['search_history'][-20:]
            
            cache.set(f"conversation_context_{session_id}", context, self.cache_timeout)
            
            logger.info(f"✅ 검색 히스토리 추가: {search_query}")
            
        except Exception as e:
            logger.error(f"❌ 검색 히스토리 추가 실패: {e}")
    
    def generate_context_prompt(self, session_id: str, current_message: str) -> str:
        """맥락을 포함한 프롬프트 생성"""
        try:
            relevant_context = self.get_relevant_context(session_id, current_message)
            
            prompt_parts = []
            
            # 최근 관련 대화
            if relevant_context.get('recent_conversations'):
                prompt_parts.append("📝 최근 관련 대화:")
                for conv_info in relevant_context['recent_conversations'][:3]:
                    conv = conv_info['conversation']
                    prompt_parts.append(f"- 사용자: {conv['user_message']}")
                    # 가장 좋은 AI 응답 선택
                    best_response = self._select_best_response(conv['ai_responses'])
                    prompt_parts.append(f"- AI: {best_response[:100]}...")
            
            # 비디오 히스토리
            if relevant_context.get('related_videos'):
                prompt_parts.append("🎬 최근 본 비디오:")
                for video in relevant_context['related_videos']:
                    prompt_parts.append(f"- {video.get('video_name', 'Unknown')}")
            
            # 사용자 선호도
            preferences = relevant_context.get('user_preferences', {})
            if preferences:
                prompt_parts.append("⭐ 사용자 선호도:")
                for key, value in preferences.items():
                    prompt_parts.append(f"- {key}: {value}")
            
            # 검색 패턴
            if relevant_context.get('search_patterns'):
                prompt_parts.append("🔍 최근 검색 패턴:")
                for search in relevant_context['search_patterns']:
                    prompt_parts.append(f"- {search.get('query', 'Unknown')}")
            
            context_prompt = "\n".join(prompt_parts) if prompt_parts else ""
            
            if context_prompt:
                context_prompt = f"다음은 이전 대화 맥락입니다:\n\n{context_prompt}\n\n위 맥락을 고려하여 자연스럽게 응답해주세요."
            
            return context_prompt
            
        except Exception as e:
            logger.error(f"❌ 맥락 프롬프트 생성 실패: {e}")
            return ""
    
    def _extract_intent(self, message: str) -> str:
        """메시지에서 의도 추출"""
        try:
            message_lower = message.lower()
            
            intent_keywords = {
                'video_summary': ['요약', 'summary', '간단', '상세', '하이라이트'],
                'video_search': ['찾아', '검색', 'search', '보여', '어디'],
                'person_search': ['사람', 'person', 'people', 'human', '남성', '여성'],
                'color_search': ['빨간색', '파란색', '노란색', '초록색', '색깔', '색상'],
                'temporal_analysis': ['시간', '분', '초', '언제', '몇시', '성비', '인원'],
                'general_chat': ['안녕', 'hello', 'hi', '고마워', '감사', '도움']
            }
            
            for intent, keywords in intent_keywords.items():
                if any(keyword in message_lower for keyword in keywords):
                    return intent
            
            return 'general_chat'
            
        except Exception as e:
            logger.error(f"❌ 의도 추출 실패: {e}")
            return 'general_chat'
    
    def _extract_entities(self, message: str) -> List[str]:
        """메시지에서 엔티티 추출"""
        try:
            import re
            
            entities = []
            
            # 색상 엔티티
            colors = re.findall(r'(빨간색|파란색|노란색|초록색|보라색|분홍색|검은색|흰색|회색|주황색|갈색)', message)
            entities.extend(colors)
            
            # 시간 엔티티
            time_patterns = re.findall(r'(\d+):(\d+)~(\d+):(\d+)|(\d+)분~(\d+)분|(\d+)초~(\d+)초', message)
            if time_patterns:
                entities.append('time_range')
            
            # 숫자 엔티티
            numbers = re.findall(r'\d+', message)
            entities.extend(numbers)
            
            return entities
            
        except Exception as e:
            logger.error(f"❌ 엔티티 추출 실패: {e}")
            return []
    
    def _calculate_relevance(self, conversation: Dict[str, Any], 
                           current_intent: str, current_entities: List[str]) -> float:
        """대화 관련성 점수 계산"""
        try:
            score = 0.0
            
            # 의도 일치
            if conversation.get('intent') == current_intent:
                score += 0.5
            
            # 엔티티 일치
            conv_entities = conversation.get('entities', [])
            entity_overlap = len(set(conv_entities) & set(current_entities))
            if entity_overlap > 0:
                score += 0.3 * (entity_overlap / max(len(conv_entities), len(current_entities)))
            
            # 키워드 일치
            conv_message = conversation.get('user_message', '').lower()
            # 간단한 키워드 매칭
            common_words = set(conv_message.split()) & set(current_entities)
            if common_words:
                score += 0.2
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"❌ 관련성 계산 실패: {e}")
            return 0.0
    
    def _select_best_response(self, ai_responses: Dict[str, str]) -> str:
        """가장 좋은 AI 응답 선택"""
        try:
            if not ai_responses:
                return ""
            
            # 간단한 선택 로직 (길이와 구조 고려)
            best_response = ""
            best_score = 0
            
            for ai_name, response in ai_responses.items():
                score = 0
                
                # 길이 점수 (50-200 단어가 이상적)
                word_count = len(response.split())
                if 50 <= word_count <= 200:
                    score += 0.5
                elif 30 <= word_count < 50 or 200 < word_count <= 300:
                    score += 0.3
                
                # 구조 점수
                if '\n' in response or len(response.split('.')) > 3:
                    score += 0.3
                
                # AI별 가중치
                if ai_name == 'gpt':
                    score += 0.2
                elif ai_name == 'claude':
                    score += 0.2
                elif ai_name == 'mixtral':
                    score += 0.1
                
                if score > best_score:
                    best_score = score
                    best_response = response
            
            return best_response or list(ai_responses.values())[0]
            
        except Exception as e:
            logger.error(f"❌ 최적 응답 선택 실패: {e}")
            return list(ai_responses.values())[0] if ai_responses else ""
    
    def clear_context(self, session_id: str) -> None:
        """대화 맥락 초기화"""
        try:
            cache.delete(f"conversation_context_{session_id}")
            logger.info(f"✅ 대화 맥락 초기화: {session_id}")
            
        except Exception as e:
            logger.error(f"❌ 대화 맥락 초기화 실패: {e}")

# 전역 인스턴스 생성
conversation_memory = ConversationMemory()
