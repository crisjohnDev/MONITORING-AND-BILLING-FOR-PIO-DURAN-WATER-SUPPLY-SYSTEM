from django.db import models

# Create your models here.
from customer.models import Customer
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()

def default_expiry():
    return timezone.now() + timedelta(hours=24)


class Billing(models.Model):
    STATUS_CHOICES = (
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="billings"
    )

    billing_month = models.DateField()

    previous_reading = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    current_reading = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    consumption = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False
    )

    rate_per_cubic = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("25.00")
    )

    # Optional additional fees
    connection_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
        null=True
    )

    reconnection_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
        null=True
    )

    violation_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
        null=True
    )

    penalty_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
        null=True
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False
    )

    due_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="unpaid"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.consumption = self.current_reading - self.previous_reading

        connection = self.connection_fee or Decimal("0.00")
        reconnection = self.reconnection_fee or Decimal("0.00")
        violation = self.violation_fee or Decimal("0.00")
        penalty = self.penalty_fee or Decimal("0.00")

        self.total_amount = (
            (self.consumption * self.rate_per_cubic)
            + connection
            + reconnection
            + violation
            + penalty
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer.submitter_no} - {self.billing_month}"
    
class Payment(models.Model):

    billing = models.OneToOneField(
        Billing,
        on_delete=models.CASCADE,
        related_name="payment"
    )

    receipt_number = models.CharField(
        max_length=30,
        unique=True,
        blank=True
    )

    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    payment_date = models.DateTimeField(
        default=timezone.now
    )

    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    remarks = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        # Generate Official Receipt Number
        if not self.receipt_number:

            year = timezone.now().year

            last = Payment.objects.filter(
                receipt_number__startswith=f"OR-{year}"
            ).order_by("-receipt_number").first()

            if last:
                number = int(last.receipt_number.split("-")[-1]) + 1
            else:
                number = 1

            self.receipt_number = f"OR-{year}-{number:05d}"

        super().save(*args, **kwargs)

        # Update billing status
        if self.billing.status != "paid":
            self.billing.status = "paid"
            self.billing.save()

    def __str__(self):
        return self.receipt_number


class Notification(models.Model):

    TARGET_CHOICES = (
        ("customer", "Single Customer"),
        ("barangay", "Barangay"),
        ("all", "All Customers"),
    )

    STATUS_CHOICES = (
        ("general", "General"),
        ("billing", "Billing"),
        ("payment_reminder", "Payment Reminder"),
        ("disconnection", "Disconnection"),
        ("reconnection", "Reconnection"),
        ("maintenance", "Maintenance"),
        ("clearing_operation", "Clearing Operation"),
    )

    target = models.CharField(
        max_length=20,
        choices=TARGET_CHOICES,
        default="customer"
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )

    barangay = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="general"
    )

    title = models.CharField(max_length=200)
    message = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expiry)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title