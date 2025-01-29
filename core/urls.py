from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('menu/', views.menu, name='menu'),
    path('details/', views.details, name='details'),
    path('feedbacks/', views.feedbacks, name='feedbacks'),
    path('post_feedback/', views.post_feedback, name='post_feedback'),
    path('reserve/', views.reserve, name='reserve'),
    path('order/', views.order, name='order'),
]
