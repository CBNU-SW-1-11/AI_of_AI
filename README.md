# AI of AI - 다중 LLM 기반 지능형 채팅 및 영상 분석 시스템

## 📋 프로젝트 소개

AI of AI는 여러 대형 언어 모델(LLM)을 통합하여 최적의 답변을 생성하는 지능형 채팅 시스템입니다. 영상 분석 기능을 통해 영상 내용을 이해하고, 한국어로 자연스럽게 질의응답할 수 있습니다.

### 주요 특징

- 🤖 **다중 LLM 통합**: GPT, Gemini, Claude 등 여러 AI 모델의 답변을 비교하여 최적의 답변 생성
- ⚖️ **Judge 모델**: 여러 AI의 답변을 평가하고 검증하여 가장 신뢰할 수 있는 답변 선택
- 🔍 **사실 검증**: Wikipedia, Wikidata, DBpedia 등 외부 소스를 활용한 사실 검증
- 🎬 **영상 분석**: YOLO, DeepFace, Ollama를 활용한 영상 내용 분석 및 질의응답
- 🌐 **한국어 지원**: 한국어 질문으로 객체 검색 및 자연스러운 답변 생성
- 💬 **세션 관리**: 채팅 세션별 대화 기록 관리 및 자동 초기화

## 🚀 주요 기능

### 1. 다중 LLM 채팅 시스템

- 여러 AI 모델(GPT-4o-Mini, Gemini-2.0-Flash-Lite, Claude-3.5-Haiku)의 답변을 동시에 수집
- Judge 모델이 각 답변을 평가하여 최적의 답변 선택
- 상호 모순이 있는 경우 프리미엄 모델 보팅 시스템 활성화

### 2. 영상 분석 및 질의응답

#### 영상 분석
- **YOLO**: 모든 객체 감지 (person, handbag, cup, car 등)
- **DeepFace**: 사람의 성별, 나이, 감정, 옷 색상 분석
- **Ollama (llava)**: 프레임별 자연어 캡션 생성

#### 질의응답
- **색상 검색**: "초록색 옷 입은 사람 찾아줘"
- **객체 검색**: "핸드백이 있는 프레임은?"
- **시간 범위**: "처음 5초 동안 무슨 일이 있었어?"
- **요약**: "영상 요약해줘"

### 3. 한국어 객체 검색

- 한국어 질문을 영어 객체명으로 자동 변환
- 예: "핸드백" → ["handbag", "purse"]
- YOLO로 감지된 모든 객체를 한국어로 검색 가능

### 4. 사실 검증 시스템

- **Wikipedia**: 빠른 사실 검증
- **Wikidata**: 구조화된 데이터 검색
- **DBpedia**: SPARQL 쿼리를 통한 지식 검색
- **DuckDuckGo**: Instant Answer API 활용

## 🛠️ 기술 스택

### Backend
- **Django**: 웹 프레임워크
- **Django REST Framework**: API 개발
- **YOLO (ultralytics)**: 객체 감지
- **DeepFace**: 얼굴 및 속성 분석
- **Ollama**: 로컬 LLM 실행
- **OpenAI API**: GPT 모델
- **Anthropic API**: Claude 모델
- **Google Gemini API**: Gemini 모델

### Frontend
- **React**: 사용자 인터페이스
- **Axios**: HTTP 클라이언트
- **Tailwind CSS**: 스타일링

### AI/ML
- **YOLOv8**: 객체 감지 모델
- **DeepFace**: 얼굴 인식 및 속성 분석
- **LLaVA (Ollama)**: 비전-언어 모델
- **BLIP**: 이미지 캡셔닝

## 📦 설치 방법

### 1. 저장소 클론

```bash
git clone https://github.com/CBNU-SW-1-11/AI_of_AI.git
cd AI_of_AI
```

### 2. Backend 설정

```bash
cd chatbot_backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### 3. Frontend 설정

```bash
cd frontend
npm install
npm start
```

### 4. Ollama 설정

```bash
# Ollama 설치 후 비전 모델 다운로드
ollama pull llava:llama3.1
ollama pull llava:13b
```

## 🎯 사용 방법

### 일반 채팅

1. 원하는 AI 모델 선택 (GPT, Gemini, Claude 등)
2. 질문 입력
3. 여러 AI의 답변과 최적 답변 확인

### 영상 분석

1. 영상 업로드
2. 영상 분석 완료 대기
3. 한국어로 질문:
   - "초록색 옷 입은 사람 찾아줘"
   - "핸드백이 있는 프레임은?"
   - "영상 요약해줘"

## 📁 프로젝트 구조

```
AI_of_AI/
├── chatbot_backend/          # Django 백엔드
│   ├── chat/
│   │   ├── services/         # 비즈니스 로직
│   │   │   ├── optimal_response.py      # 최적 답변 생성
│   │   │   ├── verification_sources.py  # 사실 검증
│   │   │   └── video_analysis_service.py # 영상 분석
│   │   ├── views/            # API 엔드포인트
│   │   │   ├── chat_views.py            # 일반 채팅
│   │   │   └── video_chat_views.py      # 영상 채팅
│   │   └── enhanced_video_chat_handler.py # 영상 채팅 핸들러
│   └── media/                # 업로드된 파일 및 분석 결과
├── frontend/                 # React 프론트엔드
│   └── src/
│       ├── components/       # 재사용 가능한 컴포넌트
│       └── pages/            # 페이지 컴포넌트
└── README.md
```

## 🔧 주요 기능 상세

### 프레임 검색 로직

1. **의도 분류**: 색상/키워드/시간/요약 질문 자동 감지
2. **점수 기반 검색**:
   - 객체 정보 매칭: 3점 (최우선)
   - 캡션 매칭: 2점
   - 색상 분석: 1점
3. **한국어-영어 매핑**: 자동 변환 및 검색

### AI 응답 생성

1. **컨텍스트 구성**: 관련 프레임 캡션 + 감지된 객체 정보
2. **다중 AI 응답**: 여러 모델의 답변 수집
3. **응답 필터링**: 부적절한 응답 자동 제거
4. **통합 답변**: Judge 모델이 최적 답변 생성

### 세션 관리

- 채팅창(세션)이 바뀌면 자동으로 이전 대화 기록 초기화
- 세션별 독립적인 대화 컨텍스트 유지

## 📊 영상 분석 결과

각 영상 분석 후 다음 정보가 생성됩니다:

- **meta_db.json**: 프레임별 캡션, 객체 정보, 사람 속성
- **detection_db.json**: YOLO 원본 감지 결과
- **프레임 이미지**: 분석된 프레임의 이미지 파일

## 🤝 기여 방법

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

## 👥 팀

- 충북대학교 소프트웨어학과

## 🙏 감사의 말

- OpenAI, Anthropic, Google의 LLM API
- Ultralytics의 YOLO 모델
- Ollama 커뮤니티

---

**Note**: 이 프로젝트는 졸업 프로젝트로 개발되었습니다.

