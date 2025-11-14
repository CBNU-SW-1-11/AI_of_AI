#!/usr/bin/env python
"""
캡션의 문법 오류 수정 (is/are)
"""
import json
import os
from django.conf import settings
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

def fix_grammar_captions():
    """캡션의 문법 오류 수정"""
    media_dir = settings.MEDIA_ROOT
    meta_db_path = os.path.join(media_dir, "upload_1758152157_test2.mp4-meta_db.json")
    
    with open(meta_db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    frames = data.get('frame', [])
    
    fixed_count = 0
    for frame in frames:
        caption = frame.get('caption', '')
        original_caption = caption
        
        # "and ... is visible" -> "and ... are visible" 수정
        if "and" in caption and "is visible in the scene" in caption:
            # 여러 사람이 언급된 경우 "are"로 변경
            if "one person" in caption and caption.count("one person") > 1:
                caption = caption.replace("is visible in the scene", "are visible in the scene")
            elif "people" in caption or "2 people" in caption or "3 people" in caption or "4 people" in caption or "5 people" in caption:
                caption = caption.replace("is visible in the scene", "are visible in the scene")
        
        # "Notably, ... and ... and ... is" -> "are" 수정
        if "Notably," in caption and "and" in caption and "is visible" in caption:
            # 여러 항목이 "and"로 연결된 경우
            notably_part = caption.split("Notably,")[1].split(".")[0] if "Notably," in caption else ""
            if notably_part.count("and") >= 1:
                caption = caption.replace("is visible in the scene", "are visible in the scene")
        
        if caption != original_caption:
            frame['caption'] = caption
            fixed_count += 1
            print(f"Frame {frame.get('image_id', 0)} ({frame.get('timestamp', 0):.1f}s): 문법 수정")
            print(f"  수정: {caption[-150:]}\n")
    
    # 수정된 파일 저장
    with open(meta_db_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 총 {fixed_count}개 프레임의 문법 수정 완료")
    print(f"✅ 파일 저장 완료: {os.path.basename(meta_db_path)}")

if __name__ == '__main__':
    fix_grammar_captions()

