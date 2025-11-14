"""
웹 검증 및 검색 관련 함수들을 services/video_search.py로 추출하는 스크립트
"""
import re


def extract_function_by_name(content, func_name, next_func_name=None):
    """함수 이름으로 함수 전체를 추출"""
    if next_func_name:
        pattern = rf'(def {func_name}\(.*?\n)(def {next_func_name}\()'
    else:
        pattern = rf'(def {func_name}\(.*?\n)((?:def |class |@api_view|# ===))'
    
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).rstrip() + '\n\n'
    return None


def extract_video_search_services():
    """웹 검증 및 검색 함수들을 services/video_search.py로 추출"""
    
    with open('views.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 추출할 함수 목록
    functions_to_extract = [
        ('quick_web_verify', 'search_wikipedia'),
        ('search_wikipedia', 'extract_search_terms_from_question'),
        ('extract_search_terms_from_question', 'search_wikipedia_api'),
        ('search_wikipedia_api', 'get_wikipedia_full_text'),
        ('get_wikipedia_full_text', 'search_google_simple'),
        ('search_google_simple', None),
    ]
    
    extracted_functions = []
    
    for func_name, next_func in functions_to_extract:
        print(f"📝 Extracting {func_name}...")
        func_code = extract_function_by_name(content, func_name, next_func)
        if func_code:
            extracted_functions.append(func_code)
            print(f"✅ {func_name} 추출 완료")
        else:
            print(f"⚠️ {func_name} 추출 실패")
    
    # services/video_search.py 생성
    video_search_content = '''"""
웹 검증 및 검색 서비스
Wikipedia API를 통한 사실 검증
"""
import re
import requests
from collections import Counter


''' + '\n\n'.join(extracted_functions)
    
    with open('services/video_search.py', 'w', encoding='utf-8') as f:
        f.write(video_search_content)
    
    print(f"\n✅ services/video_search.py 생성 완료! ({len(extracted_functions)}개 함수)")
    
    # views.py에서 추출한 함수들 제거
    for func_name, _ in functions_to_extract:
        pattern = rf'def {func_name}\(.*?\n(?=(?:def |class |@api_view|# ===))'
        content = re.sub(pattern, '', content, flags=re.DOTALL, count=1)
        print(f"🗑️ {func_name} 제거됨")
    
    # import 추가
    import_position = content.find('from .services.optimal_response import')
    if import_position != -1:
        # 닫는 괄호 찾기
        end_position = content.find(')', import_position) + 1
        next_line = content.find('\n', end_position)
        new_import = "\nfrom .services.video_search import (\n    quick_web_verify,\n    search_wikipedia,\n    extract_search_terms_from_question,\n    search_wikipedia_api,\n    get_wikipedia_full_text,\n    search_google_simple\n)"
        content = content[:next_line] + new_import + content[next_line:]
    
    # 빈 줄 정리
    content = re.sub(r'\n{4,}', '\n\n\n', content)
    
    with open('views.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ views.py에서 함수들 제거 및 import 추가 완료!")


if __name__ == '__main__':
    import os
    os.chdir('/Users/seon/AIOFAI_F/AI_of_AI/chatbot_backend/chat')
    extract_video_search_services()

