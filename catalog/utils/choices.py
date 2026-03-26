from django.db import models

class ProductType(models.TextChoices):
    DIGITAL = 'digital', 'Digital'
    TOPUP = 'topup', 'Top-up'
    
class StockMode(models.TextChoices):
    AUTOMATIC = 'automatic', 'Automatic'
    MANUAL = 'manual', 'Manual'