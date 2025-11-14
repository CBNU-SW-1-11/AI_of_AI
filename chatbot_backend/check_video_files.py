#!/usr/bin/env python
"""
영상 파일과 분석 파일 매칭 확인 스크립트
"""
import os
import json
import django
import sys

# Django 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

from chat.models import Video
from django.conf import settings

def check_video_files():
    """모든 비디오와 매칭되는 분석 파일 확인"""
    media_dir = settings.MEDIA_ROOT
    print(f"📁 Media 디렉토리: {media_dir}\n")
    
    # 모든 meta_db 파일 목록
    import glob
    meta_db_files = glob.glob(os.path.join(media_dir, "*-meta_db.json"))
    detection_db_files = glob.glob(os.path.join(media_dir, "*-detection_db.json"))
    
    print(f"📊 발견된 파일:")
    print(f"  - Meta DB 파일: {len(meta_db_files)}개")
    print(f"  - Detection DB 파일: {len(detection_db_files)}개\n")
    
    # 각 파일의 정보 출력
    print("=" * 80)
    print("Meta DB 파일 목록:")
    print("=" * 80)
    for meta_file in sorted(meta_db_files):
        basename = os.path.basename(meta_file)
        mtime = os.path.getmtime(meta_file)
        from datetime import datetime
        mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                video_id_in_file = data.get('video_id', 'N/A')
                frame_count = len(data.get('frame', []))
                print(f"\n📄 {basename}")
                print(f"   수정 시간: {mtime_str}")
                print(f"   파일 내 video_id: {video_id_in_file}")
                print(f"   프레임 수: {frame_count}개")
                
                # 첫 번째 프레임의 캡션 샘플
                frames = data.get('frame', [])
                if frames:
                    first_caption = frames[0].get('caption', '')[:100]
                    print(f"   첫 프레임 캡션: {first_caption}...")
        except Exception as e:
            print(f"   ❌ 파일 읽기 실패: {e}")
    
    print("\n" + "=" * 80)
    print("Detection DB 파일 목록:")
    print("=" * 80)
    for det_file in sorted(detection_db_files):
        basename = os.path.basename(det_file)
        mtime = os.path.getmtime(det_file)
        from datetime import datetime
        mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n📄 {basename}")
        print(f"   수정 시간: {mtime_str}")
    
    print("\n" + "=" * 80)
    print("데이터베이스의 Video 모델:")
    print("=" * 80)
    videos = Video.objects.all().order_by('-id')
    for video in videos:
        print(f"\n🎥 Video ID: {video.id}")
        print(f"   filename: {video.filename}")
        print(f"   original_name: {video.original_name}")
        print(f"   analysis_json_path: {video.analysis_json_path}")
        
        # 매칭되는 파일 찾기
        print(f"\n   🔍 매칭되는 파일:")
        
        # 1. filename 기반
        if video.filename:
            filename_base = os.path.splitext(video.filename)[0]
            test_paths = [
                os.path.join(media_dir, f"{filename_base}-meta_db.json"),
                os.path.join(media_dir, f"{video.filename}-meta_db.json"),
            ]
            for test_path in test_paths:
                if os.path.exists(test_path):
                    print(f"      ✅ {os.path.basename(test_path)} (filename 기반)")
        
        # 2. original_name 기반
        if video.original_name:
            original_base = os.path.splitext(video.original_name)[0]
            test_path = os.path.join(media_dir, f"{original_base}-meta_db.json")
            if os.path.exists(test_path):
                print(f"      ✅ {os.path.basename(test_path)} (original_name 기반)")
        
        # 3. analysis_json_path 기반
        if video.analysis_json_path:
            try:
                analysis_file = os.path.join(media_dir, video.analysis_json_path)
                if os.path.exists(analysis_file):
                    with open(analysis_file, 'r', encoding='utf-8') as f:
                        analysis_data = json.load(f)
                        video_id_in_json = analysis_data.get('video_summary', {}).get('video_id')
                        if video_id_in_json:
                            test_path = os.path.join(media_dir, f"{video_id_in_json}-meta_db.json")
                            if os.path.exists(test_path):
                                print(f"      ✅ {os.path.basename(test_path)} (analysis_json 기반)")
            except Exception as e:
                print(f"      ⚠️ analysis_json 읽기 실패: {e}")

if __name__ == '__main__':
    check_video_files()

