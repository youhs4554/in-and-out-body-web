from django.apps import AppConfig

class AnalysisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analysis'

    def ready(self):
        from analysis.custom.tasks import scheduler
        # 스케줄러가 이미 실행 중인지 확인 후 실행
        if not scheduler.running:
            scheduler.start()