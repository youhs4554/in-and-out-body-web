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
from .helpers import extract_digits, generate_presigned_url, parse_userinfo, upload_image_to_s3, verify_image, \
    calculate_normal_ratio, create_excel_report
from .models import BodyResult, CodeInfo, GaitResult, OrganizationInfo, SchoolInfo, UserInfo, SessionInfo, UserHist
from .forms import UploadFileForm, CustomPasswordChangeForm, CustomUserCreationForm, CustomPasswordResetForm
from .serializers import BodyResultSerializer, GaitResponseSerializer, GaitResultSerializer

from django.db.models import Min, Max, Exists, OuterRef, Count
from django.db.models.functions import ExtractYear
from django.db import transaction

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from datetime import datetime as dt
from collections import defaultdict
from django.http import JsonResponse, HttpResponse
from urllib.parse import quote

# 응답코드 관련
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND, \
    HTTP_500_INTERNAL_SERVER_ERROR


def home(request):
    if request.user.is_authenticated:
        return redirect('main')
    else:
        return redirect('login')


from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.urls import reverse_lazy


@login_required
def main(request):  # 추후 캐싱 기법 적용
    user = request.user
    context = {}

    # 기관 등록 여부 확인
    has_affiliation = bool(user.school or user.organization)

    # 기관이 등록된 경우
    if has_affiliation:
        # 학교
        if user.user_type == 'S':
            # 유저 소속
            user_affil = user.school.school_name

            # 총 회원 수
            members = UserInfo.objects.filter(
                school__school_name=user.school.school_name
            ).count()

            # 총 검사 수
            total_results = BodyResult.objects.filter(
                user__school__school_name=user.school.school_name,
                image_front_url__isnull=False,
                image_side_url__isnull=False
            ).count()

            # 이번달 검사 수
            current_month_results = BodyResult.objects.filter(
                user__school__school_name=user.school.school_name,
                image_front_url__isnull=False,
                image_side_url__isnull=False,
                created_dt__month=dt.now().month
            ).count()

            # 미완료 검사 수
            # 소속된 학교의 모든 사용자 중 검사를 받지 않은 사용자 수
            pending_tests = UserInfo.objects.filter(
                school__id=user.school.id,
                year=dt.now().year
            ).exclude(
                id__in=BodyResult.objects.filter(
                    user__school__id=user.school.id,
                    image_front_url__isnull=False,
                    image_side_url__isnull=False,
                    created_dt__year=dt.now().year
                ).values('user_id')
            ).count()

            # 학교의 그룹 정보 가져오기
            groups = UserInfo.objects.filter(
                school__school_name=user.school.school_name,
                year=dt.now().year
            ).values('student_grade', 'student_class').annotate(student_count=Count('id')).order_by('student_grade',
                                                                                                    'student_class')

            # 학년-반 별 구성원 수를 포함하는 딕셔너리 초기화
            group_structure = {}

            # 학년별로 반 정보 구조화 및 구성원 수 추가
            for group in groups:
                if group['student_grade'] and group['student_class']:  # None 값 제외
                    grade = str(group['student_grade'])
                    class_num = str(group['student_class'])

                    # 학년이 group_structure에 없으면 초기화
                    if grade not in group_structure:
                        group_structure[grade] = {}

                    # 반이 학년의 딕셔너리에 없으면 초기화
                    if class_num not in group_structure[grade]:
                        group_structure[grade][class_num] = 0  # 초기화

                    # 구성원 수 증가
                    group_structure[grade][class_num] = group['student_count']  # 쿼리에서 가져온 학생 수로 설정

            print(group_structure)

        else:
            # 유저 소속 - 기관
            user_affil = user.organization.organization_name

            # 총 회원 수
            members = UserInfo.objects.filter(
                organization__id=user.organization.id
            ).count()

            # 총 검사 수
            total_results = BodyResult.objects.filter(
                user__organization__id=user.organization.id,
                image_front_url__isnull=False,
                image_side_url__isnull=False
            ).count()

            # 이번달 검사 수
            current_month_results = BodyResult.objects.filter(
                user__organization__organization_name=user.organization.organization_name,
                image_front_url__isnull=False,
                image_side_url__isnull=False,
                created_dt__month=dt.now().month
            ).count()

            # 미완료 검사 수
            # 소속된 기관의 모든 사용자 중 검사를 받지 않은 사용자 수(문제점 : 작년도 유저까지 포함될 수 있음 - 2023년 가입인데 2024년에 갱신이 안된 경우)
            # userInfo에서 organization__id=user.organization.id인 것 들 중에 BodyResult에 있는 user_id와 일치하지 않는 것들을 제외하고 count
            pending_tests = UserInfo.objects.filter(
                organization__id=user.organization.id
            ).exclude(
                id__in=BodyResult.objects.filter(
                    user_id=OuterRef('id'),
                    image_front_url__isnull=False,
                    image_side_url__isnull=False
                ).values('user_id')
            ).count()

            # 부서 : 구성원 수 구조화
            group_structure = UserInfo.objects.filter(
                organization__organization_name=user.organization.organization_name
            ).values('department').annotate(count=Count('id')).order_by('department')

            # None 결과(부서에 속해있지 않은) 제외한 딕셔너리로 변환
            group_structure = {item['department']: item['count'] for item in group_structure if
                               item['department'] is not None}

            # 검사 완료율 계산 (퍼센트)
            # test_completion_rate = ((members - pending_tests) / members * 100) if members > 0 else 0

        year = dt.now().year
        context.update({
            'user_affil': user_affil,
            'total_members': members,
            'total_results': total_results,
            'current_month_results': current_month_results,
            'user_type': user.user_type,
            'pending_tests': pending_tests,
            'group_structure': group_structure,
            'year': year,
        })

    context['has_affiliation'] = has_affiliation
    return render(request, 'main.html', context)


def org_register(request):
    return render(request, 'org_register.html')


@login_required
def member_register(request):
    existing_member = 0  # 기존 회원 카운팅
    new_member = 0  # 신규 회원 카운팅

    user_id = request.user.id

    user = UserInfo.objects.get(id=user_id)

    type = user.user_type

    if type not in ['S', 'O']:  # 'G' == 게스트(일반 사용자)
        return render(request, 'main.html', context={"message": "먼저 기관을 등록해주세요."})  # 'home' URL로 리디렉션

    orgName = user.organization.organization_name if user.organization else user.school.school_name  # 기관명(학교명) 가져오기

    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                excel_file = request.FILES['file']
                df = pd.read_excel(excel_file,
                                   dtype={'전화번호': str})  # 전화번호를 문자열로 읽음( 01000010001, 010-0001-0001) 다중 처리 위해서

                # 컬럼 검증
                expected_columns = ['학년', '반', '번호', '이름', '전화번호'] if type == 'S' else ['부서명', '이름', '전화번호']
                if not all(col in df.columns for col in expected_columns):
                    user_type_str = '교직원용' if type == 'S' else '일반 기관용'
                    raise ValueError(f"올바른 템플릿이 아닙니다. {user_type_str} 템플릿을 다운로드 받아서 다시 시도해주세요.")

                # NaN 값을 가진 행 제거
                df = df.dropna(subset=['이름', '전화번호'])  # 이름과 전화번호는 필수값으로 처리

                # 데이터 전처리
                users = []
                for _, row in df.iterrows():
                    user_data = {}
                    for col in expected_columns:
                        if pd.notna(row[col]):
                            # 숫자형 컬럼 처리
                            if col in ['학년', '반', '번호'] and pd.notna(row[col]):
                                user_data[col] = str(int(row[col]))  # float를 int로 변환 후 문자열로
                            else:
                                user_data[col] = str(row[col]).strip()

                    if len(user_data) == len(expected_columns):  # 모든 필수 컬럼이 있는 경우만 추가
                        users.append(user_data)

                # 저장 요청인 경우
                if request.POST.get('save') == 'true':
                    with transaction.atomic():  # 트랜잭션 시작
                        for user_data in users:
                            phone_number = extract_digits(str(user_data['전화번호']).replace('-', ''))
                            if phone_number.startswith('10'):  # 10 으로 시작하는 경우 0 추가(int로 입력이 들어오면 맨 앞에 0이 빠지기 때문)
                                phone_number = '0' + phone_number

                            if type == 'S':  # 학생인 경우
                                school_info = SchoolInfo.objects.get(school_name=user.school.school_name)

                                # 기존 사용자 확인 및 이력 저장
                                existing_user = UserInfo.objects.filter(phone_number=phone_number).first()
                                if existing_user:  # 기존 사용자가 있는 경우
                                    if existing_user.created_dt.year != dt.now().year or existing_user.year != dt.now().year:  # 작년도 사용자인 경우
                                        UserHist.objects.update_or_create(
                                            user=existing_user,
                                            school=existing_user.school,
                                            student_grade=existing_user.student_grade,
                                            student_class=existing_user.student_class,
                                            student_number=existing_user.student_number,
                                            student_name=existing_user.student_name,
                                            year=existing_user.year
                                        )
                                    existing_member += 1

                                new_member += 1
                                # 사용자 정보 업데이트 또는 생성
                                UserInfo.objects.update_or_create(
                                    phone_number=phone_number,
                                    defaults={
                                        'school': school_info,
                                        'student_grade': user_data['학년'],
                                        'student_class': user_data['반'],
                                        'student_number': user_data['번호'],
                                        'student_name': user_data['이름'],
                                        'username': phone_number,
                                        'password': make_password(os.environ['DEFAULT_PASSWORD']),
                                        'user_type': type,
                                        'user_display_name': f"{school_info.school_name} {user_data['학년']}학년 {user_data['반']}반 {user_data['번호']}번 {user_data['이름']}",
                                        'organization': None,
                                        'department': None,
                                        'year': dt.now().year
                                    }
                                )
                            else:  # user_type == 'O' (기관인 경우)
                                organization_info = OrganizationInfo.objects.get(
                                    organization_name=user.organization.organization_name)  # 기관 정보 가져오기

                                # 기존 사용자 확인 및 이력 저장
                                existing_user = UserInfo.objects.filter(phone_number=phone_number).first()
                                if existing_user:  # 기존 유저
                                    if existing_user.created_dt.year != dt.now().year or existing_user.year != dt.now().year:  # 작년도 사용자인 경우
                                        UserHist.objects.update_or_create(
                                            user=existing_user,
                                            organization=existing_user.organization,
                                            department=existing_user.department,
                                            student_name=existing_user.student_name,  # 기관회원의 이름도 student_name에 저장
                                            year=existing_user.year
                                        )
                                    existing_member += 1

                                new_member += 1
                                UserInfo.objects.update_or_create(  # 기존 사용자가 없는 경우 -> 신규 생성 및 갱신
                                    phone_number=phone_number,
                                    defaults={
                                        'organization': organization_info,
                                        'department': user_data['부서명'],
                                        'student_name': user_data['이름'],
                                        'username': phone_number,
                                        'password': make_password(os.environ['DEFAULT_PASSWORD']),
                                        'user_type': type,
                                        'user_display_name': f"{organization_info.organization_name} {user_data['이름']}",
                                        'school': None,
                                        'year': dt.now().year
                                    }
                                )

                        new_member = new_member - existing_member
                        return JsonResponse(
                            {'message': '성공적으로 저장되었습니다.', 'existing_member': existing_member, 'new_member': new_member})

                # 미리보기 요청인 경우
                return JsonResponse({
                    'users': users,
                    'columns': expected_columns
                })

            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)
    else:
        form = UploadFileForm()

    return render(request, 'member_register.html', {
        'form': form,
        'orgName': orgName,
        'user_type': type,
    })


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
                    columns = ['학년', '반', '번호', '이름', '전화번호']
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
                            phone_number = '0' + phone_number

                        # 회원가입이 되어 있는지 확인
                        user_info = UserInfo.objects.filter(phone_number=phone_number).first()

                        if user_info:
                            # 기존의 반 정보를 UserHist로 저장
                            UserHist.objects.create(
                                phone_number=user_info.phone_number,
                                user=user_info.id,
                                school=user_info.school,
                                student_grade=user_info.student_grade,
                                student_class=user_info.student_class,
                                student_number=user_info.student_number,
                                student_name=user_info.student_name,
                                year=user_info.year,
                            )

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
                                year=dt.now().year  # 현재 년도 int 값으로 저장
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
                    columns = ['부서명', '이름', '전화번호']
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
                            phone_number = '0' + phone_number
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
                                year=dt.now().year  # 현재 년도 int 값으로 저장
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
        'columns': columns,  # Pass dynamic columns
        'total_users': len(users),
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
    selected_year = request.session.get('selected_year', None)  # 세션에서 년도 정보 가져오기
    user_results = []
    groups = []  # 해당 School의 현재 연도 그룹 정보 저장
    years = []  # 해당 School의 BodyResult에 있는 최소 연도, 최대 연도 저장
    year_group_map = defaultdict(list)  # 연도별 그룹 정보 저장 ('연도': ['그룹1', '그룹2', ...])

    if request.method == 'POST':
        selected_group = request.POST.get('group')
        selected_year = request.POST.get('year')

        if not selected_group:
            return redirect('report')  # PRG 패턴을 위해 POST 처리 후 리다이렉트
        else:
            # 선택된 그룹을 세션에 저장하여 리다이렉트 후에도 유지
            request.session['selected_group'] = selected_group
            request.session['selected_year'] = selected_year
            return redirect('report')  # 리다이렉트 후 GET 요청으로 변환

    # GET 요청 처리 (리다이렉트 후 처리)
    if user.user_type == 'S':
        # 학교별 학년/반 정보 가져오기 -> select 태그에 들어가는 값
        groups = UserInfo.objects.filter(
            school__school_name=user.school.school_name,
        ).values_list(
            'student_grade', 'student_class', 'year', named=True
        ).distinct().order_by('year', 'student_grade', 'student_class')

        # 연도별 그룹 정보 생성
        user_hists = UserHist.objects.filter(school__id=user.school.id)
        for hist in user_hists:
            year = str(hist.year)  # UserHist의 연도 정보
            year_group = f"{hist.student_grade}학년 {hist.student_class}반"

            # 해당 연도가 year_group_map에 없으면 초기화
            if year not in year_group_map:
                year_group_map[year] = []

            # 중복되지 않게 추가
            if year_group not in year_group_map[year]:
                year_group_map[year].append(year_group)

        # UserInfo의 연도 데이터 추가
        for group in groups:
            year = str(group.year)  # UserInfo의 연도 정보
            year_group = f"{group.student_grade}학년 {group.student_class}반"

            if year not in year_group_map:
                year_group_map[year] = []

            if year_group not in year_group_map[year]:
                year_group_map[year].append(year_group)

        """ 현재 연도의 데이터가 실제로 존재하는지 확인하는 과정 """
        current_year = str(dt.now().year)

        existing_years_in_db = set(UserHist.objects.values_list('year', flat=True))

        # 현재 연도가 DB에 있는 연도에 포함될 경우만 처리
        if current_year in existing_years_in_db:
            # year_group_map에 현재 연도가 없으면 초기화
            if current_year not in year_group_map:
                year_group_map[current_year] = []

            for group in groups:
                current_group = f"{group.student_grade}학년 {group.student_class}반"
                # 현재 연도에 해당 반 정보가 없으면 추가
                if current_group not in year_group_map[current_year]:
                    year_group_map[current_year].append(current_group)

        # 학교별 년도 정보 가져오기 -> select 태그에 들어가는 값
        # school_id에 해당하는 BodyResult 데이터에서 created_dt의 최소/최대 연도를 가져오기
        years = list(year_group_map.keys())

        if selected_year and selected_group:
            if selected_year != str(dt.now().year) and selected_year not in year_group_map:
                error_message = '해당 연도는 검사 결과가 없습니다.'

            # 정규 표현식으로 학년과 반 추출
            match = re.search(r"(\d+)학년 (\d+)반", selected_group)

            # 당년도
            if selected_year == str(dt.now().year) and match:
                user_results.clear()  # 기존 결과 초기화

                body_result_subquery = BodyResult.objects.filter(
                    user_id=OuterRef('id'),
                    image_front_url__isnull=False,
                    image_side_url__isnull=False,
                    created_dt__year=selected_year
                )

                users = UserInfo.objects.filter(
                    school__school_name=user.school.school_name,
                    student_grade=match.group(1),
                    student_class=match.group(2),
                    year=selected_year
                ).annotate(
                    analysis_valid=Exists(body_result_subquery)
                ).order_by('student_number')

                user_results = [{
                    'user': user,
                    'analysis_valid': user.analysis_valid
                } for user in users]

            elif selected_year != str(dt.now().year) and match:
                user_results.clear()  # 기존 결과 초기화

                # UserHist에서 데이터 조회
                user_hists = UserHist.objects.filter(
                    school__id=user.school.id,
                    student_grade=match.group(1),
                    student_class=match.group(2),
                    year=selected_year
                ).order_by('student_number')

                # UserInfo에서 데이터 조회
                user_infos = UserInfo.objects.filter(
                    school__id=user.school.id,
                    student_grade=match.group(1),
                    student_class=match.group(2),
                    year=selected_year
                ).order_by('student_number')

                # UserHist에서 조회된 user_id 목록
                hist_user_ids = set(user_hists.values_list('user_id', flat=True))

                # UserInfo에서 UserHist에 없는 데이터만 필터링
                unique_user_infos = user_infos.exclude(id__in=hist_user_ids)

                # UserHist 데이터 처리
                for user_hist in user_hists:
                    body_result_queryset = BodyResult.objects.filter(
                        user_id=user_hist.user.id,
                        created_dt__year=selected_year,
                        image_front_url__isnull=False,
                        image_side_url__isnull=False,
                    )
                    analysis_valid = len(body_result_queryset) > 0

                    user_results.append({
                        'user': {
                            'id': user_hist.user.id,
                            'student_grade': user_hist.student_grade,
                            'student_class': user_hist.student_class,
                            'student_number': user_hist.student_number,
                            'student_name': user_hist.user.student_name
                        },
                        'analysis_valid': analysis_valid,
                        'created_dt': body_result_queryset[0].created_dt.strftime(
                            '%Y-%m-%d %H:%M:%S') if analysis_valid else None
                    })

                # UserInfo 데이터 처리 (UserHist에 없는 데이터만)
                for user_info in unique_user_infos:
                    body_result_queryset = BodyResult.objects.filter(
                        user_id=user_info.id,
                        created_dt__year=selected_year,
                        image_front_url__isnull=False,
                        image_side_url__isnull=False,
                    )
                    analysis_valid = len(body_result_queryset) > 0

                    user_results.append({
                        'user': {
                            'id': user_info.id,
                            'student_grade': user_info.student_grade,
                            'student_class': user_info.student_class,
                            'student_number': user_info.student_number,
                            'student_name': user_info.student_name
                        },
                        'analysis_valid': analysis_valid,
                        'created_dt': body_result_queryset[0].created_dt.strftime(
                            '%Y-%m-%d %H:%M:%S') if analysis_valid else None
                    })


    elif user.user_type == 'O':
        groups = UserInfo.objects.filter(
            organization__organization_name=user.organization.organization_name).values_list('department',
                                                                                             named=True).distinct().order_by(
            'department')
        groups = [g.department for g in groups if ((g.department is not None))]

        if selected_group:
            users = UserInfo.objects.filter(organization__organization_name=user.organization.organization_name,
                                            department=selected_group).order_by('student_name')

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

    if user.user_type == '' or len(user_results) == 0:  # 초기 렌더링
        return render(request, 'report.html', {
            'groups': groups,  # 그룹을 초기화
            'years': years,
            'year_group_map': json.dumps(dict(year_group_map), ensure_ascii=False),
            'user_results': [],  # 테이블 초기화
            'selected_year': str(dt.now().year),
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
        user_results = []  # 테이블 초기화
        selected_group = None
        valid_count = 0
        total_users = 0
        progress_percentage = 0
        error_message = '그룹이 선택되지 않았습니다. 그룹 선택 후 조회 해주세요!'

    return render(request, 'report.html', {
        'groups': groups,
        'years': years,
        'year_group_map': json.dumps(dict(year_group_map), ensure_ascii=False),
        'user_results': user_results,
        'selected_year': selected_year,
        'selected_group': selected_group,
        'error_message': error_message,
        'valid_count': valid_count,
        'total_users': total_users,
        'progress_percentage': progress_percentage,
        'is_registered': True,
    })


@login_required
def report_download(request):
    user_request = request.user
    selected_group = request.GET.get('group', None)
    selected_year = request.GET.get('year', None)

    user = UserInfo.objects.get(id=user_request.id)
    user_type = user.user_type

    if not selected_group or not selected_year or not user.is_authenticated or user is None:
        return redirect('report')

    # 사용자 목록 조회
    if user_type == 'S':  # 학교 사용자
        match = re.search(r"(\d+)학년 (\d+)반", selected_group)
        if selected_year == str(dt.now().year) and match:  # 현재 년도 조회
            users = UserInfo.objects.filter(
                school__school_name=user.school.school_name,
                student_grade=match.group(1),
                student_class=match.group(2),
                year=selected_year
            ).order_by('student_number')
        else:  # 이전 년도 조회
            # UserHist에서 데이터 조회
            user_hists = UserHist.objects.filter(
                school__id=user.school.id,
                student_grade=match.group(1),
                student_class=match.group(2),
                year=selected_year
            ).order_by('student_number')

            # UserInfo에서 데이터 조회
            user_infos = UserInfo.objects.filter(
                school__id=user.school.id,
                student_grade=match.group(1),
                student_class=match.group(2),
                year=selected_year
            ).order_by('student_number')

            # UserHist에서 조회된 user_id 목록
            hist_user_ids = set(user_hists.values_list('user_id', flat=True))

            # UserInfo에서 UserHist에 없는 데이터만 필터링
            unique_user_infos = user_infos.exclude(id__in=hist_user_ids)

            # 최종 사용자 목록 생성
            users = list(user_hists) + list(unique_user_infos)

    elif user_type == 'O':  # 기관 사용자
        users = UserInfo.objects.filter(
            organization__organization_name=user.organization.organization_name,
            department=selected_group
        ).order_by('student_name')

    # 한 번에 모든 사용자의 ID 리스트 생성
    if user_type == 'S':  # 학교 사용자의 경우 (이전 년도가 포함될 수 있음 (UserHist))
        user_ids = [user.user_id for user in user_hists] + [user.id for user in
                                                            unique_user_infos] if selected_year != str(
            dt.now().year) else [user.id for user in users]
    else:  # 기관 사용자의 경우
        user_ids = [user.id for user in users]

    if user_type == 'S':
        # 한 번의 쿼리로 모든 BodyResult 데이터 조회
        body_results = BodyResult.objects.filter(  # user_id로 필터링 (선택된 년도에 생성된 bodyResult)
            user_id__in=user_ids,
            created_dt__year=selected_year,
            image_front_url__isnull=False,
            image_side_url__isnull=False,
        ).select_related('user')
    else:  # 기관은 모든 년도의 데이터를 사용
        body_results = BodyResult.objects.filter(  # user_id로 필터링 (선택된 년도에 생성된 bodyResult)
            user_id__in=user_ids,
            image_front_url__isnull=False,
            image_side_url__isnull=False,
        ).select_related('user')

    # {user_id : <BodyResult:QuerySet> }
    body_results_dict = {}
    for br in body_results:
        if br.user_id not in body_results_dict:
            body_results_dict[br.user_id] = br

    # code_name 목록 가져오기
    code_names = []
    if body_results:
        first_result = next(iter(body_results))
        _, status_results = calculate_normal_ratio(first_result)
        code_names = list(status_results.keys())

    # 엑셀 데이터 생성
    excel_data = []
    for user in users:
        # UserHist에서 가져온 경우 user_id를 user.user_id로 설정
        if hasattr(user, 'user_id'):
            user_id = user.user_id
        else:  # UserInfo에서 가져온 경우
            user_id = user.id

        body_result = body_results_dict.get(user_id)

        if user_type == 'S':
            row_data = {
                '학년': user.student_grade,
                '반': user.student_class,
                '번호': user.student_number,
                '이름': user.student_name,
                '검사일': body_result.created_dt.strftime('%Y-%m-%d %H:%M:%S') if body_result else None,
                '검사결과': 'O' if body_result else 'X',
            }
        else:
            row_data = {
                '부서명': user.department,
                '이름': user.student_name,
                '검사일': body_result.created_dt.strftime('%Y-%m-%d %H:%M:%S') if body_result else None,
                '검사결과': 'O' if body_result else 'X',
            }

        if body_result:
            ratio, status_results = calculate_normal_ratio(body_result)
            row_data['정상범위'] = ratio
            # 각 측정 항목의 상태(양호/주의)를 추가
            for code_name, status in status_results.items():
                row_data[code_name] = status
        else:
            row_data['정상범위'] = None
            for code_name in code_names:
                row_data[code_name] = None

        excel_data.append(row_data)

    # 데이터프레임 생성 (기본 컬럼 + code_name 컬럼들)
    df = pd.DataFrame(excel_data)

    # 컬럼 순서 설정
    if user_type == 'S':
        columns = ['학년', '반', '번호', '이름', '검사일', '검사결과', '정상범위'] + code_names
    else:
        columns = ['부서명', '이름', '검사일', '검사결과', '정상범위'] + code_names
    df = df[columns]

    # 엑셀 커스텀마이징(열 폭, 색상)
    workbook = create_excel_report(df, user_type, code_names)

    # 파일명 생성 및 응답 반환
    if user_type == 'S':
        file_name = f"{selected_year}_{user.school.school_name}_{selected_group}.xlsx"
    else:
        file_name = f"{selected_year}_{user.organization.organization_name}_{selected_group}.xlsx"
    encoded_file_name = quote(file_name)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_file_name}"
    workbook.save(response)

    return response


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


@login_required
def report_detail_report_id(request, id, report_id):
    user_id = id
    return generate_report(request, user_id, report_id)


def generate_report(request, id, report_id=None):
    max_count = 20
    body_info_queryset = CodeInfo.objects.filter(group_id='01').order_by('seq_no')

    # 해당 유저의 모든 검사 결과를 가져옴
    body_result_queryset = BodyResult.objects.filter(
        user_id=id,
        image_front_url__isnull=False,
        image_side_url__isnull=False,
    )

    # body result 최신 순 정렬 후 날짜만 뽑아오기
    body_result_queryset = body_result_queryset.order_by('created_dt')[
                           max(0, len(body_result_queryset) - int(max_count)):]

    if len(body_result_queryset) == 0:
        return render(request, 'no_result.html', status=404)

    body_result_latest = body_result_queryset[len(body_result_queryset) - 1]

    # body result에서 날짜만 뽑아서 정렬하기
    result_dates = [result.created_dt.strftime('%Y-%m-%d %H:%M:%S') for result in body_result_queryset]
    sorted_dates = sorted(result_dates, key=lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S'), reverse=True)

    # 사용자가 선택한 날짜 처리
    selected_date = request.GET.get('selected_date')
    selected_result = []
    select_report_date = None

    if selected_date:
        # 전체 쿼리셋은 유지하면서 선택된 날짜의 결과만 latest로 설정
        selected_result = [
            result for result in body_result_queryset
            if result.created_dt.strftime('%Y-%m-%d %H:%M:%S') == selected_date
        ]

        if len(selected_result) == 0:
            return render(request, 'no_result.html', status=404)

        # 선택된 날짜의 결과만 latest로 설정하고, 전체 쿼리셋은 유지
        # selected_result의 순서를 맨 앞으로 가져오고, 나머지는 뒤에 배치
        body_result_queryset = [result for result in body_result_queryset if
                                result not in selected_result] + selected_result
        body_result_latest = selected_result[0]

    elif report_id:
        # report_id에 해당하는 BodyResult를 가져옴
        tmp = list(BodyResult.objects.filter(id=report_id))

        # body_result_queryset과 tmp의 차집합을 유지하고, tmp를 뒤에 추가
        body_result_queryset = [result for result in body_result_queryset if result not in tmp] + tmp
        select_report_date = body_result_queryset[-1].created_dt.astimezone(kst).strftime(
            '%Y-%m-%d %H:%M:%S') if body_result_queryset else None

    else:
        select_report_date = body_result_latest.created_dt.astimezone(kst).strftime('%Y-%m-%d %H:%M:%S')

    report_items = []

    for body_info in body_info_queryset:
        trend_data = []
        is_paired = False

        for body_result in body_result_queryset:
            body_code_id_ = body_info.code_id
            alias = body_info.code_id
            if 'leg_alignment' in body_code_id_ or 'back_knee' in body_code_id_ or 'scoliosis' in body_code_id_:
                is_paired = True
                if 'scoliosis' in body_code_id_:
                    code_parts = body_code_id_.split('_')
                    pair_names = ['shoulder', 'hip']
                    paired_body_code_id_list = ['_'.join([code_parts[0], pair, code_parts[2]]) for pair in pair_names]

                else:
                    pair_names = ['left', 'right']
                    paired_body_code_id_list = [f'{pair}_' + '_'.join(body_code_id_.split('_')[1:]) for pair in
                                                pair_names]

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
                trend_samples = [getattr(body_result, body_code_id_),
                                 body_result.created_dt.strftime('%Y-%m-%d %H:%M:%S')]
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
                    title = '척추 균형'
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
                result1 = f'{status_desc}{abs(result1)}{unit_name}'

            if not result2:
                result2 = "?"
            else:
                status_desc = ""
                if alias == 'spinal_imbalance':
                    if result2 < 0:
                        status_desc += "왼쪽으로" + " "
                    else:
                        status_desc += "오른쪽으로" + " "
                result2 = f'{status_desc}{abs(result2)}{unit_name}'

            if alias == 'spinal_imbalance':
                result = f'· 척추-어깨: {result1}의 편향, · 척추-골반: {result2}의 편향'
            else:
                result = f'{result1} / {result2}'
            if all([i['title'] != title for i in report_items]):
                report_items.append({
                    'title': title,
                    'alias': alias,
                    'result': result,
                    'description': description_list,
                    'description_list': True,
                    'metric': metric,
                    'summary': [re.sub(r'\(.*?\)', '', x) for x in description_list],
                    'normal_range': [body_info.normal_min_value, body_info.normal_max_value],
                    'value_range': [body_info.min_value, body_info.max_value],
                    'trend': trend_data,
                    'sections': {getattr(body_info, f'title_{name}'): getattr(body_info, name) for name in
                                 ['outline', 'risk', 'improve', 'recommended']}
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

                result = f'{abs(result)}{unit_name}{status_desc}'  # show absolute value
            report_items.append({
                'title': body_info.code_name,
                'alias': alias,
                'result': result,
                'description': description,
                'description_list': False,
                'metric': metric,
                'summary': re.sub(r'\(.*?\)', '', description),
                'normal_range': normal_range,
                'value_range': [body_info.min_value, body_info.max_value],
                'trend': trend_data,
                'sections': {getattr(body_info, f'title_{name}'): getattr(body_info, name) for name in
                             ['outline', 'risk', 'improve', 'recommended']}
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

    front_img_url = generate_presigned_url(file_keys=['front', created_dt])
    side_img_url = generate_presigned_url(file_keys=['side', created_dt])

    context = {
        'user': user,
        'report_items': report_items,
        'trend_data_dict': trend_data_dict,
        'image_front_url': front_img_url,
        'image_side_url': side_img_url,
        'sorted_dates': sorted_dates,  # 날짜 리스트
        'selected_date': selected_date,  # 선택한 날짜
    }

    context['report_date'] = select_report_date

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
                    'd_supp_perc_l': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                    description='Double support percentage left'),
                    'd_supp_perc_r': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                    description='Double support percentage right'),
                    'toeinout_l': openapi.Schema(type=openapi.TYPE_NUMBER, description='Toe-in/out angle left'),
                    'toeinout_r': openapi.Schema(type=openapi.TYPE_NUMBER, description='Toe-in/out angle right'),
                    'stridelen_cv_l': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                     description='Stride length coefficient of variation left'),
                    'stridelen_cv_r': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                     description='Stride length coefficient of variation right'),
                    'stridetm_cv_l': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                    description='Stride time coefficient of variation left'),
                    'stridetm_cv_r': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                    description='Stride time coefficient of variation right'),
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
        return Response({'data': {'message': serializer.errors, 'status': 500}})


@swagger_auto_schema(
    method='get',
    operation_description="Retrieve latest gait analysis results by session key",
    manual_parameters=[
        openapi.Parameter('session_key', openapi.IN_QUERY, description="Session key for the current user",
                          type=openapi.TYPE_STRING, required=True),
        openapi.Parameter('count', openapi.IN_QUERY, description="The number of items to retrieve from latest results",
                          type=openapi.TYPE_INTEGER, required=False),
        openapi.Parameter('start_date', openapi.IN_QUERY,
                          description="The start date for filtering results (format: YYYY-MM-DD)",
                          type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('end_date', openapi.IN_QUERY,
                          description="The end date for filtering results (format: YYYY-MM-DD)",
                          type=openapi.TYPE_STRING, required=False),
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
        gait_results = GaitResult.objects.filter(user_id=user_id, created_dt__range=(start_date, end_date)).order_by(
            '-created_dt')
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
        openapi.Parameter('name', openapi.IN_QUERY, description="Name of analysis (i.e., gait or body)",
                          type=openapi.TYPE_STRING, required=True),
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
                    'shoulder_level_angle': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                           description='Shoulder level angle'),
                    'hip_level_angle': openapi.Schema(type=openapi.TYPE_NUMBER, description='Hip level angle'),
                    'leg_length_ratio': openapi.Schema(type=openapi.TYPE_NUMBER, description='Leg length ratio'),
                    'left_leg_alignment_angle': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                               description='Left leg alignment angle'),
                    'right_leg_alignment_angle': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                                description='Right leg alignment angle'),
                    'left_back_knee_angle': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                           description='Left back knee angle'),
                    'right_back_knee_angle': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                            description='Right back knee angle'),
                    'forward_head_angle': openapi.Schema(type=openapi.TYPE_NUMBER, description='Forward head angle'),
                    'scoliosis_shoulder_ratio': openapi.Schema(type=openapi.TYPE_NUMBER,
                                                               description='Scoliosis shoulder ratio'),
                    'scoliosis_hip_ratio': openapi.Schema(type=openapi.TYPE_NUMBER, description='Scoliosis hip ratio'),
                },
            ),
            'image_front': openapi.Schema(type=openapi.TYPE_STRING,
                                          description='Base64 encoded bytes of the front image'),
            'image_side': openapi.Schema(type=openapi.TYPE_STRING,
                                         description='Base64 encoded bytes of the side image'),
        },
        required=['session_key', 'body_data', 'image_front', 'image_side'],  # Required fields
    ),
    responses={
        200: openapi.Response(
            description='OK; created_body_result successfully',
            examples={
                "application/json": {
                    "message": "created_body_result",
                    "status": 200
                }
            }
        ),
        400: openapi.Response(
            description='Bad Request; session_key or body_data or image is missing, or image format is invalid',
            examples={
                "application/json": {
                    "message": "session_key_required",
                    "status": 400
                }
            }
        ),
        401: openapi.Response(
            description='Unauthorized; user not found',
            examples={
                "application/json": {
                    "message": "user_not_found",
                    "status": 401
                }
            }
        ),
        404: openapi.Response(
            description='Not Found; session_key is not found',
            examples={
                "application/json": {
                    "message": "session_key_not_found",
                    "status": 404
                }
            }
        ),
        500: openapi.Response(
            description='Internal Server Error; unexpected error occurred',
            examples={
                "application/json": {
                    "message": "An unexpected error occurred.",
                    "status": 500
                }
            }
        ),
    },
    tags=['analysis results']
)
@api_view(['POST'])
def create_body_result(request):
    session_key = request.data.get('session_key')
    # session_key가 없는 경우
    if not session_key:
        return Response({'data': {'message': 'session_key_required', 'status': HTTP_400_BAD_REQUEST}},
                        status=HTTP_400_BAD_REQUEST)

    body_data = request.data.get('body_data')
    # body_data가 없는 경우
    if not body_data:
        return Response({'data': {'message': 'body_data_required', 'status': HTTP_400_BAD_REQUEST}},
                        status=HTTP_400_BAD_REQUEST)

    try:
        # session_key를 기반으로 세션 정보 조회
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        # 세션 정보가 없는 경우
        return Response({'data': {'message': 'session_key_not_found', 'status': HTTP_404_NOT_FOUND}},
                        status=HTTP_404_NOT_FOUND)

    try:
        # 세션 정보에서 사용자 정보 조회
        user_info = UserInfo.objects.get(id=session_info.user_id)
    except UserInfo.DoesNotExist:
        # 사용자 정보가 없는 경우
        return Response({'data': {'message': 'user_not_found', 'status': HTTP_401_UNAUTHORIZED}},
                        status=HTTP_401_UNAUTHORIZED)

    # 사용자의 학교 정보가 없는 경우에 채울 Temp School 정보
    null_school, created = SchoolInfo.objects.update_or_create(
        id=-1,
        defaults=dict(
            school_name='N/A',
            contact_number='N/A'
        )
    )

    data = body_data.copy()
    if user_info.school is None:  # 회원의 학교 정보가 없는 경우
        data['school'] = null_school.id
    else:  # 회원의 학교 정보가 있는 경우
        # 학교 id, 학년, 반, 번호를 저장
        data['school'] = user_info.school.id
        data['student_grade'] = user_info.student_grade
        data['student_class'] = user_info.student_class
        data['student_number'] = user_info.student_number

    data['user'] = user_info.id
    serializer = BodyResultSerializer(data=data)

    if serializer.is_valid():
        # 데이터 저장
        serializer.save()
        # 저장된 데이터의 생성 시간으로 파일 이름 생성
        created_dt = dt.strptime(serializer.data['created_dt'], '%Y-%m-%dT%H:%M:%S.%f').strftime('%Y%m%dT%H%M%S%f')
        image_front_bytes = request.data.get('image_front', None)
        image_side_bytes = request.data.get('image_side', None)

        try:
            # 이미지 검증 및 업로드
            if image_front_bytes and image_side_bytes:
                try:
                    # 이미지 검증
                    verified_front = verify_image(image_front_bytes)
                    verified_side = verify_image(image_side_bytes)

                    # 검증된 이미지만 업로드
                    upload_image_to_s3(verified_front, file_keys=['front', created_dt])
                    upload_image_to_s3(verified_side, file_keys=['side', created_dt])
                except ValueError as ve:
                    # 이미지 형식이 잘못된 경우
                    return Response(
                        {'data': {'message': f"Invalid image format: {str(ve)}", 'status': HTTP_400_BAD_REQUEST}},
                        status=HTTP_400_BAD_REQUEST)
            else:
                # 누락된 이미지 확인
                missing_images = []
                if not image_front_bytes:
                    missing_images.append("image_front")
                if not image_side_bytes:
                    missing_images.append("image_side")
                return Response({'data': {'message': f"Missing images: {', '.join(missing_images)}",
                                          'status': HTTP_400_BAD_REQUEST}}, status=HTTP_400_BAD_REQUEST)

        except Exception as e:
            # 기타 예외 발생 시
            return Response({'data': {'message': str(e), 'status': HTTP_500_INTERNAL_SERVER_ERROR}},
                            status=HTTP_500_INTERNAL_SERVER_ERROR)

        # 성공 응답
        return Response({'data': {'message': 'created_body_result', 'status': HTTP_200_OK}}, status=HTTP_200_OK)
    else:
        # Serializer 유효성 검사 실패
        return Response({'data': {'message': serializer.errors, 'status': HTTP_500_INTERNAL_SERVER_ERROR}},
                        status=HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_description="Retrieve latest body analysis results by session key",
    manual_parameters=[
        openapi.Parameter('session_key', openapi.IN_QUERY, description="Session key for the current user",
                          type=openapi.TYPE_STRING, required=True),
        openapi.Parameter('count', openapi.IN_QUERY, description="The number of items to retrieve from latest results",
                          type=openapi.TYPE_INTEGER, required=False),
        openapi.Parameter('start_date', openapi.IN_QUERY,
                          description="The start date for filtering results (format: YYYY-MM-DD)",
                          type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('end_date', openapi.IN_QUERY,
                          description="The end date for filtering results (format: YYYY-MM-DD)",
                          type=openapi.TYPE_STRING, required=False),
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
        body_results = BodyResult.objects.filter(user_id=user_id, created_dt__range=(start_date, end_date)).order_by(
            '-created_dt')
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

        if body_result.image_front_url is not None and requests.get(body_result.image_front_url).status_code in [400,
                                                                                                                 404]:
            body_result.image_front_url = None
        if body_result.image_side_url is not None and requests.get(body_result.image_side_url).status_code in [400,
                                                                                                               404]:
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
            })),
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

    return Response({'data': {'session_key': session_key, 'message': 'success', 'status': 200}})


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
        return Response(
            {'data': {'message': 'incorrect_password', 'status': 401}, 'message': 'incorrect_password', 'status': 401})
    else:
        session_info.user_id = user_info.id
        session_info.save()
        return Response(
            {'data': {'message': 'login_success', 'status': 200}, 'message': 'login_success', 'status': 200})


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

    return Response({'data': parse_userinfo(user_info), 'message': 'OK', 'status': 200})


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
    return Response({'data': {'message': 'session_closed', 'status': 200}, 'message': 'session_closed', 'status': 200})




