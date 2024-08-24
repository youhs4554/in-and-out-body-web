from django.urls import path, include
from django.contrib.auth import views as auth_views
# from .views import home, upload_file, report, policy, UserViewSet, GroupViewSet, GaitAnalysisViewSet, PoseAnalysisViewSet
from .views import home, upload_file, report, policy, GroupViewSet, UserInfoViewSet, GaitResultViewSet, \
    BodyResultViewSet, CustomPasswordChangeView

from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'users', UserInfoViewSet)
router.register(r'groups', GroupViewSet)
router.register(r'gaits', GaitResultViewSet)
router.register(r'bodies', BodyResultViewSet)

urlpatterns = [
    path('', home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True, next_page='upload_file'), name='login'),
    path('upload/', upload_file, name='upload_file'),
    path('report/', report, name='report'),
    path('policy/', policy, name='policy'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('password-change/', CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-change-done/', auth_views.PasswordChangeDoneView.as_view(template_name='password_change_done.html'), name='password_change_done'),
]