from prometheus_client import Counter, Gauge
from django.utils.timezone import now, timedelta

# 학교 별 체형 카운팅
body_result_by_school = Counter(
    'django_model_body_result_by_school_total',
    'Number of body results by school',
    ['school_name']
)

# 기관 별 체형 카운팅
body_result_by_org = Counter(
    'django_model_body_result_by_org_total',
    'Number of body results by org',
    ['organization_name']
)

# DAU, WAU, MAU 카운팅
daily_active_users = Gauge(
    'daily_active_users',
    'Daily Active Users for BodyResult creation'
)

weekly_active_users = Gauge(
    'weekly_active_users',
    'Weekly Active Users for BodyResult creation'
)

monthly_active_users = Gauge(
    'monthly_active_users',
    'Monthly Active Users for BodyResult creation'
)

# DAU, WAU, MAU 계산 함수
def calculate_active_users():
    from ..models import BodyResult
    today = now().date()

    # DAU 계산: 오늘 BodyResult를 생성한 고유 사용자 수
    dau_count = BodyResult.objects.filter(created_dt__date=today, mobile_yn = 'y').values('user').distinct().count()
    daily_active_users.set(dau_count)

    # WAU 계산: 최근 7일 동안 BodyResult를 생성한 고유 사용자 수
    last_week = today - timedelta(days=7)
    wau_count = BodyResult.objects.filter(created_dt__date__gte=last_week, mobile_yn = 'y').values('user').distinct().count()
    weekly_active_users.set(wau_count)

    # MAU 계산: 최근 30일 동안 BodyResult를 생성한 고유 사용자 수
    last_month = today - timedelta(days=30)
    mau_count = BodyResult.objects.filter(created_dt__date__gte=last_month, mobile_yn = 'y').values('user').distinct().count()
    monthly_active_users.set(mau_count)


    """
    -- WAU
    select distinct(user_id) from analysis_bodyresult 
    where created_dt >= now() - INTERVAL '7 days' and mobile_yn = 'y';

    -- MAU
    select distinct(user_id) from analysis_bodyresult 
    where created_dt >= now() - INTERVAL '30 days' and mobile_yn = 'y';


    -- DAU
    select distinct(user_id) from analysis_bodyresult 
    where created_dt >= now() - INTERVAL '1 days' and mobile_yn = 'y';
    """