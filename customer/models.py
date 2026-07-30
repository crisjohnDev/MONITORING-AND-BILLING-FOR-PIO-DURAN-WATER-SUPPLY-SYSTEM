from django.db import models
from accounts.models import User

# Create your models here.

class Barangay(models.Model):
    barangay_name = models.CharField(max_length=100, unique=True)
    municipality = models.CharField(max_length=100)
    province = models.CharField(max_length=100)

    class Meta:
        ordering = ["barangay_name"]
        verbose_name_plural = "Barangays"

    def __str__(self):
        return f"{self.barangay_name}, {self.municipality}"

class Customer(models.Model):

    STATUS_CHOICES = (
        ("new", "New Applicant"),
        ("old", "Old Customer"),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="customer_profile"
    )

    firstname = models.CharField(max_length=200)
    lastname = models.CharField(max_length=200)
    middlename = models.CharField(max_length=200)

    submitter_no = models.CharField(
        max_length=250,
        unique=True,
        blank=True,
        null=True
    )

    address = models.CharField(max_length=250)

    barangay = models.ForeignKey(
        Barangay,
        on_delete=models.PROTECT,
        related_name="customers"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new"
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.submitter_no


class CustomerFeedback(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("reviewed", "Reviewed"),
        ("resolved", "Resolved"),
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="feedbacks"
    )

    subject = models.CharField(
        max_length=200
    )

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    admin_reply = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    resolved_at = models.DateTimeField(
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Customer Feedback"
        verbose_name_plural = "Customer Feedbacks"

    def __str__(self):
        return f"{self.customer.submitter_no} - {self.subject}"