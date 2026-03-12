"""
dashboard/views.py
==================
Admin-only views for unified atomic product operations.
"""

import logging

from django.core.cache import cache
from rest_framework.response import Response
from rest_framework.views import APIView

from cache.utils import (
    get_product_cache_key,
    get_topup_game_cache_key,
    get_topup_game_list_admin_cache_key,
    get_topup_game_list_public_cache_key,
)
from catalog.models import Product
from catalog.serializers import ProductDashboardAdminSerializer
from catalog.utils.choices import ProductType
from core.response_schema import get_response_schema_1
from permissions.custom import AdminPermission
from users_auth.authentication import CookieJWTAuthentication

from dashboard.serializers import ProductCreateSerializer, ProductFullUpdateSerializer

logger = logging.getLogger(__name__)


def _invalidate_product_caches(product: Product) -> None:
    """Clear all cache keys that may reference this product."""
    cache.delete(get_product_cache_key(product.slug))

    if product.product_type == ProductType.TOPUP:
        cache.delete(get_topup_game_cache_key(product.slug, is_admin=True))
        cache.delete(get_topup_game_cache_key(product.slug))
        cache.delete(get_topup_game_list_admin_cache_key())
        cache.delete(get_topup_game_list_public_cache_key())

    # Invalidate product list pages (pattern-based: delete matching keys if
    # using a cache backend that supports it, otherwise delete known keys)
    # Since Django's built-in cache doesn't support pattern delete,
    # we clear the admin and public list caches with known keys.
    from django.core.cache import cache as _cache
    # Clear all paginated list caches by pattern prefix (best-effort)
    # Works with Redis via django-redis; safe no-op with locmem cache.
    try:
        _cache.delete_pattern("product_list_cache_page_*")
        _cache.delete_pattern("product_admin_list_cache_page_*")
    except AttributeError:
        # Non-redis cache (e.g. LocMemCache) — skip pattern delete
        pass


class ProductCreateAdminView(APIView):
    """
    POST /api/v1/dashboard/admin/products/create/

    Accepts all product data (basic info, images, attributes, codes, topup data)
    in a single multipart/form-data request.
    All database operations run inside a single transaction.atomic() block —
    any failure causes a complete rollback with no partial data saved.

    Returns the full product representation on success (201).
    """

    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request):
        serializer = ProductCreateSerializer(data=request.data, request=request)

        if not serializer.is_valid():
            return Response(
                get_response_schema_1(
                    status=400,
                    message="Validation failed. No data was saved.",
                    errors=serializer.errors,
                ),
                status=400,
            )

        try:
            product = serializer.save()
        except Exception as exc:
            logger.exception("Unexpected error during atomic product create: %s", exc)
            return Response(
                get_response_schema_1(
                    status=500,
                    message="An unexpected error occurred. No data was saved.",
                ),
                status=500,
            )

        _invalidate_product_caches(product)

        return Response(
            get_response_schema_1(
                status=201,
                message="Product created successfully.",
                data=ProductDashboardAdminSerializer(product).data,
            ),
            status=201,
        )


class ProductFullUpdateAdminView(APIView):
    """
    PUT /api/v1/dashboard/admin/products/<slug>/full-update/

    Accepts any combination of product data for a full or partial update.
    All database operations run in a single transaction.atomic() block.

    Update strategies per section:
      - Basic fields   → partial (only provided fields are updated)
      - images         → REPLACE (old images deleted, new ones created)
      - attributes     → REPLACE (old deleted, new created)
      - codes (non-topup) → MERGE (new codes appended; existing untouched)
      - topup fields   → UPSERT by key (update existing, add new)
      - topup packages → REPLACE (send full desired list)

    Returns the full updated product representation on success (200).
    """

    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def put(self, request, slug):
        try:
            product = Product.objects.prefetch_related(
                "images", "attributes", "category", "tags"
            ).get(slug=slug)
        except Product.DoesNotExist:
            return Response(
                get_response_schema_1(status=404, message="Product not found."),
                status=404,
            )

        serializer = ProductFullUpdateSerializer(
            instance=product, data=request.data, request=request
        )

        if not serializer.is_valid():
            return Response(
                get_response_schema_1(
                    status=400,
                    message="Validation failed. No changes were saved.",
                    errors=serializer.errors,
                ),
                status=400,
            )

        try:
            product = serializer.save()
        except Exception as exc:
            logger.exception(
                "Unexpected error during atomic product full-update (slug=%s): %s",
                slug,
                exc,
            )
            return Response(
                get_response_schema_1(
                    status=500,
                    message="An unexpected error occurred. No changes were saved.",
                ),
                status=500,
            )

        _invalidate_product_caches(product)

        return Response(
            get_response_schema_1(
                status=200,
                message="Product updated successfully.",
                data=ProductDashboardAdminSerializer(product).data,
            ),
            status=200,
        )
