from django.contrib.contenttypes.models import ContentType
from rest_framework.views import APIView
from rest_framework.response import Response

from catalog.models import Product
from catalog.utils.choices import ProductType
from codes.models import FulfillmentCode
from codes.serializers import FulfillmentCodeSerializer, PackageWithCodesSerializer, CodeSerializer
from core.response_schema import get_response_schema_1
from permissions.custom import AdminPermission
from topup.models import TopUpPackage
from users_auth.authentication import CookieJWTAuthentication


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _get_product_or_404(slug):
    """Return (product, error_response) — exactly one will be None."""
    product = Product.objects.filter(slug=slug).first()
    if not product:
        return None, Response(
            get_response_schema_1(404, message="Product not found"),
            status=404,
        )
    return product, None


def _get_owner_content_type_and_id(product, package_id=None):
    """
    Resolve the GenericFK owner based on product type.

    Returns:
        (content_type, object_id, error_response)
        error_response is None on success.
    """
    if product.product_type == ProductType.TOPUP:
        if not package_id:
            return None, None, Response(
                get_response_schema_1(
                    400,
                    message="package_id is required for topup products",
                ),
                status=400,
            )
        package = TopUpPackage.objects.filter(
            id=package_id, game__product=product
        ).first()
        if not package:
            return None, None, Response(
                get_response_schema_1(
                    404,
                    message="Package not found for this product",
                ),
                status=404,
            )
        ct = ContentType.objects.get_for_model(TopUpPackage)
        return ct, package.id, None
    else:
        ct = ContentType.objects.get_for_model(Product)
        return ct, product.id, None


def _parse_codes_textarea(raw_text):
    """
    Parse a newline-separated string of codes.
    Returns a deduplicated list of non-empty stripped strings preserving order.
    """
    seen = set()
    result = []
    for line in raw_text.splitlines():
        code = line.strip()
        if code and code not in seen:
            seen.add(code)
            result.append(code)
    return result


def _bulk_sync_codes(content_type, object_id, new_codes):
    """
    Compare new_codes (list of strings) against existing DB codes for the owner.

    Rules:
      - Codes in new_codes but not in DB  → create.
      - Codes in DB but not in new_codes  → delete (skip if is_used=True).
      - Codes in both                     → no-op.

    Returns dict: {added, deleted, skipped_used, total}
    """
    existing_qs = FulfillmentCode.objects.filter(
        content_type=content_type,
        object_id=object_id,
    )

    existing_map = {obj.code: obj for obj in existing_qs}
    new_set = set(new_codes)
    existing_set = set(existing_map.keys())

    to_add = new_set - existing_set
    to_remove_codes = existing_set - new_set

    # Bulk create – ignore_conflicts silently skips codes that violate the
    # unique constraint (e.g. race conditions or duplicates in the textarea).
    FulfillmentCode.objects.bulk_create(
        [
            FulfillmentCode(
                code=code,
                content_type=content_type,
                object_id=object_id,
            )
            for code in to_add
        ],
        ignore_conflicts=True,
    )

    # Delete unused, skip used
    skipped_used = 0
    to_delete_ids = []
    for code_str in to_remove_codes:
        obj = existing_map[code_str]
        if obj.is_used:
            skipped_used += 1
        else:
            to_delete_ids.append(obj.id)

    deleted_count = 0
    if to_delete_ids:
        deleted_count, _ = FulfillmentCode.objects.filter(
            id__in=to_delete_ids
        ).delete()

    total_after = FulfillmentCode.objects.filter(
        content_type=content_type,
        object_id=object_id,
    ).count()

    return {
        "added": len(to_add),
        "deleted": deleted_count,
        "skipped_used": skipped_used,
        "total": total_after,
    }


# ---------------------------------------------------------------------------
# Existing generic admin views (kept intact)
# ---------------------------------------------------------------------------

class AdminCodeListView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, _request):
        codes = FulfillmentCode.objects.all()
        serializer = CodeSerializer(codes, many=True)
        return Response(
            get_response_schema_1(200, serializer.data, "Codes fetched successfully"),
            status=200,
        )

    def post(self, request):
        serializer = CodeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                get_response_schema_1(201, serializer.data, "Code created successfully"),
                status=201,
            )
        return Response(
            get_response_schema_1(400, serializer.errors, "Invalid data"),
            status=400,
        )


class AdminCodeDetailView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, _request, code_id):
        code = FulfillmentCode.objects.filter(id=code_id).first()
        if not code:
            return Response(
                get_response_schema_1(404, message="Code not found"), status=404
            )
        serializer = CodeSerializer(code)
        return Response(
            get_response_schema_1(200, serializer.data, "Code fetched successfully"),
            status=200,
        )

    def patch(self, request, code_id):
        code = FulfillmentCode.objects.filter(id=code_id).first()
        if not code:
            return Response(
                get_response_schema_1(404, message="Code not found"), status=404
            )
        serializer = CodeSerializer(code, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                get_response_schema_1(200, serializer.data, "Code updated successfully"),
                status=200,
            )
        return Response(
            get_response_schema_1(400, serializer.errors, "Invalid data"),
            status=400,
        )

    def delete(self, _request, code_id):
        code = FulfillmentCode.objects.filter(id=code_id).first()
        if not code:
            return Response(
                get_response_schema_1(404, message="Code not found"), status=404
            )
        code.delete()
        return Response(
            get_response_schema_1(200, message="Code deleted successfully"),
            status=200,
        )


# ---------------------------------------------------------------------------
# New: product-scoped views by slug
# ---------------------------------------------------------------------------

class AdminProductCodesView(APIView):
    """
    GET  /admin/codes/product/<slug>/
        - Non-topup product     → all codes for that product.
        - Topup + ?package_id   → all codes for that package.
        - Topup + no package_id → all packages with their codes.

    PUT  /admin/codes/product/<slug>/
        Body: { "codes": "CODE1\\nCODE2\\nCODE3" }
        - Non-topup product     → bulk sync codes for the product.
        - Topup product         → package_id required in body, then sync.
        Returns a sync summary.
    """

    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------
    def get(self, request, slug):
        product, err = _get_product_or_404(slug)
        if err:
            return err

        # --- Topup product ---
        if product.product_type == ProductType.TOPUP:
            package_id = request.query_params.get("package_id")

            # Specific package requested
            if package_id:
                try:
                    package_id = int(package_id)
                except (ValueError, TypeError):
                    return Response(
                        get_response_schema_1(400, message="package_id must be a valid integer"),
                        status=400,
                    )

                package = TopUpPackage.objects.filter(
                    id=package_id, game__product=product
                ).first()
                if not package:
                    return Response(
                        get_response_schema_1(404, message="Package not found for this product"),
                        status=404,
                    )

                codes = package.codes.all().order_by("-created_at")
                serializer = FulfillmentCodeSerializer(codes, many=True)
                return Response(
                    get_response_schema_1(
                        200,
                        {
                            "package_id": package.id,
                            "package_name": package.name,
                            "total_codes": codes.count(),
                            "available_codes": codes.filter(is_used=False).count(),
                            "codes": serializer.data,
                        },
                        "Package codes fetched successfully",
                    ),
                    status=200,
                )

            # No package_id → return all packages with codes
            try:
                topup_game = product.topup
            except product.__class__.topup.RelatedObjectDoesNotExist:
                return Response(
                    get_response_schema_1(404, message="TopUp game not found for this product"),
                    status=404,
                )

            packages = TopUpPackage.objects.filter(game=topup_game).order_by("order", "-created_at")
            result = []
            for pkg in packages:
                pkg_codes = pkg.codes.all().order_by("-created_at")
                result.append({
                    "package_id": pkg.id,
                    "package_name": pkg.name,
                    "total_codes": pkg_codes.count(),
                    "available_codes": pkg_codes.filter(is_used=False).count(),
                    "codes": FulfillmentCodeSerializer(pkg_codes, many=True).data,
                })

            return Response(
                get_response_schema_1(200, result, "All packages with codes fetched successfully"),
                status=200,
            )

        # --- Non-topup product ---
        codes = product.codes.all().order_by("-created_at")
        serializer = FulfillmentCodeSerializer(codes, many=True)
        return Response(
            get_response_schema_1(
                200,
                {
                    "total_codes": codes.count(),
                    "available_codes": codes.filter(is_used=False).count(),
                    "codes": serializer.data,
                },
                "Product codes fetched successfully",
            ),
            status=200,
        )

    # ------------------------------------------------------------------
    # PUT – bulk textarea sync
    # ------------------------------------------------------------------
    def put(self, request, slug):
        product, err = _get_product_or_404(slug)
        if err:
            return err

        # Validate payload
        raw_codes = request.data.get("codes", "")
        if not isinstance(raw_codes, str):
            return Response(
                get_response_schema_1(400, message="'codes' must be a newline-separated string"),
                status=400,
            )

        package_id = request.data.get("package_id")

        # Resolve owner
        content_type, object_id, err = _get_owner_content_type_and_id(product, package_id)
        if err:
            return err

        # Parse, deduplicate
        parsed_codes = _parse_codes_textarea(raw_codes)

        # Sync
        summary = _bulk_sync_codes(content_type, object_id, parsed_codes)

        return Response(
            get_response_schema_1(200, summary, "Codes synced successfully"),
            status=200,
        )


class AdminProductCodeDetailView(APIView):
    """
    PATCH  /admin/codes/product/<slug>/<int:code_id>/  — update a single code value.
    DELETE /admin/codes/product/<slug>/<int:code_id>/  — delete a code (403 if used).
    """

    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def _get_code_for_product(self, slug, code_id):
        """
        Returns (code, error_response).
        Validates that the code belongs to this product (or one of its packages).
        """
        product, err = _get_product_or_404(slug)
        if err:
            return None, err

        code = FulfillmentCode.objects.filter(id=code_id).first()
        if not code:
            return None, Response(
                get_response_schema_1(404, message="Code not found"),
                status=404,
            )

        # Verify ownership: the code must belong to this product or to one of its packages
        if product.product_type == ProductType.TOPUP:
            package_ct = ContentType.objects.get_for_model(TopUpPackage)
            valid_package_ids = TopUpPackage.objects.filter(
                game__product=product
            ).values_list("id", flat=True)
            if not (
                code.content_type == package_ct
                and code.object_id in valid_package_ids
            ):
                return None, Response(
                    get_response_schema_1(404, message="Code not found for this product"),
                    status=404,
                )
        else:
            product_ct = ContentType.objects.get_for_model(Product)
            if not (code.content_type == product_ct and code.object_id == product.id):
                return None, Response(
                    get_response_schema_1(404, message="Code not found for this product"),
                    status=404,
                )

        return code, None

    def patch(self, request, slug, code_id):
        code, err = self._get_code_for_product(slug, code_id)
        if err:
            return err

        new_code_value = request.data.get("code")
        if not new_code_value or not isinstance(new_code_value, str):
            return Response(
                get_response_schema_1(400, message="'code' field is required and must be a string"),
                status=400,
            )

        new_code_value = new_code_value.strip()
        if not new_code_value:
            return Response(
                get_response_schema_1(400, message="'code' cannot be blank"),
                status=400,
            )

        # Uniqueness check (exclude self)
        if FulfillmentCode.objects.filter(code=new_code_value).exclude(id=code.id).exists():
            return Response(
                get_response_schema_1(409, message="A code with this value already exists"),
                status=409,
            )

        code.code = new_code_value
        code.save(update_fields=["code"])

        return Response(
            get_response_schema_1(200, FulfillmentCodeSerializer(code).data, "Code updated successfully"),
            status=200,
        )

    def delete(self, request, slug, code_id):
        code, err = self._get_code_for_product(slug, code_id)
        if err:
            return err

        if code.is_used:
            return Response(
                get_response_schema_1(
                    400,
                    message="Cannot delete a code that has already been used",
                ),
                status=400,
            )

        code.delete()
        return Response(
            get_response_schema_1(200, message="Code deleted successfully"),
            status=200,
        )
