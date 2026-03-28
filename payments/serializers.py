from .models import PaymentGateway, Payment
from rest_framework import serializers
from orders.serializers import OrderDetailSerializer

class PaymentGatewaySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentGateway
        fields = ['id', 'name', 'tax_rate', 'description', 'icon']

class AdminPaymentGatewaySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentGateway
        fields = ['id', 'name', 'tax_rate', 'description', 'icon', 'is_active', "created_at", "updated_at"]

class PaymentSerializer(serializers.ModelSerializer):
    user = serializers.IntegerField(source='order.user.id', read_only=True)
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'order_number', 'user', 'gateway', 'gateway_name', 
            'amount', 'currency', 'status', 'transaction_id', 'created_at'
        ]

class AdminPaymentSimpleSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='order.user.id', read_only=True)
    username = serializers.CharField(source='order.user.username', read_only=True)
    user_email = serializers.CharField(source='order.user.email', read_only=True)
    full_name = serializers.CharField(source='order.user.full_name', read_only=True)
    user_country = serializers.CharField(source='order.user.profile.country', read_only=True)
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'order_number', 'user_id', 'username', 'user_email','full_name', 
            'user_country', 'gateway', 'gateway_name', 'amount', 'currency', 
            'status', 'transaction_id', 'created_at'
        ]

class AdminPaymentSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='order.user.id', read_only=True)
    username = serializers.CharField(source='order.user.username', read_only=True)
    user_email = serializers.CharField(source='order.user.email', read_only=True)
    user_country = serializers.CharField(source='order.user.profile.country', read_only=True)
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'order_number', 'user_id', 'username', 'user_email', 
            'user_country', 'gateway', 'gateway_name', 'amount', 'currency', 
            'status', 'transaction_id', 'created_at', 'raw_response'
        ]

class AdminPaymentDetailSerializer(serializers.ModelSerializer):
    order_details = OrderDetailSerializer(source='order', read_only=True)
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)
    user_id = serializers.UUIDField(source='order.user.id', read_only=True)
    username = serializers.CharField(source='order.user.username', read_only=True)
    user_email = serializers.CharField(source='order.user.email', read_only=True)
    full_name = serializers.CharField(source='order.user.full_name', read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # We can add custom logic here if needed, but 'order_details' is already included via the field definition
        return ret
