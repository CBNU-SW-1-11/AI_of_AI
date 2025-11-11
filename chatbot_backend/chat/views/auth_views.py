from rest_framework.views import APIView
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


def generate_unique_username(email, name=None):
    """이메일 기반으로 고유한 사용자명 생성"""
    base_username = email.split('@')[0]
    username = base_username
    counter = 1
    
    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{counter}"
        counter += 1
    
    return username

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def google_callback(request):
    try:
        # 액세스 토큰 추출
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return Response(
                {'error': '잘못된 인증 헤더'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        access_token = auth_header.split(' ')[1]

        # Google API로 사용자 정보 요청
        user_info_response = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )

        if user_info_response.status_code != 200:
            return Response(
                {'error': 'Google에서 사용자 정보를 가져오는데 실패했습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        user_info = user_info_response.json()
        email = user_info.get('email')
        name = user_info.get('name')
        
        if not email:
            return Response(
                {'error': '이메일이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 기존 사용자 검색
            user = User.objects.get(email=email)
            # 기존 사용자의 이름이 없으면 업데이트
            if name and (not user.first_name and not user.last_name):
                if ' ' in name:
                    first_name, last_name = name.split(' ', 1)
                    user.first_name = first_name
                    user.last_name = last_name
                else:
                    user.first_name = name
                user.save()
        except User.DoesNotExist:
            # 새로운 사용자 생성
            username = generate_unique_username(email, name)
            user = User.objects.create(
                username=username,
                email=email,
                is_active=True
            )
            
            # 이름 설정
            if name:
                if ' ' in name:
                    first_name, last_name = name.split(' ', 1)
                    user.first_name = first_name
                    user.last_name = last_name
                else:
                    user.first_name = name
            
            # 기본 비밀번호 설정 (선택적)
            random_password = uuid.uuid4().hex
            user.set_password(random_password)
            user.save()

        # 소셜 계정 정보 생성 또는 업데이트
        social_account, created = SocialAccount.objects.get_or_create(
            email=email,
            provider='google',
            defaults={'user': user}
        )

        if not created and social_account.user != user:
            social_account.user = user
            social_account.save()

        # 사용자 정보 직렬화
        serializer = UserSerializer(user)
        
        return Response({
            'message': '구글 로그인 성공',
            'user': serializer.data
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def google_callback(request):
    try:
        # 액세스 토큰 추출
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return Response(
                {'error': '잘못된 인증 헤더'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        access_token = auth_header.split(' ')[1]

        # Google API로 사용자 정보 요청
        user_info_response = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )

        if user_info_response.status_code != 200:
            return Response(
                {'error': 'Google에서 사용자 정보를 가져오는데 실패했습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        user_info = user_info_response.json()
        email = user_info.get('email')
        name = user_info.get('name')
        
        if not email:
            return Response(
                {'error': '이메일이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 기존 사용자 검색
            user = User.objects.get(email=email)
            # 기존 사용자의 이름이 없으면 업데이트
            if name and (not user.first_name and not user.last_name):
                if ' ' in name:
                    first_name, last_name = name.split(' ', 1)
                    user.first_name = first_name
                    user.last_name = last_name
                else:
                    user.first_name = name
                user.save()
        except User.DoesNotExist:
            # 새로운 사용자 생성
            username = generate_unique_username(email, name)
            user = User.objects.create(
                username=username,
                email=email,
                is_active=True
            )
            
            # 이름 설정
            if name:
                if ' ' in name:
                    first_name, last_name = name.split(' ', 1)
                    user.first_name = first_name
                    user.last_name = last_name
                else:
                    user.first_name = name
            
            # 기본 비밀번호 설정 (선택적)
            random_password = uuid.uuid4().hex
            user.set_password(random_password)
            user.save()

        # 소셜 계정 정보 생성 또는 업데이트
        social_account, created = SocialAccount.objects.get_or_create(
            email=email,
            provider='google',
            defaults={'user': user}
        )

        if not created and social_account.user != user:
            social_account.user = user
            social_account.save()

        # 사용자 정보 직렬화
        serializer = UserSerializer(user)
        
        return Response({
            'message': '구글 로그인 성공',
            'user': serializer.data
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def kakao_callback(request):
    """카카오 로그인 콜백"""
    try:
        data = request.data
        access_token = data.get('access_token')
        
        if not access_token:
            return Response(
                {'error': '액세스 토큰이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 카카오 API로 사용자 정보 가져오기
        user_info_response = requests.get(
            'https://kapi.kakao.com/v2/user/me',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if user_info_response.status_code != 200:
            return Response(
                {'error': '카카오에서 사용자 정보를 가져오는데 실패했습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_info = user_info_response.json()
        kakao_account = user_info.get('kakao_account', {})
        profile = kakao_account.get('profile', {})
        
        email = kakao_account.get('email')
        name = profile.get('nickname')
        
        if not email:
            return Response(
                {'error': '이메일이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # 기존 사용자 검색
            user = User.objects.get(email=email)
            # 기존 사용자의 이름이 없으면 업데이트
            if name and (not user.first_name and not user.last_name):
                user.first_name = name
                user.save()
        except User.DoesNotExist:
            # 새로운 사용자 생성
            username = generate_unique_username(email, name)
            user = User.objects.create(
                username=username,
                email=email,
                is_active=True
            )
            
            # 이름 설정
            if name:
                user.first_name = name
            
            # 기본 비밀번호 설정 (선택적)
            random_password = uuid.uuid4().hex
            user.set_password(random_password)
            user.save()
        
        # 소셜 계정 정보 생성 또는 업데이트
        social_account, created = SocialAccount.objects.get_or_create(
            email=email,
            provider='kakao',
            defaults={'user': user}
        )
        
        if not created and social_account.user != user:
            social_account.user = user
            social_account.save()
        
        serializer = UserSerializer(user)
        return Response({
            'message': '카카오 로그인 성공',
            'user': serializer.data
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def google_callback(request):
    try:
        # 액세스 토큰 추출
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return Response(
                {'error': '잘못된 인증 헤더'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        access_token = auth_header.split(' ')[1]

        # Google API로 사용자 정보 요청
        user_info_response = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )

        if user_info_response.status_code != 200:
            return Response(
                {'error': 'Google에서 사용자 정보를 가져오는데 실패했습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        user_info = user_info_response.json()
        email = user_info.get('email')
        name = user_info.get('name')
        
        if not email:
            return Response(
                {'error': '이메일이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 기존 사용자 검색
            user = User.objects.get(email=email)
            # 기존 사용자의 이름이 없으면 업데이트
            if name and (not user.first_name and not user.last_name):
                if ' ' in name:
                    first_name, last_name = name.split(' ', 1)
                    user.first_name = first_name
                    user.last_name = last_name
                else:
                    user.first_name = name
                user.save()
        except User.DoesNotExist:
            # 새로운 사용자 생성
            username = generate_unique_username(email, name)
            user = User.objects.create(
                username=username,
                email=email,
                is_active=True
            )
            
            # 이름 설정
            if name:
                if ' ' in name:
                    first_name, last_name = name.split(' ', 1)
                    user.first_name = first_name
                    user.last_name = last_name
                else:
                    user.first_name = name
            
            # 기본 비밀번호 설정 (선택적)
            random_password = uuid.uuid4().hex
            user.set_password(random_password)
            user.save()

        # 소셜 계정 정보 생성 또는 업데이트
        social_account, created = SocialAccount.objects.get_or_create(
            email=email,
            provider='google',
            defaults={'user': user}
        )

        if not created and social_account.user != user:
            social_account.user = user
            social_account.save()

        # 사용자 정보 직렬화
        serializer = UserSerializer(user)
        
        return Response({
            'message': '구글 로그인 성공',
            'user': serializer.data
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def kakao_callback(request):
    """카카오 로그인 콜백"""
    try:
        data = request.data
        access_token = data.get('access_token')
        
        if not access_token:
            return Response(
                {'error': '액세스 토큰이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 카카오 API로 사용자 정보 가져오기
        user_info_response = requests.get(
            'https://kapi.kakao.com/v2/user/me',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if user_info_response.status_code != 200:
            return Response(
                {'error': '카카오에서 사용자 정보를 가져오는데 실패했습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_info = user_info_response.json()
        kakao_account = user_info.get('kakao_account', {})
        profile = kakao_account.get('profile', {})
        
        email = kakao_account.get('email')
        name = profile.get('nickname')
        
        if not email:
            return Response(
                {'error': '이메일이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # 기존 사용자 검색
            user = User.objects.get(email=email)
            # 기존 사용자의 이름이 없으면 업데이트
            if name and (not user.first_name and not user.last_name):
                user.first_name = name
                user.save()
        except User.DoesNotExist:
            # 새로운 사용자 생성
            username = generate_unique_username(email, name)
            user = User.objects.create(
                username=username,
                email=email,
                is_active=True
            )
            
            # 이름 설정
            if name:
                user.first_name = name
            
            # 기본 비밀번호 설정 (선택적)
            random_password = uuid.uuid4().hex
            user.set_password(random_password)
            user.save()
        
        # 소셜 계정 정보 생성 또는 업데이트
        social_account, created = SocialAccount.objects.get_or_create(
            email=email,
            provider='kakao',
            defaults={'user': user}
        )
        
        if not created and social_account.user != user:
            social_account.user = user
            social_account.save()
        
        serializer = UserSerializer(user)
        return Response({
            'message': '카카오 로그인 성공',
            'user': serializer.data
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def naver_callback(request):
    """네이버 로그인 콜백"""
    try:
        data = request.data
        access_token = data.get('access_token')
        code = data.get('code')
        state = data.get('state')
        client_id_override = data.get('client_id')
        client_secret_override = data.get('client_secret')
        redirect_uri_override = data.get('redirect_uri')
        
        if not access_token:
            if not code:
                return Response(
                    {'error': 'access_token 또는 code가 제공되지 않았습니다'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            client_id = client_id_override or os.getenv('NAVER_CLIENT_ID') or getattr(settings, 'NAVER_CLIENT_ID', '')
            client_secret = client_secret_override or os.getenv('NAVER_CLIENT_SECRET') or getattr(settings, 'NAVER_CLIENT_SECRET', '')
            redirect_uri = redirect_uri_override or os.getenv('NAVER_REDIRECT_URI') or getattr(settings, 'NAVER_REDIRECT_URI', '')
            
            if not client_id or not client_secret:
                return Response(
                    {'error': '네이버 클라이언트 설정이 누락되었습니다'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            token_response = requests.post(
                'https://nid.naver.com/oauth2.0/token',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data={
                    'grant_type': 'authorization_code',
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri,
                    'code': code,
                    'state': state or '',
                }
            )
            
            token_data = token_response.json()
            if token_response.status_code != 200 or not token_data.get('access_token'):
                return Response(
                    {
                        'error': '네이버 토큰 교환 실패',
                        'detail': token_data
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            access_token = token_data.get('access_token')
        
        if not access_token:
            return Response(
                {'error': '액세스 토큰이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 네이버 API로 사용자 정보 가져오기
        user_info_response = requests.get(
            'https://openapi.naver.com/v1/nid/me',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if user_info_response.status_code != 200:
            return Response(
                {'error': '네이버에서 사용자 정보를 가져오는데 실패했습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_info = user_info_response.json()
        response_data = user_info.get('response', {})
        
        email = response_data.get('email')
        name = response_data.get('name')
        nickname = response_data.get('nickname')
        
        if not email:
            return Response(
                {'error': '이메일이 제공되지 않았습니다'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 이름이 없으면 닉네임 사용
        display_name = name or nickname
        
        try:
            # 기존 사용자 검색
            user = User.objects.get(email=email)
            # 기존 사용자의 이름이 없으면 업데이트
            if display_name and (not user.first_name and not user.last_name):
                user.first_name = display_name
                user.save()
        except User.DoesNotExist:
            # 새로운 사용자 생성
            username = generate_unique_username(email, display_name)
            user = User.objects.create(
                username=username,
                email=email,
                is_active=True
            )
            
            # 이름 설정
            if display_name:
                user.first_name = display_name
            
            # 기본 비밀번호 설정 (선택적)
            random_password = uuid.uuid4().hex
            user.set_password(random_password)
            user.save()
        
        # 소셜 계정 정보 생성 또는 업데이트
        social_account, created = SocialAccount.objects.get_or_create(
            email=email,
            provider='naver',
            defaults={'user': user}
        )
        
        if not created and social_account.user != user:
            social_account.user = user
            social_account.save()
        
        serializer = UserSerializer(user)
        return Response({
            'message': '네이버 로그인 성공',
            'user': serializer.data
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

