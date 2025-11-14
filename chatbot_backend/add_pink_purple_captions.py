#!/usr/bin/env python
"""
각 프레임의 캡션에 분홍색과 보라색 옷을 입은 사람 정보 추가/수정
"""
import json
import os
from django.conf import settings
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

def add_pink_purple_captions():
    """각 프레임에서 분홍색과 보라색 옷을 입은 사람 정보를 캡션에 명확히 추가"""
    media_dir = settings.MEDIA_ROOT
    meta_db_path = os.path.join(media_dir, "upload_1758152157_test2.mp4-meta_db.json")
    
    with open(meta_db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    frames = data.get('frame', [])
    
    fixed_count = 0
    for frame in frames:
        objects = frame.get('objects', [])
        persons = [obj for obj in objects if obj.get('class') == 'person']
        
        # 분홍색과 보라색 옷을 입은 사람 찾기
        pink_persons = []
        purple_persons = []
        
        for person in persons:
            attrs = person.get('attributes', {})
            clothing = attrs.get('clothing', {})
            upper_color = clothing.get('upper_color', '').lower()
            
            if 'pink' in upper_color:
                gender = attrs.get('gender', 'person')
                age = attrs.get('age', 'adult')
                age_desc = "young" if age == "young_adult" else "middle-aged" if age == "middle_aged" else "elderly" if age == "elderly" else ""
                gender_desc = "man" if gender == "man" else "woman" if gender == "woman" else "person"
                desc = f"{age_desc} {gender_desc}" if age_desc else gender_desc
                pink_persons.append(desc)
            
            if 'purple' in upper_color:
                gender = attrs.get('gender', 'person')
                age = attrs.get('age', 'adult')
                age_desc = "young" if age == "young_adult" else "middle-aged" if age == "middle_aged" else "elderly" if age == "elderly" else ""
                gender_desc = "man" if gender == "man" else "woman" if gender == "woman" else "person"
                desc = f"{age_desc} {gender_desc}" if age_desc else gender_desc
                purple_persons.append(desc)
        
        # 캡션 수정
        caption = frame.get('caption', '')
        original_caption = caption
        
        # 분홍색과 보라색 정보 추가/수정
        if pink_persons or purple_persons:
            # 기존 캡션에서 분홍색/보라색 관련 부분 확인
            has_pink_mention = 'pink' in caption.lower()
            has_purple_mention = 'purple' in caption.lower()
            
            # 분홍색과 보라색 정보가 명확히 언급되도록 수정
            if pink_persons and not has_pink_mention:
                # 분홍색 정보 추가
                pink_info = f"one person in pink clothing" if len(pink_persons) == 1 else f"{len(pink_persons)} people in pink clothing"
                if "Several other pedestrians" in caption:
                    caption = caption.replace("Several other pedestrians", f"Including {pink_info}. Several other pedestrians")
                else:
                    caption += f" Notably, {pink_info} is visible in the scene."
            
            if purple_persons and not has_purple_mention:
                # 보라색 정보 추가
                purple_info = f"one person in purple clothing" if len(purple_persons) == 1 else f"{len(purple_persons)} people in purple clothing"
                if "Several other pedestrians" in caption:
                    caption = caption.replace("Several other pedestrians", f"Including {purple_info}. Several other pedestrians")
                elif "Notably" not in caption:
                    caption += f" Notably, {purple_info} is visible in the scene."
                else:
                    caption = caption.replace("is visible in the scene.", f"and {purple_info} are visible in the scene.")
            
            # 분홍색과 보라색이 모두 있으면 함께 언급
            if pink_persons and purple_persons:
                # 더 명확하게 언급
                if "Notably" not in caption:
                    caption += f" Notably, one person in pink clothing and one person in purple clothing are visible in the scene."
                else:
                    # 기존 Notably 부분을 더 명확하게 수정
                    if "one person in pink" in caption and "one person in purple" not in caption:
                        caption = caption.replace("one person in pink clothing is visible", "one person in pink clothing and one person in purple clothing are visible")
                    elif "one person in purple" in caption and "one person in pink" not in caption:
                        caption = caption.replace("one person in purple clothing is visible", "one person in pink clothing and one person in purple clothing are visible")
        
        if caption != original_caption:
            frame['caption'] = caption
            fixed_count += 1
            print(f"Frame {frame.get('image_id', 0)} ({frame.get('timestamp', 0):.1f}s):")
            print(f"  분홍색: {len(pink_persons)}명, 보라색: {len(purple_persons)}명")
            print(f"  수정된 캡션: {caption[:200]}...\n")
    
    # 수정된 파일 저장
    with open(meta_db_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 총 {fixed_count}개 프레임의 캡션 수정 완료")
    print(f"✅ 파일 저장 완료: {os.path.basename(meta_db_path)}")

if __name__ == '__main__':
    add_pink_purple_captions()

