from django.urls import path
from django.contrib.auth import views as auth_views
from .views import home, upload_file, report, policy

urlpatterns = [
    path('', home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True, next_page='upload_file'), name='login'),
    path('upload/', upload_file, name='upload_file'),
    path('report/', report, name='report'),
    path('policy/', policy, name='policy'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]