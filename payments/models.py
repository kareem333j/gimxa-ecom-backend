from django.db import models

class PaymentGateway(models.Model):
    name = models.CharField(max_length=100)
    tax_rate = models.DecimalField(max_digits=15, decimal_places=4, default=0.0000, help_text="Tax rate as a decimal (e.g. 0.05 for 5%)")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    icon = models.ImageField(upload_to="payment_gateways/icons/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Payment(models.Model):
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payments"
    )

    gateway = models.ForeignKey(
        "payments.PaymentGateway",
        on_delete=models.PROTECT
    )

    payment_intent_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=15, decimal_places=4)

    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("success", "Success"),
            ("failed", "Failed"),
            ("refunded", "Refunded"),
        ],
        default="pending"
    )

    raw_response = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)