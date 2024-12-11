import logging
from apscheduler.schedulers.background import BackgroundScheduler
from analysis.models import SessionInfo
from django.utils import timezone
from datetime import timedelta
import atexit
from django.conf import settings
import os

# 로그 파일 위치 설정
LOG_FILE_PATH = os.path.join(settings.BASE_DIR, 'session_cleanup.log')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=LOG_FILE_PATH,
    filemode='a',
)

scheduler = BackgroundScheduler()

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

# 스케줄러 작업 등록
scheduler.add_job(delete_old_sessions, 'cron', hour=0, minute=0)

# 서버 종료 시 스케줄러 중지
def stop_scheduler():
    if scheduler.running:
        logging.info("Shutting down scheduler...")
        scheduler.shutdown()

atexit.register(stop_scheduler)