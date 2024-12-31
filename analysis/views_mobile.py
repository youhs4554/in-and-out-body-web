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

from analysis.helpers import generate_presigned_url, parse_userinfo, upload_image_to_s3, verify_image
from analysis.models import GaitResult, AuthInfo, UserInfo, CodeInfo, BodyResult, SessionInfo, SchoolInfo, Keypoint
from analysis.serializers import GaitResultSerializer, CodeInfoSerializer, BodyResultSerializer, KeypointSerializer

import pytz
from django.core.paginator import Paginator  # 페이지네이션
from concurrent.futures import ThreadPoolExecutor  # 병렬 처리
from django.db.models import Subquery
from datetime import datetime as dt
from django.db import transaction  # DB 트랜잭션

kst = pytz.timezone('Asia/Seoul')


@swagger_auto_schema(
    method='post',
    operation_summary="모버알 로그인(토큰 발급)",
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

    authorized_user_info, user_created = UserInfo.objects.get_or_create(
        phone_number=auth_info.phone_number,
        defaults=dict(
            username=auth_info.phone_number,
            password=make_password(os.environ['DEFAULT_PASSWORD']),
        ))

    if authorized_user_info.school is not None:
        authorized_user_info.user_type = 'S'
    elif authorized_user_info.organization is not None:  # if -> elif로 수정
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
    operation_summary="UUID 로그인",
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

    authorized_user_info, user_created = UserInfo.objects.get_or_create(
        phone_number=auth_info.uuid,
        defaults=dict(
            username=auth_info.uuid,
            password=make_password(os.environ['DEFAULT_PASSWORD']),
        ))

    if authorized_user_info.school is not None:
        authorized_user_info.user_type = 'S'
    elif authorized_user_info.organization is not None:
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


@swagger_auto_schema(
    method='post',
    operation_summary="회원 탈퇴",
    operation_description="Delete user information",
    responses={
        200: openapi.Response('Success',
                              openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                                  'data':
                                      openapi.Schema(
                                          type=openapi.TYPE_OBJECT,
                                          properties={
                                              'message': openapi.Schema(type=openapi.TYPE_STRING,
                                                                        description='Success message'),
                                          }
                                      )}),
                              ),
        404: 'Not Found; user_not_found',
    },
    tags=['mobile']
)
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
    operation_summary="모바일 -> 키오스크 로그인",
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

@swagger_auto_schema(
    method='post',
    operation_summary="사용자 정보 조회",
    operation_description="Get user information using access token",
    responses={
        200: openapi.Response('Success',
                              openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                                  'data':
                                      openapi.Schema(
                                          type=openapi.TYPE_OBJECT,
                                          properties={
                                              'user_info': openapi.Schema(type=openapi.TYPE_OBJECT,
                                                                          description='User information'),
                                              'message': openapi.Schema(type=openapi.TYPE_STRING,
                                                                        description='Success message'),
                                          }
                                      )}),
                              ),
        404: 'Not Found; user_not_found',
    },
    tags=['mobile']
)
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
@swagger_auto_schema(
    method='get',
    operation_summary="체형 계산 코드 정보 조회",
    operation_description="""select code info list
                            - group_id_list: list of group_id
                            ex) 01, 02
                            """,
    manual_parameters=[
        openapi.Parameter('group_id_list', openapi.IN_QUERY, description="group_id list", type=openapi.TYPE_INTEGER),
    ],
    responses={
        200: openapi.Response(
            description="Success",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "data": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "group_id": openapi.Schema(type=openapi.TYPE_STRING),
                                "code_id": openapi.Schema(type=openapi.TYPE_STRING),
                                "code_name": openapi.Schema(type=openapi.TYPE_STRING),
                                "min_value": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "max_value": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "normal_min_value": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "normal_max_value": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "caution_min_value": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "caution_max_value": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "outline": openapi.Schema(type=openapi.TYPE_STRING),
                                "risk": openapi.Schema(type=openapi.TYPE_STRING),
                                "improve": openapi.Schema(type=openapi.TYPE_STRING),
                                "recommended": openapi.Schema(type=openapi.TYPE_ARRAY,
                                                              items=openapi.Schema(type=openapi.TYPE_STRING), ),
                                "title": openapi.Schema(type=openapi.TYPE_STRING),
                                "title_outline": openapi.Schema(type=openapi.TYPE_STRING),
                                "title_risk": openapi.Schema(type=openapi.TYPE_STRING),
                                "title_improve": openapi.Schema(type=openapi.TYPE_STRING),
                                "title_recommended": openapi.Schema(type=openapi.TYPE_STRING),
                                "unit_name": openapi.Schema(type=openapi.TYPE_STRING),
                                "seq_no": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "display_ticks": openapi.Schema(type=openapi.TYPE_ARRAY,
                                                                items=openapi.Schema(type=openapi.TYPE_STRING)),
                                "direction": openapi.Schema(type=openapi.TYPE_STRING),
                                "created_dt": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                            }
                        )
                    ),
                },
            )
        ),
        400: 'Bad Request; group_id_list_required',
        404: 'Not Found; code_not_found',
    },
    tags=['mobile']
)
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
    operation_summary="게이트 결과 리스트 조회",
    operation_description="""select gait result list
    - page: page number. default 1
    - page_size: page size. default 10
    """,
    manual_parameters=[
        openapi.Parameter('page', openapi.IN_QUERY, description="page number.", type=openapi.TYPE_INTEGER, default=1),
        openapi.Parameter('page_size', openapi.IN_QUERY, description="page size(items)", type=openapi.TYPE_INTEGER,
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
# 수정이력 : 241211 - mobile_yn 필터링 추가
# 수정이력 : 241217 - mobile_yn 디폴트 all -> n
@swagger_auto_schema(
    method='get',
    operation_summary="체형 결과 리스트 조회",
    operation_description="""select body result list
    - page: page number. default 1
    - page_size: page size. default 10
    - mobile: y: mobile, n: kiosk. default 'n'
    """,
    manual_parameters=[
        openapi.Parameter('page', openapi.IN_QUERY, description="page number.", type=openapi.TYPE_INTEGER, default=1),
        openapi.Parameter('page_size', openapi.IN_QUERY, description="page size(items)", type=openapi.TYPE_INTEGER,
                          default=10),
        openapi.Parameter('mobile', openapi.IN_QUERY, description="'y': mobile, 'n': kiosk, default: 'n'",
                          type=openapi.TYPE_STRING),
    ],
    responses={
        200: openapi.Response(
            description="Success",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "data": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "student_grade": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "student_class": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "student_number": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "face_level_angle": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "shoulder_level_angle": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "hip_level_angle": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "leg_length_ratio": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "left_leg_alignment_angle": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "right_leg_alignment_angle": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "left_back_knee_angle": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "right_back_knee_angle": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "forward_head_angle": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "scoliosis_shoulder_ratio": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "scoliosis_hip_ratio": openapi.Schema(type=openapi.TYPE_NUMBER),
                                "image_front_url": openapi.Schema(type=openapi.TYPE_STRING),
                                "image_side_url": openapi.Schema(type=openapi.TYPE_STRING),
                                "mobile_yn": openapi.Schema(type=openapi.TYPE_STRING, description="y: mobile, n: kiosk",
                                                            default="n"),
                                "created_dt": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                                "user": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "school": openapi.Schema(type=openapi.TYPE_INTEGER),
                            }
                        )
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
    mobile = request.GET.get("mobile", "n")  # mobile_yn 필터링

    # 기본 쿼리셋 정의
    query_filters = {'user_id': user_id}

    # mobile 파라미터가 있는 경우에만 필터 추가
    if mobile is not None:
        query_filters['mobile_yn'] = mobile

    body_results = BodyResult.objects.filter(**query_filters).order_by('-created_dt')

    body_id = request.query_params.get('id', None)
    if body_id is not None:
        current_result = BodyResult.objects.filter(user_id=user_id, id=body_id).first()
        if not current_result:
            return Response({"message": "body_result_not_found"})

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
    method='get',
    operation_summary="체형 결과 단건 조회",
    operation_description="""Get body result by ID
    - mobile only
    - header: Bearer token required
    - returns front and side data with keypoints
    """,
    responses={
        200: openapi.Response(
            description='Success',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'front_data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'results': openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'shoulder_level_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    'hip_level_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    'face_level_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    'scoliosis_shoulder_ratio': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    'scoliosis_hip_ratio': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    'leg_length_ratio': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    'left_leg_alignment_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    'right_leg_alignment_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                                }
                            ),
                            'keypoints': openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        'x': openapi.Schema(type=openapi.TYPE_NUMBER),
                                        'y': openapi.Schema(type=openapi.TYPE_NUMBER),
                                        'z': openapi.Schema(type=openapi.TYPE_NUMBER),
                                        'visibility': openapi.Schema(type=openapi.TYPE_NUMBER),
                                        'presence': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    }
                                )
                            )
                        }
                    ),
                    'side_data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'results': openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'forward_head_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    'left_back_knee_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    'right_back_knee_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                                }
                            ),
                            'keypoints': openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        'x': openapi.Schema(type=openapi.TYPE_NUMBER),
                                        'y': openapi.Schema(type=openapi.TYPE_NUMBER),
                                        'z': openapi.Schema(type=openapi.TYPE_NUMBER),
                                        'visibility': openapi.Schema(type=openapi.TYPE_NUMBER),
                                        'presence': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    }
                                )
                            )
                        }
                    ),
                    'image_front': openapi.Schema(type=openapi.TYPE_STRING),
                    'image_side': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )
        ),
        400: 'Bad Request; body_id_required',
        401: 'Unauthorized',
        404: 'Not Found; body_result_not_found',
        500: 'Internal Server Error',
    },
    tags=['mobile']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_body_result_id(request, id):
    user_id = request.user.id

    if not id:  # body_id가 없는 경우
        return Response({'data': {'message': 'body_id_required'}}, status=status.HTTP_400_BAD_REQUEST)

    # keypoints 같이 조회
    body_result = BodyResult.objects.prefetch_related('keypoints').filter(
        user_id=user_id,
        id=id
    ).first()
    if body_result is None:  # body_result가 없는 경우(존재하지 않거나, 회원 id와 매칭되는 body_result가 아닌경우)
        return Response({'data': {'message': 'body_result_not_found'}}, status=status.HTTP_404_NOT_FOUND)

    try:
        # 이미지 URL 생성
        created_dt = body_result.created_dt.strftime('%Y%m%dT%H%M%S%f')
        image_front_url = generate_presigned_url(file_keys=['front', created_dt])
        image_side_url = generate_presigned_url(file_keys=['side', created_dt])

        # image_front_url, image_side_url 1시간 접근 가능 URL 업데이트
        body_result.image_front_url = image_front_url
        body_result.image_side_url = image_side_url
        body_result.save()

        # Front data 구성
        front_data = {
            'results': {
                'shoulder_level_angle': body_result.shoulder_level_angle,
                'hip_level_angle': body_result.hip_level_angle,
                'face_level_angle': body_result.face_level_angle,
                'scoliosis_shoulder_ratio': body_result.scoliosis_shoulder_ratio,
                'scoliosis_hip_ratio': body_result.scoliosis_hip_ratio,
                'leg_length_ratio': body_result.leg_length_ratio,
                'left_leg_alignment_angle': body_result.left_leg_alignment_angle,
                'right_leg_alignment_angle': body_result.right_leg_alignment_angle,
            },
            'keypoints': []
        }

        # Side data 구성
        side_data = {
            'results': {
                'forward_head_angle': body_result.forward_head_angle,
                'left_back_knee_angle': body_result.left_back_knee_angle,
                'right_back_knee_angle': body_result.right_back_knee_angle,
            },
            'keypoints': []
        }

        # Keypoints 데이터 처리
        for keypoint in body_result.keypoints.all():  # Keypoint 객체 순회(총 2개)
            keypoint_data = [
                {
                    'x': x,
                    'y': y,
                    'z': z,
                    'visibility': v,
                    'presence': p
                }
                for x, y, z, v, p in zip(
                    keypoint.x,
                    keypoint.y,
                    keypoint.z,
                    keypoint.visibility,
                    keypoint.presence
                )
            ]

            if keypoint.pose_type == 'front':  # pose별 keypoint 데이터 분리
                front_data['keypoints'] = keypoint_data
            else:
                side_data['keypoints'] = keypoint_data

        # 최종 응답 데이터 구성
        response_data = {
            'front_data': front_data,
            'side_data': side_data,
            'image_front': image_front_url,
            'image_side': image_side_url
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'data': {'message': str(e)}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_summary="게이트 결과 삭제",
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
    operation_summary="체형 결과 삭제",
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
    operation_summary="체형 결과 생성",
    operation_description="""Create a new body result record
    - mobile only
    - AI server result --> image base64 add --> API request --> DB save
    - header: Bearer token required
    - front_data: Front pose results and keypoints (33 keypoints required)
    - side_data: Side pose results and keypoints (33 keypoints required)
    - keypoints idx : https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/pose.md#pose-landmark-model-blazepose-ghum-3d
    """,
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'front_data': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'results': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'shoulder_level_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'hip_level_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'face_level_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'scoliosis_shoulder_ratio': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'scoliosis_hip_ratio': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'leg_length_ratio': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'left_leg_alignment_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'right_leg_alignment_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                        }
                    ),
                    'keypoints': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'x': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'y': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'z': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'visibility': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'presence': openapi.Schema(type=openapi.TYPE_NUMBER),
                            }
                        )
                    )
                }
            ),
            'side_data': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'results': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'forward_head_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'left_back_knee_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'right_back_knee_angle': openapi.Schema(type=openapi.TYPE_NUMBER),
                        }
                    ),
                    'keypoints': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'x': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'y': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'z': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'visibility': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'presence': openapi.Schema(type=openapi.TYPE_NUMBER),
                            }
                        )
                    )
                }
            ),
            'image_front': openapi.Schema(type=openapi.TYPE_STRING),
            'image_side': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['front_data', 'side_data', 'image_front', 'image_side']
    ),
    responses={
        200: openapi.Response(
            description='Success',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'message': openapi.Schema(type=openapi.TYPE_STRING),
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        }
                    )
                }
            )
        ),
        400: 'Bad Request',
        401: 'Unauthorized',
        500: 'Internal Server Error',
    },
    tags=['mobile']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_body_result(request) -> Response:
    user_id = request.user.id
    if not user_id:
        return Response({'data': {'message': 'token_required'}}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # 데이터 추출
        front_data = request.data.get('front_data', {})
        side_data = request.data.get('side_data', {})

        # results 데이터 병합
        body_data = {
            **front_data.get('results', {}),
            **side_data.get('results', {}),
            'mobile_yn': 'y',
            'user': user_id
        }

        # 사용자 정보 확인
        try:
            user_info = UserInfo.objects.get(id=user_id)
        except UserInfo.DoesNotExist:  # 유저가 존재하지 않는 경우
            return Response({'data': {'message': 'user_not_found'}}, status=status.HTTP_401_UNAUTHORIZED)

        # null_school 처리
        null_school, created = SchoolInfo.objects.get_or_create(
            id=-1,
            defaults={'school_name': 'N/A', 'contact_number': 'N/A'}
        )

        # 학교 정보 설정
        if user_info.school is None:
            body_data['school'] = null_school.id  # 학교가 없는 경우 id -1로 저장
        else:  # 학교가 있는 경우 해당 유저의 반, 학년, 학번을 저장
            body_data['school'] = user_info.school.id
            body_data['student_grade'] = user_info.student_grade
            body_data['student_class'] = user_info.student_number
            body_data['student_number'] = user_info.student_number

        # BodyResult 생성
        serializer = BodyResultSerializer(data=body_data)
        if not serializer.is_valid():
            return Response({'data': {'message': serializer.errors}}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            body_result = serializer.save()  # BodyResult 저장

            # Front Keypoints 저장
            front_keypoints = front_data.get('keypoints', [])
            if len(front_keypoints) == 33:  # keypoints는 총 33개의 데이터여야 함
                front_keypoint_data = {
                    'body_result': body_result.id,
                    'pose_type': 'front',
                    'x': [float(kp['x']) for kp in front_keypoints],
                    'y': [float(kp['y']) for kp in front_keypoints],
                    'z': [float(kp['z']) for kp in front_keypoints],
                    'visibility': [float(kp['visibility']) for kp in front_keypoints],
                    'presence': [float(kp['presence']) for kp in front_keypoints]
                }
                front_keypoint_serializer = KeypointSerializer(data=front_keypoint_data)
                if not front_keypoint_serializer.is_valid():
                    raise ValueError(f"Invalid front keypoints: {front_keypoint_serializer.errors}")
                front_keypoint_serializer.save()
            else:
                raise ValueError(f"Invalid front keypoints: {front_keypoints}")  # front_keypoints != 33

            # Side Keypoints 저장
            side_keypoints = side_data.get('keypoints', [])
            if len(side_keypoints) == 33:
                side_keypoint_data = {
                    'body_result': body_result.id,
                    'pose_type': 'side',
                    'x': [float(kp['x']) for kp in side_keypoints],
                    'y': [float(kp['y']) for kp in side_keypoints],
                    'z': [float(kp['z']) for kp in side_keypoints],
                    'visibility': [float(kp['visibility']) for kp in side_keypoints],
                    'presence': [float(kp['presence']) for kp in side_keypoints]
                }
                side_keypoint_serializer = KeypointSerializer(data=side_keypoint_data)
                if not side_keypoint_serializer.is_valid():
                    raise ValueError(f"Invalid side keypoints: {side_keypoint_serializer.errors}")
                side_keypoint_serializer.save()
            else:
                raise ValueError(f"Invalid side keypoints: {side_keypoints}")

            # 이미지 처리
            # created_dt = dt.now().strftime('%Y%m%dT%H%M%S%f')
            # String -> datetime 변환 후 날짜포맷 설정
            _db_created_dt = dt.strptime(serializer.data['created_dt'], '%Y-%m-%dT%H:%M:%S.%f')

            created_dt = _db_created_dt.strftime('%Y%m%dT%H%M%S%f')

            image_front = request.data.get('image_front')
            image_side = request.data.get('image_side')

            if image_front and image_side:
                try:
                    verified_front = verify_image(image_front)
                    verified_side = verify_image(image_side)
                    upload_image_to_s3(verified_front, file_keys=['front', created_dt])
                    upload_image_to_s3(verified_side, file_keys=['side', created_dt])
                except ValueError as ve:
                    raise ValueError(f"Invalid image format: {str(ve)}")
            else:  # 이미지 누락 처리
                missing_images = []
                if not image_front: missing_images.append("image_front")
                if not image_side: missing_images.append("image_side")
                raise ValueError(f"Missing images: {', '.join(missing_images)}")

        return Response(  # 200(생성) 응답
            {'data': {'message': 'created_body_result', 'id': serializer.data['id']}},
            status=status.HTTP_200_OK
        )

    except ValueError as ve:
        return Response({'data': {'message': str(ve)}}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'data': {'message': str(e)}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_summary="체형 결과 ID값 리스트 조회",
    operation_description="""select body result id list
    - mobile created data only(mobile_yn = 'y')
    - JWT Token required    
    """,
    # 응답값 정의
    responses={
        200: openapi.Response(
            description="Success",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "data": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "message": openapi.Schema(type=openapi.TYPE_STRING, description="Success message"),
                            "body_results": openapi.Schema(type=openapi.TYPE_ARRAY,
                                                           items=openapi.Schema(type=openapi.TYPE_INTEGER),
                                                           description="Body result ID list"),
                            "items": openapi.Schema(type=openapi.TYPE_INTEGER, description="Number of items")
                        }
                    )
                }
            )
        ),
        401: 'Unauthorized; user_not_found',
    },
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def mobile_body_sync(request):
    # 사용자 Id
    user_id = request.user.id
    try:
        user_body_id_list = BodyResult.objects.filter(user_id=user_id, mobile_yn='y').values_list('id', flat=True)

        return Response(
            {'data': {'message': 'success', 'body_results': user_body_id_list, 'items': len(user_body_id_list)}},
            status=status.HTTP_200_OK)

    except UserInfo.DoesNotExist:
        return Response({'data': {'message': 'user_not_found'}}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({'data': {'message': str(e)}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# @api_view(['GET'])
# @permission_classes([permissions.IsAuthenticated])
# def mobile_gait_sync(request):  # 아직 사용 X

#     # 사용자 Id
#     user_id = request.user.id
#     try:
#         user_gait_id_list = GaitResult.objects.filter(user_id=user_id).values_list('id', flat=True)

#         return Response(
#             {'data': {'message': 'success', 'gait_results': user_gait_id_list, 'items': len(user_gait_id_list)}},
#             status=status.HTTP_200_OK)

#     except UserInfo.DoesNotExist:
#         return Response({'data': {'message': 'user_not_found'}}, status=status.HTTP_401_UNAUTHORIZED)