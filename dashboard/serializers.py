"""
dashboard/serializers.py
========================
Unified write serializers for atomic product creation and full update.

Payload structure (multipart/form-data):
  ┌─ Basic product fields (name, product_type, price, …)
  ├─ images              → list via images[0][image], images[0][is_main] …
  ├─ attributes          → list via attributes[0][name], attributes[0][value] …
  ├─ codes               → JSON string "["CODE1","CODE2"]"  (non-topup only)
  └─ topup section  (only when product_type == "topup")
       ├─ topup_logo      → image file
       ├─ fields[0][...] → TopUpField rows
       └─ packages[0][...], packages[0][codes] → TopUpPackage + their codes
"""

from __future__ import annotations

import json
import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from rest_framework import serializers

from catalog.models import Category, Product, ProductAttribute, ProductImage, Tag
from catalog.utils.choices import ProductType, StockMode
from codes.models import FulfillmentCode
from topup.models import TopUpField, TopUpFieldHelp, TopUpGame, TopUpPackage
from topup.utils.choices import FieldTypes

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Small write serializers (used for nested validation only)
# ─────────────────────────────────────────────────────────────────────────────


class _ImageWriteSerializer(serializers.Serializer):
    image = serializers.ImageField()
    is_main = serializers.BooleanField(default=False)


class _AttributeWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    value = serializers.CharField(max_length=255)


class _FieldHelpWriteSerializer(serializers.Serializer):
    description = serializers.CharField(allow_blank=True, required=False)
    image = serializers.ImageField(required=False)


class _TopUpFieldWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    placeholder = serializers.CharField(
        max_length=200, allow_blank=True, required=False
    )
    key = serializers.SlugField()
    field_type = serializers.ChoiceField(
        choices=FieldTypes.choices, default=FieldTypes.Text
    )
    is_required = serializers.BooleanField(default=True)
    order = serializers.IntegerField(default=0, min_value=0)
    min_input_length = serializers.IntegerField(default=1, min_value=1)
    helps = _FieldHelpWriteSerializer(many=True, required=False)


class _TopUpPackageWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    amount = serializers.CharField(max_length=100)
    price = serializers.DecimalField(max_digits=15, decimal_places=4)
    image = serializers.ImageField(required=False)
    is_active = serializers.BooleanField(default=True)
    is_popular = serializers.BooleanField(default=False)
    order = serializers.IntegerField(default=0, min_value=0)
    stock_mode = serializers.ChoiceField(choices=StockMode.choices)
    manual_fulfillment_time = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )
    # codes can be a JSON-encoded string (multipart) or a list (standard JSON)
    codes = serializers.JSONField(required=False, allow_null=True)

    def validate_codes(self, value):
        if not value:
            return []
        
        if isinstance(value, list):
            parsed = value
        else:
            try:
                parsed = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                raise serializers.ValidationError(
                    "codes must be a valid JSON array of strings."
                )
        if not isinstance(parsed, list):
            raise serializers.ValidationError("codes must be a JSON array.")
        cleaned = []
        for i, c in enumerate(parsed):
            # If it's a dict like {"code": "xyz"}, extract the string
            if isinstance(c, dict) and "code" in c:
                c = c["code"]
            
            if not isinstance(c, str):
                raise serializers.ValidationError(
                    f"codes[{i}] must be a string or an object with a 'code' field."
                )
            c = c.strip()
            if c:
                cleaned.append(c)
        return cleaned

    def validate(self, attrs):
        stock_mode = attrs.get("stock_mode")
        if stock_mode == StockMode.AUTOMATIC:
            # Automatic delivery → instant fulfillment, no wait time needed
            attrs["manual_fulfillment_time"] = 0
        elif stock_mode == StockMode.MANUAL:
            mft = attrs.get("manual_fulfillment_time")
            if not mft or mft <= 0:
                raise serializers.ValidationError(
                    {
                        "manual_fulfillment_time": (
                            "Required and must be greater than 0 when stock_mode is 'manual'."
                        )
                    }
                )
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# Small update serializers (used for nested validation in full-update)
# ─────────────────────────────────────────────────────────────────────────────

class _ImageUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)
    is_main = serializers.BooleanField(default=False)

class _AttributeUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    name = serializers.CharField(max_length=100)
    value = serializers.CharField(max_length=255)

class _FieldHelpUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(allow_blank=True, required=False)
    image = serializers.ImageField(required=False, allow_null=True)

class _TopUpFieldUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    title = serializers.CharField(max_length=200)
    placeholder = serializers.CharField(
        max_length=200, allow_blank=True, required=False
    )
    key = serializers.SlugField()
    field_type = serializers.ChoiceField(
        choices=FieldTypes.choices, default=FieldTypes.Text
    )
    is_required = serializers.BooleanField(default=True)
    order = serializers.IntegerField(default=0, min_value=0)
    min_input_length = serializers.IntegerField(default=1, min_value=1)
    helps = _FieldHelpUpdateSerializer(many=True, required=False)


class _TopUpPackageUpdateSerializer(_TopUpPackageWriteSerializer):
    id = serializers.IntegerField(required=False, allow_null=True)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers for parsing multipart/form-data indexed arrays
# ─────────────────────────────────────────────────────────────────────────────


def _extract_indexed_data(source_dict, prefix: str) -> list[dict]:
    """
    Extract indexed multipart fields into a list of dicts.
    Also supports standard list data if already present (e.g. from JSON).
    """
    # 1. Check if it's already a list (standard JSON case)
    val = source_dict.get(prefix)
    if isinstance(val, list):
        return val

    result: dict[int, dict] = {}
    prefix_bracket = f"{prefix}["
    for key, value in source_dict.items():
        if not key.startswith(prefix_bracket):
            continue
        rest = key[len(prefix_bracket):]  # e.g. "0][image]"
        bracket_pos = rest.find("]")
        if bracket_pos == -1:
            continue
        try:
            idx = int(rest[:bracket_pos])
        except ValueError:
            continue
        field_part = rest[bracket_pos + 1:]  # e.g. "[image]"
        if not field_part.startswith("[") or not field_part.endswith("]"):
            continue
        field_name = field_part[1:-1]  # e.g. "image"
        result.setdefault(idx, {})[field_name] = value

    return [result[k] for k in sorted(result)]


def _extract_indexed_files(files_dict, source_dict, prefix: str) -> list[dict]:
    """
    Extract both multipart file uploads and regular fields for an indexed prefix.
    Also supports standard list data if already present.
    """
    # 1. Check if it's already a list in source_dict
    val = source_dict.get(prefix)
    if isinstance(val, list):
        return val

    from collections import defaultdict

    merged: dict[int, dict] = defaultdict(dict)
    prefix_bracket = f"{prefix}["

    for src in (source_dict, files_dict):
        for key, value in src.items():
            if not key.startswith(prefix_bracket):
                continue
            rest = key[len(prefix_bracket):]
            bracket_pos = rest.find("]")
            if bracket_pos == -1:
                continue
            try:
                idx = int(rest[:bracket_pos])
            except ValueError:
                continue
            field_part = rest[bracket_pos + 1:]
            if not field_part.startswith("[") or not field_part.endswith("]"):
                continue
            field_name = field_part[1:-1]
            merged[idx][field_name] = value

    return [merged[k] for k in sorted(merged)]


def _parse_json_list_field(data: dict, field_name: str) -> list[str]:
    """Parse a JSON-encoded list of strings from a multipart field."""
    raw = data.get(field_name, "")
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError
        return [str(x).strip() for x in parsed if str(x).strip()]
    except (json.JSONDecodeError, ValueError):
        raise serializers.ValidationError(
            {field_name: "Must be a valid JSON array of strings."}
        )

def _parse_json_int_list_field(data: dict, field_name: str) -> list[int]:
    """Parse a valid JSON array of integers from a multipart field."""
    raw = data.get(field_name, "")
    if not raw:
        return []
    if isinstance(raw, list):
        try:
            return [int(x) for x in raw if str(x).strip()]
        except ValueError:
            pass
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError
        return [int(x) for x in parsed if str(x).strip()]
    except (json.JSONDecodeError, ValueError, TypeError):
        raise serializers.ValidationError(
            {field_name: "Must be a valid JSON array of integers."}
        )

# ─────────────────────────────────────────────────────────────────────────────
# Main CREATE serializer
# ─────────────────────────────────────────────────────────────────────────────


class ProductCreateSerializer(serializers.Serializer):
    """
    Accepts all product data in one shot.
    Validates everything BEFORE touching the database, then saves atomically.
    """

    # ── Basic product fields ──────────────────────────────────────────────
    name = serializers.CharField(max_length=255)
    product_type = serializers.ChoiceField(choices=ProductType.choices)
    price = serializers.DecimalField(
        max_digits=15, decimal_places=4, required=False, allow_null=True
    )
    stock_mode = serializers.ChoiceField(choices=StockMode.choices)
    manual_fulfillment_time = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )
    short_description = serializers.CharField(
        max_length=500, required=False, allow_blank=True, allow_null=True
    )
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    info = serializers.JSONField(required=False, allow_null=True)
    logo = serializers.ImageField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)
    is_available = serializers.BooleanField(default=True)
    is_popular = serializers.BooleanField(default=False)

    # ── Relations ─────────────────────────────────────────────────────────
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        many=True,
        required=False,
        source="categories",
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )

    # ── Nested collections (validated manually from raw request data) ──────
    # These are NOT standard DRF fields; we handle them in validate().
    # They are declared here only to appear in error dicts when needed.

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._request = request

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, attrs):
        request = self._request
        if request is None:
            raise serializers.ValidationError(
                "Request context is required for this serializer."
            )

        errors = {}
        data = request.data
        files = request.FILES

        product_type = attrs.get("product_type")
        stock_mode = attrs.get("stock_mode")

        # ── manual_fulfillment_time consistency ───────────────────────────
        if stock_mode == StockMode.AUTOMATIC:
            # Automatic → instant delivery; store 0 to signal the fulfillment
            # engine that codes should be sent immediately via email/notification.
            attrs["manual_fulfillment_time"] = 0
        elif stock_mode == StockMode.MANUAL:
            mft = attrs.get("manual_fulfillment_time")
            if not mft or mft <= 0:
                errors["manual_fulfillment_time"] = (
                    "Required and must be greater than 0 when stock_mode is 'manual'."
                )

        # ── Images ────────────────────────────────────────────────────────
        raw_images = _extract_indexed_files(files, data, "images")
        validated_images = []
        img_errors = {}
        main_count = 0
        for i, img_data in enumerate(raw_images):
            s = _ImageWriteSerializer(data=img_data)
            if not s.is_valid():
                img_errors[i] = s.errors
            else:
                validated_images.append(s.validated_data)
                if s.validated_data.get("is_main"):
                    main_count += 1
        if img_errors:
            errors["images"] = img_errors
        if main_count > 1:
            errors.setdefault("images", {})["is_main"] = (
                "Only one image can be marked as main."
            )

        # ── Attributes ────────────────────────────────────────────────────
        raw_attrs = _extract_indexed_data(data, "attributes")
        validated_attrs = []
        attr_errors = {}
        for i, attr_data in enumerate(raw_attrs):
            s = _AttributeWriteSerializer(data=attr_data)
            if not s.is_valid():
                attr_errors[i] = s.errors
            else:
                validated_attrs.append(s.validated_data)
        if attr_errors:
            errors["attributes"] = attr_errors

        # ── Codes or TopUp ────────────────────────────────────────────────
        if product_type == ProductType.TOPUP:
            attrs, topup_errors = self._validate_topup(attrs, data, files)
            errors.update(topup_errors)
        else:
            # Regular codes (software / game / giftcard / console)
            try:
                product_codes = _parse_json_list_field(data, "codes")
            except serializers.ValidationError as e:
                errors.update(e.detail)
                product_codes = []
            attrs["_product_codes"] = product_codes

        if errors:
            raise serializers.ValidationError(errors)

        attrs["_validated_images"] = validated_images
        attrs["_validated_attrs"] = validated_attrs
        return attrs

    def _validate_topup(self, attrs, data, files):
        errors = {}

        topup_logo = files.get("topup_logo")  # optional

        # ── Fields ──────────────────────────────────────────────────────
        raw_fields = _extract_indexed_data(data, "fields")
        # Helps are nested inside each field as fields[0][helps][0][...]
        # We handle them separately via a unified merge with files
        validated_fields = []
        field_errors = {}
        field_keys_seen: set[str] = set()

        for i, fdata in enumerate(raw_fields):
            # Extract nested helps for this field
            if "helps" in fdata and isinstance(fdata["helps"], list):
                raw_helps = fdata["helps"]
            else:
                helps_prefix = f"fields[{i}][helps]"
                # Re-extract helps from data dict with this sub-prefix
                raw_helps = _extract_indexed_files(files, data, helps_prefix)
            fdata["helps"] = raw_helps or []

            s = _TopUpFieldWriteSerializer(data=fdata)
            if not s.is_valid():
                field_errors[i] = s.errors
            else:
                vd = s.validated_data
                if vd["key"] in field_keys_seen:
                    field_errors[i] = {
                        "key": f"Duplicate key '{vd['key']}' in fields."
                    }
                else:
                    field_keys_seen.add(vd["key"])
                    validated_fields.append(vd)

        if field_errors:
            errors["fields"] = field_errors

        # ── Packages ────────────────────────────────────────────────────
        raw_packages = _extract_indexed_files(files, data, "packages")
        validated_packages = []
        pkg_errors = {}

        for i, pdata in enumerate(raw_packages):
            s = _TopUpPackageWriteSerializer(data=pdata)
            if not s.is_valid():
                pkg_errors[i] = s.errors
            else:
                validated_packages.append(s.validated_data)

        if pkg_errors:
            errors["packages"] = pkg_errors

        attrs["_topup_logo"] = topup_logo
        attrs["_validated_fields"] = validated_fields
        attrs["_validated_packages"] = validated_packages
        return attrs, errors

    # ------------------------------------------------------------------
    # Save — runs inside a single transaction.atomic()
    # ------------------------------------------------------------------

    @transaction.atomic
    def create(self, validated_data):
        # Pop internal keys
        validated_images = validated_data.pop("_validated_images", [])
        validated_attrs = validated_data.pop("_validated_attrs", [])
        product_codes = validated_data.pop("_product_codes", [])
        topup_logo = validated_data.pop("_topup_logo", None)
        validated_fields = validated_data.pop("_validated_fields", [])
        validated_packages = validated_data.pop("_validated_packages", [])

        categories = validated_data.pop("categories", [])
        tags = validated_data.pop("tags", [])

        # 1. Create Product
        product = Product.objects.create(**validated_data)
        if categories:
            product.category.set(categories)
        if tags:
            product.tags.set(tags)

        # 2. Images
        if validated_images:
            ProductImage.objects.bulk_create(
                [
                    ProductImage(
                        product=product,
                        image=img["image"],
                        is_main=img.get("is_main", False),
                    )
                    for img in validated_images
                ]
            )

        # 3. Attributes
        if validated_attrs:
            ProductAttribute.objects.bulk_create(
                [
                    ProductAttribute(
                        product=product,
                        name=attr["name"],
                        value=attr["value"],
                    )
                    for attr in validated_attrs
                ]
            )

        # 4. Codes or TopUp
        if validated_data.get("product_type") == ProductType.TOPUP or (
            product.product_type == ProductType.TOPUP
        ):
            self._create_topup(
                product, topup_logo, validated_fields, validated_packages
            )
        else:
            if product_codes:
                product_ct = ContentType.objects.get_for_model(Product)
                FulfillmentCode.objects.bulk_create(
                    [
                        FulfillmentCode(
                            code=c,
                            content_type=product_ct,
                            object_id=product.pk,
                        )
                        for c in product_codes
                    ]
                )

        logger.info(
            "Atomic product create succeeded: slug=%s type=%s",
            product.slug,
            product.product_type,
        )
        return product

    @staticmethod
    def _create_topup(product, topup_logo, validated_fields, validated_packages):
        game_kwargs = {"product": product}
        if topup_logo:
            game_kwargs["logo"] = topup_logo
        game = TopUpGame.objects.create(**game_kwargs)

        # Fields + their helps
        for fdata in validated_fields:
            helps_data = fdata.pop("helps", [])
            field_obj = TopUpField.objects.create(game=game, **fdata)
            if helps_data:
                TopUpFieldHelp.objects.bulk_create(
                    [
                        TopUpFieldHelp(
                            field=field_obj,
                            description=h.get("description", ""),
                            image=h.get("image"),
                        )
                        for h in helps_data
                    ]
                )

        # Packages + their codes
        pkg_ct = ContentType.objects.get_for_model(TopUpPackage)
        for pdata in validated_packages:
            pkg_codes = pdata.pop("codes", [])
            pkg_obj = TopUpPackage.objects.create(game=game, **pdata)
            if pkg_codes:
                FulfillmentCode.objects.bulk_create(
                    [
                        FulfillmentCode(
                            code=c,
                            content_type=pkg_ct,
                            object_id=pkg_obj.pk,
                        )
                        for c in pkg_codes
                    ]
                )


# ─────────────────────────────────────────────────────────────────────────────
# Main FULL-UPDATE serializer
# ─────────────────────────────────────────────────────────────────────────────


class ProductFullUpdateSerializer(serializers.Serializer):
    """
    Full update for an existing product.

    Strategy:
      - Basic fields    → partial update (only provided fields change)
      - images          → REPLACE (old images deleted, new ones created)
      - attributes      → REPLACE (old deleted, new created)
      - codes (non-topup) → MERGE  (new codes added; existing untouched)
      - topup basic     → partial update on TopUpGame
      - topup fields    → UPSERT by key (add new, update existing, keep missing)
      - topup packages  → REPLACE (simplest safe strategy for admin panel)
    """

    # ── Basic product fields (all optional for partial) ───────────────────
    name = serializers.CharField(max_length=255, required=False)
    price = serializers.DecimalField(
        max_digits=15, decimal_places=4, required=False, allow_null=True
    )
    stock_mode = serializers.ChoiceField(
        choices=StockMode.choices, required=False
    )
    manual_fulfillment_time = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )
    short_description = serializers.CharField(
        max_length=500, required=False, allow_blank=True, allow_null=True
    )
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    info = serializers.JSONField(required=False, allow_null=True)
    logo = serializers.ImageField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
    is_available = serializers.BooleanField(required=False)
    is_popular = serializers.BooleanField(required=False)

    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        many=True,
        required=False,
        source="categories",
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._request = request

    def validate(self, attrs):
        request = self._request
        if request is None:
            raise serializers.ValidationError(
                "Request context is required for this serializer."
            )

        errors = {}
        data = request.data
        files = request.FILES

        product = self.instance
        # Use incoming value if provided, otherwise fall back to current
        stock_mode = attrs.get("stock_mode", product.stock_mode)

        if stock_mode == StockMode.AUTOMATIC:
            # Automatic → instant delivery; always enforce manual_fulfillment_time=0
            attrs["manual_fulfillment_time"] = 0
        elif stock_mode == StockMode.MANUAL:
            mft = attrs.get(
                "manual_fulfillment_time", product.manual_fulfillment_time
            )
            if not mft or mft <= 0:
                errors["manual_fulfillment_time"] = (
                    "Required and must be greater than 0 when stock_mode is 'manual'."
                )

        # ── Images ────────────────────────────────────────────────────────
        raw_images = _extract_indexed_files(files, data, "images")
        validated_images = []
        img_errors = {}
        main_count = 0
        for i, img_data in enumerate(raw_images):
            s = _ImageUpdateSerializer(data=img_data)
            if not s.is_valid():
                img_errors[i] = s.errors
            else:
                validated_images.append(s.validated_data)
                if s.validated_data.get("is_main"):
                    main_count += 1
        if img_errors:
            errors["images"] = img_errors
        if main_count > 1:
            errors.setdefault("images", {})["is_main"] = (
                "Only one image can be marked as main."
            )

        # ── Attributes ────────────────────────────────────────────────────
        raw_attrs = _extract_indexed_data(data, "attributes")
        validated_attrs = []
        attr_errors = {}
        for i, attr_data in enumerate(raw_attrs):
            s = _AttributeUpdateSerializer(data=attr_data)
            if not s.is_valid():
                attr_errors[i] = s.errors
            else:
                validated_attrs.append(s.validated_data)
        if attr_errors:
            errors["attributes"] = attr_errors

        # ── Codes or TopUp ────────────────────────────────────────────────
        if product.product_type == ProductType.TOPUP:
            attrs, topup_errors = self._validate_topup_update(
                attrs, data, files, product
            )
            errors.update(topup_errors)
        else:
            try:
                product_codes = _parse_json_list_field(data, "codes")
            except serializers.ValidationError as e:
                errors.update(e.detail)
                product_codes = []
            attrs["_product_codes"] = product_codes
            
        try:
            attrs["_deleted_images"] = _parse_json_int_list_field(data, "deleted_images")
            attrs["_deleted_attributes"] = _parse_json_int_list_field(data, "deleted_attributes")
            attrs["_deleted_fields"] = _parse_json_int_list_field(data, "deleted_fields")
            attrs["_deleted_packages"] = _parse_json_int_list_field(data, "deleted_packages")
        except serializers.ValidationError as e:
            errors.update(e.detail)
            
        try:
            attrs["_deleted_codes"] = _parse_json_list_field(data, "deleted_codes")
        except serializers.ValidationError as e:
            errors.update(e.detail)

        if errors:
            raise serializers.ValidationError(errors)

        attrs["_validated_images"] = validated_images
        attrs["_validated_attrs"] = validated_attrs
        return attrs

    def _validate_topup_update(self, attrs, data, files, product):
        errors = {}

        topup_logo = files.get("topup_logo")

        # Fields
        raw_fields = _extract_indexed_data(data, "fields")
        validated_fields = []
        field_errors = {}
        field_keys_seen: set[str] = set()

        for i, fdata in enumerate(raw_fields):
            if "helps" in fdata and isinstance(fdata["helps"], list):
                raw_helps = fdata["helps"]
            else:
                helps_prefix = f"fields[{i}][helps]"
                raw_helps = _extract_indexed_files(files, data, helps_prefix)
            fdata["helps"] = raw_helps or []

            s = _TopUpFieldUpdateSerializer(data=fdata)
            if not s.is_valid():
                field_errors[i] = s.errors
            else:
                vd = s.validated_data
                if vd["key"] in field_keys_seen:
                    field_errors[i] = {
                        "key": f"Duplicate key '{vd['key']}' in fields."
                    }
                else:
                    field_keys_seen.add(vd["key"])
                    validated_fields.append(vd)

        if field_errors:
            errors["fields"] = field_errors

        # Packages
        raw_packages = _extract_indexed_files(files, data, "packages")
        validated_packages = []
        pkg_errors = {}

        for i, pdata in enumerate(raw_packages):
            s = _TopUpPackageUpdateSerializer(data=pdata)
            if not s.is_valid():
                pkg_errors[i] = s.errors
            else:
                validated_packages.append(s.validated_data)

        if pkg_errors:
            errors["packages"] = pkg_errors

        attrs["_topup_logo"] = topup_logo
        attrs["_validated_fields"] = validated_fields
        attrs["_validated_packages"] = validated_packages
        return attrs, errors

    @transaction.atomic
    def update(self, instance: Product, validated_data: dict):
        validated_images = validated_data.pop("_validated_images", [])
        validated_attrs = validated_data.pop("_validated_attrs", [])
        product_codes = validated_data.pop("_product_codes", [])
        topup_logo = validated_data.pop("_topup_logo", None)
        validated_fields = validated_data.pop("_validated_fields", [])
        validated_packages = validated_data.pop("_validated_packages", [])

        # 1. Update basic product fields
        for attr, value in validated_data.items():
            if attr not in ("categories", "tags"):
                setattr(instance, attr, value)
        instance.save()

        # Handle many-to-many fields safely for partial updates
        if "categories" in self.initial_data or "category" in self.initial_data:
            categories = validated_data.pop("categories", None)
            if categories is not None:
                instance.category.set(categories)
        else:
            validated_data.pop("categories", None)

        if "tags" in self.initial_data:
            tags = validated_data.pop("tags", None)
            if tags is not None:
                instance.tags.set(tags)
        else:
            validated_data.pop("tags", None)

        # 2. Images
        deleted_images = validated_data.pop("_deleted_images", [])
        if deleted_images:
            instance.images.filter(id__in=deleted_images).delete()

        for img in validated_images:
            img_id = img.get("id")
            if img_id:
                try:
                    existing_img = instance.images.get(id=img_id)
                    if img.get("image"):
                        existing_img.image = img["image"]
                    existing_img.is_main = img.get("is_main", False)
                    existing_img.save()
                except ProductImage.DoesNotExist:
                    pass
            else:
                if img.get("image"):
                    ProductImage.objects.create(
                        product=instance,
                        image=img["image"],
                        is_main=img.get("is_main", False),
                    )

        # 3. Attributes
        deleted_attributes = validated_data.pop("_deleted_attributes", [])
        if deleted_attributes:
            instance.attributes.filter(id__in=deleted_attributes).delete()
            
        for attr in validated_attrs:
            attr_id = attr.get("id")
            if attr_id:
                ProductAttribute.objects.filter(id=attr_id, product=instance).update(
                    name=attr["name"],
                    value=attr["value"]
                )
            else:
                ProductAttribute.objects.create(
                    product=instance,
                    name=attr["name"],
                    value=attr["value"]
                )

        # 4. Codes or TopUp
        if instance.product_type == ProductType.TOPUP:
            deleted_fields = validated_data.pop("_deleted_fields", [])
            deleted_packages = validated_data.pop("_deleted_packages", [])
            self._update_topup(
                instance, topup_logo, validated_fields, validated_packages, deleted_fields, deleted_packages
            )
        else:
            deleted_codes = validated_data.pop("_deleted_codes", [])
            if deleted_codes:
                product_ct = ContentType.objects.get_for_model(Product)
                FulfillmentCode.objects.filter(
                    content_type=product_ct,
                    object_id=instance.pk,
                    code__in=deleted_codes
                ).delete()
            # MERGE: only add new codes, never delete existing
            if product_codes:
                product_ct = ContentType.objects.get_for_model(Product)
                existing = set(
                    FulfillmentCode.objects.filter(
                        content_type=product_ct,
                        object_id=instance.pk,
                    ).values_list("code", flat=True)
                )
                new_codes = [c for c in product_codes if c not in existing]
                if new_codes:
                    FulfillmentCode.objects.bulk_create(
                        [
                            FulfillmentCode(
                                code=c,
                                content_type=product_ct,
                                object_id=instance.pk,
                            )
                            for c in new_codes
                        ]
                    )

        logger.info(
            "Atomic product full-update succeeded: slug=%s", instance.slug
        )
        if hasattr(instance, '_prefetched_objects_cache'):
            instance._prefetched_objects_cache.clear()
        return instance

    @staticmethod
    def _update_topup(product, topup_logo, validated_fields, validated_packages, deleted_fields, deleted_packages):
        # Get or create the game record
        game, _ = TopUpGame.objects.get_or_create(product=product)

        if topup_logo:
            game.logo = topup_logo
            game.save(update_fields=["logo", "updated_at"])

        if deleted_fields:
            TopUpField.objects.filter(game=game, id__in=deleted_fields).delete()
            
        # Fields → UPSERT by key
        if validated_fields:
            for fdata in validated_fields:
                helps_data = fdata.pop("helps", [])
                field_obj, created = TopUpField.objects.update_or_create(
                    game=game,
                    key=fdata["key"],
                    defaults={k: v for k, v in fdata.items() if k != "key"},
                )
                if helps_data:
                    # Replace helps for this field
                    field_obj.helps.all().delete()
                    TopUpFieldHelp.objects.bulk_create(
                        [
                            TopUpFieldHelp(
                                field=field_obj,
                                description=h.get("description", ""),
                                image=h.get("image"),
                            )
                            for h in helps_data
                        ]
                    )

        if deleted_packages:
            pkg_ct = ContentType.objects.get_for_model(TopUpPackage)
            # Find packages to delete
            pkgs_to_delete = game.packages.filter(id__in=deleted_packages)
            pkg_ids = list(pkgs_to_delete.values_list("pk", flat=True))
            if pkg_ids:
                FulfillmentCode.objects.filter(
                    content_type=pkg_ct,
                    object_id__in=pkg_ids,
                ).delete()
            pkgs_to_delete.delete()

        # Packages → Partial Update/Create
        if validated_packages:
            pkg_ct = ContentType.objects.get_for_model(TopUpPackage)
            for pdata in validated_packages:
                pkg_id = pdata.pop("id", None)
                pkg_codes = pdata.pop("codes", [])
                
                if pkg_id:
                    # Update
                    TopUpPackage.objects.filter(id=pkg_id, game=game).update(**pdata)
                    pkg_obj = TopUpPackage.objects.filter(id=pkg_id, game=game).first()
                else:
                    # Create
                    pkg_obj = TopUpPackage.objects.create(game=game, **pdata)
                
                if pkg_obj and pkg_codes:
                    # Merge codes for this package (non-destructive unless explicit delete mechanism later
                    existing = set(
                        FulfillmentCode.objects.filter(
                            content_type=pkg_ct,
                            object_id=pkg_obj.pk,
                        ).values_list("code", flat=True)
                    )
                    new_codes = [c for c in pkg_codes if c not in existing]
                    if new_codes:
                        FulfillmentCode.objects.bulk_create(
                            [
                                FulfillmentCode(
                                    code=c,
                                    content_type=pkg_ct,
                                    object_id=pkg_obj.pk,
                                )
                                for c in new_codes
                            ]
                        )
