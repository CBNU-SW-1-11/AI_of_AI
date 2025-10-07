"""
LangChain RAG를 활용한 신뢰도 검증 시스템
- 내부 자료와 AI 응답 비교 검증
- 벡터 데이터베이스를 활용한 지식 검색
- 응답의 사실성 및 일관성 검증
- 자동 신뢰도 점수 계산
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re

# LangChain 관련 임포트 (선택적)
try:
    from langchain.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.embeddings import OpenAIEmbeddings, HuggingFaceEmbeddings
    from langchain.vectorstores import FAISS, Chroma
    from langchain.chains import RetrievalQA
    from langchain.llms import OpenAI
    from langchain.schema import Document
    from langchain.embeddings.base import Embeddings
    LANGCHAIN_AVAILABLE = True
    print("✅ LangChain RAG 시스템 사용 가능")
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("⚠️ LangChain 사용 불가 - 기본 검증 기능만 사용")

# HuggingFace 임포트 (선택적)
try:
    import torch
    HF_AVAILABLE = True
    print("✅ HuggingFace 사용 가능")
except ImportError:
    HF_AVAILABLE = False
    print("⚠️ HuggingFace 사용 불가")

logger = logging.getLogger(__name__)

@dataclass
class VerificationResult:
    """검증 결과"""
    overall_score: float
    factual_accuracy: float
    consistency_score: float
    source_verification: float
    contradictions: List[str]
    verified_facts: List[str]
    missing_information: List[str]
    confidence_level: str

@dataclass
class KnowledgeSource:
    """지식 소스"""
    source_id: str
    source_type: str  # 'document', 'database', 'api', 'knowledge_base'
    content: str
    metadata: Dict[str, Any]
    embedding_vector: Optional[List[float]] = None
    last_updated: str = None

class RAGVerificationSystem:
    """LangChain RAG를 활용한 신뢰도 검증 시스템"""
    
    def __init__(self):
        self.knowledge_base = []
        self.vector_store = None
        self.embeddings = None
        self.retrieval_qa = None
        
        # 검증 설정
        self.verification_config = {
            'similarity_threshold': 0.7,
            'factual_accuracy_weight': 0.4,
            'consistency_weight': 0.3,
            'source_verification_weight': 0.3,
            'max_retrieved_docs': 5
        }
        
        # 지식 소스 디렉토리
        self.knowledge_sources_dir = os.path.join(os.path.dirname(__file__), 'knowledge_sources')
        os.makedirs(self.knowledge_sources_dir, exist_ok=True)
        
        if LANGCHAIN_AVAILABLE:
            self._initialize_rag_system()
        
        print("🔍 RAG 검증 시스템 초기화 완료")
    
    def _initialize_rag_system(self):
        """RAG 시스템 초기화"""
        try:
            # 임베딩 모델 초기화
            if os.getenv('OPENAI_API_KEY'):
                self.embeddings = OpenAIEmbeddings()
                print("✅ OpenAI 임베딩 사용")
            elif HF_AVAILABLE:
                # 무료 HuggingFace 임베딩 사용
                self.embeddings = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                )
                print("✅ HuggingFace 임베딩 사용")
            else:
                print("⚠️ 임베딩 모델을 사용할 수 없습니다.")
                return
            
            # 기존 벡터 스토어 로드 또는 새로 생성
            self._load_or_create_vector_store()
            
            # 검증 체인 초기화
            self._initialize_verification_chain()
            
        except Exception as e:
            logger.error(f"RAG 시스템 초기화 실패: {e}")
    
    def _load_or_create_vector_store(self):
        """벡터 스토어 로드 또는 생성"""
        try:
            vector_store_path = os.path.join(self.knowledge_sources_dir, 'vector_store')
            
            if os.path.exists(vector_store_path):
                # 기존 벡터 스토어 로드
                self.vector_store = FAISS.load_local(vector_store_path, self.embeddings)
                print("✅ 기존 벡터 스토어 로드 완료")
            else:
                # 새 벡터 스토어 생성
                self._create_initial_knowledge_base()
                
        except Exception as e:
            logger.warning(f"벡터 스토어 로드 실패: {e}")
            self._create_initial_knowledge_base()
    
    def _create_initial_knowledge_base(self):
        """초기 지식 베이스 생성"""
        try:
            # 기본 지식 문서들 로드
            documents = []
            
            # 프로젝트 관련 문서들 로드
            documents.extend(self._load_project_documents())
            
            # 일반적인 지식 문서들 로드
            documents.extend(self._load_general_knowledge())
            
            if documents:
                # 텍스트 분할
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200,
                    separators=["\n\n", "\n", " ", ""]
                )
                
                split_documents = text_splitter.split_documents(documents)
                
                # 벡터 스토어 생성
                if split_documents:
                    self.vector_store = FAISS.from_documents(split_documents, self.embeddings)
                    
                    # 벡터 스토어 저장
                    vector_store_path = os.path.join(self.knowledge_sources_dir, 'vector_store')
                    self.vector_store.save_local(vector_store_path)
                    
                    print(f"✅ 초기 지식 베이스 생성 완료: {len(split_documents)}개 문서")
            
        except Exception as e:
            logger.error(f"초기 지식 베이스 생성 실패: {e}")
    
    def _load_project_documents(self) -> List[Document]:
        """프로젝트 관련 문서 로드"""
        documents = []
        
        try:
            # README 파일들 로드
            readme_files = [
                '/Users/seon/AIOFAI_F/AI_of_AI/README.md',
                '/Users/seon/AIOFAI_F/AI_of_AI/LLM_VIDEO_SEARCH_IMPLEMENTATION_COMPLETE.md',
                '/Users/seon/AIOFAI_F/AI_of_AI/enhanced_video_search_proposal.md'
            ]
            
            for readme_path in readme_files:
                if os.path.exists(readme_path):
                    loader = TextLoader(readme_path, encoding='utf-8')
                    docs = loader.load()
                    for doc in docs:
                        doc.metadata['source_type'] = 'project_document'
                        doc.metadata['file_path'] = readme_path
                    documents.extend(docs)
            
            # 설정 파일들에서 정보 추출
            settings_files = [
                '/Users/seon/AIOFAI_F/AI_of_AI/chatbot_backend/chatbot_backend/settings.py',
                '/Users/seon/AIOFAI_F/AI_of_AI/frontend/package.json'
            ]
            
            for settings_path in settings_files:
                if os.path.exists(settings_path):
                    loader = TextLoader(settings_path, encoding='utf-8')
                    docs = loader.load()
                    for doc in docs:
                        doc.metadata['source_type'] = 'configuration'
                        doc.metadata['file_path'] = settings_path
                    documents.extend(docs)
            
        except Exception as e:
            logger.warning(f"프로젝트 문서 로드 실패: {e}")
        
        return documents
    
    def _load_general_knowledge(self) -> List[Document]:
        """일반적인 지식 문서 로드"""
        documents = []
        
        try:
            # 일반적인 기술 지식 추가
            general_knowledge = [
                {
                    'content': '''
                    AI 모델 비교 정보:
                    - GPT-4: OpenAI의 최신 모델, 창의적 글쓰기와 복잡한 추론에 뛰어남
                    - Claude-3.5-Sonnet: Anthropic의 모델, 분석적 사고와 사실 검증에 강함
                    - Mixtral-8x7B: Mistral의 모델, 빠른 응답과 효율성이 특징
                    ''',
                    'metadata': {'source_type': 'ai_knowledge', 'topic': 'ai_models'}
                },
                {
                    'content': '''
                    비디오 분석 기술:
                    - YOLO: 실시간 객체 감지 알고리즘
                    - OpenCV: 컴퓨터 비전 라이브러리
                    - TensorFlow/PyTorch: 딥러닝 프레임워크
                    - FFmpeg: 비디오 처리 도구
                    ''',
                    'metadata': {'source_type': 'tech_knowledge', 'topic': 'video_analysis'}
                },
                {
                    'content': '''
                    웹 개발 기술:
                    - Django: Python 웹 프레임워크
                    - React: JavaScript UI 라이브러리
                    - REST API: 웹 서비스 아키텍처
                    - PostgreSQL: 관계형 데이터베이스
                    ''',
                    'metadata': {'source_type': 'tech_knowledge', 'topic': 'web_development'}
                }
            ]
            
            for knowledge in general_knowledge:
                doc = Document(
                    page_content=knowledge['content'],
                    metadata=knowledge['metadata']
                )
                documents.append(doc)
            
        except Exception as e:
            logger.warning(f"일반 지식 로드 실패: {e}")
        
        return documents
    
    def _initialize_verification_chain(self):
        """검증 체인 초기화"""
        try:
            if self.vector_store and os.getenv('OPENAI_API_KEY'):
                # 검증용 LLM 초기화
                llm = OpenAI(temperature=0)
                
                # 검증 체인 생성
                self.retrieval_qa = RetrievalQA.from_chain_type(
                    llm=llm,
                    chain_type="stuff",
                    retriever=self.vector_store.as_retriever(
                        search_kwargs={"k": self.verification_config['max_retrieved_docs']}
                    ),
                    return_source_documents=True
                )
                
                print("✅ 검증 체인 초기화 완료")
            
        except Exception as e:
            logger.warning(f"검증 체인 초기화 실패: {e}")
    
    async def verify_ai_response(
        self, 
        ai_response: str, 
        query: str, 
        model_name: str = None
    ) -> VerificationResult:
        """AI 응답 검증"""
        try:
            print(f"🔍 AI 응답 검증 시작: {model_name or 'Unknown'}")
            
            # 1. 사실 정확성 검증
            factual_accuracy = await self._verify_factual_accuracy(ai_response, query)
            
            # 2. 일관성 검증
            consistency_score = await self._verify_consistency(ai_response, query)
            
            # 3. 소스 검증
            source_verification = await self._verify_against_sources(ai_response, query)
            
            # 4. 모순점 식별
            contradictions = await self._identify_contradictions(ai_response, query)
            
            # 5. 검증된 사실 추출
            verified_facts = await self._extract_verified_facts(ai_response, query)
            
            # 6. 누락 정보 식별
            missing_info = await self._identify_missing_information(ai_response, query)
            
            # 7. 전체 점수 계산
            overall_score = self._calculate_overall_score(
                factual_accuracy, consistency_score, source_verification
            )
            
            # 8. 신뢰도 레벨 결정
            confidence_level = self._determine_confidence_level(overall_score)
            
            result = VerificationResult(
                overall_score=overall_score,
                factual_accuracy=factual_accuracy,
                consistency_score=consistency_score,
                source_verification=source_verification,
                contradictions=contradictions,
                verified_facts=verified_facts,
                missing_information=missing_info,
                confidence_level=confidence_level
            )
            
            print(f"✅ 검증 완료: 신뢰도 {confidence_level} ({overall_score:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"AI 응답 검증 실패: {e}")
            return self._create_fallback_verification_result()
    
    async def _verify_factual_accuracy(self, response: str, query: str) -> float:
        """사실 정확성 검증"""
        try:
            if not self.vector_store:
                return 0.5  # 기본값
            
            # 응답에서 사실적 정보 추출
            factual_claims = self._extract_factual_claims(response)
            
            if not factual_claims:
                return 0.5
            
            verified_claims = 0
            
            for claim in factual_claims:
                # 벡터 검색으로 관련 정보 찾기
                similar_docs = self.vector_store.similarity_search(claim, k=3)
                
                # 유사도 검사
                for doc in similar_docs:
                    if self._check_claim_accuracy(claim, doc.page_content):
                        verified_claims += 1
                        break
            
            accuracy = verified_claims / len(factual_claims)
            return min(accuracy, 1.0)
            
        except Exception as e:
            logger.warning(f"사실 정확성 검증 실패: {e}")
            return 0.5
    
    def _extract_factual_claims(self, text: str) -> List[str]:
        """텍스트에서 사실적 주장 추출"""
        claims = []
        
        # 숫자나 날짜가 포함된 문장들
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20:  # 너무 짧은 문장 제외
                # 숫자, 날짜, 구체적 정보가 포함된 문장
                if (re.search(r'\d+', sentence) or 
                    re.search(r'\d{4}', sentence) or
                    re.search(r'(년|월|일|시간|분|초)', sentence)):
                    claims.append(sentence)
        
        return claims[:5]  # 최대 5개
    
    def _check_claim_accuracy(self, claim: str, source_text: str) -> float:
        """주장의 정확성 검사"""
        try:
            # 간단한 텍스트 유사도 계산
            claim_words = set(claim.lower().split())
            source_words = set(source_text.lower().split())
            
            intersection = len(claim_words.intersection(source_words))
            union = len(claim_words.union(source_words))
            
            if union == 0:
                return 0.0
            
            similarity = intersection / union
            
            # 유사도가 높으면 정확하다고 판단
            return 1.0 if similarity > 0.5 else 0.0
            
        except Exception:
            return 0.0
    
    async def _verify_consistency(self, response: str, query: str) -> float:
        """일관성 검증"""
        try:
            # 응답 내부 일관성 검사
            internal_consistency = self._check_internal_consistency(response)
            
            # 질문과의 일관성 검사
            query_consistency = self._check_query_consistency(response, query)
            
            # 가중 평균
            consistency = (internal_consistency * 0.6 + query_consistency * 0.4)
            
            return min(consistency, 1.0)
            
        except Exception as e:
            logger.warning(f"일관성 검증 실패: {e}")
            return 0.5
    
    def _check_internal_consistency(self, text: str) -> float:
        """내부 일관성 검사"""
        try:
            # 모순적인 표현 찾기
            contradictions = [
                ('많다', '적다'), ('크다', '작다'), ('높다', '낮다'),
                ('좋다', '나쁘다'), ('가능하다', '불가능하다')
            ]
            
            contradiction_count = 0
            total_pairs = len(contradictions)
            
            text_lower = text.lower()
            
            for pos, neg in contradictions:
                if pos in text_lower and neg in text_lower:
                    contradiction_count += 1
            
            # 모순이 적을수록 일관성 높음
            consistency = 1.0 - (contradiction_count / total_pairs)
            return max(consistency, 0.0)
            
        except Exception:
            return 0.5
    
    def _check_query_consistency(self, response: str, query: str) -> float:
        """질문과의 일관성 검사"""
        try:
            # 질문의 키워드가 응답에 포함되는지 확인
            query_words = set(query.lower().split())
            response_words = set(response.lower().split())
            
            keyword_overlap = len(query_words.intersection(response_words))
            total_keywords = len(query_words)
            
            if total_keywords == 0:
                return 0.5
            
            relevance = keyword_overlap / total_keywords
            return min(relevance, 1.0)
            
        except Exception:
            return 0.5
    
    async def _verify_against_sources(self, response: str, query: str) -> float:
        """소스 대비 검증"""
        try:
            if not self.vector_store:
                return 0.5
            
            # 관련 소스 문서 검색
            similar_docs = self.vector_store.similarity_search(query, k=3)
            
            if not similar_docs:
                return 0.5
            
            # 응답과 소스 문서들의 유사도 계산
            total_similarity = 0
            valid_sources = 0
            
            for doc in similar_docs:
                similarity = self._calculate_text_similarity(response, doc.page_content)
                total_similarity += similarity
                valid_sources += 1
            
            if valid_sources == 0:
                return 0.5
            
            avg_similarity = total_similarity / valid_sources
            return min(avg_similarity, 1.0)
            
        except Exception as e:
            logger.warning(f"소스 검증 실패: {e}")
            return 0.5
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """텍스트 유사도 계산"""
        try:
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            if union == 0:
                return 0.0
            
            return intersection / union
            
        except Exception:
            return 0.0
    
    async def _identify_contradictions(self, response: str, query: str) -> List[str]:
        """모순점 식별"""
        contradictions = []
        
        try:
            # 일반적인 모순 패턴
            contradiction_patterns = [
                (r'(\d+)개', r'(\d+)개'),  # 숫자 불일치
                (r'(정확히|정확한)', r'(대략|약|추정)'),  # 정확성 vs 추정
                (r'(모든|전체)', r'(일부|일부분)'),  # 전체 vs 부분
            ]
            
            for pattern1, pattern2 in contradiction_patterns:
                matches1 = re.findall(pattern1, response)
                matches2 = re.findall(pattern2, response)
                
                if matches1 and matches2:
                    contradictions.append(f"숫자나 표현의 불일치가 발견되었습니다.")
            
            # 구체적인 모순 검사
            if '가능하다' in response and '불가능하다' in response:
                contradictions.append("가능성에 대한 모순된 표현이 있습니다.")
            
            if '많다' in response and '적다' in response:
                contradictions.append("양에 대한 모순된 표현이 있습니다.")
            
        except Exception as e:
            logger.warning(f"모순점 식별 실패: {e}")
        
        return contradictions
    
    async def _extract_verified_facts(self, response: str, query: str) -> List[str]:
        """검증된 사실 추출"""
        verified_facts = []
        
        try:
            if not self.vector_store:
                return verified_facts
            
            # 응답에서 구체적인 사실들 추출
            factual_sentences = self._extract_factual_claims(response)
            
            for fact in factual_sentences:
                # 벡터 검색으로 검증
                similar_docs = self.vector_store.similarity_search(fact, k=2)
                
                for doc in similar_docs:
                    if self._check_claim_accuracy(fact, doc.page_content) > 0.7:
                        verified_facts.append(fact)
                        break
            
        except Exception as e:
            logger.warning(f"검증된 사실 추출 실패: {e}")
        
        return verified_facts
    
    async def _identify_missing_information(self, response: str, query: str) -> List[str]:
        """누락 정보 식별"""
        missing_info = []
        
        try:
            if not self.vector_store:
                return missing_info
            
            # 관련 소스에서 중요한 정보 추출
            relevant_docs = self.vector_store.similarity_search(query, k=3)
            
            for doc in relevant_docs:
                # 소스에 있지만 응답에 없는 정보 찾기
                source_keywords = set(doc.page_content.lower().split())
                response_keywords = set(response.lower().split())
                
                missing_keywords = source_keywords - response_keywords
                
                # 중요한 키워드가 누락되었는지 확인
                important_keywords = [
                    '데이터', '분석', '결과', '통계', '비율', '증가', '감소',
                    '개선', '문제', '해결', '방법', '기술', '알고리즘'
                ]
                
                for keyword in important_keywords:
                    if keyword in missing_keywords and keyword in doc.page_content.lower():
                        missing_info.append(f"'{keyword}' 관련 정보가 누락되었습니다.")
            
        except Exception as e:
            logger.warning(f"누락 정보 식별 실패: {e}")
        
        return missing_info[:3]  # 최대 3개
    
    def _calculate_overall_score(
        self, 
        factual_accuracy: float, 
        consistency: float, 
        source_verification: float
    ) -> float:
        """전체 점수 계산"""
        config = self.verification_config
        
        overall_score = (
            factual_accuracy * config['factual_accuracy_weight'] +
            consistency * config['consistency_weight'] +
            source_verification * config['source_verification_weight']
        )
        
        return min(overall_score, 1.0)
    
    def _determine_confidence_level(self, score: float) -> str:
        """신뢰도 레벨 결정"""
        if score >= 0.8:
            return 'high'
        elif score >= 0.6:
            return 'medium'
        elif score >= 0.4:
            return 'low'
        else:
            return 'very_low'
    
    def _create_fallback_verification_result(self) -> VerificationResult:
        """폴백 검증 결과 생성"""
        return VerificationResult(
            overall_score=0.5,
            factual_accuracy=0.5,
            consistency_score=0.5,
            source_verification=0.5,
            contradictions=[],
            verified_facts=[],
            missing_information=[],
            confidence_level='medium'
        )
    
    async def add_knowledge_source(
        self, 
        content: str, 
        source_type: str, 
        metadata: Dict[str, Any] = None
    ) -> bool:
        """새로운 지식 소스 추가"""
        try:
            if not self.vector_store or not self.embeddings:
                return False
            
            # 새 문서 생성
            doc = Document(
                page_content=content,
                metadata={
                    'source_type': source_type,
                    'added_at': datetime.now().isoformat(),
                    **(metadata or {})
                }
            )
            
            # 벡터 스토어에 추가
            self.vector_store.add_documents([doc])
            
            # 벡터 스토어 저장
            vector_store_path = os.path.join(self.knowledge_sources_dir, 'vector_store')
            self.vector_store.save_local(vector_store_path)
            
            print(f"✅ 지식 소스 추가 완료: {source_type}")
            return True
            
        except Exception as e:
            logger.error(f"지식 소스 추가 실패: {e}")
            return False
    
    def get_verification_summary(self, verification_result: VerificationResult) -> str:
        """검증 결과 요약 생성"""
        summary_parts = []
        
        # 전체 신뢰도
        summary_parts.append(f"## 🔍 신뢰도 검증 결과")
        summary_parts.append(f"- 전체 신뢰도: {verification_result.overall_score:.1%} ({verification_result.confidence_level})")
        
        # 세부 점수
        summary_parts.append(f"- 사실 정확성: {verification_result.factual_accuracy:.1%}")
        summary_parts.append(f"- 일관성: {verification_result.consistency_score:.1%}")
        summary_parts.append(f"- 소스 검증: {verification_result.source_verification:.1%}")
        
        # 검증된 사실
        if verification_result.verified_facts:
            summary_parts.append(f"\n## ✅ 검증된 사실")
            for fact in verification_result.verified_facts[:3]:
                summary_parts.append(f"- {fact}")
        
        # 모순점
        if verification_result.contradictions:
            summary_parts.append(f"\n## ⚠️ 모순점")
            for contradiction in verification_result.contradictions:
                summary_parts.append(f"- {contradiction}")
        
        # 누락 정보
        if verification_result.missing_information:
            summary_parts.append(f"\n## 📝 누락된 정보")
            for missing in verification_result.missing_information:
                summary_parts.append(f"- {missing}")
        
        return "\n".join(summary_parts)

# 전역 인스턴스
rag_verification_system = RAGVerificationSystem()
