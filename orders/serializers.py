from rest_framework import serializers
from payments.mixins import CurrencySerializerMixin

from orders.models import Order, OrderItem

class OrderItemSerializer(CurrencySerializerMixin, serializers.ModelSerializer):
    PRICE_FIELDS = ["price"]
    topup_data = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product_name",
            "product_slug",
            "quantity",
            "price",
            "is_topup",
            "topup_package",
            "topup_data",
            "created_at",
        )

    def get_topup_data(self, obj):
        if not obj.is_topup:
            return None
        topup_entry = obj.topup_data.first()
        if topup_entry:
            return topup_entry.fields
        return None
        
class OrderListSerializer(CurrencySerializerMixin, serializers.ModelSerializer):
    PRICE_FIELDS = ["total_price", "tax", "discount_total", "subtotal"]
    items_count = serializers.SerializerMethodField()
    payment_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "status",
            "total_price",
            "created_at",
            "user",
            "tax",
            "discount_total",
            "subtotal",
            "coupon_code",
            "items_count",
            "payment_details",
        )

    def get_items_count(self, obj):
        return obj.items.count()

    def get_payment_details(self, obj):
        payment = obj.payments.order_by("-created_at").first()
        if not payment:
            return None

        return {
            "gateway_id": payment.gateway.id,
            "gateway_name": payment.gateway.name,
            "status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency,
        }
        
class OrderDetailSerializer(CurrencySerializerMixin, serializers.ModelSerializer):
    PRICE_FIELDS = ["subtotal", "tax", "discount_total", "total_price"]
    items = OrderItemSerializer(many=True, read_only=True)
    payment_details = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "status",
            "subtotal",
            "tax",
            "coupon_code",
            "discount_total",
            "total_price",
            "created_at",
            "items",
            "payment_details",
        )

    def get_payment_details(self, obj):
        payment = obj.payments.order_by("-created_at").first()
        if not payment:
            return None

        return {
            "gateway_id": payment.gateway.id,
            "gateway_name": payment.gateway.name,
            "status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency,
        }
