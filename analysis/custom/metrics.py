from prometheus_client import Counter

""" 프로메테우스 커스텀 """

# 학교별 체형 카운팅 함수
body_result_by_school = Counter(
    'django_model_body_result_by_school_total',
    'Number of body results by school',
    ['school_name']
)