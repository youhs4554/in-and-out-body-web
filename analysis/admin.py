from django.contrib import admin
from .models import AuthInfo, UserInfo, GaitResult, BodyResult, SessionInfo, SchoolInfo, UserHist

# Register your models here.
admin.site.register([UserInfo, GaitResult, BodyResult, SessionInfo, SchoolInfo, UserHist])
