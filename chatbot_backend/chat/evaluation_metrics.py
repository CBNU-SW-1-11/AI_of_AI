"""
AI 통합 답변 최적화 플랫폼용 답변 품질 평가 시스템
프로젝트 목표: AI 통합 기반 답변 최적화 플랫폼
"""

import re
import json
import numpy as np
from typing import Dict, List, Any, Tuple
from collections import Counter
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class EvaluationMetrics:
    """AI 통합 답변 최적화 플랫폼용 품질 평가 시스템"""
    
    def __init__(self):
        self.metrics_cache = {}
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        print("🔍 AI 통합 답변 품질 평가 시스템 초기화 완료")
    
    def evaluate_ensemble_quality(self, ai_responses: Dict[str, str], ensemble_answer: str, query: str) -> Dict[str, Any]:
        """앙상블 학습 결과의 품질 평가"""
        try:
            print(f"🔍 앙상블 품질 평가 시작: {len(ai_responses)}개 응답")
            
            results = {}
            
            # 1. 개별 AI 응답 품질 평가
            individual_scores = {}
            for ai_name, response in ai_responses.items():
                individual_scores[ai_name] = self._evaluate_individual_response(response, query)
            
            # 2. 앙상블 답변 품질 평가
            ensemble_score = self._evaluate_ensemble_response(ensemble_answer, query)
            
            # 3. 앙상블 효과성 평가
            ensemble_effectiveness = self._evaluate_ensemble_effectiveness(ai_responses, ensemble_answer)
            
            # 4. 신뢰도 및 일관성 평가
            reliability_metrics = self._evaluate_reliability_and_consistency(ai_responses, ensemble_answer)
            
            # 5. 사용자 만족도 예측
            user_satisfaction_score = self._predict_user_satisfaction(ensemble_answer, query)
            
            results = {
                'individual_scores': individual_scores,
                'ensemble_score': ensemble_score,
                'ensemble_effectiveness': ensemble_effectiveness,
                'reliability_metrics': reliability_metrics,
                'user_satisfaction_score': user_satisfaction_score,
                'overall_quality': self._calculate_overall_ensemble_quality(
                    individual_scores, ensemble_score, ensemble_effectiveness, reliability_metrics, user_satisfaction_score
                )
            }
            
            print(f"✅ 앙상블 품질 평가 완료: 전체 품질 {results['overall_quality']:.2f}")
            return results
            
        except Exception as e:
            logger.error(f"❌ 앙상블 품질 평가 실패: {e}")
            return self._create_fallback_evaluation(ai_responses, ensemble_answer)
    
    def _evaluate_individual_response(self, response: str, query: str) -> Dict[str, float]:
        """개별 AI 응답 품질 평가"""
        try:
            # 기본 메트릭
            basic_metrics = self._calculate_basic_metrics(response)
            
            # 질문 관련성
            relevance_score = self._calculate_relevance_score(response, query)
            
            # 응답 완성도
            completeness_score = self._calculate_completeness_score(response, query)
            
            # 명확성 및 가독성
            clarity_score = self._calculate_clarity_score(response)
            
            # 사실 정확성 (간단한 휴리스틱)
            factual_accuracy = self._calculate_factual_accuracy(response)
            
            # 유용성
            usefulness_score = self._calculate_usefulness_score(response, query)
            
            return {
                'basic_metrics': basic_metrics,
                'relevance_score': relevance_score,
                'completeness_score': completeness_score,
                'clarity_score': clarity_score,
                'factual_accuracy': factual_accuracy,
                'usefulness_score': usefulness_score,
                'overall_score': np.mean([
                    relevance_score, completeness_score, clarity_score, 
                    factual_accuracy, usefulness_score
                ])
            }
            
        except Exception as e:
            logger.warning(f"개별 응답 평가 실패: {e}")
            return {
                'basic_metrics': {'word_count': len(response.split()), 'sentence_count': len(re.split(r'[.!?]+', response))},
                'relevance_score': 0.5,
                'completeness_score': 0.5,
                'clarity_score': 0.5,
                'factual_accuracy': 0.5,
                'usefulness_score': 0.5,
                'overall_score': 0.5
            }
    
    def _evaluate_ensemble_response(self, ensemble_answer: str, query: str) -> Dict[str, float]:
        """앙상블 답변 품질 평가"""
        try:
            # 구조적 완성도 (마크다운 구조 분석)
            structure_score = self._evaluate_ensemble_structure(ensemble_answer)
            
            # 정보 밀도
            information_density = self._calculate_information_density(ensemble_answer)
            
            # 앙상블 특성 평가
            ensemble_characteristics = self._evaluate_ensemble_characteristics(ensemble_answer)
            
            # 종합 품질
            overall_quality = np.mean([
                structure_score, information_density, ensemble_characteristics
            ])
            
            return {
                'structure_score': structure_score,
                'information_density': information_density,
                'ensemble_characteristics': ensemble_characteristics,
                'overall_quality': overall_quality
            }
            
        except Exception as e:
            logger.warning(f"앙상블 응답 평가 실패: {e}")
            return {
                'structure_score': 0.5,
                'information_density': 0.5,
                'ensemble_characteristics': 0.5,
                'overall_quality': 0.5
            }
    
    def _evaluate_ensemble_effectiveness(self, ai_responses: Dict[str, str], ensemble_answer: str) -> Dict[str, float]:
        """앙상블 효과성 평가"""
        try:
            # 개별 응답과 앙상블 답변의 유사도 분석
            similarities = []
            for ai_name, response in ai_responses.items():
                similarity = self._calculate_text_similarity(response, ensemble_answer)
                similarities.append(similarity)
            
            avg_similarity = np.mean(similarities)
            
            # 앙상블이 개별 응답보다 얼마나 개선되었는지 평가
            improvement_score = self._calculate_improvement_score(ai_responses, ensemble_answer)
            
            # 다양성 점수 (개별 응답들 간의 차이)
            diversity_score = self._calculate_diversity_score(list(ai_responses.values()))
            
            return {
                'avg_similarity': avg_similarity,
                'improvement_score': improvement_score,
                'diversity_score': diversity_score,
                'effectiveness_score': np.mean([improvement_score, diversity_score])
            }
            
        except Exception as e:
            logger.warning(f"앙상블 효과성 평가 실패: {e}")
            return {
                'avg_similarity': 0.5,
                'improvement_score': 0.5,
                'diversity_score': 0.5,
                'effectiveness_score': 0.5
            }
    
    def _evaluate_reliability_and_consistency(self, ai_responses: Dict[str, str], ensemble_answer: str) -> Dict[str, float]:
        """신뢰도 및 일관성 평가"""
        try:
            # 응답들 간의 일관성
            consistency_score = self._calculate_consistency_score(list(ai_responses.values()))
            
            # 신뢰도 지표 (구체적 정보 포함도)
            reliability_score = self._calculate_reliability_score(ensemble_answer)
            
            # 불확실성 표시
            uncertainty_score = self._calculate_uncertainty_score(ensemble_answer)
            
            return {
                'consistency_score': consistency_score,
                'reliability_score': reliability_score,
                'uncertainty_score': uncertainty_score,
                'overall_reliability': np.mean([consistency_score, reliability_score, 1 - uncertainty_score])
            }
            
        except Exception as e:
            logger.warning(f"신뢰도 평가 실패: {e}")
            return {
                'consistency_score': 0.5,
                'reliability_score': 0.5,
                'uncertainty_score': 0.5,
                'overall_reliability': 0.5
            }
    
    def _predict_user_satisfaction(self, ensemble_answer: str, query: str) -> float:
        """사용자 만족도 예측"""
        try:
            # 응답 길이 적절성
            length_score = self._calculate_length_appropriateness(ensemble_answer, query)
            
            # 질문 해결도
            resolution_score = self._calculate_query_resolution_score(ensemble_answer, query)
            
            # 사용자 친화성
            user_friendliness = self._calculate_user_friendliness(ensemble_answer)
            
            # 액션 가능성 (실행 가능한 정보 제공)
            actionability = self._calculate_actionability(ensemble_answer)
            
            return np.mean([length_score, resolution_score, user_friendliness, actionability])
            
        except Exception as e:
            logger.warning(f"사용자 만족도 예측 실패: {e}")
            return 0.5
    
    def _calculate_basic_metrics(self, text: str) -> Dict[str, int]:
        """기본 텍스트 메트릭 계산"""
        try:
            words = text.split()
            sentences = re.split(r'[.!?]+', text)
            
            return {
                'word_count': len(words),
                'sentence_count': len([s for s in sentences if s.strip()]),
                'character_count': len(text),
                'avg_words_per_sentence': len(words) / max(len(sentences), 1)
            }
        except Exception as e:
            logger.warning(f"기본 메트릭 계산 실패: {e}")
            return {'word_count': 0, 'sentence_count': 0, 'character_count': 0, 'avg_words_per_sentence': 0}
    
    def _calculate_relevance_score(self, response: str, query: str) -> float:
        """질문 관련성 점수 계산"""
        try:
            query_words = set(query.lower().split())
            response_words = set(response.lower().split())
            
            # 공통 단어 비율
            common_words = query_words.intersection(response_words)
            relevance = len(common_words) / max(len(query_words), 1)
            
            return min(relevance, 1.0)
        except Exception as e:
            logger.warning(f"관련성 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_completeness_score(self, response: str, query: str) -> float:
        """응답 완성도 점수 계산"""
        try:
            # 질문 키워드가 응답에 포함되어 있는지 확인
            query_keywords = re.findall(r'\b\w+\b', query.lower())
            response_lower = response.lower()
            
            covered_keywords = sum(1 for keyword in query_keywords if keyword in response_lower)
            completeness = covered_keywords / max(len(query_keywords), 1)
            
            # 응답 길이도 고려
            length_factor = min(len(response.split()) / max(len(query.split()) * 3, 50), 1.0)
            
            return np.mean([completeness, length_factor])
        except Exception as e:
            logger.warning(f"완성도 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_clarity_score(self, response: str) -> float:
        """명확성 점수 계산"""
        try:
            sentences = re.split(r'[.!?]+', response)
            if not sentences:
                return 0.0
            
            # 평균 문장 길이 (15-20단어가 이상적)
            avg_length = sum(len(s.split()) for s in sentences) / len(sentences)
            length_score = max(0, 1 - abs(avg_length - 17.5) / 17.5)
            
            # 문장 구조 다양성
            structure_variety = len(set(len(s.split()) for s in sentences)) / max(len(sentences), 1)
            
            return np.mean([length_score, structure_variety])
        except Exception as e:
            logger.warning(f"명확성 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_factual_accuracy(self, response: str) -> float:
        """사실 정확성 점수 계산 (휴리스틱)"""
        try:
            # 구체적 정보 포함도
            numbers = len(re.findall(r'\d+', response))
            dates = len(re.findall(r'\d{4}', response))
            specific_terms = len(re.findall(r'\b[A-Z][a-z]+\b', response))  # 고유명사
            
            factual_elements = numbers + dates + specific_terms
            return min(factual_elements / 10, 1.0)  # 최대 10개 요소
        except Exception as e:
            logger.warning(f"사실 정확성 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_usefulness_score(self, response: str, query: str) -> float:
        """유용성 점수 계산"""
        try:
            # 액션 가능한 정보 포함도
            action_words = ['방법', '단계', '과정', '절차', '가이드', '팁', '조언']
            action_count = sum(1 for word in action_words if word in response)
            
            # 구체적 예시 포함도
            example_indicators = ['예를 들어', '예시', '예', '구체적으로', '실제로']
            example_count = sum(1 for indicator in example_indicators if indicator in response)
            
            usefulness = (action_count + example_count) / 5  # 최대 5개
            return min(usefulness, 1.0)
        except Exception as e:
            logger.warning(f"유용성 점수 계산 실패: {e}")
            return 0.5
    
    def _evaluate_ensemble_structure(self, ensemble_answer: str) -> float:
        """앙상블 답변 구조 평가"""
        try:
            # 마크다운 구조 분석
            sections = re.findall(r'## .+', ensemble_answer)
            subsections = re.findall(r'### .+', ensemble_answer)
            
            # 구조적 완성도
            structure_score = 0.0
            if '🎯 통합 답변' in ensemble_answer:
                structure_score += 0.3
            if '📊 각 AI 분석' in ensemble_answer:
                structure_score += 0.3
            if '🔍 분석 근거' in ensemble_answer:
                structure_score += 0.2
            if '🏆 최종 추천' in ensemble_answer:
                structure_score += 0.2
            
            return structure_score
        except Exception as e:
            logger.warning(f"앙상블 구조 평가 실패: {e}")
            return 0.5
    
    def _calculate_information_density(self, text: str) -> float:
        """정보 밀도 계산"""
        try:
            # 의미있는 단어 비율
            words = text.split()
            meaningful_words = [w for w in words if len(w) > 3 and not w.isdigit()]
            density = len(meaningful_words) / max(len(words), 1)
            
            return min(density, 1.0)
        except Exception as e:
            logger.warning(f"정보 밀도 계산 실패: {e}")
            return 0.5
    
    def _evaluate_ensemble_characteristics(self, ensemble_answer: str) -> float:
        """앙상블 특성 평가"""
        try:
            # 앙상블 특성 키워드 포함도
            ensemble_keywords = ['통합', '앙상블', '종합', '분석', '비교', '신뢰도', '가중치']
            keyword_count = sum(1 for keyword in ensemble_keywords if keyword in ensemble_answer)
            
            return min(keyword_count / len(ensemble_keywords), 1.0)
        except Exception as e:
            logger.warning(f"앙상블 특성 평가 실패: {e}")
            return 0.5
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """텍스트 유사도 계산"""
        try:
            if not text1 or not text2:
                return 0.0
            
            # TF-IDF 벡터화
            tfidf_matrix = self.vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            return similarity
        except Exception as e:
            logger.warning(f"텍스트 유사도 계산 실패: {e}")
            return 0.5
    
    def _calculate_improvement_score(self, ai_responses: Dict[str, str], ensemble_answer: str) -> float:
        """개선 점수 계산"""
        try:
            # 개별 응답들의 평균 품질
            individual_qualities = []
            for response in ai_responses.values():
                quality = self._calculate_basic_quality_score(response)
                individual_qualities.append(quality)
            
            avg_individual_quality = np.mean(individual_qualities)
            ensemble_quality = self._calculate_basic_quality_score(ensemble_answer)
            
            # 개선 정도
            improvement = max(0, ensemble_quality - avg_individual_quality)
            return min(improvement, 1.0)
        except Exception as e:
            logger.warning(f"개선 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_diversity_score(self, responses: List[str]) -> float:
        """다양성 점수 계산"""
        try:
            if len(responses) < 2:
                return 0.0
            
            # 응답들 간의 평균 유사도
            similarities = []
            for i in range(len(responses)):
                for j in range(i + 1, len(responses)):
                    similarity = self._calculate_text_similarity(responses[i], responses[j])
                    similarities.append(similarity)
            
            avg_similarity = np.mean(similarities)
            diversity = 1 - avg_similarity  # 유사도가 낮을수록 다양성 높음
            
            return max(diversity, 0.0)
        except Exception as e:
            logger.warning(f"다양성 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_consistency_score(self, responses: List[str]) -> float:
        """일관성 점수 계산"""
        try:
            if len(responses) < 2:
                return 1.0
            
            # 공통 키워드 비율
            all_words = set()
            for response in responses:
                words = set(response.lower().split())
                all_words.update(words)
            
            common_words = set(responses[0].lower().split())
            for response in responses[1:]:
                common_words = common_words.intersection(set(response.lower().split()))
            
            consistency = len(common_words) / max(len(all_words), 1)
            return min(consistency, 1.0)
        except Exception as e:
            logger.warning(f"일관성 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_reliability_score(self, text: str) -> float:
        """신뢰도 점수 계산"""
        try:
            # 구체적 정보 포함도
            numbers = len(re.findall(r'\d+', text))
            dates = len(re.findall(r'\d{4}', text))
            citations = len(re.findall(r'출처|참고|링크|참조', text))
            
            reliability_indicators = numbers + dates + citations
            return min(reliability_indicators / 5, 1.0)
        except Exception as e:
            logger.warning(f"신뢰도 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_uncertainty_score(self, text: str) -> float:
        """불확실성 점수 계산"""
        try:
            # 불확실성 표현 포함도
            uncertainty_words = ['아마도', '추정', '가능성', '불확실', '모호', '정확하지 않음']
            uncertainty_count = sum(1 for word in uncertainty_words if word in text)
            
            return min(uncertainty_count / 3, 1.0)  # 최대 3개
        except Exception as e:
            logger.warning(f"불확실성 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_length_appropriateness(self, response: str, query: str) -> float:
        """응답 길이 적절성 계산"""
        try:
            query_length = len(query.split())
            response_length = len(response.split())
            
            # 이상적인 응답 길이 (질문 길이의 3-10배)
            ideal_min = query_length * 3
            ideal_max = query_length * 10
            
            if ideal_min <= response_length <= ideal_max:
                return 1.0
            elif response_length < ideal_min:
                return response_length / ideal_min
            else:
                return ideal_max / response_length
        except Exception as e:
            logger.warning(f"길이 적절성 계산 실패: {e}")
            return 0.5
    
    def _calculate_query_resolution_score(self, response: str, query: str) -> float:
        """질문 해결도 점수 계산"""
        try:
            # 질문 키워드가 응답에서 해결되었는지 확인
            query_words = set(query.lower().split())
            response_words = set(response.lower().split())
            
            resolved_words = query_words.intersection(response_words)
            resolution_score = len(resolved_words) / max(len(query_words), 1)
            
            return min(resolution_score, 1.0)
        except Exception as e:
            logger.warning(f"질문 해결도 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_user_friendliness(self, text: str) -> float:
        """사용자 친화성 점수 계산"""
        try:
            # 친화적 표현 포함도
            friendly_words = ['도움', '도와드리', '안내', '설명', '이해', '쉽게', '간단히']
            friendly_count = sum(1 for word in friendly_words if word in text)
            
            # 구조화된 정보 제공
            structured_indicators = ['1.', '2.', '3.', '•', '-', '단계', '과정']
            structured_count = sum(1 for indicator in structured_indicators if indicator in text)
            
            friendliness = (friendly_count + structured_count) / 10
            return min(friendliness, 1.0)
        except Exception as e:
            logger.warning(f"사용자 친화성 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_actionability(self, text: str) -> float:
        """액션 가능성 점수 계산"""
        try:
            # 실행 가능한 정보 포함도
            action_words = ['방법', '단계', '과정', '절차', '가이드', '팁', '조언', '실행', '적용']
            action_count = sum(1 for word in action_words if word in text)
            
            # 구체적 예시 포함도
            example_indicators = ['예를 들어', '예시', '예', '구체적으로', '실제로', '경우']
            example_count = sum(1 for indicator in example_indicators if indicator in text)
            
            actionability = (action_count + example_count) / 8
            return min(actionability, 1.0)
        except Exception as e:
            logger.warning(f"액션 가능성 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_basic_quality_score(self, text: str) -> float:
        """기본 품질 점수 계산"""
        try:
            # 길이 기반 점수
            length_score = min(len(text.split()) / 100, 1.0)
            
            # 구조 기반 점수
            structure_score = len(re.findall(r'[.!?]', text)) / max(len(text.split()), 1)
            
            # 다양성 기반 점수
            words = text.split()
            unique_words = len(set(words))
            diversity_score = unique_words / max(len(words), 1)
            
            return np.mean([length_score, structure_score, diversity_score])
        except Exception as e:
            logger.warning(f"기본 품질 점수 계산 실패: {e}")
            return 0.5
    
    def _calculate_overall_ensemble_quality(self, individual_scores: Dict[str, Dict], ensemble_score: Dict, 
                                          ensemble_effectiveness: Dict, reliability_metrics: Dict, 
                                          user_satisfaction_score: float) -> float:
        """전체 앙상블 품질 계산"""
        try:
            # 개별 점수들의 평균
            avg_individual_score = np.mean([score['overall_score'] for score in individual_scores.values()])
            
            # 앙상블 점수
            ensemble_quality = ensemble_score['overall_quality']
            
            # 효과성 점수
            effectiveness_score = ensemble_effectiveness['effectiveness_score']
            
            # 신뢰도 점수
            reliability_score = reliability_metrics['overall_reliability']
            
            # 사용자 만족도
            satisfaction_score = user_satisfaction_score
            
            # 가중 평균 (앙상블 품질에 더 높은 가중치)
            overall_quality = np.average([
                avg_individual_score,
                ensemble_quality,
                effectiveness_score,
                reliability_score,
                satisfaction_score
            ], weights=[0.2, 0.3, 0.2, 0.15, 0.15])
            
            return overall_quality
        except Exception as e:
            logger.warning(f"전체 앙상블 품질 계산 실패: {e}")
            return 0.5
    
    def _create_fallback_evaluation(self, ai_responses: Dict[str, str], ensemble_answer: str) -> Dict[str, Any]:
        """폴백 평가 결과 생성"""
        try:
            individual_scores = {}
            for ai_name in ai_responses.keys():
                individual_scores[ai_name] = {
                    'overall_score': 0.5,
                    'relevance_score': 0.5,
                    'completeness_score': 0.5,
                    'clarity_score': 0.5,
                    'factual_accuracy': 0.5,
                    'usefulness_score': 0.5
                }
            
            return {
                'individual_scores': individual_scores,
                'ensemble_score': {'overall_quality': 0.5},
                'ensemble_effectiveness': {'effectiveness_score': 0.5},
                'reliability_metrics': {'overall_reliability': 0.5},
                'user_satisfaction_score': 0.5,
                'overall_quality': 0.5
            }
        except Exception as e:
            logger.error(f"폴백 평가 생성 실패: {e}")
            return {'overall_quality': 0.0}
    
    # 기존 메서드들 유지 (호환성을 위해)
    def evaluate_summary_quality(self, summaries: Dict[str, str], reference: str = None) -> Dict[str, Any]:
        """기존 요약 품질 평가 메서드 (호환성 유지)"""
        return self.evaluate_ensemble_quality(summaries, reference or "", "")


# 전역 인스턴스
evaluation_metrics = EvaluationMetrics()