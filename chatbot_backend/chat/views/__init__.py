"""
Chat app views - 모듈화된 구조
"""

# 소셜 로그인 관련
from .auth_views import (
    generate_unique_username,
    google_callback,
    kakao_callback,
    naver_callback
)

# 기본 채팅
from .chat_views import ChatView

# 영상 관리 (업로드/목록/삭제/이름변경)
from .video_views import (
    VideoUploadView,
    VideoListView,
    VideoDeleteView,
    VideoRenameView,
    FrameImageView
)

# 영상 채팅
from .video_chat_views import VideoChatView

# 영상 분석/요약/하이라이트
from .video_analysis_views import (
    VideoAnalysisView,
    VideoSummaryView,
    VideoHighlightView
)

__all__ = [
    # Auth
    'generate_unique_username',
    'google_callback',
    'kakao_callback',
    'naver_callback',
    
    # Chat
    'ChatView',
    
    # Video Management
    'VideoUploadView',
    'VideoListView',
    'VideoDeleteView',
    'VideoRenameView',
    'FrameImageView',
    
    # Video Chat
    'VideoChatView',
    
    # Video Analysis
    'VideoAnalysisView',
    'VideoSummaryView',
    'VideoHighlightView',
]
