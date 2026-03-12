from django.urls import path
from dashboard.views import ProductCreateAdminView, ProductFullUpdateAdminView

urlpatterns = [
    # Unified atomic product creation (all sections in one request)
    path(
        "admin/products/create/",
        ProductCreateAdminView.as_view(),
        name="dashboard-product-create",
    ),
    # Unified atomic product full-update
    path(
        "admin/products/<slug:slug>/full-update/",
        ProductFullUpdateAdminView.as_view(),
        name="dashboard-product-full-update",
    ),
]