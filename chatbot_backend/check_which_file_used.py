#!/usr/bin/env python
"""
현재 Video ID 74에서 실제로 사용되는 파일 확인
"""
import os
import json
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

from chat.models import Video
from django.conf import settings

video_id = 74
video = Video.objects.get(id=video_id)

print(f"🎥 Video ID: {video_id}")
print(f"   filename: {video.filename}")
print(f"   original_name: {video.original_name}")
print(f"   analysis_json_path: {video.analysis_json_path}\n")

media_dir = settings.MEDIA_ROOT
meta_db_path = None

# 1순위: analysis_json_path에서 원본 파일명 추출
if video.analysis_json_path:
    analysis_file = os.path.join(media_dir, video.analysis_json_path)
    if os.path.exists(analysis_file):
        try:
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
                video_id_in_json = analysis_data.get('video_summary', {}).get('video_id')
                print(f"1순위: analysis_json에서 video_id 추출 시도")
                print(f"   video_id_in_json: {video_id_in_json}")
                if video_id_in_json:
                    test_path = os.path.join(media_dir, f"{video_id_in_json}-meta_db.json")
                    if os.path.exists(test_path):
                        meta_db_path = test_path
                        print(f"   ✅ 발견: {os.path.basename(meta_db_path)}")
                    else:
                        print(f"   ❌ 파일 없음: {os.path.basename(test_path)}")
                else:
                    print(f"   ❌ video_id 없음")
        except Exception as e:
            print(f"   ❌ 오류: {e}")

# 2순위: filename에서 타임스탬프 제거
if not meta_db_path and video.filename:
    print(f"\n2순위: filename에서 타임스탬프 제거 시도")
    filename_base = os.path.splitext(video.filename)[0]
    print(f"   filename_base: {filename_base}")
    
    if filename_base.startswith('upload_'):
        if '_upload_' in filename_base:
            parts = filename_base.split('_upload_', 1)
            if len(parts) == 2:
                # 패턴 1: upload_{timestamp}_upload_{original} -> upload_{original}
                possible_original_with_ext = f"upload_{parts[1]}.mp4"
                test_path = os.path.join(media_dir, f"{possible_original_with_ext}-meta_db.json")
                print(f"   패턴1 시도: {possible_original_with_ext}-meta_db.json")
                if os.path.exists(test_path):
                    meta_db_path = test_path
                    print(f"   ✅ 발견: {os.path.basename(meta_db_path)}")
                else:
                    print(f"   ❌ 파일 없음")
                
                if not meta_db_path:
                    possible_original_no_ext = f"upload_{parts[1]}"
                    test_path = os.path.join(media_dir, f"{possible_original_no_ext}-meta_db.json")
                    print(f"   패턴1-2 시도: {possible_original_no_ext}-meta_db.json")
                    if os.path.exists(test_path):
                        meta_db_path = test_path
                        print(f"   ✅ 발견: {os.path.basename(meta_db_path)}")
                    else:
                        print(f"   ❌ 파일 없음")

# 3순위: original_name
if not meta_db_path and video.original_name:
    print(f"\n3순위: original_name 사용")
    original_base = os.path.splitext(video.original_name)[0]
    test_path = os.path.join(media_dir, f"{original_base}-meta_db.json")
    print(f"   시도: {original_base}-meta_db.json")
    if os.path.exists(test_path):
        meta_db_path = test_path
        print(f"   ✅ 발견: {os.path.basename(meta_db_path)}")
    else:
        print(f"   ❌ 파일 없음")

# 4순위: 가장 최근 파일
if not meta_db_path:
    print(f"\n4순위: 가장 최근 파일 사용")
    import glob
    meta_db_files = glob.glob(os.path.join(media_dir, "*-meta_db.json"))
    if meta_db_files:
        meta_db_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        meta_db_path = meta_db_files[0]
        print(f"   ✅ 발견: {os.path.basename(meta_db_path)}")

if meta_db_path:
    print(f"\n✅ 최종 사용 파일: {os.path.basename(meta_db_path)}")
    with open(meta_db_path, 'r', encoding='utf-8') as f:
        meta_data = json.load(f)
        print(f"   프레임 수: {len(meta_data.get('frame', []))}개")
        if meta_data.get('frame'):
            first_caption = meta_data['frame'][0].get('caption', '')[:150]
            print(f"   첫 프레임 캡션: {first_caption}...")
else:
    print(f"\n❌ 사용할 파일을 찾을 수 없습니다.")

