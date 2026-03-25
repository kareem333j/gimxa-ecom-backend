from decimal import Decimal
from cart.models import Cart
from catalog.models import Product
from topup.models import TopUpPackage
import json
from cart.models import CartItem
from payments.services.currency_service import CurrencyService, get_user_currency

def get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart

def build_cookie_cart_response(items, coupon_code=None, request=None):
    response_items = []
    subtotal = Decimal("0.0000")

    currency = get_user_currency(request)
    service = CurrencyService()

    for item in items:
        try:
            product = Product.public.get(slug=item["product"]["slug"])
        except Product.DoesNotExist:
            continue


        if item["product"]["is_topup"]:
            try:
                package = TopUpPackage.public.get(id=item["topup_package"])
            except TopUpPackage.DoesNotExist:
                continue
            unit_price = package.price
        else:
            unit_price = product.price
            item.pop("topup_package", None)
            item.pop("topup_data", None)
            item.pop("topup_hash", None)

        total_price = unit_price * item["quantity"]
        subtotal += total_price

        unit_price_conv = str(round(service.convert(unit_price, currency), 2))
        total_price_conv = str(round(service.convert(total_price, currency), 2))

        response_items.append({
            **item,
            "unit_price": unit_price_conv,
            "total_price": total_price_conv,
        })

    # Coupon and Discount Calculation
    coupon_data = None
    discount = Decimal("0.0000")
    total_after_discount = subtotal

    if coupon_code:
        from coupons.services.coupon_service import validate_coupon, calculate_discount, get_coupon_summary, get_cookie_cart_items
        is_valid, message, coupon = validate_coupon(coupon_code)
        if is_valid and coupon:
            cart_items = get_cookie_cart_items(items)
            discount_info = calculate_discount(coupon, cart_items)
            discount = discount_info["total_discount"]
            total_after_discount = max(subtotal - discount, Decimal("0.0000"))
            coupon_data = get_coupon_summary(coupon, currency=currency)

    subtotal_conv = str(round(service.convert(subtotal, currency), 2))
    discount_conv = str(round(service.convert(discount, currency), 2))
    total_after_discount_conv = str(round(service.convert(total_after_discount, currency), 2))

    return {
        "id": None,
        "items": response_items,
        "coupon": coupon_data,
        "subtotal": subtotal_conv,
        "discount": discount_conv,
        "total_after_discount": total_after_discount_conv,
        "currency": currency,
    }

import hashlib

def make_topup_hash(data):
    normalized = json.dumps(data, sort_keys=True)
    return hashlib.md5(normalized.encode()).hexdigest()


# merge cookie cart to db
from rest_framework.response import Response

def merge_cookie_cart_to_db(request, response, user):
    """
    Move cart from cookies to DB for the authenticated user.
    """
    cookie_cart = request.COOKIES.get("cart")
    if not cookie_cart:
        return  # nothing to merge

    try:
        cookie_cart = json.loads(cookie_cart)
    except json.JSONDecodeError:
        return

    if not cookie_cart.get("items"):
        return

    cart = get_or_create_cart(user)

    for item in cookie_cart["items"]:
        product_slug = item["product"]["slug"]
        quantity = item.get("quantity", 1)
        is_topup = item["product"].get("is_topup", False)
        topup_package_id = item.get("topup_package")
        topup_data = item.get("topup_data", {})
        topup_hash = make_topup_hash(topup_data) if is_topup else None

        # get product instance
        from catalog.models import Product
        try:
            product = Product.objects.get(slug=product_slug)
        except Product.DoesNotExist:
            continue

        topup_package = None
        unit_price = product.price

        if is_topup and topup_package_id:
            try:
                topup_package = TopUpPackage.public.get(
                    id=topup_package_id,
                    game__product=product
                )
                unit_price = topup_package.price
            except TopUpPackage.DoesNotExist:
                continue

        # check if same item exists
        db_item = CartItem.objects.filter(
            cart=cart,
            product=product,
            topup_package=topup_package,
            topup_hash=topup_hash,
        ).first()

        if db_item:
            db_item.quantity += quantity
            db_item.unit_price = unit_price
            if is_topup:
                db_item.topup_data = topup_data
            db_item.save()
        else:
            CartItem.objects.create(
                cart=cart,
                product=product,
                topup_package=topup_package,
                topup_hash=topup_hash,
                topup_data=topup_data if is_topup else None,
                quantity=quantity,
                unit_price=unit_price,
                is_topup=is_topup,
            )
            
    # merge coupon
    coupon_code = cookie_cart.get("coupon")
    if coupon_code and not cart.coupon:
        from coupons.models import Coupon
        coupon = Coupon.objects.filter(code__iexact=coupon_code, is_active=True).first()
        if coupon:
            cart.coupon = coupon
            cart.save()

    # clear the cookie after merging
    response.delete_cookie("cart")