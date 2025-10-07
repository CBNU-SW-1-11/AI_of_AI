"""
앙상블 학습 기법을 활용한 AI 통합 답변 최적화 시스템
프로젝트 목표: AI 통합 기반 답변 최적화 플랫폼
"""

import json
import logging
import numpy as np
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)

# scikit-learn 의존성을 선택적으로 처리
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
    print("✅ scikit-learn 사용 가능")
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn 사용 불가 - 기본 기능만 사용")

@dataclass
class AIResponse:
    """AI 응답 데이터 구조"""
    model_name: str
    content: str
    confidence: float
    quality_score: float
    helpfulness_score: float
    clarity_score: float
    factual_accuracy: float
    completeness_score: float
    ensemble_contribution: float

@dataclass
class EnsembleResult:
    """앙상블 학습 결과"""
    final_answer: str
    confidence_score: float
    consensus_level: str
    contributing_ais: List[str]
    disagreements: List[str]
    reasoning: str
    query_type: str
    ensemble_weights: Dict[str, float]
    quality_metrics: Dict[str, float]

class EnsembleLearningOptimizer:
    """앙상블 학습을 활용한 AI 응답 최적화 시스템"""
    
    def __init__(self):
        if SKLEARN_AVAILABLE:
            self.vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2)
            )
        else:
            self.vectorizer = None
        print("🔍 앙상블 학습 최적화 시스템 초기화 완료")
    
    def optimize_responses(self, responses: Dict[str, str], query: str, file_context: str = None) -> Dict[str, Any]:
        """앙상블 학습을 활용한 응답 최적화"""
        try:
            print(f"🔍 앙상블 학습 시작: {len(responses)}개 응답")
            
            # 간단한 앙상블 답변 생성 (안전한 방식)
            simple_result = self._create_simple_ensemble_response(responses, query)
            if simple_result:
                print("✅ 간단한 앙상블 답변 생성 성공")
                return simple_result
            
            # 고급 앙상블 학습 시도
            try:
                # 1. 응답 분석 및 구조화
                ai_responses = self._analyze_and_structure_responses(responses, query)
                
                # 2. 질문 유형 분류
                query_type = self._classify_query_type(query)
                
                # 3. 앙상블 가중치 계산
                ensemble_weights = self._calculate_ensemble_weights(ai_responses, query_type)
                
                # 4. 합의도 분석
                consensus_analysis = self._analyze_consensus(ai_responses)
                
                # 5. 최종 답변 생성 (앙상블 학습)
                final_answer = self._generate_ensemble_answer(ai_responses, ensemble_weights, query, query_type)
                
                # 6. 품질 지표 계산
                quality_metrics = self._calculate_quality_metrics(ai_responses, final_answer)
                
                # 7. 결과 구성
                result = EnsembleResult(
                    final_answer=final_answer,
                    confidence_score=quality_metrics['overall_confidence'],
                    consensus_level=consensus_analysis['consensus_level'],
                    contributing_ais=[resp.model_name for resp in ai_responses if resp.ensemble_contribution > 0.3],
                    disagreements=consensus_analysis['disagreements'],
                    reasoning=f"앙상블 학습 기법 적용. 질문 유형: {query_type}",
                    query_type=query_type,
                    ensemble_weights=ensemble_weights,
                    quality_metrics=quality_metrics
                )
                
                print(f"✅ 앙상블 학습 완료: 신뢰도 {quality_metrics['overall_confidence']:.2f}")
                return self._convert_to_dict(result)
                
            except Exception as advanced_e:
                print(f"❌ 고급 앙상블 학습 실패: {advanced_e}")
                # 간단한 앙상블 답변으로 폴백
                return self._create_simple_ensemble_response(responses, query)
            
        except Exception as e:
            logger.error(f"❌ 앙상블 학습 실패: {e}")
            print(f"❌ 앙상블 학습 실패: {e}")
            import traceback
            traceback.print_exc()
            return self._create_fallback_result(responses)
    
    def _create_simple_ensemble_response(self, responses: Dict[str, str], query: str) -> Dict[str, Any]:
        """간단한 앙상블 답변 생성 (안전한 방식)"""
        try:
            print(f"🔍 간단한 앙상블 답변 생성: {len(responses)}개 응답")
            
            if not responses:
                return None
            
            # 질문 유형 간단 분류
            query_type = self._classify_query_type(query)
            
            # 모델별 기본 가중치
            model_weights = {
                'technical': {'gpt': 0.4, 'claude': 0.3, 'mixtral': 0.3},
                'creative': {'claude': 0.4, 'gpt': 0.3, 'mixtral': 0.3},
                'factual': {'gpt': 0.35, 'claude': 0.35, 'mixtral': 0.3},
                'general': {'gpt': 0.35, 'claude': 0.35, 'mixtral': 0.3}
            }
            
            weights = model_weights.get(query_type, model_weights['general'])
            
            # 가중치가 높은 순으로 정렬
            sorted_responses = sorted(
                responses.items(), 
                key=lambda x: weights.get(x[0], 0.3), 
                reverse=True
            )
            
            # 주요 응답 선택
            primary_response = sorted_responses[0][1]
            
            # 간단한 앙상블 답변 구성
            ensemble_parts = []
            
            # 통합 답변
            ensemble_parts.append("## 🎯 통합 답변")
            ensemble_parts.append(primary_response)
            
            # 각 AI 분석
            ensemble_parts.append("\n## 📊 각 AI 분석")
            for ai_name, response in sorted_responses[:2]:  # 상위 2개만
                weight = weights.get(ai_name, 0.3)
                ensemble_parts.append(f"### {ai_name.upper()}")
                ensemble_parts.append(f"- 신뢰도: {weight*100:.1f}%")
                ensemble_parts.append(f"- 앙상블 기여도: {weight*100:.1f}%")
                
                # 간단한 장점 분석
                if ai_name == 'gpt':
                    ensemble_parts.append("- 장점: 기술적 문제 해결에 뛰어남")
                elif ai_name == 'claude':
                    ensemble_parts.append("- 장점: 상세하고 포괄적인 답변")
                elif ai_name == 'mixtral':
                    ensemble_parts.append("- 장점: 빠르고 간결한 답변")
            
            # 분석 근거
            ensemble_parts.append("\n## 🔍 분석 근거")
            ensemble_parts.append(f"- 질문 유형: {query_type}")
            ensemble_parts.append(f"- 앙상블 가중치: {dict(sorted(weights.items(), key=lambda x: x[1], reverse=True))}")
            ensemble_parts.append(f"- 주요 기여 모델: {sorted_responses[0][0].upper()}")
            
            # 최종 추천
            ensemble_parts.append("\n## 🏆 최종 추천")
            best_model = sorted_responses[0][0]
            ensemble_parts.append(f"- {query_type} 유형 질문에는 {best_model.upper()}가 가장 적합합니다.")
            ensemble_parts.append(f"- 전체 신뢰도: {max(weights.values())*100:.1f}%")
            
            final_answer = "\n".join(ensemble_parts)
            
            return {
                'final_answer': final_answer,
                'confidence_score': max(weights.values()),
                'consensus_level': 'medium',
                'contributing_ais': [sorted_responses[0][0]],
                'disagreements': [],
                'reasoning': f"간단한 앙상블 학습 적용. 질문 유형: {query_type}",
                'query_type': query_type,
                'ensemble_weights': weights,
                'quality_metrics': {
                    'overall_confidence': max(weights.values()),
                    'quality_score': 0.7,
                    'helpfulness_score': 0.7,
                    'clarity_score': 0.7,
                    'factual_accuracy': 0.7
                }
            }
            
        except Exception as e:
            print(f"❌ 간단한 앙상블 답변 생성 실패: {e}")
            return None
    
    def _analyze_and_structure_responses(self, responses: Dict[str, str], query: str) -> List[AIResponse]:
        """응답 분석 및 구조화"""
        ai_responses = []
        
        for model_name, content in responses.items():
            try:
                # 기본 품질 지표 계산
                quality_scores = self._calculate_basic_quality_scores(content, query)
                
                ai_response = AIResponse(
                    model_name=model_name,
                    content=content,
                    confidence=quality_scores['confidence'],
                    quality_score=quality_scores['quality'],
                    helpfulness_score=quality_scores['helpfulness'],
                    clarity_score=quality_scores['clarity'],
                    factual_accuracy=quality_scores['factual_accuracy'],
                    completeness_score=quality_scores['completeness'],
                    ensemble_contribution=0.0  # 나중에 계산
                )
                
                ai_responses.append(ai_response)
                print(f"✅ {model_name} 응답 분석 완료: 품질 {quality_scores['quality']:.2f}")
                
            except Exception as e:
                logger.warning(f"{model_name} 응답 분석 실패: {e}")
                continue
        
        return ai_responses
    
    def _calculate_basic_quality_scores(self, content: str, query: str) -> Dict[str, float]:
        """기본 품질 지표 계산"""
        try:
            # 길이 기반 완성도
            completeness = min(len(content) / max(len(query) * 3, 100), 1.0)
            
            # 명확성 (문장 구조 분석)
            sentences = re.split(r'[.!?]+', content)
            avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
            clarity = max(0, 1 - abs(avg_sentence_length - 15) / 15)  # 15단어가 이상적
            
            # 유용성 (질문 키워드 포함도)
            query_words = set(query.lower().split())
            content_words = set(content.lower().split())
            helpfulness = len(query_words.intersection(content_words)) / max(len(query_words), 1)
            
            # 사실 정확성 (숫자, 날짜 등 구체적 정보 포함도)
            factual_elements = len(re.findall(r'\d+', content)) + len(re.findall(r'\d{4}', content))
            factual_accuracy = min(factual_elements / 5, 1.0)  # 최대 5개 요소
            
            # 전체 품질 (가중 평균)
            quality = (completeness * 0.3 + clarity * 0.25 + helpfulness * 0.25 + factual_accuracy * 0.2)
            
            # 신뢰도 (품질의 제곱근으로 보정)
            confidence = quality ** 0.5
            
            return {
                'completeness': completeness,
                'clarity': clarity,
                'helpfulness': helpfulness,
                'factual_accuracy': factual_accuracy,
                'quality': quality,
                'confidence': confidence
            }
            
        except Exception as e:
            logger.warning(f"품질 지표 계산 실패: {e}")
            return {
                'completeness': 0.5,
                'clarity': 0.5,
                'helpfulness': 0.5,
                'factual_accuracy': 0.5,
                'quality': 0.5,
                'confidence': 0.5
            }
    
    def _classify_query_type(self, query: str) -> str:
        """질문 유형 분류"""
        query_lower = query.lower()
        
        # 기술적 질문
        technical_keywords = ['코드', '프로그래밍', '알고리즘', '개발', '기술', '시스템', '데이터베이스']
        if any(keyword in query_lower for keyword in technical_keywords):
            return 'technical'
        
        # 창의적 질문
        creative_keywords = ['아이디어', '창의', '디자인', '글쓰기', '스토리', '상상', '혁신']
        if any(keyword in query_lower for keyword in creative_keywords):
            return 'creative'
        
        # 사실적 질문
        factual_keywords = ['언제', '어디서', '누가', '무엇을', '얼마나', '정의', '의미']
        if any(keyword in query_lower for keyword in factual_keywords):
            return 'factual'
        
        # 분석적 질문
        analytical_keywords = ['분석', '비교', '평가', '장단점', '차이점', '관계', '원인']
        if any(keyword in query_lower for keyword in analytical_keywords):
            return 'analytical'
        
        return 'general'
    
    def _calculate_ensemble_weights(self, ai_responses: List[AIResponse], query_type: str) -> Dict[str, float]:
        """앙상블 가중치 계산"""
        weights = {}
        
        # 질문 유형별 모델 선호도
        model_preferences = {
            'technical': {'gpt': 0.4, 'claude': 0.3, 'mixtral': 0.3},
            'creative': {'claude': 0.4, 'gpt': 0.3, 'mixtral': 0.3},
            'factual': {'gpt': 0.35, 'claude': 0.35, 'mixtral': 0.3},
            'analytical': {'claude': 0.4, 'gpt': 0.35, 'mixtral': 0.25},
            'general': {'gpt': 0.35, 'claude': 0.35, 'mixtral': 0.3}
        }
        
        base_preferences = model_preferences.get(query_type, model_preferences['general'])
        
        # 품질 점수 기반 가중치 조정
        total_quality = sum(resp.quality_score for resp in ai_responses)
        
        for resp in ai_responses:
            # 기본 선호도
            base_weight = base_preferences.get(resp.model_name, 0.3)
            
            # 품질 점수 기반 조정
            quality_factor = resp.quality_score / max(total_quality, 0.1)
            
            # 최종 가중치
            weights[resp.model_name] = base_weight * quality_factor
        
        # 가중치 정규화
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        
        print(f"🔍 앙상블 가중치: {weights}")
        return weights
    
    def _analyze_consensus(self, ai_responses: List[AIResponse]) -> Dict[str, Any]:
        """합의도 분석"""
        if len(ai_responses) < 2:
            return {
                'consensus_level': 'low',
                'agreements': [],
                'disagreements': [],
                'agreement_ratio': 0.0
            }
        
        try:
            # TF-IDF 벡터화
            contents = [resp.content for resp in ai_responses]
            tfidf_matrix = self.vectorizer.fit_transform(contents)
            
            # 코사인 유사도 계산
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
            # 평균 유사도 계산
            avg_similarity = np.mean(similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)])
            
            # 합의도 레벨 결정
            if avg_similarity > 0.7:
                consensus_level = 'high'
            elif avg_similarity > 0.4:
                consensus_level = 'medium'
            else:
                consensus_level = 'low'
            
            # 공통 키워드 추출
            agreements = self._extract_common_keywords(contents)
            
            return {
                'consensus_level': consensus_level,
                'agreements': agreements,
                'disagreements': [],
                'agreement_ratio': avg_similarity
            }
            
        except Exception as e:
            logger.warning(f"합의도 분석 실패: {e}")
            return {
                'consensus_level': 'low',
                'agreements': [],
                'disagreements': [],
                'agreement_ratio': 0.0
            }
    
    def _extract_common_keywords(self, contents: List[str]) -> List[str]:
        """공통 키워드 추출"""
        try:
            # 모든 텍스트 결합
            all_text = ' '.join(contents)
            
            # 단어 빈도 계산
            words = re.findall(r'\b\w+\b', all_text.lower())
            word_freq = {}
            
            for word in words:
                if len(word) > 2:  # 2글자 이상만
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # 공통 키워드 (모든 텍스트에 나타나는 단어)
            common_keywords = []
            for word, freq in word_freq.items():
                if freq >= len(contents):  # 모든 응답에 나타남
                    common_keywords.append(word)
            
            return common_keywords[:10]  # 상위 10개
            
        except Exception as e:
            logger.warning(f"공통 키워드 추출 실패: {e}")
            return []
    
    def _generate_ensemble_answer(self, ai_responses: List[AIResponse], weights: Dict[str, float], query: str, query_type: str) -> str:
        """앙상블 학습을 활용한 최종 답변 생성"""
        try:
            # 가중치가 높은 순으로 정렬
            sorted_responses = sorted(ai_responses, key=lambda x: weights.get(x.model_name, 0), reverse=True)
            
            # 주요 응답 선택 (가중치 상위 2개)
            primary_responses = sorted_responses[:2]
            
            # 앙상블 답변 구성
            ensemble_answer = self._construct_ensemble_answer(primary_responses, weights, query, query_type)
            
            return ensemble_answer
            
        except Exception as e:
            logger.error(f"앙상블 답변 생성 실패: {e}")
            # 폴백: 가장 품질이 높은 응답 사용
            best_response = max(ai_responses, key=lambda x: x.quality_score)
            return best_response.content
    
    def _construct_ensemble_answer(self, primary_responses: List[AIResponse], weights: Dict[str, float], query: str, query_type: str) -> str:
        """앙상블 답변 구성"""
        try:
            # 기본 구조
            answer_parts = []
            
            # 통합 답변 섹션
            main_content = primary_responses[0].content
            if len(primary_responses) > 1:
                # 두 번째 응답의 보완 정보 추가
                secondary_content = primary_responses[1].content
                main_content = self._merge_responses(main_content, secondary_content)
            
            answer_parts.append(f"## 🎯 통합 답변\n{main_content}")
            
            # 각 AI 분석 섹션
            analysis_parts = []
            for resp in primary_responses:
                weight = weights.get(resp.model_name, 0)
                analysis = f"### {resp.model_name.upper()}\n"
                analysis += f"- 신뢰도: {resp.confidence:.1%}\n"
                analysis += f"- 품질 점수: {resp.quality_score:.1%}\n"
                analysis += f"- 앙상블 기여도: {weight:.1%}\n"
                analysis += f"- 장점: {self._get_model_strengths(resp.model_name, query_type)}\n"
                analysis_parts.append(analysis)
            
            answer_parts.append(f"## 📊 각 AI 분석\n" + "\n".join(analysis_parts))
            
            # 분석 근거 섹션
            reasoning = f"## 🔍 분석 근거\n"
            reasoning += f"- 질문 유형: {query_type}\n"
            reasoning += f"- 앙상블 가중치: {dict(sorted(weights.items(), key=lambda x: x[1], reverse=True))}\n"
            reasoning += f"- 주요 기여 모델: {primary_responses[0].model_name.upper()}\n"
            
            answer_parts.append(reasoning)
            
            # 최종 추천 섹션
            recommendation = f"## 🏆 최종 추천\n"
            recommendation += f"- {query_type} 유형 질문에는 {primary_responses[0].model_name.upper()}가 가장 적합합니다.\n"
            recommendation += f"- 전체 신뢰도: {sum(resp.confidence * weights.get(resp.model_name, 0) for resp in primary_responses):.1%}\n"
            
            answer_parts.append(recommendation)
            
            return "\n\n".join(answer_parts)
            
        except Exception as e:
            logger.error(f"앙상블 답변 구성 실패: {e}")
            return primary_responses[0].content if primary_responses else "답변을 생성할 수 없습니다."
    
    def _merge_responses(self, primary: str, secondary: str) -> str:
        """두 응답을 지능적으로 병합"""
        try:
            # 문장 단위로 분리
            primary_sentences = re.split(r'[.!?]+', primary)
            secondary_sentences = re.split(r'[.!?]+', secondary)
            
            # 중복 제거 및 병합
            merged_sentences = []
            used_sentences = set()
            
            # 주요 응답 우선
            for sentence in primary_sentences:
                sentence = sentence.strip()
                if sentence and sentence not in used_sentences:
                    merged_sentences.append(sentence)
                    used_sentences.add(sentence)
            
            # 보조 응답에서 보완 정보 추가
            for sentence in secondary_sentences:
                sentence = sentence.strip()
                if sentence and sentence not in used_sentences and len(sentence) > 20:
                    merged_sentences.append(sentence)
                    used_sentences.add(sentence)
            
            return '. '.join(merged_sentences) + '.'
            
        except Exception as e:
            logger.warning(f"응답 병합 실패: {e}")
            return primary
    
    def _get_model_strengths(self, model_name: str, query_type: str) -> str:
        """모델별 강점 반환"""
        strengths = {
            'gpt': {
                'technical': '코딩과 기술적 문제 해결에 뛰어남',
                'factual': '사실 정보 제공에 정확함',
                'analytical': '논리적 분석과 추론이 강함',
                'creative': '창의적 아이디어 생성 가능',
                'general': '다양한 주제에 균형잡힌 답변'
            },
            'claude': {
                'technical': '복잡한 기술 문제 이해도가 높음',
                'factual': '정확한 정보 검증과 제공',
                'analytical': '심층 분석과 통찰력 제공',
                'creative': '창의적 사고와 글쓰기 전문',
                'general': '상세하고 포괄적인 답변'
            },
            'mixtral': {
                'technical': '빠른 기술적 응답 제공',
                'factual': '간결한 사실 정보 전달',
                'analytical': '효율적인 분석과 요약',
                'creative': '신속한 창의적 아이디어',
                'general': '빠르고 간결한 답변'
            }
        }
        
        return strengths.get(model_name, {}).get(query_type, '균형잡힌 답변 제공')
    
    def _calculate_quality_metrics(self, ai_responses: List[AIResponse], final_answer: str) -> Dict[str, float]:
        """품질 지표 계산"""
        try:
            # 전체 신뢰도
            overall_confidence = np.mean([resp.confidence for resp in ai_responses])
            
            # 품질 점수
            quality_score = np.mean([resp.quality_score for resp in ai_responses])
            
            # 유용성 점수
            helpfulness_score = np.mean([resp.helpfulness_score for resp in ai_responses])
            
            # 명확성 점수
            clarity_score = np.mean([resp.clarity_score for resp in ai_responses])
            
            # 사실 정확성
            factual_accuracy = np.mean([resp.factual_accuracy for resp in ai_responses])
            
            return {
                'overall_confidence': overall_confidence,
                'quality_score': quality_score,
                'helpfulness_score': helpfulness_score,
                'clarity_score': clarity_score,
                'factual_accuracy': factual_accuracy
            }
            
        except Exception as e:
            logger.warning(f"품질 지표 계산 실패: {e}")
            return {
                'overall_confidence': 0.5,
                'quality_score': 0.5,
                'helpfulness_score': 0.5,
                'clarity_score': 0.5,
                'factual_accuracy': 0.5
            }
    
    def _convert_to_dict(self, result: EnsembleResult) -> Dict[str, Any]:
        """EnsembleResult를 딕셔너리로 변환"""
        return {
            'final_answer': result.final_answer,
            'confidence_score': result.confidence_score,
            'consensus_level': result.consensus_level,
            'contributing_ais': result.contributing_ais,
            'disagreements': result.disagreements,
            'reasoning': result.reasoning,
            'query_type': result.query_type,
            'ensemble_weights': result.ensemble_weights,
            'quality_metrics': result.quality_metrics
        }
    
    def _create_fallback_result(self, responses: Dict[str, str]) -> Dict[str, Any]:
        """폴백 결과 생성"""
        if responses:
            first_response = list(responses.values())[0]
            return {
                'final_answer': first_response,
                'confidence_score': 0.5,
                'consensus_level': 'low',
                'contributing_ais': list(responses.keys())[:1],
                'disagreements': [],
                'reasoning': "앙상블 학습 실패로 폴백 모드 사용",
                'query_type': 'general',
                'ensemble_weights': {list(responses.keys())[0]: 1.0},
                'quality_metrics': {
                    'overall_confidence': 0.5,
                    'quality_score': 0.5,
                    'helpfulness_score': 0.5,
                    'clarity_score': 0.5,
                    'factual_accuracy': 0.5
                }
            }
        else:
            return {
                'final_answer': "AI 응답을 생성할 수 없습니다.",
                'confidence_score': 0.0,
                'consensus_level': 'none',
                'contributing_ais': [],
                'disagreements': [],
                'reasoning': "모든 AI 응답 생성 실패",
                'query_type': 'general',
                'ensemble_weights': {},
                'quality_metrics': {
                    'overall_confidence': 0.0,
                    'quality_score': 0.0,
                    'helpfulness_score': 0.0,
                    'clarity_score': 0.0,
                    'factual_accuracy': 0.0
                }
            }


# 전역 인스턴스
ensemble_learning_optimizer = EnsembleLearningOptimizer()
