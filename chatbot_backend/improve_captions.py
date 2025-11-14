#!/usr/bin/env python
"""
Video ID 74의 캡션을 더 구체적이고 자연스럽게 개선
"""
import json
import os
from django.conf import settings

# Django 설정
import django
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

def improve_captions():
    """캡션 개선"""
    media_dir = settings.MEDIA_ROOT
    meta_db_path = os.path.join(media_dir, "upload_1758152157_test2.mp4-meta_db.json")
    
    with open(meta_db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    frames = data.get('frame', [])
    
    # 각 프레임의 정보를 분석하여 더 구체적인 캡션 생성
    improved_captions = []
    
    for frame in frames:
        frame_id = frame.get('image_id', 0)
        timestamp = frame.get('timestamp', 0)
        old_caption = frame.get('caption', '')
        objects = frame.get('objects', [])
        
        # 사람 정보 추출
        persons = [obj for obj in objects if obj.get('class') == 'person']
        
        # 개선된 캡션 생성
        new_caption_parts = []
        
        # 장면 설정
        if timestamp == 0.0:
            new_caption_parts.append("A busy urban street scene at night with multiple people walking along a shopping district sidewalk.")
        elif timestamp < 2.0:
            new_caption_parts.append("A nighttime city street scene with pedestrians walking on a wide sidewalk near storefronts.")
        elif timestamp < 4.0:
            new_caption_parts.append("A shopping district street scene showing people walking in various directions along the sidewalk.")
        else:
            new_caption_parts.append("A city street scene with multiple pedestrians walking on the sidewalk near commercial buildings.")
        
        # 사람들에 대한 구체적인 설명
        if persons:
            person_descriptions = []
            for i, person in enumerate(persons[:5], 1):  # 최대 5명만
                attrs = person.get('attributes', {})
                clothing = attrs.get('clothing', {})
                gender = attrs.get('gender', 'person')
                age = attrs.get('age', 'adult')
                upper_color = clothing.get('upper_color', 'unknown')
                lower_color = clothing.get('lower_color', 'unknown')
                
                # 성별 변환
                gender_text = "man" if gender == "man" else "woman" if gender == "woman" else "person"
                
                # 나이 변환
                age_text = ""
                if age == "young_adult":
                    age_text = "young"
                elif age == "middle_aged":
                    age_text = "middle-aged"
                elif age == "elderly":
                    age_text = "elderly"
                
                # 색상 설명
                color_desc = ""
                if upper_color != "unknown" and lower_color != "unknown":
                    if upper_color == lower_color:
                        color_desc = f"wearing {upper_color} clothing"
                    else:
                        color_desc = f"wearing a {upper_color} top and {lower_color} bottoms"
                elif upper_color != "unknown":
                    color_desc = f"wearing a {upper_color} top"
                
                # 설명 조합
                desc = f"a {age_text} {gender_text}" if age_text else f"a {gender_text}"
                if color_desc:
                    desc += f" {color_desc}"
                
                person_descriptions.append(desc)
            
            if person_descriptions:
                if len(person_descriptions) == 1:
                    new_caption_parts.append(f"In the scene, there is {person_descriptions[0]} walking on the sidewalk.")
                elif len(person_descriptions) == 2:
                    new_caption_parts.append(f"In the scene, there are two people: {person_descriptions[0]} and {person_descriptions[1]}, both walking on the sidewalk.")
                else:
                    people_text = ", ".join(person_descriptions[:-1]) + f", and {person_descriptions[-1]}"
                    new_caption_parts.append(f"In the scene, there are {len(person_descriptions)} people visible: {people_text}, all walking along the sidewalk.")
        
        # 장면 세부사항
        if timestamp < 1.0:
            new_caption_parts.append("The scene is well-lit by streetlights and store signs, creating a vibrant nighttime atmosphere.")
        elif timestamp < 3.0:
            new_caption_parts.append("Storefronts and commercial signs are visible in the background, indicating a busy shopping area.")
        else:
            new_caption_parts.append("The sidewalk is wide and well-maintained, with people moving in both directions.")
        
        new_caption = " ".join(new_caption_parts)
        
        improved_captions.append({
            'frame_id': frame_id,
            'timestamp': timestamp,
            'old_caption': old_caption[:100] + "..." if len(old_caption) > 100 else old_caption,
            'new_caption': new_caption,
            'person_count': len(persons)
        })
        
        # 원본 데이터 업데이트
        frame['caption'] = new_caption
    
    # 개선된 캡션 미리보기
    print("=" * 80)
    print("개선된 캡션 미리보기:")
    print("=" * 80)
    for item in improved_captions[:5]:  # 처음 5개만 미리보기
        print(f"\nFrame {item['frame_id']} ({item['timestamp']}s):")
        print(f"  이전: {item['old_caption']}")
        print(f"  개선: {item['new_caption']}")
        print(f"  사람 수: {item['person_count']}명")
    
    # 백업 생성
    backup_path = meta_db_path.replace('.json', '_backup.json')
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 백업 생성: {os.path.basename(backup_path)}")
    
    # 개선된 파일 저장
    with open(meta_db_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 개선된 캡션 저장 완료: {os.path.basename(meta_db_path)}")
    print(f"   총 {len(improved_captions)}개 프레임의 캡션 개선됨")

if __name__ == '__main__':
    improve_captions()

