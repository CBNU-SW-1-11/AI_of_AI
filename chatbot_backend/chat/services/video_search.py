"""
웹 검증 및 검색 서비스
Wikipedia API를 통한 사실 검증
"""
import re
import requests
from collections import Counter


def quick_web_verify(conflict_type, conflict_values, question):
    """개선된 웹 검증 (Wikipedia + Google Search) - 범용적"""
    import requests
    import time
    import re
    
    try:
        print(f"🌐 웹 검증 시작: '{question}'")
        
        # 1차: Wikipedia API 검색 (질문 기반)
        print("🔍 Wikipedia 검색 시도...")
        wiki_result = search_wikipedia(question, [])
        if wiki_result.get("verified"):
            print(f"✅ Wikipedia 검증 성공")
            return wiki_result
        
        # 2차: Google Search (간단한 방법)
        print("🔍 Google 검색 시도...")
        google_result = search_google_simple(question, [])
        if google_result.get("verified"):
            print(f"✅ Google 검증 성공")
            return google_result
        
        # 모든 검색이 실패한 경우
        print("⚠️ 모든 웹 검색 실패")
        return {"verified": False, "error": "모든 검색 엔진 실패"}
                
    except Exception as e:
        print(f"⚠️ 웹 검증 실패: {e}")
        return {"verified": False, "error": str(e)}



def search_wikipedia(question, keywords):
    """Wikipedia API를 통한 자동 검증 (하드코딩 없음)"""
    import requests
    import re
    
    try:
        # 1단계: 질문에서 핵심 키워드 추출
        search_terms = extract_search_terms_from_question(question)
        
        if not search_terms:
            print("⚠️ 검색 키워드 추출 실패")
            return {"verified": False, "error": "검색 키워드 없음"}
        
        print(f"🔍 Wikipedia 검색 키워드: {search_terms}")
        
        # 2단계: 각 검색어로 Wikipedia 검색 시도
        for term in search_terms[:3]:  # 최대 3개 키워드 시도
            # 한글 Wikipedia 검색
            wiki_results = search_wikipedia_api(term, 'ko')
            
            if wiki_results.get("verified"):
                return wiki_results
            
            # 실패 시 영어 Wikipedia 검색
            wiki_results_en = search_wikipedia_api(term, 'en')
            
            if wiki_results_en.get("verified"):
                return wiki_results_en
        
        print("⚠️ 모든 Wikipedia 검색 실패")
        return {"verified": False, "error": "Wikipedia 검색 실패"}
        
    except Exception as e:
        print(f"⚠️ Wikipedia 검증 오류: {e}")
        return {"verified": False, "error": f"Wikipedia 오류: {e}"}



def extract_search_terms_from_question(question):
    """질문에서 검색 키워드 자동 추출 (범용적)"""
    import re
    
    keywords = []
    
    # 1. 일반적인 명사 패턴 (하드코딩 없이)
    # 한국어 명사 패턴 (2글자 이상)
    korean_nouns = re.findall(r'[가-힣]{2,}', question)
    keywords.extend(korean_nouns)
    
    # 영어 대문자로 시작하는 단어들 (고유명사)
    english_proper_nouns = re.findall(r'[A-Z][a-z]+(?:\s[A-Z][a-z]+)*', question)
    keywords.extend(english_proper_nouns)
    
    # 숫자와 함께 나오는 단어들 (연도, 수치 등)
    number_words = re.findall(r'\d{4}년?|\d+명?|\d+개?', question)
    keywords.extend(number_words)
    
    # 특수 패턴들 (범용적)
    special_patterns = [
        r'([가-힣]+대학교?)',  # 대학교
        r'([가-힣]+대학?)',    # 대학
        r'([가-힣]+회사?)',    # 회사
        r'([가-힣]+정부?)',    # 정부
        r'([가-힣]+사건?)',    # 사건
        r'([가-힣]+전쟁?)',    # 전쟁
        r'([가-힣]+혁명?)',    # 혁명
        r'([가-힣]+올림픽?)',  # 올림픽
    ]
    
    for pattern in special_patterns:
        matches = re.findall(pattern, question)
        keywords.extend(matches)
    
    # 중복 제거 및 정리
    unique_keywords = []
    for kw in keywords:
        if kw and kw not in unique_keywords and len(kw.strip()) > 1:
            # 너무 일반적인 단어들 제외
            common_words = ['설명', '대해', '알려', '줘', '해줘', '어떤', '무엇', '언제', '어디', '왜', '어떻게']
            if kw.strip() not in common_words:
                unique_keywords.append(kw.strip())
    
    # 상위 3개 키워드만 반환 (너무 많으면 검색이 비효율적)
    print(f"🔍 추출된 키워드: {unique_keywords[:3]}")
    return unique_keywords[:3]



def search_wikipedia_api(search_term, lang='ko'):
    """Wikipedia API 실제 검색"""
    import requests
    import re
    from collections import Counter
    
    try:
        # User-Agent 헤더 추가 (Wikipedia API 요구사항)
        headers = {
            'User-Agent': 'AI_of_AI_ChatBot/1.0 (Educational Project)'
        }
        
        # Wikipedia Search API로 페이지 찾기
        search_url = f"https://{lang}.wikipedia.org/w/api.php"
        search_params = {
            'action': 'opensearch',
            'search': search_term,
            'limit': 1,
            'namespace': 0,
            'format': 'json'
        }
        
        response = requests.get(search_url, params=search_params, headers=headers, timeout=5)
        
        if response.status_code != 200:
            return {"verified": False, "error": f"검색 실패: {response.status_code}"}
        
        search_results = response.json()
        
        if not search_results or len(search_results) < 2 or not search_results[1]:
            print(f"⚠️ '{search_term}' Wikipedia 페이지 없음")
            return {"verified": False, "error": "페이지 없음"}
        
        page_title = search_results[1][0]
        print(f"📄 Wikipedia 페이지 발견: {page_title}")
        
        # 페이지 요약 가져오기
        summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{page_title}"
        summary_response = requests.get(summary_url, headers=headers, timeout=5)
        
        if summary_response.status_code == 200:
            data = summary_response.json()
            extract = data.get('extract', '')
            
            if extract and len(extract) > 20:
                print(f"✅ Wikipedia 요약: {extract[:100]}...")
                
                # 모든 정보 추출 (연도, 위치, 기타 정보)
                extracted_info = {
                    "verified": True,
                    "source": f"Wikipedia ({lang})",
                    "abstract": extract[:400] + "..." if len(extract) > 400 else extract,
                    "full_text": extract,  # 전체 텍스트 저장
                    "confidence": 0.95,
                    "page_title": page_title
                }
                
                # 연도 패턴 추출 (설립, 창립, 개교 등)
                years = re.findall(r'(\d{4})', extract)
                valid_years = [year for year in years if 1900 <= int(year) <= 2024]
                
                if valid_years:
                    # 설립/개교 관련 연도 우선 추출
                    founding_patterns = [
                        r'(\d{4})년[^\d]*(?:설립|창립|개교|대학.*설립|대학교.*설립|설립.*대학)',
                        r'(?:설립|창립|개교)[^\d]*(\d{4})년',
                        r'(\d{4})년.*(?:출범|탄생|생성)'
                    ]
                    
                    # 각 패턴에서 가장 먼저 매치되는 연도 찾기 (위치 기준)
                    first_matches = []
                    for pattern in founding_patterns:
                        match = re.search(pattern, extract, re.IGNORECASE)
                        if match:
                            matched_year = match.group(1)
                            if matched_year in valid_years:
                                position = match.start()
                                first_matches.append((position, matched_year))
                    
                    if first_matches:
                        # 위치가 가장 앞선 연도 선택
                        first_matches.sort()
                        most_common_year = first_matches[0][1]
                    else:
                        # 설립 연도 패턴이 없으면 가장 자주 언급된 연도
                        year_counts = Counter(valid_years)
                        most_common_year = year_counts.most_common(1)[0][0]
                    
                    extracted_info["extracted_year"] = most_common_year
                    print(f"📅 추출된 연도: {most_common_year}년")
                
                # 위치 정보 추출 (시, 도, 구 등)
                location_patterns = [
                    r'([가-힣]+특별시|[가-힣]+광역시|[가-힣]+시)\s+([가-힣]+구|[가-힣]+군)',
                    r'([가-힣]+특별시|[가-힣]+광역시|[가-힣]+시)',
                    r'([가-힣]+도)\s+([가-힣]+시)',
                ]
                
                for pattern in location_patterns:
                    location_matches = re.findall(pattern, extract)
                    if location_matches:
                        if isinstance(location_matches[0], tuple):
                            location = ' '.join(location_matches[0])
                        else:
                            location = location_matches[0]
                        extracted_info["location"] = location
                        print(f"📍 추출된 위치: {location}")
                        break
                
                # 국립/사립/공립 정보 추출
                if '국립' in extract:
                    extracted_info["type"] = "국립"
                    print(f"🏛️ 유형: 국립")
                elif '사립' in extract:
                    extracted_info["type"] = "사립"
                    print(f"🏛️ 유형: 사립")
                
                # 연도가 없으면 본문에서 추가 검색
                if not extracted_info.get("extracted_year"):
                    print("⚠️ 요약에 연도 없음, 본문 API로 fallback...")
                    full_text_result = get_wikipedia_full_text(page_title, lang, headers)
                    if full_text_result.get("verified") and full_text_result.get("extracted_year"):
                        extracted_info["extracted_year"] = full_text_result["extracted_year"]
                        print(f"📅 본문에서 추출된 설립연도: {full_text_result['extracted_year']}년")
                
                return extracted_info
        
        return {"verified": False, "error": "내용 추출 실패"}
        
    except Exception as e:
        return {"verified": False, "error": f"API 오류: {e}"}



def get_wikipedia_full_text(page_title, lang, headers):
    """Wikipedia 본문에서 연도 정보 추출"""
    import requests
    import re
    from collections import Counter
    
    try:
        # Wikipedia Parse API로 본문 일부 가져오기
        parse_url = f"https://{lang}.wikipedia.org/w/api.php"
        parse_params = {
            'action': 'query',
            'prop': 'extracts',
            'exintro': True,  # 서론만 가져오기
            'explaintext': True,  # 순수 텍스트
            'titles': page_title,
            'format': 'json'
        }
        
        response = requests.get(parse_url, params=parse_params, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            pages = data.get('query', {}).get('pages', {})
            
            if pages:
                page = list(pages.values())[0]
                full_text = page.get('extract', '')
                
                if full_text and len(full_text) > 50:
                    print(f"📄 Wikipedia 본문: {full_text[:150]}...")
                    
                    # 연도 패턴 추출 (설립/개교 관련 연도 우선)
                    years = re.findall(r'(\d{4})', full_text)
                    valid_years = [year for year in years if 1900 <= int(year) <= 2024]
                    
                    if valid_years:
                        # 설립/개교 키워드가 있는 문장에서 연도 우선 추출
                        founding_patterns = [
                            r'(\d{4})년[^\d]*(?:설립|창립|개교|대학.*설립|대학교.*설립|설립.*대학)',
                            r'(?:설립|창립|개교)[^\d]*(\d{4})년',
                            r'(\d{4})년.*(?:출범|탄생|생성)'
                        ]
                        # 각 패턴에서 가장 먼저 매치되는 연도 찾기 (위치 기준)
                        first_matches = []
                        for pattern in founding_patterns:
                            match = re.search(pattern, full_text, re.IGNORECASE)
                            if match:
                                matched_year = match.group(1)
                                if matched_year in valid_years:
                                    position = match.start()
                                    first_matches.append((position, matched_year))
                        
                        if first_matches:
                            # 위치가 가장 앞선 연도 선택 (원래 설립 연도 우선)
                            first_matches.sort()  # 위치 순으로 정렬
                            most_common_year = first_matches[0][1]
                        else:
                            # 없으면 가장 자주 언급된 연도 선택
                            year_counts = Counter(valid_years)
                            most_common_year = year_counts.most_common(1)[0][0]
                        
                        return {
                            "verified": True,
                            "source": f"Wikipedia Full Text ({lang})",
                            "extracted_year": most_common_year,
                            "abstract": full_text[:200] + "..." if len(full_text) > 200 else full_text,
                            "confidence": 0.85,
                            "page_title": page_title
                        }
        
        return {"verified": False, "error": "본문 추출 실패"}
        
    except Exception as e:
        return {"verified": False, "error": f"본문 검색 오류: {e}"}



def search_google_simple(question, keywords):
    """대체 검색 방법 (Wikipedia 실패 시)"""
    # Wikipedia API가 실패한 경우 다른 공개 API 시도 가능
    # 현재는 Wikipedia에만 의존
    return {"verified": False, "error": "Wikipedia 외 검색 미구현"}

