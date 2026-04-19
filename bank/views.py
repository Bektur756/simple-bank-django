from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    TransactionFilterSerializer,
    TransactionSerializer,
    TransferSerializer,
    build_token_pair,
)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = build_token_pair(user)

        return Response(
            {
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "email": user.email,
                "account_number": user.account.account_number,
                "balance": user.account.balance,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(build_token_pair(serializer.validated_data["user"]))


class BalanceView(APIView):
    def get(self, request):
        account = request.user.account
        return Response(
            {
                "account_number": account.account_number,
                "balance": account.balance,
            }
        )


class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        filters = TransactionFilterSerializer(
            data={
                "from_date": self.request.query_params.get("from"),
                "to_date": self.request.query_params.get("to"),
            }
        )
        filters.is_valid(raise_exception=True)

        queryset = self.request.user.account.transactions.all()
        if filters.validated_data["from_date"]:
            queryset = queryset.filter(timestamp__gte=filters.validated_data["from_date"])
        if filters.validated_data["to_date"]:
            queryset = queryset.filter(timestamp__lte=filters.validated_data["to_date"])
        return queryset


class TransferView(APIView):
    def post(self, request):
        serializer = TransferSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)
