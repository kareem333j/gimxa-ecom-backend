from decimal import Decimal
from typing import Tuple, Optional, Dict
from django.db import transaction
from django.utils import timezone

from coupons.models import Coupon, CouponUsage
from coupons.utils.choices import CouponScope, DiscountType
from django.db.models import F


class CouponError(Exception):
    """Custom exception for coupon errors"""
    pass


class CookieCartItem:
    def __init__(self, product, quantity, unit_price, topup_package_id=None):
        self.product = product
        self.product_id = product.id
        self.quantity = quantity
        self.unit_price = unit_price
        self.topup_package_id = topup_package_id
        self.id = f"cookie_{product.slug}"


def get_cookie_cart_items(cookie_items: list) -> list:
    from catalog.models import Product
    from topup.models import TopUpPackage

    cart_items = []
    for item in cookie_items:
        try:
            product = Product.public.prefetch_related("category").get(
                slug=item['product']['slug']
            )
        except Product.DoesNotExist:
            continue

        if item.get("product", {}).get("is_topup") and item.get("topup_package"):
            try:
                package = TopUpPackage.public.get(
                    id=item["topup_package"]
                )
                unit_price = package.price
            except TopUpPackage.DoesNotExist:
                continue
        else:
            unit_price = product.price

        cart_items.append(CookieCartItem(
            product=product,
            quantity=item["quantity"],
            unit_price=unit_price,
            topup_package_id=item.get("topup_package"),
        ))
    return cart_items


def validate_coupon(code: str, user=None) -> Tuple[bool, str, Optional[Coupon]]:
    coupon = Coupon.objects.filter(code__iexact=code).first()
    
    if not coupon:
        return False, "coupon not found", None
    
    if not coupon.is_active:
        return False, "coupon is not active", None
    
    now = timezone.now()
    if coupon.start_at > now:
        return False, "coupon not started yet", None
    
    if coupon.end_at < now:
        return False, "coupon is expired", None
    
    if coupon.max_usage and coupon.used_count >= coupon.max_usage:
        return False, "coupon reached maximum usage", None
    
    if user and user.is_authenticated:
        already_used = CouponUsage.objects.filter(
            coupon=coupon,
            user=user
        ).exists()
        if already_used:
            return False, "you used this coupon before", None
    
    return True, "coupon is valid", coupon


def get_applicable_items(coupon: Coupon, cart_items) -> list:
    """
    Get items that the coupon applies to
    """
    if coupon.scope == CouponScope.GLOBAL:
        # applies to all items
        return list(cart_items)
    
    elif coupon.scope == CouponScope.PRODUCT:
        # applies to specific products only
        product_ids = coupon.product_discounts.values_list("product_id", flat=True)
        return [item for item in cart_items if item.product_id in product_ids]
    
    elif coupon.scope == CouponScope.CATEGORY:
        # applies to products from specific categories
        category_ids = set(coupon.category_discounts.values_list("category_id", flat=True))
        applicable = []
        for item in cart_items:
            # Get product categories
            product_categories = set(item.product.category.values_list("id", flat=True))
            if product_categories & category_ids:  # intersection
                applicable.append(item)
        return applicable

    elif coupon.scope == CouponScope.PACKAGE:
        # applies to specific topup packages only
        package_ids = coupon.package_discounts.values_list("package_id", flat=True)
        return [item for item in cart_items if item.topup_package_id in package_ids]
    
    return []


def calculate_item_discount(
    item,
    discount_type: str,
    discount_value: Decimal
) -> Decimal:
    """
    Calculate discount for a single item
    """
    item_total = item.unit_price * item.quantity
    
    if discount_type == DiscountType.PERCENT:
        discount = item_total * (discount_value / Decimal("100"))
    else:  # FIXED
        discount = min(discount_value * item.quantity, item_total)
    
    return discount.quantize(Decimal("0.0001"))


def calculate_discount(
    coupon: Coupon,
    cart_items,
    cart_subtotal: Decimal = None
) -> Dict:
    """
    Calculate total discount for the coupon on the cart
    Returns: {
        'total_discount': Decimal,
        'applicable_items_count': int,
        'discount_breakdown': [{'item_id': int, 'discount': Decimal}, ...]
    }
    """
    cart_subtotal = Decimal("0.0000")
    for item in cart_items:
        cart_subtotal += item.unit_price * item.quantity
    
    applicable_items = get_applicable_items(coupon, cart_items)
    
    if not applicable_items:
        return {
            "total_discount": Decimal("0.0000"),
            "applicable_items_count": 0,
            "discount_breakdown": [],
            "cart_subtotal": cart_subtotal,
            "cart_total_after_discount": cart_subtotal,
        }
    
    total_discount = Decimal("0.0000")
    discount_breakdown = []
    
    if coupon.scope == CouponScope.GLOBAL:
        # discount from the coupon itself
        discount_type = coupon.discount_type
        discount_value = coupon.discount_value
        
        for item in applicable_items:
            item_discount = calculate_item_discount(item, discount_type, discount_value)
            total_discount += item_discount
            discount_breakdown.append({
                "item_id": item.id,
                "product_name": item.product.name,
                "discount": item_discount,
            })
    
    elif coupon.scope == CouponScope.PRODUCT:
        # discount from CouponProduct for each product
        product_discounts = {
            pd.product_id: pd 
            for pd in coupon.product_discounts.all()
        }
        
        for item in applicable_items:
            pd = product_discounts.get(item.product_id)
            if pd:
                item_discount = calculate_item_discount(
                    item, pd.discount_type, pd.discount_value
                )
                total_discount += item_discount
                discount_breakdown.append({
                    "item_id": item.id,
                    "product_name": item.product.name,
                    "discount": item_discount,
                })
    
    elif coupon.scope == CouponScope.CATEGORY:
        # discount from CouponCategory for each category
        category_discounts = {
            cd.category_id: cd 
            for cd in coupon.category_discounts.all()
        }
        
        for item in applicable_items:
            # Get the best discount if product is in multiple categories
            product_categories = item.product.category.values_list("id", flat=True)
            best_discount = Decimal("0.0000")
            
            for cat_id in product_categories:
                cd = category_discounts.get(cat_id)
                if cd:
                    item_discount = calculate_item_discount(
                        item, cd.discount_type, cd.discount_value
                    )
                    if item_discount > best_discount:
                        best_discount = item_discount
            
            if best_discount > 0:
                total_discount += best_discount
                discount_breakdown.append({
                    "item_id": item.id,
                    "product_name": item.product.name,
                    "discount": best_discount,
                })

    elif coupon.scope == CouponScope.PACKAGE:
        # discount from CouponPackage for each package
        package_discounts = {
            pd.package_id: pd 
            for pd in coupon.package_discounts.all()
        }
        
        for item in applicable_items:
            pd = package_discounts.get(item.topup_package_id)
            if pd:
                item_discount = calculate_item_discount(
                    item, pd.discount_type, pd.discount_value
                )
                total_discount += item_discount
                discount_breakdown.append({
                    "item_id": item.id,
                    "product_name": f"{item.product.name} (Package)",
                    "discount": item_discount,
                })
    
    return {
        "total_discount": total_discount.quantize(Decimal("0.0001")),
        "applicable_items_count": len(applicable_items),
        "discount_breakdown": discount_breakdown,
        "cart_subtotal": cart_subtotal,
        "cart_total_after_discount": cart_subtotal - total_discount,
    }


def apply_coupon_to_order(coupon: Coupon, order, user=None) -> CouponUsage:
    """
    Apply coupon to order and record usage
    """
    with transaction.atomic():
        # update usage count
        Coupon.objects.filter(id=coupon.id).update(used_count=F('used_count') + 1)
        
        # record coupon usage
        usage = CouponUsage.objects.create(
            coupon=coupon,
            user=user,
            order=order,
        )
        
        return usage


def get_coupon_summary(coupon: Coupon) -> Dict:
    """
    Get coupon summary for display
    """
    summary = {
        "code": coupon.code,
        "scope": coupon.scope,
        "scope_display": coupon.get_scope_display(),
        "is_valid": coupon.is_valid(),
    }
    
    if coupon.scope in [CouponScope.GLOBAL, CouponScope.PRODUCT, CouponScope.CATEGORY, CouponScope.PACKAGE]:
        summary["discount_type"] = coupon.discount_type
        summary["discount_value"] = str(coupon.discount_value)
        if coupon.discount_type == DiscountType.PERCENT:
            summary["discount_text"] = f"{coupon.discount_value}%"
        else:
            summary["discount_text"] = f"{coupon.discount_value} $"
    else:
        summary["discount_type"] = "variable"
        summary["discount_text"] = "variable discount based on product/category/package"
    
    return summary
