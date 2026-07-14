from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    # path('new-applicants/', views.new_applicants, name='new_applicants'),
    path('customer-list/', views.customer_list, name='customers'),
    path('add-customer/', views.add_customer, name='add-customer'),
    path('pwss/import-customers/', views.import_customers, name='import_customers'),
    # path("approve-applicant/<int:id>/", views.approve_applicant, name="approve_applicant"),
    # path("decline-applicant/<int:id>/", views.decline_applicant, name="decline_applicant"),
    # path("customer/suspend/<int:id>/", views.suspend_customer, name="suspend_customer"),
    path("customer/delete/<int:id>/", views.delete_customer, name="delete_customer"),
    # path("customer/reactivate/<int:id>/", views.reactivate_customer, name="reactivate_customer"),
    path('billing/', views.billing, name='billing'),
    path('create-bill/', views.create_bill, name='create_bill'),
    path('payment/', views.payment, name='payments'),
    path("process-payment/<int:id>/", views.process_payment, name="process_payment"),
    path('reports/', views.reports, name='reports'),
    path("official-receipt/<int:payment_id>/", views.official_receipt, name="official_receipt",),
    path("customer/<int:customer_id>/",views.customer_profile, name="customer_profile"),
    path('post-notification/', views.post_notification, name='post-notifacation'),
    path("notifications/delete/<int:pk>/", views.delete_notification, name="delete-notification"),
    path("reports/paid/", views.paid_report, name="paid_report"),
    path("reports/unpaid/", views.unpaid_report, name="unpaid_report"),
]