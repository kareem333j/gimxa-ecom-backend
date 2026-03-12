from rest_framework import serializers

from coupons.models import Coupon, CouponProduct, CouponCategory, CouponPackage, CouponUsage


class CouponProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)

    class Meta:
        model = CouponProduct
        fields = (
            "id",
            "product",
            "product_name",
            "product_slug",
            "discount_type",
            "discount_value",
        )


class CouponCategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)

    class Meta:
        model = CouponCategory
        fields = (
            "id",
            "category",
            "category_name",
            "category_slug",
            "discount_type",
            "discount_value",
        )


class CouponPackageSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source="package.name", read_only=True)
    package_slug = serializers.CharField(source="package.slug", read_only=True)

    class Meta:
        model = CouponPackage
        fields = (
            "id",
            "package",
            "package_name",
            "package_slug",
            "discount_type",
            "discount_value",
        )

class SimpleCouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = (
            "id",
            "code",
            "scope",
            "discount_type",
            "discount_value",
            "is_active",
            "start_at",
            "end_at",
            "max_usage",
            "used_count",
            "created_at",
        )

class CouponSerializer(serializers.ModelSerializer):
    product_discounts = CouponProductSerializer(many=True, read_only=True)
    category_discounts = CouponCategorySerializer(many=True, read_only=True)
    package_discounts = CouponPackageSerializer(many=True, read_only=True)

    class Meta:
        model = Coupon
        fields = (
            "id",
            "code",
            "scope",
            "discount_type",
            "discount_value",
            "is_active",
            "start_at",
            "end_at",
            "max_usage",
            "used_count",
            "product_discounts",
            "category_discounts",
            "package_discounts",
            "created_at",
        )


class CouponUsageSerializer(serializers.ModelSerializer):
    coupon_code = serializers.CharField(source="coupon.code", read_only=True)

    class Meta:
        model = CouponUsage
        fields = (
            "id",
            "coupon",
            "coupon_code",
            "user",
            "order",
            "used_at",
        )


class ValidateCouponSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)

    def validate_code(self, value):
        coupon = Coupon.objects.filter(code__iexact=value).first()
        if not coupon:
            raise serializers.ValidationError("coupon not found")
        if not coupon.is_valid():
            raise serializers.ValidationError("coupon is not valid")
        return value


class ApplyCouponSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)

    def validate_code(self, value):
        coupon = Coupon.objects.filter(code__iexact=value).first()
        if not coupon:
            raise serializers.ValidationError("coupon not found")
        if not coupon.is_valid():
            raise serializers.ValidationError("coupon is not valid")
        return value


# Admin Serializers
class AdminCouponCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = (
            "code",
            "scope",
            "discount_type",
            "discount_value",
            "is_active",
            "start_at",
            "end_at",
            "max_usage",
        )

    def validate(self, attrs):
        scope = attrs.get("scope")
        discount_type = attrs.get("discount_type")
        discount_value = attrs.get("discount_value")

        if scope in ["global"]:
            if not discount_type:
                raise serializers.ValidationError({
                    "discount_type": "you must select discount type"
                })
            if discount_value is None or discount_value <= 0:
                raise serializers.ValidationError({
                    "discount_value": "you must select discount value"
                })

        if discount_type == "percent" and discount_value:
            if discount_value > 100:
                raise serializers.ValidationError({
                    "discount_value": "discount value must be less than or equal to 100"
                })

        return attrs


class AdminCouponProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CouponProduct
        fields = (
            "coupon",
            "product",
            "discount_type",
            "discount_value",
        )

    def validate_discount_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("discount value must be greater than 0")
        return value

class AdminCouponCategoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CouponCategory
        fields = (
            "coupon",
            "category",
            "discount_type",
            "discount_value",
        )

    def validate_discount_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("discount value must be greater than 0")
        return value

class AdminCouponPackageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CouponPackage
        fields = (
            "coupon",
            "package",
            "discount_type",
            "discount_value",
        )

    def validate_discount_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("discount value must be greater than 0")
        return value