from rest_framework import serializers
from catalog.utils.choices import ProductType
from rest_framework.validators import UniqueValidator

from catalog.models import (
    Category,
    ProductAttribute,
    Tag,
    Product,
    ProductImage,
)

class CategorySerializerPublic(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "description",
            "slug",
            "parent",
            "level",
            "order",
            "is_active",
            "image",
            "logo",
            "children",
        ]

    def get_children(self, obj):
        return CategorySerializerPublic(obj.children.filter(is_active=True), many=True).data

class CategoryShortSerializerPublic(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
        ]

class CategorySerializerAdmin(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "description",
            "slug",
            "parent",
            "level",
            "order",
            "is_active",
            "image",
            "logo",
            "children",
        ]

    def get_children(self, obj):
        return CategorySerializerAdmin(obj.children.all(), many=True).data

class CategoryAdminWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'
        extra_kwargs = {
            "slug": {
                "validators": [
                    UniqueValidator(queryset=Category.objects.all())
                ],
            },
            "parent": {
                "allow_null": True,
            },
            "level": {
                "read_only": True,
            },
        }
    

class CategorySerializerForProduct(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "image",
            "logo",
            "children",
        ]

    def get_children(self, obj):
        if obj.level >= 4:
            return []
        return CategorySerializerForProduct(
            obj.children.filter(is_active=True),
            many=True
        ).data

class TagSerializerPublic(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "is_active"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_main"]

class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = ["id", "name", "value"]
 
class ProductListSerializer(serializers.ModelSerializer):
    main_image = serializers.SerializerMethodField()
    is_topup = serializers.SerializerMethodField()
    tags = TagSerializerPublic(many=True, read_only=True)
    categories = CategoryShortSerializerPublic(source="category", many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "stock_mode",
            "manual_fulfillment_time",
            "description",
            "short_description",
            "price",
            "product_type",
            "tags",
            "categories",
            "is_available",
            "is_popular",
            "main_image",
            "is_topup",
        ]
    
    def get_main_image(self, obj):
        image = obj.images.filter(is_main=True).first()
        return ProductImageSerializer(image).data if image else None

    def get_is_topup(self, obj):
        return obj.product_type == ProductType.TOPUP

class ProductShortDetailSerializerPublic(serializers.ModelSerializer):
    main_image = serializers.SerializerMethodField()
    tags = TagSerializerPublic(many=True, read_only=True)
    categories = CategoryShortSerializerPublic(source="category", many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "stock_mode",
            "manual_fulfillment_time",
            "description",
            "short_description",
            "info",
            "logo",
            "is_available",
            "is_popular",
            "product_type",
            "tags",
            "categories",
            "main_image"
        ]

    def get_main_image(self, obj):
        image = obj.images.filter(is_main=True).first()
        return ProductImageSerializer(image).data if image else None

class ProductDetailSerializerPublic(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    tags = TagSerializerPublic(many=True, read_only=True)
    categories = CategorySerializerPublic(source="category", many=True, read_only=True)
    is_topup = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "stock_mode",
            "manual_fulfillment_time",
            "description",
            "short_description",
            "info",
            "logo",
            "price",
            "is_available",
            "is_popular",
            "product_type",
            "tags",
            "categories",
            "images",
            "attributes",
            "is_topup",
        ]
    
    def get_is_topup(self, obj):
        return obj.product_type == ProductType.TOPUP

class ProductAdminSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    tags = TagSerializerPublic(many=True, read_only=True)
    categories = CategoryShortSerializerPublic(source="category", many=True, read_only=True)
    is_topup = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "stock_mode",
            "manual_fulfillment_time",
            "description",
            "short_description",
            "info",
            "logo",
            "price",
            "is_available",
            "product_type",
            "tags",
            "categories",
            "images",
            "attributes",
            "is_topup",
            "is_active",
            "is_popular",
            "created_at",
            "updated_at",
        ]
    
    def get_is_topup(self, obj):
        return obj.product_type == ProductType.TOPUP

class ProductDashboardAdminSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    tags = TagSerializerPublic(many=True, read_only=True)
    categories = CategoryShortSerializerPublic(source="category", many=True, read_only=True)
    is_topup = serializers.SerializerMethodField()
    fields = serializers.SerializerMethodField(method_name="get_topup_fields")
    packages = serializers.SerializerMethodField(method_name="get_topup_packages")

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "stock_mode",
            "manual_fulfillment_time",
            "description",
            "short_description",
            "info",
            "logo",
            "price",
            "is_available",
            "product_type",
            "tags",
            "categories",
            "images",
            "attributes",
            "is_topup",
            "is_active",
            "is_popular",
            "fields",
            "packages",
            "created_at",
            "updated_at",
        ]
    
    def get_is_topup(self, obj):
        return obj.product_type == ProductType.TOPUP

    def get_topup_fields(self, obj):
        if obj.product_type == ProductType.TOPUP and hasattr(obj, "topup"):
            from topup.serializers import TopUpFieldSerializer
            return TopUpFieldSerializer(obj.topup.fields.all(), many=True).data
        return None

    def get_topup_packages(self, obj):
        if obj.product_type == ProductType.TOPUP and hasattr(obj, "topup"):
            from topup.serializers import TopUpSimplePackageAdminSerializer
            return TopUpSimplePackageAdminSerializer(obj.topup.packages.all(), many=True).data
        return None

class ProductAdminWriteSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all()
    )
    categories = serializers.PrimaryKeyRelatedField(
        source="category",
        many=True,
        queryset=Category.objects.all()
    )

    class Meta:
        model = Product
        fields = "__all__"


class ProductListAdminSerializer(serializers.ModelSerializer):
    main_image = serializers.SerializerMethodField()
    is_topup = serializers.SerializerMethodField()
    tags = TagSerializerPublic(many=True, read_only=True)
    categories = CategoryShortSerializerPublic(source="category", many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "stock_mode",
            "manual_fulfillment_time",
            "description",
            "short_description",
            "price",
            "product_type",
            "is_available",
            "is_popular",
            "main_image",
            "is_topup",
            "tags",
            "categories",
            "is_active",
            "created_at",
            "updated_at",
        ]
    
    def get_main_image(self, obj):
        image = obj.images.filter(is_main=True).first()
        return ProductImageSerializer(image).data if image else None

    def get_is_topup(self, obj):
        return obj.product_type == ProductType.TOPUP


# search
# class SearchSerializer(serializers.ModelSerializer):
#     main_image = serializers.SerializerMethodField()
#     class Meta:
#         model = Product
#         fields = (
#             'id',
#             "name",
#             "slug",
#             "is_popular",
#             "price",
#             "product_type",
#             "short_description",
#             'logo',
#             'main_image',
#             "is_available",
#         )

#     def get_main_image(self, obj):
#         image = obj.images.filter(is_main=True).first()
#         return ProductImageSerializer(image).data if image else None