from django.contrib import admin
from .models import UserInfo, GaitResult, BodyResult, SessionInfo, SchoolInfo, UserHist


@admin.register(BodyResult)
class BodyResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_id', 'created_dt')

    @staticmethod
    def user_id(user):
        return user.id


@admin.register(UserInfo)
class UserInfoAdmin(admin.ModelAdmin):
    actions = ['update_display_name']

    def update_display_name(self, request, queryset):
        # 학교와 기관 정보를 prefetch_related로 한 번에 가져옴
        users = UserInfo.objects.select_related('organization', 'school').all()
        users_to_update = []

        for user in users:
            if user.user_type == 'O' and user.organization:
                if user.department:
                    user.user_display_name = f"{user.organization.organization_name} {user.department} {user.student_name}"
                else:
                    user.user_display_name = f"{user.organization.organization_name} " + (
                        user.student_name if user.student_name else '관리자')
                    # dept가 없으면

                users_to_update.append(user)
            elif user.user_type == 'S' and user.school:
                if user.student_grade and user.student_class and user.student_number:
                    user.user_display_name = f"{user.school.school_name} {user.student_grade}학년 {user.student_class}반 {user.student_number}번 {user.student_name}"
                else:
                    user.user_display_name = f"{user.school.school_name} " + (
                        user.student_name if user.student_name else '관리자')
                users_to_update.append(user)

        # bulk_update로 한 번에 처리
        UserInfo.objects.bulk_update(users_to_update, ['user_display_name'])

    update_display_name.short_description = "Update display names for all users"


# Register your models here.
admin.site.register([GaitResult, SessionInfo, SchoolInfo, UserHist])
