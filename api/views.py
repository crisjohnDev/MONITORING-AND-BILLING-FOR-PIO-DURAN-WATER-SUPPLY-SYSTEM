from django.shortcuts import render

# Create your views here.
from django.db.models import Q
from rest_framework import generics
from .serializers import RegisterSerializer, CustomerSerializer, NotificationSerializer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from core.models import Billing, Payment, Notification

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

class CustomerProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = CustomerSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data)

        return Response(serializer.errors, status=400)
    
class CustomerDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        customer = request.user.customer_profile

        unpaid = Billing.objects.filter(
            customer=customer,
            status="unpaid"
        ).order_by("-billing_month")

        paid = Billing.objects.filter(
            customer=customer,
            status="paid"
        ).order_by("-billing_month")

        return Response({
            "customer": {
                "fullname": customer.fullname,
                "submitter_no": customer.submitter_no,
            },

            "current_bills": [
                {
                    "id": bill.id,
                    "period": bill.billing_month.strftime("%B %Y"),
                    "amount": str(bill.total_amount),
                    "due_date": bill.due_date,
                    "status": bill.status,
                }
                for bill in unpaid
            ],

            "paid_bills": [
                {
                    "id": bill.id,
                    "period": bill.billing_month.strftime("%B %Y"),
                    "amount": str(bill.total_amount),
                    "paid_date": getattr(
                        getattr(bill, "payment", None),
                        "payment_date",
                        None,
                    ),
                }
                for bill in paid
            ]
        })
    
class CustomerPaymentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        customer = request.user.customer_profile

        payments = (
            Payment.objects
            .filter(billing__customer=customer)
            .select_related("billing", "billing__customer")
            .order_by("-payment_date")
        )

        data = []

        for payment in payments:
            data.append({
                "id": payment.id,
                "receipt_number": payment.receipt_number,
                "amount_paid": str(payment.amount_paid),
                "payment_date": payment.payment_date,
                "remarks": payment.remarks,

                "billing": {
                    "submitter_no": payment.billing.customer.submitter_no,
                    "billing_month": payment.billing.billing_month.strftime("%B %Y"),

                    "previous_reading": str(payment.billing.previous_reading),
                    "current_reading": str(payment.billing.current_reading),
                    "consumption": str(payment.billing.consumption),
                    "rate_per_cubic": str(payment.billing.rate_per_cubic),

                    "connection_fee": str(payment.billing.connection_fee or 0),
                    "reconnection_fee": str(payment.billing.reconnection_fee or 0),
                    "violation_fee": str(payment.billing.violation_fee or 0),
                    "penalty_fee": str(payment.billing.penalty_fee or 0),

                    "total_amount": str(payment.billing.total_amount),
                    "due_date": payment.billing.due_date.strftime("%B %d, %Y"),
                    "status": payment.billing.status,
                }
            })

        return Response(data)
    
class CustomerProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    # Get logged-in customer profile
    def get(self, request):

        customer = request.user.customer_profile

        return Response({
            "id": customer.id,
            "fullname": customer.fullname,
            "address": customer.address,
            "status": customer.status,
            "submitter_no": customer.submitter_no,
        })

    # Create customer profile
    def post(self, request):

        serializer = CustomerSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data)

        return Response(serializer.errors, status=400)
    
class CustomerNotificationAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        customer = request.user.customer_profile

        # Extract barangay from address
        barangay = ""

        parts = customer.address.split(",")

        if len(parts) >= 2:
            barangay = parts[1].strip()

        notifications = Notification.objects.filter(

            Q(target="all") |

            Q(
                target="customer",
                customer=customer
            ) |

            Q(
                target="barangay",
                barangay=barangay
            )

        ).order_by("-created_at")

        serializer = NotificationSerializer(
            notifications,
            many=True
        )

        return Response(serializer.data)