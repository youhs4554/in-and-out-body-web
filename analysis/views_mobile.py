import os

from django.contrib.auth.hashers import make_password
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from analysis.helpers import parse_userinfo
from analysis.models import GaitResult, AuthInfo, UserInfo, CodeInfo, BodyResult
from analysis.serializers import GaitResultSerializer, CodeInfoSerializer, BodyResultSerializer


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
def request_auth(request):
    mobile_uid = request.data.get('mobile_uid')
    if not mobile_uid:
        return Response({'message': 'mobile_uid_required', 'status': 400})

    try:
        auth_info = AuthInfo.objects.get(uid=mobile_uid)
    except AuthInfo.DoesNotExist:
        return Response(
            {
                'message': 'user_not_found', 'status': 401
            })

    authorized_user_info, user_created = UserInfo.objects.update_or_create(
        phone_number=auth_info.phone_number,
        defaults=dict(
            username=auth_info.phone_number,
            password=make_password(os.environ['DEFAULT_PASSWORD']),
        ))

    authorized_user_info.user_type = 'G' if authorized_user_info.school is None else 'S'
    if authorized_user_info.user_type == 'G':
        authorized_user_info.username = f'test_{authorized_user_info.id}'

    authorized_user_info.save()

    token = TokenObtainPairSerializer.get_token(authorized_user_info)
    refresh_token = str(token)
    access_token = str(token.access_token)

    data_obj = {
        'data': {
            'user_info': parse_userinfo(authorized_user_info),
            'jwt_tokens': {
                'access_token': access_token,
                'refresh_token': refresh_token,
            },
        },
    }

    auth_info.delete()

    return Response({'data': {k: v for k, v in data_obj.items() if v is not None}, 'message': 'OK', 'status': 200})


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
    return Response({'data': {k: v for k, v in data_obj.items() if v is not None}})

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

    return Response({'data': serializer.data})

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
            return Response({"message": "gait_result_not_found"})

        gait_results = GaitResult.objects.filter(
            user_id=user_id,
            created_dt__lte=current_result.created_dt
        ).order_by('-created_dt')[:7]
    else:
        if not gait_results.exists():
            return Response({"message": "gait_result_not_found"})

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
        body_results = body_results.filter(id=body_id)

    if not body_results.exists():
        return Response({"message": "body_result_not_found"})

    # Serialize the GaitResult objects
    serializer = BodyResultSerializer(body_results, many=True)
    return Response({'data': serializer.data})