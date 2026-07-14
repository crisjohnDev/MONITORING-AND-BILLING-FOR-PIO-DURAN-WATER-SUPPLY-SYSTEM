from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from django.urls import path
from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("customer/profile/", views.CustomerProfileView.as_view(),name="customer-profile"),
    path("customer/dashboard/", views.CustomerDashboardView.as_view(),name="customer_dashboard"),
    path("customer/payments/", views.CustomerPaymentHistoryView.as_view(), name="customer_payments"),
    path("customer/profile/", views.CustomerProfileView.as_view(), name="customer_profile_api"),
    path("customer/notifications/", views.CustomerNotificationAPIView.as_view(), name="customer-notifications"),
    path("customer/notifications/unread-count/", views.NotificationUnreadCountAPIView.as_view(),name="notification-unread-count"),
]
