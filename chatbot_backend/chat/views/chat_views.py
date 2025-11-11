from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse, Http404
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.cache import cache
import requests
import hmac
import hashlib
import uuid
import os

from chat.serializers import UserSerializer, VideoChatSessionSerializer, VideoChatMessageSerializer, VideoAnalysisCacheSerializer
from chat.models import VideoChatSession, VideoChatMessage, VideoAnalysisCache, Video, User, SocialAccount
from ..utils.chatbot import ChatBot, chatbots
from ..utils.file_utils import process_uploaded_file, summarize_content
from ..utils.error_handlers import get_user_friendly_error_message
from ..services.optimal_response import (
    collect_multi_llm_responses,
    format_optimal_response,
    detect_question_type_from_content
)
from ..services.video_analysis_service import video_analysis_service
from ..enhanced_video_chat_handler import get_video_chat_handler
from ..llm_cache_manager import conversation_context_manager


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
                print(f"❌ Invalid bot name: {bot_name}")
                print(f"   사용 가능한 모델: {list(chatbots.keys())[:10]}...")
                return Response({'error': 'Invalid bot name'}, status=status.HTTP_400_BAD_REQUEST)

            # 파일이 업로드된 경우 처리
            if uploaded_file:
                try:
                    print(f"파일 업로드 감지: {uploaded_file.name}")
                    
                    # 파일에서 텍스트 추출 또는 이미지 파일 식별
                    extracted_content = process_uploaded_file(uploaded_file)
                    print(f"📄 추출된 텍스트 길이: {len(extracted_content)}자")
                    print(f"📄 추출된 내용 미리보기 (처음 200자): {extracted_content[:200]}...")
                    
                    # Ollama로 분석 (이미지는 직접, 텍스트는 전체 내용 전달)
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
                            uploaded_file.seek(0)  # 파일 포인터 리셋
                            for chunk in uploaded_file.chunks():
                                temp_file.write(chunk)
                        print(f"이미지 파일 임시 저장: {temp_file_path}")
                    
                    # 사용자가 질문을 입력한 경우: 전체 내용 전달 (요약하지 않음)
                    # 질문이 없으면 요약 모드 사용
                    use_full_content = bool(user_message and user_message.strip())
                    
                    if use_full_content:
                        print(f"📋 전체 내용 모드: 추출된 텍스트({len(extracted_content)}자)를 그대로 전달합니다.")
                    else:
                        print(f"📝 요약 모드: Ollama로 요약합니다.")
                    
                    analyzed_content = summarize_content(
                        extracted_content, 
                        file_path=temp_file_path,
                        full_content=use_full_content
                    )
                    
                    print(f"📊 최종 분석 내용 길이: {len(analyzed_content)}자")
                    
                    # 사용자 메시지와 파일 분석 결과를 결합
                    if user_message and user_message.strip():
                        # 사용자가 질문을 입력한 경우 - 전체 내용 전달
                        print(f"📝 사용자 질문과 파일 함께 처리: {user_message}")
                        if uploaded_file.name.lower().endswith('.pdf'):
                            final_message = f"""다음은 업로드된 PDF 문서의 전체 내용입니다:

{analyzed_content}

---
사용자 질문: {user_message}

위 PDF 문서의 전체 내용을 바탕으로 사용자의 질문에 정확하고 자세하게 한국어로 답변해주세요.
문서에 연습 문제가 포함되어 있다면, 그 연습 문제를 찾아서 풀어주세요.
문서의 모든 내용을 주의 깊게 읽고, 관련된 정보를 모두 포함하여 답변해주세요."""
                        else:
                            # 이미지인 경우 (Ollama가 영어로 분석한 결과를 여러 LLM이 한국어로 답변)
                            final_message = f"""다음은 업로드된 이미지를 Ollama로 분석한 결과입니다 (영어):

{analyzed_content}

사용자 질문: {user_message}

위 영어로 작성된 이미지 분석 결과를 바탕으로 사용자의 질문에 한국어로 자세히 답변해주세요. 이미지 분석 결과의 내용을 충실히 반영하여 답변해주세요."""
                    else:
                        # 사용자 메시지가 없으면 기본 분석 요청
                        if uploaded_file.name.lower().endswith('.pdf'):
                            final_message = f"다음 문서 내용을 한국어로 요약해주세요:\n\n{analyzed_content}"
                        else:
                            final_message = f"""다음은 업로드된 이미지를 Ollama로 분석한 결과입니다 (영어):

{analyzed_content}

위 영어로 작성된 이미지 분석 결과를 바탕으로 이 이미지에 대해 한국어로 자세하고 자연스럽게 설명해주세요. 이미지 분석 결과의 내용을 충실히 반영하여 답변해주세요."""
                    print("분석 완료")
                except Exception as e:
                    print(f"파일 처리 오류: {str(e)}")
                    final_message = f"파일 처리 중 오류가 발생했습니다: {str(e)}"
            else:
                final_message = user_message

            # optimal 모델인 경우 특별 처리
            if bot_name == 'optimal':
                # 사용자 선택 심판 모델 (기본값: GPT-4o - 빠른 속도 + 우수한 성능)
                judge_model = request.data.get('judge_model', 'GPT-4o')
                
                # 사용자가 선택한 LLM 모델들 (프론트엔드에서 전달)
                selected_models = request.data.get('selected_models', None)
                
                # FormData로 전달된 경우 JSON 파싱
                if isinstance(selected_models, str):
                    try:
                        import json
                        selected_models = json.loads(selected_models)
                        print(f"📋 JSON 파싱된 selected_models: {selected_models}")
                    except Exception as e:
                        print(f"⚠️ selected_models JSON 파싱 실패: {e}")
                        selected_models = None
                
                # selected_models가 빈 리스트인 경우 처리
                if selected_models is not None and len(selected_models) == 0:
                    print(f"⚠️ selected_models가 빈 리스트입니다. 기본 모델 사용")
                    selected_models = None
                
                print(f"🎯 사용자 선택 모델들: {selected_models}")
                print(f"🎯 심판 모델: {judge_model}")
                print(f"📝 처리할 메시지 길이: {len(final_message)}자")
                
                # 모델 변경 감지 및 대화 히스토리 초기화 처리
                session_id = request.data.get('user_id', 'default_user')
                
                # 모델 이름 매핑 (표시명 -> 내부명)
                model_name_mapping = {
                    'GPT-5': 'gpt-5',
                    'GPT-5-Mini': 'gpt-5-mini',
                    'GPT-4.1': 'gpt-4.1',
                    'GPT-4.1-Mini': 'gpt-4.1-mini',
                    'GPT-4o': 'gpt-4o',
                    'GPT-4o-Mini': 'gpt-4o-mini',
                    'GPT-4-Turbo': 'gpt-4-turbo',
                    'GPT-3.5-Turbo': 'gpt-3.5-turbo',
                    'Gemini-2.5-Pro': 'gemini-2.5-pro',
                    'Gemini-2.5-Flash': 'gemini-2.5-flash',
                    'Gemini-2.0-Flash-Exp': 'gemini-2.0-flash-exp',
                    'Gemini-2.0-Flash-Lite': 'gemini-2.0-flash-lite',
                    'Claude-4-Opus': 'claude-4-opus',
                    'Claude-3.7-Sonnet': 'claude-3.7-sonnet',
                    'Claude-3.5-Sonnet': 'claude-3.5-sonnet',
                    'Claude-3.5-Haiku': 'claude-3.5-haiku',
                    'Claude-3-Opus': 'claude-3-opus',
                    'HCX-003': 'clova-hcx-003',
                    'HCX-DASH-001': 'clova-hcx-dash-001',
                }
                
                if selected_models and len(selected_models) > 0:
                    # 이전 모델 목록 가져오기
                    previous_models_key = f"previous_models_{session_id}"
                    previous_models = cache.get(previous_models_key, [])
                    
                    # 현재 모델 목록 정규화 (정렬하여 비교)
                    current_models = sorted([m.strip() for m in selected_models if m])
                    previous_models_sorted = sorted([m.strip() for m in previous_models if m]) if previous_models else []
                    
                    # 모델 변경 여부 확인
                    if previous_models_sorted:
                        # 교집합 계산 (공통 모델)
                        common_models = set(current_models) & set(previous_models_sorted)
                        
                        # 모든 모델이 교체되었는지 확인 (교집합이 0개)
                        all_models_changed = len(common_models) == 0
                        
                        if all_models_changed:
                            print(f"🔄 모든 모델이 교체됨 감지! 대화 히스토리 초기화")
                            print(f"   이전 모델: {previous_models_sorted}")
                            print(f"   현재 모델: {current_models}")
                            print(f"   공통 모델: {list(common_models)} (0개)")
                            
                            # 1. ConversationContextManager의 대화 히스토리 초기화
                            conversation_context_manager.clear_context(session_id)
                            print(f"   ✅ ConversationContextManager 초기화 완료")
                            
                            # 2. 모든 ChatBot 인스턴스의 대화 히스토리 초기화 (이전 + 현재 모든 모델)
                            all_models_to_clear = set(previous_models_sorted) | set(current_models)
                            for model_display_name in all_models_to_clear:
                                bot_name = model_name_mapping.get(model_display_name)
                                if bot_name and bot_name in chatbots:
                                    chatbots[bot_name].conversation_history = []
                                    print(f"   ✅ {model_display_name} ({bot_name}) 대화 히스토리 초기화")
                            
                            print(f"✅ 모든 모델의 대화 히스토리 초기화 완료 ({len(all_models_to_clear)}개 모델)")
                        else:
                            print(f"✔️ 일부 모델만 변경됨 - 대화 히스토리 유지")
                            print(f"   이전 모델: {previous_models_sorted}")
                            print(f"   현재 모델: {current_models}")
                            print(f"   공통 모델 ({len(common_models)}개): {list(common_models)}")
                            print(f"   → 1-2개 모델 교체이므로 이전 대화 내용 기억")
                    else:
                        print(f"📝 첫 요청 또는 이전 모델 정보 없음")
                    
                    # 현재 모델 목록을 캐시에 저장 (다음 요청을 위해)
                    cache.set(previous_models_key, current_models, 3600)  # 1시간 유지
                
                # 1-4단계: 선택된 LLM 병렬 질의 → 심판 모델 검증 → 최적 답변 생성
                response = None
                try:
                    print(f"🚀 최적 답변 생성 시작...")
                    print(f"📝 사용자 메시지: {final_message[:200]}...")
                    print(f"🎯 선택된 모델: {selected_models}")
                    print(f"⚖️ 심판 모델: {judge_model}")
                    
                    # 질문 유형 감지
                    has_image = uploaded_file and not uploaded_file.name.lower().endswith('.pdf')
                    has_document = uploaded_file and uploaded_file.name.lower().endswith('.pdf')
                    
                    question_type = None
                    if has_image:
                        question_type = 'image'
                    elif has_document:
                        question_type = 'document'
                    else:
                        question_type = detect_question_type_from_content(final_message)
                    
                    # 모든 모델 교체 여부 확인
                    all_models_changed = False
                    if selected_models and len(selected_models) > 0:
                        previous_models_key = f"previous_models_{session_id}"
                        previous_models = cache.get(previous_models_key, [])
                        if previous_models:
                            current_models_sorted = sorted([m.strip() for m in selected_models if m])
                            previous_models_sorted = sorted([m.strip() for m in previous_models if m])
                            common_models = set(current_models_sorted) & set(previous_models_sorted)
                            all_models_changed = len(common_models) == 0
                    
                    final_result = collect_multi_llm_responses(
                        final_message, 
                        judge_model, 
                        selected_models, 
                        question_type=question_type,
                        session_id=session_id,
                        clear_history=all_models_changed
                    )
                    print(f"✅ 최적 답변 생성 완료: {type(final_result)}")
                    print(f"✅ 최적 답변 결과 키: {list(final_result.keys()) if isinstance(final_result, dict) else 'N/A'}")
                    
                    # 최적 답변 내용 확인
                    optimal_answer = final_result.get("최적의_답변", "")
                    if not optimal_answer:
                        # optimal_answer가 없으면 다른 키 확인
                        optimal_answer = final_result.get("optimal_answer", "")
                    print(f"📄 최적 답변 내용 길이: {len(optimal_answer) if optimal_answer else 0}자")
                    print(f"📄 최적 답변 미리보기: {optimal_answer[:300] if optimal_answer else 'None'}...")
                    
                    # optimal_answer가 있으면 최적의_답변으로 변환
                    if optimal_answer and not final_result.get("최적의_답변"):
                        final_result["최적의_답변"] = optimal_answer
                    
                    # 결과 포맷팅
                    response = format_optimal_response(final_result)
                    print(f"✅ 결과 포맷팅 완료: {len(response) if response else 0}자")
                    print(f"✅ 포맷팅된 응답 미리보기: {response[:500] if response else 'None'}...")
                    
                    # 대화 맥락에 추가 (session_id는 위에서 이미 선언됨)
                    conversation_context_manager.add_conversation(
                        session_id=session_id,
                        user_message=final_message,
                        ai_responses=final_result.get('llm_검증_결과', {}),
                        optimal_response=final_result.get('최적의_답변', '')
                    )
                    
                    # response가 None이면 오류 메시지 반환
                    if not response:
                        print(f"❌ response가 None입니다!")
                        response = "최적 답변 생성에 실패했습니다. 서버 로그를 확인해주세요."
                    
                    print(f"📤 최종 응답 반환 (길이: {len(response) if response else 0}자)")
                    print(f"📤 최종 응답 미리보기: {response[:500] if response else 'None'}...")
                    
                    # 프론트엔드에서 분석 데이터를 쉽게 사용할 수 있도록 JSON 데이터도 함께 전송
                    return Response({
                        'response': response,
                        'analysisData': final_result.get('llm_검증_결과', {}),
                        'rationale': final_result.get('분석_근거', '')
                    })
                    
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    print(f"❌ 최적 답변 생성 실패: {e}")
                    print(f"❌ 상세 오류:\n{error_trace}")
                    # 폴백: 사용자 친화적인 오류 메시지 반환
                    friendly_error = get_user_friendly_error_message(e)
                    return Response({'response': friendly_error})
            
            # optimal 모델이 아닌 경우
            # 비용 절약: 파일 분석 시 간소화된 프롬프트 사용
            has_image = uploaded_file and not uploaded_file.name.lower().endswith('.pdf')
            has_document = uploaded_file and uploaded_file.name.lower().endswith('.pdf')
            
            # 질문 유형 자동 감지
            question_type = None
            if has_image:
                question_type = 'image'
            elif has_document:
                question_type = 'document'
            else:
                question_type = detect_question_type_from_content(final_message)
            
            if uploaded_file and '파일 내용을 분석해' in final_message:
                # 이미 Ollama로 분석된 내용이므로 간단한 응답 요청
                simplified_message = f"다음 분석 내용에 대해 간단한 의견을 제시해주세요:\n\n{final_message.split('다음 파일 내용을 분석해주세요:')[1] if '다음 파일 내용을 분석해주세요:' in final_message else final_message}"
                response = chatbot.chat(simplified_message, has_image=has_image, question_type=question_type)
            else:
                response = chatbot.chat(final_message, has_image=has_image, question_type=question_type)
            
            return Response({'response': response})
        except Exception as e:
            import traceback
            traceback.print_exc()
            # 사용자 친화적인 오류 메시지 반환
            friendly_error = get_user_friendly_error_message(e)
            return Response({'error': friendly_error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def generate_unique_username(email, name=None):
    """이메일 기반으로 고유한 사용자명 생성"""
    base_username = email.split('@')[0]
    username = base_username
    counter = 1
    
    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{counter}"
        counter += 1
    
    return username

