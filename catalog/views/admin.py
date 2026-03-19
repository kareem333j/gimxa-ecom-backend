from rest_framework.views import APIView
from rest_framework.response import Response

from catalog.models import Category, Product, Tag, ProductImage, ProductAttribute
from catalog.serializers import (
    ProductAdminSerializer,
    TagSerializerPublic,
    CategorySerializerAdmin,
    ProductListAdminSerializer,
    ProductAdminWriteSerializer,
    CategoryAdminWriteSerializer,
    ProductImageSerializer,
    ProductAttributeSerializer
)
from core.response_schema import get_response_schema_1
from permissions.custom import AdminPermission
from users_auth.authentication import CookieJWTAuthentication
from django.core.cache import cache
from cache.utils import (
    get_product_cache_timeout,
    get_product_cache_key, 
    get_product_list_cache_page_key, 
    format_filter_value, 
    get_tag_cache_timeout, 
    get_category_cache_timeout, 
    get_category_cache_key
)
from django.db.models import Q, Min
from django.db.models.functions import Coalesce
from core.pagination import DynamicPageNumberPagination

class CategoryAdminView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]
    serializer_class = CategorySerializerAdmin

    def get(self, _request):
        data = cache.get("all_categories")
        if data:
            return Response(get_response_schema_1(
                data=data,
                status=200,
                message="Categories retrieved successfully (cached)"
            ), status=200)
            
        categories_qs = Category.objects.filter(parent=None).prefetch_related("children")
        categories = CategorySerializerAdmin(categories_qs, many=True).data
        cache.set("all_categories", categories, get_category_cache_timeout())
        return Response(get_response_schema_1(
            data=categories,
            status=200,
            message="Categories retrieved successfully"
        ), status=200)
    
    def post(self, request):
        serializer = CategoryAdminWriteSerializer(data=request.data)
        if serializer.is_valid():
            category = serializer.save()
            cache.delete("all_categories")
            return Response(get_response_schema_1(
                data=CategorySerializerAdmin(category).data,
                status=201,
                message="Category created successfully"
            ), status=201)
        return Response(get_response_schema_1(
            data=None,
            errors=serializer.errors,
            status=400,
        ), status=400)

class CategoryAdminDetailView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]
    serializer_class = CategorySerializerAdmin

    def get(self, _request, slug):
        try:
            category = Category.objects.get(slug=slug)
            return Response(get_response_schema_1(
                data=CategorySerializerAdmin(category).data,
                status=200,
                message="Category retrieved successfully"
            ), status=200)
        except Category.DoesNotExist:
            return Response(get_response_schema_1(message="Category not found", status=404), status=404)
    
    def put(self, request, slug):
        try:
            category = Category.objects.get(slug=slug)
        except Category.DoesNotExist:
            return Response(get_response_schema_1(message="Category not found", status=404), status=404)

        serializer = CategoryAdminWriteSerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            category = serializer.save()
            cache.delete("all_categories")
            cache.delete(get_category_cache_key(slug))
            return Response(get_response_schema_1(
                data=CategorySerializerAdmin(category).data,
                status=200,
                message="Category updated successfully"
            ), status=200)
        return Response(get_response_schema_1(
            errors=serializer.errors,
            status=400
        ), status=400)
    
    def delete(self, _request, slug):
        try:
            category = Category.objects.get(slug=slug)
            category.delete()
            cache.delete("all_categories")
            cache.delete(get_category_cache_key(slug))
            return Response(get_response_schema_1(
                data=None,
                status=204,
                message="Category deleted successfully"
            ), status=204)
        except Category.DoesNotExist:
            return Response(get_response_schema_1(message="Category not found", status=404), status=404)
        
class TagAdminView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]
    serializer_class = TagSerializerPublic

    def get(self, _request):
        data = cache.get("all_tags")
        if data:
            return Response(get_response_schema_1(
                data=data,
                status=200,
                message="Tags retrieved successfully (cached)"
            ), status=200)
            
        tags = TagSerializerPublic(Tag.objects.all(), many=True).data
        
        cache.set("all_tags", tags, get_tag_cache_timeout())
        
        return Response(get_response_schema_1(
            data=tags,
            status=200,
            message="Tags retrieved successfully"
        ), status=200)
    
    def post(self, request):
        serializer = TagSerializerPublic(data=request.data)
        if serializer.is_valid():
            tag = serializer.save()
            cache.delete("all_tags")  
            return Response(get_response_schema_1(
                data=TagSerializerPublic(tag).data,
                status=201,
                message="Tag created successfully"
            ), status=201)
        return Response(get_response_schema_1(
            errors=serializer.errors,
            status=400
        ), status=400)

class TagAdminDetailView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]
    serializer_class = TagSerializerPublic

    def get(self, request, slug):
        try:
            tag = Tag.objects.get(slug=slug)
            return Response(get_response_schema_1(
                data=TagSerializerPublic(tag).data,
                status=200,
                message="Tag retrieved successfully"
            ), status=200)
        except Tag.DoesNotExist:
            return Response(get_response_schema_1(message="Tag not found", status=404), status=404)
    
    def put(self, request, slug):
        try:
            tag = Tag.objects.get(slug=slug)
        except Tag.DoesNotExist:
            return Response(get_response_schema_1(message="Tag not found", status=404), status=404)

        serializer = TagSerializerPublic(tag, data=request.data, partial=True)
        if serializer.is_valid():
            tag = serializer.save()
            cache.delete("all_tags")  
            return Response(get_response_schema_1(
                data=TagSerializerPublic(tag).data,
                status=200,
                message="Tag updated successfully"
            ), status=200)
        return Response(get_response_schema_1(
            errors=serializer.errors,
            status=400
        ), status=400)
    
    def delete(self, _request, slug):
        try:
            tag = Tag.objects.get(slug=slug)
            tag.delete()
            cache.delete("all_tags")
            return Response(get_response_schema_1(
                data=None,
                status=204,
                message="Tag deleted successfully"
            ), status=204)
        except Tag.DoesNotExist:
            return Response(get_response_schema_1(message="Tag not found", status=404), status=404)
        
class ProductAdminListView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]
    ALLOWED_FILTERS = {"category", "tags", "is_popular", "region", "is_featured", "product_type", "is_available", "is_topup", "is_active"}
    ALLOWED_ORDERING = {"price", "-price"}

    def get(self, request):
        page_number = request.query_params.get('page', 1)
        filter_params = request.query_params.get('filter', None)
        search_query = request.query_params.get('search', None)
        price_min = request.query_params.get('price_min', None)
        price_max = request.query_params.get('price_max', None)
        ordering = request.query_params.get('ordering', None)

        paginator = DynamicPageNumberPagination()
        page_size = paginator.get_page_size(request)

        filter_dict = {}
        if filter_params:
            for pair in filter_params.split(','):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    if k in self.ALLOWED_FILTERS:
                        filter_dict[k] = format_filter_value(v)
                    else:
                        return Response(get_response_schema_1(
                            message="Invalid filter parameter",
                            status=400
                        ), status=400)

        if ordering and ordering not in self.ALLOWED_ORDERING:
            return Response(get_response_schema_1(
                message="Invalid ordering. Allowed: price, -price",
                status=400
            ), status=400)

        cache_key = get_product_list_cache_page_key(
            page_number=page_number,
            page_size=page_size,
            filter_params=','.join([f"{k}={v}" for k, v in filter_dict.items()]) if filter_dict else None,
            search_query=search_query,
            is_admin=True,
            extra=f"pmin={price_min}&pmax={price_max}&ord={ordering}"
        )

        data = cache.get(cache_key)

        if data:
            return Response(get_response_schema_1(
                data=data,
                status=200,
                message="Products retrieved successfully (cached)"
            ), status=200)

        queryset = Product.objects.annotate(
            min_package_price=Min('topup__packages__price')
        )

        if filter_dict:
            queryset = queryset.filter(**filter_dict)

        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(short_description__icontains=search_query) |
                Q(tags__name__icontains=search_query) |
                Q(category__name__icontains=search_query) |
                Q(product_type__icontains=search_query)
            )

        if price_min:
            try:
                price_min_val = float(price_min)
                queryset = queryset.filter(
                    Q(price__gte=price_min_val) | Q(min_package_price__gte=price_min_val)
                )
            except ValueError:
                return Response(get_response_schema_1(
                    message="Invalid price_min value", status=400
                ), status=400)

        if price_max:
            try:
                price_max_val = float(price_max)
                queryset = queryset.filter(
                    Q(price__lte=price_max_val) | Q(min_package_price__lte=price_max_val)
                )
            except ValueError:
                return Response(get_response_schema_1(
                    message="Invalid price_max value", status=400
                ), status=400)

        if ordering:
            sort_expr = Coalesce('price', 'min_package_price')
            queryset = queryset.order_by(sort_expr.desc() if ordering == '-price' else sort_expr)

        queryset = queryset.prefetch_related('images', 'topup__packages').distinct()

        # pagination
        page = paginator.paginate_queryset(queryset, request)

        serializer = ProductListAdminSerializer(page, many=True)
        data = paginator.get_paginated_response(serializer.data).data

        cache.set(cache_key, data, get_product_cache_timeout())

        return Response(get_response_schema_1(
            data=data,
            status=200,
            message="Products retrieved successfully"
        ), status=200)
        
    def post(self, request):
        serializer = ProductAdminWriteSerializer(data=request.data)
        if serializer.is_valid():
            product = serializer.save()
            cache.delete(get_product_cache_key(product.slug))
            return Response(get_response_schema_1(
                data=ProductAdminSerializer(product).data,
                status=201,
                message="Product created successfully"
            ), status=201)
        return Response(get_response_schema_1(
            errors=serializer.errors,
            status=400
        ), status=400)

class ProductDetailAdminView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, _request, slug):
        try:
            product = Product.objects.prefetch_related('images').get(slug=slug)
            serializer = ProductAdminSerializer(product)
            return Response(get_response_schema_1(
                data=serializer.data,
                status=200,
                message="Product retrieved successfully"
            ), status=200)
        except Product.DoesNotExist:
            return Response(get_response_schema_1(message="Product not found", status=404), status=404)
        
    def put(self, request, slug):
        try:
            product = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            return Response(get_response_schema_1(message="Product not found", status=404), status=404)

        serializer = ProductAdminWriteSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            product = serializer.save()
            cache.delete(get_product_cache_key(product.slug))
            return Response(get_response_schema_1(
                data=ProductAdminSerializer(product).data,
                status=200,
                message="Product updated successfully"
            ), status=200)
        return Response(get_response_schema_1(
            errors=serializer.errors,
            status=400
        ), status=400)
        
    def delete(self, _request, slug):
        try:
            product = Product.objects.get(slug=slug)
            product.delete()
            cache.delete(get_product_cache_key(product.slug))
            return Response(get_response_schema_1(
                data=None,
                status=204,
                message="Product deleted successfully"
            ), status=204)
        except Product.DoesNotExist:
            return Response(get_response_schema_1(message="Product not found", status=404), status=404)


class ProductImageAdminView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, slug):
        try:
            product = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            return Response(get_response_schema_1(message="Product not found", status=404), status=404)

        serializer = ProductImageSerializer(data=request.data)
        if serializer.is_valid():
            image = serializer.save(product=product)
            cache.delete(get_product_cache_key(product.slug))
            return Response(get_response_schema_1(
                data=ProductImageSerializer(image).data,
                status=201,
                message="Product image created successfully"
            ), status=201)
        return Response(get_response_schema_1(
            errors=serializer.errors,
            status=400
        ), status=400)

    def put(self, request, slug, image_id):
        try:
            product = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            return Response(get_response_schema_1(message="Product not found", status=404), status=404)

        try:
            image = ProductImage.objects.get(id=image_id, product=product)
        except ProductImage.DoesNotExist:
            return Response(get_response_schema_1(message="Product image not found", status=404), status=404)

        serializer = ProductImageSerializer(image, data=request.data, partial=True)
        if serializer.is_valid():
            image = serializer.save()
            cache.delete(get_product_cache_key(product.slug))
            return Response(get_response_schema_1(
                data=ProductImageSerializer(image).data,
                status=200,
                message="Product image updated successfully"
            ), status=200)
        return Response(get_response_schema_1(
            errors=serializer.errors,
            status=400
        ), status=400)

    def delete(self, _request, slug, image_id):
        try:
            product = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            return Response(get_response_schema_1(message="Product not found", status=404), status=404)

        try:
            image = ProductImage.objects.get(id=image_id, product=product)
            image.delete()
            cache.delete(get_product_cache_key(product.slug))
            return Response(get_response_schema_1(
                data=None,
                status=204,
                message="Product image deleted successfully"
            ), status=204)
        except ProductImage.DoesNotExist:
            return Response(get_response_schema_1(message="Product image not found", status=404), status=404)


class ProductAttributeAdminView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, slug):
        try:
            product = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            return Response(get_response_schema_1(message="Product not found", status=404), status=404)

        serializer = ProductAttributeSerializer(data=request.data)
        if serializer.is_valid():
            attribute = serializer.save(product=product)
            cache.delete(get_product_cache_key(product.slug))
            return Response(get_response_schema_1(
                data=ProductAttributeSerializer(attribute).data,
                status=201,
                message="Product attribute created successfully"
            ), status=201)
        return Response(get_response_schema_1(
            errors=serializer.errors,
            status=400
        ), status=400)

    def put(self, request, slug, attribute_id):
        try:
            product = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            return Response(get_response_schema_1(message="Product not found", status=404), status=404)

        try:
            attribute = ProductAttribute.objects.get(id=attribute_id, product=product)
        except ProductAttribute.DoesNotExist:
            return Response(get_response_schema_1(message="Product attribute not found", status=404), status=404)

        serializer = ProductAttributeSerializer(attribute, data=request.data, partial=True)
        if serializer.is_valid():
            attribute = serializer.save()
            cache.delete(get_product_cache_key(product.slug))
            return Response(get_response_schema_1(
                data=ProductAttributeSerializer(attribute).data,
                status=200,
                message="Product attribute updated successfully"
            ), status=200)
        return Response(get_response_schema_1(
            errors=serializer.errors,
            status=400
        ), status=400)

    def delete(self, _request, slug, attribute_id):
        try:
            product = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            return Response(get_response_schema_1(message="Product not found", status=404), status=404)

        try:
            attribute = ProductAttribute.objects.get(id=attribute_id, product=product)
            attribute.delete()
            cache.delete(get_product_cache_key(product.slug))
            return Response(get_response_schema_1(
                data=None,
                status=204,
                message="Product attribute deleted successfully"
            ), status=204)
        except ProductAttribute.DoesNotExist:
            return Response(get_response_schema_1(message="Product attribute not found", status=404), status=404)
