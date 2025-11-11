"""
AI 모델 설정 및 상수
"""

KOREAN_LANGUAGE_INSTRUCTION = "\n\nIMPORTANT: Regardless of the question language, you MUST respond in natural and fluent Korean. Never reply in any other language."

OPENAI_MODEL_COMPLETION_LIMITS = [
    ("gpt-3.5", 4096),
    ("gpt-4o-mini", 8192),
    ("gpt-4o", 8192),
    ("gpt-4-turbo", 8192),
    ("gpt-4.1-mini", 8192),
    ("gpt-4.1", 8192),
    ("gpt-4", 8192),
    ("gpt-5", 8192),
    ("o1", 8192),
    ("o3", 8192),
]

DEFAULT_OPENAI_COMPLETION_LIMIT = 4096

