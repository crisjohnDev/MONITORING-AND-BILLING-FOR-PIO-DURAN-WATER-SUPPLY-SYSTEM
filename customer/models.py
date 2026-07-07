from django.db import models
from accounts.models import User

# Create your models here.
class Customer(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('decline', "Decline")
    )
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="customer_profile"
    )
    fullname = models.CharField(max_length=200)
    email = models.EmailField(max_length=200)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    image = models.ImageField(upload_to='customer_images/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=False)
    account_number = models.CharField(max_length=20, unique=True, blank=True, null=True)

    def __str__(self):
        return self.account_number