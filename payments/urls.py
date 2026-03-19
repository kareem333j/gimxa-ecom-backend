from django.urls import path
from payments.views import PaymentGatewayListView, payment_webhook, init_payment

urlpatterns = [
    path('gateways/', PaymentGatewayListView.as_view(), name='payment-gateway-list'),
    path('init-payment/', init_payment, name='init-payment'),
    path('webhook/', payment_webhook, name='payment-webhook'),
]