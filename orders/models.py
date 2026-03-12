import uuid
from django.db import models
from django.db.models import Q, CheckConstraint, UniqueConstraint
from django.contrib.auth import get_user_model

from orders.utils.choices import OrderStatus

User = get_user_model()

class Order(models.Model):
    order_number = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='orders'
    )
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    subtotal = models.DecimalField(max_digits=15, decimal_places=4)
    tax = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    total_price = models.DecimalField(max_digits=15, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    coupon_code = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    discount_total = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        default=0
    )

    class Meta:
        indexes = [
            models.Index(fields=["order_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"Order {self.order_number} by {self.user.username} - {self.status}"
    
class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="order_items"
    )
    
    product_name = models.CharField(max_length=255)
    product_slug = models.SlugField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=15, decimal_places=4)
    
    is_topup = models.BooleanField(default=False)

    topup_package = models.ForeignKey(
        "topup.TopUpPackage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["order", "product", "topup_package"],
                name="unique_order_product_package"
            ),
            CheckConstraint(
                condition=(
                    Q(is_topup=True, topup_package__isnull=False) |
                    Q(is_topup=False, topup_package__isnull=True)
                ),
                name="valid_order_topup_logic"
            )
        ]

    def __str__(self):
        return f"{self.product.name} ({self.order.order_number})"