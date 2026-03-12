from rest_framework import serializers
from .models import PaymentGateway

class PaymentGatewaySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentGateway
        fields = ['id', 'name', 'tax_rate', 'description', 'icon']
