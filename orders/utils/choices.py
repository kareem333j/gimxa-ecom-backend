from django.db import models

class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'
    COMPLETED = 'completed', 'Completed'
    PROCESSING = 'processing', 'Processing'
    CANCELLED = 'cancelled', 'Cancelled'