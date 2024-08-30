from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import home, register_student, report, policy, UserInfoViewSet, GaitResultViewSet, \
    BodyResultViewSet, CustomPasswordChangeView

from rest_framework import routers

from . import views
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

router = routers.DefaultRouter()
router.register(r'users', UserInfoViewSet)
router.register(r'analysis/gait', GaitResultViewSet)
router.register(r'analysis/body', BodyResultViewSet)

urlpatterns = [
    path('', home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True, next_page='register_student'), name='login'),
    path('register-student/', register_student, name='register_student'),
    path('report/', report, name='report'),
    path('policy/', policy, name='policy'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('password-change/', CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-change-done/', auth_views.PasswordChangeDoneView.as_view(template_name='password_change_done.html'), name='password_change_done'),

    # for JWT token
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # for custom authentication process
    path('api/auth-mobile/', views.auth_mobile, name='auth_mobile'),
    path('api/user-mobile/', views.user_mobile, name='user_mobile'),
    path('api/login-kiosk/', views.login_kiosk, name='login_kiosk'),
    path('api/login-mobile-qr/', views.login_mobile_qr, name='login_mobile_qr'),
    path('api/login-kiosk-id/', views.login_kiosk_id, name='login_kiosk_id'),
    path('api/get-userinfo-session/', views.get_userinfo_session, name='get_userinfo_session'),
    path('api/end-session/', views.end_session, name='end_session'),
]

if settings.DEBUG:
    urlpatterns += [
        re_path(r'^docs(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name="schema-json"),
        re_path(r'^docs/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),    ]