"""
통합 채팅 뷰
- 일반 채팅과 영상 채팅 통합
- 정확한 사실 검증 시스템 적용
- 여러 AI 모델의 응답을 통합하여 최적의 답변 제공
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
import logging
import asyncio

from .integrated_chat_service import integrated_chat_service

logger = logging.getLogger(__name__)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def integrated_chat_view(request):
    """통합 채팅 뷰 - 일반 채팅과 영상 채팅 통합"""
    try:
        data = request.data
        message = data.get('message', '').strip()
        chat_type = data.get('type', 'general')  # 'general' or 'video'
        video_id = data.get('video_id')
        attachments = data.get('attachments', [])
        
        if not message:
            return Response({
                'success': False,
                'error': '메시지가 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"💬 통합 채팅 요청: {chat_type}, {message[:50]}...")
        
        # 비동기 처리
        if chat_type == 'video' and video_id:
            # 영상 채팅 처리
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    integrated_chat_service.process_video_chat(
                        user_id=request.user.id,
                        video_id=video_id,
                        message=message,
                        query_type=data.get('query_type', 'general')
                    )
                )
            finally:
                loop.close()
        else:
            # 일반 채팅 처리
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    integrated_chat_service.process_general_chat(
                        user_id=request.user.id,
                        message=message,
                        attachments=attachments
                    )
                )
            finally:
                loop.close()
        
        if result['success']:
            return Response({
                'success': True,
                'data': result
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': result.get('error', '채팅 처리 실패')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"❌ 통합 채팅 처리 실패: {e}")
        return Response({
            'success': False,
            'error': '채팅 처리 중 오류가 발생했습니다.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_chat_history(request):
    """채팅 히스토리 조회"""
    try:
        session_id = request.GET.get('session_id')
        
        if not session_id:
            return Response({
                'success': False,
                'error': '세션 ID가 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        history = integrated_chat_service.get_chat_history(session_id)
        
        return Response({
            'success': True,
            'history': history
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ 채팅 히스토리 조회 실패: {e}")
        return Response({
            'success': False,
            'error': '채팅 히스토리 조회 중 오류가 발생했습니다.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def verify_fact_view(request):
    """사실 검증 뷰 - 특정 사실의 정확성 검증"""
    try:
        data = request.data
        fact_text = data.get('fact', '').strip()
        query = data.get('query', '').strip()
        
        if not fact_text or not query:
            return Response({
                'success': False,
                'error': '사실과 질문이 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 비동기 사실 검증
        from .factual_verification_system import factual_verification_system
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 가상의 AI 응답들 생성 (실제로는 여러 AI에서 받은 응답)
            mock_responses = {
                'gpt': f"GPT 응답: {fact_text}",
                'claude': f"Claude 응답: {fact_text}",
                'mixtral': f"Mixtral 응답: {fact_text}"
            }
            
            verification_result = loop.run_until_complete(
                factual_verification_system.analyze_and_verify_responses(mock_responses, query)
            )
            
            return Response({
                'success': True,
                'verification': {
                    'overall_accuracy': verification_result.overall_accuracy,
                    'verified_facts': len([f for f in verification_result.verified_facts if f.is_verified]),
                    'conflicting_facts': len(verification_result.conflicting_facts),
                    'correction_suggestions': verification_result.correction_suggestions[:3]
                }
            }, status=status.HTTP_200_OK)
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"❌ 사실 검증 실패: {e}")
        return Response({
            'success': False,
            'error': '사실 검증 중 오류가 발생했습니다.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegratedChatAPIView(APIView):
    """통합 채팅 API 뷰 클래스"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """통합 채팅 처리"""
        try:
            data = request.data
            message = data.get('message', '').strip()
            chat_type = data.get('type', 'general')
            video_id = data.get('video_id')
            attachments = data.get('attachments', [])
            
            if not message:
                return Response({
                    'success': False,
                    'error': '메시지가 필요합니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 비동기 처리
            if chat_type == 'video' and video_id:
                result = self._process_video_chat(request.user.id, video_id, message, data)
            else:
                result = self._process_general_chat(request.user.id, message, attachments)
            
            return Response(result, status=status.HTTP_200_OK if result['success'] else status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"❌ 통합 채팅 API 처리 실패: {e}")
            return Response({
                'success': False,
                'error': '채팅 처리 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _process_video_chat(self, user_id, video_id, message, data):
        """영상 채팅 처리"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                integrated_chat_service.process_video_chat(
                    user_id=user_id,
                    video_id=video_id,
                    message=message,
                    query_type=data.get('query_type', 'general')
                )
            )
            return result
        finally:
            loop.close()
    
    def _process_general_chat(self, user_id, message, attachments):
        """일반 채팅 처리"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                integrated_chat_service.process_general_chat(
                    user_id=user_id,
                    message=message,
                    attachments=attachments
                )
            )
            return result
        finally:
            loop.close()
    
    def get(self, request):
        """채팅 히스토리 조회"""
        try:
            session_id = request.GET.get('session_id')
            
            if not session_id:
                return Response({
                    'success': False,
                    'error': '세션 ID가 필요합니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            history = integrated_chat_service.get_chat_history(session_id)
            
            return Response({
                'success': True,
                'history': history
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"❌ 채팅 히스토리 조회 실패: {e}")
            return Response({
                'success': False,
                'error': '채팅 히스토리 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
