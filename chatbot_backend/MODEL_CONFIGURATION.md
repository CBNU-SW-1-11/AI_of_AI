# AI 모델 구성 가이드

## 🤖 지원하는 AI 모델 (10개)

### 1. GPT 모델 (OpenAI)

| 모델 ID | 모델명 | API 모델명 | 특징 |
|---------|--------|-----------|------|
| `gpt-4-turbo` | GPT-4 Turbo | `gpt-4-turbo-preview` | 최신 고성능 모델 |
| `gpt-4` | GPT-4 | `gpt-4` | 강력한 추론 능력 |
| `gpt-3.5-turbo` | GPT-3.5 Turbo | `gpt-3.5-turbo` | 빠르고 효율적 |

**API 키 설정:**
```bash
OPENAI_API_KEY=sk-...
```

**사용 예시:**
```bash
curl -X POST http://localhost:8000/chat/gpt-4-turbo/ \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕하세요"}'
```

---

### 2. Gemini 모델 (Google)

| 모델 ID | 모델명 | API 모델명 | 특징 |
|---------|--------|-----------|------|
| `gemini-pro-1.5` | Gemini Pro 1.5 | `gemini-1.5-pro-latest` | 최신 멀티모달 AI |
| `gemini-pro-1.0` | Gemini Pro 1.0 | `gemini-pro` | 안정적인 AI |

**API 키 설정:**
```bash
GEMINI_API_KEY=AIzaSy...
```

**무료 티어 제한:**
- Gemini Pro 1.5: 2 RPM
- Gemini Pro 1.0: 60 RPM

**사용 예시:**
```bash
curl -X POST http://localhost:8000/chat/gemini-pro-1.5/ \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕하세요"}'
```

---

### 3. Claude 모델 (Anthropic)

| 모델 ID | 모델명 | API 모델명 | 특징 |
|---------|--------|-----------|------|
| `claude-3-opus` | Claude 3 Opus | `claude-3-opus-20240229` | 최고 성능 모델 |
| `claude-3-sonnet` | Claude 3 Sonnet | `claude-3-5-sonnet-20241022` | 균형잡힌 모델 |
| `claude-3-haiku` | Claude 3 Haiku | `claude-3-5-haiku-20241022` | 빠른 모델 |

**API 키 설정:**
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

**사용 예시:**
```bash
curl -X POST http://localhost:8000/chat/claude-3-opus/ \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕하세요"}'
```

---

### 4. Clova 모델 (Naver HyperCLOVA X)

| 모델 ID | 모델명 | API 모델명 | 특징 |
|---------|--------|-----------|------|
| `clova-hcx-003` | HCX-003 | `HCX-003` | 고성능 한국어 AI |
| `clova-hcx-dash-001` | HCX-DASH-001 | `HCX-DASH-001` | 빠른 한국어 AI |

**API 키 설정:**
```bash
CLOVA_API_KEY=your_clova_studio_api_key
CLOVA_API_KEY_PRIMARY=your_apigw_api_key
CLOVA_REQUEST_ID=your_request_id
```

**API 키 발급 방법:**
1. https://www.clovastudio.naver.com/ 접속
2. API 키 발급
3. .env 파일에 설정

**사용 예시:**
```bash
curl -X POST http://localhost:8000/chat/clova-hcx-003/ \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕하세요"}'
```

---

## 🔧 환경 변수 설정

`/chatbot_backend/.env` 파일에 다음 내용을 추가하세요:

```bash
# OpenAI API Key
OPENAI_API_KEY=sk-proj-...

# Anthropic API Key
ANTHROPIC_API_KEY=sk-ant-api03-...

# Gemini API Key
GEMINI_API_KEY=AIzaSy...

# Clova API Keys (Naver HyperCLOVA X)
CLOVA_API_KEY=your_clova_api_key_here
CLOVA_API_KEY_PRIMARY=your_clova_api_key_primary_here
CLOVA_REQUEST_ID=your_request_id_here
```

---

## 🚀 사용 가능한 엔드포인트

### 개별 모델 엔드포인트

```
POST /chat/gpt-4-turbo/
POST /chat/gpt-4/
POST /chat/gpt-3.5-turbo/

POST /chat/gemini-pro-1.5/
POST /chat/gemini-pro-1.0/

POST /chat/claude-3-opus/
POST /chat/claude-3-sonnet/
POST /chat/claude-3-haiku/

POST /chat/clova-hcx-003/
POST /chat/clova-hcx-dash-001/
```

### 통합 엔드포인트 (앙상블)

```
POST /api/chat/integrated/
{
  "message": "질문 내용",
  "selected_models": ["gpt-4-turbo", "claude-3-opus", "gemini-pro-1.5"]
}
```

---

## 📊 모델 성능 비교

| 모델 | 속도 | 품질 | 비용 | 한국어 |
|------|------|------|------|--------|
| **GPT-4 Turbo** | 🟢 빠름 | 🟢 최고 | 🔴 고가 | 🟡 우수 |
| **GPT-4** | 🟡 보통 | 🟢 최고 | 🔴 고가 | 🟡 우수 |
| **GPT-3.5 Turbo** | 🟢 빠름 | 🟡 우수 | 🟢 저렴 | 🟡 우수 |
| **Gemini Pro 1.5** | 🟢 빠름 | 🟢 최고 | 🟢 무료 | 🟡 우수 |
| **Gemini Pro 1.0** | 🟢 빠름 | 🟡 우수 | 🟢 무료 | 🟡 우수 |
| **Claude 3 Opus** | 🟡 보통 | 🟢 최고 | 🔴 고가 | 🟡 우수 |
| **Claude 3 Sonnet** | 🟢 빠름 | 🟢 최고 | 🟡 보통 | 🟡 우수 |
| **Claude 3 Haiku** | 🟢 빠름 | 🟡 우수 | 🟢 저렴 | 🟡 우수 |
| **Clova HCX-003** | 🟢 빠름 | 🟡 우수 | 🟡 보통 | 🟢 최고 |
| **Clova HCX-DASH** | 🟢 빠름 | 🟡 우수 | 🟢 저렴 | 🟢 최고 |

---

## 🎯 추천 조합

### 최고 품질
```json
["gpt-4-turbo", "claude-3-opus", "gemini-pro-1.5"]
```

### 균형잡힌 성능
```json
["gpt-3.5-turbo", "claude-3-sonnet", "gemini-pro-1.5"]
```

### 빠른 응답
```json
["gpt-3.5-turbo", "claude-3-haiku", "clova-hcx-dash-001"]
```

### 한국어 특화
```json
["clova-hcx-003", "claude-3-sonnet", "gpt-4-turbo"]
```

---

## 🔍 문제 해결

### Clova API 오류
- API 키 확인: https://www.clovastudio.naver.com/
- Request ID는 UUID 형식이어야 함
- testapp 부분을 실제 앱 이름으로 변경 필요

### Gemini 할당량 초과
- Pro 1.5: 분당 2회 제한
- Pro 1.0: 분당 60회 가능
- Flash 사용 권장 (분당 15회)

### OpenAI 비용 관리
- GPT-4 Turbo 사용 시 비용 모니터링 필수
- 개발 환경에서는 GPT-3.5 Turbo 권장

