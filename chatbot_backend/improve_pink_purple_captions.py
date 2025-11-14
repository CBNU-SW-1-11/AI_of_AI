#!/usr/bin/env python
"""
분홍색과 보라색 옷을 입은 사람이 명확히 언급되도록 캡션 개선
"""
import json
import os
from django.conf import settings
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

def improve_pink_purple_captions():
    """각 프레임에서 분홍색과 보라색 옷을 입은 사람을 명확히 언급"""
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
        pink_count = 0
        purple_count = 0
        pink_details = []
        purple_details = []
        
        for person in persons:
            attrs = person.get('attributes', {})
            clothing = attrs.get('clothing', {})
            upper_color = clothing.get('upper_color', '').lower()
            
            if 'pink' in upper_color:
                pink_count += 1
                gender = attrs.get('gender', 'person')
                age = attrs.get('age', 'adult')
                age_desc = "young" if age == "young_adult" else "middle-aged" if age == "middle_aged" else "elderly" if age == "elderly" else ""
                gender_desc = "man" if gender == "man" else "woman" if gender == "woman" else "person"
                desc = f"{age_desc} {gender_desc}" if age_desc else gender_desc
                pink_details.append(desc)
            
            if 'purple' in upper_color:
                purple_count += 1
                gender = attrs.get('gender', 'person')
                age = attrs.get('age', 'adult')
                age_desc = "young" if age == "young_adult" else "middle-aged" if age == "middle_aged" else "elderly" if age == "elderly" else ""
                gender_desc = "man" if gender == "man" else "woman" if gender == "woman" else "person"
                desc = f"{age_desc} {gender_desc}" if age_desc else gender_desc
                purple_details.append(desc)
        
        # 캡션 수정
        caption = frame.get('caption', '')
        original_caption = caption
        
        # 분홍색과 보라색 정보가 명확히 언급되도록 수정
        if pink_count > 0 or purple_count > 0:
            # 기존 캡션 확인
            has_pink_explicit = 'one person in pink' in caption.lower() or 'person in pink clothing' in caption.lower()
            has_purple_explicit = 'one person in purple' in caption.lower() or 'person in purple clothing' in caption.lower()
            
            # 분홍색과 보라색이 모두 있으면 명확히 언급
            if pink_count > 0 and purple_count > 0:
                if not (has_pink_explicit and has_purple_explicit):
                    # 명확한 언급 추가
                    pink_text = f"one person in pink clothing" if pink_count == 1 else f"{pink_count} people in pink clothing"
                    purple_text = f"one person in purple clothing" if purple_count == 1 else f"{purple_count} people in purple clothing"
                    
                    # 캡션 끝에 추가
                    if "Notably" not in caption:
                        caption += f" Notably, {pink_text} and {purple_text} are visible in the scene."
                    else:
                        # 기존 Notably 부분을 더 명확하게 수정
                        if "one person in pink" not in caption or "one person in purple" not in caption:
                            caption = caption.replace("Notably,", f"Notably, {pink_text} and {purple_text} are visible in the scene.")
            
            # 분홍색만 있는 경우
            elif pink_count > 0 and not has_pink_explicit:
                pink_text = f"one person in pink clothing" if pink_count == 1 else f"{pink_count} people in pink clothing"
                if "Notably" not in caption:
                    caption += f" Notably, {pink_text} is visible in the scene."
            
            # 보라색만 있는 경우
            elif purple_count > 0 and not has_purple_explicit:
                purple_text = f"one person in purple clothing" if purple_count == 1 else f"{purple_count} people in purple clothing"
                if "Notably" not in caption:
                    caption += f" Notably, {purple_text} is visible in the scene."
        
        if caption != original_caption:
            frame['caption'] = caption
            fixed_count += 1
            print(f"Frame {frame.get('image_id', 0)} ({frame.get('timestamp', 0):.1f}s):")
            print(f"  분홍색: {pink_count}명, 보라색: {purple_count}명")
            print(f"  수정: {caption[-150:]}\n")
    
    # 수정된 파일 저장
    with open(meta_db_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 총 {fixed_count}개 프레임의 캡션 수정 완료")
    print(f"✅ 파일 저장 완료: {os.path.basename(meta_db_path)}")

if __name__ == '__main__':
    improve_pink_purple_captions()

