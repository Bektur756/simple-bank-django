from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from .models import (
    MIN_TRANSFER_FEE,
    TRANSFER_FEE_RATE,
    WELCOME_BONUS,
    BankAccount,
    Transaction,
    User,
)


def quantize_amount(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["amount", "type", "timestamp", "description"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "password"]

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        account = BankAccount.objects.create(
            user=user,
            account_number=BankAccount.generate_account_number(),
            balance=WELCOME_BONUS,
        )
        Transaction.objects.create(
            account=account,
            amount=WELCOME_BONUS,
            type=Transaction.Type.CREDIT,
            description="Welcome bonus",
        )
        Token.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError("Invalid email or password.")

        attrs["user"] = user
        return attrs


class TransferSerializer(serializers.Serializer):
    account_number = serializers.RegexField(regex=r"^\d{10}$")
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))

    def validate(self, attrs):
        sender_account = self.context["request"].user.account

        try:
            receiver_account = BankAccount.objects.get(account_number=attrs["account_number"])
        except BankAccount.DoesNotExist as exc:
            raise serializers.ValidationError({"account_number": "Destination account does not exist."}) from exc

        if receiver_account.pk == sender_account.pk:
            raise serializers.ValidationError({"account_number": "You cannot transfer to your own account."})

        amount = quantize_amount(attrs["amount"])
        fee = quantize_amount(max(MIN_TRANSFER_FEE, amount * TRANSFER_FEE_RATE))
        total = quantize_amount(amount + fee)

        attrs["receiver_account"] = receiver_account
        attrs["amount"] = amount
        attrs["fee"] = fee
        attrs["total"] = total
        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        sender_user = self.context["request"].user
        sender_account = sender_user.account
        receiver_account = self.validated_data["receiver_account"]
        amount = self.validated_data["amount"]
        fee = self.validated_data["fee"]
        total = self.validated_data["total"]

        account_ids = sorted([sender_account.id, receiver_account.id])
        locked_accounts = {
            account.id: account
            for account in BankAccount.objects.select_for_update().filter(id__in=account_ids)
        }
        sender_account = locked_accounts[sender_account.id]
        receiver_account = locked_accounts[receiver_account.id]

        if sender_account.balance < total:
            raise serializers.ValidationError({"amount": "Insufficient funds for transfer and fee."})

        sender_account.balance = quantize_amount(sender_account.balance - total)
        receiver_account.balance = quantize_amount(receiver_account.balance + amount)
        sender_account.save(update_fields=["balance"])
        receiver_account.save(update_fields=["balance"])

        Transaction.objects.create(
            account=sender_account,
            amount=total,
            type=Transaction.Type.DEBIT,
            description=(
                f"Transfer to {receiver_account.account_number}. "
                f"Amount {amount:.2f}, fee {fee:.2f}"
            ),
        )
        Transaction.objects.create(
            account=receiver_account,
            amount=amount,
            type=Transaction.Type.CREDIT,
            description=f"Transfer from {sender_account.account_number}",
        )

        return {
            "sender_account_number": sender_account.account_number,
            "receiver_account_number": receiver_account.account_number,
            "amount": amount,
            "fee": fee,
            "total_debited": total,
            "balance": sender_account.balance,
        }


class TransactionFilterSerializer(serializers.Serializer):
    from_date = serializers.CharField(required=False)
    to_date = serializers.CharField(required=False)

    def validate(self, attrs):
        parsed_from = self._parse_optional_datetime(attrs.get("from_date"), "from")
        parsed_to = self._parse_optional_datetime(attrs.get("to_date"), "to")

        if parsed_from and parsed_to and parsed_from > parsed_to:
            raise serializers.ValidationError("The from date must be before the to date.")

        attrs["from_date"] = parsed_from
        attrs["to_date"] = parsed_to
        return attrs

    def _parse_optional_datetime(self, value, field_name):
        if not value:
            return None

        parsed = parse_datetime(value)
        if parsed is not None:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            return parsed

        parsed_date = parse_date(value)
        if parsed_date is None:
            raise serializers.ValidationError({field_name: "Use ISO 8601 date or datetime format."})

        parsed = datetime.combine(
            parsed_date,
            time.min if field_name == "from" else time.max,
        )
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
