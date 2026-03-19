from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.core.cache import cache
from cache.utils import (
    get_product_cache_key, 
    get_product_cache_timeout, 
    get_product_list_cache_page_key, 
    get_category_cache_timeout, 
    get_category_cache_key, 
    format_filter_value
)
from core.response_schema import get_response_schema_1

from catalog.models import Category, Product, Tag
from catalog.serializers import (
    CategorySerializerPublic,
    ProductDetailSerializerPublic,
    ProductListSerializer,
    TagSerializerPublic,
)
from core.pagination import DynamicPageNumberPagination
from django.db.models import Q, Min
from django.db.models.functions import Coalesce

class CategoryListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, _request):
        data = cache.get("all_categories")
        if data:
            return Response(get_response_schema_1(
                data=data,
                status=200,
                message="Categories retrieved successfully (cached)"
            ), status=200)
            
        categories = CategorySerializerPublic(Category.public.all(), many=True).data
        cache.set("all_categories", categories, get_category_cache_timeout())
        return Response(get_response_schema_1(
            data=categories,
            status=200,
            message="Categories retrieved successfully"
        ), status=200)

class CategoryDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, _request, slug):
        try:
            data = cache.get(get_category_cache_key(slug))
            if data:
                return Response(get_response_schema_1(
                    data=data,
                    status=200,
                    message="Category retrieved successfully (cached)"
                ), status=200)
                
            category = Category.public.prefetch_related('images').get(slug=slug)
            serializer = CategorySerializerPublic(category)
            
            # Cache the category details for future requests
            cache_key = get_category_cache_key(slug)
            cache.set(cache_key, serializer.data, get_category_cache_timeout())
            
            return Response(get_response_schema_1(
                data=serializer.data,
                status=200,
                message="Category retrieved successfully"    
            ), status=200)
        except Category.DoesNotExist:
            return Response(get_response_schema_1(data=None, message="Category not found", status=404), status=404)
    
class TagListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, _request):
        data = cache.get("all_tags")
        if data:
            return Response(get_response_schema_1(
                data=data,
                status=200,
                message="Tags retrieved successfully (cached)"
            ), status=200)
            
        tags = TagSerializerPublic(Tag.public.all(), many=True).data
        cache.set("all_tags", tags, get_product_cache_timeout())
        return Response(get_response_schema_1(
            data=tags,
            status=200,
            message="Tags retrieved successfully"
        ), status=200)

class ProductListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    ALLOWED_FILTERS = {"category", "is_popular", "region", "is_featured", "tags", "product_type", "is_available", "is_topup"}
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
            extra=f"pmin={price_min}&pmax={price_max}&ord={ordering}"
        )

        data = cache.get(cache_key)

        if data:
            return Response(get_response_schema_1(
                data=data,
                status=200,
                message="Products retrieved successfully (cached)"
            ), status=200)

        queryset = Product.public.annotate(
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

        serializer = ProductListSerializer(page, many=True)
        data = paginator.get_paginated_response(serializer.data).data

        cache.set(cache_key, data, get_product_cache_timeout())

        return Response(get_response_schema_1(
            data=data,
            status=200,
            message="Products retrieved successfully"
        ), status=200)

class ProductDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, _request, slug):
        try:
            data = cache.get(get_product_cache_key(slug))
            if data:
                return Response(get_response_schema_1(
                    data=data,
                    status=200,
                    message="Product retrieved successfully (cached)"
                ), status=200)
                
            product = Product.public.prefetch_related('images', 'topup__packages').get(slug=slug)
            serializer = ProductDetailSerializerPublic(product)
            
            # Cache the product details for future requests
            cache_key = get_product_cache_key(slug)
            cache.set(cache_key, serializer.data, get_product_cache_timeout())
            
            return Response(get_response_schema_1(
                data=serializer.data,
                status=200,
                message="Product retrieved successfully"    
            ), status=200)
        except Product.DoesNotExist:
            return Response(get_response_schema_1(data=None, message="Product not found", status=404), status=404)