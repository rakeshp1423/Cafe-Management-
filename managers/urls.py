from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.manager_login, name='manager_login'),
    path('dashboard/', views.manager_dashboard, name='manager_dashboard'),
]
