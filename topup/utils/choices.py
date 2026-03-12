from django.db import models

class FieldTypes(models.TextChoices):
    Text = 'text', 'Text'
    Number = 'number', 'Number'