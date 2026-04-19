from django.urls import path

from .views import BalanceView, LoginView, RegisterView, TransactionListView, TransferView


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("account/balance/", BalanceView.as_view(), name="balance"),
    path("transactions/", TransactionListView.as_view(), name="transactions"),
    path("transfers/", TransferView.as_view(), name="transfers"),
]
