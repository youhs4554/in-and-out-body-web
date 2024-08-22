from django.contrib import admin
from .models import UserInfo, GaitResult

# Register your models here.
admin.site.register([UserInfo, GaitResult])
