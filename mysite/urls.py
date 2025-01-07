from django.contrib import admin
from django.urls import include, path
from prometheus_client import make_wsgi_app

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('analysis.urls')),
    path('metrics', make_wsgi_app()),
]