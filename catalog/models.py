from google.auth import default
from django.db import models
from django.utils.text import slugify
from catalog.utils.choices import ProductType, StockMode
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation

User = get_user_model()

class Category(models.Model):
    class CategoryManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_active=True)
    
    objects = models.Manager()

    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="children", null=True, blank=True
    )
    level = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to="category/images/", null=True, blank=True)
    logo = models.ImageField(upload_to="category/logos/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    public = CategoryManager()

    class Meta:
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["parent"]),
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def save(self, *args, **kwargs):
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 0

        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug
            
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(models.Model):
    class TagManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_active=True)
    
    objects = models.Manager()

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    public = TagManager()

    class Meta:
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["name"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            while Tag.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    class ProductManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_active=True)
    
    objects = models.Manager()
    public = ProductManager()
    
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)

    category = models.ManyToManyField(
        Category, related_name="products", blank=True
    )
    tags = models.ManyToManyField(Tag, related_name="product_tags", blank=True)

    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
    )

    region = models.CharField(max_length=100, default="global")
    
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
        related_query_name="product"
    )

    short_description = models.CharField(max_length=500, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    info = models.JSONField(null=True, blank=True)
    logo = models.ImageField(upload_to="products/logos/", null=True, blank=True)

    price = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["product_type"]),
            models.Index(fields=["is_active", "is_available"]),
            models.Index(fields=["name"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug
        super().save(*args, **kwargs)
        
    @property
    def stock_status(self):
        if self.stock_mode == StockMode.MANUAL:
            return ("Manual", self.manual_fulfillment_time)
        else:
            return ("Automatic", 0)

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )

    image = models.ImageField(upload_to="products/")
    is_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["product"]),
        ]

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductAttribute(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="attributes"
    )

    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.name}: {self.value}"