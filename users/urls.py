from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('otp_verification/', views.otp_verification, name='otp_verification'),
    path('profile/', views.profile, name='profile'),
    path('cancel_reservation/<int:reservation_id>/', views.cancel_reservation, name='cancel_reservation'),
    path('delete_feedback/<int:feedback_id>/', views.delete_feedback, name='delete_feedback'),
    path('register/', views.register, name='register'),
    path('account/login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
]
