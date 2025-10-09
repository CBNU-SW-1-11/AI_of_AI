#!/bin/bash

# AI of AI 서버 시작 스크립트

echo "=================================="
echo "🚀 AI of AI 서버 시작 중..."
echo "=================================="

# 작업 디렉토리 이동
cd /Users/seon/AIOFAI_F/AI_of_AI/chatbot_backend

# 가상환경 활성화
echo "📦 가상환경 활성화..."
source venv/bin/activate

# 환경 변수 로드
if [ -f .env ]; then
    echo "✅ .env 파일 로드 중..."
    export $(grep -v '^#' .env | xargs)
else
    echo "⚠️  .env 파일이 없습니다. .env.example을 참고하여 .env 파일을 생성하세요."
fi

# API 키 확인
echo ""
echo "🔑 API 키 확인:"
[ -n "$OPENAI_API_KEY" ] && echo "   ✅ OpenAI API Key" || echo "   ❌ OpenAI API Key 없음"
[ -n "$ANTHROPIC_API_KEY" ] && echo "   ✅ Anthropic API Key" || echo "   ❌ Anthropic API Key 없음"
[ -n "$GROQ_API_KEY" ] && echo "   ✅ Groq API Key" || echo "   ❌ Groq API Key 없음"
[ -n "$GEMINI_API_KEY" ] && echo "   ✅ Gemini API Key" || echo "   ❌ Gemini API Key 없음"

echo ""
echo "=================================="
echo "🌐 서버 시작 (http://localhost:8000)"
echo "=================================="
echo ""

# Django 서버 실행
python manage.py runserver

echo ""
echo "=================================="
echo "👋 서버 종료됨"
echo "=================================="

