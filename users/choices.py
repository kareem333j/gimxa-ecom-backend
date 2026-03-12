from django.db import models

class AUTH_PROVIDERS(models.TextChoices):
    EMAIL = 'email', 'Email'
    GOOGLE = 'google', 'Google'

class LANGUAGES(models.TextChoices):
    EN = 'en', 'English'
    AR = 'ar', 'Arabic'

class COLOR_MODES(models.TextChoices):
    LIGHT = 'light', 'Light'
    DARK = 'dark', 'Dark'

class Role(models.TextChoices):
    USER = 'user', 'User'
    ADMIN = 'admin', 'Admin'
    SELLER = 'seller', 'Seller'
    DEVELOPER = 'developer', 'Developer'