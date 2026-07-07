from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('staff', 'Staff'),
        ('customer', 'Customer')
    )

    role = models.CharField(max_length=200, choices=ROLE_CHOICES, default='customer')

    def __str__(self):
        return self.username