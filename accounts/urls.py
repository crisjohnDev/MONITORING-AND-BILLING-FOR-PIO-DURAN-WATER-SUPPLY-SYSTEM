from django.urls import path
from . import views


urlpatterns = [
    path('', views.login_view, name='login-view'),
    path('user/logout/', views.logout_view, name='logout-view'),
]