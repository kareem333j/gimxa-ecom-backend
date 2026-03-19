from rest_framework.views import APIView
from rest_framework.response import Response

from topup.models import TopUpGame, TopUpField, TopUpPackage, TopUpFieldHelp
from topup.serializers import (
    TopUpGameAdminSerializer,
    TopUpFieldAdminSerializer,
    TopUpGameCreateSerializer,
    TopUpPackageAdminSerializer,
    TopUpFieldHelpSerializer,
    TopUpGameReadOnlyAdminSerializer
)
from permissions.custom import AdminPermission
from users_auth.authentication import CookieJWTAuthentication
from core.response_schema import get_response_schema_1
from django.core.cache import cache
from cache.utils import (
    get_topup_cache_timeout, 
    get_topup_game_cache_key, 
    get_topup_game_list_admin_cache_key, 
    get_topup_game_list_public_cache_key,
    get_topup_package_list_cache_page_key,
    get_packages_cache_timeout,
    get_topup_game_list_search_cache_key,
    format_filter_value
)
from core.pagination import DynamicPageNumberPagination
from django.db.models import Min



def delete_all_caches(product_slug):
    cache.delete(get_topup_game_cache_key(product_slug, is_admin=True))
    cache.delete(get_topup_game_cache_key(product_slug))
    cache.delete(get_topup_game_list_admin_cache_key())
    cache.delete(get_topup_game_list_public_cache_key())

class TopUpGameListAdminView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]
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

        cache_key = get_topup_game_list_search_cache_key(
            page_number=page_number,
            page_size=page_size,
            search_query=search_query,
            filter_params=','.join([f"{k}={v}" for k, v in filter_dict.items()]) if filter_dict else None,
            is_admin=True,
            extra=f"pmin={price_min}&pmax={price_max}&ord={ordering}"
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

        queryset = TopUpGame.objects.select_related("product").prefetch_related("fields", "packages").annotate(
            min_pkg_price=Min('packages__price')
        )
        if filter_dict:
            queryset = queryset.filter(**filter_dict)
        if search_query:
            queryset = queryset.filter(product__name__icontains=search_query)

        if price_min:
            try:
                queryset = queryset.filter(min_pkg_price__gte=float(price_min))
            except ValueError:
                return Response(get_response_schema_1(
                    message="Invalid price_min value", status=400
                ), status=400)

        if price_max:
            try:
                queryset = queryset.filter(min_pkg_price__lte=float(price_max))
            except ValueError:
                return Response(get_response_schema_1(
                    message="Invalid price_max value", status=400
                ), status=400)

        if ordering:
            queryset = queryset.order_by('-min_pkg_price' if ordering == '-price' else 'min_pkg_price')

        page = paginator.paginate_queryset(queryset, request)
        serializer = TopUpGameReadOnlyAdminSerializer(page, many=True)
        data = paginator.get_paginated_response(serializer.data).data
        cache.set(cache_key, data, get_topup_cache_timeout())

        return Response(get_response_schema_1(
            data=data,
            status=200,
            message="TopUp games retrieved successfully"
        ))

    def post(self, request):
        serializer = TopUpGameCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        game = serializer.save()
        
        cache.delete(get_topup_game_list_admin_cache_key())
        cache.delete(get_topup_game_list_public_cache_key())

        return Response(get_response_schema_1(
            message="TopUp created successfully",
            data=TopUpGameAdminSerializer(game).data,
            status=201
        ))
    

class TopUpGameDetailAdminView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, _request, product_slug):
        cache_key = get_topup_game_cache_key(product_slug, is_admin=True)
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(
                get_response_schema_1(
                    data=cached_data,
                    status=200,
                    message="TopUp game retrieved successfully"
                ),
                status=200
            )

        try:
            game = TopUpGame.objects.prefetch_related(
                "fields__helps",
                "packages",
            ).get(product__slug=product_slug)
        except TopUpGame.DoesNotExist:
            return Response(
                get_response_schema_1(error="TopUp game not found", status=404),
                status=404
            )

        serializer = TopUpGameAdminSerializer(game)
                    
        cache.set(cache_key, serializer.data, get_topup_cache_timeout())

        return Response(
            get_response_schema_1(
                data=serializer.data,
                status=200,
                message="TopUp game retrieved successfully"
            ),
            status=200
        )
    
    def put(self, request, product_slug):
        try:
            game = TopUpGame.objects.get(product__slug=product_slug)
        except TopUpGame.DoesNotExist:
            return Response(
                get_response_schema_1(error="TopUp game not found", status=404),
                status=404
            )

        serializer = TopUpGameAdminSerializer(game, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        delete_all_caches(product_slug)

        return Response(
            get_response_schema_1(
                data=serializer.data,
                status=200,
                message="TopUp game updated successfully"
            ),
            status=200
        )
        
    def delete(self, _request, product_slug):
        try:
            topup = TopUpGame.objects.get(product__slug=product_slug)
        except TopUpGame.DoesNotExist:
            return Response(get_response_schema_1(error="TopUp not found", status=404), status=404)
        topup.delete()
        delete_all_caches(product_slug)
        return Response(get_response_schema_1(data=None, message="TopUp deleted successfully", status=204), status=204)

class TopUpFieldAdminListView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request):
        is_many = isinstance(request.data, list)
        serializer = TopUpFieldAdminSerializer(data=request.data, many=is_many)
        serializer.is_valid(raise_exception=True)
        fields = serializer.save()

        first_field = fields[0] if is_many else fields
        product_slug = first_field.game.product.slug

        delete_all_caches(product_slug)
        
        return Response(get_response_schema_1(
            data=TopUpFieldAdminSerializer(fields, many=is_many).data,
            status=201
        ), status=201)

    def delete(self, request):
        if not isinstance(request.data, list) or not request.data:
            return Response(
                get_response_schema_1(
                    message="Field IDs list is required",
                    status=400
                ),
                status=400
            )

        fields_ids = request.data

        fields = TopUpField.objects.filter(pk__in=fields_ids)

        if not fields.exists():
            return Response(
                get_response_schema_1(
                    message="TopUp fields not found",
                    status=404
                ),
                status=404
            )

        product_slugs = set(f.game.product.slug for f in fields)

        fields.delete()

        for slug in product_slugs:
            cache.delete(get_topup_game_cache_key(slug, is_admin=True))
            cache.delete(get_topup_game_cache_key(slug))

        cache.delete(get_topup_game_list_admin_cache_key())
        cache.delete(get_topup_game_list_public_cache_key())

        return Response(
            get_response_schema_1(
                data=None,
                message="TopUp fields deleted successfully",
                status=204
            ),
            status=204
        )

class TopUpFieldAdminDetailView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def put(self, request, pk):
        if not pk:
            return Response(get_response_schema_1(error="TopUp field not found", status=404), status=404)
        try:
            field = TopUpField.objects.get(pk=pk)
        except TopUpField.DoesNotExist:
            return Response(get_response_schema_1(error="TopUp field not found", status=404), status=404)
        serializer = TopUpFieldAdminSerializer(field, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        product_slug = field.game.product.slug
        delete_all_caches(product_slug)

        return Response(get_response_schema_1(data=serializer.data, status=200), status=200)

    def delete(self, _request, pk):
        try:
            field = TopUpField.objects.get(pk=pk)
        except TopUpField.DoesNotExist:
            return Response(get_response_schema_1(error="TopUp field not found", status=404), status=404)
        field.delete()
        product_slug = field.game.product.slug
        delete_all_caches(product_slug)
        
        return Response(get_response_schema_1(data=None, message="TopUp field deleted successfully", status=204), status=204)

class TopUpFieldHelpAdminView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request):
        serializer = TopUpFieldHelpSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(get_response_schema_1(message=serializer.errors, status=400), status=400)
        help = serializer.save()
        
        delete_all_caches(help.field.game.product.slug)
        
        return Response(get_response_schema_1(data=serializer.data, message="TopUp field help created successfully", status=201), status=201)

class TopUpFieldHelpAdminDetailView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def put(self, request, pk):
        try:
            help = TopUpFieldHelp.objects.get(pk=pk)
        except TopUpFieldHelp.DoesNotExist:
            return Response(get_response_schema_1(message="TopUp field help not found", status=404), status=404)
        serializer = TopUpFieldHelpSerializer(help, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        help = serializer.save()
        
        delete_all_caches(help.field.game.product.slug)
        
        return Response(get_response_schema_1(data=serializer.data, message="TopUp field help updated successfully", status=200), status=200)

    def delete(self, _request, pk):
        try:
            help = TopUpFieldHelp.objects.get(pk=pk)
        except TopUpFieldHelp.DoesNotExist:
            return Response(get_response_schema_1(message="TopUp field help not found", status=404), status=404)
        help.delete()
        product_slug = help.field.game.product.slug
        delete_all_caches(product_slug)
        
        return Response(get_response_schema_1(data=None, message="TopUp field help deleted successfully", status=204), status=204)

class TopUpPackageAdminView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]
    ORDERING_OPTIONS = ["price", "-price", "-is_popular"]

    def post(self, request):
        serializer = TopUpPackageAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        package = serializer.save()
        
        delete_all_caches(package.game.product.slug)

        return Response(get_response_schema_1(
            data=TopUpPackageAdminSerializer(package).data,
            status=201
        ))

class TopUpPackageListAdminView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]
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
            is_admin=True
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

        qs = TopUpPackage.objects.filter(game__product__slug=product_slug).order_by(ordering)
        page = paginator.paginate_queryset(qs, request)
        serializer = TopUpPackageAdminSerializer(page, many=True)
        data = paginator.get_paginated_response(serializer.data).data
        cache.set(cache_key, data, get_packages_cache_timeout())
        
        return Response(get_response_schema_1(
            data=data,
            message="TopUp packages retrieved successfully",
            status=200
        ))

class TopUpPackageDetailAdminView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def put(self, request, pk):
        package = TopUpPackage.objects.get(pk=pk)
        serializer = TopUpPackageAdminSerializer(package, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        delete_all_caches(package.game.product.slug)

        return Response(get_response_schema_1(data=serializer.data, message="TopUp package updated successfully", status=200))

    def delete(self, _request, pk):
        package = TopUpPackage.objects.get(pk=pk)
        package.delete()
        delete_all_caches(package.game.product.slug)
        return Response(get_response_schema_1(data=None, message="TopUp package deleted successfully", status=204), status=204)