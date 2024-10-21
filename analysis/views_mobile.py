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

from analysis.helpers import generate_presigned_url, parse_userinfo
from analysis.models import GaitResult, AuthInfo, UserInfo, CodeInfo, BodyResult, SessionInfo
from analysis.serializers import GaitResultSerializer, CodeInfoSerializer, BodyResultSerializer

import pytz
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
                'session_key': openapi.Schema(type=openapi.TYPE_STRING, description='Session key'),
                'message': openapi.Schema(type=openapi.TYPE_STRING, description='Success message'),
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
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_gait_result(request):
    user_id = request.user.id
    gait_results = GaitResult.objects.filter(user_id=user_id).order_by('-created_dt')
    id = request.query_params.get('id', None)
    if id is not None:
        current_result = GaitResult.objects.filter(user_id=user_id, id=id).first()
        if not current_result:
            return Response({"message": "gait_result_not_found"},)

        gait_results = GaitResult.objects.filter(
            user_id=user_id,
            created_dt__lte=current_result.created_dt
        ).order_by('-created_dt')[:6]
    else:
        if not gait_results.exists():
            return Response({"message": "gait_result_not_found"}, status=status.HTTP_200_OK)

    # Serialize the GaitResult objects
    serializer = GaitResultSerializer(gait_results, many=True)

    return Response({'data': serializer.data})

# group_id 들에 대한 CodeInfo 정보 반환
# @param String? id : GaitResult의 id
# 수정이력 : 240903 BS 작성
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_body_result(request):
    user_id = request.user.id
    body_results = BodyResult.objects.filter(user_id=user_id).order_by('-created_dt')
    body_id = request.query_params.get('id', None)
    if body_id is not None:
        current_result = BodyResult.objects.filter(user_id=user_id, id=body_id).first()
        if not current_result:
            return Response({"message": "body_result_not_found"},)

        body_results = BodyResult.objects.filter(
            user_id=user_id,
            created_dt__lte=current_result.created_dt
        ).order_by('-created_dt')[:7]
    else:
        if not body_results.exists():
            return Response({"message": "body_result_not_found"}, status=status.HTTP_200_OK)

    # 수정된 body_results를 리스트로 저장
    updated_body_results = []
    for body_result in body_results:
        created_dt = body_result.created_dt.strftime('%Y%m%dT%H%M%S%f')
        # Presigned URL 생성 (일정 시간 동안)
        body_result.image_front_url = generate_presigned_url(file_keys=['front', created_dt])
        body_result.image_side_url = generate_presigned_url(file_keys=['side', created_dt])

        if requests.get(body_result.image_front_url).status_code in [400, 404]:
            body_result.image_front_url = None
        if requests.get(body_result.image_side_url).status_code in [400, 404]:
            body_result.image_side_url = None

        updated_body_results.append(body_result)

    # 모든 객체를 한 번에 업데이트
    BodyResult.objects.bulk_update(updated_body_results, ['image_front_url', 'image_side_url'])

    # Serialize the GaitResult objects
    serializer = BodyResultSerializer(body_results, many=True)
    return Response({'data': serializer.data}, status=status.HTTP_200_OK)

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
        return Response({"message": "gait_result_not_found"},)
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
        return Response({"message": "body_result_not_found"},)
    current_result.delete()

    # Serialize the BodyResult objects
    serializer = BodyResultSerializer(current_result)
    return Response({'data': serializer.data}, status=status.HTTP_200_OK)