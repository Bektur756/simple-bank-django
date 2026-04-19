from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import BankAccount, Transaction, User


class SimpleBankAPITests(APITestCase):
    def register_user(self, email, password="strong-pass-123"):
        response = self.client.post(
            reverse("register"),
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_registration_creates_account_and_welcome_bonus(self):
        response = self.register_user("alice@example.com")

        user = User.objects.get(email="alice@example.com")
        account = user.account
        transaction = account.transactions.get()

        self.assertEqual(len(account.account_number), 10)
        self.assertEqual(account.balance, Decimal("10000.00"))
        self.assertEqual(transaction.type, Transaction.Type.CREDIT)
        self.assertEqual(transaction.amount, Decimal("10000.00"))
        self.assertEqual(response.data["account_number"], account.account_number)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_returns_jwt_pair(self):
        self.register_user("alice@example.com")

        response = self.client.post(
            reverse("login"),
            {"email": "alice@example.com", "password": "strong-pass-123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_balance_and_transaction_history_require_authentication(self):
        self.register_user("alice@example.com")

        balance_response = self.client.get(reverse("balance"))
        history_response = self.client.get(reverse("transactions"))

        self.assertEqual(balance_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(history_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_transfer_applies_percentage_fee_and_records_transactions(self):
        sender_response = self.register_user("alice@example.com")
        receiver_response = self.register_user("bob@example.com")
        self.authenticate(sender_response.data["access"])

        response = self.client.post(
            reverse("transfers"),
            {
                "account_number": receiver_response.data["account_number"],
                "amount": "100.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["fee"], Decimal("5.00"))
        self.assertEqual(response.data["total_debited"], Decimal("105.00"))
        self.assertEqual(response.data["balance"], Decimal("9895.00"))

        sender_account = BankAccount.objects.get(account_number=sender_response.data["account_number"])
        receiver_account = BankAccount.objects.get(account_number=receiver_response.data["account_number"])

        self.assertEqual(sender_account.balance, Decimal("9895.00"))
        self.assertEqual(receiver_account.balance, Decimal("10100.00"))

        sender_latest = sender_account.transactions.order_by("-timestamp", "-id").first()
        receiver_latest = receiver_account.transactions.order_by("-timestamp", "-id").first()
        self.assertEqual(sender_latest.type, Transaction.Type.DEBIT)
        self.assertEqual(sender_latest.amount, Decimal("105.00"))
        self.assertEqual(receiver_latest.type, Transaction.Type.CREDIT)
        self.assertEqual(receiver_latest.amount, Decimal("100.00"))

    def test_transfer_uses_percentage_fee_when_higher_than_minimum(self):
        sender_response = self.register_user("alice@example.com")
        receiver_response = self.register_user("bob@example.com")
        self.authenticate(sender_response.data["access"])

        response = self.client.post(
            reverse("transfers"),
            {
                "account_number": receiver_response.data["account_number"],
                "amount": "1000.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["fee"], Decimal("25.00"))
        self.assertEqual(response.data["total_debited"], Decimal("1025.00"))

    def test_transfer_rejects_insufficient_funds(self):
        sender_response = self.register_user("alice@example.com")
        receiver_response = self.register_user("bob@example.com")
        self.authenticate(sender_response.data["access"])

        response = self.client.post(
            reverse("transfers"),
            {
                "account_number": receiver_response.data["account_number"],
                "amount": "10000.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data)

    def test_transactions_can_be_filtered_by_date_range(self):
        register_response = self.register_user("alice@example.com")
        self.authenticate(register_response.data["access"])
        account = BankAccount.objects.get(account_number=register_response.data["account_number"])
        welcome_transaction = account.transactions.get(description="Welcome bonus")
        welcome_transaction.timestamp = timezone.now() - timedelta(days=5)
        welcome_transaction.save(update_fields=["timestamp"])

        Transaction.objects.create(
            account=account,
            amount=Decimal("50.00"),
            type=Transaction.Type.CREDIT,
            description="Manual adjustment",
        )

        query = urlencode(
            {
                "from": (timezone.now() - timedelta(days=1)).isoformat(),
                "to": (timezone.now() + timedelta(days=1)).isoformat(),
            }
        )
        response = self.client.get(f"{reverse('transactions')}?{query}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["description"], "Manual adjustment")
