from django.db import models

class PaymentGateway(models.Model):
    name = models.CharField(max_length=100)
    gateway_type = models.CharField(
        max_length=50, 
        choices=[("paymob", "Paymob"), ("stripe", "Stripe"), ("paypal", "PayPal")], 
        default="paymob",
        help_text="The underlying provider for this gateway method",
    )
    gateway_code = models.CharField(max_length=50, unique=True, help_text="Unique code to identify this specific method (e.g., 'paymob_wallet', 'paymob_card')", null=True)
    integration_id = models.CharField(max_length=255, blank=True, null=True, help_text="The provider's integration ID for this specific payment method")

    tax_rate = models.DecimalField(max_digits=15, decimal_places=4, default=0.0000, help_text="Tax rate as a decimal (e.g. 0.05 for 5%)")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    icon = models.ImageField(upload_to="payment_gateways/icons/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.gateway_code})"


class Payment(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        INTENDED = "intended", "Intended"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        CANCELLED = "cancelled", "Cancelled"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payments"
    )

    gateway = models.ForeignKey(
        "payments.PaymentGateway",
        on_delete=models.PROTECT
    )

    payment_intent_id = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    client_secret = models.CharField(max_length=500, null=True, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=4)
    currency = models.CharField(max_length=10, default="EGP")
    transaction_id = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    gateway_order_id = models.CharField(max_length=255, null=True, blank=True, db_index=True, help_text="The internal order ID returned by the payment gateway")


    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )

    raw_response = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order} - {self.gateway} - {self.status}"


class ExchangeRateSnapshot(models.Model):
    base = models.CharField(max_length=10, default="USD")
    rates = models.JSONField()
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Rates ({self.base}) - {self.last_updated}"