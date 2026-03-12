from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from coupons.utils.choices import CouponScope, DiscountType

User = get_user_model()

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)

    scope = models.CharField(
        max_length=20,
        choices=CouponScope.choices,
    )

    discount_type = models.CharField(
        max_length=10,
        choices=DiscountType.choices,
        null=True,
        blank=True,
    )

    discount_value = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    start_at = models.DateTimeField()
    end_at = models.DateTimeField()

    max_usage = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    used_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["scope"]),
            models.Index(fields=["start_at", "end_at"]),
        ]

    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_at > now or self.end_at < now:
            return False
        if self.max_usage and self.used_count >= self.max_usage:
            return False
        return True

    def get_scope_display(self):
        return CouponScope(self.scope).label

    def __str__(self):
        return f"{self.code} ({self.scope})"


class CouponProduct(models.Model):
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="product_discounts"
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="coupon_products"
    )

    discount_type = models.CharField(
        max_length=10,
        choices=DiscountType.choices
    )

    discount_value = models.DecimalField(max_digits=15, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "product"],
                name="unique_coupon_product"
            )
        ]

    def __str__(self):
        return f"{self.coupon.code} -> {self.product.name}"


class CouponCategory(models.Model):
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="category_discounts"
    )

    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.CASCADE,
        related_name="coupon_categories"
    )

    discount_type = models.CharField(
        max_length=10,
        choices=DiscountType.choices
    )

    discount_value = models.DecimalField(max_digits=15, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "category"],
                name="unique_coupon_category"
            )
        ]

    def __str__(self):
        return f"{self.coupon.code} -> {self.category.name}"

class CouponPackage(models.Model):
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="package_discounts"
    )

    package = models.ForeignKey(
        "topup.TopUpPackage",
        on_delete=models.CASCADE,
        related_name="coupon_packages"
    )

    discount_type = models.CharField(
        max_length=10,
        choices=DiscountType.choices
    )

    discount_value = models.DecimalField(max_digits=15, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "package"],
                name="unique_coupon_package"
            )
        ]

    def __str__(self):
        return f"{self.coupon.code} -> {self.package.name}"

class CouponUsage(models.Model):
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="usages"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupon_usages"
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="coupon_usages"
    )

    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["coupon"]),
            models.Index(fields=["user"]),
            models.Index(fields=["order"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "order"],
                name="unique_coupon_per_order"
            )
        ]

    def __str__(self):
        return f"{self.coupon.code} used in order {self.order.id}"