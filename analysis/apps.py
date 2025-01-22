from django.apps import AppConfig

class AnalysisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analysis'

    def ready(self):

        # 세션 소멸 - 스케줄러 실행
        from analysis.custom.tasks import scheduler
        # 스케줄러가 이미 실행 중인지 확인 후 실행
        # print("스케줄러 실행")
        if not scheduler.running:
            scheduler.start()

        # DAU, WAU, MAU 계산 - 스케줄러 실행 (서버 실행 시 1회 실행) 추 후 mobile create_body_result API 호출 시마다 실행됨
        from .custom.metrics import calculate_active_users
        # print("초기 DAU, WAU, MAU 불러오기")
        calculate_active_users()