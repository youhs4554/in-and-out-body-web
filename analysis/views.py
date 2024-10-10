# analysis/views.py

import json
import os
import re
import uuid
import pandas as pd
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password, check_password
import requests
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.views import PasswordChangeView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import datetime, timedelta
from .helpers import extract_digits, generate_presigned_url, parse_userinfo, upload_image_to_s3
from .models import BodyResult, CodeInfo, GaitResult, OrganizationInfo, SchoolInfo, UserInfo, SessionInfo
from .forms import UploadFileForm, CustomPasswordChangeForm, CustomUserCreationForm, CustomPasswordResetForm
from .serializers import BodyResultSerializer, GaitResponseSerializer, GaitResultSerializer


from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from datetime import datetime as dt
from django.utils import timezone
from dateutil.relativedelta import relativedelta

def home(request):
    if request.user.is_authenticated:
        return redirect('register')
    else:
        return redirect('login')

from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.urls import reverse_lazy

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Automatically log the user in after registration
            login(request, user)
            # Redirect to the desired page after registration
            return redirect(reverse_lazy('home'))  # Redirect to 'home' or any other page
    else:
        form = CustomUserCreationForm()

    return render(request, 'signup.html', {'form': form})

def password_reset(request):
    if request.method == 'POST':
        form = CustomPasswordResetForm(request.POST)

        # 1. 아이디 검증 (폼 유효성 검증 이전에 수행)
        username = request.POST.get('username')
        try:
            user = UserInfo.objects.get(username=username)
        except UserInfo.DoesNotExist:
            # 존재하지 않는 아이디일 때 오류 메시지 추가
            form.add_error('username', '존재하지 않는 아이디입니다.')
            # 유효하지 않은 경우는 기존 에러 메시지와 함께 출력
            return render(request, 'password_reset.html', {'form': form})

        # 2. 폼 유효성 검증
        if form.is_valid():
            # 3. 비밀번호 변경
            new_password = form.cleaned_data.get('new_password1')
            user.password = make_password(new_password)
            user.save()

            return redirect('password_reset_done')

        # 폼이 유효하지 않은 경우 오류 메시지를 표시
        return render(request, 'password_reset.html', {'form': form})

    # GET 요청일 경우 빈 폼을 렌더링
    form = CustomPasswordResetForm()
    return render(request, 'password_reset.html', {'form': form})

def password_reset_done(request):
    return render(request, 'password_reset_done.html')

class CustomPasswordChangeView(PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'password_change.html'
    success_url = '/password-change-done/'

@login_required
def register(request):
    users = []  # Initialize an empty list to hold user data
    columns = []  # Initialize an empty list for dynamic columns

    user = request.user  # 현재 로그인된 사용자 가져오기
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                excel_file = request.FILES['file']
                # Read the Excel file
                df = pd.read_excel(excel_file)
                user_type = user.user_type

                # Define columns based on user type
                if user_type == 'S':
                    columns = [ '학년', '반', '번호', '이름', '전화번호' ]
                    if not (df.columns.values.tolist() == columns):
                        user_type_str = '교직원용' if user_type == 'S' else '일반 기관용'
                        raise ValueError(f"올바른 템플릿이 아닙니다. {user_type_str} 템플릿을 다운로드 받아서 다시 시도해주세요.")
                    for _, row in df.iterrows():
                        school_info, created = SchoolInfo.objects.update_or_create(
                            school_name=user.school.school_name,
                            defaults={
                                'contact_number': user.school.contact_number,
                                'address': user.school.address,
                            }
                        )
                        phone_number = extract_digits(str(row['전화번호']).strip().replace('-', ''))
                        if phone_number.startswith('10'):
                            phone_number = '0'+ phone_number
                        user_info, created = UserInfo.objects.update_or_create(
                            phone_number=phone_number,
                            defaults=dict(
                                school=school_info,
                                student_grade=row['학년'],
                                student_class=row['반'],
                                student_number=row['번호'],
                                student_name=row['이름'].strip().replace(' ', ''),
                                username=phone_number,
                                password=make_password(os.environ['DEFAULT_PASSWORD']),
                                user_type=user_type,
                                user_display_name=f"{school_info.school_name} {row['학년']}학년 {row['반']}반 {row['번호']}번 {row['이름']}",
                                organization=None,
                                department=None,
                            ),
                        )
                        users.append({
                            '학년': row['학년'],
                            '반': row['반'],
                            '번호': row['번호'],
                            '이름': row['이름'],
                            '전화번호': row['전화번호'],
                        })
                else:
                    columns = [ '부서명', '이름', '전화번호' ]
                    if not (df.columns.values.tolist() == columns):
                        user_type_str = '교직원용' if user_type == 'S' else '일반 기관용'
                        raise ValueError(f"올바른 템플릿이 아닙니다. {user_type_str} 템플릿을 다운로드 받아서 다시 시도해주세요.")
                    for _, row in df.iterrows():
                        organization_info, created = OrganizationInfo.objects.update_or_create(
                            organization_name=user.organization.organization_name,
                            defaults={
                                'contact_number': user.organization.contact_number,
                                'address': user.organization.address
                            },
                        )
                        phone_number = extract_digits(str(row['전화번호']).strip().replace('-', ''))
                        if phone_number.startswith('10'):
                            phone_number = '0'+ phone_number
                        user_info, created = UserInfo.objects.update_or_create(
                            phone_number=phone_number,
                            defaults=dict(
                                organization=organization_info,
                                department=row['부서명'].strip(),
                                student_name=row['이름'].strip().replace(' ', ''),
                                username=phone_number,
                                password=make_password(os.environ['DEFAULT_PASSWORD']),
                                user_type=user_type,
                                user_display_name=f"{organization_info.organization_name} {row['이름']}",
                                school=None,
                            ),
                        )
                        users.append({
                            '부서명': row['부서명'],
                            '이름': row['이름'],
                            '전화번호': row['전화번호'],
                        })
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)
    else:
        form = UploadFileForm()
    
    return render(request, 'register.html', {
        'form': form,
        'users': users,
        'columns': columns  # Pass dynamic columns
    })

from django.http import JsonResponse

def search_organization(request):
    query = request.GET.get('query', '')  # 사용자가 입력한 검색어를 가져옴
    if not query:
        return JsonResponse({'error': 'Query parameter is required'}, status=400)

    # 카카오 키워드 검색 API 호출
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {
        "Authorization": f"KakaoAK {os.environ['KAKAO_MAP_REST_API_KEY']}"
    }

    params = {
        "query": query,  # 검색어
        "size": 5  # 검색 결과 최대 5개
    }

    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    # API 호출 결과에서 필요 정보만 추출하여 반환
    results = []
    for document in data.get('documents', []):
        results.append({
            'name': document.get('place_name'),
            'address': document.get('address_name'),
            'contact': document.get('phone'),
            'x': document.get('x'),
            'y': document.get('y'),
        })

    return JsonResponse({'results': results})

# @login_required
def register_organization(request):
    if request.method == 'POST':
        user = request.user  # 현재 로그인된 사용자 가져오기
        data = json.loads(request.body)  # JSON 요청 본문을 파싱

        org_name = data.get('org_name')
        address = data.get('address')
        contact_number = data.get('contact_number')

        # 기관이 학교인지 확인
        if org_name.endswith('학교'):
            school_info, created = SchoolInfo.objects.update_or_create(
                school_name=org_name,
                defaults={'contact_number': contact_number, 'address': address}
            )
            user.school = school_info
            user.organization = None  # 학교 등록 시 다른 기관 정보 초기화
            user.department = None
            user.user_type = 'S'
        else:
            org_info, created = OrganizationInfo.objects.update_or_create(
                organization_name=org_name,
                defaults={'contact_number': contact_number, 'address': address}
            )
            user.organization = org_info
            user.school = None  # 다른 기관 등록 시 학교 정보 초기화
            user.department = None
            user.user_type = 'O'

        user.save()  # 사용자 정보 저장

        return JsonResponse({'message': '기관이 성공적으로 등록되었습니다.'}, status=200)

    return JsonResponse({'error': '잘못된 요청입니다.'}, status=400)

# @login_required
def get_organization_info(request):
    user_id = request.user.id  # 관리자 계정의 고유 id
    user = UserInfo.objects.get(id=user_id)
    
    org_info = {}
    if user.school is not None:
        org_info = {
            'org_name': user.school.school_name,
            'address': user.school.address,
            'contact': user.school.contact_number,
            'type': 'school'
        }
    elif user.organization is not None:
        org_info = {
            'org_name': user.organization.organization_name,
            'address': user.organization.address,
            'contact': user.organization.contact_number,
            'type': 'organization'
        }
    
    return JsonResponse(org_info)

def no_result(request):
    return render(request, 'no_result.html')

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
import re

@login_required
def report(request):
    user = request.user  # 현재 유저
    error_message = None
    selected_group = request.session.get('selected_group', None)  # 세션에서 그룹 정보 가져오기
    user_results = []

    if request.method == 'POST':
        selected_group = request.POST.get('group')

        if not selected_group:
            return redirect('report')  # PRG 패턴을 위해 POST 처리 후 리다이렉트
        else:
            # 선택된 그룹을 세션에 저장하여 리다이렉트 후에도 유지
            request.session['selected_group'] = selected_group
            return redirect('report')  # 리다이렉트 후 GET 요청으로 변환
        
    print(user.user_type)

    # GET 요청 처리 (리다이렉트 후 처리)
    if user.user_type == 'S':
        groups = UserInfo.objects.filter(school__school_name=user.school.school_name).values_list('student_grade', 'student_class', named=True).distinct().order_by('student_grade', 'student_class')
        groups = [f'{g.student_grade}학년 {g.student_class}반' for g in groups if ((g.student_grade is not None) & (g.student_class is not None))]

        if selected_group:
            # 정규 표현식으로 학년과 반 추출
            match = re.search(r"(\d+)학년 (\d+)반", selected_group)
            if match:
                users = UserInfo.objects.filter(student_grade=match.group(1), student_class=match.group(2)).order_by('student_number')

                # 각 user에 대한 검사 결과 여부를 확인하여 user_results에 추가
                for user in users:
                    body_result_queryset = BodyResult.objects.filter(
                        user_id=user.id,
                        image_front_url__isnull=False,
                        image_side_url__isnull=False,
                    )

                    analysis_valid = (len(body_result_queryset) > 0)

                    # user와 검사 결과 여부를 딕셔너리 형태로 추가
                    user_results.append({
                        'user': user,
                        'analysis_valid': analysis_valid
                    })
    elif user.user_type == 'O':
        groups = UserInfo.objects.filter(organization__organization_name=user.organization.organization_name).values_list('department', named=True).distinct().order_by('department')
        groups = [g.department for g in groups if ((g.department is not None))]

        if selected_group:
            users = UserInfo.objects.filter(department=selected_group).order_by('student_name')

            # 각 user에 대한 검사 결과 여부를 확인하여 user_results에 추가
            for user in users:
                body_result_queryset = BodyResult.objects.filter(
                    user_id=user.id,
                    image_front_url__isnull=False,
                    image_side_url__isnull=False,
                )

                analysis_valid = (len(body_result_queryset) > 0)

                user_results.append({
                    'user': user,
                    'analysis_valid': analysis_valid
                })

    if user.user_type == '' or len(user_results) == 0:
        return render(request, 'report.html', {
            'groups': groups,  # 그룹을 초기화
            'user_results': [],  # 테이블 초기화
            'selected_group': None,
            'error_message': error_message,
            'valid_count': 0,
            'total_users': 0,
            'progress_percentage': 0,
            'is_registered': len(groups) > 0,
        })
    

    # 분석 진행률 계산
    total_users = len(user_results)
    valid_count = sum(1 for result in user_results if result['analysis_valid'])

    if total_users > 0:
        progress_percentage = (valid_count / total_users) * 100
    else:
        progress_percentage = 0

    if len(groups) == 0 or total_users == 0:
        selected_group = None
        user_results = [] # 테이블 초기화
        selected_group = None
        valid_count = 0
        total_users = 0
        progress_percentage = 0
        error_message = '그룹이 선택되지 않았습니다. 그룹 선택 후 조회 해주세요!'

    return render(request, 'report.html', {
        'groups': groups,
        'user_results': user_results,
        'selected_group': selected_group,
        'error_message': error_message,
        'valid_count': valid_count,
        'total_users': total_users,
        'progress_percentage': progress_percentage,
        'is_registered': True,
    })

# Example report items
# TODO: get from actual DB
from django.shortcuts import render, get_object_or_404
from .models import UserInfo

import pytz

kst = pytz.timezone('Asia/Seoul')

@login_required
def report_detail(request, id):
    user_id = id
    return generate_report(request, user_id)

@login_required
def report_detail_protected(request):
    user_id = request.user.id
    return generate_report(request, user_id)

def generate_report(request, id):
    max_count = 20
    body_info_queryset = CodeInfo.objects.filter(group_id='01').order_by('seq_no')

    # Filter records from the last 3 months
    body_result_queryset = BodyResult.objects.filter(
        user_id=id, 
        image_front_url__isnull=False,
        image_side_url__isnull=False,
    )
    body_result_queryset = body_result_queryset.order_by('created_dt')[max(0, len(body_result_queryset)-int(max_count)):]


    if len(body_result_queryset) == 0:
        return render(request, 'no_result.html', status=404)
    body_result_latest = body_result_queryset[len(body_result_queryset)-1]

    report_items = []
    for body_info in body_info_queryset:
        trend_data = []
        is_paired = False
        for body_result in body_result_queryset:
            body_code_id_ = body_info.code_id
            alias = body_info.code_id
            if 'leg_alignment' in body_code_id_ or 'back_knee' in body_code_id_  or 'scoliosis' in body_code_id_:
                is_paired = True
                if 'scoliosis' in body_code_id_:
                    code_parts = body_code_id_.split('_')
                    pair_names = ['shoulder', 'hip']
                    paired_body_code_id_list = [ '_'.join([code_parts[0], pair, code_parts[2]]) for pair in pair_names ]
                    
                else:
                    pair_names = ['left', 'right']
                    paired_body_code_id_list = [ f'{pair}_' + '_'.join(body_code_id_.split('_')[1:]) for pair in pair_names ]

                if 'leg_alignment' in body_code_id_:
                    alias = 'o_x_legs'
                if 'back_knee' in body_code_id_:
                    alias = 'knee_angle'
                if 'scoliosis' in body_code_id_:
                    alias = 'spinal_imbalance'
                
                trend_samples = [getattr(body_result, paired_body_code_id_list[0]),
                                getattr(body_result, paired_body_code_id_list[1]),
                                body_result.created_dt.strftime('%Y-%m-%d %H:%M:%S')]
            else:
                trend_samples = [getattr(body_result, body_code_id_), body_result.created_dt.strftime('%Y-%m-%d %H:%M:%S')]
            trend_data.append(trend_samples)

        if is_paired:
            result_val1, result_val2, *_ = trend_data[-1]
            result1 = None
            if result_val1 is not None:
                result1 = round(result_val1, 2)
            result2 = None
            if result_val2 is not None:
                result2 = round(result_val2, 2)

            description_list = []
            unit_name = body_info.unit_name
            normal_range = [body_info.normal_min_value, body_info.normal_max_value]
            for i, val in enumerate([result1, result2]):
                if alias == 'o_x_legs':
                    title = body_info.code_name.replace('(좌)', '').replace('(우)', '')
                    metric = '각도 [°]'
                    pair_name = '왼쪽' if i == 0 else '오른쪽'
                    if val:
                        if normal_range[0] < val < normal_range[1]:
                            description = '양호'
                        else:
                            description = 'O 다리 의심' if val < 180 else 'X 다리 의심'
                    else:
                        description = "측정값 없음"
                if alias == 'knee_angle':
                    title = body_info.code_name.replace('(좌)', '').replace('(우)', '')
                    metric = '각도 [°]'
                    pair_name = '왼쪽' if i == 0 else '오른쪽'
                    if val:
                        if normal_range[0] < val < normal_range[1]:
                            description = '양호'
                        else:
                            description = '반장슬 의심'
                    else:
                        description = "측정값 없음"
                if alias == 'spinal_imbalance':
                    title = '척추 불균형'
                    metric = '척추 기준 좌우 비율 차이 [%]'
                    pair_name = '척추-어깨' if i == 0 else '척추-골반'
                    if val:
                        if normal_range[0] < val < normal_range[1]:
                            description = '양호'
                        else:
                            description = '왼쪽 편향' if val < 0 else '오른쪽 편향'
                    else:
                        description = "측정값 없음"

                description_list.append(f'{pair_name} : ' + description)

            if not result1:
                result1 = "?"
            else:
                status_desc = ""
                if alias == 'spinal_imbalance':
                    if result1 < 0:
                        status_desc += "왼쪽으로" + " "
                    else:
                        status_desc += "오른쪽으로" + " "
                result1  = f'{status_desc}{abs(result1)}{unit_name}'
            
            if not result2:
                result2 = "?"
            else:
                status_desc = ""
                if alias == 'spinal_imbalance':
                    if result2 < 0:
                        status_desc += "왼쪽으로" + " "
                    else:
                        status_desc += "오른쪽으로" + " "
                result2  = f'{status_desc}{abs(result2)}{unit_name}'
            
            if alias == 'spinal_imbalance':
                result = f'· 척추-어깨: {result1}의 편향, · 척추-골반: {result2}의 편향'
            else:
                result = f'{result1} / {result2}'
            if all([ i['title'] != title for i in report_items ]):
                report_items.append({
                    'title': title,
                    'alias': alias,
                    'result': result,
                    'description' : description_list,
                    'description_list': True,
                    'metric': metric,
                    'summary': [ re.sub(r'\(.*?\)', '', x) for x in description_list ],
                    'normal_range': [body_info.normal_min_value, body_info.normal_max_value],
                    'value_range': [body_info.min_value, body_info.max_value],
                    'trend': trend_data,
                    'sections': { getattr(body_info, f'title_{name}'): getattr(body_info, name) for name in ['outline', 'risk', 'improve', 'recommended']  }
                })
        else:
            result_val = getattr(body_result_latest, body_info.code_id)
            result = None
            if result_val is not None:
                result = round(result_val, 2)
            unit_name = body_info.unit_name
            normal_range = [body_info.normal_min_value, body_info.normal_max_value]
            if 'angle' in alias:
                if result:
                    description = '왼쪽으로' if result < 0 else '오른쪽으로'
                else:
                    description = "측정값 없음"
                metric = '각도 [°]'
            
            if alias == 'forward_head_angle':
                if result:
                    description = '양호' if normal_range[0] < result < normal_range[1] else '거북목 진행형'
                else:
                    description = "측정값 없음"

            if alias == 'leg_length_ratio':
                if result:
                    description = '왼쪽이 더 짧음' if result < 0 else '오른쪽이 더 짧음'
                else:
                    description = "측정값 없음"
                metric = '다리 길이 차이 [%]'

            if not result:
                result = "?"
            else:
                status_desc = ""
                if normal_range[0] < result < normal_range[1]:
                    status_desc += " " + "(정상)"
                else:
                    status_desc += " " + "(유의)"

                result = f'{abs(result)}{unit_name}{status_desc}' # show absolute value
            report_items.append({
                'title': body_info.code_name,
                'alias': alias,
                'result': result,
                'description' : description,
                'description_list': False,
                'metric': metric,
                'summary': re.sub(r'\(.*?\)', '', description),
                'normal_range': normal_range,
                'value_range': [body_info.min_value, body_info.max_value],
                'trend': trend_data,
                'sections': { getattr(body_info, f'title_{name}'): getattr(body_info, name) for name in ['outline', 'risk', 'improve', 'recommended']  }
            })

    user = get_object_or_404(UserInfo, id=id)

    if not report_items:
        return render(request, '404.html', status=404)

    # Prepare trend data for each report item
    trend_data_dict = {}
    for item in report_items:
        alias = item['alias']
        trend_data = item['trend']
        
        if alias in ['spinal_imbalance', 'o_x_legs', 'knee_angle']:
            trend_data_dict[alias] = {
                'val1': [value[0] for value in trend_data],  # 왼쪽 또는 상부
                'val2': [value[1] for value in trend_data],  # 오른쪽 또는 하부
                'dates': [value[2] for value in trend_data],  # 날짜 (세 번째 요소)
                'part': ['어깨', '골반'] if alias == 'spinal_imbalance' else ['왼쪽', '오른쪽']
            }
        else:
            trend_data_dict[alias] = {
                'values': [value[0] for value in trend_data],
                'dates': [value[1] for value in trend_data]
            }

    created_dt = body_result_latest.created_dt.strftime('%Y%m%dT%H%M%S%f')

    context = {
        'user': user,
        'report_items': report_items,
        'trend_data_dict': trend_data_dict,
        'image_front_url': generate_presigned_url(file_keys=['front', created_dt]),
        'image_side_url': generate_presigned_url(file_keys=['side', created_dt]),
    }

    return render(request, 'report_detail.html', context)

def policy(request):
    return render(request, 'policy.html')

@swagger_auto_schema(
    method='post',
    operation_description="Create a new gait analysis result record",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'session_key': openapi.Schema(type=openapi.TYPE_STRING, description='Session key for the user'),
            'gait_data': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'velocity': openapi.Schema(type=openapi.TYPE_NUMBER, description='Velocity'),
                    'cadence': openapi.Schema(type=openapi.TYPE_NUMBER, description='Cadence'),
                    'cycle_time_l': openapi.Schema(type=openapi.TYPE_NUMBER, description='Cycle time left'),
                    'cycle_time_r': openapi.Schema(type=openapi.TYPE_NUMBER, description='Cycle time right'),
                    'stride_len_l': openapi.Schema(type=openapi.TYPE_NUMBER, description='Stride length left'),
                    'stride_len_r': openapi.Schema(type=openapi.TYPE_NUMBER, description='Stride length right'),
                    'supp_base_l': openapi.Schema(type=openapi.TYPE_NUMBER, description='Support base left'),
                    'supp_base_r': openapi.Schema(type=openapi.TYPE_NUMBER, description='Support base right'),
                    'swing_perc_l': openapi.Schema(type=openapi.TYPE_NUMBER, description='Swing percentage left'),
                    'swing_perc_r': openapi.Schema(type=openapi.TYPE_NUMBER, description='Swing percentage right'),
                    'stance_perc_l': openapi.Schema(type=openapi.TYPE_NUMBER, description='Stance percentage left'),
                    'stance_perc_r': openapi.Schema(type=openapi.TYPE_NUMBER, description='Stance percentage right'),
                    'd_supp_perc_l': openapi.Schema(type=openapi.TYPE_NUMBER, description='Double support percentage left'),
                    'd_supp_perc_r': openapi.Schema(type=openapi.TYPE_NUMBER, description='Double support percentage right'),
                    'toeinout_l': openapi.Schema(type=openapi.TYPE_NUMBER, description='Toe-in/out angle left'),
                    'toeinout_r': openapi.Schema(type=openapi.TYPE_NUMBER, description='Toe-in/out angle right'),
                    'stridelen_cv_l': openapi.Schema(type=openapi.TYPE_NUMBER, description='Stride length coefficient of variation left'),
                    'stridelen_cv_r': openapi.Schema(type=openapi.TYPE_NUMBER, description='Stride length coefficient of variation right'),
                    'stridetm_cv_l': openapi.Schema(type=openapi.TYPE_NUMBER, description='Stride time coefficient of variation left'),
                    'stridetm_cv_r': openapi.Schema(type=openapi.TYPE_NUMBER, description='Stride time coefficient of variation right'),
                    'score': openapi.Schema(type=openapi.TYPE_NUMBER, description='Gait score'),
                }
            ),
        },
        required=['session_key', 'gait_data'],
    ),
    responses={
        200: 'OK; created_gait_result successfully',
        400: 'Bad Request; (session_key | gait_data) is not provided in the request body',
        401: 'Unauthorized; incorrect user or password',
        404: 'Not Found; session_key is not found',
        500: 'Internal Server Error'
    },
    tags=['analysis results']
)
@api_view(['POST'])
def create_gait_result(request):
    session_key = request.data.get('session_key')
    if not session_key:
        return Response({'data': {'message': 'session_key_required', 'status': 400}})
    gait_data = request.data.get('gait_data')
    if not gait_data:
        return Response({'data': {'message': 'gait_data_required', 'status': 400}})

    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response({'data': {'message': 'session_key_not_found', 'status': 404}})

    try:
        user_info = UserInfo.objects.get(id=session_info.user_id)
    except UserInfo.DoesNotExist:
        return Response({'data': {'message': 'user_not_found', 'status': 401}})

    # Retrieve or create a fixed "null school" instance
    null_school, created = SchoolInfo.objects.get_or_create(
        id=-1,
        school_name='N/A',
        contact_number='N/A'
    )

    data = gait_data.copy()

    if user_info.school is None:
        data['school'] = null_school.id
    else:
        data['school'] = user_info.school.id
    data['user'] = user_info.id
    serializer = GaitResultSerializer(data=data)

    if serializer.is_valid():
        serializer.save()
        return Response({'data': {'message': 'created_gait_result', 'status': 200}})
    else:
        return Response({'data': {'message' : serializer.errors, 'status': 500}})


@swagger_auto_schema(
    method='get',
    operation_description="Retrieve latest gait analysis results by session key",
    manual_parameters=[
        openapi.Parameter('session_key', openapi.IN_QUERY, description="Session key for the current user", type=openapi.TYPE_STRING, required=True),
        openapi.Parameter('count', openapi.IN_QUERY, description="The number of items to retrieve from latest results", type=openapi.TYPE_INTEGER, required=False),
        openapi.Parameter('start_date', openapi.IN_QUERY, description="The start date for filtering results (format: YYYY-MM-DD)", type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('end_date', openapi.IN_QUERY, description="The end date for filtering results (format: YYYY-MM-DD)", type=openapi.TYPE_STRING, required=False),
    ],
    responses={
        200: GaitResponseSerializer,
        400: 'Bad Request; session_key is not provided in the request body',
        401: 'Unauthorized; incorrect user or password',
        404: 'Not Found; session_key or gait result is not found',
    },
    tags=['analysis results']
)
@api_view(['GET'])
def get_gait_result(request):
    if request.user.id is None:
        session_key = request.query_params.get('session_key')
        if not session_key:
            return Response({'data': {'message': 'session_key_required', 'status': 400}})

        try:
            session_info = SessionInfo.objects.get(session_key=session_key)
        except SessionInfo.DoesNotExist:
            return Response({'data': {'message': 'session_key_not_found', 'status': 404}})

        try:
            user_info = UserInfo.objects.get(id=session_info.user_id)
        except UserInfo.DoesNotExist:
            return Response({'data': {'message': 'user_not_found', 'status': 401}})
        user_id = user_info.id
    else:
        # for JWT authorized user
        user_id = request.user.id

    start_date = request.query_params.get('start_date', None)
    end_date = request.query_params.get('end_date', None)

    if start_date is not None or end_date is not None:
        # Ensure start_date and end_date are datetime objects
        if not isinstance(start_date, datetime):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if not isinstance(end_date, datetime):
            end_date = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        gait_results = GaitResult.objects.filter(user_id=user_id, created_dt__range=(start_date, end_date)).order_by('-created_dt')
    else:
        gait_results = GaitResult.objects.filter(user_id=user_id).order_by('-created_dt')
        # id 값이 들어오면 해당 검사일자 이전 데이터를 가져온다.(240903 BS)
        id = request.query_params.get('id', None)
        if id is not None:
            current_result = GaitResult.objects.filter(user_id=user_id, id=id).first()
            if not current_result:
                return Response({'data': {"message": "gait_result_not_found"}})
            gait_results = GaitResult.objects.filter(
                user_id=user_id,
                created_dt__lte=current_result.created_dt
            ).order_by('-created_dt')

    if not gait_results.exists():
        return Response({'data': {"message": "gait_result_not_found", "status": 404}})
    count = request.query_params.get('count', None)
    if count is not None:
        gait_results = gait_results.all()[:int(count)]

    # Serialize the GaitResult objects
    serializer = GaitResultSerializer(gait_results, many=True)

    return Response({'data': serializer.data, 'message': 'OK', 'status': 200})

@swagger_auto_schema(
    method='get',
    operation_description="Get information of gait & body analysis",
    manual_parameters=[
        openapi.Parameter('name', openapi.IN_QUERY, description="Name of analysis (i.e., gait or body)", type=openapi.TYPE_STRING, required=True),
    ],
    responses={
        200: 'OK',
        400: 'Bad Request; invalid name',
    },
    tags=['analysis results']
)
@api_view(['GET'])
def get_info(requests):
    name = requests.query_params.get('name')
    if name == 'body':
        group_id = '01'
    elif name == 'gait':
        group_id = '02'
    else:
        return Response({'data': {'message': 'Bad Request. Invalid name!', 'status': 400}})
    codeinfo = CodeInfo.objects.filter(group_id=group_id)
    info = {}
    for item in codeinfo.values():
        info[item['code_id']] = {
            'value_range_min': codeinfo.get(code_id=item['code_id']).min_value,
            'value_range_max': codeinfo.get(code_id=item['code_id']).max_value,
            'normal_range_min': codeinfo.get(code_id=item['code_id']).normal_min_value,
            'normal_range_max': codeinfo.get(code_id=item['code_id']).normal_max_value,
            'caution_range_min': codeinfo.get(code_id=item['code_id']).caution_min_value,
            'caution_range_max': codeinfo.get(code_id=item['code_id']).caution_max_value,
            'unit_name': item['unit_name'],
        }
        if name == 'body':
            info[item['code_id']].update({
                'outline': item['outline'],
                'risk': item['risk'],
                'improve': item['improve'],
                'recommended': item['recommended'],
                'title': item['title'],
                'title_outline': item['title_outline'],
                'title_risk': item['title_risk'],
                'title_improve': item['title_improve'],
                'title_recommended': item['title_recommended'],
            })
        if name == 'gait':
            info[item['code_id']].update({
                'display_ticks': codeinfo.get(code_id=item['code_id']).display_ticks
            })

    return Response({'data': info, 'message': 'OK', 'status': 200})
    
@swagger_auto_schema(
    method='post',
    operation_description="Create a new body result record",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'session_key': openapi.Schema(type=openapi.TYPE_STRING, description='Session key for the user'),
            'body_data': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'face_level_angle': openapi.Schema(type=openapi.TYPE_NUMBER, description='Face level angle'),
                    'shoulder_level_angle': openapi.Schema(type=openapi.TYPE_NUMBER, description='Shoulder level angle'),
                    'hip_level_angle': openapi.Schema(type=openapi.TYPE_NUMBER, description='Hip level angle'),
                    'leg_length_ratio': openapi.Schema(type=openapi.TYPE_NUMBER, description='Leg length ratio'),
                    'left_leg_alignment_angle': openapi.Schema(type=openapi.TYPE_NUMBER, description='Left leg alignment angle'),
                    'right_leg_alignment_angle': openapi.Schema(type=openapi.TYPE_NUMBER, description='Right leg alignment angle'),
                    'left_back_knee_angle': openapi.Schema(type=openapi.TYPE_NUMBER, description='Left back knee angle'),
                    'right_back_knee_angle': openapi.Schema(type=openapi.TYPE_NUMBER, description='Right back knee angle'),
                    'forward_head_angle': openapi.Schema(type=openapi.TYPE_NUMBER, description='Forward head angle'),
                    'scoliosis_shoulder_ratio': openapi.Schema(type=openapi.TYPE_NUMBER, description='Scoliosis shoulder ratio'),
                    'scoliosis_hip_ratio': openapi.Schema(type=openapi.TYPE_NUMBER, description='Scoliosis hip ratio'),
                    }),
            'image_front': openapi.Schema(type=openapi.TYPE_STRING, description='base64 encoded bytes of the front image'),
            'image_side': openapi.Schema(type=openapi.TYPE_STRING, description='base64 encoded bytes of the side image'),
        },
        required=['session_key', 'body_data'],  # Add any required fields here
    ),
    responses={
        200: 'OK; created_body_result successfully',
        400: 'Bad Request; session_key is not provided in the request body',
        401: 'Unauthorized; incorrect user or password',
        404: 'Not Found; session_key is not found',
        500: 'Internal Server Error'
    },
    tags=['analysis results']
)
@api_view(['POST'])
def create_body_result(request):
    session_key = request.data.get('session_key')
    if not session_key:
        return Response({'data': {'message': 'session_key_required', 'status': 400}})
    
    body_data = request.data.get('body_data')
    if not body_data:
        return Response({'data': {'message': 'body_data_required', 'status': 400}})

    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response({'data' : {'message': 'session_key_not_found', 'status': 404}})

    try:
        user_info = UserInfo.objects.get(id=session_info.user_id)
    except UserInfo.DoesNotExist:
        return Response({'data': {'message': 'user_not_found', 'status': 401}})

    # Retrieve or create a fixed "null school" instance
    null_school, created = SchoolInfo.objects.update_or_create(
        id=-1,
        defaults=dict(
            school_name='N/A',
            contact_number='N/A'
        )
    )

    data = body_data.copy()
    if user_info.school is None:
        data['school'] = null_school.id
    else:
        data['school'] = user_info.school.id
    data['user'] = user_info.id
    serializer = BodyResultSerializer(data=data)

    if serializer.is_valid():
        serializer.save()
        created_dt = dt.strptime(serializer.data['created_dt'], '%Y-%m-%dT%H:%M:%S.%f').strftime('%Y%m%dT%H%M%S%f')
        image_front_bytes = request.data.get('image_front', None)
        image_side_bytes = request.data.get('image_side', None)
        try:
            # S3에 이미지를 업로드
            if image_front_bytes:
                upload_image_to_s3(image_front_bytes, file_keys=['front', created_dt])
            if image_side_bytes:
                upload_image_to_s3(image_side_bytes, file_keys=['side', created_dt])
        except Exception as e:
            return Response({'data': {'message': str(e), 'status': 500}})
        return Response({'data': {'message': 'created_body_result', 'status': 200}})
    else:
        return Response({'data': {'message' : serializer.errors, 'status': 500}})

@swagger_auto_schema(
    method='get',
    operation_description="Retrieve latest body analysis results by session key",
    manual_parameters=[
        openapi.Parameter('session_key', openapi.IN_QUERY, description="Session key for the current user", type=openapi.TYPE_STRING, required=True),
        openapi.Parameter('count', openapi.IN_QUERY, description="The number of items to retrieve from latest results", type=openapi.TYPE_INTEGER, required=False),
        openapi.Parameter('start_date', openapi.IN_QUERY, description="The start date for filtering results (format: YYYY-MM-DD)", type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('end_date', openapi.IN_QUERY, description="The end date for filtering results (format: YYYY-MM-DD)", type=openapi.TYPE_STRING, required=False),
    ],
    responses={
        200: BodyResultSerializer(many=True),
        400: 'Bad Request; session_key is not provided in the request body',
        401: 'Unauthorized; incorrect user or password',
        404: 'Not Found; session_key is not found',
        500: 'Internal Server Error'
    },
    tags=['analysis results']
)
@api_view(['GET'])
def get_body_result(request):
    if request.user.id is None:
        session_key = request.query_params.get('session_key')
        if not session_key:
            return Response({'data': {'message': 'session_key_required', 'status': 400}})

        try:
            session_info = SessionInfo.objects.get(session_key=session_key)
        except SessionInfo.DoesNotExist:
            return Response({'data': {'message': 'session_key_not_found', 'status': 404}})

        try:
            user_info = UserInfo.objects.get(id=session_info.user_id)
        except UserInfo.DoesNotExist:
            return Response({'data': {'message': 'user_not_found', 'status': 401}})
        user_id = user_info.id
    else:
        # for JWT authorized user
        user_id = request.user.id
    start_date = request.query_params.get('start_date', None)
    end_date = request.query_params.get('end_date', None)

    if start_date is not None or end_date is not None:
        # Ensure start_date and end_date are datetime objects
        if not isinstance(start_date, datetime):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if not isinstance(end_date, datetime):
            end_date = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        body_results = BodyResult.objects.filter(user_id=user_id, created_dt__range=(start_date, end_date)).order_by('-created_dt')
    else:
        body_results = BodyResult.objects.filter(user_id=user_id).order_by('-created_dt')
        id = request.query_params.get('id', None)
        if id is not None:
            body_results = body_results.filter(id=id)

    if not body_results.exists():
        return Response({'data': {"message": "body_result_not_found", "status": 404}})

    count = request.query_params.get('count', None)
    if count is not None:
        body_results = body_results.all()[:int(count)]

    # 수정된 body_results를 리스트로 저장
    updated_body_results = []

    for body_result in body_results:
        created_dt = body_result.created_dt.strftime('%Y%m%dT%H%M%S%f')
        # Presigned URL 생성 (일정 시간 동안)
        body_result.image_front_url = generate_presigned_url(file_keys=['front', created_dt])
        body_result.image_side_url = generate_presigned_url(file_keys=['side', created_dt])

        if body_result.image_front_url is not None and requests.get(body_result.image_front_url).status_code in [400, 404]:
            body_result.image_front_url = None
        if body_result.image_side_url is not None and requests.get(body_result.image_side_url).status_code in [400, 404]:
            body_result.image_side_url = None

        updated_body_results.append(body_result)

    # 모든 객체를 한 번에 업데이트
    BodyResult.objects.bulk_update(updated_body_results, ['image_front_url', 'image_side_url'])

    # Serialize the BodyResult objects
    serializer = BodyResultSerializer(body_results, many=True)

    return Response({'data': serializer.data, 'message': 'OK', 'status': 200})


@swagger_auto_schema(
    method='post',
    operation_description="Login to the kiosk using kiosk_id, returning session key",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'kiosk_id': openapi.Schema(type=openapi.TYPE_STRING, description='Kiosk identifier'),
        },
        required=['kiosk_id'],
    ),
    responses={
        200: openapi.Response('Success', openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'data': 
                        openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'session_key': openapi.Schema(type=openapi.TYPE_STRING, description='Generated session key'),
                            }),
        })  ),
        400: 'Bad Request; kiosk_id is not provided in the request body',
    },
    tags=['kiosk']
)
@api_view(['POST'])
def login_kiosk(request):
    kiosk_id = request.data.get('kiosk_id')
    if not kiosk_id:
        return Response({'data': {'message': 'kiosk_id_required', 'status': 400}})
    
    # POST 메소드를 사용하여 키오스크 로그인 요청 처리
    session_key = uuid.uuid4().hex
    SessionInfo.objects.update_or_create(
        session_key=session_key,
        kiosk_id=kiosk_id,
    )

    return Response({'data' : {'session_key': session_key, 'message': 'success', 'status': 200}})


@swagger_auto_schema(
    method='post',
    operation_description="Login to the kiosk using session key, phone number, and password",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'session_key': openapi.Schema(type=openapi.TYPE_STRING, description='Session key'),
            'phone_number': openapi.Schema(type=openapi.TYPE_STRING, description='Phone number'),
            'password': openapi.Schema(type=openapi.TYPE_STRING, description='Password'),
        },
        required=['session_key', 'phone_number', 'password'],
    ),
    responses={
        200: 'Login Success',
        400: 'Bad Request; (session_key | phone_number | password) is not provided in the request body',
        401: 'Unauthorized; incorrect user or password',
        404: 'Not Found; session_key is not found',
    },
    tags=['kiosk']
)
@api_view(['POST'])
def login_kiosk_id(request):
    session_key = request.data.get('session_key')
    if not session_key:
        return Response({'data': {'message': 'session_key_required', 'status': 400}})
    
    phone_number = request.data.get('phone_number')
    password = request.data.get('password')
    
    if not phone_number or not password:
        return Response({'data': {'message': 'phone_number_and_password_required', 'status': 400}})

    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response({'data': {'message': 'session_key_not_found', 'status': 404}})

    try:
        user_info = UserInfo.objects.get(phone_number=phone_number)
    except UserInfo.DoesNotExist:
        return Response({'data': {"message": "user_not_found", 'status': 401}})
    
    if not check_password(password, user_info.password) and (phone_number == user_info.phone_number):
        return Response({'data': {'message': 'incorrect_password', 'status': 401}, 'message': 'incorrect_password', 'status': 401})
    else:
        session_info.user_id = user_info.id
        session_info.save()
        return Response({'data' : {'message': 'login_success', 'status': 200}, 'message': 'login_success', 'status': 200})

@swagger_auto_schema(
    method='get',
    operation_description="Retrieve user information by session key",
    manual_parameters=[
        openapi.Parameter('session_key', openapi.IN_QUERY, description="Session key", type=openapi.TYPE_STRING),
    ],
    responses={
        200: openapi.Response('Success', openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'user_info': openapi.Schema(type=openapi.TYPE_OBJECT, description='User information'),
                                'status': openapi.Schema(type=openapi.TYPE_INTEGER, description='Status Code'),
                            }
                        )})),
        400: 'Bad Request; session_key is not provided in the request body',
        401: 'Unauthorized; incorrect user or password',
        404: 'Not Found; session_key is not found',
    },
    tags=['kiosk']
)
@api_view(['GET'])
def get_userinfo_session(request):
    session_key = request.query_params.get('session_key')
    if not session_key:
        return Response({'data': {'message': 'session_key_required', 'status': 400}})
    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response({'data': {'message': 'session_key_not_found', 'status': 404}})
    
    try:
        user_info = UserInfo.objects.get(id=session_info.user_id)
    except UserInfo.DoesNotExist:
        return Response({"data": {"message": "user_not_found", "status": 401}})
    
    return Response({'data' : parse_userinfo(user_info), 'message': 'OK', 'status': 200})

@swagger_auto_schema(
    method='post',
    operation_description="End the session using session key",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'session_key': openapi.Schema(type=openapi.TYPE_STRING, description='Session key'),
        },
        required=['session_key'],
    ),
    responses={
        200: 'Success',
        400: 'Bad Request; (session_key | phone_number | password) is not provided in the request body',
        404: 'Not Found; session_key is not found',
    },
    tags=['kiosk']
)
@api_view(['POST'])
def end_session(request):
    session_key = request.data.get('session_key')
    if not session_key:
        return Response({'data': {'message': 'session_key_required', 'status': 400}})
    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response({'data': {'message': 'session_key_not_found', 'status': 404}})
    
    session_info.delete()
    return Response({'data' : {'message': 'session_closed', 'status': 200}, 'message': 'session_closed', 'status': 200})
