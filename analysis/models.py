from django.db import models
from django.contrib.auth.models import AbstractUser

class UserInfo(AbstractUser):
    school = models.CharField(max_length=30)
    class_name = models.CharField(max_length=30)
    student_number = models.IntegerField(null=True)
    phone = models.CharField(unique = True, null = False, blank = False, max_length=15)

    class Meta:
        # Ensures the combination of name, phone is unique
        unique_together = ('username', 'phone')

class GaitAnalysis(models.Model):
    user = models.ForeignKey(UserInfo, on_delete=models.CASCADE)
    speed = models.FloatField()
    stride_length = models.FloatField()
    cadence = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"GaitAnalysis for {self.user.username} at {self.created_at}"

class PoseAnalysis(models.Model):
    user = models.ForeignKey(UserInfo, on_delete=models.CASCADE)
    turtle_neck = models.FloatField()
    shoulder_tilt = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PoseAnalysis for {self.user.username} at {self.created_at}"
