from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from cache.utils import (
    get_topup_cache_timeout, 
    get_topup_game_cache_key, 
    get_topup_package_list_cache_page_key,
    get_packages_cache_timeout,
    get_topup_game_list_search_cache_key
)
from topup.models import TopUpGame
from topup.serializers import (
    TopUpGamePublicSerializer,
    TopUpValidateSerializer,
    TopUpGameDetailPublicSerializer,
    TopUpPackageSerializer
)
from core.response_schema import get_response_schema_1
from django.core.cache import cache
from topup.models import TopUpPackage
from core.pagination import DynamicPageNumberPagination


class TopUpGameListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        page_number = request.query_params.get('page', 1)
        search_query = request.query_params.get('search', None)
        
        paginator = DynamicPageNumberPagination()
        page_size = paginator.get_page_size(request)

        cache_key = get_topup_game_list_search_cache_key(
            page_number=page_number,
            page_size=page_size,
            search_query=search_query,
            is_admin=False
        )
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response(
                get_response_schema_1(
                    data=cached_data,
                    status=200,
                    message="TopUp games retrieved successfully (cached)"
                ),
                status=200
            )

        queryset = TopUpGame.objects.filter(is_active=True).select_related("product").prefetch_related("packages")
        if search_query:
            queryset = queryset.filter(product__name__icontains=search_query)
        
        page = paginator.paginate_queryset(queryset, request)
        serializer = TopUpGamePublicSerializer(page, many=True)
        data = paginator.get_paginated_response(serializer.data).data
        cache.set(cache_key, data, get_topup_cache_timeout())

        return Response(
            get_response_schema_1(
                data=data,
                status=200,
                message="TopUp games retrieved successfully"
            ),
            status=200
        )

class TopUpGameDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, _request, product_slug):
        cache_key = get_topup_game_cache_key(product_slug)
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(
                get_response_schema_1(
                    data=cached_data,
                    status=200,
                    message="TopUp game retrieved successfully (cached)"
                ),
                status=200
            )

        try:
            game = TopUpGame.objects.prefetch_related(
                "fields__helps",
                "packages"
            ).get(product__slug=product_slug, is_active=True)
        except TopUpGame.DoesNotExist:
            return Response(
                get_response_schema_1(error="TopUp game not found", status=404),
                status=404
            )

        serializer = TopUpGameDetailPublicSerializer(game)
                    
        cache.set(cache_key, serializer.data, get_topup_cache_timeout())

        return Response(
            get_response_schema_1(
                data=serializer.data,
                status=200,
                message="TopUp game retrieved successfully"
            ),
            status=200
        )


class TopUpPackageListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    ORDERING_OPTIONS = ["price", "-price", "-is_popular"]

    def get(self, request, product_slug):
        ordering = request.query_params.get("ordering", "")
        if ordering not in self.ORDERING_OPTIONS:
            ordering = "price"

        page_number = request.query_params.get('page', 1)
        paginator = DynamicPageNumberPagination()
        page_size = paginator.get_page_size(request)

        cache_key = get_topup_package_list_cache_page_key(
            page_number=page_number,
            page_size=page_size,
            ordering=ordering,
        )

        data = cache.get(cache_key)

        if data:
            return Response(
                get_response_schema_1(
                    data=data,
                    status=200,
                    message="TopUp packages retrieved successfully (cached)"
                ),
                status=200
            )

        qs = TopUpPackage.public.filter(game__product__slug=product_slug).order_by(ordering)
        page = paginator.paginate_queryset(qs, request)
        serializer = TopUpPackageSerializer(page, many=True)
        data = paginator.get_paginated_response(serializer.data).data
        cache.set(cache_key, data, get_packages_cache_timeout())
        
        return Response(get_response_schema_1(
            data=data,
            message="TopUp packages retrieved successfully",
            status=200
        ))


class TopUpValidateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = TopUpValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(
            get_response_schema_1(
                data={"valid": True},
                status=200,
                message="TopUp data is valid"
            ),
            status=200
        )
