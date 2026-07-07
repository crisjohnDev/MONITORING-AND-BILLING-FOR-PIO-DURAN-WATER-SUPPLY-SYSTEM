from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from customer.models import Customer
from django.contrib import messages
from accounts.models import User
from django.db.models import Q, Sum
from datetime import datetime, date
import re
from .models import Billing, Payment
from decimal import Decimal

@login_required
def admin_dashboard(request):

    total_connections = Customer.objects.filter(
        status="active",
        is_active=True
    ).count()

    pending_applicants = Customer.objects.filter(
        status="pending"
    ).count()

    current_month = date.today().strftime("%B %Y")

    total_bills = Billing.objects.count()
    paid_bills = Billing.objects.filter(status="paid").count()

    if total_bills > 0:
        collection_rate = round((paid_bills / total_bills) * 100, 1)
    else:
        collection_rate = 0

    recent_billings = (
        Billing.objects
        .select_related("customer")
        .order_by("-created_at")[:10]
    )

    context = {
        "total_connections": total_connections,
        "pending_applicants": pending_applicants,
        "current_month": current_month,
        "collection_rate": collection_rate,
        "recent_billings": recent_billings,
    }

    return render(
        request,
        "admin/admin_dashboard.html",
        context
    )

@login_required
def new_applicants(request):
    applicants = Customer.objects.filter(
        status='pending',
        is_active=False
    )
    return render(request, 'admin/new_applicants.html', {
        'applicants': applicants
    })

@login_required
def customer_list(request):
    customers = Customer.objects.filter(
        status__in=['active', 'inactive']
    ).order_by('fullname')

    return render(request, 'admin/customers.html', {
        'customers': customers
    })

@login_required
def approve_applicant(request, id):
    if request.method == "POST":
        customer = get_object_or_404(Customer, id=id)

        if not customer.account_number:
            year = datetime.now().year

            last_customer = Customer.objects.filter(
                account_number__startswith=f"PWSS-{year}"
            ).order_by("-account_number").first()

            if last_customer:
                last_number = int(last_customer.account_number.split("-")[-1])
                next_number = last_number + 1
            else:
                next_number = 1

            customer.account_number = f"PWSS-{year}-{next_number:04d}"

        customer.status = "active"
        customer.is_active = True

        customer.user.is_active = True
        customer.user.save()

        customer.save()

        messages.success(request, "Applicant activated successfully.")

    return redirect("new_applicants")


@login_required
def decline_applicant(request, id):
    if request.method == "POST":
        customer = get_object_or_404(Customer, id=id)

        customer.status = "decline"
        customer.is_active = False
        customer.save()

        customer.user.is_active = False
        customer.user.save()

        messages.success(request, "Applicant declined.")

    return redirect("new_applicants")

@login_required
def suspend_customer(request, id):
    if request.method == "POST":
        customer = get_object_or_404(Customer, id=id)

        customer.status = "inactive"
        customer.is_active = False
        customer.save()

        customer.user.is_active = False
        customer.user.save()

        messages.success(request, f"{customer.fullname} has been suspended.")

    return redirect("customers")


@login_required
def delete_customer(request, id):
    if request.method == "POST":
        customer = get_object_or_404(Customer, id=id)

        # Delete the Django user.
        # Because Customer has OneToOneField(User, on_delete=models.CASCADE),
        # deleting the user automatically deletes the Customer profile.
        customer.user.delete()

        messages.success(request, "Customer account deleted successfully.")

    return redirect("customers")

@login_required
def reactivate_customer(request, id):
    if request.method == "POST":
        customer = get_object_or_404(Customer, id=id)

        customer.status = "active"
        customer.is_active = True
        customer.save()

        customer.user.is_active = True
        customer.user.save()

        messages.success(request, f"{customer.fullname} has been reactivated.")

    return redirect("customers")

@login_required
def billing(request):
    billings = Billing.objects.select_related("customer").order_by(
        "-billing_month",
        "-created_at"
    )

    return render(request, "admin/billing.html", {
        "billings": billings
    })

@login_required
def create_bill(request):

    if request.method == "POST":

        customer = get_object_or_404(
            Customer,
            id=request.POST.get("customer")
        )

        billing_month = request.POST.get("billing_month")
        due_date = request.POST.get("due_date")

        previous_reading = Decimal(request.POST.get("previous_reading"))
        current_reading = Decimal(request.POST.get("current_reading"))

        # Prevent duplicate bill
        if Billing.objects.filter(
            customer=customer,
            billing_month=billing_month
        ).exists():
            messages.error(
                request,
                "This customer already has a bill for the selected billing month."
            )
            return redirect("create_bill")

        # Validate reading
        if current_reading < previous_reading:
            messages.error(
                request,
                "Current reading cannot be less than the previous reading."
            )
            return redirect("create_bill")

        Billing.objects.create(
            customer=customer,
            billing_month=billing_month,
            previous_reading=previous_reading,
            current_reading=current_reading,
            due_date=due_date,
            rate_per_cubic=Decimal(request.POST.get("rate_per_cubic")),
            status="unpaid",
        )

        messages.success(request, "Water bill created successfully.")

        return redirect("create_bill")

    customers = Customer.objects.filter(
        status="active",
        is_active=True
    ).order_by("fullname")

    customer_data = []

    for customer in customers:

        last_bill = Billing.objects.filter(
            customer=customer
        ).order_by("-billing_month").first()

        previous = last_bill.current_reading if last_bill else Decimal("0.00")

        customer_data.append({
            "customer": customer,
            "previous": previous
        })

    return render(request, "admin/create_bill.html", {
        "customer_data": customer_data
    })

@login_required
def payment(request):
    billings = Billing.objects.select_related("customer").filter(
        status="unpaid"
    ).order_by("customer__fullname", "-billing_month")

    return render(request, "admin/payments.html", {
        "billings": billings
    })

@login_required
def process_payment(request, id):

    bill = get_object_or_404(
        Billing,
        id=id,
        status="unpaid"
    )

    if hasattr(bill, "payment"):
        messages.info(request, "This bill has already been paid.")
        return redirect("payment")

    if request.method == "POST":

        amount_paid = Decimal(request.POST.get("amount_paid"))

        if amount_paid < bill.total_amount:
            messages.error(request, "Insufficient payment.")
            return redirect("process_payment", id=id)

        Payment.objects.create(
            billing=bill,
            amount_paid=amount_paid,
            received_by=request.user,
            remarks=request.POST.get("remarks")
        )

        messages.success(request, "Payment processed successfully.")

        return redirect("payments")

    return render(
        request,
        "admin/process_payment.html",
        {
            "bill": bill
        }
    )


@login_required
def reports(request):

    payments = (
        Payment.objects
        .select_related(
            "billing",
            "billing__customer",
            "received_by"
        )
        .order_by("-payment_date")
    )

    total_collections = payments.aggregate(
        total=Sum("amount_paid")
    )["total"] or Decimal("0.00")

    total_receipts = payments.count()

    total_consumption = Decimal("0.00")

    for payment in payments:
        total_consumption += payment.billing.consumption

    context = {
        "payments": payments,
        "total_collections": total_collections,
        "total_receipts": total_receipts,
        "total_consumption": total_consumption,
    }

    return render(request, "admin/reports.html", context)

@login_required
def official_receipt(request, payment_id):

    payment = get_object_or_404(
        Payment.objects.select_related(
            "billing",
            "billing__customer",
            "received_by"
        ),
        id=payment_id
    )

    return render(
        request,
        "admin/official_receipt.html",
        {
            "payment": payment
        }
    )