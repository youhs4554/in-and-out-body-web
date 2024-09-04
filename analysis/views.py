# analysis/views.py

import os
import re
import uuid
import pandas as pd
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from rest_framework import permissions, viewsets, status
from django.contrib.auth.hashers import make_password, check_password
from rest_framework import viewsets, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.views import PasswordChangeView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import datetime, timedelta
from .helpers import parse_userinfo
from .models import AuthInfo, BodyResult, GaitResult, SchoolInfo, UserInfo, SessionInfo, CodeInfo
from .forms import UploadFileForm, CustomPasswordChangeForm
from .serializers import BodyResponseSerializer, BodyResultSerializer, GaitResponseSerializer, GaitResultSerializer, CodeInfoSerializer


from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

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
                    username=row['전화번호'].strip().replace('-', ''),
                    defaults=dict(
                        school=school_info,
                        student_grade=row['학년'],
                        student_class=row['반'],
                        student_number=row['번호'],
                        student_name=row['이름'].strip().replace(' ', ''),
                        phone_number=row['전화번호'].strip().replace('-', ''),
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

# Example data structure with recent 3 months' trend data
# TODO: fetch from DB
report_items = [
    {
        'title': '거북목',
        'alias': 'forward_head_angle',
        'description_label': '기울어짐 각도',
        'description_value': '앞쪽으로 0.02°',
        'status': '양호',
        'normal_range': [45.00, 50.00],  # Example range
        'trend': {
            '지난 3개월': [
                [28.96, '2024-06-01'],
                [47.50, '2024-07-01'],
                [46.00, '2024-08-01']
            ]
        },
        'sections': {
            '거북목이란?': '거북목은 목이 앞으로 기울어진 상태로, 장시간 컴퓨터 작업이나 스마트폰 사용으로 인해 발생할 수 있습니다.',
            '거북목의 위험성': '거북목은 목과 어깨에 불편함을 주며, 장기적으로는 척추에 문제를 일으킬 수 있습니다.',
            '거북목 개선 방법': '자주 스트레칭하고 올바른 자세를 유지하는 것이 중요합니다. 정기적인 운동과 물리치료가 도움이 될 수 있습니다.',
            '권장 계획': '하루 30분 이상의 스트레칭을 권장하며, 자세 교정과 운동을 병행하는 것이 좋습니다.'
        }
    },
    {
        'title': '척추 불균형',
        'alias': 'spinal_imbalance',
        'description_label': '척추 기울기',
        'description_value': '상부 척추: 오른쪽으로 20%, 하부 척추: 왼쪽으로 15%',
        'status': '주의',
        'normal_range': [15.00, 25.00],  # Example range
        'trend': {
            '지난 3개월': [
                [20.00, '2024-06-01'],
                [21.50, '2024-07-01'],
                [19.75, '2024-08-01']
            ]
        },
        'sections': {
            '척추 불균형이란?': '척추 불균형은 척추가 정상 위치에서 벗어나 한쪽으로 기울어지는 상태를 말합니다.',
            '척추 불균형의 위험성': '척추 불균형은 통증을 유발하며, 장기적으로 자세 문제나 신경 압박이 발생할 수 있습니다.',
            '척추 불균형 개선 방법': '물리치료와 자세 교정 운동이 도움이 될 수 있으며, 정기적인 검진이 필요합니다.',
            '권장 계획': '매일 스트레칭과 척추 교정 운동을 권장합니다.'
        }
    },
    {
        'title': '안면 불균형',
        'alias': 'facial_imbalance',
        'description_label': '기울어짐 각도',
        'description_value': '왼쪽으로 0.02°',
        'status': '양호',
        'normal_range': [0.00, 0.05],  # Example range
        'trend': {
            '지난 3개월': [
                [0.02, '2024-06-01'],
                [0.01, '2024-07-01'],
                [0.03, '2024-08-01']
            ]
        },
        'sections': {
            '안면 불균형이란?': '안면 불균형은 얼굴이 비대칭으로 기울어지는 상태를 말합니다.',
            '안면 불균형의 위험성': '안면 불균형은 심미적 문제를 유발할 수 있으며, 얼굴의 기능에도 영향을 미칠 수 있습니다.',
            '안면 불균형 개선 방법': '안면 운동과 균형 잡힌 식사가 도움이 될 수 있습니다.',
            '권장 계획': '매일 얼굴 운동과 정기적인 검사 권장'
        }
    },
    {
        'title': '어깨 불균형',
        'alias': 'shoulder_imbalance',
        'description_label': '기울어짐 각도',
        'description_value': '오른쪽으로 0.82°',
        'status': '양호',
        'normal_range': [0.00, 1.00],  # Example range
        'trend': {
            '지난 3개월': [
                [0.80, '2024-06-01'],
                [0.85, '2024-07-01'],
                [0.82, '2024-08-01']
            ]
        },
        'sections': {
            '어깨 불균형이란?': '어깨 불균형은 양쪽 어깨가 높이나 위치에서 차이를 보이는 상태를 말합니다.',
            '어깨 불균형의 위험성': '어깨 불균형은 근육 불균형을 초래할 수 있으며, 장기적으로 자세 문제를 유발할 수 있습니다.',
            '어깨 불균형 개선 방법': '정기적인 스트레칭과 근력 운동이 도움이 될 수 있습니다.',
            '권장 계획': '매일 어깨 스트레칭과 강화 운동을 권장합니다.'
        }
    },
    {
        'title': '골반 불균형',
        'alias': 'pelvic_imbalance',
        'description_label': '기울어짐 각도',
        'description_value': '오른쪽으로 0.82°',
        'status': '양호',
        'normal_range': [0.00, 1.00],  # Example range
        'trend': {
            '지난 3개월': [
                [0.80, '2024-06-01'],
                [0.85, '2024-07-01'],
                [0.82, '2024-08-01']
            ]
        },
        'sections': {
            '골반 불균형이란?': '골반 불균형은 골반이 한쪽으로 기울어지는 상태를 말합니다.',
            '골반 불균형의 위험성': '골반 불균형은 허리 통증을 유발할 수 있으며, 장기적으로 자세 문제를 일으킬 수 있습니다.',
            '골반 불균형 개선 방법': '골반 교정 운동과 스트레칭이 도움이 될 수 있습니다.',
            '권장 계획': '매일 골반 교정 운동과 스트레칭을 권장합니다.'
        }
    },
    {
        'title': '다리 길이 불균형',
        'alias': 'leg_length_discrepancy',
        'description_label': '좌우 다리 길이 차이',
        'description_value': '왼쪽이 1% 짧음',
        'status': '양호',
        'normal_range': [0.00, 1.00],  # Example range
        'trend': {
            '지난 3개월': [
                [1.00, '2024-06-01'],
                [0.98, '2024-07-01'],
                [0.99, '2024-08-01']
            ]
        },
        'sections': {
            '다리 길이 불균형이란?': '다리 길이 불균형은 한쪽 다리가 다른 쪽보다 길거나 짧은 상태를 말합니다.',
            '다리 길이 불균형의 위험성': '다리 길이 불균형은 보행 문제를 유발할 수 있으며, 장기적으로 자세 문제를 일으킬 수 있습니다.',
            '다리 길이 불균형 개선 방법': '다리 길이 교정 운동과 맞춤형 깔창 사용이 도움이 될 수 있습니다.',
            '권장 계획': '매일 교정 운동과 정기적인 검사 권장'
        }
    },
    {
        'title': 'O/X 다리',
        'alias': 'o_x_legs',
        'description_label': '기울어짐 각도',
        'description_value': '좌: 173.75°, 우: 177.84°',
        'status': '양호',
        'normal_range': [170.00, 180.00],  # Example range
        'trend': {
            '지난 3개월': [
                [173.50, '2024-06-01'],
                [174.00, '2024-07-01'],
                [173.75, '2024-08-01']
            ]
        },
        'sections': {
            'O/X 다리란?': 'O/X 다리는 다리가 서로 바깥쪽 또는 안쪽으로 기울어지는 상태를 말합니다.',
            'O/X 다리의 위험성': 'O/X 다리는 보행 문제를 유발할 수 있으며, 장기적으로 자세 문제를 일으킬 수 있습니다.',
            'O/X 다리 개선 방법': '교정 운동과 물리치료가 도움이 될 수 있습니다.',
            '권장 계획': '매일 교정 운동과 정기적인 검사 권장'
        }
    },
    {
        'title': '무릎 기울기',
        'alias': 'knee_angle',
        'description_label': '휘어짐 각도',
        'description_value': '178°',
        'status': '양호',
        'normal_range': [175.00, 180.00],  # Example range
        'trend': {
            '지난 3개월': [
                [177.50, '2024-06-01'],
                [178.00, '2024-07-01'],
                [178.25, '2024-08-01']
            ]
        },
        'sections': {
            '무릎 기울기란?': '무릎 기울기는 무릎이 휘어지는 각도를 말합니다.',
            '무릎 기울기의 위험성': '무릎 기울기는 관절에 압박을 유발할 수 있으며, 장기적으로 통증을 유발할 수 있습니다.',
            '무릎 기울기 개선 방법': '무릎 스트레칭과 강화 운동이 도움이 될 수 있습니다.',
            '권장 계획': '매일 무릎 스트레칭과 강화 운동을 권장합니다.'
        }
    }
]


def body_report(request, id):
    student = get_object_or_404(UserInfo, id=id)
        
    if not report_items:
        return render(request, '404.html', status=404)

    # Prepare trend data for each report item
    trend_data_dict = {item['alias']: item['trend'].get('지난 3개월', []) for item in report_items}

    context = {
        'student': student,
        'report_items': report_items,
        'trend_data_dict': trend_data_dict,
    }
    
    return render(request, 'body_report.html', context)



def policy(request):
    return render(request, 'policy.html')

class CustomPasswordChangeView(PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'password_change.html'
    success_url = '/password-change-done/'

# 코드 정보 조회 기능 추가 (240903 BS)
class CodeInfoViewSet(viewsets.ViewSet):
    queryset = CodeInfo.objects.all().order_by('-created_dt')
    serializer_class = CodeInfoSerializer
    # permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def get_code(self, request):
        group_id_list = self.request.query_params.getlist('group_id_list')
        if not group_id_list:
            return Response({'message': 'group_id_list_required'}, status=status.HTTP_400_BAD_REQUEST)
        results = CodeInfo.objects.filter(group_id__in=group_id_list)
        if not results.exists():
            return Response({"message": "code_not_found"})

        # Serialize the GaitResult objects
        serializer = CodeInfoSerializer(results, many=True)

        return Response({'data': serializer.data})

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
    tags=['gait-analysis']
)
@api_view(['POST'])
def create_gait_result(request):
    session_key = request.data.get('session_key')
    if not session_key:
        return Response({'message': 'session_key_required', 'status': 400})
    gait_data = request.data.get('gait_data')
    if not gait_data:
        return Response({'message': 'gait_data_required', 'status': 400})

    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response({'message': 'session_key_not_found', 'status': 404})

    try:
        user_info = UserInfo.objects.get(id=session_info.user_id)
    except UserInfo.DoesNotExist:
        return Response({'message': 'user_not_found', 'status': 401})

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
        return Response({'message': 'created_gait_result', 'status': 200})
    else:
        return Response({'message' : serializer.errors, 'status': 500})


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
    tags=['gait-analysis']
)
@api_view(['GET'])
def get_gait_result(request):
    if request.user.id is None:
        session_key = request.query_params.get('session_key')
        if not session_key:
            return Response({'message': 'session_key_required', 'status': 400})

        try:
            session_info = SessionInfo.objects.get(session_key=session_key)
        except SessionInfo.DoesNotExist:
            return Response({'message': 'session_key_not_found', 'status': 404})

        try:
            user_info = UserInfo.objects.get(id=session_info.user_id)
        except UserInfo.DoesNotExist:
            return Response({'message': 'user_not_found', 'status': 401})
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
                return Response({"message": "gait_result_not_found"})
            gait_results = GaitResult.objects.filter(
                user_id=user_id,
                created_dt__lte=current_result.created_dt
            ).order_by('-created_dt')

    if not gait_results.exists():
        return Response({"message": "gait_result_not_found", "status": 404})
    count = request.query_params.get('count', None)
    if count is not None:
        gait_results = gait_results.all()[:int(count)]

    # Serialize the GaitResult objects
    serializer = GaitResultSerializer(gait_results, many=True)

    # TODO: get range of gait parameters
    codeinfo = CodeInfo.objects.filter(group_id='02')
    code_ids

    import pdb; pdb.set_trace()

    # range_of_params = {}
    # for param in codeinfo.code_id:

    # range_of_params = {
    #     f'{param}_normal_range' : [codeinfo.normal_min_value, codeinfo.normal_max_value],
    #     f'{param}_value_range': [codeinfo.min_value, codeinfo.max_value],
    # }


    return Response({'data': serializer.data, 'message': 'OK', 'status': 200})
        
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
                    })
        },
        required=['session_key'],  # Add any required fields here
    ),
    responses={
        200: 'OK; created_body_result successfully',
        400: 'Bad Request; session_key is not provided in the request body',
        401: 'Unauthorized; incorrect user or password',
        404: 'Not Found; session_key is not found',
        500: 'Internal Server Error'
    },
    tags=['body-analysis']
)
@api_view(['POST'])
def create_body_result(request):
    session_key = request.data.get('session_key')
    if not session_key:
        return Response({'message': 'session_key_required', 'status': 400})
    body_data = request.data.get('body_data')
    if not body_data:
        return Response({'message': 'body_data_required', 'status': 400})

    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response({'message': 'session_key_not_found', 'status': 404})

    try:
        user_info = UserInfo.objects.get(id=session_info.user_id)
    except UserInfo.DoesNotExist:
        return Response({'message': 'user_not_found', 'status': 401})

    # Retrieve or create a fixed "null school" instance
    null_school, created = SchoolInfo.objects.get_or_create(
        id=-1,
        school_name='null',
        contact_number='null'
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
        return Response({'message': 'created_body_result', 'status': 200})
    else:
        return Response({'message' : serializer.errors, 'status': 500})

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
    tags=['body-analysis']
)
@api_view(['GET'])
def get_body_result(request):
    if request.user.id is None:
        session_key = request.query_params.get('session_key')
        if not session_key:
            return Response({'message': 'session_key_required', 'status': 400})

        try:
            session_info = SessionInfo.objects.get(session_key=session_key)
        except SessionInfo.DoesNotExist:
            return Response({'message': 'session_key_not_found', 'status': 404})

        try:
            user_info = UserInfo.objects.get(id=session_info.user_id)
        except UserInfo.DoesNotExist:
            return Response({'message': 'user_not_found', 'status': 401})
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
        return Response({"message": "body_result_not_found", "status": 404})

    count = request.query_params.get('count', None)
    if count is not None:
        body_results = body_results.all()[:int(count)]

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
    }
)
@api_view(['POST'])
def login_kiosk(request):
    kiosk_id = request.data.get('kiosk_id')
    if not kiosk_id:
        return Response({'message': 'kiosk_id_required', 'status': 400})
    
    # POST 메소드를 사용하여 키오스크 로그인 요청 처리
    session_key = uuid.uuid4().hex
    SessionInfo.objects.update_or_create(
        session_key=session_key,
        kiosk_id=kiosk_id,
    )

    return Response({'data' : {'session_key': session_key, 'message': 'success', 'status': 200}})

@swagger_auto_schema(
    method='post',
    operation_description="Login using session-key-generated QR code in mobile app",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'session_key': openapi.Schema(type=openapi.TYPE_STRING, description='Session key from QR code'),
            'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID (i.e., index)')
        },
        required=['session_key'],
    ),
    responses={
        200: openapi.Response('Login Success', 
                              openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                                  'data': 
                               openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'session_key': openapi.Schema(type=openapi.TYPE_STRING, description='Session key'),
                'message': openapi.Schema(type=openapi.TYPE_STRING, description='Success message'),
            }
        )})),
        400: 'Bad Request; session_key is not provided in the request body',
        404: 'Not Found; session_key is not found',
    }
)
@api_view(['POST'])
def login_mobile_qr(request):
    session_key = request.data.get('session_key')
    if not session_key:
        return Response({'message': 'session_key_required', 'status': 400})
    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response(
            {
                'message': 'session_key_not_found', 'status': 404
            })

    session_info.user_id = request.user.id
    session_info.save()

    return Response({'data': {'session_key': session_key}, 'message': 'login_success', 'status': 200})

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
    }
)
@api_view(['POST'])
def login_kiosk_id(request):
    session_key = request.data.get('session_key')
    if not session_key:
        return Response({'message': 'session_key_required', 'status': 400})
    
    phone_number = request.data.get('phone_number')
    password = request.data.get('password')
    
    if not phone_number or not password:
        return Response({'message': 'phone_number_and_password_required', 'status': 400})

    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response(
            {
                'message': 'session_key_not_found', 'status': 404
            })

    try:
        user_info = UserInfo.objects.get(phone_number=phone_number)
    except UserInfo.DoesNotExist:
        return Response({"message": "user_not_found", 'status': 401},
                )

    session_info.user_id = user_info.id
    session_info.save()

    if check_password(password, user_info.password) and (phone_number == user_info.phone_number):
        return Response({'data' : {'message': 'login_success', 'status': 200}, 'message': 'login_success', 'status': 200})
    else:
        return Response({'data': {'message': 'incorrect_password', 'status': 401}, 'message': 'incorrect_password', 'status': 401})

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
    }
)
@api_view(['GET'])
def get_userinfo_session(request):
    session_key = request.query_params.get('session_key')
    if not session_key:
        return Response({'message': 'session_key_required', 'status': 400})
    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response(
            {
                'message': 'session_key_not_found', 'status': 404,
            })
    
    try:
        user_info = UserInfo.objects.get(id=session_info.user_id)
    except UserInfo.DoesNotExist:
        return Response({"message": "user_not_found", "status": 401},
                )
    
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
    }
)
@api_view(['POST'])
def end_session(request):
    session_key = request.data.get('session_key')
    if not session_key:
        return Response({'message': 'session_key_required', 'status': 400})
    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response(
            {
                'message': 'session_key_not_found', 'status': 404
            })
    
    session_info.delete()
    return Response({'data' : {'message': 'session_closed', 'status': 200}, 'message': 'session_closed', 'status': 200})
