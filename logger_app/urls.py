from django.urls import path
from . import views

urlpatterns = [
    path('fetch-logs/', views.fetch_logs, name='fetch_logs'),
]
