"""
에러 메시지 처리 유틸리티
"""
import re
import json
import ast


def get_user_friendly_error_message(error: Exception) -> str:
    """API 예외를 사용자가 이해하기 쉬운 한국어 메시지로 변환"""
    raw_message = str(error) if error else ""
    lower_message = raw_message.lower()
    error_payload = None

    if raw_message:
        json_like_match = re.search(r"\{.*\}", raw_message, re.DOTALL)
        if json_like_match:
            json_like_text = json_like_match.group(0)
            try:
                error_payload = ast.literal_eval(json_like_text)
            except (ValueError, SyntaxError):
                try:
                    error_payload = json.loads(json_like_text)
                except json.JSONDecodeError:
                    error_payload = None

    if isinstance(error_payload, dict):
        payload_error = error_payload.get("error") or {}
        payload_code = payload_error.get("code") or error_payload.get("code")
        payload_message = payload_error.get("message") or error_payload.get("message") or ""
    else:
        payload_code = None
        payload_message = ""

    combined_message = f"{payload_code or ''} {payload_message}".lower()

    # 429 오류 (Rate Limit)
    if "429" in raw_message or any(keyword in (lower_message or "") for keyword in ["rate_limit_exceeded", "tokens per min", "requests per min", "tpm limit", "rate limit", "quota exceeded", "quota_exceeded"]) \
            or any(keyword in combined_message for keyword in ["rate_limit_exceeded", "tokens per min", "requests per min", "tpm limit", "rate limit", "quota exceeded", "quota_exceeded"]):
        return "모델 사용량이 초과되었습니다. 다른 모델을 사용해주세요."

    # 401 오류 (인증 실패)
    if "401" in raw_message or any(keyword in (lower_message or "") for keyword in ["invalid_api_key", "incorrect api key", "authentication error", "unauthorized", "invalid key"]) \
            or any(keyword in combined_message for keyword in ["invalid_api_key", "incorrect api key", "authentication error", "unauthorized", "invalid key"]):
        return "API 인증에 실패했습니다. API 키를 다시 확인해 주세요."

    # 403 오류 (권한 없음)
    if "403" in raw_message or any(keyword in (lower_message or "") for keyword in ["forbidden", "access denied", "permission denied"]) \
            or any(keyword in combined_message for keyword in ["forbidden", "access denied", "permission denied"]):
        return "접근 권한이 없습니다. API 키 권한을 확인해 주세요."

    # 400 오류 (잘못된 요청)
    if "400" in raw_message or any(keyword in (lower_message or "") for keyword in ["bad request", "invalid request", "malformed request"]) \
            or any(keyword in combined_message for keyword in ["bad request", "invalid request", "malformed request"]):
        return "잘못된 요청입니다. 입력 내용을 확인해 주세요."

    # 404 오류 (리소스 없음)
    if "404" in raw_message or any(keyword in (lower_message or "") for keyword in ["not found", "resource not found", "model not found"]) \
            or any(keyword in combined_message for keyword in ["not found", "resource not found", "model not found"]):
        return "요청한 리소스를 찾을 수 없습니다. 모델 이름을 확인해 주세요."

    # 500/502/503 오류 (서버 오류)
    if any(code in raw_message for code in ["500", "502", "503", "504"]) or any(keyword in (lower_message or "") for keyword in ["internal server error", "bad gateway", "service unavailable", "gateway timeout", "server error"]) \
            or any(keyword in combined_message for keyword in ["internal server error", "bad gateway", "service unavailable", "gateway timeout", "server error"]):
        return "서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."

    # 컨텍스트 길이 초과
    if any(keyword in (lower_message or "") for keyword in ["context_length_exceeded", "maximum context length", "too many tokens", "context window", "token limit exceeded"]) \
            or any(keyword in combined_message for keyword in ["context_length_exceeded", "maximum context length", "too many tokens", "context window", "token limit exceeded"]):
        return "대화 길이가 너무 깁니다. 메시지를 줄이거나 새 대화를 시작해 주세요."

    # 네트워크 오류
    if any(keyword in (lower_message or "") for keyword in ["connection", "network", "timeout", "connection error", "network error", "connection refused", "connection reset"]) \
            or any(keyword in combined_message for keyword in ["connection", "network", "timeout", "connection error", "network error"]):
        return "네트워크 연결에 문제가 발생했습니다. 인터넷 연결을 확인하고 잠시 후 다시 시도해 주세요."

    # 안전 필터 (Gemini)
    if any(keyword in (lower_message or "") for keyword in ["safety", "safety filter", "blocked", "content filter", "harmful content"]) \
            or any(keyword in combined_message for keyword in ["safety", "safety filter", "blocked", "content filter"]):
        return "콘텐츠 정책에 의해 차단되었습니다. 다른 질문을 시도해 주세요."

    # 할당량 초과 (다양한 형태)
    if any(keyword in (lower_message or "") for keyword in ["quota", "limit exceeded", "usage limit", "billing", "insufficient quota"]) \
            or any(keyword in combined_message for keyword in ["quota", "limit exceeded", "usage limit", "billing", "insufficient quota"]):
        return "사용량 한도를 초과했습니다. 다른 모델을 사용하거나 잠시 후 다시 시도해 주세요."

    # 타임아웃 오류 (명시적 처리)
    if "timeout" in lower_message or "timed out" in lower_message:
        return "요청 시간이 초과되었습니다. 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요."

    # 기본 오류 메시지 (원본 오류 코드 숨김)
    return "오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

