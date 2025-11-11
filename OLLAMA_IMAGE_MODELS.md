# 🖼️ Ollama 이미지 분석 모델 설치 가이드

## 📋 개요

Ollama는 **완전히 무료**이고 **제한이 없는** 로컬 이미지 분석 솔루션입니다. 여러 버전의 모델을 사용할 수 있으며, 코드는 자동으로 사용 가능한 가장 높은 버전의 모델을 선택합니다.

## 🚀 Ollama 설치 (아직 설치하지 않은 경우)

### macOS
```bash
brew install ollama
```

### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows
[Ollama 공식 웹사이트](https://ollama.com/download)에서 다운로드

## 📦 이미지 분석 모델 설치

코드는 다음 순서로 모델을 시도합니다 (높은 버전부터):

1. **llava:llama3.1** (최신, 가장 정확) - 추천
2. **llava:13b** (중간, 좋은 성능)
3. **llava:7b** (기본, 빠름)

### 모델 설치 명령어

```bash
# 최신 버전 (추천)
ollama pull llava:llama3.1

# 또는 중간 버전
ollama pull llava:13b

# 또는 기본 버전
ollama pull llava:7b
```

### 모든 모델 한번에 설치
```bash
ollama pull llava:llama3.1
ollama pull llava:13b
ollama pull llava:7b
```

## 💡 모델 선택 가이드

### llava:llama3.1 (추천)
- **장점**: 가장 정확한 텍스트 인식 및 이미지 분석
- **단점**: 더 많은 메모리 필요 (약 8GB RAM)
- **용량**: 약 4.7GB

### llava:13b
- **장점**: 좋은 성능과 적당한 속도
- **단점**: 중간 정도의 메모리 필요 (약 6GB RAM)
- **용량**: 약 7.3GB

### llava:7b
- **장점**: 빠른 속도, 적은 메모리 사용 (약 4GB RAM)
- **단점**: 정확도가 상대적으로 낮음
- **용량**: 약 4.7GB

## 🔍 설치된 모델 확인

```bash
ollama list
```

## ⚙️ Ollama 서버 실행 확인

Ollama 서버가 실행 중인지 확인:
```bash
# 서버 상태 확인
curl http://localhost:11434/api/tags

# 또는 간단히
ollama list
```

서버가 실행되지 않은 경우:
```bash
# 백그라운드에서 실행
ollama serve
```

## 🎯 사용 방법

코드는 자동으로 사용 가능한 가장 높은 버전의 모델을 선택합니다:

1. `llava:llama3.1` 시도 → 실패 시
2. `llava:13b` 시도 → 실패 시
3. `llava:7b` 시도 → 실패 시
4. GPT API로 fallback (유료)

## 📊 성능 비교

| 모델 | 정확도 | 속도 | 메모리 | 추천 용도 |
|------|--------|------|--------|----------|
| llava:llama3.1 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 높음 | 정확도가 중요한 경우 |
| llava:13b | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 중간 | 균형잡힌 성능 |
| llava:7b | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 낮음 | 빠른 응답이 필요한 경우 |

## 🔧 문제 해결

### 모델을 찾을 수 없다는 오류
```bash
# 모델 다시 설치
ollama pull llava:llama3.1
```

### 메모리 부족 오류
- 더 작은 모델 사용 (llava:7b)
- 또는 시스템 메모리 업그레이드

### 서버 연결 오류
```bash
# Ollama 서버 재시작
pkill ollama
ollama serve
```

## 💰 비용

**Ollama는 완전히 무료입니다!**
- 다운로드 무료
- 사용 무료
- 제한 없음
- 로컬에서 실행되므로 API 비용 없음

## 🆚 다른 솔루션과 비교

| 솔루션 | 비용 | 제한 | 정확도 |
|--------|------|------|--------|
| **Ollama** | ✅ 무료 | ❌ 없음 | ⭐⭐⭐⭐ |
| Gemini | ⚠️ 제한적 무료 | ⚠️ 일정 수준 초과 시 유료 | ⭐⭐⭐⭐⭐ |
| GPT-4 Vision | ❌ 유료 | ❌ 토큰당 비용 | ⭐⭐⭐⭐⭐ |
| Claude Vision | ❌ 유료 | ❌ 토큰당 비용 | ⭐⭐⭐⭐⭐ |

## 📝 참고사항

- Ollama는 로컬에서 실행되므로 인터넷 연결이 필요 없습니다
- 첫 실행 시 모델을 다운로드하므로 시간이 걸릴 수 있습니다
- 모델은 한 번만 다운로드하면 이후에는 빠르게 사용 가능합니다
- 여러 모델을 설치하면 코드가 자동으로 최적의 모델을 선택합니다

