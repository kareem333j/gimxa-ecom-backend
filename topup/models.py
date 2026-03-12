from django.db import models
from catalog.utils.choices import StockMode
from topup.utils.choices import FieldTypes
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation

User = get_user_model()


class TopUpGame(models.Model):
    class PublicManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_active=True)

    objects = models.Manager()
    public = PublicManager()
    
    product = models.OneToOneField(
        "catalog.Product", on_delete=models.CASCADE, related_name="topup"
    )

    is_active = models.BooleanField(default=True)
    logo = models.ImageField(upload_to="topup/games/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"TopUp - {self.product.name}"


class TopUpField(models.Model):
    game = models.ForeignKey(TopUpGame, on_delete=models.CASCADE, related_name="fields")

    title = models.CharField(max_length=200)
    placeholder = models.CharField(max_length=200, null=True, blank=True)
    key = models.SlugField(
        help_text="key used in frontend & backend (player_id, zone, server)"
    )

    field_type = models.CharField(
        max_length=20, choices=FieldTypes.choices, default=FieldTypes.Text
    )

    min_input_length = models.PositiveIntegerField(default=1)

    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]
        indexes = [
            models.Index(fields=["game"]),
            models.Index(fields=["key"]),
        ]
        constraints = [
        models.UniqueConstraint(
            fields=["game", "key"],
            name="unique_game_field_key"
        )
    ]


    def __str__(self):
        return f"{self.game.product.name} - {self.title}"


class TopUpFieldHelp(models.Model):
    field = models.ForeignKey(
        TopUpField, on_delete=models.CASCADE, related_name="helps"
    )

    description = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to="topup/field_help/", null=True, blank=True)

    def __str__(self):
        return f"Help for {self.field.title}"


class TopUpPackage(models.Model):
    class PublicManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_active=True)

    objects = models.Manager()
    public = PublicManager()
    
    game = models.ForeignKey(
        TopUpGame, on_delete=models.CASCADE, related_name="packages"
    )

    name = models.CharField(max_length=150)
    amount = models.CharField(max_length=100, help_text="Example: 60 Diamonds / 325 UC")

    price = models.DecimalField(max_digits=15, decimal_places=4)
    image = models.ImageField(upload_to="topup/packages/", null=True, blank=True)

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    is_popular = models.BooleanField(default=False)
    
    stock_mode = models.CharField(
        max_length=20,
        choices=StockMode.choices,
    )
    
    manual_fulfillment_time = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    
    codes = GenericRelation(
        "codes.FulfillmentCode",
        related_query_name="topup_package"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    
    @property
    def stock_status(self):
        if self.stock_mode == StockMode.MANUAL:
            return ("Manual", self.manual_fulfillment_time)
        else:
            return ("Automatic", 0)


    class Meta:
        ordering = ["order", "-created_at"]
        indexes = [
            models.Index(fields=["game"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.game.product.name} - {self.amount}"


class TopUpUserData(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="topup_data")
    order_item = models.ForeignKey(
        "orders.OrderItem", on_delete=models.CASCADE, related_name="topup_data"
    )
    game = models.ForeignKey(
        TopUpGame, on_delete=models.CASCADE, related_name="user_data"
    )
    fields = models.JSONField(
        help_text="User inputs like player_id, zone, server..."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["game"]),
        ]

    def __str__(self):
        order_number = getattr(self.order_item.order, "order_number", "N/A")
        return f"{self.user.username} - {self.game.product.name} - Order: {order_number}"
