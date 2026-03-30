from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from cache.utils import (
    get_topup_cache_timeout, 
    get_topup_game_cache_key, 
    get_topup_package_list_cache_page_key,
    get_packages_cache_timeout,
    get_topup_game_list_search_cache_key,
    format_filter_value
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
from django.db.models import Min
from users_auth.authentication import OptionalJWTAuthentication
from payments.services.currency_service import get_user_currency
from payments.services.currency_service import CurrencyService


class TopUpGameListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]
    ALLOWED_FILTERS = ["is_popular", "is_featured"]
    ALLOWED_ORDERING = {"price", "-price"}

    def get(self, request):
        page_number = request.query_params.get('page', 1)
        search_query = request.query_params.get('search', None)
        filter_params = request.query_params.get('filter', None)
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
                        filter_dict[f'product__{k}'] = format_filter_value(v)
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

        currency = get_user_currency(request)
        service = CurrencyService()

        cache_key = get_topup_game_list_search_cache_key(
            page_number=page_number,
            page_size=page_size,
            search_query=search_query,
            filter_params=','.join([f"{k}={v}" for k, v in filter_dict.items()]) if filter_dict else None,
            is_admin=False,
            extra=f"pmin={price_min}&pmax={price_max}&ord={ordering}&currency={currency}"
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

        queryset = TopUpGame.objects.filter(is_active=True).select_related("product").prefetch_related("packages").annotate(
            min_pkg_price=Min('packages__price')
        )
        if filter_dict:
            queryset = queryset.filter(**filter_dict)
        if search_query:
            queryset = queryset.filter(product__name__icontains=search_query)

        if price_min:
            try:
                # Convert price_min from user currency back to USD for DB filtering
                price_min_usd = float(service.convert(price_min, "USD", from_currency=currency))
                queryset = queryset.filter(min_pkg_price__gte=price_min_usd)
            except ValueError:
                return Response(get_response_schema_1(
                    message="Invalid price_min value", status=400
                ), status=400)

        if price_max:
            try:
                # Convert price_max from user currency back to USD for DB filtering
                price_max_usd = float(service.convert(price_max, "USD", from_currency=currency))
                queryset = queryset.filter(min_pkg_price__lte=price_max_usd)
            except ValueError:
                return Response(get_response_schema_1(
                    message="Invalid price_max value", status=400
                ), status=400)

        if ordering:
            queryset = queryset.order_by('-min_pkg_price' if ordering == '-price' else 'min_pkg_price')

        page = paginator.paginate_queryset(queryset, request)
        serializer = TopUpGamePublicSerializer(page, many=True, context={"request": request})
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
    authentication_classes = [OptionalJWTAuthentication]

    def get(self, request, product_slug):
        cache_key = get_topup_game_cache_key(product_slug) + f"&currency={get_user_currency(request)}"
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

        serializer = TopUpGameDetailPublicSerializer(game, context={"request": request})
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
    authentication_classes = [OptionalJWTAuthentication]
    ORDERING_OPTIONS = ["price", "-price", "-is_popular"]

    def get(self, request, product_slug):
        ordering = request.query_params.get("ordering", "")
        if ordering not in self.ORDERING_OPTIONS:
            ordering = "price"

        page_number = request.query_params.get('page', 1)
        paginator = DynamicPageNumberPagination()
        page_size = paginator.get_page_size(request)

        cache_key = get_topup_package_list_cache_page_key(
            product_slug=product_slug,
            page_number=page_number,
            page_size=page_size,
            ordering=ordering,
            currency=get_user_currency(request)
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
        serializer = TopUpPackageSerializer(page, many=True, context={"request": request})
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
