
from django.urls import path, include
from django.contrib.auth import views as auth_views

from . import views, views_mobile
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from django.urls import path, re_path
from django.conf import settings
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view( 
    openapi.Info( 
        title="Swagger API Document of In-and-Out-Body", 
        default_version="v1",
        description="In-and-Out-Body API 문서 입니다.", 
        terms_of_service="https://www.google.com/policies/terms/", 
        license=openapi.License(name="BSD License"),
    ), 
    public=True,
    permission_classes=(permissions.AllowAny,), 
)

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True, next_page='register'), name='login'),
    path('register/', views.register, name='register'),
    path('report/', views.report, name='report'),
    path('report/<int:id>/', views.report_detail, name='report_detail'),
    path('no-result/', views.no_result, name='no_result'),
    path('policy/', views.policy, name='policy'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),


    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-change-done/', auth_views.PasswordChangeDoneView.as_view(template_name='password_change_done.html'), name='password_change_done'),

    # for JWT token
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # for custom authentication process
    path('api/login-kiosk/', views.login_kiosk, name='login_kiosk'),
    path('api/login-kiosk-id/', views.login_kiosk_id, name='login_kiosk_id'),
    path('api/get-userinfo-session/', views.get_userinfo_session, name='get_userinfo_session'),
    path('api/end-session/', views.end_session, name='end_session'),

    path('api/analysis/gait/create_result/', views.create_gait_result, name='create_gait_result'),
    path('api/analysis/gait/get_result/', views.get_gait_result, name='get_gait_result'),
    path('api/analysis/body/create_result/', views.create_body_result, name='create_body_result'),
    path('api/analysis/body/get_result/', views.get_body_result, name='get_body_result'),
    path('api/analysis/get_info/', views.get_info, name='get_info'),

    # 기관 정보 조회 api
    path('api/search-organization/', views.search_organization, name='search_organization'),
    path('api/register-organization/', views.register_organization, name='register_organization'),
    path('api/get-organization-info/', views.get_organization_info, name='get_organization_info'),

    ## 모바일 전용 API (모바일 이외의 용도로 사용하지 말것)
    path('api/mobile/login-mobile/', views_mobile.login_mobile, name='mobile-auth-request_auth'), # 휴대폰 인증 요청
    path('api/mobile/login-mobile-qr/', views_mobile.login_mobile_qr, name='login_mobile_qr'), # 휴대폰에서 QR 인증 요청,
    path('api/mobile/user/get_user/', views_mobile.get_user, name='mobile-user-get_user'), # 사용자 정보 가져오기
    path('api/mobile/code/get_code/', views_mobile.get_code, name='mobile-code-get_code'), # 코드 정보 가져오기
    path('api/mobile/gait/get_gait_result/', views_mobile.get_gait_result, name='mobile-gait-get_gait_result'), # 보행 결과 가져오기
    path('api/mobile/body/get_body_result/', views_mobile.get_body_result, name='mobile-body-get_body_result'), # 체형 결과 가져오기

]

if settings.DEBUG:
    urlpatterns += [
        re_path(r'^docs(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name="schema-json"),
        re_path(r'^docs/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),    ]