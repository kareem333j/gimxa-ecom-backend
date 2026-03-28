from rest_framework import serializers
from catalog.models import Product
from catalog.utils.choices import ProductType
from topup.serializers import TopUpValidateSerializer
from cart.models import Cart, CartItem
from payments.mixins import CurrencySerializerMixin    
from django.db.models import Sum
from decimal import Decimal
        
class CartItemSerializer(CurrencySerializerMixin, serializers.ModelSerializer):
    PRICE_FIELDS = ["unit_price", "total_price"]
    product = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "product",
            "quantity",
            "unit_price",
            "total_price",
            "topup_package",
            "topup_data"
        ]

    def get_product(self, obj):
        return {
            "id": obj.product.id,
            "name": obj.product.name,
            "slug": obj.product.slug,
            "is_topup": obj.product.product_type == ProductType.TOPUP,
        }
        
class CartSerializer(CurrencySerializerMixin, serializers.ModelSerializer):
    PRICE_FIELDS = ["subtotal", "discount", "total_after_discount"]
    items = CartItemSerializer(many=True, read_only=True)
    coupon = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    total_after_discount = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id", 
            "items", 
            "coupon", 
            "subtotal", 
            "discount", 
            "total_after_discount",
        ]

    def get_coupon(self, obj):
        if not obj.coupon:
            return None
        from coupons.services.coupon_service import get_coupon_summary
        currency = self.get_currency(obj)
        cart_items = list(obj.items.select_related("product").all())
        return get_coupon_summary(obj.coupon, currency=currency, cart_items=cart_items)

    def get_subtotal(self, obj):
        return obj.items.aggregate(total=Sum("total_price"))["total"] or 0

    def get_discount(self, obj):
        if not obj.coupon:
            return 0
        from coupons.services.coupon_service import calculate_discount
        items = obj.items.select_related("product").prefetch_related("product__category").all()
        discount_info = calculate_discount(obj.coupon, items)
        return discount_info["total_discount"]

    def get_total_after_discount(self, obj):
        subtotal = self.get_subtotal(obj)
        discount = self.get_discount(obj)
        return max(Decimal(str(subtotal)) - Decimal(str(discount)), Decimal("0.00"))
    
class AddToCartSerializer(serializers.Serializer):
    product_slug = serializers.SlugField()
    quantity = serializers.IntegerField(min_value=1, default=1)

    # topup
    topup_package_id = serializers.IntegerField(required=False)
    topup_data = serializers.JSONField(required=False)

    def validate(self, attrs):
        try:
            product = Product.public.get(slug=attrs["product_slug"])
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or inactive")

        if product.product_type == ProductType.TOPUP:
            if not attrs.get("topup_package_id"):
                raise serializers.ValidationError("topup_package_id is required")

            TopUpValidateSerializer(
                data={
                    "product_slug": product.slug,
                    "data": attrs.get("topup_data", {}),
                }
            ).is_valid(raise_exception=True)

        else:
            attrs.pop("topup_package_id", None)
            attrs.pop("topup_data", None)

        attrs["product"] = product
        attrs["is_topup"] = product.product_type == ProductType.TOPUP
        return attrs

class CartItemUpdateSerializer(serializers.Serializer):
    product_slug = serializers.SlugField()

    quantity = serializers.IntegerField(required=False, min_value=0)
    quantity_delta = serializers.IntegerField(required=False)

    topup_package_id = serializers.IntegerField(required=False)
    topup_data = serializers.JSONField(required=False)

    def validate(self, attrs):
        quantity = attrs.get("quantity")
        quantity_delta = attrs.get("quantity_delta")

        if quantity is None and quantity_delta is None:
            raise serializers.ValidationError(
                "quantity or quantity_delta is required"
            )

        if quantity is not None and quantity_delta is not None:
            raise serializers.ValidationError(
                "Use either quantity or quantity_delta"
            )

        try:
            product = Product.public.get(slug=attrs["product_slug"])
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or inactive")

        if product.product_type == ProductType.TOPUP:
            if not attrs.get("topup_package_id"):
                raise serializers.ValidationError("topup_package_id is required")

            TopUpValidateSerializer(
                data={
                    "product_slug": product.slug,
                    "data": attrs.get("topup_data", {}),
                }
            ).is_valid(raise_exception=True)
        else:
            attrs.pop("topup_package_id", None)
            attrs.pop("topup_data", None)

        attrs["product"] = product
        attrs["is_topup"] = product.product_type == ProductType.TOPUP

        return attrs