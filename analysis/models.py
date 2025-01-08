from email.policy import default

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django_prometheus.models import ExportModelOperationsMixin
from analysis.custom import metrics


class CodeInfo(models.Model):
    group_id = models.CharField(max_length=4)
    code_id = models.CharField(max_length=20)
    code_name = models.CharField(max_length=100)
    min_value = models.FloatField(null=True)
    max_value = models.FloatField(null=True)
    normal_min_value = models.FloatField(null=True)
    normal_max_value = models.FloatField(null=True)
    caution_min_value = models.FloatField(null=True)
    caution_max_value = models.FloatField(null=True)
    outline = models.CharField(max_length=1000, null=True)
    risk = models.CharField(max_length=1000, null=True, blank=True)
    improve = models.CharField(max_length=1000, null=True, blank=True)
    recommended = ArrayField(models.CharField(max_length=500, null=True, blank=True), size=2, null=True, blank=True)
    title = models.CharField(max_length=100, null=True)
    title_outline = models.CharField(max_length=100, null=True)
    title_risk = models.CharField(max_length=100, null=True)
    title_improve = models.CharField(max_length=100, null=True)
    title_recommended = models.CharField(max_length=100, null=True)
    unit_name = models.CharField(max_length=20, null=True)
    seq_no = models.IntegerField(null=True)
    display_ticks = ArrayField(
        models.IntegerField(null=True, blank=True),
        size=None,
        null=True, blank=True,
        default=list,
    )
    direction = models.CharField(max_length=10, choices=[('positive', 'Positive'), ('negative', 'Negative')], null=True)
    created_dt = models.DateTimeField(auto_now_add=True)


class AuthInfo(models.Model):
    uid = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=100)
    uuid = models.CharField(max_length=100, null=True)  # For test only
    created_dt = models.DateTimeField(auto_now_add=True)


class SessionInfo(models.Model):
    req_type = models.CharField(max_length=1)
    session_key = models.CharField(max_length=100)
    user_id = models.BigIntegerField(null=True)
    kiosk_id = models.CharField(max_length=100, null=True, blank=True)
    is_issued = models.BooleanField(default=False)
    created_dt = models.DateTimeField(auto_now_add=True)


class SchoolInfo(ExportModelOperationsMixin('school_info'), models.Model):
    school_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=100, null=True)
    address = models.CharField(max_length=100, null=True)
    created_dt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.school_name


class OrganizationInfo(ExportModelOperationsMixin('organization_info'), models.Model):
    organization_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=100, null=True)
    address = models.CharField(max_length=100, null=True)
    created_dt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.organization_name


class UserInfo(ExportModelOperationsMixin('user_info'), AbstractUser):
    user_type = models.CharField(max_length=1, null=False, blank=False)
    phone_number = models.CharField(max_length=100)
    school = models.ForeignKey(SchoolInfo, on_delete=models.CASCADE, null=True, blank=True)  # Allow null values
    organization = models.ForeignKey(OrganizationInfo, on_delete=models.CASCADE, null=True,
                                     blank=True)  # Allow null values
    department = models.CharField(max_length=100, null=True, blank=True)
    student_grade = models.IntegerField(null=True, blank=True)
    student_class = models.IntegerField(null=True, blank=True)
    student_number = models.IntegerField(null=True, blank=True)
    student_name = models.CharField(max_length=100, null=True, blank=True)
    user_display_name = models.CharField(max_length=100, null=True, blank=True)
    dob = models.CharField(max_length=8, null=True, blank=True)
    gender = models.CharField(max_length=1, null=True)
    height = models.FloatField(null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    created_dt = models.DateTimeField(auto_now_add=True)
    last_active_dt = models.DateTimeField(null=True, blank=True)  # 마지막 활동 시간

    class Meta:
        indexes = [
            models.Index(fields=['year', 'student_grade', 'student_class'])
        ]

    def __str__(self):
        if self.user_type in ['S', 'O']:
            return self.user_display_name
        else:
            return f'{self.phone_number}'


class UserHist(models.Model):
    user = models.ForeignKey(UserInfo, on_delete=models.CASCADE)
    school = models.ForeignKey(SchoolInfo, on_delete=models.CASCADE, null=True, blank=True)  # Allow null values
    organization = models.ForeignKey(OrganizationInfo, on_delete=models.CASCADE, null=True,
                                     blank=True)  # Allow null values
    student_grade = models.IntegerField(null=True)
    student_class = models.IntegerField(null=True)
    student_number = models.IntegerField(null=True)
    student_name = models.CharField(max_length=100, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    year = models.IntegerField(null=True)
    created_dt = models.DateTimeField(auto_now_add=True)


class GaitResult(ExportModelOperationsMixin('gait_result'), models.Model):
    user = models.ForeignKey(UserInfo, on_delete=models.CASCADE)
    school = models.ForeignKey(SchoolInfo, on_delete=models.CASCADE)
    student_grade = models.IntegerField(null=True)
    student_class = models.IntegerField(null=True)
    student_number = models.IntegerField(null=True)
    score = models.FloatField(null=True)
    velocity = models.FloatField(null=True)
    cadence = models.FloatField(null=True)
    cycle_time_l = models.FloatField(null=True)
    cycle_time_r = models.FloatField(null=True)
    stride_len_l = models.FloatField(null=True)
    stride_len_r = models.FloatField(null=True)
    supp_base_l = models.FloatField(null=True)
    supp_base_r = models.FloatField(null=True)
    swing_perc_l = models.FloatField(null=True)
    swing_perc_r = models.FloatField(null=True)
    stance_perc_l = models.FloatField(null=True)
    stance_perc_r = models.FloatField(null=True)
    d_supp_perc_l = models.FloatField(null=True)
    d_supp_perc_r = models.FloatField(null=True)
    toeinout_l = models.FloatField(null=True)
    toeinout_r = models.FloatField(null=True)
    stridelen_cv_l = models.FloatField(null=True)
    stridelen_cv_r = models.FloatField(null=True)
    stridetm_cv_l = models.FloatField(null=True)
    stridetm_cv_r = models.FloatField(null=True)
    created_dt = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_dt'])
        ]
        ordering = ['-created_dt']

    def __str__(self):
        return f"GaitResult for {self.user.username} at {self.created_dt}"

    def get_code_info(self, code_id):
        """CodeInfo 테이블에서 특정 code_id에 해당하는 normal_min_value, normal_max_value, min_value, max_value, direction을 가져옴"""
        try:
            code_info = CodeInfo.objects.get(code_id=code_id)
            return (code_info.normal_min_value, code_info.normal_max_value,
                    code_info.min_value, code_info.max_value, code_info.direction)
        except CodeInfo.DoesNotExist:
            return None, None, None, None, None

    def get_code_info(self, code_id):
        """CodeInfo 테이블에서 특정 code_id에 해당하는 normal_min_value, normal_max_value, min_value, max_value, direction을 가져옴"""
        try:
            code_info = CodeInfo.objects.get(code_id=code_id)
            return (code_info.normal_min_value, code_info.normal_max_value,
                    code_info.caution_min_value, code_info.caution_max_value,
                    code_info.min_value, code_info.max_value, code_info.direction)
        except CodeInfo.DoesNotExist:
            return None, None, None, None, None, None, None

    def calculate_normalized_score(self, value, code_id):
        """normal_min_value, normal_max_value, min_value, max_value, direction을 이용해 점수를 계산 (clipping 추가)"""
        normal_min, normal_max, caution_min, caution_max, min_value, max_value, direction = self.get_code_info(code_id)
        if value is None or normal_min is None or normal_max is None or caution_min is None or caution_max is None or direction is None:
            return None

        # Clipping: value가 min_value와 max_value 범위를 벗어나면 값을 제한
        if value < min_value:
            value = min_value
        elif value > max_value:
            value = max_value

        # direction에 따른 global min/max 점수 계산
        if direction == 'positive':
            # 클수록 좋은 경우: value가 min_value에 가까우면 0, max_value에 가까우면 1
            if min_value <= value <= caution_max:
                score = 0.4 * (value - min_value) / (caution_min - min_value)
            elif caution_min <= value <= normal_min:
                score = 0.3 * (value - caution_min) / (normal_min - caution_min) + 0.4
            elif normal_min <= value <= max_value:
                score = 0.3 * (value - normal_min) / (max_value - normal_min) + 0.7
        elif direction == 'negative':
            # 작을수록 좋은 경우: value가 max_value에 가까우면 0, min_value에 가까우면 1
            if min_value <= value <= normal_max:
                score = -0.3 * (value - min_value) / (normal_max - min_value) + 1.0
            elif normal_max <= value <= caution_max:
                score = -0.3 * (value - normal_max) / (caution_max - normal_max) + 0.7
            elif caution_max <= value <= max_value:
                score = -0.4 * (value - caution_max) / (max_value - caution_max) + 0.4

        # score가 항상 0과 1 사이의 값이 되도록 보장
        return max(0, min(score, 1))

    def calculate_score(self):
        total_sum = 0
        total_weight = 0

        # 나머지 필드들에 대한 정규화 점수 계산
        fields_with_codes = [
            (self.velocity, 'velocity'),
            (self.stride_len_l, 'stride_len_l'),
            (self.stride_len_r, 'stride_len_r'),
            (self.swing_perc_l, 'swing_perc_l'),
            (self.swing_perc_r, 'swing_perc_r'),
            (self.stance_perc_l, 'stance_perc_l'),
            (self.stance_perc_r, 'stance_perc_r'),
            (self.d_supp_perc_l, 'd_supp_perc_l'),
            (self.d_supp_perc_r, 'd_supp_perc_r')
        ]

        for field, code_id in fields_with_codes:
            field_score = self.calculate_normalized_score(field, code_id)
            if field_score is not None:
                if field in ['velocity', 'stride_len_l', 'stride_len_r']:
                    total_sum += field_score * 2  # 가중치 2
                    total_weight += 2
                else:
                    total_sum += field_score
                    total_weight += 1

        # score 계산 (가중합 평균)
        if total_weight > 0:
            *_, score_max_value, _ = self.get_code_info('score')
            self.score = total_sum / total_weight * score_max_value
        else:
            self.score = None

    def save(self, *args, **kwargs):
        # score 계산 후 저장
        self.calculate_score()
        super().save(*args, **kwargs)


class BodyResult(ExportModelOperationsMixin('body_result'), models.Model):
    user = models.ForeignKey(UserInfo, on_delete=models.CASCADE)
    school = models.ForeignKey(SchoolInfo, on_delete=models.CASCADE)
    student_grade = models.IntegerField(null=True)
    student_class = models.IntegerField(null=True)
    student_number = models.IntegerField(null=True)
    face_level_angle = models.FloatField(null=True)
    shoulder_level_angle = models.FloatField(null=True)
    hip_level_angle = models.FloatField(null=True)
    leg_length_ratio = models.FloatField(null=True)
    left_leg_alignment_angle = models.FloatField(null=True)
    right_leg_alignment_angle = models.FloatField(null=True)
    left_back_knee_angle = models.FloatField(null=True)
    right_back_knee_angle = models.FloatField(null=True)
    forward_head_angle = models.FloatField(null=True)
    scoliosis_shoulder_ratio = models.FloatField(null=True)
    scoliosis_hip_ratio = models.FloatField(null=True)
    # S3 미리 서명 URL 갱신 시 컬럼 길이 제한으로 짤려서 들어감
    image_front_url = models.CharField(max_length=500, null=True)  # 수정
    image_side_url = models.CharField(max_length=500, null=True)  # 수정
    mobile_yn = models.CharField(max_length=1, default='n')  # 체형 결과에서 키오스크와 모바일 구분하기 위함
    created_dt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"BodyResult for {self.user.username} at {self.created_dt}"

    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_dt'])
        ]
        ordering = ['-created_dt']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            if self.user.user_type == 'S':
                metrics.body_result_by_school.labels(
                    school_name=self.school.school_name
                ).inc()
            elif self.user.user_type == 'O':
                metrics.body_result_by_org.labels(
                    organization_name=self.user.organization.organization_name
                ).inc()
        super().save(*args, **kwargs)


### 체형 분석 결과에서 keypoints 들을 저장할 테이블
### 모바일에서만 사용함 (null = True)
class Keypoint(models.Model):
    body_result = models.ForeignKey(BodyResult, on_delete=models.CASCADE, related_name='keypoints')
    pose_type = models.CharField(max_length=5, choices=[('front', 'Front'), ('side', 'Side')])
    x = ArrayField(models.FloatField())
    y = ArrayField(models.FloatField())
    z = ArrayField(models.FloatField())
    visibility = ArrayField(models.FloatField())
    presence = ArrayField(models.FloatField())

    class Meta:
        # unique_together를 사용하여 (body_result, pose_type) 조합이 유일하도록 제한
        unique_together = ('body_result', 'pose_type')
        # 추가로 제약조건을 걸어 pose_type이 'front'나 'side'만 가능하도록 함
        constraints = [
            models.CheckConstraint(
                check=models.Q(pose_type__in=['front', 'side']),
                name='valid_pose_type'
            )
        ]
