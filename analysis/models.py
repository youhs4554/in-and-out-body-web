from django.db import models
from django.contrib.auth.models import AbstractUser

class SessionInfo(models.Model):
    req_type = models.CharField(max_length=1)
    session_key = models.CharField(max_length=100)
    user_id = models.BigIntegerField(null=True)
    kiosk_id = models.CharField(max_length=100, null=True)
    created_dt = models.DateTimeField(auto_now_add=True)

class SchoolInfo(models.Model):
    school_name = models.CharField(max_length=100)
    contact_number = models.IntegerField(null=True)
    created_dt = models.DateTimeField(auto_now_add=True)

class UserInfo(AbstractUser):
    user_type = models.CharField(max_length=1)
    phone_number = models.CharField(max_length=100)
    school = models.ForeignKey(SchoolInfo, on_delete=models.CASCADE)
    student_grade = models.IntegerField(null=True)
    student_class = models.IntegerField(null=True)
    student_number = models.IntegerField(null=True)
    year = models.IntegerField(null=True)
    created_dt = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['year', 'student_grade', 'student_class'])
        ]

class UserHist(models.Model):
    user = models.ForeignKey(UserInfo, on_delete=models.CASCADE)
    school = models.ForeignKey(SchoolInfo, on_delete=models.CASCADE)
    student_grade = models.IntegerField(null=True)
    student_class = models.IntegerField(null=True)
    student_number = models.IntegerField(null=True)
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
    created_dt = models.DateTimeField(auto_now_add=True)



# class UserInfo(AbstractUser):
#     school = models.CharField(max_length=30)
#     class_name = models.CharField(max_length=30)
#     student_number = models.IntegerField(null=True)
#     phone = models.CharField(unique = True, null = False, blank = False, max_length=15)
#
#     class Meta:
#         # Ensures the combination of name, phone is unique
#         unique_together = ('username', 'phone')

# class GaitAnalysis(models.Model):
#     user = models.ForeignKey(UserInfo, on_delete=models.CASCADE)
#     speed = models.FloatField()
#     stride_length = models.FloatField()
#     cadence = models.FloatField()
#     created_at = models.DateTimeField(auto_now_add=True)
#
#     def __str__(self):
#         return f"GaitAnalysis for {self.user.username} at {self.created_at}"
#
# class PoseAnalysis(models.Model):
#     user = models.ForeignKey(UserInfo, on_delete=models.CASCADE)
#     turtle_neck = models.FloatField()
#     shoulder_tilt = models.FloatField()
#     created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PoseAnalysis for {self.user.username} at {self.created_dt}"


