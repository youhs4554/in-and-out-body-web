import os

from django.contrib.auth.hashers import make_password
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
import requests
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from analysis.helpers import generate_presigned_url, parse_userinfo, upload_image_to_s3
from analysis.models import GaitResult, AuthInfo, UserInfo, CodeInfo, BodyResult, SessionInfo, SchoolInfo
from analysis.serializers import GaitResultSerializer, CodeInfoSerializer, BodyResultSerializer

import pytz
from django.core.paginator import Paginator  # 페이지네이션
from concurrent.futures import ThreadPoolExecutor  # 병렬 처리
from django.db.models import Subquery
from datetime import datetime as dt
from django.db import transaction  # DB 트랜잭션

kst = pytz.timezone('Asia/Seoul')


@swagger_auto_schema(
    method='post',
    operation_description="Authenticate mobile device using mobile_uid",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'mobile_uid': openapi.Schema(type=openapi.TYPE_STRING,
                                         description='Unique identifier for the mobile device'),
        },
        required=['mobile_uid'],
    ),
    responses={
        200: openapi.Response('Success', openapi.Schema(type=openapi.TYPE_OBJECT,
                                                        properties={
                                                            'data':
                                                                openapi.Schema(
                                                                    type=openapi.TYPE_OBJECT,
                                                                    properties={
                                                                        'user_info': openapi.Schema(
                                                                            type=openapi.TYPE_OBJECT,
                                                                            description='User information'),
                                                                        'jwt_tokens': openapi.Schema(
                                                                            type=openapi.TYPE_OBJECT,
                                                                            properties={
                                                                                'access_token': openapi.Schema(
                                                                                    type=openapi.TYPE_STRING,
                                                                                    description='Access token'),
                                                                                'refresh_token': openapi.Schema(
                                                                                    type=openapi.TYPE_STRING,
                                                                                    description='Refresh token'),
                                                                            }
                                                                        ),
                                                                    }
                                                                ),
                                                        })),
        400: 'Bad Request; mobile_uid is not provided in the request body',
        401: 'Unauthorized; incorrect user or password',
    }
)
@api_view(['POST'])
def login_mobile(request):
    mobile_uid = request.data.get('mobile_uid')
    if not mobile_uid:
        return Response({'message': 'mobile_uid_required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        auth_info = AuthInfo.objects.get(uid=mobile_uid)
    except AuthInfo.DoesNotExist:
        return Response({'message': 'user_not_found'}, status=status.HTTP_200_OK)

    authorized_user_info, user_created = UserInfo.objects.update_or_create(
        phone_number=auth_info.phone_number,
        defaults=dict(
            username=auth_info.phone_number,
            password=make_password(os.environ['DEFAULT_PASSWORD']),
        ))

    if authorized_user_info.school is not None:
        authorized_user_info.user_type = 'S'
    if authorized_user_info.organization is not None:
        authorized_user_info.user_type = 'O'
    else:
        authorized_user_info.user_type = 'G'

    authorized_user_info.save()

    token = TokenObtainPairSerializer.get_token(authorized_user_info)
    refresh_token = str(token)
    access_token = str(token.access_token)

    data_obj = {
        'user_info': parse_userinfo(authorized_user_info),
        'jwt_tokens': {
            'access_token': access_token,
            'refresh_token': refresh_token,
        },
    }

    auth_info.delete()

    return Response({'data': {k: v for k, v in data_obj.items() if v is not None}}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    operation_description="Authenticate mobile device using uuid",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'uuid': openapi.Schema(type=openapi.TYPE_STRING,
                                   description='Unique identifier for the mobile device'),
        },
        required=['uuid'],
    ),
    responses={
        200: openapi.Response('Success', openapi.Schema(type=openapi.TYPE_OBJECT,
                                                        properties={
                                                            'data':
                                                                openapi.Schema(
                                                                    type=openapi.TYPE_OBJECT,
                                                                    properties={
                                                                        'user_info': openapi.Schema(
                                                                            type=openapi.TYPE_OBJECT,
                                                                            description='User information'),
                                                                        'jwt_tokens': openapi.Schema(
                                                                            type=openapi.TYPE_OBJECT,
                                                                            properties={
                                                                                'access_token': openapi.Schema(
                                                                                    type=openapi.TYPE_STRING,
                                                                                    description='Access token'),
                                                                                'refresh_token': openapi.Schema(
                                                                                    type=openapi.TYPE_STRING,
                                                                                    description='Refresh token'),
                                                                            }
                                                                        ),
                                                                    }
                                                                ),
                                                        })),
        400: 'Bad Request; uuid is not provided in the request body',
    }
)
@api_view(['POST'])
def login_mobile_uuid(request):
    uuid = request.data.get('uuid')
    if not uuid:
        return Response({'message': 'uuid_required'}, status=status.HTTP_400_BAD_REQUEST)

    auth_info = AuthInfo.objects.update_or_create(uuid=uuid)[0]

    authorized_user_info, user_created = UserInfo.objects.update_or_create(
        phone_number=auth_info.uuid,
        defaults=dict(
            username=auth_info.uuid,
            password=make_password(os.environ['DEFAULT_PASSWORD']),
        ))

    if authorized_user_info.school is not None:
        authorized_user_info.user_type = 'S'
    if authorized_user_info.organization is not None:
        authorized_user_info.user_type = 'O'
    else:
        authorized_user_info.user_type = 'G'

    authorized_user_info.save()

    token = TokenObtainPairSerializer.get_token(authorized_user_info)
    refresh_token = str(token)
    access_token = str(token.access_token)

    data_obj = {
        'user_info': parse_userinfo(authorized_user_info),
        'jwt_tokens': {
            'access_token': access_token,
            'refresh_token': refresh_token,
        },
    }

    return Response({'data': {k: v for k, v in data_obj.items() if v is not None}}, status=status.HTTP_200_OK)


@api_view(['POST'])
def delete_user(request):
    user = request.user
    user_id = user.id

    try:
        user_info = UserInfo.objects.get(id=user_id)
    except UserInfo.DoesNotExist:
        return Response(
            {
                'message': 'user_not_found'
            })

    user_info.delete()
    data_obj = {
        'message': 'success',
    }
    return Response({'data': {k: v for k, v in data_obj.items() if v is not None}}, status=status.HTTP_200_OK)


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
                                              'session_key': openapi.Schema(type=openapi.TYPE_STRING,
                                                                            description='Session key'),
                                              'message': openapi.Schema(type=openapi.TYPE_STRING,
                                                                        description='Success message'),
                                          }
                                      )})),
        400: 'Bad Request; session_key is not provided in the request body',
        404: 'Not Found; session_key is not found',
    }
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def login_mobile_qr(request):
    session_key = request.data.get('session_key')
    if not session_key:
        return Response({'message': 'session_key_required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        session_info = SessionInfo.objects.get(session_key=session_key)
    except SessionInfo.DoesNotExist:
        return Response({'message': 'session_key_not_found'}, status=status.HTTP_404_NOT_FOUND)

    session_info.user_id = request.user.id
    session_info.save()

    return Response({'data': {'session_key': session_key}}, status=status.HTTP_200_OK)


# access token으로 사용자 정보 가져오기
# 수정이력 : 240903 BS 작성
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def get_user(request):
    user = request.user
    user_id = user.id

    try:
        user = UserInfo.objects.get(id=user_id)
    except UserInfo.DoesNotExist:
        return Response(
            {
                'message': 'user_not_found'
            })
    user_info = parse_userinfo(user)
    data_obj = {
        'user_info': user_info,
        'message': 'success',
    }
    return Response({'data': {k: v for k, v in data_obj.items() if v is not None}}, status=status.HTTP_200_OK)


# group_id 들에 대한 CodeInfo 정보 반환
# @param List group_id_list
# 수정이력 : 240903 BS 작성
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_code(request):
    group_id_list = request.query_params.getlist('group_id_list')

    if not group_id_list:
        return Response({'status': 'FAILURE', 'message': 'group_id_list_required'}, status=status.HTTP_400_BAD_REQUEST)

    results = CodeInfo.objects.filter(group_id__in=group_id_list)

    if not results.exists():
        return Response({"" "message": "code_not_found"}, status=status.HTTP_404_NOT_FOUND)

    # Serialize the CodeInfo objects
    serializer = CodeInfoSerializer(results, many=True)

    data = serializer.data
    return Response({'data': data}, status=status.HTTP_200_OK)


# 보행 결과 리스트 반환
# @param String? id : GaitResult의 id
# 수정이력 : 240903 BS 작성
# 수정이력 : 241205 - 페이지 네이션 추가
@swagger_auto_schema(
    method='get',
    operation_description="""select gait result list
    - page: page number. default 1
    - page_size: page size. default 10
    """,
    manual_parameters=[
        openapi.Parameter('page', openapi.IN_QUERY, description="page number.", type=openapi.TYPE_INTEGER, default=1),
        openapi.Parameter('page_size', openapi.IN_QUERY, description="page size(itmes)", type=openapi.TYPE_INTEGER,
                          default=10),
    ],
    responses={
        200: openapi.Response(
            description="Success",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "data": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_OBJECT, description="Result object")
                    ),
                    "total_pages": openapi.Schema(type=openapi.TYPE_INTEGER, description="Total number of pages."),
                    "current_page": openapi.Schema(type=openapi.TYPE_INTEGER, description="Current page number."),
                    "total_items": openapi.Schema(type=openapi.TYPE_INTEGER, description="Total number of items."),
                    "items": openapi.Schema(type=openapi.TYPE_INTEGER,
                                            description="Number of items in the current page."),
                },
            )
        ),
        400: 'Bad Request; page number out of range',
    },
    tags=['mobile']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_gait_result(request):
    user_id = request.user.id

    page_size = request.GET.get("page_size", 10)  # 한 페이지에 보여줄 개수 - 가변적으로 설정 가능
    page = request.GET.get("page", 1)  # 만약 GET 요청에 아무런 정보가 없으면 default 1페이지로 설정

    gait_results = GaitResult.objects.filter(user_id=user_id).order_by('-created_dt')

    # 'id'가 존재하면 created_dt를 기준으로 이전 6개의 결과를 가져오고 내림차순으로 정렬
    id = request.query_params.get('id', None)
    if id is not None:
        gait_results = GaitResult.objects.filter(
            user_id=user_id,
            created_dt__lte=Subquery(
                GaitResult.objects.filter(id=id, user_id=user_id)
                .values('created_dt')[:1]
            )
        ).order_by('-created_dt')[:6]
    else:
        if not gait_results.exists():
            return Response({"message": "gait_result_not_found"}, status=status.HTTP_200_OK)

    # 페이지네이터 선언
    paginator = Paginator(gait_results, page_size)

    try:
        current_page = paginator.page(page)  # 해당 페이지의 객체를 가져옴
    except:
        return Response({"message": "page number out of range"}, status=status.HTTP_400_BAD_REQUEST)

    minimal_gait_results = current_page.object_list  # 현재 페이지의 객체

    # Serialize the GaitResult objects
    serializer = GaitResultSerializer(minimal_gait_results, many=True)

    return Response({
        'data': serializer.data,  # 현재 페이지의 아이템 정보
        'total_pages': paginator.num_pages,  # 전체 페이지 수
        'current_page': int(page),  # 현재 페이지
        'total_items': paginator.count,  # 전체 아이템 개수
        'items': len(minimal_gait_results),  # 현재 페이지의 아이템 개수
    }, status.HTTP_200_OK)


# group_id 들에 대한 CodeInfo 정보 반환
# @param String? id : GaitResult의 id
# 수정이력 : 240903 BS 작성
# 수정이력 : 241203 - 페이지 네이션 추가
@swagger_auto_schema(
    method='get',
    operation_description="""select body result list
    - page: page number. default 1
    - page_size: page size. default 10
    """,
    manual_parameters=[
        openapi.Parameter('page', openapi.IN_QUERY, description="page number.", type=openapi.TYPE_INTEGER, default=1),
        openapi.Parameter('page_size', openapi.IN_QUERY, description="page size(itmes)", type=openapi.TYPE_INTEGER,
                          default=10),
    ],
    responses={
        200: openapi.Response(
            description="Success",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "data": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_OBJECT, description="Result object")
                    ),
                    "total_pages": openapi.Schema(type=openapi.TYPE_INTEGER, description="Total number of pages."),
                    "current_page": openapi.Schema(type=openapi.TYPE_INTEGER, description="Current page number."),
                    "total_items": openapi.Schema(type=openapi.TYPE_INTEGER, description="Total number of items."),
                    "items": openapi.Schema(type=openapi.TYPE_INTEGER,
                                            description="Number of items in the current page."),
                },
            )
        ),
        400: 'Bad Request; page number out of range',
    },
    tags=['mobile']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_body_result(request):
    user_id = request.user.id
    page_size = request.GET.get("page_size", 10)  # 한 페이지에 보여줄 개수 - 가변적으로 설정 가능
    page = request.GET.get("page", 1)  # 만약 GET 요청에 아무런 정보가 없으면 default 1페이지로 설정

    body_results = BodyResult.objects.filter(user_id=user_id).order_by('-created_dt')
    body_id = request.query_params.get('id', None)
    if body_id is not None:
        current_result = BodyResult.objects.filter(user_id=user_id, id=body_id).first()
        if not current_result:
            return Response({"message": "body_result_not_found"}, )

        body_results = BodyResult.objects.filter(
            user_id=user_id,
            created_dt__lte=current_result.created_dt
        ).order_by('-created_dt')[:7]
    else:
        if not body_results.exists():
            return Response({"message": "body_result_not_found"}, status=status.HTTP_200_OK)

    paginator = Paginator(body_results, page_size)  # 페이지네이터 생성

    try:
        currnet_page = paginator.page(page)  # 해당 페이지의 객체를 n개씩 가져옴
    except:
        return Response({"message": "page number out of range"}, status=status.HTTP_400_BAD_REQUEST)

    minimal_body_results = currnet_page.object_list  # 현재 페이지의 객체의 정보를 대입

    # 수정된 body_results를 리스트로 저장
    """ body_result -> 페이지네이션 처리 후 페이지 사이즈만큼의 쿼리셋 -> 
        minimal_body_results -> S3 이미지 객체를 S3 미리 서명된 URL로 변환 ->  
        updated_body_results """
    updated_body_results = []

    # body_result 객체를 받아서 이미지 URL을 생성하고, 상태를 확인
    def process_body_result(body_result):
        # Presigned URL 생성 및 상태 확인.
        created_dt = body_result.created_dt.strftime('%Y%m%dT%H%M%S%f')
        body_result.image_front_url = generate_presigned_url(file_keys=['front', created_dt])
        body_result.image_side_url = generate_presigned_url(file_keys=['side', created_dt])

        # URL 검증
        if requests.get(body_result.image_front_url).status_code in [400, 404]:
            body_result.image_front_url = None
        if requests.get(body_result.image_side_url).status_code in [400, 404]:
            body_result.image_side_url = None

        return body_result

    # 병렬 처리로 minimal_body_results 순회
    with ThreadPoolExecutor(max_workers=10) as executor:
        updated_body_results = list(executor.map(process_body_result, minimal_body_results))
    # 모든 객체를 한 번에 업데이트
    BodyResult.objects.bulk_update(updated_body_results, ['image_front_url', 'image_side_url'])

    # Serialize the BodyResult objects
    serializer = BodyResultSerializer(minimal_body_results, many=True)

    # 페이지네이션 INFO 및 정보 가공
    response_data = {
        'data': serializer.data,  # 현재 페이지의 아이템 정보
        'total_pages': paginator.num_pages,  # 전체 페이지 수
        'current_page': int(page),  # 현재 페이지
        'total_items': paginator.count,  # 전체 아이템 개수
        'items': minimal_body_results.count(),  # 현재 페이지의 아이템 개수
    }

    return Response(response_data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    operation_description="Delete gait result using gait_id",
    manual_parameters=[
        openapi.Parameter('id', openapi.IN_QUERY, description="gait id", type=openapi.TYPE_INTEGER),
    ],
    responses={
        200: 'Success',
        400: 'Bad Request; gait_id is not provided in the request body',
    },
    tags=['mobile']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def delete_gait_result(request):
    user_id = request.user.id
    gait_id = request.query_params.get('id', None)
    if not gait_id:
        return Response({'data': {'message': 'gait_id_required', 'status': 400}})
    current_result = GaitResult.objects.filter(user_id=user_id, id=gait_id).first()
    if not current_result:
        return Response({"message": "gait_result_not_found"}, )
    current_result.delete()

    # Serialize the GaitResult objects
    serializer = GaitResultSerializer(current_result)
    return Response({'data': serializer.data}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    operation_description="Delete body result using body_id",
    manual_parameters=[
        openapi.Parameter('id', openapi.IN_QUERY, description="body id", type=openapi.TYPE_INTEGER),
    ],
    responses={
        200: 'Success',
        400: 'Bad Request; body_id is not provided in the request body',
    },
    tags=['mobile']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def delete_body_result(request):
    user_id = request.user.id
    body_id = request.query_params.get('id', None)
    if not body_id:
        return Response({'data': {'message': 'body_id_required', 'status': 400}})
    current_result = BodyResult.objects.filter(user_id=user_id, id=body_id).first()
    if not current_result:
        return Response({"message": "body_result_not_found"}, )
    current_result.delete()

    # Serialize the BodyResult objects
    serializer = BodyResultSerializer(current_result)
    return Response({'data': serializer.data}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    operation_description="""Create a new body result record - mobile only
                            - header: Bearer token required
                            - body_data: Body data 
                            """,
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
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
                }),
            'image_front': openapi.Schema(type=openapi.TYPE_STRING,
                                          description='base64 encoded bytes of the front image'),
            'image_side': openapi.Schema(type=openapi.TYPE_STRING,
                                         description='base64 encoded bytes of the side image'),
        },
        required=['body_data'],  # Add any required fields here
    ),
    responses={
        200: 'OK; created_body_result successfully',
        400: 'Bad Request; token is not provided in the request body',
        401: 'Unauthorized; incorrect user or password | user_not_found',
        500: 'Internal Server Error'
    },
    tags=['mobile']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])  # JWT 토큰 인증
def create_body_result(request) -> Response:
    user_id = request.user.id
    if not user_id:
        return Response({'data': {'message': 'token_required', 'status': 400}})

    body_data = request.data.get('body_data')
    if not body_data:
        return Response({'data': {'message': 'body_data_required', 'status': 400}})

    try:
        user_info = UserInfo.objects.get(id=user_id)
    except UserInfo.DoesNotExist:
        return Response({'data': {'message': 'user_not_found', 'status': 401}})

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

    if not serializer.is_valid():
        return Response({'data': {'message': serializer.errors, 'status': 500}})  # 유효성 검사 실패

    try:
        with transaction.atomic():  # 트랜잭션 시작 (만약 중간에 예외 발생 시 rollback -> DB 반영 X)
            serializer.save()
            created_dt = dt.strptime(serializer.data['created_dt'], '%Y-%m-%dT%H:%M:%S.%f').strftime('%Y%m%dT%H%M%S%f')
            image_front_bytes = request.data.get('image_front', None)
            image_side_bytes = request.data.get('image_side', None)

            # 이미지 업로드 시도
            if image_front_bytes:
                upload_image_to_s3(image_front_bytes, file_keys=['front', created_dt])
            if image_side_bytes:
                upload_image_to_s3(image_side_bytes, file_keys=['side', created_dt])
    except ValueError as ve:
        return Response({'data': {'message': str(ve), 'status': 400}})  # 잘못된 요청 (이미지 처리 실패 - 이미지 base64 관련 문제)
    except Exception as e:
        return Response({'data': {'message': str(e), 'status': 500}})  # 서버 에러 (AWS S3 에러)

    return Response({'data': {'message': 'created_body_result', 'status': 200}})  # 성공 응답
