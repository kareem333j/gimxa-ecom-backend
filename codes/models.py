from django.db import models
from django.contrib.auth import get_user_model
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, CheckConstraint

User = get_user_model()

class FulfillmentCode(models.Model):
    code = models.CharField(max_length=500)

    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    # owner (Product OR TopUpPackage)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField()
    owner = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["is_used"]),
        ]
        constraints = [
            CheckConstraint(
                condition=(
                    Q(is_used=True, used_at__isnull=False) |
                    Q(is_used=False)
                ),
                name="valid_used_state"
            )
        ]

    def __str__(self):
        return f"{self.code} | {'USED' if self.is_used else 'FREE'}"

# class ProductCode(models.Model):
#     product = models.ForeignKey(
#         Product,
#         on_delete=models.CASCADE,
#         related_name="codes"
#     )
    
#     topup_package = models.ForeignKey(
#         "topup.TopUpPackage",
#         on_delete=models.CASCADE,
#         null=True,
#         blank=True,
#         related_name="codes"
#     )

#     order_item = models.ForeignKey(
#         "orders.OrderItem",
#         null=True,
#         blank=True,
#         on_delete=models.SET_NULL,
#         related_name="item_codes"
#     )
    
#     used_by = models.ForeignKey(
#         User,
#         null=True,
#         blank=True,
#         on_delete=models.SET_NULL,
#         related_name="used_codes"
#     )
    
#     code = models.CharField(max_length=500, unique=True)

#     is_used = models.BooleanField(default=False)


#     used_at = models.DateTimeField(null=True, blank=True)


#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         indexes = [
#             models.Index(fields=["product"]),
#             models.Index(fields=["is_used"]),
#             models.Index(fields=["code"]),
#             models.Index(fields=["used_by"]),
#             models.Index(fields=["topup_package"]),
#             models.Index(fields=["order"]),
#         ]

#     def __str__(self):
#         return f"{self.product.name} {(self.topup_package.name + ' package') if self.topup_package else ''} | {'USED' if self.is_used else 'FREE'}"