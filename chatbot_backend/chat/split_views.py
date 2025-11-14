"""
views.py를 여러 파일로 분리하는 스크립트
"""
import re


def extract_class_or_function(content, name, is_class=True):
    """클래스나 함수를 추출"""
    if is_class:
        # class 정의부터 다음 class나 @api_view까지
        pattern = rf'(class {name}.*?)(?=(?:\nclass |\n@api_view|\Z))'
    else:
        # 함수 정의부터 다음 class, 함수, 또는 @api_view까지
        pattern = rf'(def {name}.*?)(?=(?:\ndef |\nclass |\n@api_view|\Z))'
    
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).rstrip() + '\n\n'
    return None


def extract_decorated_function(content, decorator, func_name):
    """@api_view 같은 데코레이터가 있는 함수 추출"""
    pattern = rf'({decorator}.*?def {func_name}.*?)(?=(?:\n@api_view|\nclass |\ndef (?!    )|\Z))'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).rstrip() + '\n\n'
    return None


def create_view_files():
    """views.py를 여러 파일로 분리"""
    
    with open('views.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        content = ''.join(lines)
    
    # Import 문들 추출 (처음 100줄 정도)
    imports = ''.join(lines[:100])
    
    # 공통 import 헤더
    common_imports = """from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse, Http404
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import requests
import hmac
import hashlib
import uuid
import os

from chat.serializers import UserSerializer, VideoChatSessionSerializer, VideoChatMessageSerializer, VideoAnalysisCacheSerializer
from chat.models import VideoChatSession, VideoChatMessage, VideoAnalysisCache, Video, User, SocialAccount
from ..utils.chatbot import ChatBot, chatbots
from ..utils.file_utils import process_uploaded_file, summarize_content
from ..services.optimal_response import collect_multi_llm_responses, format_optimal_response
from ..services.video_analysis_service import video_analysis_service
from ..enhanced_video_chat_handler import get_video_chat_handler

"""
    
    # 1. auth_views.py (소셜 로그인)
    print("📝 auth_views.py 생성 중...")
    auth_content = common_imports + "\n"
    
    # generate_unique_username 함수
    func = extract_class_or_function(content, 'generate_unique_username', is_class=False)
    if func:
        auth_content += func
    
    # google_callback
    func = extract_decorated_function(content, '@api_view', 'google_callback')
    if func:
        auth_content += func
    
    # kakao_callback
    func = extract_decorated_function(content, '@api_view', 'kakao_callback')
    if func:
        auth_content += func
    
    # naver_callback
    func = extract_decorated_function(content, '@api_view', 'naver_callback')
    if func:
        auth_content += func
    
    with open('views/auth_views.py', 'w', encoding='utf-8') as f:
        f.write(auth_content)
    print("✅ auth_views.py 생성 완료")
    
    # 2. chat_views.py (기본 채팅)
    print("📝 chat_views.py 생성 중...")
    chat_content = common_imports + "\n"
    
    cls = extract_class_or_function(content, 'ChatView', is_class=True)
    if cls:
        chat_content += cls
    
    with open('views/chat_views.py', 'w', encoding='utf-8') as f:
        f.write(chat_content)
    print("✅ chat_views.py 생성 완료")
    
    # 3. video_views.py (영상 업로드/목록/삭제)
    print("📝 video_views.py 생성 중...")
    video_content = common_imports + "\n"
    
    for class_name in ['VideoUploadView', 'VideoListView', 'VideoDeleteView', 'VideoRenameView', 'FrameImageView']:
        cls = extract_class_or_function(content, class_name, is_class=True)
        if cls:
            video_content += cls
    
    with open('views/video_views.py', 'w', encoding='utf-8') as f:
        f.write(video_content)
    print("✅ video_views.py 생성 완료")
    
    # 4. video_chat_views.py (영상 채팅)
    print("📝 video_chat_views.py 생성 중...")
    video_chat_content = common_imports + "\n"
    
    cls = extract_class_or_function(content, 'VideoChatView', is_class=True)
    if cls:
        video_chat_content += cls
    
    with open('views/video_chat_views.py', 'w', encoding='utf-8') as f:
        f.write(video_chat_content)
    print("✅ video_chat_views.py 생성 완료")
    
    # 5. video_analysis_views.py (영상 분석/요약/하이라이트)
    print("📝 video_analysis_views.py 생성 중...")
    video_analysis_content = common_imports + "\n"
    
    for class_name in ['VideoAnalysisView', 'VideoSummaryView', 'VideoHighlightView']:
        cls = extract_class_or_function(content, class_name, is_class=True)
        if cls:
            video_analysis_content += cls
    
    with open('views/video_analysis_views.py', 'w', encoding='utf-8') as f:
        f.write(video_analysis_content)
    print("✅ video_analysis_views.py 생성 완료")
    
    print("\n✅ 모든 view 파일 생성 완료!")
    print("   - views/auth_views.py")
    print("   - views/chat_views.py")
    print("   - views/video_views.py")
    print("   - views/video_chat_views.py")
    print("   - views/video_analysis_views.py")


if __name__ == '__main__':
    import os
    os.chdir('/Users/seon/AIOFAI_F/AI_of_AI/chatbot_backend/chat')
    create_view_files()

