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
from collections import defaultdict
from difflib import SequenceMatcher

# 로컬 imports
from ..utils.error_handlers import get_user_friendly_error_message
from ..utils.ai_utils import get_openai_completion_limit
from .verification_sources import get_best_verification_source


def detect_question_type_from_content(content):
    """질문 내용에서 실제 질문 유형 감지: code, image, document, creative, general"""
    
    content_lower = content.lower()
    
    # 코드 관련 키워드
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
    
    # 이미지 관련 질문 감지
    if any(keyword in content_lower for keyword in image_keywords):
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
    """질문 유형 자동 분류 및 검증 키워드 추출: 사실(Factual) vs 의견(Opinion)"""
    try:
        
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        classification_prompt = f"""
다음 질문을 분석하여 질문 유형을 분류하고, 사실적 질문인 경우 검증에 사용할 핵심 키워드를 추출하세요.

질문: "{question}"

분류 기준:
- 사실적 질문: 객관적 사실, 정확한 답이 존재 (예: 설립연도, 위치, 역사적 사실, 대통령 이름)
- 의견/추천 질문: 주관적 평가, 추천, 선호도 (예: 맛집 추천, 좋은 카페, 최고의 제품)
- 코드/프로그래밍 질문: 코드 작성, 프로그래밍 예제, 알고리즘 구현 요청

검증 키워드 추출 규칙 (사실적 질문인 경우만):
- 질문의 핵심 주제를 나타내는 명사 추출
- 설명 요청 표현("에 대해", "설명해줘", "알려줘" 등) 제외
- 조사("은", "는", "이", "가" 등) 제외
- 검색에 사용할 핵심 키워드만 추출 (최대 3개)

예시:
- "충북대에 대해 설명해줘" → keywords: ["충북대"]
- "대한민국 11대 대통령은 누구야?" → keywords: ["대한민국", "11대", "대통령"]
- "서울의 인구는?" → keywords: ["서울", "인구"]

JSON 형식으로만 응답:
{{
  "type": "factual" 또는 "opinion" 또는 "code",
  "confidence": 0.0-1.0,
  "reason": "분류 이유",
  "keywords": ["키워드1", "키워드2"] (사실적 질문인 경우만, 빈 배열 가능)
}}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 질문 유형 분류 및 키워드 추출 전문가입니다. JSON 형식으로만 응답하세요."},
                {"role": "user", "content": classification_prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        question_type = result.get('type', 'factual')
        keywords = result.get('keywords', [])
        
        print(f"📝 질문 유형: {question_type} (신뢰도: {result.get('confidence', 0):.2f})")
        print(f"   이유: {result.get('reason', '')}")
        if keywords:
            print(f"   추출된 검증 키워드: {keywords}")
        
        # 결과를 딕셔너리로 반환 (하위 호환성을 위해)
        return {
            'type': question_type,
            'keywords': keywords,
            'confidence': result.get('confidence', 0.9),
            'reason': result.get('reason', '')
        }
        
    except Exception as e:
        print(f"⚠️ 질문 분류 실패: {e}, 기본값 'factual' 사용")
        return {
            'type': 'factual',
            'keywords': [],
            'confidence': 0.5,
            'reason': '분류 실패로 인한 기본값'
        }


def get_premium_models_to_call(currently_used_models):
    """사용 중인 모델을 제외한 프리미엄 모델 목록 반환
    
    Args:
        currently_used_models: 현재 사용 중인 모델 리스트 (예: ['GPT-4o', 'Gemini-2.0-Flash-Lite'])
    
    Returns:
        추가로 호출할 프리미엄 모델 리스트
    """
    # 프리미엄 모델 정의 (최상위 모델들)
    premium_models = ['GPT-5', 'Gemini-2.5-Pro', 'Claude-3.7-Sonnet']
    
    # 모델명 정규화 (대소문자, 하이픈 등 통일)
    def normalize_model_name(name):
        return name.lower().replace('-', '').replace('.', '').replace('_', '')
    
    # 현재 사용 중인 모델 정규화
    used_normalized = {normalize_model_name(model) for model in currently_used_models}
    
    # 사용하지 않는 프리미엄 모델 필터링
    models_to_call = []
    for premium in premium_models:
        if normalize_model_name(premium) not in used_normalized:
            models_to_call.append(premium)
    
    print(f"🎯 추가 호출할 프리미엄 모델: {models_to_call}")
    return models_to_call


async def call_additional_premium_models(user_message, premium_models, session_id=None):
    """프리미엄 모델들을 비동기로 호출
    
    Args:
        user_message: 사용자 질문
        premium_models: 호출할 프리미엄 모델 리스트
        session_id: 세션 ID
    
    Returns:
        {모델명: 응답} 딕셔너리
    """
    
    # 엔드포인트 매핑
    all_llm_endpoints = {
        'GPT-5': 'http://localhost:8000/chat/gpt-5/',
        'GPT-5-Mini': 'http://localhost:8000/chat/gpt-5-mini/',
        'GPT-4.1': 'http://localhost:8000/chat/gpt-4.1/',
        'GPT-4.1-Mini': 'http://localhost:8000/chat/gpt-4.1-mini/',
        'GPT-4o': 'http://localhost:8000/chat/gpt-4o/',
        'GPT-4o-Mini': 'http://localhost:8000/chat/gpt-4o-mini/',
        'GPT-4-Turbo': 'http://localhost:8000/chat/gpt-4-turbo/',
        'GPT-3.5-Turbo': 'http://localhost:8000/chat/gpt-3.5-turbo/',
        'Gemini-2.5-Pro': 'http://localhost:8000/chat/gemini-2.5-pro/',
        'Gemini-2.5-Flash': 'http://localhost:8000/chat/gemini-2.5-flash/',
        'Gemini-2.0-Flash-Exp': 'http://localhost:8000/chat/gemini-2.0-flash-exp/',
        'Gemini-2.0-Flash-Lite': 'http://localhost:8000/chat/gemini-2.0-flash-lite/',
        'Claude-4-Opus': 'http://localhost:8000/chat/claude-4-opus/',
        'Claude-3.7-Sonnet': 'http://localhost:8000/chat/claude-3.7-sonnet/',
        'Claude-3.5-Sonnet': 'http://localhost:8000/chat/claude-3.5-sonnet/',
        'Claude-3.5-Haiku': 'http://localhost:8000/chat/claude-3.5-haiku/',
        'Claude-3-Opus': 'http://localhost:8000/chat/claude-3-opus/',
        'HCX-003': 'http://localhost:8000/chat/clova-hcx-003/',
        'HCX-DASH-001': 'http://localhost:8000/chat/clova-hcx-dash-001/',
    }
    
    responses = {}
    
    async def fetch_response(session, ai_name, endpoint):
        try:
            payload = {'message': user_message, 'user_id': session_id or 'system'}
            async with session.post(endpoint, json=payload, timeout=60) as response:
                if response.status == 200:
                    result = await response.json()
                    response_content = result.get('response', '응답 없음')
                    print(f"✅ [추가] {ai_name} 응답 수신: {len(str(response_content))}자")
                    return ai_name, response_content
                else:
                    error_text = await response.text()
                    friendly_msg = get_user_friendly_error_message(Exception(f"HTTP {response.status}"))
                    return ai_name, friendly_msg
        except Exception as e:
            friendly_msg = get_user_friendly_error_message(e)
            return ai_name, friendly_msg
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for model in premium_models:
            if model in all_llm_endpoints:
                endpoint = all_llm_endpoints[model]
                tasks.append(fetch_response(session, model, endpoint))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, tuple):
                ai_name, response = result
                responses[ai_name] = response
    
    # 에러 메시지 필터링
    error_patterns = [
        "네트워크 연결에 문제가", "요청 시간이 초과", "서버에 일시적인 문제",
        "API 인증에 실패", "사용량 한도를 초과", "연결할 수 없습니다"
    ]
    
    valid_responses = {}
    for ai_name, response in responses.items():
        response_str = str(response)
        is_error = any(pattern in response_str for pattern in error_patterns)
        if len(response_str) < 50 and any(kw in response_str.lower() for kw in ["timeout", "error", "오류"]):
            is_error = True
        
        if not is_error:
            valid_responses[ai_name] = response
    
    print(f"📊 [추가] 유효한 프리미엄 모델 응답: {len(valid_responses)}개")
    return valid_responses


def apply_voting_system(all_responses, user_question):
    """보팅 시스템 적용: 가장 많은 모델이 동의하는 답변 선택
    
    Args:
        all_responses: {모델명: 응답} 딕셔너리
        user_question: 사용자 질문
    
    Returns:
        최적 답변 결과
    """
    print(f"\n🗳️ 보팅 시스템 적용 시작")
    print(f"   참여 모델: {list(all_responses.keys())}")
    
    # 1. 각 응답의 핵심 내용 추출
    response_summaries = {}
    for model, response in all_responses.items():
        # 첫 문장이나 핵심 문장 추출 (간단한 요약)
        sentences = extract_sentences_from_response(response)
        summary = sentences[0] if sentences else response[:200]
        response_summaries[model] = normalize_text(summary)
    
    # 2. 응답 간 유사도 계산 및 그룹화
    from collections import defaultdict
    similarity_groups = defaultdict(list)
    processed = set()
    
    models = list(all_responses.keys())
    for i, model1 in enumerate(models):
        if model1 in processed:
            continue
        
        group = [model1]
        summary1 = response_summaries[model1]
        
        for model2 in models[i+1:]:
            if model2 in processed:
                continue
            
            summary2 = response_summaries[model2]
            similarity = similarity_ratio(summary1, summary2)
            
            # 유사도 60% 이상이면 같은 그룹으로 간주
            if similarity >= 0.6:
                group.append(model2)
                processed.add(model2)
        
        processed.add(model1)
        similarity_groups[model1] = group
    
    # 3. 가장 많은 모델이 동의하는 그룹 찾기
    largest_group = max(similarity_groups.values(), key=len)
    representative_model = largest_group[0]
    
    print(f"\n📊 보팅 결과:")
    for leader, members in similarity_groups.items():
        if len(members) > 1:
            print(f"   그룹 ({len(members)}개 모델): {members}")
    
    print(f"\n🏆 최다 득표 그룹: {largest_group} ({len(largest_group)}표)")
    
    # 4. 결과 생성
    optimal_answer = all_responses[representative_model]
    
    result = {
        "최적의_답변": optimal_answer,
        "llm_검증_결과": {},
        "심판모델": "Voting System",
        "상태": "보팅 완료",
        "신뢰도": str(int((len(largest_group) / len(all_responses)) * 100)),
        "보팅_결과": {
            "총_모델_수": len(all_responses),
            "최다_득표": len(largest_group),
            "득표_모델": largest_group,
            "그룹_정보": {k: v for k, v in similarity_groups.items()}
        },
        "원본_응답": all_responses
    }
    
    # 각 모델의 검증 결과 생성
    for model in all_responses.keys():
        sentences = extract_sentences_from_response(all_responses[model])
        is_winner = model in largest_group
        
        result["llm_검증_결과"][model] = {
            "정확성": "✅ 다수결 채택" if is_winner else "❌ 소수 의견",
            "오류": "없음" if is_winner else "다수 의견과 불일치",
            "신뢰도": str(int((len(largest_group) / len(all_responses)) * 100)) if is_winner else "30",
            "채택된_정보": sentences[:3] if is_winner else [],
            "제외된_정보": [] if is_winner else sentences[:2]
        }
    
    return result


def collect_multi_llm_responses(user_message, judge_model="GPT-4o", selected_models=None, question_type=None, session_id=None, clear_history=False):
    """1단계: 선택된 LLM들에게 병렬 질의 후 심판 모델로 검증
    
    Args:
        user_message: 사용자 메시지
        judge_model: 심판 모델 이름
        selected_models: 선택된 모델 목록
        question_type: 질문 유형
        session_id: 세션 ID (히스토리 관리용)
        clear_history: 히스토리 초기화 여부
    """
    import time
    
    responses = {}
    
    # 히스토리 초기화가 필요한 경우 각 모델의 히스토리 초기화
    if clear_history and selected_models:
        from ..utils.chatbot import chatbots
        model_name_mapping = {
            'GPT-5': 'gpt-5', 'GPT-5-Mini': 'gpt-5-mini',
            'GPT-4.1': 'gpt-4.1', 'GPT-4.1-Mini': 'gpt-4.1-mini',
            'GPT-4o': 'gpt-4o', 'GPT-4o-Mini': 'gpt-4o-mini',
            'GPT-4-Turbo': 'gpt-4-turbo', 'GPT-3.5-Turbo': 'gpt-3.5-turbo',
            'Gemini-2.5-Pro': 'gemini-2.5-pro', 'Gemini-2.5-Flash': 'gemini-2.5-flash',
            'Gemini-2.0-Flash-Exp': 'gemini-2.0-flash-exp', 'Gemini-2.0-Flash-Lite': 'gemini-2.0-flash-lite',
            'Claude-4-Opus': 'claude-4-opus', 'Claude-3.7-Sonnet': 'claude-3.7-sonnet',
            'Claude-3.5-Sonnet': 'claude-3.5-sonnet', 'Claude-3.5-Haiku': 'claude-3.5-haiku',
            'Claude-3-Opus': 'claude-3-opus',
            'HCX-003': 'clova-hcx-003', 'HCX-DASH-001': 'clova-hcx-dash-001',
        }
        for model_display_name in selected_models:
            bot_name = model_name_mapping.get(model_display_name)
            if bot_name and bot_name in chatbots:
                chatbots[bot_name].conversation_history = []
                print(f"   🔄 {model_display_name} ({bot_name}) 히스토리 초기화 (collect_multi_llm_responses)")
    
    # 사용 가능한 LLM 엔드포인트들
    all_llm_endpoints = {
        'GPT-5': 'http://localhost:8000/chat/gpt-5/',
        'GPT-5-Mini': 'http://localhost:8000/chat/gpt-5-mini/',
        'GPT-4.1': 'http://localhost:8000/chat/gpt-4.1/',
        'GPT-4.1-Mini': 'http://localhost:8000/chat/gpt-4.1-mini/',
        'GPT-4o': 'http://localhost:8000/chat/gpt-4o/',
        'GPT-4o-Mini': 'http://localhost:8000/chat/gpt-4o-mini/',
        'GPT-4-Turbo': 'http://localhost:8000/chat/gpt-4-turbo/',
        'GPT-3.5-Turbo': 'http://localhost:8000/chat/gpt-3.5-turbo/',
        'Gemini-2.5-Pro': 'http://localhost:8000/chat/gemini-2.5-pro/',
        'Gemini-2.5-Flash': 'http://localhost:8000/chat/gemini-2.5-flash/',
        'Gemini-2.0-Flash-Exp': 'http://localhost:8000/chat/gemini-2.0-flash-exp/',
        'Gemini-2.0-Flash-Lite': 'http://localhost:8000/chat/gemini-2.0-flash-lite/',
        'Claude-4-Opus': 'http://localhost:8000/chat/claude-4-opus/',
        'Claude-3.7-Sonnet': 'http://localhost:8000/chat/claude-3.7-sonnet/',
        'Claude-3.5-Sonnet': 'http://localhost:8000/chat/claude-3.5-sonnet/',
        'Claude-3.5-Haiku': 'http://localhost:8000/chat/claude-3.5-haiku/',
        'Claude-3-Opus': 'http://localhost:8000/chat/claude-3-opus/',
        'HCX-003': 'http://localhost:8000/chat/clova-hcx-003/',
        'HCX-DASH-001': 'http://localhost:8000/chat/clova-hcx-dash-001/',
    }
    
    # 모델 선택 로직
    if selected_models:
        print(f"📋 selected_models 입력: {selected_models}")
        model_mapping = {
            'gpt-5': 'GPT-5', 'gpt-5-mini': 'GPT-5-Mini',
            'gpt-4.1': 'GPT-4.1', 'gpt-4.1-mini': 'GPT-4.1-Mini',
            'gpt-4o': 'GPT-4o', 'gpt-4o-mini': 'GPT-4o-Mini',
            'gpt-4-turbo': 'GPT-4-Turbo', 'gpt-3.5-turbo': 'GPT-3.5-Turbo',
            'gemini-2.5-pro': 'Gemini-2.5-Pro', 'gemini-2.5-flash': 'Gemini-2.5-Flash',
            'gemini-2.0-flash-exp': 'Gemini-2.0-Flash-Exp', 'gemini-2.0-flash-lite': 'Gemini-2.0-Flash-Lite',
            'claude-4-opus': 'Claude-4-Opus', 'claude-3.7-sonnet': 'Claude-3.7-Sonnet',
            'claude-3.5-sonnet': 'Claude-3.5-Sonnet', 'claude-3.5-haiku': 'Claude-3.5-Haiku',
            'claude-3-opus': 'Claude-3-Opus',
            'clova-hcx-003': 'HCX-003', 'clova-hcx-dash-001': 'HCX-DASH-001',
        }
        
        selected_standard_models = []
        for model in selected_models:
            model_lower = model.lower() if isinstance(model, str) else str(model).lower()
            if model_lower in model_mapping:
                selected_standard_models.append(model_mapping[model_lower])
        
        llm_endpoints = {k: v for k, v in all_llm_endpoints.items() if k in selected_standard_models}
    else:
        print(f"⚠️ selected_models가 없습니다. 기본 모델 3개 사용")
        default_models = ['GPT-4o-Mini', 'Gemini-2.0-Flash-Lite', 'Claude-3.5-Haiku']
        llm_endpoints = {k: v for k, v in all_llm_endpoints.items() if k in default_models}
    
    if not llm_endpoints:
        raise ValueError("사용 가능한 LLM 모델이 없습니다.")
    
    print(f"🎯 선택된 LLM 모델들: {list(llm_endpoints.keys())}")
    
    async def fetch_response(session, ai_name, endpoint):
        try:
            payload = {'message': user_message, 'user_id': session_id or 'system'}
            async with session.post(endpoint, json=payload, timeout=60) as response:
                if response.status == 200:
                    result = await response.json()
                    response_content = result.get('response', '응답 없음')
                    print(f"✅ {ai_name} 응답 수신: {len(str(response_content))}자")
                    return ai_name, response_content
                else:
                    error_text = await response.text()
                    friendly_msg = get_user_friendly_error_message(Exception(f"HTTP {response.status}"))
                    return ai_name, friendly_msg
        except Exception as e:
            friendly_msg = get_user_friendly_error_message(e)
            return ai_name, friendly_msg
    
    async def collect_all_responses():
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_response(session, ai_name, endpoint) for ai_name, endpoint in llm_endpoints.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, tuple):
                    ai_name, response = result
                    responses[ai_name] = response
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(collect_all_responses())
        loop.close()
        
        print(f"✅ {len(responses)}개 LLM 응답 수집 완료")
        
        # 에러 메시지 필터링
        error_patterns = [
            "네트워크 연결에 문제가", "요청 시간이 초과", "서버에 일시적인 문제",
            "API 인증에 실패", "사용량 한도를 초과", "연결할 수 없습니다"
        ]
        
        valid_responses = {}
        for ai_name, response in responses.items():
            response_str = str(response)
            is_error = any(pattern in response_str for pattern in error_patterns)
            if len(response_str) < 50 and any(kw in response_str.lower() for kw in ["timeout", "error", "오류"]):
                is_error = True
            
            if not is_error:
                valid_responses[ai_name] = response
        
        if not valid_responses:
            raise ValueError("모든 LLM 요청이 실패했습니다.")
        
        print(f"📊 유효한 응답: {len(valid_responses)}개")
        final_result = judge_and_generate_optimal_response(valid_responses, user_message, judge_model, question_type, session_id)
        return final_result
        
    except Exception as e:
        print(f"❌ LLM 응답 수집 실패: {e}")
        raise


def detect_conflicts_in_responses(llm_responses):
    """LLM 응답에서 상호모순 감지 (정확도 향상 버전)"""
    
    CONTEXT_STOPWORDS = {
        '그리고', '또한', '그러나', '하지만', '그런데', '그래서', '따라서', '즉', '이후', '최근',
        '대한', '관련', '기준', '대해', '있는', '없는', '하는', '되는', '것은', '것이', '것을',
        '것에', '것으로', '것이다', '것입니다', '입니다', '습니다', '있습니다', '됩니다', '합니다',
        '에서', '에게', '으로', '로', '및', '등', '때', '때문', '위해', '여러', '다양한',
        '이', '그', '저', '또는', '혹은', '우리', '해당', '이번', '해', '년', '월', '일'
    }
    
    def extract_context_tokens(text, start, end):
        window = text[max(0, start - 25):min(len(text), end + 25)]
        tokens = re.findall(r'[A-Za-z가-힣]{2,}', window)
        keywords = set()
        for token in tokens:
            token_norm = token.lower()
            if token_norm in CONTEXT_STOPWORDS:
                continue
            keywords.add(token_norm)
        return keywords
    
    def normalize_numeric_tokens(value):
        numbers = re.findall(r'\d+(?:\.\d+)?', value)
        normalized = []
        for num in numbers:
            if '.' in num:
                normalized.append(float(num))
            else:
                normalized.append(int(num))
        return normalized
    
    def values_conflict(category, value_a, info_a, value_b, info_b):
        a_norm = value_a.strip().lower()
        b_norm = value_b.strip().lower()
        
        if not a_norm or not b_norm:
            return False
        if a_norm == b_norm:
            return False
        if a_norm in b_norm or b_norm in a_norm:
            return False
        
        shared_keywords = info_a["keywords"] & info_b["keywords"]
        if not shared_keywords:
            return False
        
        if category in {"dates", "numbers"}:
            nums_a = normalize_numeric_tokens(a_norm)
            nums_b = normalize_numeric_tokens(b_norm)
            if nums_a and nums_b:
                return nums_a != nums_b
            return False
        
        if category == "names":
            similarity = similarity_ratio(a_norm, b_norm)
            return similarity < 0.6
        
        return False
    
    conflicts = {
        "dates": defaultdict(lambda: {"models": set(), "keywords": set()}),
        "numbers": defaultdict(lambda: {"models": set(), "keywords": set()}),
        "names": defaultdict(lambda: {"models": set(), "keywords": set()})
    }
    
    for model_name, response in llm_responses.items():
        for match in re.finditer(r'(\d{4})(?:년)?', response):
            year_str = match.group(1)
            try:
                year = int(year_str)
                if 1000 <= year <= 2100:
                    entry = conflicts["dates"][year_str]
                    entry["models"].add(model_name)
                    entry["keywords"].update(extract_context_tokens(response, match.start(), match.end()))
            except ValueError:
                continue
        
        for match in re.finditer(r'\d+(?:\.\d+)?(?:명|개|월|일|억|만|천|대|년|세|%|cm|mm|kg|g)?', response):
            value = match.group(0)
            entry = conflicts["numbers"][value]
            entry["models"].add(model_name)
            entry["keywords"].update(extract_context_tokens(response, match.start(), match.end()))
        
        for match in re.finditer(r'[가-힣]{2,4}(?:\([^)]+\))?', response):
            name = match.group(0)
            name_clean = name.split('(')[0].strip()
            if len(name_clean) < 2:
                continue
            entry = conflicts["names"][name_clean]
            entry["models"].add(model_name)
            entry["keywords"].update(extract_context_tokens(response, match.start(), match.end()))
    
    detected_conflicts = {}
    for category, items in conflicts.items():
        value_infos = []
        for value, info in items.items():
            if len(info["models"]) >= 2:
                value_infos.append((value, info))
        
        if len(value_infos) <= 1:
            continue
        
        conflicting_values = {}
        for i in range(len(value_infos)):
            value_i, info_i = value_infos[i]
            models_i = info_i["models"]
            for j in range(i + 1, len(value_infos)):
                value_j, info_j = value_infos[j]
                models_j = info_j["models"]
                
                if not models_i.isdisjoint(models_j):
                    continue
                
                if values_conflict(category, value_i, info_i, value_j, info_j):
                    conflicting_values.setdefault(value_i, models_i)
                    conflicting_values.setdefault(value_j, models_j)
        
        if conflicting_values:
            detected_conflicts[category] = {
                value: list(models) for value, models in conflicting_values.items()
            }
    
    return detected_conflicts


def extract_sentences_from_response(response_text):
    """응답 텍스트에서 문장 단위로 추출"""
    
    sentences = []
    
    # 1. 코드 블록 추출
    code_blocks = re.findall(r'```[\s\S]*?```', response_text)
    for code_block in code_blocks:
        sentences.append(code_block.strip())
    
    # 2. 코드 제외 후 문장 분리
    text_without_code = re.sub(r'```[\s\S]*?```', '', response_text)
    text_sentences = re.split(r'[.!?]\s+', text_without_code)
    
    for sentence in text_sentences:
        sentence = sentence.strip()
        if len(sentence) > 10:
            sentences.append(sentence)
    
    return sentences


def normalize_text(text):
    """텍스트 정규화"""
    if not text:
        return ""
    # 공백 통일
    text = re.sub(r'\s+', ' ', text)
    # 따옴표 통일
    text = text.replace('"', '"').replace('"', '"').replace("'", "'").replace("'", "'")
    # Wikipedia 메타 정보 제거
    text = re.sub(r'\s*\([^)]*Wikipedia[^)]*\)', '', text)
    text = re.sub(r'\s*\([^)]*불일치[^)]*\)', '', text)
    return text.strip().lower()


def similarity_ratio(a, b):
    """두 문자열의 유사도 계산"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def is_sentence_in_response(sentence, original_response, threshold=0.85):
    """문장이 원본 응답에 실제로 포함되어 있는지 엄격하게 검증"""
    if not sentence or not original_response:
        return False
    
    sentence_norm = normalize_text(sentence)
    response_norm = normalize_text(original_response)
    
    # 너무 짧은 문장 필터링
    if len(sentence_norm) < 5:
        return False
    
    # 1차: 정확한 부분 문자열 매칭
    if sentence_norm in response_norm:
        return True
    
    # 2차: 단어 단위 매칭
    sentence_words = sentence_norm.split()
    response_words = response_norm.split()
    
    # 짧은 문장은 정확한 매칭 요구
    if len(sentence_words) < 5:
        return sentence_norm in response_norm
    
    # 긴 문장은 유사도 기반
    best_ratio = 0.0
    window_size = len(sentence_words)
    
    for i in range(len(response_words) - window_size + 1):
        window = ' '.join(response_words[i:i + window_size])
        ratio = similarity_ratio(sentence_norm, window)
        best_ratio = max(best_ratio, ratio)
    
    if best_ratio >= threshold:
        return True
    
    # 3차: 핵심 키워드 매칭
    stopwords = {'은', '는', '이', '가', '을', '를', '의', '에', '와', '과', '도', '로', '으로',
                 '입니다', '습니다', '있습니다', '됩니다', '합니다'}
    key_words = [w for w in sentence_words if len(w) > 1 and w not in stopwords]
    
    if not key_words:
        return False
    
    match_count = sum(1 for word in key_words if word in response_norm)
    match_ratio = match_count / len(key_words)
    
    return match_ratio >= 0.8


def _build_judge_prompt(user_question, llm_responses, llm_sentences, wikipedia_info):
    """Judge 모델용 프롬프트 생성"""
    model_sections = [f"[{name} 원본]\n{(r[:800] + '...' if len(r) > 800 else r)}" 
                     for name, r in llm_responses.items()]
    sentences_sections = [f"[{name} 문장 목록 - 이 문장만 사용 가능]\n" + 
                         "\n".join([f"  {i+1}. {s}" for i, s in enumerate(sentences)])
                         for name, sentences in llm_sentences.items()]
    wikipedia_section = ""
    if wikipedia_info:
        source_name = wikipedia_info.get('source', '검증 소스')
        wikipedia_section = f"""

**🌐 {source_name} 검증 결과 (공식 정보):**
제목: {wikipedia_info['title']}
내용: {wikipedia_info['extract'][:500]}

**🚨 {source_name} 검증 기준:**
- {source_name} 정보와 **일치하는 AI 답변만 채택**
- {source_name} 정보와 **불일치하는 AI 답변은 제외**
- 각 AI의 채택/제외 판단 시 {source_name}을 기준으로 판단하세요


"""
    sentences_text = "\n\n".join(sentences_sections)
    model_responses_text = "\n\n".join(model_sections)
    wiki_used = True if wikipedia_info else False
    
    return f"""질문: {user_question}

**🚨 핵심 규칙 (반드시 준수):**
1. **아래 "문장 목록"에 있는 문장만 사용** - 새로운 문장 생성 절대 금지
2. **각 AI의 문장은 해당 AI의 목록에서만 선택** - 다른 AI 문장 가져오기 금지
3. **채택/제외 정보는 해당 AI의 원본 문장을 그대로 복사**
4. **검증 소스 정보가 있으면 해당 소스를 기준으로 채택/제외 판단**

{sentences_text}
{wikipedia_section}

**원본 답변 (참고용):**
{model_responses_text}

**verification_results 작성 규칙:**

각 AI마다:
```json
"AI모델명": {{
  "accuracy": "정확성 (검증 소스와 일치하면 '정확', 불일치하면 '부정확')",
  "errors": "오류 설명 (검증 소스 불일치 시 명시)",
  "confidence": "0-100",
  "adopted_info": ["해당 AI 문장 목록에서 검증 소스와 일치하는 원문"],
  "rejected_info": ["해당 AI 문장 목록에서 검증 소스와 불일치하는 원문"]
}}
```

**🚨 절대 규칙:**
1. **해당 AI의 문장 목록에 있는 문장만 복사** - 한 글자도 바꾸지 마세요
2. **다른 AI의 문장 절대 복사 금지**
3. **새로운 문장 생성 금지**
4. **검증 소스 정보가 있으면 반드시 해당 소스 기준으로 판단**

**optimal_answer:**
- **반드시 최적의 답변을 생성해야 합니다!**
- 검증 소스 정보가 있으면 검증 소스 내용을 기반으로 답변 생성
- 검증 소스 정보와 일치하는 AI 문장들을 조합하여 답변 생성
- 검증 소스 정보가 없으면 여러 AI 공통 정보 우선
- **절대 "없습니다", "없음" 같은 빈 답변을 반환하지 마세요!**
- **최소 100자 이상의 의미 있는 답변을 생성하세요!**

JSON 형식으로만 응답:
{{
  "optimal_answer": "검증 소스 기준으로 검증된 문장 조합",
  "verification_results": {{"모든 AI 검증 결과"}},
  "confidence_score": "0-100",
  "contradictions_detected": [],
  "fact_verification": {{"wikipedia_used": {wiki_used}}},
  "analysis_rationale": "검증 소스 검증 결과 및 선택 근거"
}}"""


def extract_valid_sentences(sentence_list, original_response, ai_name):
    """문장 리스트에서 실제로 원본에 포함된 것만 추출"""
    if not sentence_list or not original_response:
        return []
    
    valid_sentences = []
    invalid_count = 0
    
    for item in sentence_list:
        if not isinstance(item, str) or not item.strip():
            continue
        
        item_cleaned = normalize_text(item)
        if len(item_cleaned) < 5:
            continue
        
        if is_sentence_in_response(item, original_response):
            valid_sentences.append(item.strip())
        else:
            invalid_count += 1
            print(f"❌ {ai_name} 환각 감지 및 제거: '{item[:60]}...'")
    
    if invalid_count > 0:
        print(f"⚠️ {ai_name}: {invalid_count}개 환각 문장 제거됨")
    
    return valid_sentences


def judge_and_generate_optimal_response(llm_responses, user_question, judge_model="GPT-5", question_type=None, session_id=None):
    """하이브리드 검증 시스템 (Wikipedia 검증 + 프리미엄 모델 보팅)"""
    try:
        print(f"\n🔍 하이브리드 검증 시작: {user_question}")
        
        # 질문 유형 분류 및 검증 키워드 추출
        verification_keywords = []
        if question_type is None:
            classification_result = classify_question_type(user_question)
            if isinstance(classification_result, dict):
                question_type = classification_result.get('type', 'factual')
                verification_keywords = classification_result.get('keywords', [])
            else:
                # 하위 호환성: 문자열로 반환된 경우
                question_type = classification_result
                verification_keywords = []
        else:
            print(f"📝 전달받은 질문 유형: {question_type}")
            # 전달받은 question_type이 문자열인 경우, 키워드 추출을 위해 재분류
            if isinstance(question_type, str) and question_type not in ['image', 'document', 'code', 'creative']:
                classification_result = classify_question_type(user_question)
                if isinstance(classification_result, dict):
                    verification_keywords = classification_result.get('keywords', [])
        
        # question_type이 "general"이거나 None이면 다시 분류
        if question_type in [None, "general"]:
            print(f"🔄 질문 유형 재분류 중...")
            classification_result = classify_question_type(user_question)
            if isinstance(classification_result, dict):
                question_type = classification_result.get('type', 'factual')
                verification_keywords = classification_result.get('keywords', [])
            else:
                question_type = classification_result
                verification_keywords = []
            print(f"📝 재분류 결과: {question_type}")
        
        # 문장 단위 분할
        print(f"\n📝 각 AI 응답을 문장 단위로 분할...")
        llm_sentences = {}
        for model_name, response in llm_responses.items():
            sentences = extract_sentences_from_response(response)
            llm_sentences[model_name] = sentences
            print(f"  - {model_name}: {len(sentences)}개 문장")
        
        # 상호모순 감지
        conflicts = detect_conflicts_in_responses(llm_responses)
        print(f"\n📊 상호모순 감지: {len(conflicts)}개 카테고리")
        for category, items in conflicts.items():
            print(f"  - {category}: {items}")
        
        # 🚨 검증 소스 검색 (사실 질문일 때 항상 검색)
        wikipedia_info = None
        use_voting = False
        
        if question_type == "factual":
            if len(conflicts) > 0:
                print(f"\n🌐 상호모순 감지됨! 다중 검증 소스 검색 시작...")
            else:
                print(f"\n🌐 사실 질문 감지! 다중 검증 소스 검색 시작...")
            
            # 검증 키워드 사용 (LLM이 추출한 키워드 우선, 없으면 원본 질문 사용)
            if verification_keywords:
                search_query = ' '.join(verification_keywords)
                print(f"🔍 LLM 추출 검증 키워드 사용: {verification_keywords} -> '{search_query}'")
            else:
                search_query = user_question
                print(f"🔍 원본 질문 사용: '{search_query}'")
            
            # Wikipedia, Wikidata, DBpedia, DuckDuckGo 중 가장 좋은 하나 선택
            wikipedia_info = get_best_verification_source(search_query)
            
            if wikipedia_info:
                print(f"✅ 검증 완료: {wikipedia_info.get('source', 'Unknown')} - {wikipedia_info.get('title', 'No title')}")
                print(f"   신뢰도: {wikipedia_info.get('confidence', 0):.2f}")
                # 상호모순이 없어도 검증 소스가 있으면 사용
            else:
                print(f"⚠️ 모든 검증 소스 실패 - 검증 소스 검색 결과가 None입니다")
                # 상호모순이 있을 때만 보팅 시스템 사용
                if len(conflicts) > 0:
                    print(f"   상호모순이 있으므로 프리미엄 모델 보팅 시스템 활성화")
                    use_voting = True
        else:
            print(f"ℹ️ 질문 유형이 'factual'이 아니므로 검증 소스 검색을 건너뜁니다. (현재 유형: {question_type})")
        
        # 🗳️ Wikipedia가 없으면 프리미엄 모델 추가 호출 및 보팅
        if use_voting:
            print(f"\n🎯 프리미엄 모델 추가 호출 시작...")
            
            # 현재 사용 중인 모델 목록
            currently_used = list(llm_responses.keys())
            print(f"   현재 사용 중인 모델: {currently_used}")
            
            # 추가 호출할 프리미엄 모델 결정
            premium_models_to_call = get_premium_models_to_call(currently_used)
            
            if premium_models_to_call:
                print(f"   추가 호출할 모델: {premium_models_to_call}")
                
                # 프리미엄 모델 비동기 호출
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                premium_responses = loop.run_until_complete(
                    call_additional_premium_models(user_question, premium_models_to_call, session_id)
                )
                loop.close()
                
                if premium_responses:
                    print(f"✅ {len(premium_responses)}개 프리미엄 모델 응답 수신")
                    
                    # 기존 응답과 프리미엄 응답 합치기
                    all_responses = {**llm_responses, **premium_responses}
                    
                    # 보팅 시스템 적용
                    voting_result = apply_voting_system(all_responses, user_question)
                    
                    extra_models_used = list(premium_responses.keys())
                    voting_result["추가_모델_호출"] = {
                        "사유": "상충 응답 및 검증 소스 부재",
                        "추가_모델": extra_models_used,
                        "총_호출": len(extra_models_used),
                        "기존_모델": list(llm_responses.keys()),
                        "전체_모델": list(all_responses.keys())
                    }
                    
                    if not voting_result.get("분석_근거"):
                        voting_summary_models = voting_result.get("보팅_결과", {}).get("득표_모델", [])
                        total_models = list(dict.fromkeys(all_responses.keys()))
                        if voting_summary_models:
                            summary_leads = ', '.join(voting_summary_models[:2])
                            if len(voting_summary_models) > 2:
                                summary_leads += " 등"
                        else:
                            summary_leads = ', '.join(total_models[:2]) if total_models else "추가 모델"
                        reason_text = (
                            f"AI 응답 간 상충이 감지되어 추가적으로 {len(extra_models_used)}개의 프리미엄 모델"
                            f"({', '.join(extra_models_used)})을 호출했습니다. "
                            f"결과적으로 {summary_leads} {len(total_models)}개 모델의 합의 내용을 채택했습니다."
                        )
                        voting_result["분석_근거"] = reason_text
                    
                    print(f"\n🏆 보팅 완료: {voting_result['보팅_결과']['득표_모델']}")
                    
                    return voting_result
                else:
                    print(f"⚠️ 프리미엄 모델 응답 실패 - 기본 Judge 시스템 사용")
            else:
                print(f"⚠️ 추가 호출할 프리미엄 모델 없음 - 기본 Judge 시스템 사용")
        
        # Wikipedia 검증이 있거나 보팅이 불필요한 경우 기존 Judge 시스템 사용
        judge_prompt = _build_judge_prompt(user_question, llm_responses, llm_sentences, wikipedia_info)
        
        print(f"\n📞 심판 모델({judge_model}) 호출...")
        judge_response = call_judge_model(judge_model, judge_prompt)
        
        print(f"\n📝 응답 파싱 및 환각 검증...")
        parsed_result = parse_judge_response(judge_response, judge_model, llm_responses, llm_sentences, wikipedia_info)
        
        return parsed_result
        
    except Exception as e:
        print(f"❌ 검증 실패: {e}")
        import traceback
        traceback.print_exc()
        
        if llm_responses:
            longest_response = max(llm_responses.values(), key=len)
            result = {
                "최적의_답변": longest_response,
                "llm_검증_결과": {
                    model: {
                        "정확성": "❌",
                        "오류": "검증 실패",
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
            # 검증 소스 정보 추가 (wikipedia_info가 있는 경우)
            # wikipedia_info는 함수 시작 부분에서 None으로 초기화되므로 항상 접근 가능
            if wikipedia_info:
                result["검증_소스"] = {
                    "사용됨": True,
                    "소스": wikipedia_info.get("source", "Unknown"),
                    "제목": wikipedia_info.get("title", ""),
                    "내용": wikipedia_info.get("extract", "")[:200],
                    "신뢰도": wikipedia_info.get("confidence", 0)
                }
            else:
                result["검증_소스"] = {
                    "사용됨": False,
                    "소스": None,
                    "제목": None,
                    "내용": None,
                    "신뢰도": 0
                }
            return result


def call_judge_model(model_name, prompt):
    """심판 모델 호출"""
    try:
        if model_name in ['GPT-5', 'GPT-4', 'GPT-4o', 'GPT-4o-mini', 'GPT-3.5-turbo']:
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                raise ValueError("OpenAI API 키 미설정")
            
            client = openai.OpenAI(api_key=openai_api_key)
            
            # 모델명 변환
            model_map = {
                'GPT-5': 'gpt-5',
                'GPT-4': 'gpt-4',
                'GPT-4o': 'gpt-4o',
                'GPT-4o-mini': 'gpt-4o-mini',
                'GPT-3.5-turbo': 'gpt-3.5-turbo'
            }
            openai_model = model_map.get(model_name, 'gpt-4o')
            
            is_latest = 'gpt-5' in openai_model or 'o1' in openai_model or 'o3' in openai_model
            
            api_params = {
                "model": openai_model,
                "messages": [
                    {"role": "system", "content": """당신은 텍스트 분석 전문가입니다.

🚨 절대 규칙:
1. **각 AI가 실제로 말한 문장만** adopted_info/rejected_info에 복사
2. **절대 새로운 문장 생성 금지** - 환각(hallucination) 금지!
3. **각 AI 문장은 해당 AI 원본에 있어야 함**
4. **다른 AI 문장 복사 금지**
5. **검증 소스 정보가 있으면 해당 소스 기준으로 채택/제외 판단**

✅ 올바른 분석:
- 각 AI 원본에서 문장 그대로 복사
- 검증 소스와 일치하는 정보 채택
- 검증 소스와 불일치하는 정보 제외

❌ 환각:
- 원본에 없는 새 문장 생성
- 다른 AI 문장을 해당 AI 채택/제외에 포함
- AI가 말하지 않은 내용 만들어내기

JSON 형식으로만 응답."""},
                    {"role": "user", "content": prompt}
                ]
            }
            
            if not is_latest:
                api_params["temperature"] = 0.0
            
            completion_limit = get_openai_completion_limit(openai_model)
            if is_latest:
                api_params["max_completion_tokens"] = completion_limit
            else:
                api_params["max_tokens"] = completion_limit
                api_params["response_format"] = {"type": "json_object"}
            
            response = client.chat.completions.create(**api_params)
            return response.choices[0].message.content.strip()
        else:
            return call_judge_model('GPT-4o', prompt)
            
    except Exception as e:
        print(f"❌ 심판 모델 호출 실패: {e}")
        raise


def parse_judge_response(judge_response, judge_model, llm_responses=None, llm_sentences=None, wikipedia_info=None):
    """심판 모델 JSON 응답 파싱 및 엄격한 환각 검증"""
    try:
        
        # JSON 추출
        json_match = re.search(r'\{.*\}', judge_response, re.DOTALL)
        if not json_match:
            return create_fallback_result(judge_model, llm_responses, wikipedia_info)
        
        json_str = json_match.group()
        try:
            parsed_data = json.loads(json_str)
            print(f"✅ JSON 파싱 성공")
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 실패: {e}")
            return create_fallback_result(judge_model, llm_responses, wikipedia_info)
        
        optimal_answer = parsed_data.get("optimal_answer", "").strip()
        
        # optimal_answer가 비어있거나 의미 없는 경우, Wikipedia 정보나 AI 응답으로 대체
        if not optimal_answer or len(optimal_answer) < 10 or "없습니다" in optimal_answer or "없음" in optimal_answer:
            print(f"⚠️ Judge가 제공한 optimal_answer가 비어있거나 부적절함: '{optimal_answer}'")
            
            # Wikipedia 정보가 있으면 Wikipedia 내용 기반으로 답변 생성
            if wikipedia_info:
                wiki_title = wikipedia_info.get('title', '')
                wiki_extract = wikipedia_info.get('extract', '')
                if wiki_extract:
                    # Wikipedia 내용의 첫 부분을 최적 답변으로 사용
                    optimal_answer = f"{wiki_title}에 대한 정보:\n\n{wiki_extract[:500]}"
                    print(f"✅ Wikipedia 정보로 최적 답변 생성: {len(optimal_answer)}자")
            
            # Wikipedia도 없으면 가장 긴 AI 응답 사용
            if (not optimal_answer or len(optimal_answer) < 10) and llm_responses:
                longest_response = max(llm_responses.values(), key=len)
                if longest_response and len(longest_response) > 10:
                    optimal_answer = longest_response[:1000]  # 최대 1000자
                    print(f"✅ 가장 긴 AI 응답으로 최적 답변 생성: {len(optimal_answer)}자")
        
        result = {
            "최적의_답변": optimal_answer,
            "llm_검증_결과": {},
            "심판모델": judge_model,
            "상태": "성공",
            "신뢰도": parsed_data.get("confidence_score", "50"),
            "상호모순": parsed_data.get("contradictions_detected", []),
            "사실검증": parsed_data.get("fact_verification", {}),
            "분석_근거": parsed_data.get("analysis_rationale", "")
        }
        
        # 검증 소스 정보는 아래에서 통합 처리
        
        # 검증 결과 파싱 및 엄격한 환각 검증
        verification_results = parsed_data.get("verification_results", {})
        processed_models = set()
        
        for model_name, verification in verification_results.items():
            processed_models.add(model_name)
            
            adopted_raw = verification.get("adopted_info", [])
            rejected_raw = verification.get("rejected_info", [])
            
            print(f"\n🔍 {model_name} 검증:")
            print(f"   Judge 제공 adopted: {len(adopted_raw)}개")
            print(f"   Judge 제공 rejected: {len(rejected_raw)}개")
            
            adopted_info = []
            rejected_info = []
            
            if llm_responses and model_name in llm_responses:
                original_response = llm_responses[model_name]
                
                # 엄격한 환각 검증
                adopted_info = extract_valid_sentences(adopted_raw, original_response, model_name)
                rejected_info = extract_valid_sentences(rejected_raw, original_response, model_name)
                
                print(f"   검증 후 adopted: {len(adopted_info)}개")
                print(f"   검증 후 rejected: {len(rejected_info)}개")
                
                # 둘 다 비어있으면 원본에서 추출
                if not adopted_info and not rejected_info:
                    print(f"⚠️ {model_name}: 모두 비어있음, 원본에서 추출")
                    sentences = extract_sentences_from_response(original_response)
                    
                    # Wikipedia 정보가 있으면 Wikipedia 기준으로 분류
                    if wikipedia_info and sentences:
                        wiki_text = wikipedia_info['extract'].lower()
                        for sentence in sentences[:3]:
                            sentence_lower = sentence.lower()
                            # Wikipedia 내용과 유사한지 확인
                            similarity = similarity_ratio(sentence_lower, wiki_text)
                            if similarity > 0.3:  # 30% 이상 유사하면 채택
                                adopted_info.append(sentence)
                            else:
                                rejected_info.append(sentence)
                    else:
                        adopted_info = sentences[:3] if sentences else []
                    
                    print(f"   원본 추출 후 adopted: {len(adopted_info)}개, rejected: {len(rejected_info)}개")
            
            result["llm_검증_결과"][model_name] = {
                "정확성": verification.get("accuracy", "정확"),
                "오류": verification.get("errors", "없음"),
                "신뢰도": verification.get("confidence", "50"),
                "채택된_정보": adopted_info,
                "제외된_정보": rejected_info
            }
        
        # Judge가 누락한 모델 처리
        if llm_responses:
            for model_name in llm_responses.keys():
                if model_name not in processed_models:
                    print(f"\n⚠️ {model_name}: Judge 결과 누락, 기본 정보 생성")
                    sentences = extract_sentences_from_response(llm_responses[model_name])
                    
                    adopted_info = []
                    rejected_info = []
                    
                    # Wikipedia 정보가 있으면 Wikipedia 기준으로 분류
                    if wikipedia_info and sentences:
                        wiki_text = wikipedia_info['extract'].lower()
                        for sentence in sentences[:3]:
                            sentence_lower = sentence.lower()
                            similarity = similarity_ratio(sentence_lower, wiki_text)
                            if similarity > 0.3:
                                adopted_info.append(sentence)
                            else:
                                rejected_info.append(sentence)
                    else:
                        adopted_info = sentences[:3] if sentences else []
                    
                    result["llm_검증_결과"][model_name] = {
                        "정확성": "✅" if adopted_info else "❌",
                        "오류": "없음" if adopted_info else "검증 소스 불일치",
                        "신뢰도": "50",
                        "채택된_정보": adopted_info,
                        "제외된_정보": rejected_info
                    }
            
            result["원본_응답"] = llm_responses
        
        # 최종 통계
        print(f"\n📊 최종 검증 통계:")
        total_adopted = sum(len(v.get("채택된_정보", [])) for v in result["llm_검증_결과"].values())
        total_rejected = sum(len(v.get("제외된_정보", [])) for v in result["llm_검증_결과"].values())
        print(f"   전체 채택: {total_adopted}개")
        print(f"   전체 제외: {total_rejected}개")
        print(f"   처리 모델: {len(result['llm_검증_결과'])}개")
        
        # 검증 소스 정보 추가 (없을 때도 명시적으로 표시)
        if wikipedia_info:
            result["검증_소스"] = {
                "사용됨": True,
                "소스": wikipedia_info.get("source", "Unknown"),
                "제목": wikipedia_info.get("title", ""),
                "내용": wikipedia_info.get("extract", "")[:200],
                "신뢰도": wikipedia_info.get("confidence", 0)
            }
            print(f"   검증 소스: ✅ {wikipedia_info.get('source', 'Unknown')} 사용됨")
        else:
            result["검증_소스"] = {
                "사용됨": False,
                "소스": None,
                "제목": None,
                "내용": None,
                "신뢰도": 0
            }
            print(f"   검증 소스: ❌ 사용되지 않음")
        
        return result
        
    except Exception as e:
        print(f"❌ 파싱 실패: {e}")
        import traceback
        traceback.print_exc()
        return create_fallback_result(judge_model, llm_responses, wikipedia_info)


def create_fallback_result(judge_model, llm_responses=None, wikipedia_info=None):
    """폴백 결과 생성"""
    result = {
        "최적의_답변": "검증 중 오류가 발생했습니다.",
        "llm_검증_결과": {},
        "심판모델": judge_model,
        "상태": "파싱 실패",
        "신뢰도": "0",
        "상호모순": [],
        "사실검증": {}
    }
    
    # 검증 소스 정보 추가
    if wikipedia_info:
        result["검증_소스"] = {
            "사용됨": True,
            "소스": wikipedia_info.get("source", "Unknown"),
            "제목": wikipedia_info.get("title", ""),
            "내용": wikipedia_info.get("extract", "")[:200],
            "신뢰도": wikipedia_info.get("confidence", 0)
        }
    else:
        result["검증_소스"] = {
            "사용됨": False,
            "소스": None,
            "제목": None,
            "내용": None,
            "신뢰도": 0
    }
    
    if llm_responses:
        for model in llm_responses.keys():
            sentences = extract_sentences_from_response(llm_responses[model])
            result["llm_검증_결과"][model] = {
                "정확성": "❌",
                "오류": "검증 실패",
                "신뢰도": "0",
                "채택된_정보": sentences[:3] if sentences else [],
                "제외된_정보": []
            }
        result["원본_응답"] = llm_responses
    
    return result


def format_optimal_response(final_result):
    """최적 답변 포맷팅"""
    try:
        optimal_answer = final_result.get("최적의_답변", "")
        
        if not optimal_answer or len(optimal_answer.strip()) == 0:
            optimal_answer = "최적 답변 생성 중 오류가 발생했습니다."
        
        return f"""## 최적의 답변

{optimal_answer}
"""
    except Exception as e:
        print(f"❌ 포맷팅 실패: {e}")
        return f"""**최적의 답변:**

{final_result.get('최적의_답변', '답변 생성 실패')}

*포맷팅 오류*
"""