from email.policy import default

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField

class CodeInfo(models.Model):
    group_id = models.CharField(max_length=4)
    code_id = models.CharField(max_length=20)
    code_name = models.CharField(max_length=100)
    min_value = models.FloatField(null=True)
    max_value = models.FloatField(null=True)
    normal_min_value = models.FloatField(null=True)
    normal_max_value =  models.FloatField(null=True)
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
    uuid = models.CharField(max_length=100, null=True) # For test only
    created_dt = models.DateTimeField(auto_now_add=True)

class SessionInfo(models.Model):
    req_type = models.CharField(max_length=1)
    session_key = models.CharField(max_length=100)
    user_id = models.BigIntegerField(null=True)
    kiosk_id = models.CharField(max_length=100, null=True, blank=True)
    is_issued = models.BooleanField(default=False)
    created_dt = models.DateTimeField(auto_now_add=True)

class SchoolInfo(models.Model):
    school_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=100, null=True)
    address = models.CharField(max_length=100, null=True)
    created_dt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.school_name

class OrganizationInfo(models.Model):
    organization_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=100, null=True)
    address = models.CharField(max_length=100, null=True)
    created_dt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.organization_name

class UserInfo(AbstractUser):
    user_type = models.CharField(max_length=1, null=False, blank=False)
    phone_number = models.CharField(max_length=100)
    school = models.ForeignKey(SchoolInfo, on_delete=models.CASCADE, null=True, blank=True)  # Allow null values
    organization = models.ForeignKey(OrganizationInfo, on_delete=models.CASCADE, null=True, blank=True)  # Allow null values
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
    school = models.ForeignKey(SchoolInfo, on_delete=models.CASCADE)
    student_grade = models.IntegerField(null=True)
    student_class = models.IntegerField(null=True)
    student_number = models.IntegerField(null=True)
    student_name = models.CharField(max_length=100, null=True, blank=True)
    year = models.IntegerField(null=True)
    created_dt = models.DateTimeField(auto_now_add=True)


class GaitResult(models.Model):
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
                    code_info.min_value, code_info.max_value, code_info.direction)
        except CodeInfo.DoesNotExist:
            return None, None, None, None, None

    def calculate_normalized_score(self, value, code_id):
        """normal_min_value, normal_max_value, min_value, max_value, direction을 이용해 점수를 계산 (clipping 추가)"""
        normal_min, normal_max, min_value, max_value, direction = self.get_code_info(code_id)
        if value is None or normal_min is None or normal_max is None or direction is None:
            return None

        # Clipping: value가 min_value와 max_value 범위를 벗어나면 값을 제한
        if value < min_value:
            value = min_value
        elif value > max_value:
            value = max_value

        # normal_range 내에 있으면 1점 부여
        if normal_min <= value <= normal_max:
            return 1

        # direction에 따른 global min/max 점수 계산
        if direction == 'positive':
            # 클수록 좋은 경우: value가 min_value에 가까우면 0, max_value에 가까우면 1
            return (value - min_value) / (normal_min - min_value)

        elif direction == 'negative':
            # 작을수록 좋은 경우: value가 max_value에 가까우면 0, min_value에 가까우면 1
            return -1 * (value - normal_max) / (max_value - normal_max) + 1

    def calculate_score(self):
        total_sum = 0

        # velocity에 대한 정규화 점수 계산 (code_id는 실제로 대체해야 함)
        velocity_score = self.calculate_normalized_score(self.velocity, 'velocity')
        if velocity_score is not None:
            total_sum += velocity_score * 2  # velocity의 가중치는 2

        # 나머지 필드들에 대한 정규화 점수 계산
        fields_with_codes = [
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
                total_sum += field_score

        # score 계산 (가중합 평균)
        self.score = total_sum

    def save(self, *args, **kwargs):
        # score 계산 후 저장
        self.calculate_score()
        super().save(*args, **kwargs)

class BodyResult(models.Model):
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
    image_front_url = models.CharField(max_length=100, null=True)
    image_side_url = models.CharField(max_length=100, null=True)
    created_dt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"BodyResult for {self.user.username} at {self.created_dt}"