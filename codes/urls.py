from django.urls import path
from codes.views import (
    AdminCodeListView,
    AdminCodeDetailView,
    AdminProductCodesView,
    AdminProductCodeDetailView,
)

urlpatterns = [
    # Generic (all codes)
    path("admin/all/", AdminCodeListView.as_view(), name="admin-code-list"),
    path("admin/<int:code_id>/", AdminCodeDetailView.as_view(), name="admin-code-detail"),

    # Product-scoped by slug
    # GET  → list codes (or all packages + codes for topup)
    # PUT  → bulk textarea sync
    path(
        "admin/product/<slug:slug>/",
        AdminProductCodesView.as_view(),
        name="admin-product-codes",
    ),
    # PATCH → update single code value
    # DELETE → delete single code
    path(
        "admin/product/<slug:slug>/<int:code_id>/",
        AdminProductCodeDetailView.as_view(),
        name="admin-product-code-detail",
    ),
]