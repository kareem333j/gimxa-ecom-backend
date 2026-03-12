from django.db import models
from django.contrib.auth import get_user_model
import uuid
User = get_user_model()

class Notification(models.Model):
    class NotificationManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_active=True, is_deleted=False)

    objects = models.Manager()
    public_manager = NotificationManager()
    
    class EmailTypeChoices(models.TextChoices):
        NONE = "none", "None"
        PAYMENT_SUCCESS = "payment_success", "Payment Success"
        PAYMENT_FAILED = "payment_failed", "Payment Failed"
        ORDER_SUCCESS = "order_success", "Order Success"
        ORDER_FAILED = "order_failed", "Order Failed"
        ORDER_SHIPPED = "order_shipped", "Order Shipped"
        ORDER_DELIVERED = "order_delivered", "Order Delivered"
        ORDER_RETURNED = "order_returned", "Order Returned"
        ORDER_REFUNDED = "order_refunded", "Order Refunded"
        ORDER_CANCELLED = "order_cancelled", "Order Cancelled"
        CODE_SENT = "code_sent", "Code Sent"
        REDEEM_LINK = "redeem_link", "Redeem Link"
        CREDITS_DELIVERED = "credits_delivered", "Credits Delivered"
        DEFAULT = "default", "Default"
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    subject = models.CharField(max_length=200)
    message = models.TextField()
    email_type = models.CharField(max_length=20, choices=EmailTypeChoices.choices)

    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    is_emailed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    readed_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["is_read"]),
            models.Index(fields=["is_deleted"]),
            models.Index(fields=["is_emailed"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.user.username} (notification) - {self.subject}"
