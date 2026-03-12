from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()

class Review(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reviews"
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="reviews"
    )

    rating = models.PositiveSmallIntegerField(
        choices=[(i, i) for i in range(1, 6)]
    )

    comment = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["rating"]),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.rating}/5"
