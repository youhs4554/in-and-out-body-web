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
    created_dt = models.DateTimeField(auto_now_add=True)

class AuthInfo(models.Model):
    uid = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=100)
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
    user_type = models.CharField(max_length=1, default='S', null=False, blank=False)
    phone_number = models.CharField(max_length=100)
    school = models.ForeignKey(SchoolInfo, on_delete=models.CASCADE, null=True, blank=True)  # Allow null values
    organization = models.ForeignKey(OrganizationInfo, on_delete=models.CASCADE, null=True, blank=True)  # Allow null values
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