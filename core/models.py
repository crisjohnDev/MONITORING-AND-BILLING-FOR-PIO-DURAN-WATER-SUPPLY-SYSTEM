from django.db import models

# Create your models here.
from customer.models import Customer
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


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
        decimal_places=2
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
        self.total_amount = self.consumption * self.rate_per_cubic
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer.account_number} - {self.billing_month}"
    
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