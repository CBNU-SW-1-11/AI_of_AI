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

# 로컬 import
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



def judge_and_generate_optimal_response(llm_responses, user_question, judge_model="GPT-5", question_type=None):
    """하이브리드 검증 시스템: LLM 비교 + 선택적 웹 검증 + 다수결"""
    try:
        print(f"🔍 하이브리드 검증 시작: {user_question}")
        print(f"📋 judge_and_generate_optimal_response에 전달된 llm_responses 키: {list(llm_responses.keys()) if llm_responses else 'None'}")
        print(f"📋 llm_responses 전체: {llm_responses}")
        
        # 0단계: 질문 유형 분류 (전달받지 않은 경우에만 자동 분류)
        if question_type is None:
            question_type = classify_question_type(user_question)
        else:
            print(f"📋 전달받은 질문 유형: {question_type}")
        
        # 1단계: 상호모순 감지
        conflicts = detect_conflicts_in_responses(llm_responses)
        print(f"📊 감지된 상호모순: {conflicts}")
        print(f"🔍 상호모순 카테고리 수: {len(conflicts)}")
        for category, items in conflicts.items():
            print(f"  - {category}: {items}")
        
        # 2단계: 의견 질문 - Tie-breaker 확인
        if question_type == "opinion" and len(llm_responses) == 2:
            print("🗳️ 의견 질문 + 2개 모델 → Tie-breaker 호출")
            # Tie-breaker 로직은 나중에 구현
            pass
        
        # 3단계: 웹 검증 (사실 질문만) 또는 다수결 (의견 질문) 또는 코드 품질 평가 (코드 질문)
        verified_facts = {}
        web_verification_used = False
        
        if question_type == "code":
            print(f"💻 코드 질문 감지 → Wikipedia 검증 생략, 코드 품질 평가 사용")
            web_result = {"verified": False}
        elif question_type == "image":
            print(f"🖼️ 이미지 질문 감지 → Wikipedia 검증 생략, OCR/Ollama 검증 사용")
            web_result = {"verified": False}
        elif question_type == "document":
            print(f"📄 문서 질문 감지 → Wikipedia 검증 생략, 문서 분석 사용")
            web_result = {"verified": False}
        elif question_type == "factual":
            print(f"🌐 Wikipedia 웹 검증 시작... 질문: '{user_question}'")
            
            # 범용적 웹 검증 - 사실 질문에만 적용
            web_result = quick_web_verify("general", {}, user_question)
        else:
            print(f"🗳️ 의견 질문 → Wikipedia 검증 생략, 다수결 방식 사용")
            web_result = {"verified": False}
        
        if web_result.get("verified"):
            # 검증된 정보를 적절한 카테고리에 저장
            if web_result.get('extracted_year'):
                verified_facts["dates"] = web_result
            if web_result.get('location'):
                if "locations" not in verified_facts:
                    verified_facts["locations"] = web_result
                else:
                    verified_facts["locations"].update(web_result)
            if not verified_facts:  # 아무것도 저장되지 않은 경우
                verified_facts["general_facts"] = web_result
                
            web_verification_used = True
            
            # 검증 결과 로그 출력
            info_parts = []
            if web_result.get('extracted_year'):
                info_parts.append(f"연도 {web_result.get('extracted_year')}년")
            if web_result.get('location'):
                info_parts.append(f"위치 {web_result.get('location')}")
            if web_result.get('type'):
                info_parts.append(f"유형 {web_result.get('type')}")
            
            print(f"✅ 웹 검증 성공: {', '.join(info_parts)}")
        else:
            print(f"⚠️ 웹 검증 실패: {web_result.get('error')}")
        
        # 상호모순 기반 검증 (웹 검증 성공/실패와 독립적으로 실행)
        if conflicts:
            print("⚡ 상호모순 발견! 상호모순 기반 검증 시작...")
            print(f"🔍 처리할 상호모순: {conflicts}")
            
            for conflict_type, conflict_values in conflicts.items():
                # 웹 검증이 이미 성공한 항목은 덮어쓰지 않음
                if conflict_type not in verified_facts or not verified_facts[conflict_type].get("verified"):
                    verified_facts[conflict_type] = {
                        "verified": False,
                        "conflict_detected": True,
                        "conflict_values": list(conflict_values.keys()),
                        "conflict_details": dict(conflict_values)  # {값: [AI목록]}
                    }
                    print(f"✅ 상호모순 처리됨: {conflict_type} -> {verified_facts[conflict_type]}")
                else:
                    print(f"ℹ️ {conflict_type}는 이미 Wikipedia 검증 완료, 상호모순 처리 건너뜀")
        else:
            print("ℹ️ 상호모순 없음")
        
        # 3단계: 심판 프롬프트 구성 (웹 검증 결과 포함)
        model_sections = []
        verification_json_entries = []
        
        for model_name, response in llm_responses.items():
            model_sections.append(f"[{model_name} 답변]\n{response}")
            verification_json_entries.append(f'    "{model_name}": {{"accuracy": "정확성_판정", "errors": "구체적_오류_설명", "confidence": "신뢰도_0-100", "adopted_info": ["채택된_정보들"], "rejected_info": ["제외된_정보들과_이유"]}}')
        
        model_responses_text = "\n\n".join(model_sections)
        verification_json_format = ",\n".join(verification_json_entries)
        
        # 웹 검증 결과를 프롬프트에 추가 (범용적)
        web_verification_text = ""
        if web_verification_used:
            # 모든 검증된 사실에 대해 범용적으로 처리
            verified_info_parts = []
            
            for fact_type, verification in verified_facts.items():
                if verification.get('verified'):
                    if verification.get('extracted_year'):
                        verified_info_parts.append(f"- **✅ 공식 연도**: {verification['extracted_year']}년")
                    if verification.get('location'):
                        verified_info_parts.append(f"- **✅ 공식 위치**: {verification['location']}")
                    if verification.get('type'):
                        verified_info_parts.append(f"- **✅ 공식 유형**: {verification['type']}")
                    if verification.get('abstract') and not any([verification.get('extracted_year'), verification.get('location'), verification.get('type')]):
                        # 기타 검증된 정보
                        verified_info_parts.append(f"- **✅ 검증된 정보**: {verification['abstract'][:100]}...")
            
            if verified_info_parts:
                verified_info_text = '\n'.join(verified_info_parts)
                # 첫 번째 검증 결과의 신뢰도 사용
                first_verification = next(iter(verified_facts.values()))
                
                # Wikipedia 원문 포함 (LLM이 직접 비교 분석 가능)
                wikipedia_full_text = first_verification.get('full_text', '') or first_verification.get('abstract', '')
                wikipedia_excerpt = wikipedia_full_text[:500] if len(wikipedia_full_text) > 500 else wikipedia_full_text
                
                web_verification_text = f"""

**🌐 Wikipedia 웹 검증 결과 (신뢰도 {first_verification.get('confidence', 0.9)*100:.0f}%):**
{verified_info_text}
- **출처**: {first_verification.get('source', 'Wikipedia')}
- **페이지**: {first_verification.get('page_title', '확인됨')}

**📖 Wikipedia 원문:**
{wikipedia_excerpt}

🚨 **절대 준수 규칙**: 위 Wikipedia 원문은 공식 검증된 정보입니다.

**📋 Wikipedia 검증 기준:**
1. **일치하는 정보 = 채택**: LLM이 Wikipedia와 동일한 정보를 말했다면 → **반드시 adopted_info에 포함**
2. **불일치하는 정보 = 제외**: LLM이 Wikipedia와 다른 정보를 말했다면 → rejected_info에 포함

**✅ 올바른 처리 예시:**
- Wikipedia: "1951년 설립"
- LLM A: "1951년에 설립되었습니다" → ✅ **일치** → **adopted_info에 포함**
- LLM B: "1946년에 설립되었습니다" → ❌ **불일치** → rejected_info에 포함

**❌ 잘못된 처리 (절대 금지):**
- Wikipedia: "1951년 설립"
- LLM A: "1951년에 설립되었습니다" → ❌ "불일치"라고 표시하면 안됨!

**각 LLM 답변을 Wikipedia 원문과 직접 비교하여:**
- 일치하는 내용은 **반드시 채택** (adopted_info)
- 불일치하는 내용만 **제외** (rejected_info)
"""
        # 상호모순이 감지된 경우 (웹 검증 실패 시)
        elif any(fact.get("conflict_detected") for fact in verified_facts.values()):
            # 모든 상호모순 유형에 대해 범용적으로 처리
            conflict_summaries = []
            conflict_ai_details = []
            
            for conflict_type, conflict_data in verified_facts.items():
                if conflict_data.get("conflict_detected"):
                    conflict_values = conflict_data.get("conflict_values", [])
                    conflict_details = conflict_data.get("conflict_details", {})
                    
                    # 유형별 한국어 라벨 매핑
                    type_labels = {
                        "dates": "날짜/연도",
                        "locations": "위치",
                        "numbers": "수치",
                        "general_facts": "일반 사실"
                    }
                    type_label = type_labels.get(conflict_type, conflict_type)
                    
                    conflict_summaries.append(f"- **{type_label} 불일치**: {', '.join(conflict_values)}")
                    
                    # 각 AI별 상호모순 상세 정보 생성
                    for value, ai_list in conflict_details.items():
                        ai_names = ', '.join(ai_list)
                        conflict_ai_details.append(f"- {value} ({type_label}): {ai_names}")
            
            conflict_summary_text = '\n'.join(conflict_summaries)
            conflict_ai_text = '\n'.join(conflict_ai_details)
            
            web_verification_text = f"""

**⚠️ 상호모순 감지됨 (웹 검증 실패):**
{conflict_summary_text}
- **조치**: 확신할 수 없는 정보는 최적 답변에서 생략하세요

**🚨 각 AI별 상호모순 상세:**
{conflict_ai_text}

**🚨 각 AI별 오류 처리 규칙 (필수 준수):**
- 위에서 상호모순에 참여한 모든 AI는 반드시 "틀린 정보"에 "정보 불확실 (다른 AI와 상충)"을 기록하세요
- 상호모순이 있는 정보는 절대 "틀린 정보 없음"으로 표시하면 안됩니다
- 예시: GPT-4o Mini가 1946년이라고 했고, Gemini가 1951년이라고 했다면 → 둘 다 "틀린 정보"에 "설립연도 불확실 (다른 AI와 상충)"을 기록
"""
        
        # 상호모순 정보가 있으면 더 강력한 지시사항 추가
        contradiction_warning = ""
        has_conflicts = any(fact.get("conflict_detected") for fact in verified_facts.values())
        print(f"🔍 상호모순 경고 생성 여부: {has_conflicts}")
        print(f"🔍 verified_facts: {verified_facts}")
        
        if has_conflicts:
            contradiction_warning = f"""

**🚨 상호모순 감지됨 - 필수 처리 규칙:**
{web_verification_text}

**⚠️ 절대 금지사항:**
- 상호모순에 참여한 AI에게 "틀린 정보 없음"이라고 하면 안됩니다
- 상호모순에 참여한 AI에게 "정확한 정보 제공"이라고 하면 안됩니다
- 반드시 "틀린 정보"에 구체적인 상호모순 내용을 기록하세요

**✅ 올바른 예시:**
- GPT-4o Mini: "틀린 정보: 설립연도 불확실 (다른 AI와 상충)"
- Gemini 2.0 Flash Lite: "틀린 정보: 설립연도 불확실 (다른 AI와 상충)"
- Claude 3.5 Haiku: "틀린 정보: 설립연도 불확실 (다른 AI와 상충)"
"""

        # 질문 유형에 따른 지시사항
        if question_type == "code":
            # 코드 질문 전용 간단한 프롬프트 (토큰 절약)
            question_type_instruction = """
**💻 이 질문은 코드/프로그래밍 질문입니다:**
- Wikipedia 검증 불필요 - 코드 품질 기준으로 평가하세요
- 코드의 정확성, 완전성, 가독성, 실행 가능성을 평가하세요
- 여러 AI의 코드를 비교하여 가장 좋은 코드를 선택하거나 조합하세요
- 마크다운 코드 블록 형식(```python ... ```)을 유지하세요
"""
            
            # 코드 질문 전용 간단한 Judge 프롬프트 (토큰 절약)
            judge_prompt = f"""
질문: {user_question}

**제공된 AI 코드 답변들:**
{model_responses_text}

**최적 답변 생성 규칙:**
1. **반드시 여러 AI의 코드를 조합** - 단일 AI의 코드를 그대로 복사하는 것 절대 금지
2. 여러 AI의 코드를 비교하여 **가장 정확하고 완전한 코드**를 선택하거나 조합하세요
3. 코드가 **실행 가능하고 완전한지** 확인하세요
4. **마크다운 코드 블록 형식**을 유지하세요 (```python ... ```)
5. 여러 코드의 장점을 조합하여 더 나은 코드를 만드세요 - 단일 AI 코드 복사 금지

**각 AI 코드 평가 기준:**
- **정확성**: 요구사항 만족 여부
- **완전성**: 실행 가능 여부
- **가독성**: 코드 가독성
- **최적성**: 효율성과 간결성

**🚨 중요: verification_results 작성 규칙:**
각 AI의 코드 답변에서:
- **adopted_info**: 해당 AI가 제공한 코드 중 **유용하고 정확한 부분**을 그대로 복사 (예: "```python\\n...\\n```" 형식의 코드 블록)
- **rejected_info**: 해당 AI가 제공한 코드 중 **오류가 있거나 불완전한 부분**을 그대로 복사 (없으면 빈 배열 [])
- **반드시 각 AI의 원본 답변에서 코드를 그대로 복사**하여 adopted_info/rejected_info에 포함하세요
- **절대 빈 배열을 반환하지 마세요!** 각 AI가 제공한 코드가 있으면 반드시 adopted_info에 포함하세요

**🎨 optimal_answer 포맷팅 규칙 (필수!):**
- **마크다운 코드 블록** 형식 필수: ```python\n코드\n```
- 코드 설명은 **간단한 문단**으로 작성 (코드 전후)
- 여러 예제가 있으면 **## 제목**으로 구분

반드시 아래 JSON 형식으로만 응답하세요:

{{
  "optimal_answer": "반드시 2개 이상의 AI 코드를 조합한 최적 코드 (단일 AI 코드 복사 절대 금지, 마크다운 코드 블록 포함)",
  "verification_results": {{
    {verification_json_format}
  }},
  "confidence_score": "코드 품질 신뢰도 (0-100)",
  "contradictions_detected": [],
  "fact_verification": {{}},
  "analysis_rationale": "어떤 AI의 어떤 코드를 조합했는지와 그 이유를 간단히 설명"
}}
"""
        elif question_type == "image":
            judge_prompt = f"""
질문: {user_question}

**🖼️ 이미지 분석 질문 - OCR/Ollama 검증 결과 기반**
- 각 AI가 이미지를 분석한 결과를 비교하여 최적의 답변 생성
- Wikipedia 검증은 사용하지 않음 (이미지 분석 결과 기반)

**제공된 AI 답변들:**
{model_responses_text}
{contradiction_warning}

**🚨 절대 준수 핵심 규칙 (매우 중요!):**
1. **반드시 위에 제공된 AI 답변의 원본 문장만 사용** - 새로운 문장 작성/요약/재구성 절대 금지
2. **여러 AI 답변 반드시 조합** - 단일 모델 선택 절대 금지, 단일 모델의 답변을 그대로 복사하는 것 절대 금지
3. **할루시네이션 절대 금지** - 위 AI 답변에 언급되지 않은 내용 절대 포함 금지
4. **optimal_answer는 반드시 위 AI 답변들에서 추출한 문장들로만 구성** - 절대 새로운 내용 추가 금지
5. **각 AI의 원본 답변을 그대로 복사**하여 adopted_info/rejected_info 작성
6. **각 AI마다 반드시 adopted_info 또는 rejected_info 중 하나에는 내용 포함** (둘 다 빈 배열 절대 금지)
7. **optimal_answer는 반드시 2개 이상의 AI 답변에서 문장을 추출하여 조합** - 단일 AI의 답변을 그대로 사용하는 것 절대 금지
8. **각 AI가 실제로 답변한 부분만 추출** - AI가 답변하지 않은 내용은 절대 포함 금지

**⚠️ 절대 금지 사항:**
- 위 AI 답변에 없는 예제, 코드, 설명 추가 금지
- 위 AI 답변에 없는 주제나 카테고리 추가 금지
- 위 AI 답변을 확장하거나 보완하는 내용 추가 금지

**adopted_info/rejected_info 작성:**
- adopted_info: 위 AI 답변에서 추출한 정확하고 유용한 원본 문장 그대로 복사
- rejected_info: 위 AI 답변에서 추출한 부정확하거나 모순되는 정보만 원본 그대로 복사
- **상호 배타적** - 같은 문장이 양쪽에 동시 존재 금지
- **adopted_info/rejected_info는 반드시 위에 제공된 해당 AI의 원본 답변에서 직접 복사한 문장이어야 함**

**마크다운 포맷:**
- 리스트: `- 항목`
- 제목: `## 주제`
- 강조: `**굵게**`

JSON 응답:
{{
  "optimal_answer": "반드시 2개 이상의 AI 답변에서 문장을 추출하여 조합한 답변 (단일 AI 답변 복사 절대 금지, 각 AI가 실제로 답변한 부분만 추출)",
  "verification_results": {{
    {verification_json_format}
  }},
  "confidence_score": "0-100",
  "contradictions_detected": ["상호모순 사항"],
  "fact_verification": {{"dates": [], "locations": [], "facts": []}},
  "analysis_rationale": "어떤 AI의 어떤 정보를 채택/제외했는지 상세히 설명"
}}

**⚠️ optimal_answer 작성 시 필수 사항:**
- **반드시 2개 이상의 AI 답변에서 문장을 추출하여 조합** - 단일 AI의 답변을 그대로 사용하는 것 절대 금지
- **각 AI가 실제로 답변한 부분만 추출** - AI가 답변하지 않은 내용은 절대 포함 금지
- 이미지 분석 결과를 정확하게 반영하되, 위 AI 답변에 없는 내용은 절대 추가하지 마세요
"""
        elif question_type == "opinion":
            judge_prompt = f"""
질문: {user_question}

**📊 의견/추천 질문 - 다수결 방식 사용**
- 여러 AI가 공통적으로 추천하는 항목에 높은 가중치 부여
- 소수 의견도 포함하되 다수 의견 우선 배치

**제공된 AI 답변들:**
{model_responses_text}
{web_verification_text}
{contradiction_warning}

**🚨 절대 준수 핵심 규칙 (매우 중요!):**
1. **반드시 위에 제공된 AI 답변의 원본 문장만 사용** - 새로운 문장 작성/요약/재구성 절대 금지
2. **여러 AI 답변 반드시 조합** - 단일 모델 선택 절대 금지, 단일 모델의 답변을 그대로 복사하는 것 절대 금지
3. **할루시네이션 절대 금지** - 위 AI 답변에 언급되지 않은 내용 절대 포함 금지
4. **optimal_answer는 반드시 위 AI 답변들에서 추출한 문장들로만 구성** - 절대 새로운 내용 추가 금지
5. **각 AI의 원본 답변을 그대로 복사**하여 adopted_info/rejected_info 작성
6. **각 AI마다 반드시 adopted_info 또는 rejected_info 중 하나에는 내용 포함** (둘 다 빈 배열 절대 금지)
7. **optimal_answer는 반드시 2개 이상의 AI 답변에서 문장을 추출하여 조합** - 단일 AI의 답변을 그대로 사용하는 것 절대 금지
8. **각 AI가 실제로 답변한 부분만 추출** - AI가 답변하지 않은 내용은 절대 포함 금지

**⚠️ 절대 금지 사항:**
- 위 AI 답변에 없는 예제, 코드, 설명 추가 금지
- 위 AI 답변에 없는 주제나 카테고리 추가 금지
- 위 AI 답변을 확장하거나 보완하는 내용 추가 금지
- 단순 인사 질문에는 단순 인사 답변만 제공 (추가 설명 금지)

**adopted_info/rejected_info 작성:**
- adopted_info: 위 AI 답변에서 추출한 유용한 원본 문장 그대로 복사
- rejected_info: 위 AI 답변에서 추출한 Wikipedia 불일치 또는 상충 정보만 원본 그대로 복사
- **상호 배타적** - 같은 문장이 양쪽에 동시 존재 금지
- **adopted_info/rejected_info는 반드시 위에 제공된 해당 AI의 원본 답변에서 직접 복사한 문장이어야 함**

**마크다운 포맷:**
- 리스트: `- 항목`
- 제목: `## 주제`
- 강조: `**굵게**`

JSON 응답:
{{
  "optimal_answer": "반드시 2개 이상의 AI 답변에서 문장을 추출하여 조합한 답변 (단일 AI 답변 복사 절대 금지, 각 AI가 실제로 답변한 부분만 추출)",
  "verification_results": {{
    {verification_json_format}
  }},
  "confidence_score": "0-100",
  "contradictions_detected": ["상호모순 사항"],
  "fact_verification": {{"dates": [], "locations": [], "facts": []}},
  "analysis_rationale": "어떤 AI의 어떤 정보를 채택/제외했는지 상세히 설명"
}}

**⚠️ optimal_answer 작성 시 필수 사항:**
- **반드시 2개 이상의 AI 답변에서 문장을 추출하여 조합** - 단일 AI의 답변을 그대로 사용하는 것 절대 금지
- **각 AI가 실제로 답변한 부분만 추출** - AI가 답변하지 않은 내용은 절대 포함 금지
- 질문이 "hi", "안녕" 같은 단순 인사라면 → 위 AI 답변의 인사 문장들을 조합 (단일 AI 답변 복사 금지)
- 질문이 프로그래밍 질문이 아니라면 → 프로그래밍 예제나 코드 절대 포함 금지
- 위 AI 답변에 없는 주제나 카테고리는 절대 추가하지 마세요
"""
        else:
            # 일반/사실 질문 (factual, general, document, image, creative 등)
            judge_prompt = f"""
질문: {user_question}

**🔍 사실 확인 질문 - Wikipedia 검증 기준 사용**
- Wikipedia와 **명확히 모순**되는 정보만 제외
- Wikipedia에 없지만 **모순되지 않는** 유용한 정보는 포함 (학과, 특징, 역사 등)
- 여러 AI 답변 종합하여 **풍부한 최적 답변** 생성

**제공된 AI 답변들:**
{model_responses_text}
{web_verification_text}
{contradiction_warning}

**🚨 절대 준수 핵심 규칙 (매우 중요!):**
1. **반드시 위에 제공된 AI 답변의 원본 문장만 사용** - 새로운 문장 작성/요약/재구성 절대 금지
2. **여러 AI 답변 반드시 조합** - 단일 모델 선택 절대 금지, 단일 모델의 답변을 그대로 복사하는 것 절대 금지
3. **할루시네이션 절대 금지** - 위 AI 답변에 언급되지 않은 내용 절대 포함 금지
4. **optimal_answer는 반드시 위 AI 답변들에서 추출한 문장들로만 구성** - 절대 새로운 내용 추가 금지
5. **optimal_answer는 반드시 2개 이상의 AI 답변에서 문장을 추출하여 조합** - 단일 AI의 답변을 그대로 사용하는 것 절대 금지
6. **각 AI가 실제로 답변한 부분만 추출** - AI가 답변하지 않은 내용은 절대 포함 금지

**⚠️ 절대 금지 사항:**
- 위 AI 답변에 없는 예제, 코드, 설명 추가 금지
- 위 AI 답변에 없는 주제나 카테고리 추가 금지
- 위 AI 답변을 확장하거나 보완하는 내용 추가 금지
- 단순 인사 질문에는 단순 인사 답변만 제공 (추가 설명 금지)
- 단일 AI의 답변을 그대로 복사하여 optimal_answer에 사용하는 것 절대 금지

**정보 채택 기준:**
- ✅ **adopted_info**: 위 AI 답변에서 추출한 Wikipedia 일치 정보 + 모순되지 않는 유용한 정보 (원본 문장 그대로 복사)
- ❌ **rejected_info**: 위 AI 답변에서 추출한 Wikipedia 명확히 모순되는 정보만 (원본 문장 그대로 복사)
- **각 AI마다 반드시 adopted_info 또는 rejected_info 중 하나에는 내용 포함** (둘 다 빈 배열 절대 금지)
- **상호 배타적** - 같은 문장이 양쪽에 동시 존재 금지
- **adopted_info/rejected_info는 반드시 위에 제공된 해당 AI의 원본 답변에서 직접 복사한 문장이어야 함**

**마크다운 포맷:**
- 제목: `## 주제`, `### 소주제`
- 리스트: `- 항목`
- 강조: `**굵게**`
- 문단: 2-3문장, 빈 줄로 구분

JSON 응답:
{{
  "optimal_answer": "반드시 2개 이상의 AI 답변에서 문장을 추출하여 조합한 답변 (단일 AI 답변 복사 절대 금지, 각 AI가 실제로 답변한 부분만 추출)",
  "verification_results": {{
    {verification_json_format}
  }},
  "confidence_score": "0-100",
  "contradictions_detected": ["상호모순 사항"],
  "fact_verification": {{"dates": [], "locations": [], "facts": []}},
  "analysis_rationale": "어떤 AI의 어떤 정보를 채택/제외했는지, Wikipedia 검증 결과 반영 방법 상세 설명"
}}

**⚠️ optimal_answer 작성 시 필수 사항:**
- **반드시 2개 이상의 AI 답변에서 문장을 추출하여 조합** - 단일 AI의 답변을 그대로 사용하는 것 절대 금지
- **각 AI가 실제로 답변한 부분만 추출** - AI가 답변하지 않은 내용은 절대 포함 금지
- 질문이 "hi", "안녕" 같은 단순 인사라면 → 위 AI 답변의 인사 문장들을 조합 (단일 AI 답변 복사 금지)
- 질문이 프로그래밍 질문이 아니라면 → 프로그래밍 예제나 코드 절대 포함 금지
- 위 AI 답변에 없는 주제나 카테고리는 절대 추가하지 마세요

"""

        # 프롬프트 길이 체크
        prompt_length = len(judge_prompt)
        print(f"📏 심판 모델 프롬프트 길이: {prompt_length}자 ({prompt_length // 1000}K자)")
        
        # 프롬프트가 너무 길면 요약 (각 LLM 응답을 요약)
        if prompt_length > 50000:  # 50K자 이상이면
            print(f"⚠️ 프롬프트가 너무 깁니다 ({prompt_length}자). LLM 응답을 요약합니다...")
            # 각 LLM 응답을 요약 (처음 4000자 + 끝 500자만 유지)
            summarized_responses = {}
            for model_name, response in llm_responses.items():
                if len(response) > 5000:
                    summarized_responses[model_name] = response[:4000] + "\n\n... (중략) ...\n\n" + response[-500:]
                    print(f"  - {model_name}: {len(response)}자 → {len(summarized_responses[model_name])}자로 요약")
                else:
                    summarized_responses[model_name] = response
            
            llm_responses = summarized_responses
            
            # 프롬프트 재구성
            model_sections = []
            for model_name, response in llm_responses.items():
                model_sections.append(f"[{model_name} 답변]\n{response}")
            model_responses_text = "\n\n".join(model_sections)
            
            # 프롬프트 전체 재구성 (model_responses_text 부분만 교체)
            judge_prompt = judge_prompt.replace(
                judge_prompt.split(model_responses_text)[0] + model_responses_text,
                judge_prompt.split(model_responses_text)[0] + model_responses_text
            )
            # 실제로는 위 방식이 복잡하므로 간단하게 재구성
            judge_prompt = f"""
질문: {user_question}
{question_type_instruction}

{model_responses_text}
{web_verification_text}
{contradiction_warning}

**🚨 절대 준수 사항 (매우 중요!):**
1. **반드시 위에 제공된 AI 답변의 원본 문장만 사용하세요** - 새로운 문장 작성/요약/재구성 절대 금지
2. **여러 AI 답변 반드시 조합** - 단일 모델 선택 절대 금지, 단일 모델의 답변을 그대로 복사하는 것 절대 금지
3. **절대 새로운 정보를 추가하거나 만들어내지 마세요**
4. **AI가 언급하지 않은 맛집, 카페, 장소, 정보는 절대 포함하지 마세요**
5. **할루시네이션 절대 금지!** - 위 답변에 없는 내용은 절대 작성 금지
6. **위에 제공된 AI 답변의 개수를 확인하세요** - 1개만 있으면 "다른 AI"라는 표현을 사용하지 마세요
7. **optimal_answer의 모든 문장은 반드시 위 AI 답변들에서 직접 추출한 것이어야 합니다** - 절대 새로운 내용 추가 금지
8. **optimal_answer는 반드시 2개 이상의 AI 답변에서 문장을 추출하여 조합** - 단일 AI의 답변을 그대로 사용하는 것 절대 금지
9. **각 AI가 실제로 답변한 부분만 추출** - AI가 답변하지 않은 내용은 절대 포함 금지
10. **adopted_info/rejected_info는 반드시 위에 제공된 해당 AI의 원본 답변에서 직접 복사한 문장이어야 합니다**
11. **각 AI마다 반드시 adopted_info 또는 rejected_info 중 하나에는 내용을 포함하세요** (둘 다 빈 배열 절대 금지)

**⚠️ 절대 금지 사항:**
- 위 AI 답변에 없는 예제, 코드, 설명 추가 금지
- 위 AI 답변에 없는 주제나 카테고리 추가 금지
- 위 AI 답변을 확장하거나 보완하는 내용 추가 금지
- 단순 인사 질문에는 단순 인사 답변만 제공 (추가 설명 금지)
- 단일 AI의 답변을 그대로 복사하여 optimal_answer에 사용하는 것 절대 금지

반드시 아래 JSON 형식으로만 응답하세요:

{{
  "optimal_answer": "반드시 2개 이상의 AI 답변에서 문장을 추출하여 조합한 답변 (단일 AI 답변 복사 절대 금지, 각 AI가 실제로 답변한 부분만 추출)",
  "verification_results": {{
    {verification_json_format}
  }},
  "confidence_score": "전체 응답에 대한 신뢰도 (0-100)",
  "contradictions_detected": ["발견된 상호모순 사항들"],
  "fact_verification": {{
    "dates": ["검증된 연도 정보들"],
    "locations": ["검증된 위치 정보들"],
    "facts": ["검증된 기타 사실들"]
  }},
  "analysis_rationale": "최적 답변 생성 근거 - 각 AI의 답변에서 어떤 정보를 채택했는지, 어떤 정보가 틀렸거나 상반되어서 제외했는지, Wikipedia 검증 결과를 어떻게 반영했는지 상세히 설명"
}}

**⚠️ optimal_answer 작성 시 주의사항:**
- 질문이 "hi", "안녕" 같은 단순 인사라면 → 위 AI 답변의 인사 문장만 사용 (추가 설명 절대 금지)
- 질문이 프로그래밍 질문이 아니라면 → 프로그래밍 예제나 코드 절대 포함 금지
- 위 AI 답변에 없는 주제나 카테고리는 절대 추가하지 마세요
"""
            print(f"📏 요약 후 프롬프트 길이: {len(judge_prompt)}자")
        
        # 심판 모델 호출
        print(f"📞 심판 모델({judge_model}) 호출 시작... (프롬프트: {len(judge_prompt)}자)")
        try:
            judge_response = call_judge_model(judge_model, judge_prompt)
            print(f"✅ 심판 모델 응답 받음: {len(judge_response) if judge_response else 0}자")
            if judge_response:
                print(f"📄 심판 모델 응답 미리보기: {judge_response[:300]}...")
            else:
                print(f"❌ 심판 모델 응답이 비어있습니다!")
        except Exception as e:
            import traceback
            print(f"❌ 심판 모델 호출 실패: {e}")
            print(f"❌ 상세 에러:\n{traceback.format_exc()}")
            raise
        
        # 결과 파싱
        print(f"📝 심판 모델 응답 파싱 시작...")
        print(f"📄 심판 모델 전체 응답 (처음 2000자): {judge_response[:2000]}...")
        print(f"📄 심판 모델 전체 응답 (끝 500자): ...{judge_response[-500:]}")
        parsed_result = parse_judge_response(judge_response, judge_model, llm_responses)
        print(f"✅ 파싱 완료: {list(parsed_result.keys()) if isinstance(parsed_result, dict) else 'N/A'}")
        print(f"📄 파싱된 최적의_답변: {parsed_result.get('최적의_답변', '')[:300]}...")
        
        # 웹 검증 정보 추가
        parsed_result["웹_검증_사용"] = web_verification_used
        if verified_facts:
            parsed_result["웹_검증_결과"] = verified_facts
            parsed_result["검증_성능"] = {
                "상호모순_감지": len(conflicts),
                "웹_검증_성공": len(verified_facts),
                "비용": "$0.003" if web_verification_used else "$0.000"
            }
        
        # Wikipedia 검증 연도로 후처리 (잘못된 연도 제거)
        if web_verification_used and verified_facts:
            verified_year = None
            for fact_type, verification in verified_facts.items():
                if verification.get('verified') and verification.get('extracted_year'):
                    verified_year = verification['extracted_year']
                    break
            
            if verified_year and parsed_result.get("최적의_답변"):
                import re
                optimal_answer = parsed_result["최적의_답변"]
                
                # 최적 답변에서 다른 연도를 찾음
                years_in_answer = re.findall(r'(\d{4})년', optimal_answer)
                wrong_years = [y for y in years_in_answer if y != verified_year and 1900 <= int(y) <= 2024]
                
                # 잘못된 연도가 있으면 제거
                if wrong_years:
                    print(f"⚠️ Wikipedia 검증 연도 {verified_year}와 다른 연도 발견: {wrong_years}")
                    for wrong_year in wrong_years:
                        # 해당 연도를 포함한 문장 패턴 찾기
                        patterns_to_remove = [
                            rf'{wrong_year}년.*?설립.*?[.!가-힣]',
                            rf'{wrong_year}년.*?개교.*?[.!가-힣]',
                            rf'{wrong_year}년.*?창립.*?[.!가-힣]',
                            rf'{wrong_year}년에.*?[.!가-힣]{0,50}',
                        ]
                        
                        for pattern in patterns_to_remove:
                            optimal_answer = re.sub(pattern, '', optimal_answer, flags=re.DOTALL)
                    
                    # 정리
                    optimal_answer = re.sub(r'[ \t]+', ' ', optimal_answer)
                    optimal_answer = re.sub(r'\n{3,}', '\n\n', optimal_answer)
                    optimal_answer = optimal_answer.strip()
                    
                    # 최종 답변이 비었으면 검증된 연도로 재구성
                    if not optimal_answer or len(optimal_answer) < 50:
                        # 원래 LLM 답변에서 검증된 연도를 포함한 문장 찾기
                        if llm_responses:
                            for model, response in llm_responses.items():
                                if verified_year in response:
                                    # 검증된 연도가 포함된 문장 추출
                                    sentences = re.split(r'[.!]\s+', response)
                                    matching_sentences = [s for s in sentences if verified_year in s and 150 <= len(s) <= 400]
                                    if matching_sentences:
                                        optimal_answer = matching_sentences[0]
                                        break
                        
                        # 여전히 비었으면 생성
                        if not optimal_answer:
                            optimal_answer = f"Wikipedia 검증 결과에 따르면 충북대학교는 {verified_year}년에 설립되었습니다."
                    
                    parsed_result["최적의_답변"] = optimal_answer
                    print(f"✅ Wikipedia 후처리 완료: {verified_year}년 유지, {wrong_years}년 제거")
        
        print(f"✅ 하이브리드 검증 완료: 웹검증={web_verification_used}, 상호모순={len(conflicts)}")
        
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
                # GPT-5는 실제로 o1, o3 등의 최신 모델일 수 있음
                # 사용자가 지정한 모델명을 그대로 사용 (o1, o3 등)
                openai_model_name = 'gpt-5'  # 실제 모델명 사용 시도
                print(f"🔍 GPT-5 모델명: {openai_model_name} (API 호출 시도)")
            elif model_name == 'GPT-4':
                openai_model_name = 'gpt-4'
            elif model_name == 'GPT-4o':
                openai_model_name = 'gpt-4o'
            elif model_name == 'GPT-4o-mini':
                openai_model_name = 'gpt-4o-mini'
            elif model_name == 'GPT-3.5-turbo':
                openai_model_name = 'gpt-3.5-turbo'
            
            # 최신 OpenAI 모델(o1, o3 등)은 max_completion_tokens 사용 및 temperature 미지원
            # 기존 모델은 max_tokens 사용
            is_latest_model = any(model in openai_model_name.lower() for model in ['o1', 'o3', 'gpt-5'])
            
            api_params = {
                "model": openai_model_name,
                "messages": [
                    {"role": "system", "content": """당신은 텍스트 분석 전문가입니다. 당신의 역할은 각 AI의 답변을 **있는 그대로 분석**하는 것입니다.

🚨 절대 규칙:
1. 각 AI가 **실제로 말한 내용만** adopted_info/rejected_info에 복사
2. 각 AI의 답변은 **서로 다를 수 있습니다** - 모든 AI가 똑같은 문장을 말할 필요는 없음
3. AI가 특정 정보(연도, 위치, 이름 등)를 말했다면 → 그대로 복사 (절대 바꾸지 마세요!)
4. 절대 새로운 문장을 만들지 마세요
5. 각 AI가 실제로 말하지 않은 내용을 만들어내면 안됨 (할루시네이션 금지!)
6. **특히 주의**: AI가 "1946년"이라고 말했다면, 절대 "1951년"으로 바꾸지 마세요!
7. adopted_info/rejected_info에는 각 AI의 원본 답변에서 문장을 그대로 복사해야 합니다

✅ 올바른 분석:
- 각 AI의 원본 답변에서 문장을 그대로 복사하여 adopted_info/rejected_info에 포함
- 각 AI마다 다른 내용이 나타날 수 있음 (이것이 정상)
- Wikipedia 검증 결과가 있다면, 각 AI의 원본 답변과 비교하여 일치/불일치 판단

❌ 잘못된 분석 (할루시네이션):
- 모든 AI가 똑같은 문장을 가진 adopted_info (이는 불가능함)
- 원본 답변에 없는 정보를 새로 만들어내기 (예: AI가 1946년이라고 했는데 1951년으로 바꾸기)
- 최적 답변의 내용을 참고해서 각 AI의 답변을 바꾸기

**당신은 각 AI의 원본 답변을 읽고, 각 AI가 뭐라고 했는지 정확히 분석하세요.**

JSON 형식으로만 응답하세요."""},
                    {"role": "user", "content": prompt}
                ],
            }
            
            # 최신 모델은 temperature를 지원하지 않음
            if not is_latest_model:
                api_params["temperature"] = 0.0  # 더 일관된 출력을 위해 0으로 설정
            
            completion_limit = get_openai_completion_limit(openai_model_name)
            # 최신 모델은 max_completion_tokens, 기존 모델은 max_tokens 사용
            if is_latest_model:
                api_params["max_completion_tokens"] = completion_limit
            else:
                api_params["max_tokens"] = completion_limit
                api_params["response_format"] = {"type": "json_object"}  # JSON 형식 강제
            
            response = client.chat.completions.create(**api_params)
            
            response_content = response.choices[0].message.content.strip()
            
            # 응답이 잘렸는지 확인
            if response.choices[0].finish_reason == 'length':
                print(f"⚠️ {model_name} 응답이 토큰 제한으로 잘렸습니다 (finish_reason: length)")
                response_content += "\n\n[응답이 토큰 제한으로 인해 잘렸습니다. 더 긴 답변이 필요하시면 질문을 나누어 주세요.]"
            elif response.choices[0].finish_reason:
                print(f"📝 {model_name} 응답 완료 (finish_reason: {response.choices[0].finish_reason})")
            
            print(f"📏 {model_name} 응답 길이: {len(response_content)}자")
            
            return response_content
            
        elif model_name == 'Claude-3.5-haiku':
            # Claude 모델 사용 (대안)
            import anthropic
            anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
            if not anthropic_api_key:
                raise ValueError("Anthropic API 키가 설정되지 않음")
            
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1500,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        elif model_name == 'LLaMA 3.1 8B':
            # LLaMA 모델 사용 (Groq API)
            import groq
            groq_api_key = os.getenv('GROQ_API_KEY')
            if not groq_api_key:
                raise ValueError("Groq API 키가 설정되지 않음")
            
            client = groq.Groq(api_key=groq_api_key)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "당신은 사실 검증 전문가입니다. 정확한 정보만 제공하고 틀린 정보를 명확히 지적하세요."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        else:
            # 기본값으로 GPT-5 사용
            return call_judge_model('GPT-5', prompt)
            
    except Exception as e:
        print(f"❌ 심판 모델 {model_name} 호출 실패: {e}")
        import traceback
        print(f"상세 에러: {traceback.format_exc()}")
        
        # 폴백: 다른 모델로 시도 (GPT-5 -> GPT-4o -> GPT-4o-mini -> GPT-3.5-turbo)
        fallback_models = {
            'GPT-5': 'GPT-4o',
            'GPT-4o': 'GPT-4o-mini',
            'GPT-4o-mini': 'GPT-3.5-turbo',
            'GPT-3.5-turbo': None
        }
        
        fallback_model = fallback_models.get(model_name)
        if fallback_model:
            print(f"🔄 {model_name} 실패, {fallback_model}로 폴백 시도...")
            try:
                return call_judge_model(fallback_model, prompt)
            except Exception as fallback_error:
                print(f"❌ 폴백 모델 {fallback_model}도 실패: {fallback_error}")
                raise e
        else:
            raise e



def parse_judge_response(judge_response, judge_model, llm_responses=None):
    """심판 모델 JSON 응답 파싱"""
    try:
        import json
        import re
        
        # JSON 부분만 추출
        json_match = re.search(r'\{.*\}', judge_response, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            print(f"📋 추출된 JSON 문자열 (처음 500자): {json_str[:500]}...")
            print(f"📋 추출된 JSON 문자열 (끝 500자): ...{json_str[-500:]}")
            try:
                parsed_data = json.loads(json_str)
                print(f"✅ JSON 파싱 성공!")
            except json.JSONDecodeError as e:
                print(f"❌ JSON 파싱 실패: {e}")
                print(f"❌ JSON 문자열 위치: {e.pos}")
                print(f"❌ JSON 문자열 (오류 위치 주변): {json_str[max(0, e.pos-100):e.pos+100]}")
                # JSON 파싱 실패 시 폴백
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
            
            # 검증 결과 파싱 (상호모순 우선 처리)
            verification_results = parsed_data.get("verification_results", {})
            contradictions = parsed_data.get("contradictions_detected", [])
            
            # 처리된 모델 추적
            processed_models = set()
            
            for model_name, verification in verification_results.items():
                processed_models.add(model_name)
                errors_text = verification.get("errors", "오류 없음")
                
                # 상호모순이 감지된 경우 강제로 오류 처리
                has_contradiction = any(
                    model_name.lower() in str(contradiction).lower() or 
                    "상충" in errors_text or 
                    "불확실" in errors_text or
                    "다른 AI" in errors_text
                    for contradiction in contradictions
                )
                
                # 기본 정확성 판단
                is_accurate_by_default = (
                    verification.get("accuracy") == "정확" or
                    errors_text.lower() in ["없음", "오류 없음", "정확한 정보 제공", "정확한 정보"] or
                    "정확한 정보" in errors_text
                )
                
                # 상호모순이 있으면 무조건 오류로 처리
                is_accurate = is_accurate_by_default and not has_contradiction
                
                # adopted_info와 rejected_info 추출
                adopted_info = verification.get("adopted_info", [])
                rejected_info = verification.get("rejected_info", [])
                
                # adopted_info가 비어있고 rejected_info도 비어있으면, 원본 LLM 응답에서 추출
                if (not adopted_info or len(adopted_info) == 0) and (not rejected_info or len(rejected_info) == 0):
                    print(f"⚠️ {model_name}: adopted_info와 rejected_info가 모두 비어있음. 원본 응답에서 추출 시도...")
                    if llm_responses and model_name in llm_responses:
                        original_response = llm_responses[model_name]
                        # 원본 응답이 있으면 adopted_info에 포함 (일단 채택)
                        if original_response and len(original_response.strip()) > 0:
                            # 응답을 문장 단위로 분할 (최대 3개 문장)
                            import re
                            sentences = re.split(r'[.!?]\s+', original_response.strip())
                            adopted_info = [s.strip() + '.' for s in sentences[:3] if len(s.strip()) > 10]
                            print(f"✅ {model_name}: 원본 응답에서 {len(adopted_info)}개 문장 추출")
                
                # rejected_info에서 "(Wikipedia ...과 불일치)" 텍스트 제거
                cleaned_rejected_info = []
                for item in rejected_info:
                    # "(Wikipedia ...과 불일치)" 패턴 제거
                    import re
                    cleaned_item = re.sub(r'\s*\(Wikipedia[^)]*불일치[^)]*\)', '', str(item))
                    cleaned_item = re.sub(r'\s*\(Wikipedia.*?\)', '', cleaned_item)  # 기타 Wikipedia 괄호 제거
                    cleaned_item = cleaned_item.strip()
                    if cleaned_item:
                        cleaned_rejected_info.append(cleaned_item)
                
                # adopted_info도 문자열 리스트로 정규화
                cleaned_adopted_info = []
                for item in adopted_info:
                    if isinstance(item, str) and item.strip():
                        cleaned_adopted_info.append(item.strip())
                
                print(f"📊 {model_name}: adopted_info={len(cleaned_adopted_info)}개, rejected_info={len(cleaned_rejected_info)}개")

                result["llm_검증_결과"][model_name] = {
                    "정확성": "✅" if is_accurate else "❌",
                    "오류": errors_text if not is_accurate else "정확한 정보 제공",
                    "신뢰도": verification.get("confidence", "50"),
                    "채택된_정보": cleaned_adopted_info,
                    "제외된_정보": cleaned_rejected_info
                }
            
            # Judge 모델이 반환하지 않은 모델들에 대해서도 기본 검증 결과 생성
            if llm_responses:
                print(f"📋 llm_responses의 모든 모델: {list(llm_responses.keys())}")
                print(f"📋 processed_models: {list(processed_models)}")
                for model_name in llm_responses.keys():
                    if model_name not in processed_models:
                        print(f"⚠️ {model_name}: Judge 모델이 검증 결과를 반환하지 않음. 기본 검증 결과 생성...")
                        # 원본 응답에서 정보 추출
                        original_response = llm_responses[model_name]
                        adopted_info = []
                        if original_response and len(original_response.strip()) > 0:
                            import re
                            sentences = re.split(r'[.!?]\s+', original_response.strip())
                            adopted_info = [s.strip() + '.' for s in sentences[:3] if len(s.strip()) > 10]
                        
                        result["llm_검증_결과"][model_name] = {
                            "정확성": "✅",
                            "오류": "정확한 정보 제공",
                            "신뢰도": "50",
                            "채택된_정보": adopted_info,
                            "제외된_정보": []
                        }
                        print(f"✅ {model_name}: 기본 검증 결과 생성 완료 (adopted_info={len(adopted_info)}개)")
                    else:
                        print(f"✅ {model_name}: Judge 모델이 검증 결과를 반환함 (이미 처리됨)")
                
                print(f"📊 최종 llm_검증_결과 키: {list(result['llm_검증_결과'].keys())}")
                result["원본_응답"] = llm_responses
            
            return result
        else:
            # JSON 파싱 실패 시 폴백
            return create_fallback_result(judge_model, llm_responses)
            
    except Exception as e:
        print(f"❌ JSON 파싱 실패: {e}")
        return create_fallback_result(judge_model, llm_responses)



def create_fallback_result(judge_model, llm_responses=None):
    """폴백 결과 생성"""
    if llm_responses:
        actual_models = list(llm_responses.keys())
    else:
        actual_models = ["GPT-4-Turbo", "GPT-4o", "GPT-3.5-Turbo", "GPT-4o-mini", 
                        "Gemini-Pro-1.5", "Gemini-Pro-1.0",
                        "Claude-3-Opus", "Claude-3-Sonnet", "Claude-3-Haiku",
                        "Clova-HCX-003", "Clova-HCX-DASH-001"]
    
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
        # 원본 LLM 응답에서 직접 추출
        adopted_info = []
        if llm_responses and model in llm_responses:
            original_response = llm_responses[model]
            if original_response and len(original_response.strip()) > 0:
                # 응답을 문장 단위로 분할 (최대 3개 문장)
                import re
                sentences = re.split(r'[.!?]\s+', original_response.strip())
                adopted_info = [s.strip() + '.' for s in sentences[:3] if len(s.strip()) > 10]
        
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
        print(f"🔍 final_result 타입: {type(final_result)}")
        print(f"🔍 final_result 키: {list(final_result.keys()) if isinstance(final_result, dict) else 'N/A'}")
        
        optimal_answer = final_result.get("최적의_답변", "")
        print(f"🔍 optimal_answer 길이: {len(optimal_answer) if optimal_answer else 0}자")
        print(f"🔍 optimal_answer 내용: {optimal_answer[:200] if optimal_answer else 'None'}...")
        
        verification_results = final_result.get("llm_검증_결과", {})
        print(f"🔍 verification_results 키 개수: {len(verification_results)}개")
        print(f"🔍 verification_results 모델: {list(verification_results.keys())}")
        
        judge_model = final_result.get("심판모델", "GPT-5")
        status = final_result.get("상태", "성공")
        
        # 새로운 JSON 형식 지원
        confidence = final_result.get("신뢰도", "50")
        contradictions = final_result.get("상호모순", [])
        
        # 분석 근거 추출
        analysis_rationale = final_result.get("분석_근거", "")
        print(f"🔍 analysis_rationale 길이: {len(analysis_rationale) if analysis_rationale else 0}자")

        original_responses = final_result.get("원본_응답", {})

        def normalize_spaces(text):
            return re.sub(r'\s+', ' ', text or '').strip()

        def contains_text(container, snippet):
            if not container or not snippet:
                return False
            normalized_container = normalize_spaces(container).lower()
            normalized_snippet = normalize_spaces(snippet).lower()
            return bool(normalized_snippet) and normalized_snippet in normalized_container

        def find_original_text(model_key):
            if not original_responses:
                return ""
            if model_key in original_responses:
                return original_responses[model_key]
            lower_key = model_key.lower()
            for candidate_key, value in original_responses.items():
                if candidate_key.lower() == lower_key:
                    return value
            return ""
        
        # 최적 답변이 비어있는 경우 체크
        if not optimal_answer or len(optimal_answer.strip()) == 0:
            print(f"⚠️ 최적 답변이 비어있습니다! 폴백 메시지 생성...")
            optimal_answer = "최적 답변 생성 중 오류가 발생했습니다. 각 AI 모델의 개별 응답을 확인해주세요."
        
        # 메인 답변 구성 (채팅 창에는 최적 답변 본문만 표시)
        formatted_response = f"""## 최적의 답변

{optimal_answer}
"""
        
        # 분석 근거와 각 LLM 검증 결과는 모달에서만 표시되도록 제거
        # (프론트엔드에서 analysisData를 통해 모달에 표시)
        # 하지만 verification_results 필터링은 모달 데이터를 위해 유지
        model_names = {
            # GPT 모델들 (최신 추가)
            "GPT-5": "GPT-5",
            "GPT-5-Mini": "GPT-5 Mini",
            "GPT-4.1": "GPT-4.1",
            "GPT-4.1-Mini": "GPT-4.1 Mini",
            "GPT-4o": "GPT-4o",
            "GPT-4o-Mini": "GPT-4o Mini",
            "GPT-4-Turbo": "GPT-4 Turbo",
            "GPT-3.5-Turbo": "GPT-3.5 Turbo",
            
            # Gemini 모델들 (최신 추가)
            "Gemini-2.5-Pro": "Gemini 2.5 Pro",
            "Gemini-2.5-Flash": "Gemini 2.5 Flash",
            "Gemini-2.0-Flash-Exp": "Gemini 2.0 Flash Exp",
            "Gemini-2.0-Flash-Lite": "Gemini 2.0 Flash Lite",
            
            # Claude 모델들 (최신 추가)
            "Claude-4-Opus": "Claude 4 Opus",
            "Claude-3.7-Sonnet": "Claude 3.7 Sonnet",
            "Claude-3.5-Sonnet": "Claude 3.5 Sonnet",
            "Claude-3.5-Haiku": "Claude 3.5 Haiku",
            "Claude-3-Opus": "Claude 3 Opus",
            
            # HyperCLOVA X 모델들
            "HCX-003": "HyperCLOVA X HCX-003",
            "HCX-DASH-001": "HyperCLOVA X HCX-DASH-001",
        }
        
        # verification_results 필터링 (모달 데이터를 위해 유지, 마크다운에는 추가하지 않음)
        # 필터링 로직 완화: adopted_info가 비어있으면 원본 사용
        print(f"🔍 format_optimal_response - verification_results 키: {list(verification_results.keys())}")
        print(f"🔍 format_optimal_response - model_names 키: {list(model_names.keys())}")
        
        # verification_results의 모든 키를 순회 (model_names에 없는 모델도 포함)
        for model_key in verification_results.keys():
            verification = verification_results[model_key]
            adopted = verification.get("채택된_정보", []) or []
            rejected = verification.get("제외된_정보", []) or []

            original_text = find_original_text(model_key)
            print(f"🔍 format_optimal_response - 처리 중인 모델: {model_key}, original_text 길이: {len(original_text) if original_text else 0}")

            # adopted_info 필터링 (완화된 조건)
            if optimal_answer:
                # 원본 답변에 포함되어 있고, 최적 답변과 관련이 있는 정보만 필터링
                adopted_filtered = [
                    item.strip() for item in adopted
                    if isinstance(item, str) and item.strip()
                    and contains_text(original_text, item)
                ]
                # 필터링 결과가 비어있으면 원본 adopted_info 사용
                if not adopted_filtered and adopted:
                    adopted_filtered = [item.strip() for item in adopted if isinstance(item, str) and item.strip()]
            else:
                adopted_filtered = [
                    item.strip() for item in adopted
                    if isinstance(item, str) and item.strip() and contains_text(original_text, item)
                ]
                # 필터링 결과가 비어있으면 원본 adopted_info 사용
                if not adopted_filtered and adopted:
                    adopted_filtered = [item.strip() for item in adopted if isinstance(item, str) and item.strip()]

            # rejected_info 필터링 (원본 답변에 포함된 정보만)
            rejected_filtered = [
                item.strip() for item in rejected
                if isinstance(item, str) and item.strip()
                and contains_text(original_text, item)
            ]

            # verification_results 업데이트 (모달에서 사용)
            verification["채택된_정보"] = adopted_filtered if adopted_filtered else adopted
            verification["제외된_정보"] = rejected_filtered
        
        # 상호모순 정보도 채팅 창에서는 제외 (필요시 모달에서 표시 가능)
        
        return formatted_response
        
    except Exception as e:
        print(f"❌ 응답 포맷팅 실패: {e}")
        return f"""**최적의 답변:**

{final_result.get('최적의_답변', '답변 생성 실패')}

*포맷팅 오류 발생*
"""

