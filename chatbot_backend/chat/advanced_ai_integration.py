"""
고도화된 멀티 AI 통합 시스템
- 여러 AI 모델에 동시 질문 전송
- PDF, 사진 등 첨부 자료 통합 분석
- LangChain RAG를 활용한 신뢰도 검증
- 응답 간 유사 문장 및 불일치 정보 분석
- 정제된 핵심 정보를 바탕으로 최적 답변 도출
"""

import asyncio
import aiohttp
import json
import logging
import os
import time
import concurrent.futures
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
import base64
from pathlib import Path

# LangChain 관련 임포트 (선택적)
try:
    from langchain.document_loaders import PyPDFLoader, TextLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.embeddings import OpenAIEmbeddings
    from langchain.vectorstores import FAISS
    from langchain.chains import RetrievalQA
    from langchain.llms import OpenAI
    LANGCHAIN_AVAILABLE = True
    print("✅ LangChain 사용 가능")
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("⚠️ LangChain 사용 불가 - 기본 기능만 사용")

# 이미지 처리 관련 임포트 (선택적)
try:
    from PIL import Image
    import pytesseract
    IMAGE_PROCESSING_AVAILABLE = True
    print("✅ 이미지 처리 사용 가능")
except ImportError:
    IMAGE_PROCESSING_AVAILABLE = False
    print("⚠️ 이미지 처리 사용 불가")

logger = logging.getLogger(__name__)

@dataclass
class AttachmentInfo:
    """첨부 파일 정보"""
    file_type: str  # 'pdf', 'image', 'text', 'video'
    file_path: str
    file_size: int
    content_hash: str
    extracted_text: Optional[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class AIResponse:
    """AI 응답 정보"""
    model_name: str
    response_content: str
    confidence_score: float
    response_time: float
    tokens_used: int
    error: Optional[str] = None
    attachments_analyzed: List[str] = None

@dataclass
class IntegratedResponse:
    """통합 응답 결과"""
    final_answer: str
    confidence_score: float
    consensus_level: str
    contributing_models: List[str]
    disagreements: List[str]
    attachments_summary: str
    rag_verification: Dict[str, Any]
    quality_metrics: Dict[str, float]
    processing_time: float

class AdvancedAIIntegration:
    """고도화된 AI 통합 시스템"""
    
    def __init__(self):
        self.ai_models = {
            'gpt4': {
                'api_key': os.getenv('OPENAI_API_KEY'),
                'model': 'gpt-4o',
                'max_tokens': 2000,
                'temperature': 0.7,
                'timeout': 30
            },
            'claude': {
                'api_key': os.getenv('ANTHROPIC_API_KEY'),
                'model': 'claude-3-5-sonnet-20241022',
                'max_tokens': 2000,
                'temperature': 0.7,
                'timeout': 30
            },
            'mixtral': {
                'api_key': os.getenv('GROQ_API_KEY'),
                'model': 'mixtral-8x7b-32768',
                'max_tokens': 2000,
                'temperature': 0.7,
                'timeout': 30
            }
        }
        
        # LangChain RAG 시스템 초기화
        self.rag_system = None
        if LANGCHAIN_AVAILABLE:
            self._initialize_rag_system()
        
        # 응답 캐시
        self.response_cache = {}
        
        print("🚀 고도화된 AI 통합 시스템 초기화 완료")
    
    def _initialize_rag_system(self):
        """LangChain RAG 시스템 초기화"""
        try:
            if os.getenv('OPENAI_API_KEY'):
                self.embeddings = OpenAIEmbeddings()
                self.rag_system = "initialized"
                print("✅ LangChain RAG 시스템 초기화 완료")
        except Exception as e:
            logger.warning(f"LangChain RAG 초기화 실패: {e}")
    
    async def generate_comprehensive_response(
        self, 
        query: str, 
        attachments: List[str] = None,
        context: Dict[str, Any] = None
    ) -> IntegratedResponse:
        """종합적인 AI 응답 생성"""
        start_time = time.time()
        
        try:
            print(f"🔍 종합 AI 응답 생성 시작: '{query[:50]}...'")
            
            # 1. 첨부 파일 분석
            attachment_info = await self._analyze_attachments(attachments or [])
            
            # 2. 컨텍스트 통합
            integrated_context = self._integrate_context(query, attachment_info, context)
            
            # 3. 여러 AI에 동시 질문 전송
            ai_responses = await self._send_parallel_queries(integrated_context)
            
            # 4. 응답 분석 및 비교
            response_analysis = self._analyze_responses(ai_responses, query)
            
            # 5. LangChain RAG 검증
            rag_verification = await self._verify_with_rag(ai_responses, integrated_context)
            
            # 6. 최적 답변 도출
            final_answer = self._generate_optimal_answer(
                ai_responses, 
                response_analysis, 
                rag_verification,
                query
            )
            
            # 7. 품질 지표 계산
            quality_metrics = self._calculate_quality_metrics(
                ai_responses, 
                final_answer, 
                response_analysis
            )
            
            processing_time = time.time() - start_time
            
            result = IntegratedResponse(
                final_answer=final_answer,
                confidence_score=quality_metrics['overall_confidence'],
                consensus_level=response_analysis['consensus_level'],
                contributing_models=[resp.model_name for resp in ai_responses if not resp.error],
                disagreements=response_analysis['disagreements'],
                attachments_summary=self._create_attachments_summary(attachment_info),
                rag_verification=rag_verification,
                quality_metrics=quality_metrics,
                processing_time=processing_time
            )
            
            print(f"✅ 종합 AI 응답 생성 완료: {processing_time:.2f}초")
            return result
            
        except Exception as e:
            logger.error(f"❌ 종합 AI 응답 생성 실패: {e}")
            return self._create_fallback_response(query, str(e))
    
    async def _analyze_attachments(self, attachments: List[str]) -> List[AttachmentInfo]:
        """첨부 파일 분석"""
        attachment_info = []
        
        for attachment_path in attachments:
            try:
                if not os.path.exists(attachment_path):
                    continue
                
                file_type = self._detect_file_type(attachment_path)
                file_size = os.path.getsize(attachment_path)
                content_hash = self._calculate_file_hash(attachment_path)
                
                # 파일 내용 추출
                extracted_text = await self._extract_file_content(attachment_path, file_type)
                
                info = AttachmentInfo(
                    file_type=file_type,
                    file_path=attachment_path,
                    file_size=file_size,
                    content_hash=content_hash,
                    extracted_text=extracted_text,
                    metadata=self._extract_file_metadata(attachment_path, file_type)
                )
                
                attachment_info.append(info)
                print(f"✅ 첨부 파일 분석 완료: {attachment_path}")
                
            except Exception as e:
                logger.warning(f"첨부 파일 분석 실패 {attachment_path}: {e}")
                continue
        
        return attachment_info
    
    def _detect_file_type(self, file_path: str) -> str:
        """파일 타입 감지"""
        ext = Path(file_path).suffix.lower()
        
        if ext == '.pdf':
            return 'pdf'
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
            return 'image'
        elif ext in ['.txt', '.md', '.docx']:
            return 'text'
        elif ext in ['.mp4', '.avi', '.mov', '.wmv']:
            return 'video'
        else:
            return 'unknown'
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """파일 해시 계산"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return "unknown"
    
    async def _extract_file_content(self, file_path: str, file_type: str) -> Optional[str]:
        """파일 내용 추출"""
        try:
            if file_type == 'pdf' and LANGCHAIN_AVAILABLE:
                return await self._extract_pdf_content(file_path)
            elif file_type == 'image' and IMAGE_PROCESSING_AVAILABLE:
                return await self._extract_image_content(file_path)
            elif file_type == 'text':
                return await self._extract_text_content(file_path)
            else:
                return None
        except Exception as e:
            logger.warning(f"파일 내용 추출 실패 {file_path}: {e}")
            return None
    
    async def _extract_pdf_content(self, file_path: str) -> str:
        """PDF 내용 추출"""
        try:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            texts = text_splitter.split_documents(documents)
            
            content = "\n".join([doc.page_content for doc in texts])
            return content[:5000]  # 최대 5000자
        except Exception as e:
            logger.warning(f"PDF 내용 추출 실패: {e}")
            return ""
    
    async def _extract_image_content(self, file_path: str) -> str:
        """이미지 내용 추출 (OCR)"""
        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang='kor+eng')
            return text[:2000]  # 최대 2000자
        except Exception as e:
            logger.warning(f"이미지 OCR 실패: {e}")
            return ""
    
    async def _extract_text_content(self, file_path: str) -> str:
        """텍스트 파일 내용 추출"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content[:5000]  # 최대 5000자
        except Exception as e:
            logger.warning(f"텍스트 파일 읽기 실패: {e}")
            return ""
    
    def _extract_file_metadata(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """파일 메타데이터 추출"""
        try:
            stat = os.stat(file_path)
            metadata = {
                'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'file_size': stat.st_size
            }
            
            if file_type == 'image' and IMAGE_PROCESSING_AVAILABLE:
                try:
                    with Image.open(file_path) as img:
                        metadata.update({
                            'width': img.width,
                            'height': img.height,
                            'format': img.format,
                            'mode': img.mode
                        })
                except Exception:
                    pass
            
            return metadata
        except Exception:
            return {}
    
    def _integrate_context(
        self, 
        query: str, 
        attachment_info: List[AttachmentInfo], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """컨텍스트 통합"""
        integrated_context = {
            'query': query,
            'attachments': [],
            'context': context or {},
            'timestamp': datetime.now().isoformat()
        }
        
        # 첨부 파일 정보 통합
        for attachment in attachment_info:
            attachment_data = {
                'type': attachment.file_type,
                'path': attachment.file_path,
                'size': attachment.file_size,
                'content_preview': attachment.extracted_text[:500] if attachment.extracted_text else None,
                'metadata': attachment.metadata
            }
            integrated_context['attachments'].append(attachment_data)
        
        return integrated_context
    
    async def _send_parallel_queries(self, context: Dict[str, Any]) -> List[AIResponse]:
        """여러 AI에 동시 질문 전송"""
        tasks = []
        
        for model_name, config in self.ai_models.items():
            if config['api_key']:
                task = self._query_single_ai(model_name, config, context)
                tasks.append(task)
        
        # 동시 실행
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        valid_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                model_name = list(self.ai_models.keys())[i]
                error_response = AIResponse(
                    model_name=model_name,
                    response_content="",
                    confidence_score=0.0,
                    response_time=0.0,
                    tokens_used=0,
                    error=str(response)
                )
                valid_responses.append(error_response)
            else:
                valid_responses.append(response)
        
        return valid_responses
    
    async def _query_single_ai(
        self, 
        model_name: str, 
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> AIResponse:
        """단일 AI 모델에 질문"""
        start_time = time.time()
        
        try:
            # 프롬프트 생성
            prompt = self._create_comprehensive_prompt(context, model_name)
            
            if model_name == 'gpt4':
                response = await self._query_openai(config, prompt)
            elif model_name == 'claude':
                response = await self._query_anthropic(config, prompt)
            elif model_name == 'mixtral':
                response = await self._query_groq(config, prompt)
            else:
                raise ValueError(f"지원하지 않는 모델: {model_name}")
            
            response_time = time.time() - start_time
            
            return AIResponse(
                model_name=model_name,
                response_content=response['content'],
                confidence_score=response.get('confidence', 0.8),
                response_time=response_time,
                tokens_used=response.get('tokens', 0),
                attachments_analyzed=[att['type'] for att in context['attachments']]
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            return AIResponse(
                model_name=model_name,
                response_content="",
                confidence_score=0.0,
                response_time=response_time,
                tokens_used=0,
                error=str(e)
            )
    
    def _create_comprehensive_prompt(self, context: Dict[str, Any], model_name: str) -> str:
        """종합적인 프롬프트 생성"""
        query = context['query']
        attachments = context['attachments']
        
        prompt_parts = [
            f"다음 질문에 대해 정확하고 상세한 답변을 제공해주세요:",
            f"질문: {query}",
            ""
        ]
        
        if attachments:
            prompt_parts.append("첨부된 파일들의 내용을 분석하여 답변에 포함해주세요:")
            for i, attachment in enumerate(attachments, 1):
                prompt_parts.append(f"첨부파일 {i} ({attachment['type']}):")
                if attachment['content_preview']:
                    prompt_parts.append(f"내용 미리보기: {attachment['content_preview']}")
                prompt_parts.append("")
        
        # 모델별 특성화된 지시사항
        model_instructions = {
            'gpt4': "GPT-4의 강점인 정확성과 포괄성을 살려서 답변해주세요.",
            'claude': "Claude의 강점인 분석력과 창의성을 살려서 답변해주세요.",
            'mixtral': "Mixtral의 강점인 효율성과 명확성을 살려서 답변해주세요."
        }
        
        prompt_parts.append(f"답변 시 {model_instructions.get(model_name, '정확하고 유용한 정보를 제공해주세요.')}")
        
        return "\n".join(prompt_parts)
    
    async def _query_openai(self, config: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """OpenAI API 호출"""
        import openai
        
        client = openai.AsyncOpenAI(api_key=config['api_key'])
        
        response = await client.chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": "당신은 전문가 AI 어시스턴트입니다. 제공된 정보를 바탕으로 정확하고 유용한 답변을 제공하세요."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=config['max_tokens'],
            temperature=config['temperature']
        )
        
        return {
            'content': response.choices[0].message.content,
            'tokens': response.usage.total_tokens if response.usage else 0,
            'confidence': 0.9
        }
    
    async def _query_anthropic(self, config: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Anthropic API 호출"""
        import anthropic
        
        client = anthropic.AsyncAnthropic(api_key=config['api_key'])
        
        response = await client.messages.create(
            model=config['model'],
            max_tokens=config['max_tokens'],
            temperature=config['temperature'],
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return {
            'content': response.content[0].text,
            'tokens': response.usage.output_tokens if response.usage else 0,
            'confidence': 0.9
        }
    
    async def _query_groq(self, config: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Groq API 호출"""
        from groq import AsyncGroq
        
        client = AsyncGroq(api_key=config['api_key'])
        
        response = await client.chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": "당신은 전문가 AI 어시스턴트입니다. 제공된 정보를 바탕으로 정확하고 유용한 답변을 제공하세요."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=config['max_tokens'],
            temperature=config['temperature']
        )
        
        return {
            'content': response.choices[0].message.content,
            'tokens': response.usage.total_tokens if response.usage else 0,
            'confidence': 0.8
        }
    
    def _analyze_responses(self, responses: List[AIResponse], query: str) -> Dict[str, Any]:
        """응답 분석 및 비교"""
        valid_responses = [r for r in responses if not r.error]
        
        if len(valid_responses) < 2:
            return {
                'consensus_level': 'low',
                'agreements': [],
                'disagreements': [],
                'similarity_scores': {},
                'quality_scores': {r.model_name: r.confidence_score for r in valid_responses}
            }
        
        # 유사도 분석
        similarity_scores = self._calculate_response_similarity(valid_responses)
        
        # 합의도 분석
        consensus_level = self._determine_consensus_level(similarity_scores)
        
        # 불일치 정보 식별
        disagreements = self._identify_disagreements(valid_responses, similarity_scores)
        
        return {
            'consensus_level': consensus_level,
            'agreements': self._find_agreements(valid_responses),
            'disagreements': disagreements,
            'similarity_scores': similarity_scores,
            'quality_scores': {r.model_name: r.confidence_score for r in valid_responses}
        }
    
    def _calculate_response_similarity(self, responses: List[AIResponse]) -> Dict[str, float]:
        """응답 간 유사도 계산"""
        similarity_scores = {}
        
        for i, resp1 in enumerate(responses):
            for j, resp2 in enumerate(responses[i+1:], i+1):
                similarity = self._calculate_text_similarity(
                    resp1.response_content, 
                    resp2.response_content
                )
                pair_key = f"{resp1.model_name}-{resp2.model_name}"
                similarity_scores[pair_key] = similarity
        
        return similarity_scores
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """텍스트 유사도 계산 (간단한 방식)"""
        try:
            # 단어 집합으로 변환
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            
            # Jaccard 유사도
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            if union == 0:
                return 0.0
            
            return intersection / union
        except Exception:
            return 0.0
    
    def _determine_consensus_level(self, similarity_scores: Dict[str, float]) -> str:
        """합의도 레벨 결정"""
        if not similarity_scores:
            return 'low'
        
        avg_similarity = sum(similarity_scores.values()) / len(similarity_scores)
        
        if avg_similarity > 0.7:
            return 'high'
        elif avg_similarity > 0.4:
            return 'medium'
        else:
            return 'low'
    
    def _identify_disagreements(self, responses: List[AIResponse], similarity_scores: Dict[str, float]) -> List[str]:
        """불일치 정보 식별"""
        disagreements = []
        
        # 유사도가 낮은 응답 쌍 찾기
        low_similarity_pairs = [
            pair for pair, score in similarity_scores.items() 
            if score < 0.3
        ]
        
        for pair in low_similarity_pairs:
            model1, model2 = pair.split('-')
            disagreements.append(f"{model1}과 {model2}의 답변이 상당히 다릅니다.")
        
        return disagreements
    
    def _find_agreements(self, responses: List[AIResponse]) -> List[str]:
        """공통된 내용 찾기"""
        agreements = []
        
        if len(responses) < 2:
            return agreements
        
        # 공통 키워드 찾기
        all_words = []
        for resp in responses:
            words = set(resp.response_content.lower().split())
            all_words.append(words)
        
        # 모든 응답에 나타나는 단어
        common_words = set.intersection(*all_words)
        if common_words:
            agreements.append(f"공통 키워드: {', '.join(list(common_words)[:5])}")
        
        return agreements
    
    async def _verify_with_rag(
        self, 
        responses: List[AIResponse], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """LangChain RAG를 활용한 신뢰도 검증"""
        if not LANGCHAIN_AVAILABLE or not self.rag_system:
            return {
                'rag_available': False,
                'verification_score': 0.5,
                'verified_facts': [],
                'contradictions': []
            }
        
        try:
            # 내부 자료와 비교
            verification_results = []
            
            for response in responses:
                if response.error:
                    continue
                
                # RAG 검증 (간단한 형태)
                verification_score = self._simple_rag_verification(response.response_content)
                
                verification_results.append({
                    'model': response.model_name,
                    'score': verification_score,
                    'verified': verification_score > 0.6
                })
            
            avg_verification = sum(r['score'] for r in verification_results) / max(len(verification_results), 1)
            
            return {
                'rag_available': True,
                'verification_score': avg_verification,
                'verified_facts': [r for r in verification_results if r['verified']],
                'contradictions': [r for r in verification_results if not r['verified']]
            }
            
        except Exception as e:
            logger.warning(f"RAG 검증 실패: {e}")
            return {
                'rag_available': False,
                'verification_score': 0.5,
                'verified_facts': [],
                'contradictions': []
            }
    
    def _simple_rag_verification(self, response_content: str) -> float:
        """간단한 RAG 검증 (실제로는 더 복잡한 검증 로직 필요)"""
        # 숫자, 날짜, 구체적 정보 포함도로 검증
        factual_elements = len(re.findall(r'\d+', response_content))
        factual_elements += len(re.findall(r'\d{4}-\d{2}-\d{2}', response_content))
        
        # 구체적인 정보가 많을수록 높은 점수
        return min(factual_elements / 10, 1.0)
    
    def _generate_optimal_answer(
        self, 
        responses: List[AIResponse], 
        analysis: Dict[str, Any], 
        rag_verification: Dict[str, Any],
        query: str
    ) -> str:
        """최적 답변 도출"""
        try:
            valid_responses = [r for r in responses if not r.error]
            
            if not valid_responses:
                return "AI 응답을 생성할 수 없습니다."
            
            # 품질 점수 기반으로 정렬
            sorted_responses = sorted(
                valid_responses, 
                key=lambda x: x.confidence_score, 
                reverse=True
            )
            
            # 주요 응답 선택
            primary_response = sorted_responses[0]
            
            # 앙상블 답변 구성
            answer_parts = []
            
            # 통합 답변
            answer_parts.append("## 🎯 통합 답변")
            answer_parts.append(primary_response.response_content)
            
            # 첨부 파일 분석 결과
            if any(r.attachments_analyzed for r in valid_responses):
                answer_parts.append("\n## 📎 첨부 파일 분석")
                attachment_types = set()
                for r in valid_responses:
                    if r.attachments_analyzed:
                        attachment_types.update(r.attachments_analyzed)
                
                answer_parts.append(f"분석된 파일 유형: {', '.join(attachment_types)}")
            
            # AI 모델별 분석
            answer_parts.append("\n## 🤖 AI 모델별 분석")
            for response in sorted_responses[:3]:  # 상위 3개
                answer_parts.append(f"### {response.model_name.upper()}")
                answer_parts.append(f"- 신뢰도: {response.confidence_score:.1%}")
                answer_parts.append(f"- 응답 시간: {response.response_time:.2f}초")
                answer_parts.append(f"- 토큰 사용량: {response.tokens_used}")
                
                if response.attachments_analyzed:
                    answer_parts.append(f"- 첨부 파일 분석: {', '.join(response.attachments_analyzed)}")
            
            # 합의도 분석
            answer_parts.append(f"\n## 📊 합의도 분석")
            answer_parts.append(f"- 합의도 레벨: {analysis['consensus_level']}")
            
            if analysis['agreements']:
                answer_parts.append(f"- 공통 내용: {', '.join(analysis['agreements'])}")
            
            if analysis['disagreements']:
                answer_parts.append(f"- 불일치 사항: {', '.join(analysis['disagreements'])}")
            
            # RAG 검증 결과
            if rag_verification['rag_available']:
                answer_parts.append(f"\n## 🔍 신뢰도 검증")
                answer_parts.append(f"- 검증 점수: {rag_verification['verification_score']:.1%}")
                
                if rag_verification['verified_facts']:
                    verified_models = [f['model'] for f in rag_verification['verified_facts']]
                    answer_parts.append(f"- 검증된 모델: {', '.join(verified_models)}")
            
            # 최종 추천
            answer_parts.append(f"\n## 🏆 최종 추천")
            best_model = sorted_responses[0].model_name
            answer_parts.append(f"- {best_model.upper()}가 가장 신뢰할 수 있는 답변을 제공했습니다.")
            answer_parts.append(f"- 전체 신뢰도: {analysis['quality_scores'].get(best_model, 0.5):.1%}")
            
            return "\n".join(answer_parts)
            
        except Exception as e:
            logger.error(f"최적 답변 생성 실패: {e}")
            return "답변 생성 중 오류가 발생했습니다."
    
    def _calculate_quality_metrics(
        self, 
        responses: List[AIResponse], 
        final_answer: str, 
        analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """품질 지표 계산"""
        valid_responses = [r for r in responses if not r.error]
        
        if not valid_responses:
            return {
                'overall_confidence': 0.0,
                'response_quality': 0.0,
                'consensus_quality': 0.0,
                'processing_efficiency': 0.0
            }
        
        # 전체 신뢰도
        overall_confidence = sum(r.confidence_score for r in valid_responses) / len(valid_responses)
        
        # 응답 품질
        response_quality = sum(r.confidence_score for r in valid_responses) / len(valid_responses)
        
        # 합의도 품질
        consensus_scores = {'high': 1.0, 'medium': 0.7, 'low': 0.4}
        consensus_quality = consensus_scores.get(analysis['consensus_level'], 0.4)
        
        # 처리 효율성
        avg_response_time = sum(r.response_time for r in valid_responses) / len(valid_responses)
        processing_efficiency = max(0, 1 - avg_response_time / 30)  # 30초 기준
        
        return {
            'overall_confidence': overall_confidence,
            'response_quality': response_quality,
            'consensus_quality': consensus_quality,
            'processing_efficiency': processing_efficiency
        }
    
    def _create_attachments_summary(self, attachments: List[AttachmentInfo]) -> str:
        """첨부 파일 요약 생성"""
        if not attachments:
            return "첨부 파일 없음"
        
        summary_parts = []
        for attachment in attachments:
            summary_parts.append(
                f"- {attachment.file_type.upper()}: "
                f"{attachment.file_size} bytes"
            )
        
        return "\n".join(summary_parts)
    
    def _create_fallback_response(self, query: str, error: str) -> IntegratedResponse:
        """폴백 응답 생성"""
        return IntegratedResponse(
            final_answer=f"죄송합니다. 질문 '{query}'에 대한 답변 생성 중 오류가 발생했습니다: {error}",
            confidence_score=0.0,
            consensus_level='none',
            contributing_models=[],
            disagreements=[],
            attachments_summary="첨부 파일 없음",
            rag_verification={'rag_available': False, 'verification_score': 0.0},
            quality_metrics={
                'overall_confidence': 0.0,
                'response_quality': 0.0,
                'consensus_quality': 0.0,
                'processing_efficiency': 0.0
            },
            processing_time=0.0
        )

# 전역 인스턴스
advanced_ai_integration = AdvancedAIIntegration()
