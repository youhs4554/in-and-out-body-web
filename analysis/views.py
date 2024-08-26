# analysis/views.py

import os
import re
import pandas as pd
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.contrib.auth.models import Group
from rest_framework import permissions, viewsets
from django.contrib.auth.hashers import make_password
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.contrib.auth.views import PasswordChangeView

from .models import BodyResult, GaitResult, SchoolInfo, UserInfo, SessionInfo
from .forms import UploadFileForm, CustomPasswordChangeForm
from .serializers import BodyResultSerializer, GaitResultSerializer, GroupSerializer, UserInfoSerializer


from rest_framework.decorators import api_view
from rest_framework.response import Response

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers

def home(request):
    if request.user.is_authenticated:
        return redirect('upload_file')
    else:
        return redirect('login')

@login_required
def upload_file(request):
    users = []  # Initialize an empty list to hold user data

    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['file']
            # Read the Excel file
            df = pd.read_excel(excel_file)
            
            for _, row in df.iterrows():
                    
                school_info, created = SchoolInfo.objects.update_or_create(
                    school_name=row['학교'],
                )
                
                # Find or create the UserInfo
                user_info, created = UserInfo.objects.update_or_create(
                    username=row['전화번호'],
                    defaults=dict(
                        school=school_info,
                        student_grade=row['학년'],
                        student_class=row['반'],
                        student_number=row['번호'],
                        student_name=row['이름'].replace(' ', ''),
                        phone_number=row['전화번호'],
                        password=make_password(os.environ['DEFAULT_PASSWORD'])
                    ),
                )

                users.append(user_info)


            return render(request, 'upload.html', {
                'form': form,
                'users': users
            })
    else:
        form = UploadFileForm()
    
    return render(request, 'upload.html', {'form': form})

@login_required
def report(request):
    groups = UserInfo.objects.values_list('student_grade', 'student_class', named=True).distinct().order_by('student_grade', 'student_class')
    groups = [ f'{g.student_grade}학년 {g.student_class}반' for g in groups if ((g.student_grade is not None) & (g.student_class is not None)) ] # Note : 학년, 반 정보 없는 superuser는 그룹에 포함안됨
    print(groups)
    if request.method == 'POST':
        selected_group = request.POST.get('group')

        # 정규 표현식을 사용하여 학년과 반 추출
        match = re.search(r"(\d+)학년 (\d+)반", selected_group)
        users = UserInfo.objects.filter(student_grade=match.group(1), 
                                        student_class=match.group(2))
    else:
        users = UserInfo.objects.none()
        selected_group = None
    return render(request, 'report.html', {'groups': groups, 'users': users, 'selected_group': selected_group})

def policy(request):
    return render(request, 'policy.html')


class UserInfoViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = UserInfo.objects.all().order_by('-created_dt')
    serializer_class = UserInfoSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all().order_by('name')
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


class GaitResultViewSet(viewsets.ModelViewSet):
    queryset = GaitResult.objects.all().order_by('-created_dt')
    serializer_class = GaitResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user

        try:
            # Ensure the user has a corresponding UserInfo instance
            user_info = UserInfo.objects.get(phone_number=user.phone_number)
        except UserInfo.DoesNotExist:
            return Response({"detail": "UserInfo does not exist for the current user."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Save the GaitAnalysis instance with the associated UserInfo
        serializer.save(user=user_info)

    def get_queryset(self):
        # Filter the queryset to show only entries for the current user
        return GaitResult.objects.filter(user__phone_number=self.request.user.phone_number).order_by('-created_dt')
    
class BodyResultViewSet(viewsets.ModelViewSet):
    queryset = BodyResult.objects.all().order_by('-created_dt')
    serializer_class = BodyResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Filter the queryset to show only entries for the current user
        return BodyResult.objects.filter(user__phone_number=self.request.user.phone_number).order_by('-created_dt')
    
class CustomPasswordChangeView(PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'password_change.html'
    success_url = '/password-change-done/'



# 인증키 요청하기
@api_view(['GET'])
def request_auth_key(request, code):
    sess_infos = SessionInfo.objects.filter(session_key=code, is_issued=False)
    if len(sess_infos) == 0:
        return Response(
            {
                'message': 'nodata'
            })

    sess_info = sess_infos[0]
    user_id = sess_info.user_id
    user = UserInfo.objects.get(id=user_id)
    token = TokenObtainPairSerializer.get_token(user)
    refresh_token = str(token)
    access_token = str(token.access_token)
    # response = Response(
    #     [{
    #         'user': {
    #           'user_id': user.id,
    #             'user_name': user.username,
    #             'phone_number': user.phone_number,
    #             'student_name': user.student_name,
    #             'year': user.year,
    #             'school_id': user.school_id,
    #             'school_name': user.school.school_name,
    #             'student_grade': user.student_grade,
    #             'student_class': user.student_class,
    #             'student_number': user.student_number,
    #         },
    #         'message': 'success',
    #         'jwt_token': {
    #             'access_token': access_token,
    #             'refresh_token': refresh_token,
    #         }
    #     }]
    # )
    response = Response(
        {
            'data':{
                'user_id': user.id,
                'user_name': user.username,
                'phone_number': user.phone_number,
                'student_name': user.student_name,
                'year': user.year,
                'school_id': user.school_id,
                'school_name': user.school.school_name,
                'student_grade': user.student_grade,
                'student_class': user.student_class,
                'student_number': user.student_number,
                'message': 'success',
                'access_token': access_token,
                'refresh_token': refresh_token,
            }
        }
    )

    sess_info.is_issued = True
    sess_info.save()

    return response


