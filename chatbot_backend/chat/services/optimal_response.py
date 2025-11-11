"""
최적 응답 생성 서비스
심판 모델을 통한 다중 LLM 응답 검증 및 최적 답변 생성
"""
import os
import re
import json
import asyncio
import aiohttp
import openai
import anthropic
from groq import Groq
import ollama

# 로컬 imports
from ..utils.error_handlers import get_user_friendly_error_message
from ..utils.ai_utils import enforce_korean_instruction, get_openai_completion_limit


def detect_question_type_from_content(content):
    """질문 내용에서 실제 질문 유형 감지: code, image, document, creative, general"""
    import re
    
    content_lower = content.lower()
    
    # 코드 관련 키워드 (코드 작성, 구현, 함수, 알고리즘 등)
    code_keywords = ['코드', 'code', '함수', 'function', '프로그래밍', 'programming', '알고리즘', 'algorithm', 
                     '구현', 'implement', '작성', 'write', '개발', 'develop', '스크립트', 'script',
                     '파이썬', 'python', '자바', 'java', '자바스크립트', 'javascript', 'c++', 'c#']
    
    # 이미지 관련 키워드
    image_keywords = ['이미지', 'image', '사진', 'photo', '그림', 'picture', '시각', 'visual', '화면']
    
    # 문서 관련 키워드
    document_keywords = ['문서', 'document', 'pdf', '파일', 'file', '요약', 'summary', '내용', 'content']
    
    # 창작/글쓰기 관련 키워드
    creative_keywords = ['글쓰기', 'writing', '창작', 'creative', '소설', 'novel', '시', 'poem', '에세이', 'essay',
                        '이야기', 'story', '내용 작성', 'write content', '문장', 'sentence']
    
    # 코드 관련 질문 감지
    if any(keyword in content_lower for keyword in code_keywords):
        # 실제 코드 작성 요청인지 확인 (예: "코드 작성", "함수 만들어줘", "구현해줘" 등)
        code_patterns = [
            r'코드.*작성|작성.*코드',
            r'함수.*만들|만들.*함수',
            r'구현.*해|해.*구현',
            r'코드.*보여|보여.*코드',
            r'프로그램.*작성|작성.*프로그램',
            r'파이썬.*코드|코드.*파이썬',
            r'알고리즘.*구현|구현.*알고리즘'
        ]
        if any(re.search(pattern, content_lower) for pattern in code_patterns):
            return 'code'
    
    # 이미지 관련 질문 감지 (이미지가 실제로 업로드된 경우는 has_image로 처리됨)
    if any(keyword in content_lower for keyword in image_keywords):
        # 이미지 분석 요청인지 확인
        image_patterns = [
            r'이미지.*분석|분석.*이미지',
            r'사진.*설명|설명.*사진',
            r'그림.*뭐|뭐.*그림',
            r'이미지.*뭐|뭐.*이미지'
        ]
        if any(re.search(pattern, content_lower) for pattern in image_patterns):
            return 'image'
    
    # 문서 관련 질문 감지
    if any(keyword in content_lower for keyword in document_keywords):
        # 문서 분석 요청인지 확인
        document_patterns = [
            r'문서.*분석|분석.*문서',
            r'파일.*내용|내용.*파일',
            r'pdf.*요약|요약.*pdf',
            r'문서.*요약|요약.*문서'
        ]
        if any(re.search(pattern, content_lower) for pattern in document_patterns):
            return 'document'
    
    # 창작/글쓰기 관련 질문 감지
    if any(keyword in content_lower for keyword in creative_keywords):
        # 창작 요청인지 확인
        creative_patterns = [
            r'글.*쓰|쓰.*글',
            r'소설.*작성|작성.*소설',
            r'시.*작성|작성.*시',
            r'이야기.*만들|만들.*이야기',
            r'창작.*해|해.*창작',
            r'에세이.*작성|작성.*에세이'
        ]
        if any(re.search(pattern, content_lower) for pattern in creative_patterns):
            return 'creative'
    
    # 기본값: 일반 질문
    return 'general'


def classify_question_type(question):
    """질문 유형 자동 분류: 사실(Factual) vs 의견(Opinion)"""
    try:
        import openai
        import os
        
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        classification_prompt = f"""
다음 질문이 "사실적 질문", "의견/추천 질문", 또는 "코드/프로그래밍 질문"인지 분류하세요.

질문: "{question}"

분류 기준:
- 사실적 질문: 객관적 사실, 정확한 답이 존재 (예: 설립연도, 위치, 역사적 사실)
- 의견/추천 질문: 주관적 평가, 추천, 선호도 (예: 맛집 추천, 좋은 카페, 최고의 제품)
- 코드/프로그래밍 질문: 코드 작성, 프로그래밍 예제, 알고리즘 구현 요청 (예: "별찍기 코드", "파이썬으로 작성", "함수 만들어줘")

JSON 형식으로만 응답:
{{
  "type": "factual" 또는 "opinion" 또는 "code",
  "confidence": 0.0-1.0,
  "reason": "분류 이유"
}}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 질문 유형 분류 전문가입니다. JSON 형식으로만 응답하세요."},
                {"role": "user", "content": classification_prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        print(f"📝 질문 유형: {result['type']} (신뢰도: {result['confidence']})")
        print(f"   이유: {result['reason']}")
        
        return result['type']
        
    except Exception as e:
        print(f"⚠️ 질문 분류 실패: {e}, 기본값 'factual' 사용")
        return "factual"


def collect_multi_llm_responses(user_message, judge_model="GPT-4o", selected_models=None, question_type=None):
    """1단계: 선택된 LLM들에게 병렬 질의 후 심판 모델로 검증"""
    import asyncio
    import aiohttp
    import json
    import time
    
    responses = {}
    
    # 사용 가능한 LLM 엔드포인트들 (명시적 모델명 사용)
    all_llm_endpoints = {
        # GPT 모델들 (최신 추가)
        'GPT-5': 'http://localhost:8000/chat/gpt-5/',
        'GPT-5-Mini': 'http://localhost:8000/chat/gpt-5-mini/',
        'GPT-4.1': 'http://localhost:8000/chat/gpt-4.1/',
        'GPT-4.1-Mini': 'http://localhost:8000/chat/gpt-4.1-mini/',
        'GPT-4o': 'http://localhost:8000/chat/gpt-4o/',
        'GPT-4o-Mini': 'http://localhost:8000/chat/gpt-4o-mini/',
        'GPT-4-Turbo': 'http://localhost:8000/chat/gpt-4-turbo/',
        'GPT-3.5-Turbo': 'http://localhost:8000/chat/gpt-3.5-turbo/',
        
        # Gemini 모델들 (최신 추가)
        'Gemini-2.5-Pro': 'http://localhost:8000/chat/gemini-2.5-pro/',
        'Gemini-2.5-Flash': 'http://localhost:8000/chat/gemini-2.5-flash/',
        'Gemini-2.0-Flash-Exp': 'http://localhost:8000/chat/gemini-2.0-flash-exp/',
        'Gemini-2.0-Flash-Lite': 'http://localhost:8000/chat/gemini-2.0-flash-lite/',
        
        # Claude 모델들 (최신 추가)
        'Claude-4-Opus': 'http://localhost:8000/chat/claude-4-opus/',
        'Claude-3.7-Sonnet': 'http://localhost:8000/chat/claude-3.7-sonnet/',
        'Claude-3.5-Sonnet': 'http://localhost:8000/chat/claude-3.5-sonnet/',
        'Claude-3.5-Haiku': 'http://localhost:8000/chat/claude-3.5-haiku/',
        'Claude-3-Opus': 'http://localhost:8000/chat/claude-3-opus/',
        
        # HyperCLOVA X 모델들
        'HCX-003': 'http://localhost:8000/chat/clova-hcx-003/',
        'HCX-DASH-001': 'http://localhost:8000/chat/clova-hcx-dash-001/',
    }
    
    # 사용자가 선택한 모델들만 필터링 (기본값: 모든 모델)
    if selected_models:
        print(f"📋 selected_models 입력: {selected_models} (타입: {type(selected_models)})")
        # 선택된 모델명을 표준 형식으로 변환
        model_mapping = {
            # GPT 모델들
            'gpt-5': 'GPT-5',
            'gpt-5-mini': 'GPT-5-Mini',
            'gpt-4.1': 'GPT-4.1',
            'gpt-4.1-mini': 'GPT-4.1-Mini',
            'gpt-4o': 'GPT-4o',
            'gpt-4o-mini': 'GPT-4o-Mini',
            'gpt-4-turbo': 'GPT-4-Turbo',
            'gpt-3.5-turbo': 'GPT-3.5-Turbo',
            
            # Gemini 모델들
            'gemini-2.5-pro': 'Gemini-2.5-Pro',
            'gemini-2.5-flash': 'Gemini-2.5-Flash',
            'gemini-2.0-flash-exp': 'Gemini-2.0-Flash-Exp',
            'gemini-2.0-flash-lite': 'Gemini-2.0-Flash-Lite',
            
            # Claude 모델들
            'claude-4-opus': 'Claude-4-Opus',
            'claude-3.7-sonnet': 'Claude-3.7-Sonnet',
            'claude-3.5-sonnet': 'Claude-3.5-Sonnet',
            'claude-3.5-haiku': 'Claude-3.5-Haiku',
            'claude-3-opus': 'Claude-3-Opus',
            
            # HyperCLOVA X 모델들
            'clova-hcx-003': 'HCX-003',
            'clova-hcx-dash-001': 'HCX-DASH-001',
        }
        
        selected_standard_models = []
        for model in selected_models:
            model_lower = model.lower() if isinstance(model, str) else str(model).lower()
            if model_lower in model_mapping:
                selected_standard_models.append(model_mapping[model_lower])
            else:
                print(f"⚠️ 알 수 없는 모델명: {model}")
        
        # 선택된 모델들의 엔드포인트만 사용
        llm_endpoints = {k: v for k, v in all_llm_endpoints.items() if k in selected_standard_models}
        print(f"📋 매핑된 표준 모델: {selected_standard_models}")
    else:
        # 선택된 모델이 없으면 기본 모델 3개 사용 (비용 절감)
        print(f"⚠️ selected_models가 없습니다. 기본 모델 3개 사용")
        default_models = ['GPT-4o-Mini', 'Gemini-2.0-Flash-Lite', 'Claude-3.5-Haiku']
        llm_endpoints = {k: v for k, v in all_llm_endpoints.items() if k in default_models}
    
    if not llm_endpoints:
        print(f"❌ 사용 가능한 LLM 엔드포인트가 없습니다!")
        raise ValueError("사용 가능한 LLM 모델이 없습니다. selected_models를 확인해주세요.")
    
    print(f"🎯 선택된 LLM 모델들: {list(llm_endpoints.keys())} (총 {len(llm_endpoints)}개)")
    
    async def fetch_response(session, ai_name, endpoint):
        """개별 LLM에서 응답 가져오기"""
        try:
            payload = {
                'message': user_message,
                'user_id': 'system'
            }
            
            print(f"🔄 {ai_name} 모델에 요청 전송 중... (엔드포인트: {endpoint})")
            async with session.post(endpoint, json=payload, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    response_content = result.get('response', '응답 없음')
                    print(f"✅ {ai_name} 응답 수신 완료: {len(str(response_content))}자")
                    print(f"📄 {ai_name} 응답 내용 (처음 200자): {str(response_content)[:200]}...")
                    return ai_name, response_content
                else:
                    # HTTP 상태 코드 오류를 친화적 메시지로 변환
                    error_text = await response.text()
                    print(f"❌ {ai_name} HTTP 오류: {response.status}, 내용: {error_text[:200]}")
                    error_msg = Exception(f"HTTP {response.status}: {error_text}")
                    friendly_msg = get_user_friendly_error_message(error_msg)
                    return ai_name, friendly_msg
        except Exception as e:
            # 예외를 친화적 메시지로 변환
            print(f"❌ {ai_name} 요청 중 예외 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            friendly_msg = get_user_friendly_error_message(e)
            return ai_name, friendly_msg
    
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
        
        # 에러 메시지 필터링 (타임아웃/네트워크 오류 등)
        # get_user_friendly_error_message가 반환하는 정확한 에러 메시지 패턴
        error_patterns = [
            "네트워크 연결에 문제가 발생했습니다",
            "요청 시간이 초과되었습니다",
            "서버에 일시적인 문제가 발생했습니다",
            "API 인증에 실패했습니다",
            "모델 사용량이 초과되었습니다",
            "사용량 한도를 초과했습니다",
            "오류가 발생했습니다. 잠시 후 다시 시도해 주세요",
            "연결할 수 없습니다",
            "대화 길이가 너무 깁니다",
            "콘텐츠 정책에 의해 차단되었습니다"
        ]
        
        valid_responses = {}
        error_responses = {}
        
        for ai_name, response in responses.items():
            response_str = str(response)
            # 정확한 에러 패턴 매칭 (부분 문자열이 아닌 전체 메시지 확인)
            is_error = any(pattern in response_str for pattern in error_patterns)
            
            # 응답이 너무 짧고 에러 키워드를 포함하면 에러로 간주
            if len(response_str) < 50 and any(keyword in response_str.lower() for keyword in ["timeout", "connection", "error", "오류", "실패"]):
                is_error = True
            
            if is_error:
                error_responses[ai_name] = response
                print(f"⚠️ {ai_name} 응답이 에러 메시지로 감지됨: {response_str[:100]}...")
            else:
                valid_responses[ai_name] = response
                print(f"✅ {ai_name} 유효한 응답: {len(response_str)}자")
        
        print(f"📊 유효한 응답: {len(valid_responses)}개, 에러 응답: {len(error_responses)}개")
        
        # 유효한 응답이 없으면 에러
        if not valid_responses:
            if error_responses:
                error_summary = ", ".join([f"{name}: {msg[:50]}..." for name, msg in list(error_responses.items())[:3]])
                raise ValueError(f"모든 LLM 요청이 실패했습니다. ({error_summary})")
            else:
                print(f"❌ 수집된 응답이 없습니다!")
                raise ValueError("LLM에서 응답을 받지 못했습니다.")
        
        # 유효한 응답만 사용하여 최적 답변 생성
        print(f"⚖️ 심판 모델({judge_model})로 검증 및 최적 답변 생성 시작... (유효한 응답 {len(valid_responses)}개 사용)")
        print(f"📋 질문 유형: {question_type}")
        final_result = judge_and_generate_optimal_response(valid_responses, user_message, judge_model, question_type=question_type)
        print(f"✅ 최적 답변 생성 완료: {type(final_result)}, 키: {list(final_result.keys()) if isinstance(final_result, dict) else 'N/A'}")
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


def extract_sentences_from_response(response_text):
    """응답 텍스트에서 문장 단위로 추출 (마크다운 코드 블록 포함)"""
    import re
    
    sentences = []
    
    # 1. 마크다운 코드 블록 추출 (```로 감싸진 부분)
    code_blocks = re.findall(r'```[\s\S]*?```', response_text)
    for code_block in code_blocks:
        sentences.append(code_block.strip())
    
    # 2. 코드 블록을 제외한 나머지 텍스트에서 문장 추출
    text_without_code = re.sub(r'```[\s\S]*?```', '', response_text)
    
    # 3. 문장 분리 (마침표, 느낌표, 물음표 기준)
    text_sentences = re.split(r'[.!?]\s+', text_without_code)
    for sentence in text_sentences:
        sentence = sentence.strip()
        if len(sentence) > 10:  # 너무 짧은 문장 제외
            sentences.append(sentence)
    
    return sentences


def judge_and_generate_optimal_response(llm_responses, user_question, judge_model="GPT-5", question_type=None):
    """하이브리드 검증 시스템: LLM 비교 + 선택적 웹 검증 + 다수결"""
    try:
        print(f"🔍 하이브리드 검증 시작: {user_question}")
        print(f"📋 judge_and_generate_optimal_response에 전달된 llm_responses 키: {list(llm_responses.keys()) if llm_responses else 'None'}")
        
        # 0단계: 질문 유형 분류 (전달받지 않은 경우에만 자동 분류)
        if question_type is None:
            question_type = classify_question_type(user_question)
        else:
            print(f"📋 전달받은 질문 유형: {question_type}")
        
        # 1단계: 각 AI 응답을 문장 단위로 분할
        print(f"📝 각 AI 응답을 문장 단위로 분할...")
        llm_sentences = {}
        for model_name, response in llm_responses.items():
            sentences = extract_sentences_from_response(response)
            llm_sentences[model_name] = sentences
            print(f"  - {model_name}: {len(sentences)}개 문장 추출")
        
        # 2단계: 상호모순 감지
        conflicts = detect_conflicts_in_responses(llm_responses)
        print(f"📊 감지된 상호모순: {conflicts}")
        
        # 3단계: 심판 프롬프트 구성
        model_sections = []
        for model_name, response in llm_responses.items():
            model_sections.append(f"[{model_name} 답변]\n{response}")
        
        model_responses_text = "\n\n".join(model_sections)
        
        # 각 AI의 문장 목록을 프롬프트에 추가
        sentences_sections = []
        for model_name, sentences in llm_sentences.items():
            sentences_list = "\n".join([f"  {i+1}. {s[:100]}..." if len(s) > 100 else f"  {i+1}. {s}" for i, s in enumerate(sentences)])
            sentences_sections.append(f"[{model_name} 문장 목록]\n{sentences_list}")
        
        sentences_text = "\n\n".join(sentences_sections)
        
        # 질문 유형에 따른 프롬프트 (코드 질문은 간단하게)
        if question_type == "code":
            judge_prompt = f"""
질문: {user_question}

**제공된 AI 코드 답변들:**
{model_responses_text}

**🚨 절대 준수 규칙:**
1. **반드시 위 AI 답변의 실제 코드만 사용** - 새로운 코드 작성 절대 금지
2. **여러 AI의 코드를 조합하여 최적화** - 단일 AI 코드 복사 금지
3. **마크다운 코드 블록 형식 유지** (```python ... ```)
4. **각 AI의 코드를 그대로 복사**하여 adopted_info/rejected_info 작성

**verification_results 작성 규칙:**
- **adopted_info**: 해당 AI가 제공한 코드 중 **실제로 사용된 부분**을 원본 그대로 복사
- **rejected_info**: 해당 AI가 제공한 코드 중 **사용되지 않은 부분**을 원본 그대로 복사
- **반드시 해당 AI의 원본 답변에서 직접 복사**해야 함

JSON 응답:
{{
  "optimal_answer": "여러 AI 코드를 조합한 최적 코드 (마크다운 형식)",
  "verification_results": {{
    "AI모델명": {{
      "accuracy": "정확성",
      "errors": "오류 설명",
      "confidence": "신뢰도",
      "adopted_info": ["실제 사용된 코드 부분"],
      "rejected_info": ["사용되지 않은 코드 부분"]
    }}
  }},
  "confidence_score": "신뢰도 0-100",
  "contradictions_detected": [],
  "fact_verification": {{}},
  "analysis_rationale": "조합 근거"
}}
"""
        else:
            # 일반 질문용 프롬프트 (교집합 기반)
            judge_prompt = f"""
질문: {user_question}

**제공된 AI 답변들:**
{model_responses_text}

**각 AI의 문장 목록 (선택 가능한 문장들):**
{sentences_text}

**🚨 절대 준수 핵심 규칙:**
1. **위 문장 목록의 문장들만 사용** - 새로운 문장 작성 절대 금지
2. **각 AI가 실제로 말한 문장만 채택/제외 가능**
3. **여러 AI에서 공통으로 나온 정보 우선 채택** (교집합 기반)
4. **한 AI만 언급한 정보는 신중하게 검토**
5. **절대 새로운 내용을 추론하거나 생성하지 마세요**

**optimal_answer 작성 방법:**
- 위 문장 목록에서 **실제 문장을 선택**하여 조합
- **여러 AI가 공통으로 언급한 정보** 우선 선택
- 선택한 문장은 **원문 그대로** 사용 (수정/요약 금지)
- 문장들을 자연스럽게 연결 (문장 순서 조정 가능)

**verification_results 작성 규칙:**
- **adopted_info**: 해당 AI의 문장 목록에서 **실제로 채택된 문장**을 원문 그대로 복사
- **rejected_info**: 해당 AI의 문장 목록에서 **제외된 문장**을 원문 그대로 복사
- **반드시 해당 AI의 문장 목록에 있는 문장만 사용**
- **다른 AI의 문장을 해당 AI의 채택/제외 정보에 포함하면 안됨**

**예시:**
GPT-4o가 "충북대학교는 1951년에 설립되었습니다."라고 말했다면
→ adopted_info: ["충북대학교는 1951년에 설립되었습니다."]

Gemini가 "충북대학교는 1946년에 설립되었습니다."라고 말했다면
→ rejected_info: ["충북대학교는 1946년에 설립되었습니다."]

**❌ 절대 금지:**
- 위 문장 목록에 없는 새로운 문장 생성
- 여러 문장을 요약하여 새로운 문장 만들기
- AI가 말하지 않은 내용을 해당 AI의 채택/제외 정보에 포함
- 다른 AI의 문장을 해당 AI의 채택/제외 정보에 포함

JSON 응답:
{{
  "optimal_answer": "위 문장 목록에서 선택한 문장들을 조합한 답변",
  "verification_results": {{
    "AI모델명": {{
      "accuracy": "정확성",
      "errors": "오류 설명",
      "confidence": "신뢰도",
      "adopted_info": ["해당 AI의 문장 목록에서 채택된 원문"],
      "rejected_info": ["해당 AI의 문장 목록에서 제외된 원문"]
    }}
  }},
  "confidence_score": "신뢰도 0-100",
  "contradictions_detected": ["상호모순 사항"],
  "fact_verification": {{"dates": [], "locations": [], "facts": []}},
  "analysis_rationale": "문장 선택 근거"
}}
"""
        
        # 심판 모델 호출
        print(f"📞 심판 모델({judge_model}) 호출 시작...")
        judge_response = call_judge_model(judge_model, judge_prompt)
        print(f"✅ 심판 모델 응답 받음: {len(judge_response) if judge_response else 0}자")
        
        # 결과 파싱
        print(f"📝 심판 모델 응답 파싱 시작...")
        parsed_result = parse_judge_response(judge_response, judge_model, llm_responses, llm_sentences)
        print(f"✅ 파싱 완료")
        
        return parsed_result
        
    except Exception as e:
        print(f"❌ 심판 모델 검증 실패: {e}")
        import traceback
        print(f"상세 에러: {traceback.format_exc()}")
        
        # 폴백: 가장 긴 응답을 최적 답변으로 사용
        if llm_responses:
            longest_response = max(llm_responses.values(), key=len)
            return {
                "최적의_답변": longest_response,
                "llm_검증_결과": {
                    model: {
                        "정확성": "❌",
                        "오류": "검증 실패 - Judge 모델 오류",
                        "신뢰도": "0",
                        "채택된_정보": [],
                        "제외된_정보": []
                    }
                    for model in llm_responses.keys()
                },
                "심판모델": judge_model,
                "상태": "검증 실패",
                "원본_응답": llm_responses
            }
        return {
            "최적의_답변": "검증 중 오류가 발생했습니다.",
            "llm_검증_결과": {},
            "심판모델": judge_model,
            "상태": "오류",
            "원본_응답": llm_responses or {}
        }


def call_judge_model(model_name, prompt):
    """심판 모델 호출"""
    try:
        if model_name in ['GPT-5', 'GPT-3.5-turbo', 'GPT-4', 'GPT-4o', 'GPT-4o-mini']:
            # OpenAI 모델 사용
            import openai
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                raise ValueError("OpenAI API 키가 설정되지 않음")
            
            client = openai.OpenAI(api_key=openai_api_key)
            
            # 모델명을 OpenAI API 형식으로 변환
            openai_model_name = model_name.lower().replace('-', '-')
            if model_name == 'GPT-5':
                openai_model_name = 'gpt-5'
            elif model_name == 'GPT-4':
                openai_model_name = 'gpt-4'
            elif model_name == 'GPT-4o':
                openai_model_name = 'gpt-4o'
            elif model_name == 'GPT-4o-mini':
                openai_model_name = 'gpt-4o-mini'
            elif model_name == 'GPT-3.5-turbo':
                openai_model_name = 'gpt-3.5-turbo'
            
            # 최신 OpenAI 모델(o1, o3 등)은 max_completion_tokens 사용 및 temperature 미지원
            is_latest_model = any(model in openai_model_name.lower() for model in ['o1', 'o3', 'gpt-5'])
            
            api_params = {
                "model": openai_model_name,
                "messages": [
                    {"role": "system", "content": """당신은 텍스트 분석 전문가입니다. 당신의 역할은 각 AI의 답변을 **있는 그대로 분석**하는 것입니다.

🚨 절대 규칙:
1. **각 AI가 실제로 말한 문장만** adopted_info/rejected_info에 복사
2. **절대 새로운 문장을 만들지 마세요** - 환각(hallucination) 금지!
3. **각 AI의 문장은 해당 AI의 원본 답변에 있어야 합니다**
4. **다른 AI의 문장을 복사하면 안됩니다**
5. **여러 AI가 공통으로 언급한 정보를 우선 채택**

✅ 올바른 분석:
- 각 AI의 원본 답변에서 문장을 그대로 복사
- 여러 AI가 공통으로 언급한 정보 우선 선택
- 한 AI만 언급한 정보는 신중하게 검토

❌ 잘못된 분석 (환각):
- 원본 답변에 없는 새로운 문장 생성
- 여러 문장을 요약하여 새로운 문장 만들기
- 다른 AI의 문장을 해당 AI의 채택/제외 정보에 포함
- AI가 말하지 않은 내용을 만들어내기

JSON 형식으로만 응답하세요."""},
                    {"role": "user", "content": prompt}
                ],
            }
            
            if not is_latest_model:
                api_params["temperature"] = 0.0
            
            completion_limit = get_openai_completion_limit(openai_model_name)
            if is_latest_model:
                api_params["max_completion_tokens"] = completion_limit
            else:
                api_params["max_tokens"] = completion_limit
                api_params["response_format"] = {"type": "json_object"}
            
            response = client.chat.completions.create(**api_params)
            response_content = response.choices[0].message.content.strip()
            
            if response.choices[0].finish_reason == 'length':
                print(f"⚠️ {model_name} 응답이 토큰 제한으로 잘렸습니다")
                response_content += "\n\n[응답이 토큰 제한으로 인해 잘렸습니다.]"
            
            return response_content
            
        else:
            # 기본값으로 GPT-5 사용
            return call_judge_model('GPT-5', prompt)
            
    except Exception as e:
        print(f"❌ 심판 모델 {model_name} 호출 실패: {e}")
        import traceback
        print(f"상세 에러: {traceback.format_exc()}")
        raise e


def parse_judge_response(judge_response, judge_model, llm_responses=None, llm_sentences=None):
    """심판 모델 JSON 응답 파싱 및 검증"""
    try:
        import json
        import re
        
        # JSON 부분만 추출
        json_match = re.search(r'\{.*\}', judge_response, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                parsed_data = json.loads(json_str)
                print(f"✅ JSON 파싱 성공!")
            except json.JSONDecodeError as e:
                print(f"❌ JSON 파싱 실패: {e}")
                return create_fallback_result(judge_model, llm_responses)
            
            result = {
                "최적의_답변": parsed_data.get("optimal_answer", ""),
                "llm_검증_결과": {},
                "심판모델": judge_model,
                "상태": "성공",
                "신뢰도": parsed_data.get("confidence_score", "50"),
                "상호모순": parsed_data.get("contradictions_detected", []),
                "사실검증": parsed_data.get("fact_verification", {}),
                "분석_근거": parsed_data.get("analysis_rationale", "")
            }
            
            # 검증 결과 파싱 및 검증
            verification_results = parsed_data.get("verification_results", {})
            
            for model_name, verification in verification_results.items():
                adopted_info = verification.get("adopted_info", [])
                rejected_info = verification.get("rejected_info", [])
                
                # 🚨 환각 검증: 각 AI의 실제 응답과 대조
                if llm_responses and model_name in llm_responses:
                    original_response = llm_responses[model_name]
                    
                    # adopted_info 검증
                    validated_adopted = []
                    for item in adopted_info:
                        if isinstance(item, str) and item.strip():
                            # 실제 응답에 포함되어 있는지 확인 (유사도 검사)
                            item_normalized = re.sub(r'\s+', ' ', item.strip().lower())
                            response_normalized = re.sub(r'\s+', ' ', original_response.lower())
                            
                            # 긴 문장은 부분 매칭 허용 (80% 이상)
                            if len(item_normalized) > 50:
                                words = item_normalized.split()
                                match_count = sum(1 for word in words if word in response_normalized)
                                if match_count / len(words) >= 0.8:
                                    validated_adopted.append(item.strip())
                                else:
                                    print(f"⚠️ {model_name} adopted_info 환각 감지: {item[:50]}...")
                            else:
                                # 짧은 문장은 정확한 매칭 요구
                                if item_normalized in response_normalized:
                                    validated_adopted.append(item.strip())
                                else:
                                    print(f"⚠️ {model_name} adopted_info 환각 감지: {item[:50]}...")
                    
                    # rejected_info 검증
                    validated_rejected = []
                    for item in rejected_info:
                        if isinstance(item, str) and item.strip():
                            item_normalized = re.sub(r'\s+', ' ', item.strip().lower())
                            response_normalized = re.sub(r'\s+', ' ', original_response.lower())
                            
                            if len(item_normalized) > 50:
                                words = item_normalized.split()
                                match_count = sum(1 for word in words if word in response_normalized)
                                if match_count / len(words) >= 0.8:
                                    validated_rejected.append(item.strip())
                                else:
                                    print(f"⚠️ {model_name} rejected_info 환각 감지: {item[:50]}...")
                            else:
                                if item_normalized in response_normalized:
                                    validated_rejected.append(item.strip())
                                else:
                                    print(f"⚠️ {model_name} rejected_info 환각 감지: {item[:50]}...")
                    
                    # 검증된 정보로 업데이트
                    adopted_info = validated_adopted
                    rejected_info = validated_rejected
                    
                    # 둘 다 비어있으면 원본 응답에서 자동 추출
                    if not adopted_info and not rejected_info:
                        print(f"⚠️ {model_name}: 검증 후 채택/제외 정보가 모두 비어있음. 원본에서 추출...")
                        sentences = extract_sentences_from_response(original_response)
                        adopted_info = sentences[:3] if sentences else []
                
                print(f"📊 {model_name}: 검증 후 adopted={len(adopted_info)}개, rejected={len(rejected_info)}개")
                
                result["llm_검증_결과"][model_name] = {
                    "정확성": verification.get("accuracy", "정확"),
                    "오류": verification.get("errors", "없음"),
                    "신뢰도": verification.get("confidence", "50"),
                    "채택된_정보": adopted_info,
                    "제외된_정보": rejected_info
                }
            
            # 누락된 모델 처리
            if llm_responses:
                for model_name in llm_responses.keys():
                    if model_name not in result["llm_검증_결과"]:
                        print(f"⚠️ {model_name}: Judge 결과 누락. 기본 정보 생성...")
                        sentences = extract_sentences_from_response(llm_responses[model_name])
                        result["llm_검증_결과"][model_name] = {
                            "정확성": "✅",
                            "오류": "정확한 정보 제공",
                            "신뢰도": "50",
                            "채택된_정보": sentences[:3] if sentences else [],
                            "제외된_정보": []
                        }
                
                result["원본_응답"] = llm_responses
            
            return result
        else:
            return create_fallback_result(judge_model, llm_responses)
            
    except Exception as e:
        print(f"❌ JSON 파싱 실패: {e}")
        return create_fallback_result(judge_model, llm_responses)


def create_fallback_result(judge_model, llm_responses=None):
    """폴백 결과 생성"""
    if llm_responses:
        actual_models = list(llm_responses.keys())
    else:
        actual_models = []
    
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
        adopted_info = []
        if llm_responses and model in llm_responses:
            sentences = extract_sentences_from_response(llm_responses[model])
            adopted_info = sentences[:3] if sentences else []
        
        result["llm_검증_결과"][model] = {
            "정확성": "❌",
            "오류": "검증 실패 - Judge 모델 오류",
            "신뢰도": "0",
            "채택된_정보": adopted_info,
            "제외된_정보": []
        }
    
    if llm_responses:
        result["원본_응답"] = llm_responses
    
    return result


def format_optimal_response(final_result):
    """최적 답변 결과를 사용자 친화적 형식으로 포맷팅"""
    try:
        print(f"🔍 format_optimal_response 시작...")
        
        optimal_answer = final_result.get("최적의_답변", "")
        verification_results = final_result.get("llm_검증_결과", {})
        
        # 최적 답변이 비어있는 경우 체크
        if not optimal_answer or len(optimal_answer.strip()) == 0:
            print(f"⚠️ 최적 답변이 비어있습니다! 폴백 메시지 생성...")
            optimal_answer = "최적 답변 생성 중 오류가 발생했습니다. 각 AI 모델의 개별 응답을 확인해주세요."
        
        # 메인 답변 구성 (채팅 창에는 최적 답변 본문만 표시)
        formatted_response = f"""## 최적의 답변

{optimal_answer}
"""
        
        return formatted_response
        
    except Exception as e:
        print(f"❌ 응답 포맷팅 실패: {e}")
        return f"""**최적의 답변:**

{final_result.get('최적의_답변', '답변 생성 실패')}

*포맷팅 오류 발생*
"""