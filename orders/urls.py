from django.urls import path
from orders.views.admin import *
from orders.views.public import *

urlpatterns = [
    # public
    path("all/", OrderListView.as_view(), name="order-list"),
    path("order/<str:order_number>/", OrderDetailView.as_view(), name="order-detail"),
    path("order/<str:order_number>/cancel/", CancelOrderView.as_view(), name="cancel-order"),
    path("buy-now/", BuyNowCheckoutView.as_view(), name="buy-now-checkout"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),

    # admin
    path("admin/all/", AdminOrderListView.as_view(), name="admin-order-list"),
    path("admin/<str:order_number>/", AdminOrderDetailView.as_view(), name="admin-order-detail")
]