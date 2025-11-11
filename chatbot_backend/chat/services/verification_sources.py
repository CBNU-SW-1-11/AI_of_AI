"""
검증 소스 검색 모듈
Wikipedia, Wikidata, DBpedia, DuckDuckGo 검색 기능
"""
import json
import requests


def quick_wikipedia_search(query, lang='ko'):
    """Wikipedia에서 빠른 검색 (한국어/영어 지원)"""
    try:
        search_query = query
        lang_name = "한국어" if lang == 'ko' else "영어"
        print(f"🔍 Wikipedia ({lang_name}) 검색 시작: '{search_query}'")
        
        search_url = f"https://{lang}.wikipedia.org/w/api.php"
        search_params = {
            "action": "query", "format": "json", "list": "search",
            "srsearch": search_query, "utf8": 1, "srlimit": 5,
            "srprop": "size|wordcount|timestamp"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.get(search_url, params=search_params, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Wikipedia ({lang_name}) API 응답 오류: {response.status_code}")
            return None
        
        try:
            search_data = response.json()
        except json.JSONDecodeError as e:
            print(f"⚠️ Wikipedia JSON 파싱 실패: {e}")
            return None
        
        if not search_data.get("query", {}).get("search"):
            print(f"⚠️ Wikipedia 검색 결과 없음")
            return None
        
        search_results = search_data["query"]["search"]
        original_keywords = search_query.lower().split()
        best_result = None
        best_score = 0
        
        for result in search_results[:5]:
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "").lower()
            keyword_match_score = 0
            matched_keywords = []
            
            for keyword in original_keywords:
                if keyword in title:
                    keyword_match_score += 15
                    matched_keywords.append(keyword)
                elif keyword in snippet:
                    keyword_match_score += 8
                    matched_keywords.append(keyword)
            
            if len(matched_keywords) == 0:
                continue
            
            if keyword_match_score > best_score:
                best_score = keyword_match_score
                best_result = result
        
        if not best_result or best_score < 10:
            print(f"⚠️ 검색 결과의 관련성 점수가 낮음 (최고 점수: {best_score:.1f}점). 검색 실패로 처리")
            return None
        
        page_id = best_result["pageid"]
        page_title = best_result["title"]
        print(f"📄 Wikipedia 페이지 발견: '{page_title}' (ID: {page_id}, 관련성 점수: {best_score:.1f})")
        
        content_params = {
            "action": "query", "format": "json", "pageids": page_id,
            "prop": "extracts", "exintro": True, "explaintext": True, "exchars": 500
        }
        content_response = requests.get(search_url, params=content_params, headers=headers, timeout=10)
        
        if content_response.status_code != 200:
            print(f"⚠️ Wikipedia ({lang_name}) 페이지 내용 가져오기 실패: {content_response.status_code}")
            return None
        
        try:
            content_data = content_response.json()
        except json.JSONDecodeError:
            return None
        
        pages = content_data.get("query", {}).get("pages", {})
        if str(page_id) not in pages:
            return None
        
        page_data = pages[str(page_id)]
        if page_data.get("missing"):
            return None
        
        extract = page_data.get("extract", "")
        title = page_data.get("title", page_title)
        
        if not extract:
            return None
        
        print(f"✅ Wikipedia 페이지 찾음: '{title}'")
        return {
            "source": "Wikipedia", "title": title, "extract": extract,
            "verified": True, "confidence": 0.9
        }
        
    except requests.exceptions.Timeout:
        print(f"❌ Wikipedia 검색 타임아웃")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Wikipedia 네트워크 오류: {e}")
        return None
    except Exception as e:
        print(f"❌ Wikipedia 검색 실패: {e}")
        return None


def search_duckduckgo_instant_answer(query):
    """DuckDuckGo Instant Answer API 검색"""
    try:
        print(f"🔍 DuckDuckGo Instant Answer 검색 시작: '{query}'")
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        try:
            data = response.json()
        except Exception:
            return None
        
        if data.get("AbstractText"):
            print(f"✅ DuckDuckGo Instant Answer 찾음")
            return {
                "source": "DuckDuckGo Instant Answer",
                "title": data.get("Heading", query),
                "extract": data.get("AbstractText", ""),
                "url": data.get("AbstractURL", ""),
                "verified": True, "confidence": 0.85
            }
        
        if data.get("RelatedTopics") and len(data["RelatedTopics"]) > 0:
            first_topic = data["RelatedTopics"][0]
            if isinstance(first_topic, dict) and first_topic.get("Text"):
                print(f"✅ DuckDuckGo RelatedTopics 찾음")
                return {
                    "source": "DuckDuckGo Instant Answer",
                    "title": first_topic.get("FirstURL", "").split("/")[-1] if first_topic.get("FirstURL") else query,
                    "extract": first_topic.get("Text", ""),
                    "url": first_topic.get("FirstURL", ""),
                    "verified": True, "confidence": 0.8
                }
        
        return None
    except Exception:
        return None


def search_wikidata(query, lang='ko'):
    """Wikidata SPARQL 검색 (한국어/영어 지원)"""
    try:
        lang_name = "한국어" if lang == 'ko' else "영어"
        print(f"🔍 Wikidata ({lang_name}) 검색 시작: '{query}'")
        
        sparql_url = "https://query.wikidata.org/sparql"
        search_query_escaped = query.replace('"', '\\"')
        search_words = search_query_escaped.split()[:2]
        search_term = " ".join(search_words)
        
        sparql_query = f"""
        SELECT ?item ?itemLabel ?itemDescription WHERE {{
          ?item rdfs:label ?itemLabel .
          FILTER(LANG(?itemLabel) = "{lang}" && CONTAINS(LCASE(?itemLabel), LCASE("{search_term}")))
          OPTIONAL {{ ?item schema:description ?itemDescription . FILTER(LANG(?itemDescription) = "{lang}") }}
        }}
        LIMIT 1
        """
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/sparql-results+json"
        }
        
        response = requests.get(
            sparql_url, params={"query": sparql_query, "format": "json"},
            headers=headers, timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", {}).get("bindings", [])
            if results:
                result = results[0]
                item_label = result.get("itemLabel", {}).get("value", query)
                item_desc = result.get("itemDescription", {}).get("value", "")
                print(f"✅ Wikidata ({lang_name}) 항목 찾음: '{item_label}'")
                return {
                    "source": "Wikidata", "title": item_label, "extract": item_desc,
                    "item_id": result.get("item", {}).get("value", ""),
                    "verified": True, "confidence": 0.88
                }
        return None
    except Exception:
        return None


def search_dbpedia(query, lang='ko'):
    """DBpedia SPARQL 검색 (한국어/영어 지원)"""
    try:
        lang_name = "한국어" if lang == 'ko' else "영어"
        print(f"🔍 DBpedia ({lang_name}) 검색 시작: '{query}'")
        
        sparql_url = "https://dbpedia.org/sparql"
        search_query_escaped = query.replace('"', '\\"')
        search_words = search_query_escaped.split()[:2]
        search_term = " ".join(search_words)
        
        sparql_query = f"""
        SELECT ?resource ?label ?abstract WHERE {{
          ?resource rdfs:label ?label .
          FILTER(LANG(?label) = "{lang}" && CONTAINS(LCASE(?label), LCASE("{search_term}")))
          OPTIONAL {{ ?resource dbo:abstract ?abstract . FILTER(LANG(?abstract) = "{lang}") }}
        }}
        LIMIT 1
        """
        
        headers = {"Accept": "application/sparql-results+json", "User-Agent": "Mozilla/5.0"}
        
        response = requests.get(
            sparql_url, params={"query": sparql_query, "format": "json"},
            headers=headers, timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", {}).get("bindings", [])
            if results:
                result = results[0]
                label = result.get("label", {}).get("value", query)
                abstract = result.get("abstract", {}).get("value", "")
                if not abstract:
                    abstract = f"{label}에 대한 정보입니다." if lang == 'ko' else f"Information about {label}."
                print(f"✅ DBpedia ({lang_name}) 항목 찾음: '{label}'")
                return {
                    "source": "DBpedia", "title": label, "extract": abstract,
                    "resource": result.get("resource", {}).get("value", ""),
                    "verified": True, "confidence": 0.87
                }
        return None
    except Exception:
        return None


def get_best_verification_source(query):
    """여러 검증 소스 중 가장 좋은 하나 선택"""
    print(f"\n🔍 다중 검증 소스 검색 시작: '{query}'")
    
    wiki_result = quick_wikipedia_search(query, lang='ko')
    if not wiki_result:
        print(f"   한국어 Wikipedia 실패, 영어 Wikipedia 시도...")
        wiki_result = quick_wikipedia_search(query, lang='en')
    if wiki_result:
        print(f"✅ Wikipedia 검색 성공! 다른 소스는 건너뜁니다.")
        print(f"\n✅ 최적 검증 소스 선택: {wiki_result['source']} (신뢰도: {wiki_result.get('confidence', 0):.2f})")
        return wiki_result
    
    print(f"⚠️ Wikipedia 검색 실패, 다른 검증 소스 시도...")
    results = []
    
    try:
        wikidata_result = search_wikidata(query, lang='ko')
        if not wikidata_result:
            wikidata_result = search_wikidata(query, lang='en')
        if wikidata_result:
            results.append(wikidata_result)
    except Exception as e:
        print(f"⚠️ Wikidata 검색 중 오류 발생, 건너뜁니다: {e}")
    
    try:
        dbpedia_result = search_dbpedia(query, lang='ko')
        if not dbpedia_result:
            dbpedia_result = search_dbpedia(query, lang='en')
        if dbpedia_result:
            results.append(dbpedia_result)
    except Exception as e:
        print(f"⚠️ DBpedia 검색 중 오류 발생, 건너뜁니다: {e}")
    
    try:
        ddg_result = search_duckduckgo_instant_answer(query)
        if ddg_result:
            results.append(ddg_result)
    except Exception as e:
        print(f"⚠️ DuckDuckGo 검색 중 오류 발생, 건너뜁니다: {e}")
    
    if not results:
        print(f"⚠️ 모든 검증 소스에서 결과 없음")
        return None
    
    results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    best_result = results[0]
    print(f"\n✅ 최적 검증 소스 선택: {best_result['source']} (신뢰도: {best_result.get('confidence', 0):.2f})")
    return best_result

