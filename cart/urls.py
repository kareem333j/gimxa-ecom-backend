from django.urls import path

from cart.views import CartItemCreateView, CartDetailView, CartItemUpdateView, CartItemDeleteView

urlpatterns = [
    path("", CartDetailView.as_view(), name="cart-detail"),
    path("items/", CartItemCreateView.as_view(), name="cart-item-create"), 
    path("items/update/", CartItemUpdateView.as_view(), name="cart-item-update"),
    path("items/delete/", CartItemDeleteView.as_view(), name="cart-item-delete"),
]