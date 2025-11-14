#!/usr/bin/env python
"""
초록색 옷 언급을 더 명확하게 수정 ("in green" -> "in green clothing")
"""
import json
import os
from django.conf import settings
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

def make_green_explicit():
    """초록색 옷 언급을 더 명확하게 수정"""
    media_dir = settings.MEDIA_ROOT
    meta_db_path = os.path.join(media_dir, "upload_1758152157_test2.mp4-meta_db.json")
    
    with open(meta_db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    frames = data.get('frame', [])
    
    fixed_count = 0
    for frame in frames:
        caption = frame.get('caption', '')
        original_caption = caption
        
        # "in green" -> "in green clothing"으로 변경 (더 명확하게)
        if "in green" in caption and "in green clothing" not in caption:
            # "a young man in green" -> "a young man in green clothing"
            caption = caption.replace("in green,", "in green clothing,")
            caption = caption.replace("in green.", "in green clothing.")
            caption = caption.replace("in green ", "in green clothing ")
            # 마지막에 있는 경우
            if caption.endswith("in green"):
                caption = caption.replace("in green", "in green clothing")
        
        # "wearing green" -> "wearing green clothing"으로 변경
        if "wearing green" in caption and "wearing green clothing" not in caption:
            caption = caption.replace("wearing green,", "wearing green clothing,")
            caption = caption.replace("wearing green.", "wearing green clothing.")
            caption = caption.replace("wearing green ", "wearing green clothing ")
            if caption.endswith("wearing green"):
                caption = caption.replace("wearing green", "wearing green clothing")
        
        # "wearing green and" -> "wearing green clothing and" (다른 색상과 함께)
        caption = caption.replace("wearing green and", "wearing green clothing and")
        
        if caption != original_caption:
            frame['caption'] = caption
            fixed_count += 1
            print(f"Frame {frame.get('image_id', 0)} ({frame.get('timestamp', 0):.1f}s): 수정")
            print(f"  수정: {caption[:200]}...\n")
    
    # 수정된 파일 저장
    with open(meta_db_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 총 {fixed_count}개 프레임의 캡션 수정 완료")
    print(f"✅ 파일 저장 완료: {os.path.basename(meta_db_path)}")

if __name__ == '__main__':
    make_green_explicit()

