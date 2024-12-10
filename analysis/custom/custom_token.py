from drf_yasg.utils import swagger_auto_schema
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_yasg import openapi

"""토큰 관련 스웨거 문서화 커스텀 클래스"""
class CustomTokenObtainPairView(TokenObtainPairView):
    @swagger_auto_schema(
        operation_summary="로그인 토큰 발급(사용 X)",
        operation_description="""
                            사용 X
                            """,
        responses={
            200: openapi.Response(
                description="로그인 성공",
                examples={
                    "application/json": {
                        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
                    }
                }
            ),
            401: "인증 실패"
        },
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password'],
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='사용자 아이디'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='비밀번호')
            }
        )
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class CustomTokenRefreshView(TokenRefreshView):
    @swagger_auto_schema(
        operation_summary="토큰 갱신",
        operation_description="refresh token을 사용하여 새로운 access token을 발급받습니다.",
        responses={
            200: openapi.Response(
                description="토큰 갱신 성공",
                examples={
                    "application/json": {
                        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
                    }
                }
            ),
            401: openapi.Response(description="리프레시 토큰 만료 혹은 유효하지 않음",
                examples={
                    "application/json": {
                        "detail": "Token is invalid or expired",
                        "code": "token_not_valid"
                    }
                }
            )
        },
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refresh'],
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='리프레시 토큰')
            }
        )
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)