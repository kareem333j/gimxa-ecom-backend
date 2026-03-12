from django.urls import path

from coupons.views.public import (
    ValidateCouponView,
    ApplyCouponView,
    RemoveCouponView,
    CouponDetailsView,
)
from coupons.views.admin import (
    AdminCouponListCreateView,
    AdminCouponDetailView,
    AdminCouponProductView,
    AdminCouponCategoryView,
    AdminCouponPackageView,
    AdminCouponUsageListView,
)

urlpatterns = [
    # Public endpoints
    path("validate/", ValidateCouponView.as_view(), name="coupon-validate"),
    path("apply/", ApplyCouponView.as_view(), name="coupon-apply"),
    path("remove/", RemoveCouponView.as_view(), name="coupon-remove"),
    path("<str:code>/", CouponDetailsView.as_view(), name="coupon-details"),
    
    # Admin endpoints
    path("admin/all/", AdminCouponListCreateView.as_view(), name="admin-coupon-list"),
    path("admin/coupon/<int:pk>/", AdminCouponDetailView.as_view(), name="admin-coupon-detail"),
    path("admin/coupon/<int:coupon_id>/products/", AdminCouponProductView.as_view(), name="admin-coupon-products"),
    path("admin/coupon/<int:coupon_id>/products/<int:product_id>/", AdminCouponProductView.as_view(), name="admin-coupon-product-delete"),
    path("admin/coupon/<int:coupon_id>/categories/", AdminCouponCategoryView.as_view(), name="admin-coupon-categories"),
    path("admin/coupon/<int:coupon_id>/categories/<int:category_id>/", AdminCouponCategoryView.as_view(), name="admin-coupon-category-delete"),
    path("admin/coupon/<int:coupon_id>/packages/", AdminCouponPackageView.as_view(), name="admin-coupon-packages"),
    path("admin/coupon/<int:coupon_id>/packages/<int:package_id>/", AdminCouponPackageView.as_view(), name="admin-coupon-package-delete"),
    path("admin/coupon/<int:coupon_id>/usages/", AdminCouponUsageListView.as_view(), name="admin-coupon-usages"),
]