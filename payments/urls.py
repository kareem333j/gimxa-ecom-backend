from django.urls import path
from payments.views import PaymentGatewayListView, payment_webhook

urlpatterns = [
    path('gateways/', PaymentGatewayListView.as_view(), name='payment-gateway-list'),
    path('webhook/', payment_webhook, name='payment-webhook'),
]