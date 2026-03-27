from django.urls import path
from topup.views.public import *
from topup.views.admin import *

urlpatterns = [
    # public
    path("public/topups/", TopUpGameListView.as_view(), name="topup-game-list"),
    path("public/topups/<slug:product_slug>/", TopUpGameDetailView.as_view(), name="topup-game-detail"),
    path("public/topups/<slug:product_slug>/packages/", TopUpPackageListView.as_view(), name="topup-game-packages"),
    path("public/validate/", TopUpValidateView.as_view(), name="topup-validate"),

    # admin
    path("admin/topups/", TopUpGameListAdminView.as_view(), name="admin-topup-game-list"),
    path("admin/topups/<slug:product_slug>/", TopUpGameDetailAdminView.as_view(), name="admin-topup-game-detail"),
    path("admin/fields/", TopUpFieldAdminListView.as_view(), name="admin-topup-field-list"),
    path("admin/fields/<int:pk>/", TopUpFieldAdminDetailView.as_view(), name="admin-topup-field-detail"),
    path("admin/fields/helps/", TopUpFieldHelpAdminView.as_view(), name="admin-topup-field-help-list"),
    path("admin/fields/helps/<int:pk>/", TopUpFieldHelpAdminDetailView.as_view(), name="admin-topup-field-help-detail"),
    path("admin/packages/", TopUpPackageAdminView.as_view(), name="admin-topup-package-list"),
    path("admin/packages/<int:pk>/", TopUpPackageDetailAdminView.as_view(), name="admin-topup-package-detail"),
    path("admin/topups/<slug:product_slug>/packages/", TopUpPackageListAdminView.as_view(), name="admin-topup-game-packages"),
]