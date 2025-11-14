#!/usr/bin/env python
"""캡션 적용 확인"""
import json
import os
from django.conf import settings
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_backend.settings')
django.setup()

media_dir = settings.MEDIA_ROOT
meta_db_path = os.path.join(media_dir, 'upload_1758152157_test2.mp4-meta_db.json')

with open(meta_db_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

frames = data.get('frame', [])
print(f'✅ 총 프레임 수: {len(frames)}개\n')

# 처음 3개 프레임의 캡션 확인
for i, frame in enumerate(frames[:3], 1):
    print(f'Frame {i} ({frame.get("timestamp", 0):.1f}s):')
    caption = frame.get('caption', '')
    print(f'  캡션 길이: {len(caption)}자')
    print(f'  캡션: {caption[:200]}...')
    print(f'  객체 수: {len(frame.get("objects", []))}개')
    persons = [obj for obj in frame.get('objects', []) if obj.get('class') == 'person']
    print(f'  사람 수: {len(persons)}명')
    if persons:
        print(f'  첫 번째 사람: {persons[0].get("attributes", {}).get("gender", "unknown")}, {persons[0].get("attributes", {}).get("age", "unknown")}')
    print()

