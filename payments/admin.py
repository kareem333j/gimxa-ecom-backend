from django.contrib import admin
from .models import  PaymentGateway, Payment

# Register your models here.
@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ("name", "tax_rate", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)

admin.site.register(Payment)
