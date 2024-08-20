from django.db import models

class UserInfo(models.Model):
    school = models.CharField(max_length=100)
    class_name = models.CharField(max_length=100)
    student_number = models.IntegerField()
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)

    def __str__(self):
        return f"{self.name} ({self.school} - {self.class_name} - {self.student_number}) - {self.phone_number}"


class GaitAnalysis(models.Model):
    user = models.OneToOneField(UserInfo, on_delete=models.CASCADE)
    speed = models.FloatField()
    stride_length = models.FloatField()
    cadence = models.FloatField()

    def __str__(self):
        return f"Gait Analysis for {self.user.name}"


class BodyTypeAnalysis(models.Model):
    user = models.OneToOneField(UserInfo, on_delete=models.CASCADE)
    turtle_neck = models.CharField(max_length=100)
    shoulder_tilt = models.CharField(max_length=100)

    def __str__(self):
        return f"Body Type Analysis for {self.user.name}"
