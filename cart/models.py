from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Q, UniqueConstraint, CheckConstraint
from decimal import Decimal

User = get_user_model()
    
class Cart(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="cart"
    )

    coupon = models.ForeignKey(
        "coupons.Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="carts"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart - {self.user.username}"
    
class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="cart_items"
    )

    topup_package = models.ForeignKey(
        "topup.TopUpPackage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cart_items"
    )

    quantity = models.PositiveIntegerField(default=1)
    topup_hash = models.CharField(max_length=32, null=True, blank=True)
    topup_data = models.JSONField(null=True, blank=True)

    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    is_topup = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["cart", "product", "topup_package", "topup_hash"],
                name="unique_cart_product_package_hash"
            ),
            UniqueConstraint(
                fields=["cart", "product"],
                condition=Q(topup_package__isnull=True),
                name="unique_cart_product_no_package"
            ),
            CheckConstraint(
                condition=(
                    Q(is_topup=True, topup_package__isnull=False) |
                    Q(is_topup=False, topup_package__isnull=True)
                ),
                name="valid_topup_logic"
            )
        ]

        
    def save(self, *args, **kwargs):
        self.total_price = Decimal(self.unit_price) * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"