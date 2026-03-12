from django.db import models

class ProductType(models.TextChoices):
    GAME = 'game', 'Game'
    TOPUP = 'topup', 'Top-up / Recharge'
    GIFT_CARD = 'giftcard', 'Gift Card'
    SOFTWARE = 'software', 'Software'
    CONSOLE = 'console', 'Console Game'
    
class StockMode(models.TextChoices):
    AUTOMATIC = 'automatic', 'Automatic'
    MANUAL = 'manual', 'Manual'