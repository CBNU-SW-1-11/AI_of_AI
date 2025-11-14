#!/usr/bin/env python
"""
Video ID 74의 캡션을 더 자연스럽고 구체적으로 개선 (버전 2)
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

def get_color_name(color):
    """색상 이름을 더 자연스럽게 변환"""
    color_map = {
        'cyan': 'light blue',
        'yellow': 'yellow',
        'green': 'green',
        'red': 'red',
        'orange': 'orange',
        'blue': 'blue',
        'pink': 'pink',
        'purple': 'purple',
        'black': 'black',
        'white': 'white',
        'gray': 'gray',
        'brown': 'brown'
    }
    return color_map.get(color.lower(), color)

def improve_captions_v2():
    """캡션 개선 - 더 자연스럽고 구체적으로"""
    media_dir = settings.MEDIA_ROOT
    meta_db_path = os.path.join(media_dir, "upload_1758152157_test2.mp4-meta_db.json")
    
    with open(meta_db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    frames = data.get('frame', [])
    
    # 각 프레임별로 더 구체적이고 자연스러운 캡션 생성
    improved_captions = []
    
    for idx, frame in enumerate(frames):
        frame_id = frame.get('image_id', idx + 1)
        timestamp = frame.get('timestamp', 0)
        objects = frame.get('objects', [])
        
        # 사람 정보 추출 및 정리
        persons = [obj for obj in objects if obj.get('class') == 'person']
        
        # 사람들을 색상별로 그룹화
        color_groups = {}
        for person in persons:
            attrs = person.get('attributes', {})
            clothing = attrs.get('clothing', {})
            upper_color = get_color_name(clothing.get('upper_color', 'unknown'))
            gender = attrs.get('gender', 'person')
            age = attrs.get('age', 'adult')
            
            if upper_color not in color_groups:
                color_groups[upper_color] = []
            
            age_desc = ""
            if age == "young_adult":
                age_desc = "young"
            elif age == "middle_aged":
                age_desc = "middle-aged"
            elif age == "elderly":
                age_desc = "elderly"
            
            gender_desc = "man" if gender == "man" else "woman" if gender == "woman" else "person"
            if age_desc:
                color_groups[upper_color].append(f"{age_desc} {gender_desc}")
            else:
                color_groups[upper_color].append(gender_desc)
        
        # 자연스러운 캡션 생성
        caption_parts = []
        
        # 기본 장면 설명
        if timestamp < 1.0:
            caption_parts.append("A vibrant nighttime street scene in a shopping district.")
        elif timestamp < 2.0:
            caption_parts.append("A busy city sidewalk at night with pedestrians walking near storefronts.")
        elif timestamp < 4.0:
            caption_parts.append("A shopping district street scene showing people walking along a wide sidewalk.")
        else:
            caption_parts.append("A city street scene with multiple pedestrians walking on the sidewalk.")
        
        # 사람들에 대한 자연스러운 설명
        if persons:
            total_people = len(persons)
            
            # 색상별로 묘사
            color_descriptions = []
            for color, people_list in color_groups.items():
                if color != 'unknown' and people_list:
                    count = len(people_list)
                    if count == 1:
                        color_descriptions.append(f"one person in {color} clothing")
                    elif count == 2:
                        color_descriptions.append(f"two people in {color} clothing")
                    else:
                        color_descriptions.append(f"{count} people in {color} clothing")
            
            if color_descriptions:
                if len(color_descriptions) == 1:
                    caption_parts.append(f"The scene shows {color_descriptions[0]} walking on the sidewalk.")
                elif len(color_descriptions) == 2:
                    caption_parts.append(f"The scene shows {color_descriptions[0]} and {color_descriptions[1]} walking on the sidewalk.")
                else:
                    people_desc = ", ".join(color_descriptions[:-1]) + f", and {color_descriptions[-1]}"
                    caption_parts.append(f"The scene shows {people_desc} walking on the sidewalk.")
            
            # 구체적인 인물 묘사 (주요 인물 2-3명)
            if total_people > 0:
                main_persons = persons[:3]  # 최대 3명만 상세 묘사
                person_details = []
                
                for person in main_persons:
                    attrs = person.get('attributes', {})
                    clothing = attrs.get('clothing', {})
                    upper_color = get_color_name(clothing.get('upper_color', 'unknown'))
                    lower_color = get_color_name(clothing.get('lower_color', 'unknown'))
                    gender = attrs.get('gender', 'person')
                    age = attrs.get('age', 'adult')
                    
                    age_desc = ""
                    if age == "young_adult":
                        age_desc = "young"
                    elif age == "middle_aged":
                        age_desc = "middle-aged"
                    elif age == "elderly":
                        age_desc = "elderly"
                    
                    gender_desc = "man" if gender == "man" else "woman" if gender == "woman" else "person"
                    
                    if upper_color != 'unknown' and lower_color != 'unknown':
                        if upper_color == lower_color:
                            detail = f"a {age_desc} {gender_desc} in {upper_color} clothing" if age_desc else f"a {gender_desc} in {upper_color} clothing"
                        else:
                            detail = f"a {age_desc} {gender_desc} wearing a {upper_color} top with {lower_color} bottoms" if age_desc else f"a {gender_desc} wearing a {upper_color} top with {lower_color} bottoms"
                    elif upper_color != 'unknown':
                        detail = f"a {age_desc} {gender_desc} in a {upper_color} top" if age_desc else f"a {gender_desc} in a {upper_color} top"
                    else:
                        detail = f"a {age_desc} {gender_desc}" if age_desc else f"a {gender_desc}"
                    
                    person_details.append(detail)
                
                if person_details:
                    if len(person_details) == 1:
                        caption_parts.append(f"Visible in the frame is {person_details[0]}.")
                    elif len(person_details) == 2:
                        caption_parts.append(f"Visible in the frame are {person_details[0]} and {person_details[1]}.")
                    else:
                        details_text = ", ".join(person_details[:-1]) + f", and {person_details[-1]}"
                        caption_parts.append(f"Visible in the frame are {details_text}.")
        
        # 장면 세부사항
        if timestamp < 1.5:
            caption_parts.append("The area is well-lit by streetlights and illuminated storefronts.")
        elif timestamp < 3.0:
            caption_parts.append("Commercial signs and store windows are visible in the background.")
        else:
            caption_parts.append("The sidewalk is wide with people moving in various directions.")
        
        new_caption = " ".join(caption_parts)
        
        improved_captions.append({
            'frame_id': frame_id,
            'timestamp': timestamp,
            'new_caption': new_caption,
            'person_count': len(persons)
        })
        
        # 원본 데이터 업데이트
        frame['caption'] = new_caption
    
    # 개선된 캡션 미리보기
    print("=" * 80)
    print("개선된 캡션 미리보기 (버전 2):")
    print("=" * 80)
    for item in improved_captions[:8]:  # 처음 8개 미리보기
        print(f"\nFrame {item['frame_id']} ({item['timestamp']:.1f}s) - {item['person_count']}명:")
        print(f"  {item['new_caption']}")
    
    # 개선된 파일 저장
    with open(meta_db_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 개선된 캡션 저장 완료: {os.path.basename(meta_db_path)}")
    print(f"   총 {len(improved_captions)}개 프레임의 캡션 개선됨")

if __name__ == '__main__':
    improve_captions_v2()

