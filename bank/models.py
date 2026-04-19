from decimal import Decimal
import secrets

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


WELCOME_BONUS = Decimal("10000.00")
TRANSFER_FEE_RATE = Decimal("0.025")
MIN_TRANSFER_FEE = Decimal("5.00")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email field must be set.")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class BankAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="account")
    account_number = models.CharField(max_length=10, unique=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_number} ({self.user.email})"

    @classmethod
    def generate_account_number(cls):
        while True:
            account_number = f"{secrets.randbelow(10**10):010d}"
            if not cls.objects.filter(account_number=account_number).exists():
                return account_number


class Transaction(models.Model):
    class Type(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"

    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=6, choices=Type.choices)
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-timestamp", "-id"]

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Transaction amount must be positive.")

    def __str__(self):
        return f"{self.type} {self.amount} on {self.account.account_number}"
