from django.urls import path
from payments.views import (
    PaymentGatewayListView, payment_webhook, init_payment, 
    UserPaymentListView, OrderPaymentListView,
    AdminPaymentListView, AdminPaymentStatusUpdateView,
    AdminPaymentDetailView, AdminPaymentGatewayListView
)

urlpatterns = [
    path('gateways/', PaymentGatewayListView.as_view(), name='payment-gateway-list'),
    path('admin/gateways/', AdminPaymentGatewayListView.as_view(), name='admin-payment-gateway-list'),

    # Unified init endpoint — works for both Paymob and Stripe
    path('init-payment/', init_payment, name='init-payment'),

    # List payments for a specific user or order
    path('user/<str:user_id>/', UserPaymentListView.as_view(), name='user-payment-list'),
    path('order/<str:order_number>/', OrderPaymentListView.as_view(), name='order-payment-list'),

    # Admin endpoints
    path('admin/list/', AdminPaymentListView.as_view(), name='admin-payment-list'),
    path('admin/detail/<int:payment_id>/', AdminPaymentDetailView.as_view(), name='admin-payment-detail'),
    path('admin/update-status/<int:payment_id>/', AdminPaymentStatusUpdateView.as_view(), name='admin-payment-status-update'),

    # Webhook — differentiate via ?gateway=paymob or ?gateway=stripe
    path('webhook/', payment_webhook, name='payment-webhook'),
]