# analysis/views.py

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
from .models import BodyResult, CodeInfo, GaitResult, SchoolInfo, UserInfo, SessionInfo
from .forms import UploadFileForm, CustomPasswordChangeForm
from .serializers import BodyResultSerializer, GaitResponseSerializer, GaitResultSerializer


from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from datetime import datetime as dt
from django.utils import timezone
from dateutil.relativedelta import relativedelta

def home(request):
    if request.user.is_authenticated:
        return redirect('register_student')
    else:
        return redirect('login')

@login_required
def register_student(request):
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
                    phone_number=extract_digits(row['전화번호'].strip().replace('-', '')),
                    defaults=dict(
                        school=school_info,
                        student_grade=row['학년'],
                        student_class=row['반'],
                        student_number=row['번호'],
                        student_name=row['이름'].strip().replace(' ', ''),
                        username=extract_digits(row['전화번호'].strip().replace('-', '')),
                        password=make_password(os.environ['DEFAULT_PASSWORD'])
                    ),
                )

                users.append(user_info)


            return render(request, 'register_student.html', {
                'form': form,
                'users': users
            })
    else:
        form = UploadFileForm()
    
    return render(request, 'register_student.html', {'form': form})

@login_required
def report(request):
    groups = UserInfo.objects.values_list('student_grade', 'student_class', named=True).distinct().order_by('student_grade', 'student_class')
    groups = [ f'{g.student_grade}학년 {g.student_class}반' for g in groups if ((g.student_grade is not None) & (g.student_class is not None)) ] # Note : 학년, 반 정보 없는 superuser는 그룹에 포함안됨
    
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

# Example report items
# TODO: get from actual DB
from django.shortcuts import render, get_object_or_404
from .models import UserInfo

import pytz

kst = pytz.timezone('Asia/Seoul')

# Example data structure with recent 3 months' trend data
# TODO: fetch from DB

@login_required
def body_report(request, id):
    max_count = 20
    body_info_queryset = CodeInfo.objects.filter(group_id='01')
    
    # Get the current date and time
    now = timezone.now()

    # Calculate the date 3 months ago
    three_months_ago = now - relativedelta(months=3)

    # Filter records from the last 3 months
    body_result_queryset = BodyResult.objects.filter(
        user_id=id, 
        created_dt__gte=three_months_ago
    ).order_by('-created_dt')[:int(max_count)]
    if len(body_result_queryset) == 0:
        return render(request, 'no_result.html', status=404)
    body_result_latest = body_result_queryset[0]

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
                                body_result.created_dt.astimezone(kst).strftime('%Y-%m-%d %H:%M:%S')]
            else:
                trend_samples = [getattr(body_result, body_code_id_), body_result.created_dt.astimezone(kst).strftime('%Y-%m-%d %H:%M:%S')]
            trend_data.append(trend_samples)

        if is_paired:
            result_val1, result_val2, *_ = trend_data[-1]
            result_val1, result_val2 = round(result_val1, 2), round(result_val2, 2)
            description_list = []
            unit_name = body_info.unit_name
            normal_range = [body_info.normal_min_value, body_info.normal_max_value]
            for i, val in enumerate([result_val1, result_val2]):
                if alias == 'o_x_legs':
                    title = '흰 다리'
                    metric = '각도 [°]'
                    pair_name = '왼쪽' if i == 0 else '오른쪽'
                    if normal_range[0] < val < normal_range[1]:
                        description = '양호'
                    else:
                        description = 'O 다리 의심' if result < 180 else 'X 다리 의심'
                if alias == 'knee_angle':
                    title = '무릎 기울기'
                    metric = '각도 [°]'
                    pair_name = '왼쪽' if i == 0 else '오른쪽'
                    if normal_range[0] < val < normal_range[1]:
                        description = '양호'
                    else:
                        description = '반장슬 의심'
                if alias == 'spinal_imbalance':
                    title = '척추 불균형'
                    metric = '척추 기준 좌우 비율 불균형 [%]'
                    pair_name = '척추-어깨' if i == 0 else '척추-골반'
                    if normal_range[0] < val < normal_range[1]:
                        description = '양호'
                    else:
                        description = '불균형 (오른쪽으로 치우침)' if val < 0 else '불균형 (왼쪽으로 치우침)'

                description_list.append(f'{pair_name} : ' + description)

            if all([ i['title'] != title for i in report_items ]):
                report_items.append({
                    'title': title,
                    'alias': alias,
                    'result': f'{abs(result_val1)}{unit_name} / {abs(result_val2)}{unit_name}',
                    'description' : description_list,
                    'description_list': True,
                    'metric': metric,
                    'normal_range': [body_info.normal_min_value, body_info.normal_max_value],
                    'value_range': [body_info.min_value, body_info.max_value],
                    'trend': trend_data,
                    'sections': { getattr(body_info, f'title_{name}'): getattr(body_info, name) for name in ['outline', 'risk', 'improve', 'recommended']  }
                })
        else:
            result = round(getattr(body_result_latest, body_info.code_id), 2)
            unit_name = body_info.unit_name
            normal_range = [body_info.normal_min_value, body_info.normal_max_value]
            if 'angle' in alias:
                description = '왼쪽으로' if result < 0 else '오른쪽으로'
                metric = '각도 [°]'
            
            if alias == 'forward_head_angle':
                description = '양호' if normal_range[0] < result < normal_range[1] else '거북목 진행형'

            if alias == 'leg_length_ratio':
                description = '왼쪽 더 짧음' if result < 0 else '오른쪽이 더 짧음'
                metric = '다리 길이 차이 [%]'

            report_items.append({
                'title': body_info.code_name,
                'alias': alias,
                'result': f'{abs(result)}{unit_name}',
                'description' : description,
                'description_list': False,
                'metric': metric,
                'normal_range': normal_range,
                'value_range': [body_info.min_value, body_info.max_value],
                'trend': trend_data,
                'sections': { getattr(body_info, f'title_{name}'): getattr(body_info, name) for name in ['outline', 'risk', 'improve', 'recommended']  }
            })

    student = get_object_or_404(UserInfo, id=id)

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

    created_dt = body_result_latest.created_dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%f')

    context = {
        'student': student,
        'report_items': report_items,
        'trend_data_dict': trend_data_dict,
        'image_front_url': generate_presigned_url(file_keys=['front', created_dt]),
        'image_side_url': generate_presigned_url(file_keys=['side', created_dt]),
    }

    return render(request, 'body_report.html', context)





def policy(request):
    return render(request, 'policy.html')

class CustomPasswordChangeView(PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'password_change.html'
    success_url = '/password-change-done/'

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
        created_dt = dt.strptime(serializer.data['created_dt'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
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
        openapi.Parameter('return_urls', openapi.IN_QUERY, description="If true return image urls", type=openapi.TYPE_BOOLEAN, required=False, default=True),
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

    return_urls = request.query_params.get('return_urls', 'true')
    return_urls = eval(return_urls.capitalize())

    # 수정된 body_results를 리스트로 저장
    updated_body_results = []

    for body_result in body_results:
        created_dt = body_result.created_dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        if return_urls:
            # Presigned URL 생성 (일정 시간 동안)
            body_result.image_front_url = generate_presigned_url(file_keys=['front', created_dt])
            body_result.image_side_url = generate_presigned_url(file_keys=['side', created_dt])
        else:
            body_result.image_front_url = None
            body_result.image_side_url = None

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
