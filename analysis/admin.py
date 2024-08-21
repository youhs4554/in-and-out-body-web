from django.contrib import admin
from .models import UserInfo, GaitAnalysis

# Register your models here.
admin.site.register([UserInfo, GaitAnalysis])
