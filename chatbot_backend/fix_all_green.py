#!/usr/bin/env python
"""
모든 "in green" 표현을 "in green clothing"으로 변경
"""
import json
import os
import re
from django.conf import settings
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

def fix_all_green():
    """모든 "in green" 표현을 "in green clothing"으로 변경"""
    media_dir = settings.MEDIA_ROOT
    meta_db_path = os.path.join(media_dir, "upload_1758152157_test2.mp4-meta_db.json")
    
    with open(meta_db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    frames = data.get('frame', [])
    
    fixed_count = 0
    for frame in frames:
        caption = frame.get('caption', '')
        original_caption = caption
        
        # "in green" -> "in green clothing" (정규식으로 정확하게)
        # "a young man in green" -> "a young man in green clothing"
        # "in green," -> "in green clothing,"
        # "in green." -> "in green clothing."
        # "in green " -> "in green clothing "
        
        # "in green"이 "in green clothing"이 아닌 경우만 변경
        caption = re.sub(r'\bin green\b(?! clothing)', 'in green clothing', caption)
        
        if caption != original_caption:
            frame['caption'] = caption
            fixed_count += 1
            print(f"Frame {frame.get('image_id', 0)} ({frame.get('timestamp', 0):.1f}s): 수정")
            print(f"  이전: {original_caption[:150]}...")
            print(f"  수정: {caption[:150]}...\n")
    
    # 수정된 파일 저장
    with open(meta_db_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 총 {fixed_count}개 프레임의 캡션 수정 완료")
    print(f"✅ 파일 저장 완료: {os.path.basename(meta_db_path)}")

if __name__ == '__main__':
    fix_all_green()

