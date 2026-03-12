from django.contrib import admin
from coupons.models import Coupon, CouponProduct, CouponCategory, CouponUsage, CouponPackage


class CouponProductInline(admin.TabularInline):
    model = CouponProduct
    extra = 1
    autocomplete_fields = ["product"]


class CouponCategoryInline(admin.TabularInline):
    model = CouponCategory
    extra = 1
    autocomplete_fields = ["category"]


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "scope",
        "discount_type",
        "discount_value",
        "is_active",
        "start_at",
        "end_at",
        "used_count",
        "max_usage",
    )
    list_filter = ("scope", "discount_type", "is_active")
    search_fields = ("code",)
    readonly_fields = ("used_count", "created_at")
    ordering = ("-created_at",)
    
    inlines = [CouponProductInline, CouponCategoryInline]
    
    fieldsets = (
        ("Coupon Info", {
            "fields": ("code", "scope", "is_active")
        }),
        ("Discount", {
            "fields": ("discount_type", "discount_value"),
            "description": "Required only for GLOBAL or ORDER scope coupons"
        }),
        ("Validity Period", {
            "fields": ("start_at", "end_at")
        }),
        ("Usage Limits", {
            "fields": ("max_usage", "used_count")
        }),
        ("Additional Info", {
            "fields": ("created_at",),
            "classes": ("collapse",)
        }),
    )


@admin.register(CouponProduct)
class CouponProductAdmin(admin.ModelAdmin):
    list_display = ("coupon", "product", "discount_type", "discount_value")
    list_filter = ("discount_type", "coupon")
    search_fields = ("coupon__code", "product__name")
    autocomplete_fields = ["coupon", "product"]


@admin.register(CouponCategory)
class CouponCategoryAdmin(admin.ModelAdmin):
    list_display = ("coupon", "category", "discount_type", "discount_value")
    list_filter = ("discount_type", "coupon")
    search_fields = ("coupon__code", "category__name")
    autocomplete_fields = ["coupon", "category"]


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ("coupon", "user", "order", "used_at")
    list_filter = ("coupon", "used_at")
    search_fields = ("coupon__code", "user__username", "order__order_number")
    readonly_fields = ("coupon", "user", "order", "used_at")
    ordering = ("-used_at",)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CouponPackage)
class CouponPackageAdmin(admin.ModelAdmin):
    list_display = ("coupon", "package", "discount_type", "discount_value")
    list_filter = ("discount_type", "coupon")
