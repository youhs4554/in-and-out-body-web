import logging
from apscheduler.schedulers.background import BackgroundScheduler
from analysis.models import SessionInfo
from django.utils import timezone
from datetime import timedelta
import atexit
from django.conf import settings
import os

# 로그 파일 위치 설정
# 로그는 프로젝트 루트 디렉토리에 저장됨
LOG_FILE_PATH = os.path.join(settings.BASE_DIR, 'session_cleanup.log')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=LOG_FILE_PATH,
    filemode='a',
)

def delete_old_sessions():
    """
    sessionInfo table의 created_dt 기준 현재 날짜로 부터
    30일 이상 경과 된(오래된 세션)을 삭제
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count, _ = SessionInfo.objects.filter(created_dt__lt=cutoff_date).delete()

        # 로그 및 콘솔 출력
        logging.info(f"{deleted_count} old sessions deleted successfully.")
        # print(f"{deleted_count} old sessions deleted successfully.")
    except Exception as e:
        logging.error(f"Error while deleting old sessions: {e}")
        # print(f"Error while deleting old sessions: {e}")


def print_test():
    try:
        print("TEST")
    except Exception as e:
        logging.error(f"Error while printing test: {e}")

# 작업 등록
scheduler = BackgroundScheduler()

# 매일 00:00에 실행
# 동일한 작업이 이미 등록되어 있다면 대체
scheduler.add_job(delete_old_sessions, 'cron', hour=0, minute=0, replace_existing=True)

# 서버 종료 시 스케줄러 중지 및 로그 출력
def stop_scheduler():
    if scheduler.running:
        logging.info("Shutting down scheduler...")
        scheduler.shutdown()

atexit.register(stop_scheduler)