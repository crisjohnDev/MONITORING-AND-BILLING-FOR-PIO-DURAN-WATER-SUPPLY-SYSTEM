from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from customer.models import Customer, Barangay, CustomerFeedback
from django.contrib import messages
from django.db import IntegrityError
from accounts.models import User
from django.db.models import Q, Sum
from datetime import datetime, date, timedelta
from django.utils import timezone
import re
from .models import Billing, Payment, Notification, MeterReading
from decimal import Decimal
from openpyxl import load_workbook
from collections import defaultdict
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Sum, Count
from django.db.models.functions import Coalesce
import json

@login_required
def admin_dashboard(request):

    # ==========================
    # Dashboard Cards
    # ==========================
    total_connections = Customer.objects.count()

    pending_applicants = Customer.objects.filter(
        status="new"
    ).count()

    current_month = date.today().strftime("%B %Y")

    total_bills = Billing.objects.count()

    paid_bills = Billing.objects.filter(
        status="paid"
    ).count()

    if total_bills > 0:
        collection_rate = round(
            (paid_bills / total_bills) * 100,
            1
        )
    else:
        collection_rate = 0

    # ==========================
    # Recent Billings
    # ==========================
    recent_billings = (
        Billing.objects
        .select_related("customer", "customer__barangay")
        .order_by("-created_at")[:10]
    )

    # ==========================
    # Consumption Per Barangay
    # ==========================
    barangay_consumption = (
        Barangay.objects
        .annotate(
            total_consumption=Sum(
                "customers__billings__consumption"
            )
        )
        .order_by("barangay_name")
    )

    context = {
        "total_connections": total_connections,
        "pending_applicants": pending_applicants,
        "current_month": current_month,
        "collection_rate": collection_rate,
        "recent_billings": recent_billings,
        "barangay_consumption": barangay_consumption,
    }

    return render(
        request,
        "admin/admin_dashboard.html",
        context
    )

@login_required
def customer_list(request):
    customers = Customer.objects.all().order_by(
        'address',
        'firstname',
        'lastname'
    )

    barangays_list = Barangay.objects.order_by(
        'barangay_name'
    )

    return render(
        request,
        "admin/customers.html",
        {
            "customers": customers,
            "barangays_list": barangays_list,
        }
    )

@login_required
def add_customer(request):
    if request.method == "POST":

        # Get selected barangay
        barangay = Barangay.objects.get(id=request.POST.get("barangay"))

        # Create user
        user = User.objects.create_user(
            username=request.POST.get("username"),
            password=request.POST.get("password"),
            role="customer",
        )

        # Create customer
        Customer.objects.create(
            user=user,
            firstname=request.POST.get("firstname"),
            middlename=request.POST.get("middlename"),
            lastname=request.POST.get("lastname"),
            submitter_no=request.POST.get("submitter_no"),
            barangay=barangay,
            address=barangay.barangay_name,   # or request.POST.get("address") if you later add an address field
        )

        messages.success(request, "Customer added successfully.")
        return redirect("customers")

    barangays = Barangay.objects.all()

    return render(request, "admin/add_customer.html", {
        "barangays": barangays
    })

@login_required
def update_customer(request, pk):

    customer = get_object_or_404(Customer, pk=pk)
    barangays = Barangay.objects.all()

    if request.method == "POST":

        # Update User
        customer.user.username = request.POST.get("username")

        password = request.POST.get("password")
        if password:
            customer.user.set_password(password)

        customer.user.save()

        # Update Customer
        customer.firstname = request.POST.get("firstname")
        customer.middlename = request.POST.get("middlename")
        customer.lastname = request.POST.get("lastname")
        customer.submitter_no = request.POST.get("submitter_no")
        customer.barangay_id = request.POST.get("barangay")

        customer.save()

        return redirect("customers")

    return render(request, "admin/add_customer.html", {
        "customer": customer,
        "barangays": barangays,
    })

@login_required
def import_customers(request):

    print("\n========== IMPORT STARTED ==========")

    if request.method != "POST":
        return redirect("customers")

    print("POST Data:", request.POST)
    print("FILES:", request.FILES)

    # ---------------------------------
    # Barangay
    # ---------------------------------
    barangay_id = request.POST.get("barangay_id")

    if not barangay_id:
        messages.error(request, "Please select a barangay.")
        return redirect("customers")

    try:
        barangay = Barangay.objects.get(pk=barangay_id)
    except Barangay.DoesNotExist:
        messages.error(request, "Invalid barangay selected.")
        return redirect("customers")

    # ---------------------------------
    # Excel File
    # ---------------------------------
    excel_file = request.FILES.get("excel_file")

    if not excel_file:
        messages.error(request, "Please upload an Excel file.")
        return redirect("customers")

    try:
        workbook = load_workbook(
            excel_file,
            read_only=True,
            data_only=True
        )
    except Exception as e:
        messages.error(request, f"Invalid Excel file: {e}")
        return redirect("customers")

    sheet = workbook.active

    headers = [
        str(h).strip().lower() if h else ""
        for h in next(sheet.iter_rows(max_row=1, values_only=True))
    ]

    print("Headers:", headers)

    required_headers = [
        "submitter no.",
        "first name",
        "middle name",
        "last name",
        "address",
    ]

    for header in required_headers:
        if header not in headers:
            workbook.close()
            messages.error(request, f"Missing column: {header}")
            return redirect("customers")

    submitter_col = headers.index("submitter no.")
    firstname_col = headers.index("first name")
    middlename_col = headers.index("middle name")
    lastname_col = headers.index("last name")
    address_col = headers.index("address")

    existing_submitters = set(
        Customer.objects.values_list("submitter_no", flat=True)
    )

    existing_usernames = set(
        User.objects.values_list("username", flat=True)
    )

    users = []
    customer_data = []

    skipped = 0

    print("\n========== READING ROWS ==========")

    for index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):

        firstname = str(row[firstname_col] or "").strip()
        middlename = str(row[middlename_col] or "").strip()
        lastname = str(row[lastname_col] or "").strip()
        submitter_no = str(row[submitter_col] or "").strip()
        address = str(row[address_col] or "").strip()

        print(f"Row {index}")
        print("Firstname:", firstname)
        print("Middlename:", middlename)
        print("Lastname:", lastname)
        print("Submitter:", submitter_no)
        print("Address:", address)

        # Skip blank rows
        if not any([firstname, middlename, lastname, submitter_no, address]):
            continue

        # Skip duplicate submitter numbers
        if submitter_no in existing_submitters:
            print("Duplicate submitter:", submitter_no)
            skipped += 1
            continue

        username = submitter_no

        counter = 1
        while username in existing_usernames:
            username = f"{submitter_no}_{counter}"
            counter += 1

        existing_usernames.add(username)
        existing_submitters.add(submitter_no)

        users.append(
            User(
                username=username,
                password=make_password(submitter_no),
                role="customer",
            )
        )

        customer_data.append({
            "username": username,
            "firstname": firstname,
            "middlename": middlename,
            "lastname": lastname,
            "submitter_no": submitter_no,
            "address": address,
        })

    print("\n========== SUMMARY ==========")
    print("Users:", len(users))
    print("Customers:", len(customer_data))
    print("Skipped:", skipped)

    imported = 0

    try:
        with transaction.atomic():

            print("Creating users...")

            User.objects.bulk_create(users, batch_size=500)

            user_map = {
                user.username: user
                for user in User.objects.filter(
                    username__in=[u.username for u in users]
                )
            }

            customers = []

            for item in customer_data:

                customers.append(
                    Customer(
                        user=user_map[item["username"]],
                        firstname=item["firstname"],
                        middlename=item["middlename"],
                        lastname=item["lastname"],
                        submitter_no=item["submitter_no"],
                        address=item["address"],
                        barangay=barangay,
                        status="old",
                    )
                )

            Customer.objects.bulk_create(customers, batch_size=500)

            imported = len(customers)

    except Exception as e:
        import traceback
        traceback.print_exc()

        workbook.close()

        messages.error(request, f"Import failed: {e}")
        return redirect("customers")

    workbook.close()

    messages.success(
        request,
        f"{imported} customer(s) imported successfully. "
        f"{skipped} duplicate(s) skipped."
    )

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
def customer_profile(request, customer_id):

    customer = get_object_or_404(Customer, pk=customer_id)

    billings = Billing.objects.filter(
        customer=customer
    ).order_by("-billing_month")

    payments = Payment.objects.select_related(
        "billing"
    ).filter(
        billing__customer=customer
    ).order_by("-payment_date")

    total_consumption = billings.aggregate(
        total=Sum("consumption")
    )["total"] or Decimal("0.00")

    total_billed = billings.aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0.00")

    total_paid = payments.aggregate(
        total=Sum("amount_paid")
    )["total"] or Decimal("0.00")

    return render(request, "admin/customer_profile.html", {
        "customer": customer,
        "billings": billings,
        "payments": payments,
        "total_consumption": total_consumption,
        "total_billed": total_billed,
        "total_paid": total_paid,
    })

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

    # ==========================================================
    # POST - GENERATE BILLING
    # ==========================================================
    if request.method == "POST":

        try:
            # --------------------------------------------------
            # BILLING MONTH
            # --------------------------------------------------
            billing_month_raw = request.POST.get("billing_month")

            if not billing_month_raw:
                messages.error(
                    request,
                    "Billing month is required."
                )
                return redirect("create_bill")

            billing_month = datetime.strptime(
                billing_month_raw,
                "%Y-%m"
            ).date().replace(day=1)

            # --------------------------------------------------
            # DUE DATE
            # --------------------------------------------------
            due_date_raw = request.POST.get("due_date")

            if not due_date_raw:
                messages.error(
                    request,
                    "Due date is required."
                )
                return redirect("create_bill")

            due_date = datetime.strptime(
                due_date_raw,
                "%Y-%m-%d"
            ).date()

            # --------------------------------------------------
            # RATE PER CUBIC METER
            # --------------------------------------------------
            rate_per_cubic = Decimal(
                request.POST.get("rate_per_cubic") or "25.00"
            )

            if rate_per_cubic < 0:
                messages.error(
                    request,
                    "Rate per cubic meter cannot be negative."
                )
                return redirect("create_bill")

            # --------------------------------------------------
            # CONSUMER DATA
            # --------------------------------------------------
            consumer_data_raw = request.POST.get(
                "consumer_data_json",
                "{}"
            )

            try:
                consumer_data = json.loads(
                    consumer_data_raw
                )
            except json.JSONDecodeError:
                messages.error(
                    request,
                    "Invalid consumer billing data."
                )
                return redirect("create_bill")

            if not consumer_data:
                messages.error(
                    request,
                    "No consumer entries were submitted."
                )
                return redirect("create_bill")

            created = 0
            skipped = 0

            # ==================================================
            # DATABASE TRANSACTION
            # ==================================================
            with transaction.atomic():

                # ==============================================
                # PROCESS EACH CUSTOMER
                # ==============================================
                for customer_id, data in consumer_data.items():

                    # ------------------------------------------
                    # GET CUSTOMER
                    # ------------------------------------------
                    try:
                        customer = Customer.objects.get(
                            pk=customer_id
                        )
                    except Customer.DoesNotExist:
                        skipped += 1
                        continue

                    # ------------------------------------------
                    # DUPLICATE BILLING CHECK
                    # ------------------------------------------
                    if Billing.objects.filter(
                        customer=customer,
                        billing_month=billing_month
                    ).exists():

                        skipped += 1
                        continue

                    # ==========================================
                    # READINGS
                    # ==========================================

                    previous_reading = Decimal(
                        str(
                            data.get(
                                "previous_reading",
                                "0.00"
                            )
                        )
                    )

                    current_reading = Decimal(
                        str(
                            data.get(
                                "current_reading",
                                "0.00"
                            )
                        )
                    )

                    # ------------------------------------------
                    # VALIDATE READING
                    # ------------------------------------------
                    if current_reading < previous_reading:
                        skipped += 1
                        continue

                    # ==========================================
                    # ADDITIONAL FEES
                    # ==========================================

                    connection_fee = Decimal(
                        str(
                            data.get(
                                "connection_fee",
                                "0.00"
                            )
                        )
                    )

                    reconnection_fee = Decimal(
                        str(
                            data.get(
                                "reconnection_fee",
                                "0.00"
                            )
                        )
                    )

                    violation_fee = Decimal(
                        str(
                            data.get(
                                "violation_fee",
                                "0.00"
                            )
                        )
                    )

                    penalty_fee = Decimal(
                        str(
                            data.get(
                                "penalty_fee",
                                "0.00"
                            )
                        )
                    )

                    # ==========================================
                    # SAVE METER READING
                    # ==========================================

                    MeterReading.objects.update_or_create(
                        customer=customer,
                        billing_month=billing_month,
                        defaults={
                            "previous_reading": previous_reading,
                            "current_reading": current_reading,
                        }
                    )

                    # ==========================================
                    # CREATE BILLING
                    # ==========================================

                    Billing.objects.create(
                        customer=customer,
                        billing_month=billing_month,

                        previous_reading=previous_reading,
                        current_reading=current_reading,

                        rate_per_cubic=rate_per_cubic,

                        connection_fee=connection_fee,
                        reconnection_fee=reconnection_fee,
                        violation_fee=violation_fee,
                        penalty_fee=penalty_fee,

                        due_date=due_date,
                        status="unpaid",
                    )

                    # ==========================================
                    # UPDATE CUSTOMER STATUS
                    # ==========================================

                    if customer.status == "new":

                        customer.status = "old"

                        customer.save(
                            update_fields=["status"]
                        )

                    created += 1

            # ==================================================
            # SUCCESS MESSAGE
            # ==================================================

            messages.success(
                request,
                f"{created} bill(s) generated successfully. "
                f"{skipped} skipped."
            )

            return redirect("create_bill")

        except ValueError:

            messages.error(
                request,
                "Invalid date or numeric value."
            )

            return redirect("create_bill")

        except Exception as e:

            messages.error(
                request,
                f"Unable to generate bills: {str(e)}"
            )

            return redirect("create_bill")

    # ==========================================================
    # GET - LOAD BILLING PAGE
    # ==========================================================

    current_month = date.today().replace(day=1)

    customer_data = []

    # ----------------------------------------------------------
    # LOAD CUSTOMERS
    # ----------------------------------------------------------

    customers = (
        Customer.objects
        .select_related("barangay")
        .order_by(
            "lastname",
            "firstname"
        )
    )

    # ==========================================================
    # BUILD CUSTOMER DATA
    # ==========================================================

    for customer in customers:

        # ------------------------------------------------------
        # GET MOST RECENT METER READING
        # ------------------------------------------------------

        last_reading = (
            MeterReading.objects
            .filter(customer=customer)
            .order_by("-billing_month")
            .first()
        )

        if last_reading:

            previous_reading = (
                last_reading.current_reading
            )

        else:

            previous_reading = Decimal("0.00")

        # ------------------------------------------------------
        # GET CURRENT MONTH READING
        # ------------------------------------------------------

        current_reading = (
            MeterReading.objects
            .filter(
                customer=customer,
                billing_month=current_month
            )
            .values_list(
                "current_reading",
                flat=True
            )
            .first()
        )

        # ------------------------------------------------------
        # BARANGAY
        # ------------------------------------------------------

        if customer.barangay:

            barangay_name = str(
                customer.barangay
            )

        else:

            barangay_name = ""

        # ------------------------------------------------------
        # STORE CUSTOMER
        # ------------------------------------------------------

        customer_data.append({

            "id": customer.id,

            "firstname": customer.firstname,

            "lastname": customer.lastname,

            "middlename": customer.middlename,

            "submitter_no": customer.submitter_no,

            "status": customer.status,

            "barangay": barangay_name,

            "previous_reading": previous_reading,

            "current_reading": (
                current_reading
                if current_reading is not None
                else ""
            ),
        })

    # ==========================================================
    # BARANGAY LIST
    # ==========================================================

    barangays = []

    for customer in customers:

        if customer.barangay:

            barangay_name = str(
                customer.barangay
            )

            if barangay_name not in barangays:

                barangays.append(
                    barangay_name
                )

    barangays.sort()

    # ==========================================================
    # RENDER PAGE
    # ==========================================================

    return render(
        request,
        "admin/create_bill.html",
        {
            "customer_data": customer_data,
            "barangays": barangays,
        }
    )

@login_required
def payment(request):

    today = timezone.localdate()

    # ==========================================================
    # GET ALL UNPAID BILLINGS
    # ==========================================================

    billings = (
        Billing.objects
        .select_related("customer")
        .filter(status="unpaid")
        .order_by(
            "customer__firstname",
            "-billing_month"
        )
    )

    # ==========================================================
    # APPLY OVERDUE PENALTY
    # ==========================================================

    for bill in billings:

        # Check if overdue
        if (
            bill.due_date < today
            and (bill.penalty_fee or Decimal("0.00"))
            == Decimal("0.00")
        ):

            # 10% penalty based on rate per cubic meter
            bill.penalty_fee = (
                bill.rate_per_cubic
                * Decimal("0.10")
            )

            # save() automatically recalculates total_amount
            bill.save()

    # ==========================================================
    # GET AVAILABLE BILLING MONTHS
    # ==========================================================

    billing_months = (
        Billing.objects
        .filter(status="unpaid")
        .values_list(
            "billing_month",
            flat=True
        )
        .distinct()
        .order_by("-billing_month")
    )

    # ==========================================================
    # RENDER
    # ==========================================================

    return render(
        request,
        "admin/payments.html",
        {
            "billings": billings,
            "billing_months": billing_months,
        }
    )

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

    # ======================================
    # Payments
    # ======================================
    payments = (
        Payment.objects
        .select_related(
            "billing",
            "billing__customer",
            "billing__customer__barangay",
            "received_by",
        )
        .order_by("-payment_date")
    )

    # ======================================
    # Dashboard Summary
    # ======================================
    total_collections = (
        payments.aggregate(
            total=Sum("amount_paid")
        )["total"]
        or Decimal("0.00")
    )

    total_receipts = payments.count()

    total_consumption = (
        Billing.objects.aggregate(
            total=Sum("consumption")
        )["total"]
        or Decimal("0.00")
    )

    # ======================================
    # Water Consumption per Barangay
    # ======================================
    barangay_data = (
        Billing.objects
        .values(
            "customer__barangay__barangay_name"
        )
        .annotate(
            total_consumption=Sum("consumption")
        )
        .order_by(
            "customer__barangay__barangay_name"
        )
    )

    barangay_labels = [
        row["customer__barangay__barangay_name"]
        for row in barangay_data
    ]

    barangay_values = [
        float(row["total_consumption"] or 0)
        for row in barangay_data
    ]

    # ======================================
    # Paid vs Unpaid Bills
    # ======================================
    paid = Billing.objects.filter(
        status="paid"
    ).count()

    unpaid = Billing.objects.filter(
        status="unpaid"
    ).count()

    # ======================================
    # Context
    # ======================================
    context = {
        "payments": payments,
        "total_collections": total_collections,
        "total_receipts": total_receipts,
        "total_consumption": total_consumption,
        "barangay_labels": json.dumps(barangay_labels),
        "barangay_values": json.dumps(barangay_values),
        "paid": paid,
        "unpaid": unpaid,
    }

    return render(
        request,
        "admin/reports.html",
        context,
    )

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

@login_required
def post_notification(request):

    customers = Customer.objects.order_by("firstname")
    notifications = Notification.objects.select_related("customer").order_by("-created_at")

    # Get unique barangays from customer addresses
    barangays = sorted({
        customer.address.split(",")[1].strip()
        for customer in customers
        if len(customer.address.split(",")) >= 2
    })

    if request.method == "POST":

        target = request.POST.get("target")
        customer_id = request.POST.get("customer")
        barangay = request.POST.get("barangay")
        status = request.POST.get("status")
        title = request.POST.get("title")
        message = request.POST.get("message")

        customer = None

        if target == "customer":
            if not customer_id:
                messages.error(request, "Please select a customer.")
                return redirect("post-notifacation")

            customer = Customer.objects.get(id=customer_id)

        elif target == "barangay":
            if not barangay:
                messages.error(request, "Please select a barangay.")
                return redirect("post-notifacation")

        Notification.objects.create(
            target=target,
            customer=customer,
            barangay=barangay if target == "barangay" else None,
            status=status,
            title=title,
            message=message,
        )

        messages.success(request, "Notification posted successfully.")
        return redirect("post-notifacation")

    return render(request, "admin/post_notification.html", {
        "customers": customers,
        "barangays": barangays,
        "notifications": notifications,
    })

@login_required
def delete_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    notification.delete()

    messages.success(request, "Notification deleted successfully.")
    return redirect("post-notifacation")

@login_required
def paid_report(request):

    billing_coverage = request.GET.get("billing_coverage")

    billings = (
        Billing.objects
        .filter(status="paid")
        .select_related("customer", "payment")
        .order_by(
            "-billing_month",
            "customer__lastname",
            "customer__firstname"
        )
    )

    # Filter by billing month if selected
    if billing_coverage:
        try:
            billing_date = datetime.strptime(
                billing_coverage,
                "%Y-%m"
            ).date().replace(day=1)

            billings = billings.filter(
                billing_month=billing_date
            )
        except ValueError:
            pass

    return render(
        request,
        "admin/paid_report.html",
        {
            "billings": billings,
            "billing_coverage": billing_coverage,
        }
    )

@login_required
def unpaid_report(request):

    billing_coverage = request.GET.get("billing_coverage")

    billings = (
        Billing.objects
        .filter(status="unpaid")
        .select_related("customer")
        .order_by(
            "-billing_month",
            "customer__lastname",
            "customer__firstname"
        )
    )

    if billing_coverage:
        try:
            billing_date = datetime.strptime(
                billing_coverage,
                "%Y-%m"
            ).date().replace(day=1)

            billings = billings.filter(
                billing_month=billing_date
            )
        except ValueError:
            pass

    return render(
        request,
        "admin/unpaid_report.html",
        {
            "billings": billings,
            "billing_coverage": billing_coverage,
        }
    )

@login_required
def barangay_list(request):
    barangays_list = Barangay.objects.all()
    return render(request, "admin/barangays.html", {"barangays_list":barangays_list})

@login_required
def add_brgy(request):
    if request.method == "POST":
        try:
            Barangay.objects.create(
                barangay_name=request.POST.get("barangay_name"),
                municipality=request.POST.get("municipality"),
                province=request.POST.get("province"),
            )

            messages.success(request, "Barangay added successfully.")
            return redirect("brgy_list")

        except IntegrityError as e:
            if "barangay_name" in str(e):
                messages.error(request, "Barangay already exists.")
            else:
                messages.error(request, "Unable to save the record.")

            return render(request, "components/brgy_form.html", {
                "brgy": request.POST
            })

    return render(request, "components/brgy_form.html")

@login_required
def edit_brgy(request, pk):
    brgy = get_object_or_404(Barangay, pk=pk)

    if request.method == "POST":
        brgy.barangay_name=request.POST.get('barangay_name')
        brgy.save()

        return redirect('brgy_list')
    return render(request, "components/brgy_form.html", {"brgy":brgy})

@login_required
def disconnect_customer(request, pk):

    if request.method == "POST":

        customer = get_object_or_404(
            Customer,
            pk=pk
        )

        customer.is_active = False
        customer.save(update_fields=["is_active"])

        # Optional: Disable login also
        customer.user.is_active = False
        customer.user.save(update_fields=["is_active"])

        messages.success(
            request,
            "Customer has been disconnected successfully."
        )

    return redirect("customers")

@login_required
def reconnect_customer(request, pk):

    customer = get_object_or_404(Customer, pk=pk)

    if request.method == "POST":
        customer.is_active = True
        customer.save(update_fields=["is_active"])

        customer.user.is_active = True
        customer.user.save(update_fields=["is_active"])

        messages.success(request, "Customer reconnected successfully.")

    return redirect("customers")

@login_required
def disconnected_list(request):

    disconnected_consumers = (
        Customer.objects
        .select_related("barangay")
        .filter(is_active=False)
        .order_by(
            "lastname",
            "firstname"
        )
    )

    return render(
        request,
        "admin/disconnected.html",
        {
            "disconnected_consumers": disconnected_consumers
        }
    )

@login_required
def feedback_list(request):

    feedbacks = (
        CustomerFeedback.objects
        .select_related(
            "customer",
            "customer__barangay"
        )
        .order_by("-created_at")
    )

    return render(
        request,
        "admin/feedbacks.html",
        {
            "feedbacks": feedbacks,
        }
    )