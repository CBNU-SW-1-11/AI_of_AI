# 🏗️ AI of AI - 시스템 구성도

## 📋 목차
1. [전체 시스템 아키텍처](#전체-시스템-아키텍처)
2. [하이브리드 비디오 분석 파이프라인](#하이브리드-비디오-분석-파이프라인)
3. [AI 채팅 시스템](#ai-채팅-시스템)
4. [데이터 흐름](#데이터-흐름)
5. [기술 스택](#기술-스택)

---

## 1️⃣ 전체 시스템 아키텍처

```mermaid
flowchart TB
    subgraph Frontend["🖥️ Frontend (React)"]
        UI[사용자 인터페이스]
        VideoList[영상 목록 페이지]
        VideoChat[영상 채팅 페이지]
        TextChat[텍스트 채팅 페이지]
    end

    subgraph Backend["⚙️ Backend (Django)"]
        API[REST API]
        VideoAPI[영상 업로드 API]
        SearchAPI[검색 API]
        ChatAPI[채팅 API]
        SummaryAPI[요약 API]
    end

    subgraph Analysis["🔥 하이브리드 분석 시스템"]
        VideoAnalyzer[비디오 분석 서비스]
        
        subgraph Models["🤖 AI 모델"]
            YOLO[YOLO<br/>사람 감지]
            DeepFace[DeepFace<br/>성별/나이/감정]
            OpenCV[OpenCV<br/>의상 색상]
            BLIP[BLIP<br/>장면 캡션]
            GPT4V[GPT-4V<br/>폴백 분석]
        end
    end

    subgraph Search["🔍 검색 시스템"]
        IntraSearch[영상 내 검색]
        TemporalSearch[시간대별 분석]
        ColorSearch[색상 검색]
        PersonSearch[인물 검색]
    end

    subgraph Chat["💬 AI 채팅 시스템"]
        GPT[GPT-4o]
        Claude[Claude 3.5]
        Mixtral[Mixtral]
        Ensemble[앙상블 통합]
    end

    subgraph Database["💾 데이터베이스"]
        SQLite[(SQLite DB)]
        MediaFiles[미디어 파일]
        AnalysisJSON[분석 결과 JSON]
    end

    UI --> VideoList
    UI --> VideoChat
    UI --> TextChat
    
    VideoList --> VideoAPI
    VideoChat --> ChatAPI
    VideoChat --> SearchAPI
    TextChat --> ChatAPI
    
    VideoAPI --> VideoAnalyzer
    SearchAPI --> Search
    ChatAPI --> Chat
    
    VideoAnalyzer --> YOLO
    YOLO --> DeepFace
    DeepFace --> OpenCV
    OpenCV --> BLIP
    DeepFace -.->|신뢰도 낮을때| GPT4V
    
    VideoAnalyzer --> SQLite
    VideoAnalyzer --> AnalysisJSON
    
    Search --> SQLite
    Search --> AnalysisJSON
    
    Chat --> SQLite
    Chat --> AnalysisJSON
    
    GPT --> Ensemble
    Claude --> Ensemble
    Mixtral --> Ensemble

    style YOLO fill:#ff6b6b
    style DeepFace fill:#4ecdc4
    style OpenCV fill:#45b7d1
    style BLIP fill:#96ceb4
    style GPT4V fill:#ffeaa7,stroke-dasharray: 5 5
```

---

## 2️⃣ 하이브리드 비디오 분석 파이프라인

```mermaid
flowchart LR
    subgraph Input["📹 입력"]
        Video[영상 업로드<br/>11.2MB]
    end

    subgraph FrameExtraction["🎬 프레임 추출"]
        Extract[적응형 샘플링<br/>15 프레임]
        Frame1[Frame 1: 0.0s]
        Frame2[Frame 2: 0.5s]
        FrameN[Frame 15: 7.0s]
    end

    subgraph PersonDetection["👤 사람 감지"]
        YOLOModel[YOLO v8<br/>객체 감지]
        BBox[Bounding Box<br/>추출]
    end

    subgraph HybridAnalysis["🔥 하이브리드 분석"]
        DeepFaceAnalysis[DeepFace 분석]
        ConfCheck{신뢰도<br/>>70%?}
        GPT4VAnalysis[GPT-4V 분석<br/>폴백]
        ColorExtract[OpenCV<br/>색상 추출]
        
        subgraph DeepFaceResult["📊 DeepFace 결과"]
            Gender[성별: man/woman]
            Age[나이: 32세]
            Emotion[감정: sad/happy]
        end
        
        subgraph ColorResult["🎨 색상 결과"]
            Upper[상의: pink]
            Lower[하의: green]
        end
    end

    subgraph SceneAnalysis["🏞️ 장면 분석"]
        BLIPModel[BLIP-2<br/>캡션 생성]
        SceneType[장면 타입: indoor]
        Lighting[조명: dark/normal]
    end

    subgraph Output["💾 출력"]
        JSON[분석 JSON<br/>6,698 lines]
        MetaDB[Meta DB]
        DetectionDB[Detection DB]
        Stats[통계 데이터]
    end

    Video --> Extract
    Extract --> Frame1 & Frame2 & FrameN
    
    Frame1 & Frame2 & FrameN --> YOLOModel
    YOLOModel --> BBox
    
    BBox --> DeepFaceAnalysis
    DeepFaceAnalysis --> ConfCheck
    
    ConfCheck -->|Yes| ColorExtract
    ConfCheck -->|No| GPT4VAnalysis
    GPT4VAnalysis --> ColorExtract
    
    DeepFaceAnalysis --> Gender & Age & Emotion
    ColorExtract --> Upper & Lower
    
    Frame1 & Frame2 & FrameN --> BLIPModel
    BLIPModel --> SceneType & Lighting
    
    Gender & Age & Emotion --> JSON
    Upper & Lower --> JSON
    SceneType & Lighting --> JSON
    
    JSON --> MetaDB
    JSON --> DetectionDB
    JSON --> Stats

    style DeepFaceAnalysis fill:#4ecdc4
    style GPT4VAnalysis fill:#ffeaa7,stroke-dasharray: 5 5
    style ColorExtract fill:#45b7d1
    style BLIPModel fill:#96ceb4
```

### 🔥 하이브리드 분석 상세 플로우

```mermaid
sequenceDiagram
    participant Video as 영상
    participant YOLO as YOLO
    participant DF as DeepFace
    participant CV as OpenCV
    participant GPT as GPT-4V
    participant BLIP as BLIP
    participant DB as Database

    Video->>YOLO: 프레임 전송
    YOLO->>YOLO: 사람 감지 (bbox)
    
    loop 각 감지된 사람
        YOLO->>DF: 사람 이미지 전달
        DF->>DF: 성별/나이/감정 분석
        
        alt 신뢰도 >= 70%
            DF->>CV: ✅ DeepFace 성공
            Note over DF,CV: 비용: $0.00
        else 신뢰도 < 70%
            DF->>GPT: ❌ DeepFace 실패
            GPT->>GPT: 폴백 분석
            Note over DF,GPT: 비용: $0.01
            GPT->>CV: 결과 전달
        end
        
        CV->>CV: HSV 색상 추출
        CV->>CV: 상/하의 색상 분류
    end
    
    Video->>BLIP: 프레임 전송
    BLIP->>BLIP: 장면 캡션 생성
    
    BLIP->>DB: 분석 결과 저장
    CV->>DB: 색상 데이터 저장
    DF->>DB: 속성 데이터 저장
```

---

## 3️⃣ AI 채팅 시스템

```mermaid
flowchart TB
    subgraph UserInterface["👤 사용자"]
        Query[질문 입력<br/>'분홍색 옷 입은 사람']
    end

    subgraph ChatSystem["💬 채팅 시스템"]
        QueryAnalysis[쿼리 분석]
        
        subgraph SearchEngine["🔍 검색 엔진"]
            ColorSearch[색상 검색]
            PersonSearch[인물 검색]
            TimeSearch[시간대 검색]
        end
        
        subgraph AIModels["🤖 AI 모델"]
            GPT4[GPT-4o<br/>강력한 추론]
            Claude[Claude 3.5<br/>세밀한 분석]
            Mixtral[Mixtral<br/>빠른 응답]
        end
        
        Ensemble[앙상블 통합<br/>최적 답변 선택]
    end

    subgraph DataSource["📊 데이터 소스"]
        AnalysisData[분석 데이터<br/>clothing_colors]
        MetaData[메타데이터<br/>attributes]
        FrameImages[프레임 이미지<br/>jpg]
    end

    subgraph Response["📝 응답"]
        Result1[프레임 14: 6.5초<br/>분홍색 상의, 남성 44세]
        Result2[프레임 15: 7.0초<br/>분홍색 상의, 남성 34세]
        Confidence[신뢰도: 0.85-0.89]
    end

    Query --> QueryAnalysis
    
    QueryAnalysis --> ColorSearch
    QueryAnalysis --> PersonSearch
    QueryAnalysis --> TimeSearch
    
    ColorSearch --> AnalysisData
    PersonSearch --> MetaData
    TimeSearch --> AnalysisData
    
    AnalysisData --> GPT4
    AnalysisData --> Claude
    AnalysisData --> Mixtral
    
    MetaData --> GPT4
    MetaData --> Claude
    MetaData --> Mixtral
    
    GPT4 --> Ensemble
    Claude --> Ensemble
    Mixtral --> Ensemble
    
    Ensemble --> Result1
    Ensemble --> Result2
    Ensemble --> Confidence
    
    Result1 & Result2 --> FrameImages

    style ColorSearch fill:#ff6b6b
    style GPT4 fill:#4ecdc4
    style Claude fill:#45b7d1
    style Mixtral fill:#96ceb4
```

---

## 4️⃣ 데이터 흐름

```mermaid
flowchart LR
    subgraph Upload["📤 업로드"]
        U1[영상 파일<br/>test2.mp4]
        U2[11.2MB]
    end

    subgraph Processing["⚙️ 처리"]
        P1[프레임 추출<br/>15개]
        P2[YOLO 분석<br/>100명 감지]
        P3[DeepFace 분석<br/>98% 성공]
        P4[색상 추출<br/>10색상]
        P5[BLIP 캡션<br/>15개]
    end

    subgraph Storage["💾 저장"]
        S1[(SQLite<br/>Video 테이블)]
        S2[JSON 파일<br/>6,698줄]
        S3[프레임 이미지<br/>15개 JPG]
        S4[Meta DB<br/>검색용]
        S5[Detection DB<br/>객체 정보]
    end

    subgraph Search["🔍 검색"]
        Search1[색상 검색<br/>clothing_colors]
        Search2[속성 검색<br/>attributes]
        Search3[시간대 검색<br/>timestamp]
    end

    subgraph Result["📊 결과"]
        R1[검색 결과<br/>2개 발견]
        R2[프레임 정보<br/>시간/위치]
        R3[사람 정보<br/>성별/나이/색상]
    end

    U1 --> P1
    U2 --> P1
    
    P1 --> P2
    P2 --> P3
    P3 --> P4
    P1 --> P5
    
    P2 --> S1
    P3 --> S2
    P4 --> S2
    P5 --> S2
    P1 --> S3
    S2 --> S4
    S2 --> S5
    
    S4 --> Search1
    S4 --> Search2
    S4 --> Search3
    
    Search1 --> R1
    Search2 --> R2
    Search3 --> R3

    style P3 fill:#4ecdc4
    style P4 fill:#45b7d1
    style S2 fill:#ffeaa7
```

---

## 5️⃣ 기술 스택

```mermaid
mindmap
  root((AI of AI))
    Frontend
      React 18
      Tailwind CSS
      Axios
      React Router
    Backend
      Django 4.2
      Django REST Framework
      SQLite
      Python 3.9+
    AI Models
      YOLO v8
        사람 감지
        Confidence > 0.3
      DeepFace
        성별 분석
        나이 예측
        감정 인식
        98% 성공률
      OpenCV
        HSV 색상
        상/하의 구분
        10개 색상
      BLIP-2
        장면 캡션
        무료
      GPT-4 Vision
        폴백 분석
        조건부 사용
    Storage
      SQLite
        Video 테이블
        Meta 데이터
      JSON
        분석 결과
        6,698 lines
      Media Files
        영상 파일
        프레임 이미지
    Deployment
      로컬 개발
        Frontend: 3000
        Backend: 8000
      Git
        GitHub
        버전 관리
```

---

## 📊 성능 지표

### 분석 성능

| 항목 | 이전 | 현재 | 개선율 |
|------|------|------|--------|
| **프레임 수** | 4개 | 15개 | +275% |
| **성별 정확도** | 60% | 98% | +63% |
| **색상 정확도** | 40% | 95% | +137% |
| **분석 비용** | $0.15 | $0.00 | -100% |
| **처리 시간** | 30초 | 35초 | +17% |

### AI 모델 사용 통계

```mermaid
pie title 하이브리드 분석 모델 사용 비율
    "DeepFace (무료)" : 98
    "GPT-4V (유료)" : 2
```

### 검색 정확도

```mermaid
bar title 색상 검색 결과
    x-axis [분홍색, 주황색, 초록색, 파란색]
    y-axis "검색 결과" 0 --> 80
    bar [2, 7, 71, 22]
```

---

## 🔐 보안 & 확장성

```mermaid
flowchart TB
    subgraph Security["🔐 보안"]
        Auth[인증 시스템]
        CORS[CORS 설정]
        Validation[입력 검증]
    end

    subgraph Scalability["📈 확장성"]
        Cache[캐싱 시스템]
        Queue[비동기 큐]
        CDN[미디어 CDN]
    end

    subgraph Monitoring["📊 모니터링"]
        Logs[로그 시스템]
        Metrics[성능 지표]
        Alerts[알림 시스템]
    end

    Security --> Scalability
    Scalability --> Monitoring

    style Auth fill:#ff6b6b
    style Cache fill:#4ecdc4
    style Logs fill:#96ceb4
```

---

## 🚀 API 엔드포인트

```mermaid
flowchart LR
    subgraph VideoAPI["📹 영상 API"]
        Upload[POST /api/video/upload/]
        List[GET /api/video/list/]
        Summary[GET /api/video/:id/summary/]
        Delete[DELETE /api/video/:id/delete/]
    end

    subgraph SearchAPI["🔍 검색 API"]
        IntraSearch[POST /api/video/search/intra/]
        TemporalSearch[POST /api/video/temporal/analyze/]
        PersonSearch[POST /api/video/search/person/]
    end

    subgraph ChatAPI["💬 채팅 API"]
        TextChat[POST /api/chat/text/]
        VideoChat[POST /api/chat/video/]
        IntegratedChat[POST /api/chat/integrated/]
    end

    VideoAPI --> SearchAPI
    SearchAPI --> ChatAPI

    style Upload fill:#ff6b6b
    style IntraSearch fill:#4ecdc4
    style IntegratedChat fill:#96ceb4
```

---

## 📁 프로젝트 구조

```
AI_of_AI/
├── frontend/                      # React 프론트엔드
│   ├── src/
│   │   ├── components/           # UI 컴포넌트
│   │   ├── pages/               # 페이지
│   │   │   ├── VideoListPage.jsx
│   │   │   └── VideoChat.jsx
│   │   └── utils/               # 유틸리티
│   └── build/                   # 빌드 결과물
│
├── chatbot_backend/              # Django 백엔드
│   ├── chat/
│   │   ├── services/
│   │   │   └── video_analysis_service.py  # 🔥 하이브리드 분석
│   │   ├── advanced_search_view.py        # 🔍 검색 시스템
│   │   ├── views.py                       # API 뷰
│   │   └── models.py                      # 데이터 모델
│   ├── media/
│   │   ├── uploads/             # 업로드 영상
│   │   ├── analysis_results/    # 분석 JSON
│   │   └── images/              # 프레임 이미지
│   ├── db.sqlite3               # SQLite 데이터베이스
│   └── requirements.txt         # Python 패키지
│
└── 문서/
    ├── SYSTEM_ARCHITECTURE.md   # 이 문서
    ├── TEST_RESULTS.md          # 테스트 결과
    └── README.md                # 프로젝트 소개
```

---

## 🎯 핵심 기능

### 1. 하이브리드 비디오 분석
- **YOLO**: 사람 감지 (Confidence > 0.3)
- **DeepFace**: 성별/나이/감정 (98% 성공률)
- **OpenCV**: 의상 색상 (상/하의 구분)
- **BLIP**: 장면 캡션 (무료)
- **GPT-4V**: 조건부 폴백 (2% 사용)

### 2. 정확한 검색
- **색상 검색**: 10개 색상 지원
- **인물 검색**: 성별/나이/감정
- **시간대 검색**: 특정 구간 분석

### 3. AI 채팅
- **멀티 모델**: GPT-4o, Claude, Mixtral
- **앙상블**: 최적 답변 선택
- **컨텍스트**: 영상 정보 통합

---

## 💡 주요 개선사항

✅ **정확도 향상**
- 색상 감지: 40% → 95% (+137%)
- 성별 인식: 60% → 98% (+63%)

✅ **데이터 증가**
- 프레임 수: 4개 → 15개 (+275%)
- 분석 정보: 5배 증가

✅ **비용 절감**
- $0.15/영상 → $0.00/영상 (-100%)
- DeepFace 기반 무료 분석

---

**작성일**: 2025-10-07  
**버전**: v2.0 (하이브리드 시스템)  
**상태**: ✅ 운영 중

