from django.db import models
from accounts.models import User

# Create your models here.
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

    fullname = models.CharField(max_length=200)
    submitter_no = models.CharField(max_length=250, unique=True)
    address = models.CharField(max_length=250)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new"
    )

    def __str__(self):
        return self.submitter_no