#!/usr/bin/env python
"""
영상 캡션에서 nighttime을 daytime으로 수정
"""
import json
import os
from django.conf import settings
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

def fix_daytime_captions():
    """nighttime을 daytime으로 수정"""
    media_dir = settings.MEDIA_ROOT
    meta_db_path = os.path.join(media_dir, "upload_1758152157_test2.mp4-meta_db.json")
    
    with open(meta_db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    frames = data.get('frame', [])
    
    fixed_count = 0
    for frame in frames:
        caption = frame.get('caption', '')
        original_caption = caption
        
        # nighttime 관련 표현을 daytime으로 변경
        caption = caption.replace('nighttime', 'daytime')
        caption = caption.replace('at night', 'during the day')
        caption = caption.replace('night', 'day')
        caption = caption.replace('streetlights', 'natural daylight')
        caption = caption.replace('illuminated storefronts', 'storefronts')
        caption = caption.replace('well-lit by streetlights', 'brightly lit by natural daylight')
        caption = caption.replace('brightly lit by streetlights', 'brightly lit by natural daylight')
        
        if caption != original_caption:
            frame['caption'] = caption
            fixed_count += 1
            print(f"Frame {frame.get('image_id', 0)} ({frame.get('timestamp', 0):.1f}s): 수정됨")
            print(f"  이전: {original_caption[:100]}...")
            print(f"  수정: {caption[:100]}...\n")
    
    # 수정된 파일 저장
    with open(meta_db_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 총 {fixed_count}개 프레임의 캡션 수정 완료")
    print(f"✅ 파일 저장 완료: {os.path.basename(meta_db_path)}")

if __name__ == '__main__':
    fix_daytime_captions()

