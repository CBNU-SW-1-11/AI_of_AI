"""
AI 관련 유틸리티 함수들
"""
import openai
import ollama
from ..config.ai_config import (
    KOREAN_LANGUAGE_INSTRUCTION,
    OPENAI_MODEL_COMPLETION_LIMITS,
    DEFAULT_OPENAI_COMPLETION_LIMIT
)


def enforce_korean_instruction(text: str) -> str:
    """Ensure that the given system prompt explicitly enforces Korean responses."""
    if not text:
        return text
    if KOREAN_LANGUAGE_INSTRUCTION in text:
        return text
    return text + KOREAN_LANGUAGE_INSTRUCTION


def get_openai_completion_limit(model_name: str) -> int:
    """모델명에 따라 안전한 최대 토큰 수를 반환"""
    if not model_name:
        return DEFAULT_OPENAI_COMPLETION_LIMIT
    normalized_name = model_name.lower()
    for key, limit in OPENAI_MODEL_COMPLETION_LIMITS:
        if key in normalized_name:
            return limit
    return DEFAULT_OPENAI_COMPLETION_LIMIT


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

위 답변들을 분석하여 최적의 통합 답변을 제공해주세요.

⚠️ 지시사항: 질문 언어나 내용에 상관없이 최종 통합 답변과 모든 설명은 반드시 자연스럽고 유창한 한국어로 작성하세요."""
        
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
        
        system_prompt = f"""당신은 AI 응답 분석 및 최적화 전문가입니다. 여러 AI의 답변을 분석하여 가장 완전하고 정확한 통합 답변을 제공해야 합니다.

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
[질문에 대한 더 깊은 이해나 추가 고려사항]"""
        system_prompt = enforce_korean_instruction(system_prompt)

        user_prompt = f"질문: {user_question}\n\n다음은 여러 AI의 답변입니다:\n\n{responses_text}\n위 답변들을 분석하여 최적의 통합 답변을 제공해주세요.\n\n⚠️ 지시사항: 질문 언어나 내용에 상관없이 반드시 자연스럽고 유창한 한국어로 작성하세요."

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2500
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"최적화된 답변 생성 중 오류가 발생했습니다: {str(e)}"

