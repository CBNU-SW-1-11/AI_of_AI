#!/usr/bin/env python
"""
캡션의 문법 오류 올바르게 수정 (단수/복수 일치)
"""
import json
import os
from django.conf import settings
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

def fix_grammar_correct():
    """캡션의 문법 오류 올바르게 수정"""
    media_dir = settings.MEDIA_ROOT
    meta_db_path = os.path.join(media_dir, "upload_1758152157_test2.mp4-meta_db.json")
    
    with open(meta_db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    frames = data.get('frame', [])
    
    fixed_count = 0
    for frame in frames:
        caption = frame.get('caption', '')
        original_caption = caption
        
        # "Notably, ... are visible" 부분 확인 및 수정
        if "Notably," in caption:
            notably_part = caption.split("Notably,")[1].split(".")[0] if "Notably," in caption else ""
            
            # "one person"이 하나만 있으면 "is", 여러 개 있거나 "people"이 있으면 "are"
            one_person_count = notably_part.count("one person")
            has_people = "people" in notably_part or "2 people" in notably_part or "3 people" in notably_part or "4 people" in notably_part or "5 people" in notably_part
            
            if one_person_count == 1 and not has_people:
                # 단수: "one person ... is visible"
                caption = caption.replace("one person in", "one person in")
                caption = caption.replace("one person in green clothing are visible", "one person in green clothing is visible")
                caption = caption.replace("one person in pink clothing are visible", "one person in pink clothing is visible")
                caption = caption.replace("one person in purple clothing are visible", "one person in purple clothing is visible")
            elif one_person_count > 1 or has_people:
                # 복수: "are visible"
                caption = caption.replace("one person in green clothing is visible", "one person in green clothing are visible")
                caption = caption.replace("one person in pink clothing is visible", "one person in pink clothing are visible")
                caption = caption.replace("one person in purple clothing is visible", "one person in purple clothing are visible")
            
            # "and"로 연결된 경우는 항상 복수
            if "and" in notably_part and "is visible" in caption:
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
    fix_grammar_correct()

