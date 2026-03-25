from decimal import Decimal
from typing import List, Dict, Optional, Tuple, Any
from django.db import transaction
from django.core.exceptions import ValidationError

from orders.models import Order, OrderItem
from topup.models import TopUpUserData
from coupons.services.coupon_service import (
    validate_coupon,
    calculate_discount,
    apply_coupon_to_order,
)


class OrderItemData:
    """Structure to hold data for order items before creation."""
    def __init__(
        self,
        product,
        quantity: int,
        unit_price: Decimal,
        is_topup: bool = False,
        topup_package=None,
        topup_data: dict = None,
    ):
        self.product = product
        self.quantity = quantity
        self.unit_price = unit_price
        self.is_topup = is_topup
        self.topup_package = topup_package
        self.topup_data = topup_data or {}
        
        # Attributes needed for coupon calculation (mimicking cart item structure)
        self.id = f"temp_{product.id}"
        self.product_id = product.id
        self.topup_package_id = topup_package.id if topup_package else None


class OrderService:
    @staticmethod
    def calculate_tax(subtotal: Decimal, payment_gateway_tax_rate: Decimal = Decimal("0.0000")) -> Decimal:
        """
        Calculate tax based on subtotal and payment gateway specific rate.
        Currently defaults to 0 if not specified.
        """
        # Ensure rate is Decimal
        if not isinstance(payment_gateway_tax_rate, Decimal):
             payment_gateway_tax_rate = Decimal(str(payment_gateway_tax_rate))
             
        if payment_gateway_tax_rate > 0:
            return (subtotal * payment_gateway_tax_rate).quantize(Decimal("0.0000"))
        return Decimal("0.0000")

    @classmethod
    def create_order(
        cls,
        user,
        items_data: List[OrderItemData],
        coupon_code: Optional[str] = None,
        discount_total: Decimal = Decimal("0.0000"),
        payment_gateway = None  # Accepts PaymentGateway object
    ) -> Tuple[Optional[Order], Decimal, Optional[str]]:
        """
        Creates an order from a list of item data.
        
        Args:
            user: The user creating the order.
            items_data: List of OrderItemData objects.
            coupon_code: Optional coupon code to apply.
            discount_total: Pre-calculated discount (optional).
            payment_gateway: PaymentGateway object to determine tax rate.
            
        Returns:
            Tuple containing:
            - The created Order object (or None on failure)
            - Total price
            - Error message (if any, otherwise None)
        """
        if not items_data:
            return None, Decimal("0.0000"), "No items to order"

        try:
            with transaction.atomic():
                subtotal = Decimal("0.0000")
                for item in items_data:
                    subtotal += item.unit_price * item.quantity

                # 1. Validate Coupon (if provided and not already validated/applied logic outside)
                # Ideally, validation should happen before calling this to provide fast feedback,
                # but we can double check here.
                applied_coupon = None
                if coupon_code:
                    is_valid, message, coupon = validate_coupon(coupon_code, user)
                    if not is_valid:
                        return None, Decimal("0.0000"), message
                    applied_coupon = coupon

                # 2. Tax Calculation
                payment_gateway_tax_rate = Decimal("0.0000")
                if payment_gateway:
                    payment_gateway_tax_rate = payment_gateway.tax_rate

                tax = cls.calculate_tax(subtotal, payment_gateway_tax_rate)

                # 3. Create Order Shell
                # We start with discount as 0, then update it.
                order = Order.objects.create(
                    user=user,
                    subtotal=subtotal,
                    tax=tax,
                    total_price=subtotal + tax, 
                    coupon_code=coupon_code if applied_coupon else None,
                    discount_total=Decimal("0.0000"),
                )

                # 4. Create Order Items
                for item_data in items_data:
                    order_item = OrderItem.objects.create(
                        order=order,
                        product=item_data.product,
                        product_name=item_data.product.name,
                        product_slug=item_data.product.slug,
                        quantity=item_data.quantity,
                        price=item_data.unit_price,
                        is_topup=item_data.is_topup,
                        topup_package=item_data.topup_package,
                    )

                    # 4b. Save TopUpUserData for topup items
                    if item_data.is_topup and item_data.topup_package and item_data.topup_data:
                        TopUpUserData.objects.create(
                            user=user,
                            order_item=order_item,
                            game=item_data.topup_package.game,
                            fields=item_data.topup_data,
                        )

                # 5. Apply Coupon Logic & Calculate Discount
                final_discount = Decimal("0.0000")
                
                if applied_coupon:
                    # Helper function calculate_discount mostly expects list of objects with specific attributes.
                    # Our OrderItemData has them.
                    discount_info = calculate_discount(applied_coupon, items_data)
                    final_discount = discount_info["total_discount"]

                    # Apply to DB (record usage)
                    apply_coupon_to_order(applied_coupon, order, user)
                
                # Check if a pre-calculated discount was passed (e.g. from UI estimation), 
                # but we should trust the service calculation more. 
                # If we want to force it, we can use discount_total, but let's stick to calculation.
                
                # 6. Finalize Order Totals
                order.subtotal = subtotal
                order.tax = tax
                order.discount_total = final_discount
                
                # Total calculation: Subtotal + Tax - Discount
                total = subtotal + tax - final_discount
                order.total_price = max(total, Decimal("0.0000"))
                
                order.save()
                
                # Log successful order creation
                from users.utils import log_user_activity
                from users.models import UserActivityLog
                log_user_activity(
                    user=user,
                    activity_type=UserActivityLog.ActivityType.ORDER_CREATE,
                    request=None, # request is not available here, but log_user_activity handles None (partially)
                    metadata={
                        "order": {
                            "order_number": str(order.order_number),
                            "total_price": str(order.total_price),
                            "items_count": len(items_data),
                        }
                    }
                )

                return order, order.total_price, None

        except Exception as e:
            # Log error if possible
            return None, Decimal("0.0000"), f"Order creation failed: {str(e)}"
