"""
영상 74, 75, 76, 77에 대해 모든 객체를 YOLO로 감지하여 재분석하는 Django 관리 명령어
"""
from django.core.management.base import BaseCommand
from chat.models import Video
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '영상 74, 75, 76, 77에 대해 캡션을 유지하면서 YOLO 객체 감지만 재수행'

    def handle(self, *args, **options):
        # 순환 import 방지를 위해 함수 내에서 import
        from chat.services.video_analysis_service import VideoAnalysisService
        
        video_ids = [74, 75, 76, 77]
        
        self.stdout.write("=" * 100)
        self.stdout.write(self.style.SUCCESS("📹 영상 재분석 시작 (모든 객체 YOLO 감지, 캡션 유지)"))
        self.stdout.write("=" * 100)
        self.stdout.write("")
        
        results = {}
        analysis_service = VideoAnalysisService()
        
        for video_id in video_ids:
            self.stdout.write(f"\n{'='*100}")
            self.stdout.write(f"Video ID {video_id} 재분석 중...")
            self.stdout.write(f"{'='*100}\n")
            
            try:
                video = Video.objects.get(id=video_id)
                self.stdout.write(self.style.SUCCESS(f"📹 Video ID {video_id} 재분석 시작: {video.original_name}"))
                
                # 객체만 재분석 실행 (캡션 유지)
                self.stdout.write(f"🔄 Video ID {video_id} 객체 재분석 중 (캡션 유지)...")
                result = analysis_service.reanalyze_objects_only(video_id)
                
                if result:
                    self.stdout.write(self.style.SUCCESS(f"✅ Video ID {video_id} 재분석 완료"))
                    results[video_id] = True
                else:
                    self.stdout.write(self.style.ERROR(f"❌ Video ID {video_id} 재분석 실패"))
                    results[video_id] = False
                    
            except Video.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Video ID {video_id}: 영상을 찾을 수 없습니다"))
                results[video_id] = False
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Video ID {video_id} 재분석 중 오류: {e}"))
                import traceback
                self.stdout.write(self.style.ERROR(traceback.format_exc()))
                results[video_id] = False
        
        # 결과 요약
        self.stdout.write("\n" + "=" * 100)
        self.stdout.write(self.style.SUCCESS("📊 재분석 결과 요약"))
        self.stdout.write("=" * 100)
        self.stdout.write("")
        
        for video_id, success in results.items():
            status = self.style.SUCCESS("✅ 성공") if success else self.style.ERROR("❌ 실패")
            self.stdout.write(f"Video ID {video_id}: {status}")
        
        self.stdout.write("")
        success_count = sum(1 for s in results.values() if s)
        self.stdout.write(f"총 {len(results)}개 영상 중 {success_count}개 성공")

