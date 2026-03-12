from django.db import models

class CouponScope(models.TextChoices):
    PRODUCT = "product", "Product"
    CATEGORY = "category", "Category"
    PACKAGE = "package", "Package"
    GLOBAL = "global", "Global"
    
class DiscountType(models.TextChoices):
    FIXED = "fixed", "Fixed"
    PERCENT = "percent", "Percent"