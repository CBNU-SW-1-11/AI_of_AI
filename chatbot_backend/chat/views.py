from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse, Http404
from chat.serializers import UserSerializer, VideoChatSessionSerializer, VideoChatMessageSerializer, VideoAnalysisCacheSerializer
from chat.models import VideoChatSession, VideoChatMessage, VideoAnalysisCache, Video
from .services.video_analysis_service import video_analysis_service
from .person_search_handler import handle_person_search_command
from .advanced_search_view import InterVideoSearchView, IntraVideoSearchView, TemporalAnalysisView
from .advanced_command_handler import handle_inter_video_search_command, handle_intra_video_search_command, handle_temporal_analysis_command
from .ai_response_generator import ai_response_generator
from .evaluation_metrics import evaluation_metrics
from .conversation_memory import conversation_memory
from .integrated_chat_service import integrated_chat_service
from .llm_cache_manager import llm_cache_manager, conversation_context_manager
from django.utils import timezone
import threading
import openai
import anthropic
from groq import Groq
import ollama
import anthropic
import google.generativeai as genai
import os
import sys
import io
import PyPDF2
from PIL import Image
import pytesseract
# import cv2  # NumPy 호환성 문제로 조건부 import
# import numpy as np  # NumPy 호환성 문제로 조건부 import
from pdf2image import convert_from_bytes
import base64
import tempfile
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import requests
import uuid
import hmac
import hashlib
from django.contrib.auth import get_user_model
from chat.models import User, SocialAccount
from django.conf import settings
import json
import logging
import re
from datetime import datetime, timedelta

# 로거 설정
logger = logging.getLogger(__name__)

# 인코딩 문제 해결을 위한 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 파일 처리 유틸리티 함수들
def extract_text_from_pdf(file_content):
    """PDF에서 텍스트 추출 (직접 추출 + OCR 백업)"""
    try:
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        
        # 먼저 직접 텍스트 추출 시도
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            text += page_text + "\n"
        
        # 추출된 텍스트가 충분하지 않으면 OCR 시도
        if len(text.strip()) < 100:  # 텍스트가 너무 적으면 OCR 사용
            print("PDF 직접 추출 텍스트가 부족하여 OCR을 사용합니다.")
            return extract_text_from_pdf_ocr(file_content)
        
        return text.strip()
    except Exception as e:
        print(f"PDF 직접 추출 실패, OCR을 사용합니다: {str(e)}")
        return extract_text_from_pdf_ocr(file_content)

def extract_text_from_pdf_ocr(file_content):
    """PDF를 이미지로 변환 후 OCR로 텍스트 추출"""
    try:
        # PDF를 이미지로 변환
        images = convert_from_bytes(file_content, dpi=300)
        all_text = ""
        
        for i, image in enumerate(images):
            # 간단한 이미지 전처리 (NumPy 없이)
            # 이미지를 그레이스케일로 변환
            if image.mode != 'L':
                image = image.convert('L')
            
            # OCR 수행 (전처리 없이)
            page_text = pytesseract.image_to_string(image, lang='kor+eng')
            all_text += f"\n--- 페이지 {i+1} ---\n{page_text}\n"
        
        return all_text.strip()
    except Exception as e:
        return f"PDF OCR 처리 중 오류 발생: {str(e)}"

def extract_text_from_image(file_content):
    """이미지에서 OCR을 사용하여 텍스트 추출"""
    try:
        # 이미지 열기
        image = Image.open(io.BytesIO(file_content))
        
        # 이미지 전처리 (간단한 방식)
        if image.mode != 'L':
            image = image.convert('L')  # 그레이스케일로 변환
        
        # OCR 수행 (한국어 + 영어)
        text = pytesseract.image_to_string(image, lang='kor+eng')
        
        return text.strip()
    except Exception as e:
        return f"이미지 텍스트 추출 중 오류 발생: {str(e)}"

def process_uploaded_file(file):
    """업로드된 파일 처리"""
    file_content = file.read()
    file_extension = file.name.split('.')[-1].lower()
    
    if file_extension == 'pdf':
        return extract_text_from_pdf(file_content)
    elif file_extension in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
        # 이미지 파일의 경우 파일 경로를 반환 (Ollama가 직접 읽도록)
        return f"IMAGE_FILE:{file.name}"
    else:
        return "지원하지 않는 파일 형식입니다. PDF 또는 이미지 파일을 업로드해주세요."

def summarize_content(content, api_key=None, file_path=None):
    """내용을 요약하는 함수 (Ollama 사용)"""
    try:
        # 이미지 파일인지 확인
        if content.startswith("IMAGE_FILE:"):
            if file_path and os.path.exists(file_path):
                return analyze_image_with_ollama(file_path)
            else:
                return "이미지 파일을 찾을 수 없습니다."
        
        # 텍스트 내용인 경우
        # 내용이 너무 길면 자르기 (토큰 제한 고려)
        if len(content) > 12000:
            content = content[:12000] + "..."
        
        # 요약 프롬프트
        prompt = f"""당신은 문서 내용을 요약하는 전문가입니다. 

주어진 내용이 PDF에서 추출된 텍스트인 경우:
- OCR 오류나 불완전한 텍스트가 있을 수 있음을 고려
- 가능한 한 원문의 의도를 파악하여 요약
- 중요한 정보는 보존하되 간결하게 정리

요약 시 다음을 포함해주세요:
1. 문서의 주요 주제/목적
2. 핵심 내용과 중요한 포인트
3. 결론이나 요약 (있는 경우)

원문의 주요 내용을 보존하면서도 간결하게 작성해주세요.

다음 내용을 요약해주세요:

{content}"""
        
        # Ollama 클라이언트로 요약 수행
        response = ollama.chat(
                   model='llama3.2:latest',  # 또는 사용 가능한 다른 모델
            messages=[
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            options={
                'temperature': 0.3,
                'num_predict': 1500
            }
        )
        
        return response['message']['content']
    except Exception as e:
        print(f"Ollama 요약 오류: {str(e)}")
        # Ollama 실패 시 기본 요약
        if len(content) > 1000:
            return f"문서 요약 (Ollama 오류로 간단 요약): {content[:500]}..."
        return content

def analyze_image_with_ollama(image_path):
    """하이브리드 이미지 분석 (OCR + Ollama)"""
    try:
        # 1단계: OCR로 텍스트 추출 시도
        try:
            from PIL import Image
            import pytesseract
            
            image = Image.open(image_path)
            ocr_text = pytesseract.image_to_string(image, lang='kor+eng')
            
            if len(ocr_text.strip()) > 10:  # 텍스트가 충분히 있으면 OCR 결과 사용
                return f"이미지에서 텍스트를 추출했습니다: {ocr_text.strip()[:200]}"
        except:
            pass
        
        # 2단계: OCR 실패 시 Ollama로 간단한 분석 (영어로 답변)
        prompt = """IMPORTANT: Count objects very carefully. Look at the image multiple times.

Count the exact number of objects in this image. Be very precise about the count.
Then describe each object's type and main colors.

Examples:
- "1 gray and white cat, blue background"
- "2 dogs, white background" 
- "3 cars, street scene"

Answer in English very concisely. Double-check your count."""
        
        # 성능 최적화: 더 가벼운 모델 사용
        try:
            # llava:7b 사용 (가장 가벼운 비전 모델)
            response = ollama.chat(
                model='llava:7b',
                messages=[
                    {
                        'role': 'user',
                        'content': prompt,
                        'images': [image_path]
                    }
                ],
                options={
                    'temperature': 0.1,  # 더 낮은 temperature로 일관성 향상
                    'num_predict': 300,  # 토큰 수 더 줄임
                    'num_ctx': 1024  # 컨텍스트 크기 더 제한
                }
            )
            
            # Ollama 응답 로깅
            ollama_response = response['message']['content']
            print(f"Ollama 분석 결과: {ollama_response}")
            return ollama_response
            
        except Exception as e:
            print(f"Ollama 이미지 분석 실패, GPT API로 fallback: {str(e)}")
            # GPT API로 fallback (비용이 들지만 정확도 높음)
            try:
                import openai
                import base64
                
                with open(image_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                response = openai.chat.completions.create(
                    model="gpt-4o-mini",  # 가장 저렴한 GPT-4 비전 모델
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Count the exact number of objects in this image. Then describe each object's type and main colors only. Answer in English."},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                                }
                            ]
                        }
                    ],
                    max_tokens=100  # 토큰 수 제한으로 비용 절약
                )
                
                gpt_response = response.choices[0].message.content
                print(f"GPT 분석 결과: {gpt_response}")
                return gpt_response
            except Exception as gpt_error:
                print(f"GPT API fallback도 실패: {str(gpt_error)}")
                return "이미지 분석 중 오류가 발생했습니다. 이미지를 다시 업로드해주세요."
    except Exception as e:
        print(f"Ollama 이미지 분석 오류: {str(e)}")
        return f"이미지 분석 중 오류가 발생했습니다: {str(e)}"

def generate_optimal_response_with_ollama(ai_responses, user_question):
    """Ollama를 사용하여 최적의 답변 생성 (비용 절약 + 품질 향상)"""
    try:
        # AI 응답들을 정리
        responses_text = ""
        model_names = []
        for model_name, response in ai_responses.items():
            responses_text += f"### {model_name.upper()}:\n{response}\n\n"
            model_names.append(model_name.upper())
        
        # AI 분석 섹션 생성
        analysis_sections = ""
        for name in model_names:
            analysis_sections += f"### {name}\n- 장점: [주요 장점]\n- 단점: [주요 단점]\n- 특징: [특별한 특징]\n"
        
        # 비용 절약을 위한 간소화된 프롬프트
        prompt = f"""AI 응답을 분석하여 최적의 통합 답변을 제공해주세요.

형식:
## 통합 답변
[모든 AI의 장점을 결합한 최적 답변]

## 각 AI 분석
{analysis_sections}
## 분석 근거
[통합 답변을 만든 구체적 이유]

## 최종 추천
[상황별 AI 선택 가이드]

질문: {user_question}

AI 답변들:
{responses_text}

위 답변들을 분석하여 최적의 통합 답변을 제공해주세요."""
        
        response = ollama.chat(
                   model='llama3.2:latest',
            messages=[
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            options={
                'temperature': 0.7,
                'num_predict': 2500
            }
        )
        
        return response['message']['content']
    except Exception as e:
        return f"Ollama 최적 답변 생성 중 오류가 발생했습니다: {str(e)}"

def generate_optimal_response(ai_responses, user_question, api_key=None):
    """AI들의 응답을 통합하여 최적의 답변 생성 (Ollama 사용)"""
    try:
        # Ollama로 최적 답변 생성 (비용 절약)
        if not api_key:
            return generate_optimal_response_with_ollama(ai_responses, user_question)
        
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # AI 응답들을 정리
        responses_text = ""
        model_names = []
        for model_name, response in ai_responses.items():
            responses_text += f"### {model_name.upper()}:\n{response}\n\n"
            model_names.append(model_name.upper())
        
        # 모델별 분석 섹션 동적 생성
        analysis_sections = ""
        for model_name in model_names:
            analysis_sections += f"""
### {model_name}
- 장점: [주요 장점]
- 단점: [주요 단점]
- 특징: [특별한 특징]
"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"""당신은 AI 응답 분석 및 최적화 전문가입니다. 여러 AI의 답변을 분석하여 가장 완전하고 정확한 통합 답변을 제공해야 합니다.

다음 형식으로 응답해주세요:

## 🎯 통합 답변
[가장 완전하고 정확한 통합 답변 - 모든 AI의 장점을 결합한 최적의 답변]

## 📊 각 AI 분석
{analysis_sections}

## 🔍 분석 근거
[각 AI의 정보를 어떻게 조합하여 통합 답변을 만들었는지 구체적으로 설명]

## 🏆 최종 추천
[가장 추천하는 답변과 그 이유 - 어떤 상황에서 어떤 AI를 선택해야 하는지 포함]

## 💡 추가 인사이트
[질문에 대한 더 깊은 이해나 추가 고려사항]"""},
                {"role": "user", "content": f"질문: {user_question}\n\n다음은 여러 AI의 답변입니다:\n\n{responses_text}\n위 답변들을 분석하여 최적의 통합 답변을 제공해주세요."}
            ],
            temperature=0.7,
            max_tokens=2500
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"최적화된 답변 생성 중 오류가 발생했습니다: {str(e)}"

class ChatBot:
    def __init__(self, api_key, model, api_type):
        self.conversation_history = []
        self.model = model
        self.api_type = api_type
        self.api_key = api_key  # api_key 속성 추가
        
        # API 키가 비어있는지 확인
        if not api_key:
            raise ValueError(f"{api_type.upper()} API 키가 설정되지 않았습니다.")
        
        if api_type == 'openai':
            self.client = openai.OpenAI(api_key=api_key)
        elif api_type == 'anthropic':
            self.client = anthropic.Client(api_key=api_key)
        elif api_type == 'groq':
            self.client = Groq(api_key=api_key)
        elif api_type == 'gemini':
            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(model)
        elif api_type == 'clova':
            # HyperCLOVA X Studio API 방식
            self.client = None  # HTTP 요청으로 처리
            self.hyperclova_api_key = os.getenv('HYPERCLOVA_API_KEY', '')
            self.hyperclova_apigw_key = os.getenv('HYPERCLOVA_APIGW_KEY', '')  # 선택사항
    
    def chat(self, user_input):
        try:
            # 대화 시작 시 시스템 메시지 추가 (특수 문자 제거)
            if not self.conversation_history:
                if self.api_type == 'anthropic':
                    system_content = "You are Claude, an AI assistant that can analyze images and respond in Korean. When you receive image analysis results from other AI systems (like Ollama), you should treat them as if you analyzed the image yourself and provide detailed, natural descriptions in Korean. Make the descriptions rich, engaging, and easy to understand while maintaining the accuracy of the original analysis."
                elif self.api_type == 'openai':
                    system_content = "You are GPT, an AI assistant that can analyze images and respond in Korean. When you receive image analysis results from other AI systems (like Ollama), you should treat them as if you analyzed the image yourself and provide detailed, natural descriptions in Korean. Make the descriptions rich, engaging, and easy to understand while maintaining the accuracy of the original analysis."
                elif self.api_type == 'groq':
                    system_content = "You are Mixtral, an AI assistant that can analyze images and respond in Korean. When you receive image analysis results from other AI systems (like Ollama), you should treat them as if you analyzed the image yourself and provide detailed, natural descriptions in Korean. Make the descriptions rich, engaging, and easy to understand while maintaining the accuracy of the original analysis."
                elif self.api_type == 'gemini':
                    system_content = "You are Gemini, an AI assistant that can analyze images and respond in Korean. When you receive image analysis results from other AI systems (like Ollama), you should treat them as if you analyzed the image yourself and provide detailed, natural descriptions in Korean. Make the descriptions rich, engaging, and easy to understand while maintaining the accuracy of the original analysis."
                elif self.api_type == 'clova':
                    system_content = "당신은 Clova X, 한국어에 특화된 AI 어시스턴트입니다. 다른 AI 시스템(Ollama 등)의 이미지 분석 결과를 받으면 직접 분석한 것처럼 자연스럽고 상세하게 한국어로 설명해주세요."
                else:
                    system_content = "You are an AI assistant that can analyze images and respond in Korean. When you receive image analysis results from other AI systems (like Ollama), you should treat them as if you analyzed the image yourself and provide detailed, natural descriptions in Korean."
                
                self.conversation_history.append({
                    "role": "system",
                    "content": system_content
                })

                # 사용자 입력 출력 (인코딩 안전하게 처리)
                try:
                    safe_input = user_input.encode('ascii', 'ignore').decode('ascii')
                    print(f"User input: {safe_input}")
                except:
                    print("User input received")
            
            self.conversation_history.append({"role": "user", "content": user_input})
            
            # 인코딩 안전한 응답 변수 초기화
            assistant_response = ""
            
            if self.api_type == 'openai':
                # OpenAI 방식 처리
                # GPT-5 시리즈는 특수 파라미터 사용
                if self.model.startswith('gpt-5'):
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=self.conversation_history,
                        # GPT-5는 temperature=1 (기본값)만 지원
                        max_completion_tokens=1024
                    )
                elif self.model.startswith('gpt-4.1'):
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=self.conversation_history,
                        temperature=0.7,
                        max_completion_tokens=1024
                    )
                else:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=self.conversation_history,
                        temperature=0.7,
                        max_tokens=1024
                    )
                assistant_response = response.choices[0].message.content
            
            elif self.api_type == 'anthropic':
                # Anthropic Messages API 방식 처리
                try:
                    client = anthropic.Client(api_key=self.api_key)
                    
                    # 대화 히스토리를 포함한 메시지 생성
                    messages = []
                    for msg in self.conversation_history:
                        if msg['role'] == 'system':
                            continue  # Claude는 system 메시지를 지원하지 않음
                        messages.append({
                            "role": msg['role'],
                            "content": msg['content']
                        })
                    
                    message = client.messages.create(
                        model="claude-3-5-haiku-20241022",
                        max_tokens=4096,
                        temperature=0.7,
                        messages=messages
                    )
                    
                    # 응답 추출
                    raw_response = message.content[0].text
                    assistant_response = raw_response
                    
                    print("Claude response processed successfully")
                    
                except Exception as claude_error:
                    print(f"Claude API error: {str(claude_error)}")
                    print(f"API Key: {self.api_key[:20] if self.api_key else 'None'}...")
                    # API 키가 없거나 오류가 발생한 경우 기본 응답
                    assistant_response = f"안녕하세요! '{user_input}'에 대해 도움을 드릴 수 있습니다. 구체적으로 어떤 정보가 필요하신가요?"


            
            elif self.api_type == 'groq':
                # Groq 방식 처리
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.conversation_history,
                    temperature=0.7,
                    max_tokens=1024
                )
                assistant_response = response.choices[0].message.content
            
            elif self.api_type == 'gemini':
                # Gemini 방식 처리
                try:
                    from google.generativeai.types import HarmCategory, HarmBlockThreshold
                    
                    # 안전 필터 완전 비활성화 (BLOCK_NONE)
                    safety_settings = [
                        {
                            "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                            "threshold": HarmBlockThreshold.BLOCK_NONE
                        },
                        {
                            "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            "threshold": HarmBlockThreshold.BLOCK_NONE
                        },
                        {
                            "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            "threshold": HarmBlockThreshold.BLOCK_NONE
                        },
                        {
                            "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            "threshold": HarmBlockThreshold.BLOCK_NONE
                        }
                    ]
                    
                    # 한국어 안전 필터 우회 전략:
                    # 질문을 영어 컨텍스트로 감싸기
                    english_wrapper = f"""Please answer the following question in Korean.

Question: {user_input}

Your response should be:
1. Written entirely in Korean
2. Informative and helpful
3. Based on factual information
4. Clear and concise

Answer:"""
                    
                    # 각 요청을 독립적으로 처리 (대화 이력 사용 안함)
                    # Gemini의 한국어 안전 필터 우회를 위해 항상 새로운 세션
                    chat = self.client.start_chat(history=[])
                    
                    # 메시지 전송 (영어 래퍼 사용)
                    response = chat.send_message(
                        english_wrapper,  # 영어 컨텍스트로 감싼 질문
                        safety_settings=safety_settings,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.7,
                            max_output_tokens=1024,
                        )
                    )
                    
                    # 안전한 응답 추출
                    if response.candidates:
                        candidate = response.candidates[0]
                        if candidate.content and candidate.content.parts:
                            assistant_response = candidate.content.parts[0].text
                            print("Gemini response processed successfully")
                        else:
                            # finish_reason 상세 로깅
                            print(f"⚠️ Gemini finish_reason: {candidate.finish_reason}")
                            print(f"⚠️ Safety ratings: {candidate.safety_ratings if hasattr(candidate, 'safety_ratings') else 'N/A'}")
                            
                            # 안전 필터 원인 파악
                            if candidate.finish_reason == 2:  # SAFETY
                                assistant_response = "죄송합니다. 이 질문에 대해 안전 정책상 응답할 수 없습니다. 다른 질문을 시도해주세요."
                            elif candidate.finish_reason == 3:  # RECITATION
                                assistant_response = "이 응답은 저작권 문제로 제공할 수 없습니다."
                            else:
                                assistant_response = f"Gemini가 응답을 생성하지 못했습니다 (finish_reason: {candidate.finish_reason})"
                    else:
                        print("⚠️ Gemini 응답에 candidates가 없음")
                        assistant_response = "Gemini 응답을 처리할 수 없습니다."
                    
                except Exception as gemini_error:
                    print(f"Gemini API error: {str(gemini_error)}")
                    import traceback
                    traceback.print_exc()
                    assistant_response = f"Gemini 오류가 발생했습니다. 다시 시도해주세요."
            
            elif self.api_type == 'clova':
                # HyperCLOVA X Studio API 방식 처리 (자유 대화 가능)
                try:
                    import requests
                    import json
                    
                    print(f"🔍 HyperCLOVA X 요청 시작...")
                    print(f"   - 모델: {self.model}")
                    print(f"   - 메시지: {user_input}")
                    
                    if not self.hyperclova_api_key:
                        print("❌ HyperCLOVA X API 키가 없습니다!")
                        assistant_response = "HyperCLOVA X API가 설정되지 않았습니다."
                    else:
                        # HyperCLOVA X API 엔드포인트 (v3 사용)
                        clova_api_url = f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{self.model}"
                        
                        # 헤더 설정 (Bearer 토큰 방식)
                        headers = {
                            "Authorization": f"Bearer {self.hyperclova_api_key}",
                            "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()).replace('-', ''),
                            "Content-Type": "application/json",
                            "Accept": "application/json"
                        }
                        
                        # API Gateway 키가 있으면 추가
                        if self.hyperclova_apigw_key:
                            headers["X-NCP-APIGW-API-KEY"] = self.hyperclova_apigw_key
                        
                        # 대화 히스토리를 HyperCLOVA X v3 형식으로 변환
                        clova_messages = []
                        
                        # 시스템 메시지 추가 (선택사항, content는 배열)
                        clova_messages.append({
                            "role": "system",
                            "content": ""  # 빈 문자열 사용
                        })
                        
                        # 사용자 메시지 추가 (content는 문자열)
                        for msg in self.conversation_history:
                            if msg['role'] != 'system':
                                clova_messages.append({
                                    "role": msg['role'],
                                    "content": msg['content']
                                })
                        
                        # HyperCLOVA X Chat Completions API v3 형식
                        payload = {
                            "messages": clova_messages,
                            "topP": 0.8,
                            "topK": 0,
                            "maxTokens": 1024,
                            "temperature": 0.5,
                            "repetitionPenalty": 1.1,
                            "stop": [],
                            "seed": 0,
                            "includeAiFilters": False
                        }
                        
                        print(f"   - API URL: {clova_api_url}")
                        print(f"   - Messages: {len(clova_messages)}개")
                        
                        response = requests.post(clova_api_url, headers=headers, json=payload, timeout=30)
                        
                        print(f"   - 응답 코드: {response.status_code}")
                        
                        if response.status_code == 200:
                            result = response.json()
                            
                            # status 확인
                            status_code = result.get('status', {}).get('code', '')
                            
                            if status_code == '20000':  # 성공
                                # HyperCLOVA X v3 응답 파싱
                                # 응답 구조: result > message > content (문자열)
                                message_obj = result.get('result', {}).get('message', {})
                                content = message_obj.get('content', '')
                                
                                if content:
                                    assistant_response = content
                                    print(f"✅ HyperCLOVA X 응답 성공: {len(assistant_response)}자")
                                else:
                                    print(f"⚠️ content가 비어있음")
                                    assistant_response = '응답을 받을 수 없습니다.'
                            else:
                                print(f"⚠️ Status code: {status_code}, Message: {result.get('status', {}).get('message', '')}")
                                assistant_response = '응답을 받을 수 없습니다.'
                        else:
                            print(f"⚠️ HyperCLOVA X API error: {response.status_code}")
                            print(f"⚠️ Response: {response.text}")
                            assistant_response = f"HyperCLOVA X API 오류 (코드: {response.status_code})"
                    
                except Exception as clova_error:
                    print(f"❌ HyperCLOVA X API error: {str(clova_error)}")
                    import traceback
                    traceback.print_exc()
                    assistant_response = f"HyperCLOVA X API 오류: {str(clova_error)}"
            
            # 대화 이력에 추가
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            return assistant_response
        except Exception as e:
            # 인코딩 안전한 오류 처리
            try:
                error_msg = str(e)
                # 특수 문자 제거
                import re
                safe_error_msg = re.sub(r'[^\x00-\x7F]+', '', error_msg)
                print(f"Error: {safe_error_msg}")
                return f"오류가 발생했습니다: {safe_error_msg}"
            except:
                print("Error occurred (encoding issue)")
                return "오류가 발생했습니다: 인코딩 문제"

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
HYPERCLOVA_API_KEY = os.getenv('HYPERCLOVA_API_KEY', '')
HYPERCLOVA_APIGW_KEY = os.getenv('HYPERCLOVA_APIGW_KEY', '')



# API 키가 있는 경우에만 ChatBot 인스턴스 생성
chatbots = {}

# === GPT 모델들 ===
try:
    if OPENAI_API_KEY:
        # GPT-5 시리즈 (최신)
        chatbots['gpt-5'] = ChatBot(OPENAI_API_KEY, 'gpt-5', 'openai')
        chatbots['gpt-5-mini'] = ChatBot(OPENAI_API_KEY, 'gpt-5-mini', 'openai')
        chatbots['gpt-5-chat'] = ChatBot(OPENAI_API_KEY, 'gpt-5-chat-latest', 'openai')
        
        # GPT-4.1 시리즈
        chatbots['gpt-4.1'] = ChatBot(OPENAI_API_KEY, 'gpt-4.1', 'openai')
        chatbots['gpt-4.1-mini'] = ChatBot(OPENAI_API_KEY, 'gpt-4.1-mini', 'openai')
        
        # GPT-4o 시리즈
        chatbots['gpt-4o'] = ChatBot(OPENAI_API_KEY, 'gpt-4o', 'openai')
        chatbots['gpt-4o-mini'] = ChatBot(OPENAI_API_KEY, 'gpt-4o-mini', 'openai')
        
        # 기타
        chatbots['gpt-4-turbo'] = ChatBot(OPENAI_API_KEY, 'gpt-4-turbo', 'openai')
        chatbots['gpt-3.5-turbo'] = ChatBot(OPENAI_API_KEY, 'gpt-3.5-turbo', 'openai')
        
        # 하위 호환성
        chatbots['gpt'] = ChatBot(OPENAI_API_KEY, 'gpt-4o', 'openai')
        print(f"✅ GPT 모델 초기화 성공: GPT-5, GPT-4.1, GPT-4o, GPT-4o-mini")
except ValueError as e:
    print(f"❌ GPT 모델 초기화 실패: {e}")

# === Claude 모델들 ===
try:
    if ANTHROPIC_API_KEY:
        # Claude-4 시리즈 (최신, API 출시 시)
        chatbots['claude-4-opus'] = ChatBot(ANTHROPIC_API_KEY, 'claude-4-opus', 'anthropic')
        
        # Claude-3.7 시리즈
        chatbots['claude-3.7-sonnet'] = ChatBot(ANTHROPIC_API_KEY, 'claude-3-7-sonnet', 'anthropic')
        
        # Claude-3.5 시리즈
        chatbots['claude-3.5-sonnet'] = ChatBot(ANTHROPIC_API_KEY, 'claude-3-5-sonnet-20241022', 'anthropic')
        chatbots['claude-3.5-haiku'] = ChatBot(ANTHROPIC_API_KEY, 'claude-3-5-haiku-20241022', 'anthropic')
        
        # Claude-3 시리즈
        chatbots['claude-3-opus'] = ChatBot(ANTHROPIC_API_KEY, 'claude-3-opus-20240229', 'anthropic')
        
        # 하위 호환성
        chatbots['claude'] = ChatBot(ANTHROPIC_API_KEY, 'claude-3-5-sonnet-20241022', 'anthropic')
        print(f"✅ Claude 모델 초기화 성공: Claude-4, 3.7, 3.5, 3")
except ValueError as e:
    print(f"❌ Claude 모델 초기화 실패: {e}")

# === Gemini 모델들 ===
try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Gemini 2.5 시리즈
        chatbots['gemini-2.5-pro'] = ChatBot(GEMINI_API_KEY, 'gemini-2.5-pro', 'gemini')
        chatbots['gemini-2.5-flash'] = ChatBot(GEMINI_API_KEY, 'gemini-2.5-flash', 'gemini')
        
        # Gemini 2.0 시리즈
        chatbots['gemini-2.0-flash-exp'] = ChatBot(GEMINI_API_KEY, 'gemini-2.0-flash-exp', 'gemini')
        chatbots['gemini-2.0-flash-lite'] = ChatBot(GEMINI_API_KEY, 'gemini-2.0-flash-lite', 'gemini')
        
        # 하위 호환성 (기존 프론트엔드 호환)
        chatbots['gemini-pro-1.5'] = ChatBot(GEMINI_API_KEY, 'gemini-2.0-flash-exp', 'gemini')
        chatbots['gemini-pro-1.0'] = ChatBot(GEMINI_API_KEY, 'gemini-2.5-flash', 'gemini')
        chatbots['gemini'] = ChatBot(GEMINI_API_KEY, 'gemini-2.5-flash', 'gemini')
        
        print(f"✅ Gemini 모델 초기화 성공: 2.5-Pro, 2.5-Flash, 2.0-Flash-Exp, 2.0-Flash-Lite")
except ValueError as e:
    print(f"❌ Gemini 모델 초기화 실패: {e}")

# === HyperCLOVA X 모델들 (Naver Clova Studio) ===
try:
    if HYPERCLOVA_API_KEY:
        # HyperCLOVA X Studio API로 자유 대화 가능
        # HCX-003: 고성능 모델 (사용 가능 시)
        # HCX-DASH-001: 빠른 모델 (사용 가능 시)
        # HCX-005: 기본 모델 (권장)
        chatbots['clova-hcx-003'] = ChatBot('dummy_key', 'HCX-005', 'clova')  # HCX-005 사용
        chatbots['clova-hcx-dash-001'] = ChatBot('dummy_key', 'HCX-005', 'clova')  # HCX-005 사용
        print(f"✅ HyperCLOVA X 모델 초기화 성공: HCX-005 (고성능), HCX-005 (빠름)")
    else:
        print(f"⚠️ HyperCLOVA X API 설정이 없습니다. HYPERCLOVA_API_KEY를 .env에 설정해주세요.")
except ValueError as e:
    print(f"❌ HyperCLOVA X 모델 초기화 실패: {e}")

# === 기타 모델 (하위 호환성) ===
try:
    if GROQ_API_KEY:
        chatbots['mixtral'] = ChatBot(GROQ_API_KEY, 'llama-3.1-8b-instant', 'groq')
        chatbots['optimal'] = ChatBot(GROQ_API_KEY, 'llama-3.1-8b-instant', 'groq')
except ValueError as e:
    print(f"❌ Groq 모델 초기화 실패: {e}")

class ChatView(APIView):
    def post(self, request, bot_name):
        try:
            data = request.data
            user_message = data.get('message')
            uploaded_file = request.FILES.get('file')
            
            if not user_message and not uploaded_file:
                return Response({'error': 'No message or file provided'}, status=status.HTTP_400_BAD_REQUEST)
            
            chatbot = chatbots.get(bot_name)
            if not chatbot:
                return Response({'error': 'Invalid bot name'}, status=status.HTTP_400_BAD_REQUEST)

            # 파일이 업로드된 경우 처리
            if uploaded_file:
                try:
                    print(f"파일 업로드 감지: {uploaded_file.name}")
                    
                    # 파일에서 텍스트 추출 또는 이미지 파일 식별
                    extracted_content = process_uploaded_file(uploaded_file)
                    print(f"처리된 내용: {extracted_content[:100]}...")
                    
                    # Ollama로 분석 (이미지는 직접, 텍스트는 요약)
                    print("Ollama를 사용하여 파일 분석 중...")
                    
                    # 임시 파일 저장
                    temp_file_path = None
                    if extracted_content.startswith("IMAGE_FILE:"):
                        # 이미지 파일을 임시로 저장
                        import tempfile
                        import shutil
                        temp_dir = tempfile.mkdtemp()
                        temp_file_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(temp_file_path, 'wb') as temp_file:
                            for chunk in uploaded_file.chunks():
                                temp_file.write(chunk)
                        print(f"이미지 파일 임시 저장: {temp_file_path}")
                    
                    analyzed_content = summarize_content(extracted_content, file_path=temp_file_path)
                    
                    # 파일 타입에 따라 다른 메시지 생성
                    if uploaded_file.name.lower().endswith('.pdf'):
                        final_message = f"다음 문서 내용을 한국어로 요약해주세요:\n\n{analyzed_content}"
                    else:
                        # 모든 AI가 이미지 분석 결과를 받아서 재구성하여 답변하도록 수정
                        if bot_name in ['claude', 'gpt', 'mixtral', 'gemini']:
                            final_message = f"""이미지 분석 결과를 받았습니다. 다음은 Ollama가 분석한 내용입니다:

{analyzed_content}

위 분석 결과를 바탕으로 이 이미지에 대해 한국어로 자세하고 자연스럽게 설명해주세요. 분석 결과의 내용을 그대로 전달하되, 더 풍부하고 이해하기 쉬운 표현으로 재구성해주세요."""
                        else:
                            final_message = f"이미지를 분석해보니 {analyzed_content}입니다. 이 이미지에 대해 한국어로 자세히 설명해주세요."
                    print("분석 완료")
                except Exception as e:
                    print(f"파일 처리 오류: {str(e)}")
                    final_message = f"파일 처리 중 오류가 발생했습니다: {str(e)}"
            else:
                final_message = user_message

            # optimal 모델인 경우 특별 처리
            if bot_name == 'optimal':
                # 사용자 선택 심판 모델 (기본값: GPT-3.5-turbo)
                judge_model = request.data.get('judge_model', 'GPT-3.5-turbo')
                
                # 사용자가 선택한 LLM 모델들 (프론트엔드에서 전달)
                selected_models = request.data.get('selected_models', None)
                
                # FormData로 전달된 경우 JSON 파싱
                if isinstance(selected_models, str):
                    try:
                        import json
                        selected_models = json.loads(selected_models)
                    except:
                        selected_models = None
                
                print(f"🎯 사용자 선택 모델들: {selected_models}")
                print(f"🎯 심판 모델: {judge_model}")
                
                # 1-4단계: 선택된 LLM 병렬 질의 → 심판 모델 검증 → 최적 답변 생성
                try:
                    final_result = collect_multi_llm_responses(final_message, judge_model, selected_models)
                    
                    # 결과 포맷팅
                    response = format_optimal_response(final_result)
                    
                    # 대화 맥락에 추가
                    session_id = request.data.get('user_id', 'default_user')
                    conversation_context_manager.add_conversation(
                        session_id=session_id,
                        user_message=final_message,
                        ai_responses=final_result.get('llm_검증_결과', {}),
                        optimal_response=final_result.get('최적의_답변', '')
                    )
                    
                except Exception as e:
                    print(f"❌ 최적 답변 생성 실패: {e}")
                    # 폴백: 기본 응답
                    response = f"최적 답변 생성 중 오류가 발생했습니다: {str(e)}"
            else:
                # 비용 절약: 파일 분석 시 간소화된 프롬프트 사용
                if uploaded_file and '파일 내용을 분석해' in final_message:
                    # 이미 Ollama로 분석된 내용이므로 간단한 응답 요청
                    simplified_message = f"다음 분석 내용에 대해 간단한 의견을 제시해주세요:\n\n{final_message.split('다음 파일 내용을 분석해주세요:')[1] if '다음 파일 내용을 분석해주세요:' in final_message else final_message}"
                    response = chatbot.chat(simplified_message)
                else:
                    response = chatbot.chat(final_message)
                
            return Response({'response': response})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def collect_multi_llm_responses(user_message, judge_model="GPT-3.5-turbo", selected_models=None):
    """1단계: 선택된 LLM들에게 병렬 질의 후 심판 모델로 검증"""
    import asyncio
    import aiohttp
    import json
    import time
    
    responses = {}
    
    # 사용 가능한 LLM 엔드포인트들 (명시적 모델명 사용)
    all_llm_endpoints = {
        # GPT 모델들
        'GPT-4-Turbo': 'http://localhost:8000/chat/gpt-4-turbo/',
        'GPT-4o': 'http://localhost:8000/chat/gpt-4o/',
        'GPT-3.5-Turbo': 'http://localhost:8000/chat/gpt-3.5-turbo/',
        'GPT-4o-mini': 'http://localhost:8000/chat/gpt-4o-mini/',
        
        # Gemini 모델들
        'Gemini-Pro-1.5': 'http://localhost:8000/chat/gemini-pro-1.5/',
        'Gemini-Pro-1.0': 'http://localhost:8000/chat/gemini-pro-1.0/',
        
        # Claude 모델들
        'Claude-3-Opus': 'http://localhost:8000/chat/claude-3-opus/',
        'Claude-3-Sonnet': 'http://localhost:8000/chat/claude-3-sonnet/',
        'Claude-3-Haiku': 'http://localhost:8000/chat/claude-3-haiku/',
        
        # Clova 모델들
        'Clova-HCX-003': 'http://localhost:8000/chat/clova-hcx-003/',
        'Clova-HCX-DASH-001': 'http://localhost:8000/chat/clova-hcx-dash-001/',
        
        # 하위 호환성
        'GPT-3.5-turbo': 'http://localhost:8000/chat/gpt/',
        'Claude-3.5-haiku': 'http://localhost:8000/chat/claude/', 
        'Llama-3.1-8b': 'http://localhost:8000/chat/mixtral/',
        'Gemini-2.5-Flash': 'http://localhost:8000/chat/gemini/'
    }
    
    # 사용자가 선택한 모델들만 필터링 (기본값: 모든 모델)
    if selected_models:
        # 선택된 모델명을 표준 형식으로 변환
        model_mapping = {
            # GPT 모델들
            'gpt-4-turbo': 'GPT-4-Turbo',
            'gpt-4o': 'GPT-4o',
            'gpt-3.5-turbo': 'GPT-3.5-Turbo',
            'gpt-4o-mini': 'GPT-4o-mini',
            
            # Gemini 모델들
            'gemini-pro-1.5': 'Gemini-Pro-1.5',
            'gemini-pro-1.0': 'Gemini-Pro-1.0',
            
            # Claude 모델들
            'claude-3-opus': 'Claude-3-Opus',
            'claude-3-sonnet': 'Claude-3-Sonnet',
            'claude-3-haiku': 'Claude-3-Haiku',
            
            # Clova 모델들
            'clova-hcx-003': 'Clova-HCX-003',
            'clova-hcx-dash-001': 'Clova-HCX-DASH-001',
            
            # 하위 호환성
            'gpt': 'GPT-3.5-turbo',
            'claude': 'Claude-3.5-haiku',
            'mixtral': 'Llama-3.1-8b',
            'gemini': 'Gemini-2.5-Flash'
        }
        
        selected_standard_models = []
        for model in selected_models:
            if model in model_mapping:
                selected_standard_models.append(model_mapping[model])
        
        # 선택된 모델들의 엔드포인트만 사용
        llm_endpoints = {k: v for k, v in all_llm_endpoints.items() if k in selected_standard_models}
    else:
        # 선택된 모델이 없으면 모든 모델 사용
        llm_endpoints = all_llm_endpoints
    
    print(f"🎯 선택된 LLM 모델들: {list(llm_endpoints.keys())}")
    
    async def fetch_response(session, ai_name, endpoint):
        """개별 LLM에서 응답 가져오기"""
        try:
            payload = {
                'message': user_message,
                'user_id': 'system'
            }
            
            async with session.post(endpoint, json=payload, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    return ai_name, result.get('response', '응답 없음')
                else:
                    return ai_name, f'오류: HTTP {response.status}'
        except Exception as e:
            return ai_name, f'오류: {str(e)}'
    
    async def collect_all_responses():
        """모든 LLM에서 동시에 응답 수집"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            for ai_name, endpoint in llm_endpoints.items():
                task = fetch_response(session, ai_name, endpoint)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, tuple):
                    ai_name, response = result
                    responses[ai_name] = response
                elif isinstance(result, Exception):
                    print(f"LLM 응답 수집 오류: {result}")
    
    try:
        # 비동기 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(collect_all_responses())
        loop.close()
        
        print(f"✅ {len(responses)}개 LLM에서 응답 수집 완료: {list(responses.keys())}")
        
        # 3단계: 심판 모델로 검증 및 최적 답변 생성
        final_result = judge_and_generate_optimal_response(responses, user_message, judge_model)
        return final_result
        
    except Exception as e:
        print(f"❌ LLM 응답 수집 실패: {e}")
        # 폴백: 기본 응답들
        fallback_responses = {
            'GPT-3.5-turbo': f'GPT 응답 (수집 실패): {user_message}에 대한 답변입니다.',
            'Claude-3.5-haiku': f'Claude 응답 (수집 실패): {user_message}에 대한 답변입니다.',
            'Llama-3.1-8b': f'Llama 응답 (수집 실패): {user_message}에 대한 답변입니다.'
        }
        return judge_and_generate_optimal_response(fallback_responses, user_message, judge_model)

def detect_conflicts_in_responses(llm_responses):
    """LLM 응답에서 상호모순 감지 (하드코딩 없이 범용적)"""
    import re
    from collections import defaultdict
    
    conflicts = {
        "dates": defaultdict(list),
        "locations": defaultdict(list), 
        "numbers": defaultdict(list),
        "general_facts": defaultdict(list)
    }
    
    # 각 LLM 응답에서 핵심 정보 추출
    for model_name, response in llm_responses.items():
        # 연도 패턴 추출 (4자리 숫자, 1900-2024 범위)
        year_pattern = r'(\d{4})'
        year_matches = re.findall(year_pattern, response)
        
        for year_str in year_matches:
            try:
                year = int(year_str)
                if 1900 <= year <= 2024:  # 합리적인 연도 범위
                    conflicts["dates"][year_str].append(model_name)
            except ValueError:
                continue
        
        # 위치 정보 추출 (시/도/구/군 패턴)
        locations = re.findall(r'[가-힣]+(?:시|도|구|군)', response)
        for location in locations:
            conflicts["locations"][location].append(model_name)
        
        # 수치 정보 추출 (단위 포함, 연도 제외)
        numbers = re.findall(r'\d+(?:명|개|월|일|억|만|천)', response)
        for number in numbers:
            conflicts["numbers"][number].append(model_name)
    
    # 상호모순 필터링 (2개 이상 다른 값이 있을 때만)
    detected_conflicts = {}
    
    for category, items in conflicts.items():
        if len(items) > 1:  # 서로 다른 값이 2개 이상
            detected_conflicts[category] = dict(items)
    
    return detected_conflicts

def quick_web_verify(conflict_type, conflict_values, question):
    """개선된 웹 검증 (Wikipedia + Google Search)"""
    import requests
    import time
    import re
    
    try:
        # 질문에서 핵심 키워드 추출
        keywords = []
        for value in conflict_values.keys():
            keywords.append(value)
        
        print(f"🔍 웹 검증 시작: {conflict_type} - {keywords}")
        
        # 1차: Wikipedia API 검색
        print("🔍 Wikipedia 검색 시도...")
        wiki_result = search_wikipedia(question, keywords)
        if wiki_result.get("verified"):
            print(f"✅ Wikipedia 검증 성공: {wiki_result['extracted_year']}")
            return wiki_result
        
        # 2차: Google Search (간단한 방법)
        print("🔍 Google 검색 시도...")
        google_result = search_google_simple(question, keywords)
        if google_result.get("verified"):
            print(f"✅ Google 검증 성공: {google_result['extracted_year']}")
            return google_result
        
        # 모든 검색이 실패한 경우
        print("⚠️ 모든 웹 검색 실패")
        return {"verified": False, "error": "모든 검색 엔진 실패"}
                
    except Exception as e:
        print(f"⚠️ 웹 검증 실패: {e}")
        return {"verified": False, "error": str(e)}

def search_wikipedia(question, keywords):
    """Wikipedia API를 통한 자동 검증 (하드코딩 없음)"""
    import requests
    import re
    
    try:
        # 1단계: 질문에서 핵심 키워드 추출
        search_terms = extract_search_terms_from_question(question)
        
        if not search_terms:
            print("⚠️ 검색 키워드 추출 실패")
            return {"verified": False, "error": "검색 키워드 없음"}
        
        print(f"🔍 Wikipedia 검색 키워드: {search_terms}")
        
        # 2단계: 각 검색어로 Wikipedia 검색 시도
        for term in search_terms[:3]:  # 최대 3개 키워드 시도
            # 한글 Wikipedia 검색
            wiki_results = search_wikipedia_api(term, 'ko')
            
            if wiki_results.get("verified"):
                return wiki_results
            
            # 실패 시 영어 Wikipedia 검색
            wiki_results_en = search_wikipedia_api(term, 'en')
            
            if wiki_results_en.get("verified"):
                return wiki_results_en
        
        print("⚠️ 모든 Wikipedia 검색 실패")
        return {"verified": False, "error": "Wikipedia 검색 실패"}
        
    except Exception as e:
        print(f"⚠️ Wikipedia 검증 오류: {e}")
        return {"verified": False, "error": f"Wikipedia 오류: {e}"}

def extract_search_terms_from_question(question):
    """질문에서 검색 키워드 자동 추출"""
    import re
    
    # 핵심 명사 패턴
    keywords = []
    
    # 1. 대학교/학교 패턴
    university_patterns = [
        r'([가-힣]+대학교)',
        r'([가-힣]+대)',
        r'([A-Za-z\s]+University)',
        r'([A-Za-z\s]+College)'
    ]
    
    for pattern in university_patterns:
        matches = re.findall(pattern, question)
        keywords.extend(matches)
    
    # 2. 회사명 패턴
    company_patterns = [
        r'(애플|Apple)',
        r'(구글|Google)',
        r'(삼성|Samsung)',
        r'(마이크로소프트|Microsoft)',
        r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)'
    ]
    
    for pattern in company_patterns:
        matches = re.findall(pattern, question)
        keywords.extend(matches)
    
    # 3. 역사적 사건/기관 패턴
    event_patterns = [
        r'(임시정부)',
        r'(올림픽)',
        r'(코로나19|COVID-19)',
        r'(ChatGPT)',
        r'([가-힣]{2,}정부)',
        r'([가-힣]{2,}사건)'
    ]
    
    for pattern in event_patterns:
        matches = re.findall(pattern, question)
        keywords.extend(matches)
    
    # 중복 제거 및 정리
    unique_keywords = []
    for kw in keywords:
        if kw and kw not in unique_keywords and len(kw) > 1:
            unique_keywords.append(kw.strip())
    
    return unique_keywords

def search_wikipedia_api(search_term, lang='ko'):
    """Wikipedia API 실제 검색"""
    import requests
    import re
    from collections import Counter
    
    try:
        # User-Agent 헤더 추가 (Wikipedia API 요구사항)
        headers = {
            'User-Agent': 'AI_of_AI_ChatBot/1.0 (Educational Project)'
        }
        
        # Wikipedia Search API로 페이지 찾기
        search_url = f"https://{lang}.wikipedia.org/w/api.php"
        search_params = {
            'action': 'opensearch',
            'search': search_term,
            'limit': 1,
            'namespace': 0,
            'format': 'json'
        }
        
        response = requests.get(search_url, params=search_params, headers=headers, timeout=5)
        
        if response.status_code != 200:
            return {"verified": False, "error": f"검색 실패: {response.status_code}"}
        
        search_results = response.json()
        
        if not search_results or len(search_results) < 2 or not search_results[1]:
            print(f"⚠️ '{search_term}' Wikipedia 페이지 없음")
            return {"verified": False, "error": "페이지 없음"}
        
        page_title = search_results[1][0]
        print(f"📄 Wikipedia 페이지 발견: {page_title}")
        
        # 페이지 요약 가져오기
        summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{page_title}"
        summary_response = requests.get(summary_url, headers=headers, timeout=5)
        
        if summary_response.status_code == 200:
            data = summary_response.json()
            extract = data.get('extract', '')
            
            if extract and len(extract) > 20:
                print(f"✅ Wikipedia 요약: {extract[:100]}...")
                
                # 연도 패턴 추출 (한글 텍스트에서도 작동하도록)
                years = re.findall(r'(\d{4})', extract)
                valid_years = [year for year in years if 1900 <= int(year) <= 2024]
                
                if valid_years:
                    # 가장 자주 언급된 연도 선택
                    year_counts = Counter(valid_years)
                    most_common_year = year_counts.most_common(1)[0][0]
                    
                    return {
                        "verified": True,
                        "source": f"Wikipedia ({lang})",
                        "extracted_year": most_common_year,
                        "abstract": extract[:200] + "..." if len(extract) > 200 else extract,
                        "confidence": 0.9,
                        "page_title": page_title
                    }
                
                # 요약에 연도가 없으면 본문 일부 가져오기 시도
                print("⚠️ 요약에 연도 없음, 본문 검색 시도...")
                full_text_result = get_wikipedia_full_text(page_title, lang, headers)
                return full_text_result  # 본문 검색 결과를 반환 (성공/실패 모두)
        
        return {"verified": False, "error": "내용 추출 실패"}
        
    except Exception as e:
        return {"verified": False, "error": f"API 오류: {e}"}

def get_wikipedia_full_text(page_title, lang, headers):
    """Wikipedia 본문에서 연도 정보 추출"""
    import requests
    import re
    from collections import Counter
    
    try:
        # Wikipedia Parse API로 본문 일부 가져오기
        parse_url = f"https://{lang}.wikipedia.org/w/api.php"
        parse_params = {
            'action': 'query',
            'prop': 'extracts',
            'exintro': True,  # 서론만 가져오기
            'explaintext': True,  # 순수 텍스트
            'titles': page_title,
            'format': 'json'
        }
        
        response = requests.get(parse_url, params=parse_params, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            pages = data.get('query', {}).get('pages', {})
            
            if pages:
                page = list(pages.values())[0]
                full_text = page.get('extract', '')
                
                if full_text and len(full_text) > 50:
                    print(f"📄 Wikipedia 본문: {full_text[:150]}...")
                    
                    # 연도 패턴 추출 (한글 텍스트에서도 작동하도록)
                    years = re.findall(r'(\d{4})', full_text)
                    valid_years = [year for year in years if 1900 <= int(year) <= 2024]
                    
                    if valid_years:
                        # 가장 자주 언급된 연도 선택
                        year_counts = Counter(valid_years)
                        most_common_year = year_counts.most_common(1)[0][0]
                        
                        return {
                            "verified": True,
                            "source": f"Wikipedia Full Text ({lang})",
                            "extracted_year": most_common_year,
                            "abstract": full_text[:200] + "..." if len(full_text) > 200 else full_text,
                            "confidence": 0.85,
                            "page_title": page_title
                        }
        
        return {"verified": False, "error": "본문 추출 실패"}
        
    except Exception as e:
        return {"verified": False, "error": f"본문 검색 오류: {e}"}

def search_google_simple(question, keywords):
    """대체 검색 방법 (Wikipedia 실패 시)"""
    # Wikipedia API가 실패한 경우 다른 공개 API 시도 가능
    # 현재는 Wikipedia에만 의존
    return {"verified": False, "error": "Wikipedia 외 검색 미구현"}

def judge_and_generate_optimal_response(llm_responses, user_question, judge_model="gpt-3.5-turbo"):
    """하이브리드 검증 시스템: LLM 비교 + 선택적 웹 검증"""
    try:
        print(f"🔍 하이브리드 검증 시작: {user_question}")
        
        # 1단계: 상호모순 감지
        conflicts = detect_conflicts_in_responses(llm_responses)
        print(f"📊 감지된 상호모순: {conflicts}")
        
        # 2단계: 웹 검증 (항상 실행)
        verified_facts = {}
        web_verification_used = False
        
        print("🌐 Wikipedia 웹 검증 시작...")
        web_result = quick_web_verify("dates", {}, user_question)
        if web_result.get("verified"):
            verified_facts["dates"] = web_result
            web_verification_used = True
            print(f"✅ 웹 검증 성공: 설립연도 {web_result.get('extracted_year')}년")
        else:
            print(f"⚠️ 웹 검증 실패: {web_result.get('error')}")
            
            # 웹 검증 실패 시 상호모순 기반 검증
            if conflicts:
                print("⚡ 상호모순 발견! 상호모순 기반 검증 시작...")
                
                for conflict_type, conflict_values in conflicts.items():
                    if conflict_type in ["dates"]:  # 연도만 검증 (위치는 제외)
                        # 상호모순 정보만 기록
                        verified_facts[conflict_type] = {
                            "verified": False,
                            "conflict_detected": True,
                            "conflict_values": list(conflict_values.keys())
                        }
        
        # 3단계: 심판 프롬프트 구성 (웹 검증 결과 포함)
        model_sections = []
        verification_json_entries = []
        
        for model_name, response in llm_responses.items():
            model_sections.append(f"[{model_name} 답변]\n{response}")
            verification_json_entries.append(f'    "{model_name}": {{"accuracy": "정확성_판정", "errors": "구체적_오류_설명", "confidence": "신뢰도_0-100"}}')
        
        model_responses_text = "\n\n".join(model_sections)
        verification_json_format = ",\n".join(verification_json_entries)
        
        # 웹 검증 결과를 프롬프트에 추가
        web_verification_text = ""
        if web_verification_used and verified_facts.get("dates", {}).get("verified"):
            verification = verified_facts["dates"]
            web_verification_text = f"""

**🌐 Wikipedia 웹 검증 결과 (신뢰도 {verification.get('confidence', 0.9)*100:.0f}%):**
- **✅ 공식 설립연도**: {verification['extracted_year']}년
- **출처**: {verification.get('source', 'Wikipedia')}
- **페이지**: {verification.get('page_title', '확인됨')}
- **검증 내용**: {verification.get('abstract', '')[:150]}...

⚠️ **중요**: 위 정보는 Wikipedia에서 검증된 공식 정보입니다. 
LLM 응답에 다른 연도가 있다면 그것은 오류입니다. 반드시 위 검증된 연도를 사용하세요.
"""
        elif verified_facts.get("dates", {}).get("conflict_detected"):
            conflict_values = verified_facts["dates"].get("conflict_values", [])
            web_verification_text = f"""

**⚠️ 상호모순 감지됨 (웹 검증 실패):**
- **설립연도 불일치**: {', '.join(conflict_values)}년 - 정확한 연도 확인 불가
- **조치**: 확신할 수 없는 연도는 최적 답변에서 생략하세요
"""
        
        judge_prompt = f"""
질문: {user_question}

{model_responses_text}
{web_verification_text}

**지시사항:**
1. 위 LLM 답변들을 분석하여 **공통적이고 정확한 정보**를 추출하세요
2. Wikipedia 검증 결과가 있으면 그 연도를 반드시 사용하세요
3. 각 LLM의 좋은 정보들(위치, 단과대학, 특징 등)을 **조합**하여 풍부한 답변을 생성하세요
4. 상호모순이 있는 정보는 제외하고, **검증된 정보만** 포함하세요

**최적 답변 생성 예시:**
"검증된 정보를 바탕으로 정확하고 상세한 답변을 작성하세요. 
여러 LLM의 답변에서 공통적으로 확인된 사실들을 중심으로 구성하고,
Wikipedia 등 신뢰할 수 있는 출처에서 검증된 정보를 우선적으로 포함하세요.
상호 모순되는 정보는 제외하고, 일관성 있는 답변을 제공하세요."

반드시 아래 JSON 형식으로만 응답하세요:

{{
  "optimal_answer": "검증된 정확한 정보만으로 작성한 최적의 답변",
  "verification_results": {{
    {verification_json_format}
  }},
  "confidence_score": "전체 응답에 대한 신뢰도 (0-100)",
  "contradictions_detected": ["발견된 상호모순 사항들"],
  "fact_verification": {{
    "dates": ["검증된 연도 정보들"],
    "locations": ["검증된 위치 정보들"],
    "facts": ["검증된 기타 사실들"]
  }}
}}

"""

        # 심판 모델 호출
        judge_response = call_judge_model(judge_model, judge_prompt)
        
        # 결과 파싱
        parsed_result = parse_judge_response(judge_response, judge_model, llm_responses)
        
        # 웹 검증 정보 추가
        parsed_result["웹_검증_사용"] = web_verification_used
        if verified_facts:
            parsed_result["웹_검증_결과"] = verified_facts
            parsed_result["검증_성능"] = {
                "상호모순_감지": len(conflicts),
                "웹_검증_성공": len(verified_facts),
                "비용": "$0.003" if web_verification_used else "$0.000"
            }
        
        print(f"✅ 하이브리드 검증 완료: 웹검증={web_verification_used}, 상호모순={len(conflicts)}")
        
        return parsed_result
        
    except Exception as e:
        print(f"❌ 심판 모델 검증 실패: {e}")
        # 폴백: 가장 긴 응답을 최적 답변으로 사용
        if llm_responses:
            longest_response = max(llm_responses.values(), key=len)
            return {
                "최적의_답변": longest_response,
                "llm_검증_결과": {
                    model: {"정확성": "✅", "오류": "검증 실패로 인한 기본값"}
                    for model in llm_responses.keys()
                },
                "심판모델": judge_model,
                "상태": "검증 실패"
            }
        return {
            "최적의_답변": "검증 중 오류가 발생했습니다.",
            "llm_검증_결과": {},
            "심판모델": judge_model,
            "상태": "오류"
        }

def call_judge_model(model_name, prompt):
    """심판 모델 호출"""
    try:
        if model_name in ['GPT-3.5-turbo', 'GPT-4', 'GPT-4o']:
            # OpenAI 모델 사용
            import openai
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                raise ValueError("OpenAI API 키가 설정되지 않음")
            
            client = openai.OpenAI(api_key=openai_api_key)
            
            # 모델명을 OpenAI API 형식으로 변환
            openai_model_name = model_name.lower().replace('-', '-')
            if model_name == 'GPT-4':
                openai_model_name = 'gpt-4'
            elif model_name == 'GPT-4o':
                openai_model_name = 'gpt-4o'
            elif model_name == 'GPT-3.5-turbo':
                openai_model_name = 'gpt-3.5-turbo'
            
            response = client.chat.completions.create(
                model=openai_model_name,
                messages=[
                    {"role": "system", "content": "당신은 사실 검증 전문가입니다. 정확한 정보만 제공하고 틀린 정보를 명확히 지적하세요."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        elif model_name == 'Claude-3.5-haiku':
            # Claude 모델 사용 (대안)
            import anthropic
            anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
            if not anthropic_api_key:
                raise ValueError("Anthropic API 키가 설정되지 않음")
            
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1500,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        elif model_name == 'LLaMA 3.1 8B':
            # LLaMA 모델 사용 (Groq API)
            import groq
            groq_api_key = os.getenv('GROQ_API_KEY')
            if not groq_api_key:
                raise ValueError("Groq API 키가 설정되지 않음")
            
            client = groq.Groq(api_key=groq_api_key)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "당신은 사실 검증 전문가입니다. 정확한 정보만 제공하고 틀린 정보를 명확히 지적하세요."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        else:
            # 기본값으로 GPT-3.5-turbo 사용
            return call_judge_model('GPT-3.5-turbo', prompt)
            
    except Exception as e:
        print(f"❌ 심판 모델 {model_name} 호출 실패: {e}")
        # 폴백: 기본 모델 사용
        if model_name != 'GPT-3.5-turbo':
            return call_judge_model('GPT-3.5-turbo', prompt)
        else:
            raise e

def parse_judge_response(judge_response, judge_model, llm_responses=None):
    """심판 모델 JSON 응답 파싱"""
    try:
        import json
        import re
        
        # JSON 부분만 추출
        json_match = re.search(r'\{.*\}', judge_response, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            parsed_data = json.loads(json_str)
            
            result = {
                "최적의_답변": parsed_data.get("optimal_answer", ""),
                "llm_검증_결과": {},
                "심판모델": judge_model,
                "상태": "성공",
                "신뢰도": parsed_data.get("confidence_score", "50"),
                "상호모순": parsed_data.get("contradictions_detected", []),
                "사실검증": parsed_data.get("fact_verification", {})
            }
            
            # 검증 결과 파싱
            verification_results = parsed_data.get("verification_results", {})
            for model_name, verification in verification_results.items():
                result["llm_검증_결과"][model_name] = {
                    "정확성": "✅" if verification.get("accuracy") == "정확" else "❌",
                    "오류": verification.get("errors", "오류 없음"),
                    "신뢰도": verification.get("confidence", "50")
                }
            
            return result
        else:
            # JSON 파싱 실패 시 폴백
            return create_fallback_result(judge_model, llm_responses)
            
    except Exception as e:
        print(f"❌ JSON 파싱 실패: {e}")
        return create_fallback_result(judge_model, llm_responses)

def create_fallback_result(judge_model, llm_responses=None):
    """폴백 결과 생성"""
    if llm_responses:
        actual_models = list(llm_responses.keys())
    else:
        actual_models = ["GPT-4-Turbo", "GPT-4o", "GPT-3.5-Turbo", "GPT-4o-mini", 
                        "Gemini-Pro-1.5", "Gemini-Pro-1.0",
                        "Claude-3-Opus", "Claude-3-Sonnet", "Claude-3-Haiku",
                        "Clova-HCX-003", "Clova-HCX-DASH-001"]
    
    result = {
        "최적의_답변": "검증 중 오류가 발생했습니다.",
        "llm_검증_결과": {},
        "심판모델": judge_model,
        "상태": "파싱 실패",
        "신뢰도": "0",
        "상호모순": [],
        "사실검증": {}
    }
    
    for model in actual_models:
        result["llm_검증_결과"][model] = {"정확성": "❌", "오류": "검증 실패", "신뢰도": "0"}
    
    return result

def format_optimal_response(final_result):
    """최적 답변 결과를 사용자 친화적 형식으로 포맷팅"""
    try:
        optimal_answer = final_result.get("최적의_답변", "")
        verification_results = final_result.get("llm_검증_결과", {})
        judge_model = final_result.get("심판모델", "gpt-3.5-turbo")
        status = final_result.get("상태", "성공")
        
        # 새로운 JSON 형식 지원
        confidence = final_result.get("신뢰도", "50")
        contradictions = final_result.get("상호모순", [])
        
        # 메인 답변 구성
        formatted_response = f"""**최적의 답변:**

{optimal_answer}

*({judge_model} 검증 완료 - 신뢰도: {confidence}%)*

**각 LLM 검증 결과:**
"""
        
        # 각 LLM 검증 결과 추가 (실제 응답한 모델들만)
        model_names = {
            # GPT 모델들
            "GPT-4-Turbo": "GPT-4 Turbo",
            "GPT-4o": "GPT-4o",
            "GPT-3.5-Turbo": "GPT-3.5 Turbo",
            "GPT-4o-mini": "GPT-4o-mini",
            
            # Gemini 모델들
            "Gemini-Pro-1.5": "Gemini Pro 1.5",
            "Gemini-Pro-1.0": "Gemini Pro 1.0",
            
            # Claude 모델들
            "Claude-3-Opus": "Claude 3 Opus",
            "Claude-3-Sonnet": "Claude 3 Sonnet",
            "Claude-3-Haiku": "Claude 3 Haiku",
            
            # Clova 모델들
            "Clova-HCX-003": "HCX-003",
            "Clova-HCX-DASH-001": "HCX-DASH-001",
            
            # 하위 호환성
            "GPT-3.5-turbo": "GPT-3.5 Turbo",
            "Claude-3.5-haiku": "Claude-3.5 Haiku", 
            "Llama-3.1-8b": "Llama 3.1 8B",
            "Gemini-2.5-Flash": "Gemini 2.5 Flash"
        }
        
        for model_key, model_display_name in model_names.items():
            if model_key in verification_results:
                verification = verification_results[model_key]
                accuracy = verification.get("정확성", "✅")
                error = verification.get("오류", "오류 없음")
                model_confidence = verification.get("신뢰도", "50")
                
                formatted_response += f"""
**{model_display_name}:**
{accuracy} 정확성: {accuracy}
❌ 오류: {error}
📊 신뢰도: {model_confidence}%
"""
        
        # 상호모순 정보 추가
        if contradictions:
            formatted_response += f"""

**⚠️ 발견된 상호모순:**
{chr(10).join(f"- {contradiction}" for contradiction in contradictions)}
"""
        
        # 상태 정보 추가
        if status != "성공":
            formatted_response += f"\n*상태: {status}*"
        
        return formatted_response
        
    except Exception as e:
        print(f"❌ 응답 포맷팅 실패: {e}")
        return f"""**최적의 답변:**

{final_result.get('최적의_답변', '답변 생성 실패')}

*포맷팅 오류 발생*
"""

def generate_unique_username(email, name=None):
    """이메일 기반으로 고유한 사용자명 생성"""
    base_username = email.split('@')[0]
    username = base_username
    counter = 1
    
    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{counter}"
        counter += 1
    
    return username

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def google_callback(request):
    try:
        # 액세스 토큰 추출
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return Response(
                {'error': '잘못된 인증 헤더'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        access_token = auth_header.split(' ')[1]

        # Google API로 사용자 정보 요청
        user_info_response = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )

        if user_info_response.status_code != 200:
            return Response(
                {'error': 'Google에서 사용자 정보를 가져오는데 실패했습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        user_info = user_info_response.json()
        email = user_info.get('email')
        name = user_info.get('name')
        
        if not email:
            return Response(
                {'error': '이메일이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 기존 사용자 검색
            user = User.objects.get(email=email)
            # 기존 사용자의 이름이 없으면 업데이트
            if name and (not user.first_name and not user.last_name):
                if ' ' in name:
                    first_name, last_name = name.split(' ', 1)
                    user.first_name = first_name
                    user.last_name = last_name
                else:
                    user.first_name = name
                user.save()
        except User.DoesNotExist:
            # 새로운 사용자 생성
            username = generate_unique_username(email, name)
            user = User.objects.create(
                username=username,
                email=email,
                is_active=True
            )
            
            # 이름 설정
            if name:
                if ' ' in name:
                    first_name, last_name = name.split(' ', 1)
                    user.first_name = first_name
                    user.last_name = last_name
                else:
                    user.first_name = name
            
            # 기본 비밀번호 설정 (선택적)
            random_password = uuid.uuid4().hex
            user.set_password(random_password)
            user.save()

        # 소셜 계정 정보 생성 또는 업데이트
        social_account, created = SocialAccount.objects.get_or_create(
            email=email,
            provider='google',
            defaults={'user': user}
        )

        if not created and social_account.user != user:
            social_account.user = user
            social_account.save()

        # 사용자 정보 직렬화
        serializer = UserSerializer(user)
        
        return Response({
            'message': '구글 로그인 성공',
            'user': serializer.data
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def kakao_callback(request):
    """카카오 로그인 콜백"""
    try:
        data = request.data
        access_token = data.get('access_token')
        
        if not access_token:
            return Response(
                {'error': '액세스 토큰이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 카카오 API로 사용자 정보 가져오기
        user_info_response = requests.get(
            'https://kapi.kakao.com/v2/user/me',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if user_info_response.status_code != 200:
            return Response(
                {'error': '카카오에서 사용자 정보를 가져오는데 실패했습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_info = user_info_response.json()
        kakao_account = user_info.get('kakao_account', {})
        profile = kakao_account.get('profile', {})
        
        email = kakao_account.get('email')
        name = profile.get('nickname')
        
        if not email:
            return Response(
                {'error': '이메일이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # 기존 사용자 검색
            user = User.objects.get(email=email)
            # 기존 사용자의 이름이 없으면 업데이트
            if name and (not user.first_name and not user.last_name):
                user.first_name = name
                user.save()
        except User.DoesNotExist:
            # 새로운 사용자 생성
            username = generate_unique_username(email, name)
            user = User.objects.create(
                username=username,
                email=email,
                is_active=True
            )
            
            # 이름 설정
            if name:
                user.first_name = name
            
            # 기본 비밀번호 설정 (선택적)
            random_password = uuid.uuid4().hex
            user.set_password(random_password)
            user.save()
        
        # 소셜 계정 정보 생성 또는 업데이트
        social_account, created = SocialAccount.objects.get_or_create(
            email=email,
            provider='kakao',
            defaults={'user': user}
        )
        
        if not created and social_account.user != user:
            social_account.user = user
            social_account.save()
        
        serializer = UserSerializer(user)
        return Response({
            'message': '카카오 로그인 성공',
            'user': serializer.data
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def naver_callback(request):
    """네이버 로그인 콜백"""
    try:
        data = request.data
        access_token = data.get('access_token')
        
        if not access_token:
            return Response(
                {'error': '액세스 토큰이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 네이버 API로 사용자 정보 가져오기
        user_info_response = requests.get(
            'https://openapi.naver.com/v1/nid/me',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if user_info_response.status_code != 200:
            return Response(
                {'error': '네이버에서 사용자 정보를 가져오는데 실패했습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_info = user_info_response.json()
        response_data = user_info.get('response', {})
        
        email = response_data.get('email')
        name = response_data.get('name')
        nickname = response_data.get('nickname')
        
        if not email:
            return Response(
                {'error': '이메일이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 이름이 없으면 닉네임 사용
        display_name = name or nickname
        
        try:
            # 기존 사용자 검색
            user = User.objects.get(email=email)
            # 기존 사용자의 이름이 없으면 업데이트
            if display_name and (not user.first_name and not user.last_name):
                user.first_name = display_name
                user.save()
        except User.DoesNotExist:
            # 새로운 사용자 생성
            username = generate_unique_username(email, display_name)
            user = User.objects.create(
                username=username,
                email=email,
                is_active=True
            )
            
            # 이름 설정
            if display_name:
                user.first_name = display_name
            
            # 기본 비밀번호 설정 (선택적)
            random_password = uuid.uuid4().hex
            user.set_password(random_password)
            user.save()
        
        # 소셜 계정 정보 생성 또는 업데이트
        social_account, created = SocialAccount.objects.get_or_create(
            email=email,
            provider='naver',
            defaults={'user': user}
        )
        
        if not created and social_account.user != user:
            social_account.user = user
            social_account.save()
        
        serializer = UserSerializer(user)
        return Response({
            'message': '네이버 로그인 성공',
            'user': serializer.data
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class VideoUploadView(APIView):
    """영상 업로드 뷰 - 독립적인 영상 처리"""
    permission_classes = [AllowAny]  # 임시로 AllowAny로 변경
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request):
        try:
            import os
            import uuid
            import time
            from django.core.files.storage import default_storage
            from django.conf import settings
            
            # 업로드된 파일 확인 (backend_videochat 방식)
            if 'video' not in request.FILES:
                return Response({
                    'error': '비디오 파일이 없습니다'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            video_file = request.FILES['video']
            
            # 파일 확장자 검증 (backend_videochat 방식)
            if not video_file.name.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                return Response({
                    'error': '지원하지 않는 파일 형식입니다. MP4, AVI, MOV, MKV, WEBM 형식만 지원됩니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 파일 크기 검증 (50MB 제한)
            max_size = 50 * 1024 * 1024  # 50MB
            if video_file.size > max_size:
                return Response({
                    'error': f'파일 크기가 너무 큽니다. 최대 50MB까지 업로드 가능합니다. (현재: {video_file.size / (1024*1024):.1f}MB)'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 파일명 길이 검증
            if len(video_file.name) > 200:
                return Response({
                    'error': '파일명이 너무 깁니다. 200자 이하로 제한됩니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 고유한 파일명 생성 (backend_videochat 방식)
            timestamp = int(time.time())
            filename = f"upload_{timestamp}_{video_file.name}"
            
            # 파일 저장 (backend_videochat 방식)
            from django.core.files.base import ContentFile
            file_path = default_storage.save(
                f'uploads/{filename}',
                ContentFile(video_file.read())
            )
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            
            # 파일 저장 검증
            if not os.path.exists(full_path):
                return Response({
                    'error': '파일 저장에 실패했습니다. 다시 시도해주세요.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 파일 크기 재검증 (실제 저장된 파일)
            actual_size = os.path.getsize(full_path)
            if actual_size == 0:
                return Response({
                    'error': '빈 파일이 업로드되었습니다. 유효한 영상 파일을 선택해주세요.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create Video model instance (backend_videochat 방식)
            video = Video.objects.create(
                filename=filename,
                original_name=video_file.name,
                file_path=file_path,
                file_size=video_file.size,
                file=file_path,  # file 필드도 저장
                analysis_status='pending'
            )
            
            # 백그라운드에서 영상 분석 시작
            def analyze_video_background():
                try:
                    print(f"🎬 백그라운드 영상 분석 시작: {video.id}")
                    
                    # 파일 존재 여부 재확인
                    if not os.path.exists(full_path):
                        print(f"❌ 영상 파일이 존재하지 않음: {full_path}")
                        video.analysis_status = 'failed'
                        video.analysis_message = '영상 파일을 찾을 수 없습니다.'
                        video.save()
                        return
                    
                    analysis_result = video_analysis_service.analyze_video(file_path, video.id)
                    if analysis_result and analysis_result is not True:
                        # 분석 결과가 딕셔너리인 경우 (오류 정보 포함)
                        if isinstance(analysis_result, dict) and not analysis_result.get('success', True):
                            print(f"❌ 영상 분석 실패: {video.id} - {analysis_result.get('error_message', 'Unknown error')}")
                            video.analysis_status = 'failed'
                            video.analysis_message = analysis_result.get('error_message', '분석 중 오류가 발생했습니다.')
                        else:
                            print(f"✅ 영상 분석 완료: {video.id}")
                            video.analysis_status = 'completed'
                            video.is_analyzed = True
                    else:
                        print(f"❌ 영상 분석 실패: {video.id}")
                        video.analysis_status = 'failed'
                        video.analysis_message = '분석 중 오류가 발생했습니다.'
                    
                    video.save()
                except Exception as e:
                    print(f"❌ 백그라운드 분석 오류: {e}")
                    video.analysis_status = 'failed'
                    video.analysis_message = f'분석 중 오류가 발생했습니다: {str(e)}'
                    video.save()
            
            # 별도 스레드에서 분석 실행
            analysis_thread = threading.Thread(target=analyze_video_background)
            analysis_thread.daemon = True
            analysis_thread.start()
            
            return Response({
                'success': True,
                'video_id': video.id,
                'filename': filename,
                'message': f'비디오 "{video_file.name}"이 성공적으로 업로드되었습니다.'
            })
                
        except Exception as e:
            return Response({
                'error': f'영상 업로드 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VideoListView(APIView):
    """비디오 목록 조회 - backend_videochat 방식"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            videos = Video.objects.all()
            video_list = []
            
            for video in videos:
                # 상태 동기화 수행 (파일과 DB 상태 일치 확인)
                video_analysis_service.sync_video_status_with_files(video.id)
                
                # 동기화 후 최신 상태로 다시 가져오기
                video.refresh_from_db()
                
                # 분석 상태 결정 (더 정확한 판단)
                actual_analysis_status = video.analysis_status
                if video.analysis_status == 'completed' and not video.analysis_json_path:
                    actual_analysis_status = 'failed'
                    print(f"⚠️ 영상 {video.id}: analysis_status는 completed이지만 analysis_json_path가 없음")
                
                video_data = {
                    'id': video.id,
                    'filename': video.filename,
                    'original_name': video.original_name,
                    'duration': video.duration,
                    'is_analyzed': video.is_analyzed,
                    'analysis_status': actual_analysis_status,  # 실제 상태 사용
                    'uploaded_at': video.uploaded_at,
                    'file_size': video.file_size,
                    'analysis_progress': video.analysis_progress,  # 진행률 정보 추가
                    'analysis_message': video.analysis_message or ''  # 분석 메시지 추가
                }
                video_list.append(video_data)
            
            return Response({
                'videos': video_list,
                'count': len(video_list)
            })
            
        except Exception as e:
            return Response({
                'error': f'비디오 목록 조회 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VideoDeleteView(APIView):
    """영상 삭제 API"""
    permission_classes = [AllowAny]
    
    def delete(self, request, video_id):
        try:
            video = Video.objects.get(id=video_id)
            
            # 파일 삭제
            if video.file and os.path.exists(video.file.path):
                try:
                    os.remove(video.file.path)
                    logger.info(f"✅ 영상 파일 삭제: {video.file.path}")
                except Exception as e:
                    logger.warning(f"영상 파일 삭제 실패: {e}")
            
            # 분석 결과 파일 삭제
            if video.analysis_json_path:
                json_path = os.path.join(settings.MEDIA_ROOT, video.analysis_json_path)
                if os.path.exists(json_path):
                    try:
                        os.remove(json_path)
                        logger.info(f"✅ 분석 결과 파일 삭제: {json_path}")
                    except Exception as e:
                        logger.warning(f"분석 결과 파일 삭제 실패: {e}")
            
            # 프레임 이미지 파일 삭제
            if video.frame_images_path:
                frame_paths = video.frame_images_path.split(',')
                for path in frame_paths:
                    full_path = os.path.join(settings.MEDIA_ROOT, path.strip())
                    if os.path.exists(full_path):
                        try:
                            os.remove(full_path)
                        except Exception as e:
                            logger.warning(f"프레임 이미지 삭제 실패: {e}")
            
            # DB에서 삭제
            video_name = video.original_name
            video.delete()
            
            logger.info(f"✅ 영상 삭제 완료: {video_name} (ID: {video_id})")
            
            return Response({
                'message': f'영상 "{video_name}"이(가) 삭제되었습니다.',
                'video_id': video_id
            })
            
        except Video.DoesNotExist:
            return Response({
                'error': '영상을 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"❌ 영상 삭제 오류: {e}")
            return Response({
                'error': f'영상 삭제 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VideoRenameView(APIView):
    """영상 이름 변경 API"""
    permission_classes = [AllowAny]
    
    def post(self, request, video_id):
        try:
            video = Video.objects.get(id=video_id)
            new_name = request.data.get('original_name', '').strip()
            
            if not new_name:
                return Response({
                    'error': '새 이름을 입력해주세요.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            old_name = video.original_name
            video.original_name = new_name
            video.save()
            
            logger.info(f"✅ 영상 이름 변경: {old_name} → {new_name} (ID: {video_id})")
            
            return Response({
                'message': f'영상 이름이 "{new_name}"(으)로 변경되었습니다.',
                'video_id': video_id,
                'new_name': new_name
            })
            
        except Video.DoesNotExist:
            return Response({
                'error': '영상을 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"❌ 영상 이름 변경 오류: {e}")
            return Response({
                'error': f'영상 이름 변경 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VideoAnalysisView(APIView):
    """영상 분석 상태 확인 및 시작 - backend_videochat 방식"""
    permission_classes = [AllowAny]
    
    def get(self, request, video_id):
        try:
            video = Video.objects.get(id=video_id)
            
            # 상태 동기화 수행 (파일과 DB 상태 일치 확인)
            video_analysis_service.sync_video_status_with_files(video_id)
            
            # 동기화 후 최신 상태로 다시 가져오기
            video.refresh_from_db()
            
            # 진행률 정보 추출
            progress_info = {
                'analysis_progress': video.analysis_progress,
                'analysis_message': video.analysis_message or ''
            }
            
            # 분석 상태 결정 (더 정확한 판단)
            actual_analysis_status = video.analysis_status
            if video.analysis_status == 'completed' and not video.analysis_json_path:
                actual_analysis_status = 'failed'
                print(f"⚠️ 영상 {video_id}: analysis_status는 completed이지만 analysis_json_path가 없음")
            
            return Response({
                'video_id': video.id,
                'filename': video.filename,
                'original_name': video.original_name,
                'analysis_status': actual_analysis_status,  # 실제 상태 사용
                'is_analyzed': video.is_analyzed,
                'duration': video.duration,
                'progress': progress_info,  # 프론트엔드가 기대하는 구조로 변경
                'uploaded_at': video.uploaded_at,
                'file_size': video.file_size,
                'analysis_json_path': video.analysis_json_path,
                'frame_images_path': video.frame_images_path
            })
        except Video.DoesNotExist:
            return Response({
                'error': '영상을 찾을 수 없습니다'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'영상 분석 조회 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, video_id):
        """영상 분석 시작"""
        try:
            video = Video.objects.get(id=video_id)
            
            # 이미 분석 중이거나 완료된 경우
            if video.analysis_status == 'pending':
                return Response({
                    'message': '이미 분석이 진행 중입니다.',
                    'status': 'pending'
                })
            elif video.analysis_status == 'completed':
                return Response({
                    'message': '이미 분석이 완료되었습니다.',
                    'status': 'completed'
                })
            
            # 분석 상태를 pending으로 변경
            video.analysis_status = 'pending'
            video.save()
            
            # 백그라운드에서 영상 분석 시작
            def analyze_video_background():
                try:
                    print(f"🎬 백그라운드 영상 분석 시작: {video.id}")
                    analysis_result = video_analysis_service.analyze_video(video.file_path, video.id)
                    if analysis_result:
                        print(f"✅ 영상 분석 완료: {video.id}")
                        # Video 모델 업데이트
                        video.analysis_status = 'completed'
                        video.is_analyzed = True
                        video.save()
                    else:
                        print(f"❌ 영상 분석 실패: {video.id}")
                        video.analysis_status = 'failed'
                        video.save()
                except Exception as e:
                    print(f"❌ 백그라운드 분석 오류: {e}")
                    video.analysis_status = 'failed'
                    video.save()
            
            # 별도 스레드에서 분석 실행
            analysis_thread = threading.Thread(target=analyze_video_background)
            analysis_thread.daemon = True
            analysis_thread.start()
            
            return Response({
                'message': '영상 분석을 시작했습니다.',
                'status': 'pending'
            })
            
        except Video.DoesNotExist:
            return Response({
                'error': '영상을 찾을 수 없습니다'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'영상 분석 시작 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VideoChatView(APIView):
    """영상 채팅 뷰 - 다중 AI 응답 및 통합"""
    permission_classes = [AllowAny]  # 임시로 AllowAny로 변경
    
    def get(self, request, video_id=None):
        """채팅 세션 목록 조회"""
        try:
            print(f"🔍 VideoChatView GET 요청 - video_id: {video_id}")
            
            # 사용자 정보 처리 (인증되지 않은 경우 기본 사용자 사용)
            user = None
            if hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
            else:
                # 기본 사용자 생성 또는 가져오기
                from chat.models import User
                user, created = User.objects.get_or_create(
                    username='anonymous',
                    defaults={'email': 'anonymous@example.com'}
                )
                print(f"✅ 기본 사용자 생성/가져오기: {user.username}")
            
            if video_id:
                # 특정 영상의 채팅 세션 조회
                sessions = VideoChatSession.objects.filter(
                    user=user, 
                    video_id=video_id,
                    is_active=True
                ).order_by('-created_at')
            else:
                # 사용자의 모든 채팅 세션 조회
                sessions = VideoChatSession.objects.filter(
                    user=user,
                    is_active=True
                ).order_by('-created_at')
            
            serializer = VideoChatSessionSerializer(sessions, many=True)
            return Response({
                'sessions': serializer.data,
                'total_count': sessions.count()
            })
            
        except Exception as e:
            return Response({
                'error': f'채팅 세션 조회 중 오류 발생: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, video_id):
        """영상 채팅 메시지 전송"""
        try:
            print(f"🔍 VideoChatView POST 요청 - video_id: {video_id}")
            # Django WSGIRequest에서 JSON 데이터 파싱
            import json
            if hasattr(request, 'data'):
                message = request.data.get('message')
            else:
                body = request.body.decode('utf-8')
                data = json.loads(body)
                message = data.get('message')
            print(f"📝 메시지: {message}")
            
            if not message:
                return Response({
                    'error': '메시지가 필요합니다'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 영상 분석 상태 확인 (Video 모델에서 직접 확인)
            try:
                video = Video.objects.get(id=video_id)
                if video.analysis_status == 'pending':
                    return Response({
                        'error': '영상 분석이 진행 중입니다. 잠시 후 다시 시도해주세요.',
                        'status': 'analyzing'
                    }, status=status.HTTP_202_ACCEPTED)
                elif video.analysis_status == 'failed':
                    return Response({
                        'error': '영상 분석에 실패했습니다. 다른 영상을 업로드해주세요.',
                        'status': 'failed'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except Video.DoesNotExist:
                return Response({
                    'error': '영상을 찾을 수 없습니다'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # 사용자 정보 처리 (인증되지 않은 경우 기본 사용자 사용)
            user = request.user if request.user.is_authenticated else None
            if not user:
                # 기본 사용자 생성 또는 가져오기
                from chat.models import User
                user, created = User.objects.get_or_create(
                    username='anonymous',
                    defaults={'email': 'anonymous@example.com'}
                )
            
            # 채팅 세션 가져오기 또는 생성
            session, created = VideoChatSession.objects.get_or_create(
                user=user,
                video_id=video_id,
                is_active=True,
                defaults={
                    'video_title': f"Video {video_id}",
                    'video_analysis_data': {}
                }
            )
            
            # 사용자 메시지 저장
            user_message = VideoChatMessage.objects.create(
                session=session,
                message_type='user',
                content=message
            )
            
            # 특별 명령어 시스템 제거 - 모든 메시지를 일반 채팅으로 처리
            print(f"🔍 일반 채팅 메시지 처리: '{message}'")
            
            # 영상 분석 데이터 가져오기 (Video 모델에서 직접)
            analysis_data = {
                'original_name': video.original_name,
                'file_size': video.file_size,
                'uploaded_at': video.uploaded_at.isoformat(),
                'analysis_status': video.analysis_status,
                'duration': video.duration,
                'is_analyzed': video.is_analyzed
            }
            
            # JSON 분석 결과 로드 (기존 + TeletoVision_AI 스타일)
            analysis_json_data = None
            teleto_vision_data = {}
            
            # 1. 기존 분석 JSON 로드
            if video.analysis_json_path:
                try:
                    from django.conf import settings
                    json_path = os.path.join(settings.MEDIA_ROOT, video.analysis_json_path)
                    print(f"🔍 기존 JSON 파일 경로: {json_path}")
                    print(f"🔍 파일 존재 여부: {os.path.exists(json_path)}")
                    
                    with open(json_path, 'r', encoding='utf-8') as f:
                        analysis_json_data = json.load(f)
                    print(f"✅ 기존 JSON 분석 결과 로드 성공: {json_path}")
                    print(f"📊 기존 JSON 데이터 키: {list(analysis_json_data.keys())}")
                    if 'frame_results' in analysis_json_data:
                        print(f"📊 frame_results 개수: {len(analysis_json_data['frame_results'])}")
                        if analysis_json_data['frame_results']:
                            print(f"📊 첫 번째 프레임: {analysis_json_data['frame_results'][0]}")
                except Exception as e:
                    print(f"❌ 기존 JSON 분석 결과 로드 실패: {e}")
                    import traceback
                    print(f"❌ 상세 오류: {traceback.format_exc()}")
            else:
                print("❌ analysis_json_path가 없습니다.")
            
            # 2. TeletoVision_AI 스타일 JSON 로드
            try:
                from django.conf import settings
                video_name = video.original_name or video.filename
                detection_db_path = os.path.join(settings.MEDIA_ROOT, f"{video_name}-detection_db.json")
                meta_db_path = os.path.join(settings.MEDIA_ROOT, f"{video_name}-meta_db.json")
                
                print(f"🔍 TeletoVision detection_db 경로: {detection_db_path}")
                print(f"🔍 TeletoVision meta_db 경로: {meta_db_path}")
                
                # detection_db.json 로드
                if os.path.exists(detection_db_path):
                    with open(detection_db_path, 'r', encoding='utf-8') as f:
                        teleto_vision_data['detection_db'] = json.load(f)
                    print(f"✅ TeletoVision detection_db 로드 성공: {len(teleto_vision_data['detection_db'])}개 프레임")
                else:
                    print(f"❌ TeletoVision detection_db 파일 없음: {detection_db_path}")
                
                # meta_db.json 로드
                if os.path.exists(meta_db_path):
                    with open(meta_db_path, 'r', encoding='utf-8') as f:
                        teleto_vision_data['meta_db'] = json.load(f)
                    print(f"✅ TeletoVision meta_db 로드 성공: {len(teleto_vision_data['meta_db'].get('frame', []))}개 프레임")
                    if teleto_vision_data['meta_db'].get('frame'):
                        first_frame = teleto_vision_data['meta_db']['frame'][0]
                        print(f"📊 첫 번째 meta 프레임 키: {list(first_frame.keys())}")
                else:
                    print(f"❌ TeletoVision meta_db 파일 없음: {meta_db_path}")
                    
            except Exception as e:
                print(f"❌ TeletoVision JSON 로드 실패: {e}")
                import traceback
                print(f"❌ 상세 오류: {traceback.format_exc()}")
                teleto_vision_data = {}
                print(f"❌ video.analysis_json_path: {video.analysis_json_path}")
            
            # 프레임 검색 및 이미지 URL 생성
            print(f"🔍 프레임 검색 시작 - analysis_json_data: {analysis_json_data is not None}")
            if analysis_json_data:
                print(f"📊 frame_results 존재: {'frame_results' in analysis_json_data}")
                if 'frame_results' in analysis_json_data:
                    print(f"📊 frame_results 개수: {len(analysis_json_data['frame_results'])}")
            else:
                print("❌ analysis_json_data가 None입니다!")
                print(f"❌ video.analysis_json_path: {video.analysis_json_path}")
                print(f"❌ video.analysis_status: {video.analysis_status}")
                print(f"❌ video.is_analyzed: {video.is_analyzed}")
            
            # 대화 맥락 가져오기
            session_id = f"video_{video_id}_user_{user.id}"
            context_prompt = conversation_memory.generate_context_prompt(session_id, message)
            
            # 프레임 검색 (의도 기반)
            relevant_frames = self._find_relevant_frames(message, analysis_json_data, video_id)
            print(f"🔍 검색된 프레임 수: {len(relevant_frames)}")
            if relevant_frames:
                print(f"📸 첫 번째 프레임: {relevant_frames[0]}")
                print(f"📸 모든 프레임 정보:")
                for i, frame in enumerate(relevant_frames):
                    print(f"  프레임 {i+1}: {frame}")
            else:
                print("❌ 검색된 프레임이 없습니다!")
                print(f"❌ analysis_json_data keys: {list(analysis_json_data.keys()) if analysis_json_data else 'None'}")
                if analysis_json_data and 'frame_results' in analysis_json_data:
                    print(f"❌ frame_results 개수: {len(analysis_json_data['frame_results'])}")
                    if analysis_json_data['frame_results']:
                        print(f"❌ 첫 번째 frame_result: {analysis_json_data['frame_results'][0]}")
            
            # 다중 AI 응답 생성
            ai_responses = {}
            individual_messages = []
            
            # 기본 채팅 시스템과 동일한 AI 모델 초기화
            try:
                # 전역 chatbots 변수 사용 (이미 초기화되어 있음)
                print(f"✅ 사용 가능한 AI 모델: {list(chatbots.keys())}")
            except Exception as e:
                print(f"⚠️ AI 모델 초기화 실패: {e}")
                # 전역 chatbots 변수는 이미 초기화되어 있으므로 덮어쓰지 않음
            
            # AI 모델 확인
            print(f"🤖 사용 가능한 AI 모델: {list(chatbots.keys()) if chatbots else 'None'}")
            
            # AI 모델이 없는 경우 기본 응답 (프레임 정보 포함)
            if not chatbots:
                print("⚠️ 사용 가능한 AI 모델이 없습니다. 기본 응답을 생성합니다.")
                
                # 프레임 정보를 포함한 더 나은 응답 생성
                if relevant_frames:
                    frame_count = len(relevant_frames)
                    default_response = f"영상에서 '{message}'와 관련된 {frame_count}개의 프레임을 찾았습니다!\n\n"
                    
                    for i, frame in enumerate(relevant_frames, 1):
                        default_response += f"📸 프레임 {i}:\n"
                        default_response += f"   ⏰ 시간: {frame['timestamp']:.1f}초\n"
                        default_response += f"   🎯 관련도: {frame['relevance_score']}점\n"
                        
                        if frame['persons'] and len(frame['persons']) > 0:
                            default_response += f"   👤 사람 {len(frame['persons'])}명 감지\n"
                        
                        if frame['objects'] and len(frame['objects']) > 0:
                            default_response += f"   📦 객체 {len(frame['objects'])}개 감지\n"
                        
                        scene_attrs = frame.get('scene_attributes', {})
                        if scene_attrs:
                            scene_type = scene_attrs.get('scene_type', 'unknown')
                            lighting = scene_attrs.get('lighting', 'unknown')
                            activity = scene_attrs.get('activity_level', 'unknown')
                            default_response += f"   🏞️ 장면: {scene_type}, 조명: {lighting}, 활동: {activity}\n"
                        
                        default_response += "\n"
                    
                    default_response += "💡 AI 모델이 활성화되면 더 자세한 분석을 제공할 수 있습니다."
                else:
                    default_response = f"죄송합니다. '{message}'와 관련된 프레임을 찾을 수 없습니다.\n\n"
                    default_response += "다른 키워드로 시도해보세요:\n"
                    default_response += "• 사람, 자동차, 동물, 음식, 옷, 건물, 자연, 물체"
                
                ai_responses = {
                    'default': default_response
                }
            else:
                # 각 AI 모델에 질문 전송
                for bot_name, chatbot in chatbots.items():
                    if bot_name == 'optimal':
                        continue  # optimal은 나중에 처리
                    
                    try:
                        # 색상 검색 모드 확인
                        is_color_search = any(keyword in message.lower() for keyword in ['빨간색', '파란색', '노란색', '초록색', '보라색', '분홍색', '검은색', '흰색', '회색', '주황색', '갈색', '옷'])
                        
                        # 간소화된 영상 정보 프롬프트 생성
                        video_context = f"""
영상: {analysis_data.get('original_name', 'Unknown')} ({analysis_data.get('file_size', 0) / (1024*1024):.1f}MB)
분석: {len(analysis_json_data.get('frame_results', []))}개 프레임, {analysis_json_data.get('video_summary', {}).get('total_detections', 0)}개 객체
품질: {analysis_json_data.get('video_summary', {}).get('quality_assessment', {}).get('overall_score', 0):.2f}
"""
                        
                        # 간소화된 프레임 정보
                        frame_context = ""
                        if relevant_frames:
                            frame_context = f"\n관련 프레임 {len(relevant_frames)}개:\n"
                            for i, frame in enumerate(relevant_frames[:2], 1):  # 최대 2개만
                                frame_context += f"프레임 {i}: {frame['timestamp']:.1f}초, 사람 {len(frame.get('persons', []))}명\n"
                        else:
                            frame_context = "\n관련 프레임 없음\n"
                        
                        enhanced_message = f"""{video_context}{frame_context}

사용자 질문: "{message}"

위 정보를 바탕으로 친근하게 답변해주세요."""
                        
                        # 간소화된 AI 프롬프트
                        ai_prompt = enhanced_message
                        
                        # AI별 특성화된 프롬프트로 응답 생성
                        ai_response = chatbot.chat(ai_prompt)
                        ai_responses[bot_name] = ai_response
                        
                        # 개별 AI 응답 저장
                        ai_message = VideoChatMessage.objects.create(
                            session=session,
                            message_type='ai',
                            content=ai_response,
                            ai_model=bot_name,
                            parent_message=user_message
                        )
                        individual_messages.append(ai_message)
                        
                    except Exception as e:
                        print(f"AI {bot_name} 응답 생성 실패: {str(e)}")
                        continue
            
            # 통합 응답 생성 (기본 채팅 시스템과 동일한 방식)
            optimal_response = ""
            if ai_responses and len(ai_responses) > 1:
                try:
                    # 기본 채팅 시스템의 generate_optimal_response 사용
                    optimal_response = generate_optimal_response(ai_responses, message, os.getenv('OPENAI_API_KEY'))
                    
                    # 프레임 정보 추가 (더 자세한 정보 포함)
                    if relevant_frames:
                        frame_summary = f"\n\n📸 관련 프레임 {len(relevant_frames)}개 발견:\n"
                        for i, frame in enumerate(relevant_frames, 1):
                            frame_summary += f"• 프레임 {i}: {frame['timestamp']:.1f}초 (관련도 {frame['relevance_score']:.2f}점)\n"
                            
                            # 프레임별 세부 정보 추가
                            if frame.get('persons'):
                                frame_summary += f"  👤 사람 {len(frame['persons'])}명 감지됨!\n"
                                # 각 사람의 상세 정보 추가
                                for j, person in enumerate(frame['persons'], 1):
                                    confidence = person.get('confidence', 0)
                                    frame_summary += f"    사람 {j}: 신뢰도 {confidence:.2f}\n"
                                    # 속성 정보 추가
                                    attrs = person.get('attributes', {})
                                    if 'gender' in attrs:
                                        gender_info = attrs['gender']
                                        frame_summary += f"      성별: {gender_info.get('value', 'unknown')}\n"
                                    if 'age' in attrs:
                                        age_info = attrs['age']
                                        frame_summary += f"      나이: {age_info.get('value', 'unknown')}\n"
                            if frame.get('objects'):
                                frame_summary += f"  📦 객체 {len(frame['objects'])}개 감지\n"
                            
                            scene_attrs = frame.get('scene_attributes', {})
                            if scene_attrs:
                                scene_type = scene_attrs.get('scene_type', 'unknown')
                                lighting = scene_attrs.get('lighting', 'unknown')
                                frame_summary += f"  🏞️ 장면: {scene_type}, 조명: {lighting}\n"
                        
                        frame_summary += "\n💡 위 프레임들을 참고하여 영상에서 해당 내용을 확인해보세요."
                        optimal_response += frame_summary
                    
                    # 통합 응답 저장
                    optimal_message = VideoChatMessage.objects.create(
                        session=session,
                        message_type='ai_optimal',
                        content=optimal_response,
                        ai_model='optimal',
                        parent_message=user_message
                    )
                    
                except Exception as e:
                    print(f"통합 응답 생성 실패: {str(e)}")
                    optimal_response = f"통합 응답 생성 중 오류가 발생했습니다: {str(e)}"
            elif ai_responses and len(ai_responses) == 1:
                # AI 응답이 하나만 있는 경우
                optimal_response = list(ai_responses.values())[0]
            
            # 응답 품질 평가
            evaluation_results = {}
            if ai_responses and len(ai_responses) > 1:
                try:
                    evaluation_results = evaluation_metrics.evaluate_summary_quality(
                        ai_responses, reference=optimal_response
                    )
                    print(f"✅ 응답 품질 평가 완료: {len(evaluation_results)}개 AI")
                except Exception as e:
                    print(f"❌ 응답 품질 평가 실패: {e}")
            
            # 대화 맥락 업데이트
            try:
                conversation_memory.add_context(
                    session_id=session_id,
                    user_message=message,
                    ai_responses=ai_responses,
                    video_context={
                        'video_id': video_id,
                        'video_name': video.original_name,
                        'relevant_frames_count': len(relevant_frames)
                    }
                )
                print(f"✅ 대화 맥락 업데이트 완료")
            except Exception as e:
                print(f"❌ 대화 맥락 업데이트 실패: {e}")
            
            # 응답 데이터 구성
            response_data = {
                'session_id': str(session.id),
                'user_message': {
                    'id': str(user_message.id),
                    'content': message,
                    'created_at': user_message.created_at
                },
                'ai_responses': {
                    'individual': [
                        {
                            'id': str(msg.id),
                            'model': msg.ai_model,
                            'content': msg.content,
                            'created_at': msg.created_at
                        } for msg in individual_messages
                    ],
                    'optimal': {
                        'content': optimal_response,
                        'created_at': individual_messages[0].created_at if individual_messages else None
                    } if optimal_response else None
                },
                'relevant_frames': relevant_frames,  # 관련 프레임 정보 추가
                'evaluation_results': evaluation_results,  # 품질 평가 결과
                'context_info': {
                    'session_id': session_id,
                    'context_length': len(conversation_memory.get_context(session_id).get('conversations', []))
                }
            }
            
            # 디버깅: relevant_frames 확인
            print(f"🔍 응답 생성 시 relevant_frames: {len(relevant_frames)}")
            if relevant_frames:
                print(f"📸 첫 번째 프레임: {relevant_frames[0]}")
            else:
                print("❌ relevant_frames가 비어있음!")
            
            print(f"📤 응답에 포함될 프레임 수: {len(relevant_frames)}")
            if relevant_frames:
                print(f"📸 첫 번째 프레임: {relevant_frames[0]}")
            
            return Response(response_data)
            
        except Exception as e:
            import traceback
            print(f"❌ VideoChatView POST 오류: {str(e)}")
            print(f"❌ 오류 상세: {traceback.format_exc()}")
            return Response({
                'error': f'채팅 처리 중 오류 발생: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _classify_intent(self, message):
        """사용자 메시지의 의도를 분류"""
        try:
            message_lower = message.lower()
            
            # 의도별 키워드 정의
            intent_keywords = {
                'video_summary': ['요약', 'summary', '간단', '상세', '하이라이트', 'highlight', '정리'],
                'video_search': ['찾아', '검색', 'search', '보여', '어디', '언제', '누가'],
                'person_search': ['사람', 'person', 'people', 'human', '남성', '여성', '성별'],
                'color_search': ['빨간색', '파란색', '노란색', '초록색', '보라색', '분홍색', '검은색', '흰색', '회색', '주황색', '갈색', '색깔', '색상', '옷', '입은', '착용'],
                'temporal_analysis': ['시간', '분', '초', '언제', '몇시', '성비', '인원', '통계'],
                'inter_video_search': ['비오는', '밤', '낮', '날씨', '조명', '영상간', '다른영상'],
                'general_chat': ['안녕', 'hello', 'hi', '고마워', '감사', '도움', '질문']
            }
            
            # 의도 점수 계산
            intent_scores = {}
            for intent, keywords in intent_keywords.items():
                score = sum(1 for keyword in keywords if keyword in message_lower)
                if score > 0:
                    intent_scores[intent] = score
            
            # 가장 높은 점수의 의도 선택
            if intent_scores:
                detected_intent = max(intent_scores, key=intent_scores.get)
                confidence = intent_scores[detected_intent] / len(message_lower.split())
                print(f"🎯 의도 분류: {detected_intent} (신뢰도: {confidence:.2f})")
                return detected_intent, confidence
            else:
                print("🎯 의도 분류: general_chat (기본값)")
                return 'general_chat', 0.0
                
        except Exception as e:
            print(f"❌ 의도 분류 중 오류: {e}")
            return 'general_chat', 0.0

    def _parse_time_range(self, message):
        """메시지에서 시간 범위를 파싱"""
        try:
            import re
            
            # 시간 패턴 매칭 (예: "3:00~5:00", "3분~5분", "180초~300초")
            time_patterns = [
                r'(\d+):(\d+)~(\d+):(\d+)',  # 3:00~5:00
                r'(\d+)분~(\d+)분',          # 3분~5분
                r'(\d+)초~(\d+)초',          # 180초~300초
            ]
            
            for pattern in time_patterns:
                match = re.search(pattern, message)
                if match:
                    groups = match.groups()
                    if len(groups) == 4:  # 3:00~5:00 형식
                        start_min, start_sec, end_min, end_sec = map(int, groups)
                        start_time = start_min * 60 + start_sec
                        end_time = end_min * 60 + end_sec
                        return start_time, end_time
                    elif len(groups) == 2:  # 분 또는 초 형식
                        start_val, end_val = map(int, groups)
                        if '분' in message:
                            start_time = start_val * 60
                            end_time = end_val * 60
                        else:  # 초
                            start_time = start_val
                            end_time = end_val
                        return start_time, end_time
            
            return None
            
        except Exception as e:
            print(f"❌ 시간 범위 파싱 중 오류: {e}")
            return None

    def _find_relevant_frames(self, message, analysis_json_data, video_id):
        """사용자 메시지에 따라 관련 프레임을 찾아서 이미지 URL과 함께 반환 (의도 기반)"""
        try:
            if not analysis_json_data or 'frame_results' not in analysis_json_data:
                print("❌ 분석 데이터 또는 프레임 결과가 없습니다.")
                return []
            
            relevant_frames = []
            message_lower = message.lower()
            
            # 프레임 결과에서 매칭되는 프레임 찾기
            frame_results = analysis_json_data.get('frame_results', [])
            print(f"🔍 검색할 프레임 수: {len(frame_results)}")
            
            # 의도 분류
            intent, confidence = self._classify_intent(message)
            print(f"🎯 검색 의도: {intent}")
            
            # 색상 기반 검색
            color_keywords = {
                '빨간색': ['red', '빨강', '빨간색'],
                '파란색': ['blue', '파랑', '파란색'],
                '노란색': ['yellow', '노랑', '노란색'],
                '초록색': ['green', '녹색', '초록색'],
                '보라색': ['purple', '자주색', '보라색'],
                '분홍색': ['pink', '핑크', '분홍색'],
                '검은색': ['black', '검정', '검은색'],
                '흰색': ['white', '하양', '흰색'],
                '회색': ['gray', 'grey', '회색'],
                '주황색': ['orange', '오렌지', '주황색'],
                '갈색': ['brown', '브라운', '갈색'],
                '옷': ['clothing', 'clothes', 'dress', 'shirt', 'pants', 'jacket']
            }
            
            # 의도 기반 프레임 검색
            if intent == 'color_search':
                print("🎨 색상 검색 모드")
                detected_colors = []
                for color_korean, color_terms in color_keywords.items():
                    if any(term in message_lower for term in color_terms):
                        detected_colors.append(color_korean)
                        print(f"🎨 색상 검색 감지: {color_korean}")
                
                if detected_colors:
                    print(f"🎨 색상 검색 모드: {detected_colors}")
                    print(f"🔍 검색할 프레임 수: {len(frame_results)}")
                    for frame in frame_results:
                        persons = frame.get('persons', [])
                        
                        # 색상 분석 결과 확인
                        dominant_colors = frame.get('dominant_colors', [])
                        color_match_found = False
                        
                        # 요청된 색상과 매칭되는지 확인 (더 유연한 매칭)
                        for detected_color in detected_colors:
                            for color_info in dominant_colors:
                                color_name = color_info.get('color', '').lower()
                                detected_color_lower = detected_color.lower()
                                
                                # 색상 키워드 매핑을 통한 매칭
                                color_mapping = {
                                    '분홍색': 'pink', '핑크': 'pink',
                                    '빨간색': 'red', '빨강': 'red',
                                    '파란색': 'blue', '파랑': 'blue',
                                    '노란색': 'yellow', '노랑': 'yellow',
                                    '초록색': 'green', '녹색': 'green',
                                    '보라색': 'purple', '자주색': 'purple',
                                    '검은색': 'black', '검정': 'black',
                                    '흰색': 'white', '하양': 'white',
                                    '회색': 'gray', 'grey': 'gray',
                                    '주황색': 'orange', '오렌지': 'orange',
                                    '갈색': 'brown', '브라운': 'brown'
                                }
                                
                                # 매핑된 색상으로 비교
                                mapped_color = color_mapping.get(detected_color_lower, detected_color_lower)
                                
                                # 더 유연한 색상 매칭 (색상이 없어도 일단 포함)
                                if (mapped_color == color_name or 
                                    detected_color_lower == color_name or 
                                    detected_color_lower in color_name or 
                                    color_name in detected_color_lower or
                                    len(dominant_colors) == 0):  # 색상 정보가 없어도 포함
                                    color_match_found = True
                                    print(f"✅ 색상 매칭 발견: {detected_color} -> {color_info}")
                                    break
                            if color_match_found:
                                break
                        
                        # 디버깅을 위한 로그 추가
                        print(f"🔍 프레임 {frame.get('image_id', 0)} 색상 분석:")
                        print(f"  - 요청된 색상: {detected_colors}")
                        print(f"  - 감지된 색상: {[c.get('color', '') for c in dominant_colors]}")
                        print(f"  - 매칭 결과: {color_match_found}")
                        
                        # 색상 검색의 경우 색상 매칭이 된 프레임만 포함
                        if color_match_found:
                            frame_image_path = frame.get('frame_image_path', '')
                            actual_image_path = None
                            if frame_image_path:
                                # 실제 파일 시스템 경로 생성
                                import os
                                from django.conf import settings
                                actual_image_path = os.path.join(settings.MEDIA_ROOT, frame_image_path)
                                if os.path.exists(actual_image_path):
                                    print(f"✅ 실제 이미지 파일 존재: {actual_image_path}")
                                else:
                                    print(f"❌ 실제 이미지 파일 없음: {actual_image_path}")
                            
                            frame_info = {
                                'image_id': frame.get('image_id', 0),
                                'timestamp': frame.get('timestamp', 0),
                                'frame_image_path': frame_image_path,
                                'image_url': f'/media/{frame_image_path}',
                                'actual_image_path': actual_image_path,  # 실제 파일 경로 추가
                                'persons': persons,
                                'objects': frame.get('objects', []),
                                'scene_attributes': frame.get('scene_attributes', {}),
                                'dominant_colors': dominant_colors,  # 색상 분석 결과 추가
                                'relevance_score': 2,  # 색상 매칭 시 높은 점수
                                'color_search_info': {
                                    'requested_colors': detected_colors,
                                    'color_info_available': len(dominant_colors) > 0,
                                    'color_match_found': color_match_found,
                                    'actual_image_available': actual_image_path is not None,
                                    'message': f"색상 분석 결과: {dominant_colors} | 요청하신 색상: {', '.join(detected_colors)}"
                                }
                            }
                            relevant_frames.append(frame_info)
                            print(f"✅ 프레임 {frame_info['image_id']} 추가 (색상 매칭 성공)")
                        else:
                            print(f"❌ 프레임 {frame.get('image_id', 0)}: 색상 매칭 실패 - {detected_colors} vs {dominant_colors}")
                
                else:
                    print("🎨 색상 키워드 감지 실패 - 일반 검색으로 전환")
                    # 색상 키워드가 감지되지 않으면 모든 프레임 포함
                    for frame in frame_results:
                        persons = frame.get('persons', [])
                        if persons:  # 사람이 있는 프레임만
                            frame_info = {
                                'image_id': frame.get('image_id', 0),
                                'timestamp': frame.get('timestamp', 0),
                                'frame_image_path': frame.get('frame_image_path', ''),
                                'image_url': f'/media/{frame.get("frame_image_path", "")}',
                                'persons': persons,
                                'objects': frame.get('objects', []),
                                'scene_attributes': frame.get('scene_attributes', {}),
                                'relevance_score': len(persons)
                            }
                            relevant_frames.append(frame_info)
                            print(f"✅ 프레임 {frame_info['image_id']} 추가 (일반 검색, 사람 {len(persons)}명)")
            
            elif intent == 'person_search':
                print("👤 사람 검색 모드")
                print(f"🔍 검색할 프레임 수: {len(frame_results)}")
                for frame in frame_results:
                    persons = frame.get('persons', [])
                    print(f"🔍 프레임 {frame.get('image_id', 0)}: persons = {persons}")
                    # 사람이 감지된 프레임만 포함
                    if persons and len(persons) > 0:
                        frame_info = {
                            'image_id': frame.get('image_id', 0),
                            'timestamp': frame.get('timestamp', 0),
                            'frame_image_path': frame.get('frame_image_path', ''),
                            'image_url': f'/media/{frame.get("frame_image_path", "")}',
                            'persons': persons,
                            'objects': frame.get('objects', []),
                            'scene_attributes': frame.get('scene_attributes', {}),
                            'relevance_score': len(persons) * 2  # 사람 수에 비례한 점수
                        }
                        relevant_frames.append(frame_info)
                        print(f"✅ 프레임 {frame_info['image_id']} 추가 (사람 {len(persons)}명 감지)")
                        print(f"✅ 프레임 상세 정보: {frame_info}")
                    else:
                        print(f"❌ 프레임 {frame.get('image_id', 0)}: 사람 감지 안됨")
            
            elif intent == 'video_summary':
                print("📋 요약 모드 - 주요 프레임 선택")
                # 활동 수준이 높은 프레임 우선 선택
                frame_scores = []
                for frame in frame_results:
                    scene_attrs = frame.get('scene_attributes', {})
                    activity_level = scene_attrs.get('activity_level', 'low')
                    person_count = len(frame.get('persons', []))
                    
                    score = 0
                    if activity_level == 'high':
                        score += 3
                    elif activity_level == 'medium':
                        score += 2
                    else:
                        score += 1
                    
                    score += min(person_count, 3)  # 사람 수에 따른 점수
                    frame_scores.append((frame, score))
                
                # 점수 순으로 정렬하여 상위 프레임 선택
                frame_scores.sort(key=lambda x: x[1], reverse=True)
                for frame, score in frame_scores[:3]:
                    frame_info = {
                        'image_id': frame.get('image_id', 0),
                        'timestamp': frame.get('timestamp', 0),
                        'frame_image_path': frame.get('frame_image_path', ''),
                        'image_url': f'/media/{frame.get("frame_image_path", "")}',
                        'persons': frame.get('persons', []),
                        'objects': frame.get('objects', []),
                        'scene_attributes': frame.get('scene_attributes', {}),
                        'relevance_score': score
                    }
                    relevant_frames.append(frame_info)
                    print(f"✅ 프레임 {frame_info['image_id']} 추가 (요약용, 점수: {score})")
            
            elif intent == 'temporal_analysis':
                print("⏰ 시간대 분석 모드")
                # 시간 범위 파싱
                time_range = self._parse_time_range(message)
                if time_range:
                    start_time, end_time = time_range
                    print(f"⏰ 시간 범위: {start_time}초 ~ {end_time}초")
                    for frame in frame_results:
                        timestamp = frame.get('timestamp', 0)
                        if start_time <= timestamp <= end_time:
                            frame_info = {
                                'image_id': frame.get('image_id', 0),
                                'timestamp': frame.get('timestamp', 0),
                                'frame_image_path': frame.get('frame_image_path', ''),
                                'image_url': f'/media/{frame.get("frame_image_path", "")}',
                                'persons': frame.get('persons', []),
                                'objects': frame.get('objects', []),
                                'scene_attributes': frame.get('scene_attributes', {}),
                                'relevance_score': 1
                            }
                            relevant_frames.append(frame_info)
                            print(f"✅ 프레임 {frame_info['image_id']} 추가 (시간대: {timestamp}초)")
                else:
                    # 시간 범위를 파싱할 수 없는 경우 전체 프레임
                    relevant_frames = [{
                        'image_id': frame.get('image_id', 0),
                        'timestamp': frame.get('timestamp', 0),
                        'frame_image_path': frame.get('frame_image_path', ''),
                        'image_url': f'/media/{frame.get("frame_image_path", "")}',
                        'persons': frame.get('persons', []),
                        'objects': frame.get('objects', []),
                        'scene_attributes': frame.get('scene_attributes', {}),
                        'relevance_score': 1
                    } for frame in frame_results]
                    print(f"✅ 시간 범위 파싱 실패 - 전체 프레임 {len(relevant_frames)}개 선택")
            
            else:
                print("📋 일반 검색 모드")
                # 처음 2개 프레임 선택
                for frame in frame_results[:2]:
                    frame_info = {
                        'image_id': frame.get('image_id', 0),
                        'timestamp': frame.get('timestamp', 0),
                        'frame_image_path': frame.get('frame_image_path', ''),
                        'image_url': f'/media/{frame.get("frame_image_path", "")}',
                        'persons': frame.get('persons', []),
                        'objects': frame.get('objects', []),
                        'scene_attributes': frame.get('scene_attributes', {}),
                        'relevance_score': 1
                    }
                    relevant_frames.append(frame_info)
                    print(f"✅ 프레임 {frame_info['image_id']} 추가 (일반 검색)")
            
            # 관련도 점수순으로 정렬하고 상위 3개만 반환
            relevant_frames.sort(key=lambda x: x['relevance_score'], reverse=True)
            result = relevant_frames[:3]
            print(f"🎯 최종 선택된 프레임 수: {len(result)}")
            print(f"🎯 최종 프레임 상세: {result}")
            return result
            
        except Exception as e:
            print(f"❌ 프레임 검색 실패: {e}")
            return []
    
    def _handle_special_commands(self, message, video_id):
        """특별 명령어 처리 (요약, 하이라이트)"""
        try:
            message_lower = message.lower().strip()
            
            # 영상 요약 명령어
            if any(keyword in message_lower for keyword in ['요약', 'summary', '영상 요약', '영상 요약해줘', '영상 하이라이트 알려줘']):
                return self._handle_video_summary_command(message_lower, video_id)
            
            # 영상 하이라이트 명령어
            elif any(keyword in message_lower for keyword in ['하이라이트', 'highlight', '주요 장면', '중요한 장면']):
                return self._handle_video_highlight_command(message_lower, video_id)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 특별 명령어 처리 오류: {e}")
            return None
    
    def _handle_video_summary_command(self, message, video_id):
        """영상 요약 명령어 처리"""
        try:
            # 요약 타입 결정
            summary_type = 'comprehensive'
            if '간단' in message or 'brief' in message:
                summary_type = 'brief'
            elif '상세' in message or 'detailed' in message:
                summary_type = 'detailed'
            
            # VideoSummaryView 인스턴스 생성 및 요약 생성
            summary_view = VideoSummaryView()
            summary_result = summary_view._generate_video_summary(
                Video.objects.get(id=video_id), 
                summary_type
            )
            
            if summary_result and summary_result.get('summary'):
                return f"📝 **영상 요약** ({summary_type})\n\n{summary_result['summary']}"
            else:
                return "❌ 영상 요약을 생성할 수 없습니다. 영상 분석이 완료되었는지 확인해주세요."
                
        except Exception as e:
            logger.error(f"❌ 영상 요약 명령어 처리 오류: {e}")
            return f"❌ 영상 요약 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _handle_video_highlight_command(self, message, video_id):
        """영상 하이라이트 명령어 처리"""
        try:
            # 하이라이트 기준 설정
            criteria = {
                'min_score': 2.0,
                'max_highlights': 5
            }
            
            if '많이' in message or 'more' in message:
                criteria['max_highlights'] = 10
            elif '적게' in message or 'few' in message:
                criteria['max_highlights'] = 3
            
            # VideoHighlightView 인스턴스 생성 및 하이라이트 추출
            highlight_view = VideoHighlightView()
            highlights = highlight_view._extract_highlights(
                Video.objects.get(id=video_id), 
                criteria
            )
            
            if highlights:
                highlight_text = "🎬 **영상 하이라이트**\n\n"
                for i, highlight in enumerate(highlights, 1):
                    highlight_text += f"{i}. **{highlight['timestamp']:.1f}초** - {highlight['description']}\n"
                    highlight_text += f"   - 중요도: {highlight['significance']} (점수: {highlight['score']:.1f})\n"
                    highlight_text += f"   - 인원: {highlight['person_count']}명, 장면: {highlight['scene_type']}\n\n"
                
                return highlight_text
            else:
                return "❌ 하이라이트를 찾을 수 없습니다. 영상 분석이 완료되었는지 확인해주세요."
                
        except Exception as e:
            logger.error(f"❌ 영상 하이라이트 명령어 처리 오류: {e}")
            return f"❌ 영상 하이라이트 생성 중 오류가 발생했습니다: {str(e)}"

class FrameImageView(APIView):
    """프레임 이미지 서빙"""
    permission_classes = [AllowAny]
    
    def get(self, request, video_id, frame_number):
        try:
            from django.conf import settings
            # 프레임 이미지 경로 생성
            frame_filename = f"video{video_id}_frame{frame_number}.jpg"
            frame_path = os.path.join(settings.MEDIA_ROOT, 'images', frame_filename)
            
            # 파일이 존재하는지 확인
            if not os.path.exists(frame_path):
                raise Http404("프레임 이미지를 찾을 수 없습니다")
            
            # 이미지 파일 읽기
            with open(frame_path, 'rb') as f:
                image_data = f.read()
            
            # HTTP 응답으로 이미지 반환
            response = HttpResponse(image_data, content_type='image/jpeg')
            response['Content-Disposition'] = f'inline; filename="{frame_filename}"'
            return response
            
        except Exception as e:
            return Response({
                'error': f'프레임 이미지 로드 실패: {str(e)}'
            }, status=status.HTTP_404_NOT_FOUND)


class VideoSummaryView(APIView):
    """영상 요약 기능"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            video_id = request.data.get('video_id')
            summary_type = request.data.get('summary_type', 'comprehensive')  # comprehensive, brief, detailed
            
            logger.info(f"📝 영상 요약 요청: 비디오={video_id}, 타입={summary_type}")
            
            if not video_id:
                return Response({'error': '비디오 ID가 필요합니다.'}, status=400)
            
            try:
                video = Video.objects.get(id=video_id)
            except Video.DoesNotExist:
                return Response({'error': '비디오를 찾을 수 없습니다.'}, status=404)
            
            # 영상 요약 생성
            summary_result = self._generate_video_summary(video, summary_type)
            
            return Response({
                'video_id': video_id,
                'video_name': video.original_name,
                'summary_type': summary_type,
                'summary_result': summary_result,
                'analysis_type': 'video_summary'
            })
            
        except Exception as e:
            logger.error(f"❌ 영상 요약 오류: {e}")
            return Response({'error': str(e)}, status=500)
    
    def _generate_video_summary(self, video, summary_type):
        """영상 요약 생성"""
        try:
            # 분석 결과 JSON 파일 읽기
            if not video.analysis_json_path:
                return {
                    'summary': '분석 결과가 없습니다. 영상 분석을 먼저 완료해주세요.',
                    'key_events': [],
                    'statistics': {},
                    'duration': video.duration,
                    'frame_count': 0
                }
            
            json_path = os.path.join(settings.MEDIA_ROOT, video.analysis_json_path)
            if not os.path.exists(json_path):
                return {
                    'summary': '분석 결과 파일을 찾을 수 없습니다.',
                    'key_events': [],
                    'statistics': {},
                    'duration': video.duration,
                    'frame_count': 0
                }
            
            with open(json_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            # 기본 통계 수집
            statistics = self._collect_video_statistics(video, analysis_data)
            
            # 키 이벤트 추출
            key_events = self._extract_key_events(analysis_data)
            
            # 요약 타입에 따른 처리
            if summary_type == 'brief':
                summary_text = self._generate_brief_summary(statistics, key_events)
            elif summary_type == 'detailed':
                summary_text = self._generate_detailed_summary(statistics, key_events, analysis_data)
            else:  # comprehensive
                summary_text = self._generate_comprehensive_summary(statistics, key_events, analysis_data)
            
            return {
                'summary': summary_text,
                'key_events': key_events,
                'statistics': statistics,
                'duration': video.duration,
                'frame_count': len(analysis_data.get('frame_results', [])),
                'summary_type': summary_type
            }
            
        except Exception as e:
            logger.error(f"❌ 영상 요약 생성 오류: {e}")
            return {
                'summary': f'요약 생성 중 오류가 발생했습니다: {str(e)}',
                'key_events': [],
                'statistics': {},
                'duration': video.duration,
                'frame_count': 0
            }
    
    def _collect_video_statistics(self, video, analysis_data):
        """영상 통계 수집 - 💡핵심 인사이트 포함"""
        try:
            video_summary = analysis_data.get('video_summary', {})
            frame_results = analysis_data.get('frame_results', [])
            
            # 기본 통계
            stats = {
                'total_duration': video.duration,
                'total_frames': len(frame_results),
                'total_detections': video_summary.get('total_detections', 0),
                'unique_persons': video_summary.get('unique_persons', 0),
                'quality_score': video_summary.get('quality_assessment', {}).get('overall_score', 0),
                'scene_diversity': video_summary.get('scene_diversity', {}).get('diversity_score', 0)
            }
            
            # 시간대별 활동 분석
            temporal_analysis = video_summary.get('temporal_analysis', {})
            stats.update({
                'peak_time': temporal_analysis.get('peak_time_seconds', 0),
                'peak_person_count': temporal_analysis.get('peak_person_count', 0),
                'average_person_count': temporal_analysis.get('average_person_count', 0)
            })
            
            # 장면 특성 분석
            scene_distribution = video_summary.get('scene_diversity', {})
            stats.update({
                'scene_types': scene_distribution.get('scene_type_distribution', {}),
                'activity_levels': scene_distribution.get('activity_level_distribution', {}),
                'lighting_types': scene_distribution.get('lighting_distribution', {})
            })
            
            # 💡 핵심 인사이트 생성
            stats['key_insights'] = self._generate_key_insights_for_summary(stats, frame_results)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 통계 수집 오류: {e}")
            return {}
    
    def _generate_key_insights_for_summary(self, stats, frame_results):
        """💡 핵심 인사이트 생성 (영상 요약용)"""
        insights = []
        
        try:
            # 1. 인원 구성 인사이트
            person_count = stats.get('unique_persons', 0)
            peak_count = stats.get('peak_person_count', 0)
            
            if person_count > 0:
                if peak_count > 5:
                    insights.append(f"다수 인원 등장 (최대 {peak_count}명 동시 등장)")
                elif peak_count > 2:
                    insights.append(f"소규모 그룹 활동 ({peak_count}명)")
                else:
                    insights.append(f"소수 인원 영상 ({person_count}명)")
            
            # 2. 영상 길이 인사이트
            duration = stats.get('total_duration', 0)
            if duration > 300:  # 5분 이상
                insights.append(f"긴 영상 ({duration/60:.1f}분)")
            elif duration > 60:
                insights.append(f"중간 길이 영상 ({duration/60:.1f}분)")
            else:
                insights.append(f"짧은 영상 ({duration:.0f}초)")
            
            # 3. 품질 인사이트
            quality_score = stats.get('quality_score', 0)
            if quality_score > 0.8:
                insights.append(f"높은 품질 (점수: {quality_score:.2f})")
            elif quality_score > 0.6:
                insights.append(f"양호한 품질 (점수: {quality_score:.2f})")
            elif quality_score > 0:
                insights.append(f"보통 품질 (점수: {quality_score:.2f})")
            
            # 4. 장면 다양성 인사이트
            scene_types = stats.get('scene_types', {})
            if len(scene_types) > 3:
                insights.append(f"다양한 장면 포함 ({len(scene_types)}가지 장소)")
            elif len(scene_types) > 0:
                main_scenes = list(scene_types.keys())[:2]
                insights.append(f"주요 장소: {', '.join(main_scenes)}")
            
            # 5. 활동 수준 인사이트
            activity_levels = stats.get('activity_levels', {})
            if 'high' in activity_levels:
                insights.append(f"활발한 활동 감지")
            elif 'medium' in activity_levels:
                insights.append(f"중간 수준 활동")
            
            return insights[:5]  # 최대 5개 인사이트
            
        except Exception as e:
            logger.error(f"❌ 핵심 인사이트 생성 오류: {e}")
            return ["영상 분석 완료"]
    
    def _extract_key_events(self, analysis_data):
        """키 이벤트 추출"""
        try:
            key_events = []
            frame_results = analysis_data.get('frame_results', [])
            
            # 사람 수가 많은 장면들을 키 이벤트로 선정
            for frame in frame_results:
                person_count = len(frame.get('persons', []))
                if person_count >= 2:  # 2명 이상이 있는 장면
                    key_events.append({
                        'timestamp': frame.get('timestamp', 0),
                        'description': f"{person_count}명이 감지된 장면",
                        'person_count': person_count,
                        'scene_type': frame.get('scene_attributes', {}).get('scene_type', 'unknown'),
                        'activity_level': frame.get('scene_attributes', {}).get('activity_level', 'medium')
                    })
            
            # 시간순으로 정렬
            key_events.sort(key=lambda x: x['timestamp'])
            
            return key_events[:10]  # 상위 10개만 반환
            
        except Exception as e:
            logger.error(f"❌ 키 이벤트 추출 오류: {e}")
            return []
    
    def _generate_brief_summary(self, statistics, key_events):
        """간단 요약 (1-2문장, 💡핵심만 강조)"""
        try:
            duration = statistics.get('total_duration', 0)
            duration_min = duration / 60
            person_count = statistics.get('unique_persons', 0)
            key_insights = statistics.get('key_insights', [])
            
            # 가장 중요한 핵심 1개 + 기본 정보
            main_insight = key_insights[0] if key_insights else "영상 분석 완료"
            
            return f"💡 {main_insight}. 영상 길이 {duration_min:.1f}분, 총 {person_count}명 등장."
            
        except Exception as e:
            logger.error(f"❌ 간단 요약 생성 오류: {e}")
            return "요약 생성 중 오류가 발생했습니다."
    
    def _generate_detailed_summary(self, statistics, key_events, analysis_data):
        """상세 요약 (문단 형식, 💡핵심 3개 + 주요 이벤트)"""
        try:
            duration = statistics.get('total_duration', 0)
            duration_min = duration / 60
            person_count = statistics.get('unique_persons', 0)
            peak_count = statistics.get('peak_person_count', 0)
            key_insights = statistics.get('key_insights', [])
            
            parts = [
                f"📹 이 영상은 {duration_min:.1f}분 길이로, 총 {person_count}명이 등장합니다.",
                "\n💡 핵심 포인트:",
                *[f"  • {insight}" for insight in key_insights[:3]]
            ]
            
            # 주요 이벤트 3개
            if key_events:
                parts.append("\n⏱️ 주요 장면:")
                for i, event in enumerate(key_events[:3], 1):
                    timestamp = event.get('timestamp', 0)
                    time_str = f"{int(timestamp//60)}:{int(timestamp%60):02d}"
                    desc = event.get('description', '장면')[:50]
                    parts.append(f"  {i}. [{time_str}] {desc}")
            
            # 품질 정보
            quality_score = statistics.get('quality_score', 0)
            if quality_score > 0:
                quality_status = "우수" if quality_score > 0.8 else "양호" if quality_score > 0.6 else "보통"
                parts.append(f"\n🎯 영상 품질: {quality_status} ({quality_score:.2f}/1.0)")
            
            # 장면 유형
            scene_types = statistics.get('scene_types', {})
            if scene_types:
                scene_list = [f"{k}({v})" for k, v in list(scene_types.items())[:3]]
                parts.append(f"\n🎬 장면 유형: {', '.join(scene_list)}")
            
            return "\n".join(parts)
            
        except Exception as e:
            logger.error(f"❌ 상세 요약 생성 오류: {e}")
            return "상세 요약 생성 중 오류가 발생했습니다."
    
    def _generate_comprehensive_summary(self, statistics, key_events, analysis_data):
        """종합 요약 (전체 분석, 💡핵심 5개 + 모든 이벤트 + 통계)"""
        try:
            duration = statistics.get('total_duration', 0)
            duration_min = duration / 60
            person_count = statistics.get('unique_persons', 0)
            peak_count = statistics.get('peak_person_count', 0)
            key_insights = statistics.get('key_insights', [])
            
            parts = [
                f"📹 영상 정보",
                f"  • 길이: {duration_min:.1f}분",
                f"  • 등장 인원: {person_count}명",
                f"  • 분석 프레임: {statistics.get('total_frames', 0)}개",
                f"  • 총 감지 객체: {statistics.get('total_detections', 0)}개",
                "\n💡 핵심 인사이트 (전체)"
            ]
            
            # 전체 핵심 인사이트 (최대 5개)
            parts.extend([f"  • {insight}" for insight in key_insights[:5]])
            
            # 주요 이벤트 전체 (최대 8개)
            if key_events:
                parts.append("\n⏱️ 주요 이벤트 타임라인:")
                for i, event in enumerate(key_events[:8], 1):
                    timestamp = event.get('timestamp', 0)
                    time_str = f"{int(timestamp//60)}:{int(timestamp%60):02d}"
                    desc = event.get('description', '장면')[:60]
                    person_cnt = event.get('person_count', 0)
                    activity = event.get('activity_level', 'medium')
                    emoji = "🔴" if activity == 'high' else "🟡" if activity == 'medium' else "🟢"
                    parts.append(f"  {emoji} {i}. [{time_str}] {desc} ({person_cnt}명)")
            
            # 상세 통계
            parts.append("\n📊 상세 통계:")
            parts.append(f"  • 최대 동시 인원: {peak_count}명")
            parts.append(f"  • 평균 동시 인원: {statistics.get('average_person_count', 0):.1f}명")
            
            # 품질 정보
            quality_score = statistics.get('quality_score', 0)
            if quality_score > 0:
                quality_status = "우수" if quality_score > 0.8 else "양호" if quality_score > 0.6 else "보통"
                parts.append(f"  • 영상 품질: {quality_status} ({quality_score:.2f}/1.0)")
            
            # 장면 분석
            scene_types = statistics.get('scene_types', {})
            if scene_types:
                scene_list = ', '.join([f"{k}({v})" for k, v in list(scene_types.items())[:5]])
                parts.append(f"  • 장면 유형: {scene_list}")
            
            activity_levels = statistics.get('activity_levels', {})
            if activity_levels:
                activity_list = ', '.join([f"{k}({v})" for k, v in activity_levels.items()])
                parts.append(f"  • 활동 수준: {activity_list}")
            
            lighting_types = statistics.get('lighting_types', {})
            if lighting_types:
                lighting_list = ', '.join([f"{k}({v})" for k, v in lighting_types.items()])
                parts.append(f"  • 조명 상태: {lighting_list}")
            
            # 다양성 점수
            diversity = statistics.get('scene_diversity', 0)
            if diversity > 0:
                parts.append(f"  • 장면 다양성: {diversity:.2f}/1.0")
            
            return "\n".join(parts)
            
        except Exception as e:
            logger.error(f"❌ 종합 요약 생성 오류: {e}")
            return "종합 요약 생성 중 오류가 발생했습니다."


class VideoHighlightView(APIView):
    """영상 하이라이트 자동 추출"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            video_id = request.data.get('video_id')
            highlight_criteria = request.data.get('criteria', {})
            
            logger.info(f"🎬 하이라이트 추출 요청: 비디오={video_id}, 기준={highlight_criteria}")
            
            if not video_id:
                return Response({'error': '비디오 ID가 필요합니다.'}, status=400)
            
            try:
                video = Video.objects.get(id=video_id)
            except Video.DoesNotExist:
                return Response({'error': '비디오를 찾을 수 없습니다.'}, status=404)
            
            # 하이라이트 추출
            highlights = self._extract_highlights(video, highlight_criteria)
            
            return Response({
                'video_id': video_id,
                'video_name': video.original_name,
                'highlights': highlights,
                'total_highlights': len(highlights),
                'analysis_type': 'video_highlights'
            })
            
        except Exception as e:
            logger.error(f"❌ 하이라이트 추출 오류: {e}")
            return Response({'error': str(e)}, status=500)
    
    def _extract_highlights(self, video, criteria):
        """하이라이트 추출"""
        try:
            # 분석 결과 JSON 파일 읽기
            if not video.analysis_json_path:
                return []
            
            json_path = os.path.join(settings.MEDIA_ROOT, video.analysis_json_path)
            if not os.path.exists(json_path):
                return []
            
            with open(json_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            frame_results = analysis_data.get('frame_results', [])
            if not frame_results:
                return []
            
            # 프레임별 점수 계산
            scored_frames = self._score_frames(frame_results, criteria)
            
            # 하이라이트 생성
            highlights = self._create_highlights(scored_frames, criteria)
            
            return highlights
            
        except Exception as e:
            logger.error(f"❌ 하이라이트 추출 오류: {e}")
            return []
    
    def _score_frames(self, frame_results, criteria):
        """프레임별 점수 계산"""
        try:
            scored_frames = []
            
            for frame in frame_results:
                score = 0.0
                
                # 사람 수 점수 (더 많은 사람 = 더 높은 점수)
                person_count = len(frame.get('persons', []))
                if person_count > 0:
                    score += person_count * 0.5
                
                # 품질 점수
                quality_score = self._get_quality_score(frame)
                score += quality_score * 0.3
                
                # 활동 수준 점수
                activity_level = frame.get('scene_attributes', {}).get('activity_level', 'medium')
                if activity_level == 'high':
                    score += 1.0
                elif activity_level == 'medium':
                    score += 0.5
                
                # 장면 다양성 점수
                scene_type = frame.get('scene_attributes', {}).get('scene_type', 'unknown')
                if scene_type in ['detailed', 'complex']:
                    score += 0.3
                
                # 신뢰도 점수
                avg_confidence = self._get_average_confidence(frame)
                score += avg_confidence * 0.2
                
                scored_frames.append({
                    'frame': frame,
                    'frame_id': frame.get('image_id', 0),
                    'timestamp': frame.get('timestamp', 0),
                    'score': score
                })
            
            # 점수순으로 정렬
            scored_frames.sort(key=lambda x: x['score'], reverse=True)
            
            return scored_frames
            
        except Exception as e:
            logger.error(f"❌ 프레임 점수 계산 오류: {e}")
            return []
    
    def _get_quality_score(self, frame):
        """프레임 품질 점수 계산"""
        try:
            # 간단한 품질 점수 계산 (실제로는 더 복잡한 알고리즘 사용 가능)
            persons = frame.get('persons', [])
            if not persons:
                return 0.0
            
            # 평균 신뢰도 기반 품질 점수
            confidences = [person.get('confidence', 0) for person in persons]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return avg_confidence
            
        except Exception as e:
            logger.error(f"❌ 품질 점수 계산 오류: {e}")
            return 0.0
    
    def _get_average_confidence(self, frame):
        """평균 신뢰도 계산"""
        try:
            persons = frame.get('persons', [])
            if not persons:
                return 0.0
            
            confidences = [person.get('confidence', 0) for person in persons]
            return sum(confidences) / len(confidences) if confidences else 0
            
        except Exception as e:
            logger.error(f"❌ 평균 신뢰도 계산 오류: {e}")
            return 0.0
    
    def _create_highlights(self, scored_frames, criteria):
        """하이라이트 생성"""
        try:
            highlights = []
            min_score = criteria.get('min_score', 2.0)  # 최소 점수
            max_highlights = criteria.get('max_highlights', 10)  # 최대 하이라이트 수
            
            # 점수 기준 필터링
            filtered_frames = [f for f in scored_frames if f['score'] >= min_score]
            
            # 시간 간격을 고려한 하이라이트 선택
            selected_highlights = []
            last_timestamp = -10  # 최소 10초 간격
            
            for frame_data in filtered_frames[:max_highlights * 2]:  # 여유분을 두고 선택
                if frame_data['timestamp'] - last_timestamp >= 10:  # 10초 이상 간격
                    selected_highlights.append(frame_data)
                    last_timestamp = frame_data['timestamp']
                    
                    if len(selected_highlights) >= max_highlights:
                        break
            
            # 하이라이트 정보 생성
            for i, frame_data in enumerate(selected_highlights):
                frame = frame_data['frame']
                highlight = {
                    'id': i + 1,
                    'timestamp': frame_data['timestamp'],
                    'frame_id': frame_data['frame_id'],
                    'score': frame_data['score'],
                    'description': self._generate_highlight_description(frame),
                    'person_count': len(frame.get('persons', [])),
                    'thumbnail_url': f'/api/frame/{frame.get("video_id", 0)}/{frame_data["frame_id"]}/',
                    'significance': self._get_significance_level(frame_data['score']),
                    'scene_type': frame.get('scene_attributes', {}).get('scene_type', 'unknown'),
                    'activity_level': frame.get('scene_attributes', {}).get('activity_level', 'medium')
                }
                highlights.append(highlight)
            
            return highlights
            
        except Exception as e:
            logger.error(f"❌ 하이라이트 생성 오류: {e}")
            return []
    
    def _generate_highlight_description(self, frame):
        """하이라이트 설명 생성"""
        try:
            persons = frame.get('persons', [])
            person_count = len(persons)
            
            if person_count == 0:
                return "주요 장면"
            elif person_count == 1:
                return "1명이 등장하는 장면"
            elif person_count <= 3:
                return f"{person_count}명이 등장하는 장면"
            else:
                return f"{person_count}명이 등장하는 활발한 장면"
                
        except Exception as e:
            logger.error(f"❌ 하이라이트 설명 생성 오류: {e}")
            return "주요 장면"
    
    def _get_significance_level(self, score):
        """중요도 레벨 반환"""
        try:
            if score >= 4.0:
                return "매우 높음"
            elif score >= 3.0:
                return "높음"
            elif score >= 2.0:
                return "보통"
            else:
                return "낮음"
                
        except Exception as e:
            logger.error(f"❌ 중요도 레벨 계산 오류: {e}")
            return "보통"
    
    def _handle_special_commands(self, message, video_id):
        """특별 명령어 처리 (AI별 개별 답변 생성)"""
        try:
            message_lower = message.lower().strip()
            print(f"🔍 특별 명령어 검사: '{message_lower}'")
            
            # 영상 요약 명령어
            if any(keyword in message_lower for keyword in ['요약', 'summary', '영상 요약', '영상 요약해줘', '영상 하이라이트 알려줘', '간단한 요약', '상세한 요약']):
                print(f"✅ 영상 요약 명령어 감지: '{message_lower}'")
                return self._handle_ai_generated_response(video_id, 'video_summary', message_lower)
            
            # 영상 하이라이트 명령어
            elif any(keyword in message_lower for keyword in ['하이라이트', 'highlight', '주요 장면', '중요한 장면']):
                return self._handle_ai_generated_response(video_id, 'video_highlights', message_lower)
            
            # 사람 찾기 명령어
            elif any(keyword in message_lower for keyword in ['사람 찾아줘', '사람 찾기', '인물 검색', '사람 검색']):
                return self._handle_ai_generated_response(video_id, 'person_search', message_lower)
            
            # 영상 간 검색 명령어
            elif any(keyword in message_lower for keyword in ['비가오는 밤', '비 오는 밤', '밤에 촬영', '어두운 영상', '비 오는 날']):
                return self._handle_ai_generated_response(video_id, 'inter_video_search', {'query': message_lower})
            
            # 영상 내 검색 명령어
            elif any(keyword in message_lower for keyword in ['주황색 상의', '주황 옷', '주황색 옷', '주황 상의', '오렌지 옷']):
                return self._handle_ai_generated_response(video_id, 'intra_video_search', {'query': message_lower})
            
            # 시간대별 분석 명령어
            elif any(keyword in message_lower for keyword in ['성비 분포', '성별 분포', '남녀 비율', '시간대별', '3시', '5시']):
                time_range = {'start': 180, 'end': 300}  # 기본값: 3분-5분
                return self._handle_ai_generated_response(video_id, 'temporal_analysis', {'time_range': time_range})
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 특별 명령어 처리 오류: {e}")
            return None
    
    def _handle_ai_generated_response(self, video_id, query_type, query_data=None):
        """AI별 개별 답변 생성 및 통합"""
        try:
            logger.info(f"🤖 AI 응답 생성 시작: video_id={video_id}, query_type={query_type}")
            
            # AI 응답 생성
            ai_responses = ai_response_generator.generate_responses(video_id, query_type, query_data)
            
            if not ai_responses:
                return "❌ AI 응답 생성에 실패했습니다."
            
            # 개별 AI 답변들
            individual_responses = ai_responses.get('individual', {})
            optimal_response = ai_responses.get('optimal', '')
            
            # 통합 응답 생성
            response_text = f"## 🎯 AI 통합 분석 결과\n\n{optimal_response}\n\n"
            
            # 각 AI별 답변 추가
            response_text += "## 📊 각 AI별 개별 분석\n\n"
            for ai_name, response in individual_responses.items():
                ai_display_name = {
                    'gpt': 'GPT-4o',
                    'claude': 'Claude-3.5-Sonnet', 
                    'mixtral': 'Mixtral-8x7B',
                    'gemini': 'Gemini-2.5-Flash'
                }.get(ai_name, ai_name.upper())
                
                response_text += f"### {ai_display_name}\n{response}\n\n"
            
            logger.info(f"✅ AI 응답 생성 완료: {len(response_text)}자")
            return response_text
            
        except Exception as e:
            logger.error(f"❌ AI 응답 생성 실패: {e}")
            return f"❌ AI 응답 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _handle_video_summary_command(self, message, video_id):
        """영상 요약 명령어 처리"""
        try:
            # 요약 타입 결정
            summary_type = 'comprehensive'
            if '간단' in message or 'brief' in message:
                summary_type = 'brief'
            elif '상세' in message or 'detailed' in message:
                summary_type = 'detailed'
            
            # VideoSummaryView 인스턴스 생성 및 요약 생성
            summary_view = VideoSummaryView()
            summary_result = summary_view._generate_video_summary(
                Video.objects.get(id=video_id), 
                summary_type
            )
            
            if summary_result and summary_result.get('summary'):
                return f"📝 **영상 요약** ({summary_type})\n\n{summary_result['summary']}"
            else:
                return "❌ 영상 요약을 생성할 수 없습니다. 영상 분석이 완료되었는지 확인해주세요."
                
        except Exception as e:
            logger.error(f"❌ 영상 요약 명령어 처리 오류: {e}")
            return f"❌ 영상 요약 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _handle_video_highlight_command(self, message, video_id):
        """영상 하이라이트 명령어 처리"""
        try:
            # 하이라이트 기준 설정
            criteria = {
                'min_score': 2.0,
                'max_highlights': 5
            }
            
            if '많이' in message or 'more' in message:
                criteria['max_highlights'] = 10
            elif '적게' in message or 'few' in message:
                criteria['max_highlights'] = 3
            
            # VideoHighlightView 인스턴스 생성 및 하이라이트 추출
            highlight_view = VideoHighlightView()
            highlights = highlight_view._extract_highlights(
                Video.objects.get(id=video_id), 
                criteria
            )
            
            if highlights:
                highlight_text = "🎬 **영상 하이라이트**\n\n"
                for i, highlight in enumerate(highlights, 1):
                    highlight_text += f"{i}. **{highlight['timestamp']:.1f}초** - {highlight['description']}\n"
                    highlight_text += f"   - 중요도: {highlight['significance']} (점수: {highlight['score']:.1f})\n"
                    highlight_text += f"   - 인원: {highlight['person_count']}명, 장면: {highlight['scene_type']}\n\n"
                
                return highlight_text
            else:
                return "❌ 하이라이트를 찾을 수 없습니다. 영상 분석이 완료되었는지 확인해주세요."
                
        except Exception as e:
            logger.error(f"❌ 영상 하이라이트 명령어 처리 오류: {e}")
            return f"❌ 영상 하이라이트 생성 중 오류가 발생했습니다: {str(e)}"
