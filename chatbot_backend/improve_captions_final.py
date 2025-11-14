#!/usr/bin/env python
"""
Video ID 74의 캡션을 최종적으로 자연스럽고 구체적으로 개선
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
    """색상 이름을 자연스럽게 변환"""
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

def improve_captions_final():
    """최종 캡션 개선 - 자연스럽고 간결하게"""
    media_dir = settings.MEDIA_ROOT
    meta_db_path = os.path.join(media_dir, "upload_1758152157_test2.mp4-meta_db.json")
    
    with open(meta_db_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    frames = data.get('frame', [])
    
    # 각 프레임별로 자연스럽고 구체적인 캡션 생성
    improved_captions = []
    
    for idx, frame in enumerate(frames):
        frame_id = frame.get('image_id', idx + 1)
        timestamp = frame.get('timestamp', 0)
        objects = frame.get('objects', [])
        
        persons = [obj for obj in objects if obj.get('class') == 'person']
        
        # 주요 인물 정보 추출 (상위 3-4명)
        main_persons = sorted(persons, key=lambda x: x.get('confidence', 0), reverse=True)[:4]
        
        # 자연스러운 캡션 생성
        caption_parts = []
        
        # 기본 장면 설명 (간결하게)
        if timestamp < 1.0:
            caption_parts.append("A busy nighttime shopping street with pedestrians walking along the sidewalk.")
        elif timestamp < 2.0:
            caption_parts.append("A city sidewalk at night showing people walking near illuminated storefronts.")
        elif timestamp < 4.0:
            caption_parts.append("A shopping district street scene with multiple pedestrians on a wide sidewalk.")
        else:
            caption_parts.append("A city street scene with people walking along the sidewalk near commercial buildings.")
        
        # 주요 인물 묘사 (간결하고 자연스럽게)
        if main_persons:
            person_descriptions = []
            for person in main_persons:
                attrs = person.get('attributes', {})
                clothing = attrs.get('clothing', {})
                upper_color = get_color_name(clothing.get('upper_color', 'unknown'))
                lower_color = get_color_name(clothing.get('lower_color', 'unknown'))
                gender = attrs.get('gender', 'person')
                age = attrs.get('age', 'adult')
                
                # 나이 설명
                age_desc = ""
                if age == "young_adult":
                    age_desc = "young"
                elif age == "middle_aged":
                    age_desc = "middle-aged"
                elif age == "elderly":
                    age_desc = "elderly"
                
                gender_desc = "man" if gender == "man" else "woman" if gender == "woman" else "person"
                
                # 색상 설명 (간결하게)
                if upper_color != 'unknown' and lower_color != 'unknown':
                    if upper_color == lower_color:
                        color_desc = f"in {upper_color}"
                    else:
                        color_desc = f"wearing {upper_color} and {lower_color}"
                elif upper_color != 'unknown':
                    color_desc = f"in {upper_color}"
                else:
                    color_desc = ""
                
                # 최종 설명 조합
                if age_desc and color_desc:
                    desc = f"a {age_desc} {gender_desc} {color_desc}"
                elif age_desc:
                    desc = f"a {age_desc} {gender_desc}"
                elif color_desc:
                    desc = f"a {gender_desc} {color_desc}"
                else:
                    desc = f"a {gender_desc}"
                
                person_descriptions.append(desc)
            
            # 자연스러운 문장 구성
            if len(person_descriptions) == 1:
                caption_parts.append(f"Visible in the scene is {person_descriptions[0]}.")
            elif len(person_descriptions) == 2:
                caption_parts.append(f"Visible are {person_descriptions[0]} and {person_descriptions[1]}.")
            elif len(person_descriptions) == 3:
                caption_parts.append(f"Visible are {person_descriptions[0]}, {person_descriptions[1]}, and {person_descriptions[2]}.")
            else:
                people_text = ", ".join(person_descriptions[:-1]) + f", and {person_descriptions[-1]}"
                caption_parts.append(f"Visible are {people_text}.")
        
        # 전체 인원 수 (간단히)
        if len(persons) > len(main_persons):
            caption_parts.append(f"Several other pedestrians are also visible in the scene.")
        
        # 장면 세부사항 (간결하게)
        if timestamp < 1.5:
            caption_parts.append("The area is brightly lit by streetlights and storefronts.")
        elif timestamp < 3.0:
            caption_parts.append("Store signs and commercial displays are visible in the background.")
        else:
            caption_parts.append("People are moving in various directions along the wide sidewalk.")
        
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
    print("최종 개선된 캡션 미리보기:")
    print("=" * 80)
    for item in improved_captions:
        print(f"\nFrame {item['frame_id']} ({item['timestamp']:.1f}s) - {item['person_count']}명:")
        print(f"  {item['new_caption']}")
    
    # 개선된 파일 저장
    with open(meta_db_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 최종 개선된 캡션 저장 완료: {os.path.basename(meta_db_path)}")
    print(f"   총 {len(improved_captions)}개 프레임의 캡션 개선됨")
    print(f"\n🎉 졸업작품 심사 화이팅! 채팅이 더 자연스럽고 명확해질 거예요!")

if __name__ == '__main__':
    improve_captions_final()

