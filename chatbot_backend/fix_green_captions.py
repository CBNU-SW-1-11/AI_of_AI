#!/usr/bin/env python
"""
초록색 옷을 입은 사람이 명확히 언급되도록 캡션 수정
"""
import json
import os
from django.conf import settings
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

def fix_green_captions():
    """각 프레임에서 초록색 옷을 입은 사람을 명확히 언급"""
    media_dir = settings.MEDIA_ROOT
    meta_db_path = os.path.join(media_dir, "upload_1758152157_test2.mp4-meta_db.json")
    
    with open(meta_db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    frames = data.get('frame', [])
    
    fixed_count = 0
    for frame in frames:
        objects = frame.get('objects', [])
        persons = [obj for obj in objects if obj.get('class') == 'person']
        
        # 초록색 옷을 입은 사람 찾기
        green_count = 0
        green_details = []
        
        for person in persons:
            attrs = person.get('attributes', {})
            clothing = attrs.get('clothing', {})
            upper_color = clothing.get('upper_color', '').lower()
            
            # green이 포함된 경우 (green, light green 등)
            if 'green' in upper_color:
                green_count += 1
                gender = attrs.get('gender', 'person')
                age = attrs.get('age', 'adult')
                age_desc = "young" if age == "young_adult" else "middle-aged" if age == "middle_aged" else "elderly" if age == "elderly" else ""
                gender_desc = "man" if gender == "man" else "woman" if gender == "woman" else "person"
                desc = f"{age_desc} {gender_desc}" if age_desc else gender_desc
                green_details.append(desc)
        
        # 캡션 수정
        caption = frame.get('caption', '')
        original_caption = caption
        
        # 초록색 옷을 입은 사람이 있으면 명확히 언급
        if green_count > 0:
            # 기존 캡션에서 초록색 언급 확인
            has_green_explicit = 'one person in green' in caption.lower() or 'person in green clothing' in caption.lower() or 'people in green clothing' in caption.lower()
            has_green_mention = 'in green' in caption.lower() or 'wearing green' in caption.lower() or 'green clothing' in caption.lower()
            
            # 초록색이 언급되어 있지만 명확하지 않은 경우
            if has_green_mention and not has_green_explicit:
                # 더 명확하게 언급 추가
                green_text = f"one person in green clothing" if green_count == 1 else f"{green_count} people in green clothing"
                
                # 캡션 끝에 추가
                if "Notably" not in caption:
                    caption += f" Notably, {green_text} is visible in the scene." if green_count == 1 else f" Notably, {green_text} are visible in the scene."
                else:
                    # 기존 Notably 부분에 추가
                    if "green clothing" not in caption:
                        caption = caption.replace("Notably,", f"Notably, {green_text} and")
                        caption = caption.replace("and are visible", "are visible")
            
            # 초록색이 전혀 언급되지 않은 경우
            elif not has_green_mention:
                green_text = f"one person in green clothing" if green_count == 1 else f"{green_count} people in green clothing"
                if "Notably" not in caption:
                    caption += f" Notably, {green_text} is visible in the scene." if green_count == 1 else f" Notably, {green_text} are visible in the scene."
                else:
                    if "green clothing" not in caption:
                        caption = caption.replace("Notably,", f"Notably, {green_text} and")
                        caption = caption.replace("and are visible", "are visible")
        
        if caption != original_caption:
            frame['caption'] = caption
            fixed_count += 1
            print(f"Frame {frame.get('image_id', 0)} ({frame.get('timestamp', 0):.1f}s):")
            print(f"  초록색: {green_count}명")
            print(f"  수정: {caption[-150:]}\n")
    
    # 수정된 파일 저장
    with open(meta_db_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 총 {fixed_count}개 프레임의 캡션 수정 완료")
    print(f"✅ 파일 저장 완료: {os.path.basename(meta_db_path)}")

if __name__ == '__main__':
    fix_green_captions()

