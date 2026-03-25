from rest_framework import serializers
from topup.models import TopUpFieldHelp, TopUpGame, TopUpField, TopUpPackage
from topup.utils.choices import FieldTypes
from catalog.serializers import ProductShortDetailSerializerPublic
from payments.mixins import CurrencySerializerMixin

class TopUpFieldHelpSerializer(serializers.ModelSerializer):
    field = serializers.PrimaryKeyRelatedField(
        queryset=TopUpField.objects.all(),
        error_messages={
            "required": "Field is required",
            "does_not_exist": "Field not found",
            "incorrect_type": "Invalid field id",
        },
        write_only=True
    )

    class Meta:
        model = TopUpFieldHelp
        fields = ["id", "field", "description", "image"]
        
class TopUpFieldSerializer(serializers.ModelSerializer):
    helps = TopUpFieldHelpSerializer(many=True, read_only=True)

    class Meta:
        model = TopUpField
        fields = [
            "id",
            "title",
            "placeholder",
            "key",
            "field_type",
            "is_required",
            "min_input_length",
            "order",
            "helps",
        ]
        
# TopUpPackageSerializer defined below at line 87

class TopUpGamePublicSerializer(CurrencySerializerMixin, serializers.ModelSerializer):
    PRICE_FIELDS = ["start_from"]
    product = ProductShortDetailSerializerPublic(read_only=True)
    packages = serializers.SerializerMethodField()
    start_from = serializers.SerializerMethodField()

    class Meta:
        model = TopUpGame
        fields = [
            "id",
            "product",
            "logo",
            "packages",
            "start_from",
        ]

    def get_packages(self, obj):
        qs = obj.packages.filter(is_active=True)
        return qs.count()

    def get_start_from(self, obj):
        min_pkg = obj.packages.filter(is_active=True).order_by('price').first()
        return str(min_pkg.price) if min_pkg else None

class TopUpGameDetailPublicSerializer(CurrencySerializerMixin, serializers.ModelSerializer):
    product = ProductShortDetailSerializerPublic(read_only=True)
    fields = TopUpFieldSerializer(many=True, read_only=True)

    class Meta:
        model = TopUpGame
        fields = [
            "id",
            "product",
            "logo",
            "fields",
        ]

class TopUpPackageSerializer(CurrencySerializerMixin, serializers.ModelSerializer):
    PRICE_FIELDS = ["price"]
    class Meta:
        model = TopUpPackage
        fields = [
            "id",
            "name",
            "amount",
            "price",
            "image",
            "order",
            "is_popular",
            "stock_mode"
        ]
    
class TopUpValidateSerializer(serializers.Serializer):
    product_slug = serializers.SlugField()
    data = serializers.JSONField()

    def validate(self, attrs):
        slug = attrs["product_slug"]
        data = attrs["data"]

        try:
            game = TopUpGame.objects.prefetch_related("fields").get(
                product__slug=slug,
                is_active=True
            )
        except TopUpGame.DoesNotExist:
            raise serializers.ValidationError("TopUp game not found")

        errors = {}
        if not isinstance(data, dict):
            raise serializers.ValidationError("Data must be a dict")

        for field in game.fields.all():
            value = data.get(field.key)

            if field.is_required and not value:
                errors[field.key] = "This field is required"

            if value and field.field_type == FieldTypes.Number and not str(value).isdigit():
                errors[field.key] = "Must be a number"

            if value and len(str(value)) < field.min_input_length:
                errors[field.key] = f"Must be at least {field.min_input_length} characters"


        if errors:
            raise serializers.ValidationError(errors)

        attrs["game"] = game
        return attrs
    
# -------- Admin --------
class TopUpGameCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopUpGame
        fields = ["product", "logo", "is_active"]


class TopUpGameAdminSerializer(serializers.ModelSerializer):
    product = ProductShortDetailSerializerPublic(read_only=True)
    fields = TopUpFieldSerializer(many=True, read_only=True)

    class Meta:
        model = TopUpGame
        fields = [
            "id",
            "product",
            "logo",
            "fields",
            "is_active",
            "created_at",
            "updated_at",   
        ]

class TopUpGameReadOnlyAdminSerializer(serializers.ModelSerializer):
    product = ProductShortDetailSerializerPublic(read_only=True)
    fields_count = serializers.SerializerMethodField()
    start_from = serializers.SerializerMethodField()

    class Meta:
        model = TopUpGame
        fields = [
            "id",
            "product",
            "logo",
            "is_active",
            "created_at",
            "updated_at",
            "fields_count",
            "start_from",
        ]
    
    def get_fields_count(self, obj):
        qs = obj.fields.all()
        return qs.count()

    def get_start_from(self, obj):
        min_pkg = obj.packages.filter(is_active=True).order_by('price').first()
        return str(min_pkg.price) if min_pkg else None

class TopUpFieldAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopUpField
        fields = "__all__"


class TopUpSimplePackageAdminSerializer(serializers.ModelSerializer):
    codes = serializers.SerializerMethodField()

    class Meta:
        model = TopUpPackage
        fields = [
            "id",
            "name",
            "amount",
            "price",
            "image",
            "order",
            "is_popular",
            "stock_mode",
            "is_active",
            "manual_fulfillment_time",
            "codes",
        ]

    def get_codes(self, obj):
        return [c.code for c in obj.codes.all()]
        
class TopUpPackageAdminSerializer(serializers.ModelSerializer):
    codes = serializers.SerializerMethodField()

    class Meta:
        model = TopUpPackage
        fields = "__all__"

    def get_codes(self, obj):
        return [c.code for c in obj.codes.all()]