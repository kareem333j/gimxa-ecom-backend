import json
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from cart.utils.helpers import get_or_create_cart
from core.response_schema import get_response_schema_1
from coupons.models import Coupon
from coupons.serializers import ValidateCouponSerializer, ApplyCouponSerializer, CouponSerializer
from coupons.services.coupon_service import (
    validate_coupon,
    calculate_discount,
    get_coupon_summary,
    get_cookie_cart_items,
)
from users_auth.authentication import OptionalJWTAuthentication


class ValidateCouponView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def post(self, request):
        serializer = ValidateCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["code"]
        user = request.user if request.user.is_authenticated else None
        is_valid, message, coupon = validate_coupon(code, user)

        if not is_valid:
            return Response(
                get_response_schema_1({}, 400, message),
                status=400
            )

        if request.user.is_authenticated:
            cart = get_or_create_cart(request.user)
            cart_items = cart.items.select_related("product").prefetch_related("product__category").all()
        else:
            cookie_cart = request.COOKIES.get("cart")
            cookie_cart = json.loads(cookie_cart) if cookie_cart else {"items": []}
            cart_items = get_cookie_cart_items(cookie_cart["items"])

        discount_info = calculate_discount(coupon, cart_items)
        coupon_summary = get_coupon_summary(coupon)

        return Response(
            get_response_schema_1(
                {
                    "coupon": coupon_summary,
                    "discount": {
                        "total_discount": str(discount_info["total_discount"]),
                        "cart_subtotal": str(discount_info["cart_subtotal"]),
                        "cart_total_after_discount": str(max(discount_info["cart_total_after_discount"], Decimal("0.0000"))),
                        "applicable_items_count": discount_info["applicable_items_count"],
                    }
                },
                200,
                "coupon is valid"
            ),
            status=200
        )


class ApplyCouponView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def post(self, request):
        serializer = ApplyCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["code"]
        user = request.user if request.user.is_authenticated else None
        is_valid, message, coupon = validate_coupon(code, user)

        if not is_valid:
            return Response(
                get_response_schema_1({}, 400, message),
                status=400
            )

        if request.user.is_authenticated:
            cart = get_or_create_cart(request.user)
            cart.coupon = coupon
            cart.save()
            cart_items = list(cart.items.select_related("product").prefetch_related("product__category"))
        else:
            cookie_cart = request.COOKIES.get("cart")
            cookie_cart = json.loads(cookie_cart) if cookie_cart else {"items": []}
            cart_items = get_cookie_cart_items(cookie_cart["items"])

        if not cart_items:
            return Response(
                get_response_schema_1({}, 400, "cart is empty"),
                status=400
            )

        discount_info = calculate_discount(coupon, cart_items)

        if discount_info["total_discount"] == Decimal("0.0000"):
            return Response(
                get_response_schema_1(
                    {},
                    400,
                    "coupon is not applicable to any items in the cart"
                ),
                status=400
            )

        subtotal = sum(item.unit_price * item.quantity for item in cart_items)
        total_after_discount = subtotal - discount_info["total_discount"]

        coupon_summary = get_coupon_summary(coupon)

        response_data = {
            "coupon": coupon_summary,
            "subtotal": str(subtotal),
            "discount": str(discount_info["total_discount"]),
            "total_after_discount": str(max(total_after_discount, Decimal("0.0000"))),
            "applicable_items_count": discount_info["applicable_items_count"],
            "discount_breakdown": [
                {
                    "product_name": item["product_name"],
                    "discount": str(item["discount"]),
                }
                for item in discount_info["discount_breakdown"]
            ],
        }

        response = Response(
            get_response_schema_1(
                response_data,
                200,
                "coupon applied successfully"
            ),
            status=200
        )

        if not request.user.is_authenticated:
            cookie_cart = request.COOKIES.get("cart")
            cookie_cart = json.loads(cookie_cart) if cookie_cart else {"items": []}
            cookie_cart["coupon"] = coupon.code
            response.set_cookie("cart", json.dumps(cookie_cart), max_age=7 * 24 * 60 * 60)

        return response


class RemoveCouponView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def post(self, request):
        if request.user.is_authenticated:
            cart = get_or_create_cart(request.user)
            cart.coupon = None
            cart.save()
            return Response(
                get_response_schema_1({}, 200, "coupon removed successfully"),
                status=200
            )
        
        # For non-authenticated users, remove the coupon from the cookie cart.
        response = Response(
            get_response_schema_1({}, 200, "coupon removed successfully"),
            status=200
        )
        cookie_cart = request.COOKIES.get("cart")
        if cookie_cart:
            try:
                cookie_cart = json.loads(cookie_cart)
                if "coupon" in cookie_cart:
                    del cookie_cart["coupon"]
                    response.set_cookie("cart", json.dumps(cookie_cart), max_age=7 * 24 * 60 * 60)
            except json.JSONDecodeError:
                pass

        return response


class CouponDetailsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def get(self, request, code):
        coupon = Coupon.objects.filter(code__iexact=code, is_active=True).first()

        if not coupon:
            return Response(
                get_response_schema_1({}, 404, "coupon not found"),
                status=404
            )

        coupon_summary = get_coupon_summary(coupon)

        return Response(
            get_response_schema_1(coupon_summary, 200, "coupon details retrieved successfully"),
            status=200
        )
