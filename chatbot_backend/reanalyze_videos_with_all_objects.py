#!/usr/bin/env python3
"""
영상 74, 75, 76, 77에 대해 모든 객체를 YOLO로 감지하여 재분석하는 스크립트
"""
import os
import sys
import django

# Django 설정 (import 전에 먼저 설정)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')

# Django setup을 먼저 실행
django.setup()

# 이제 import 가능
from chat.models import Video
import logging

# VideoAnalysisService는 직접 import하지 않고 경로로 접근
import importlib.util
spec = importlib.util.spec_from_file_location(
    "video_analysis_service",
    os.path.join(os.path.dirname(__file__), "chat", "services", "video_analysis_service.py")
)
video_analysis_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video_analysis_module)
VideoAnalysisService = video_analysis_module.VideoAnalysisService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reanalyze_video(video_id):
    """영상 재분석 (캡션 유지, YOLO 객체만 추가)"""
    try:
        video = Video.objects.get(id=video_id)
        logger.info(f"📹 Video ID {video_id} 재분석 시작: {video.original_name}")
        
        # 분석 서비스 초기화
        analysis_service = VideoAnalysisService()
        
        # 객체만 재분석 실행 (캡션 유지)
        logger.info(f"🔄 Video ID {video_id} 객체 재분석 중 (캡션 유지)...")
        result = analysis_service.reanalyze_objects_only(video_id)
        
        if result:
            logger.info(f"✅ Video ID {video_id} 재분석 완료")
            return True
        else:
            logger.error(f"❌ Video ID {video_id} 재분석 실패")
            return False
            
    except Video.DoesNotExist:
        logger.error(f"❌ Video ID {video_id}: 영상을 찾을 수 없습니다")
        return False
    except Exception as e:
        logger.error(f"❌ Video ID {video_id} 재분석 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 함수"""
    video_ids = [74, 75, 76, 77]
    
    print("=" * 100)
    print("📹 영상 재분석 시작 (모든 객체 YOLO 감지, 캡션 유지)")
    print("=" * 100)
    print()
    
    results = {}
    for video_id in video_ids:
        print(f"\n{'='*100}")
        print(f"Video ID {video_id} 재분석 중...")
        print(f"{'='*100}\n")
        
        success = reanalyze_video(video_id)
        results[video_id] = success
        
        if success:
            print(f"✅ Video ID {video_id} 재분석 완료\n")
        else:
            print(f"❌ Video ID {video_id} 재분석 실패\n")
    
    # 결과 요약
    print("\n" + "=" * 100)
    print("📊 재분석 결과 요약")
    print("=" * 100)
    print()
    
    for video_id, success in results.items():
        status = "✅ 성공" if success else "❌ 실패"
        print(f"Video ID {video_id}: {status}")
    
    print()
    success_count = sum(1 for s in results.values() if s)
    print(f"총 {len(results)}개 영상 중 {success_count}개 성공")

if __name__ == '__main__':
    main()

