import stripe
from django.conf import settings
from decimal import Decimal
import logging
from users.models import UserSettings
from payments.services.currency_service import CurrencyService
logger = logging.getLogger(__name__)


class StripeService:

    @staticmethod
    def _get_secret_key():
        return settings.STRIPE_SECRET_KEY

    @staticmethod
    def _get_webhook_secret():
        return getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    @classmethod
    def create_payment_intent(cls, order, user, gateway):
        """
        Creates a Stripe PaymentIntent for the given order.
        Applies coupon discounts and gateway tax the same way as Paymob.
        Returns:
            {
                "success": True,
                "client_secret": "...",
                "payment_intent_id": "pi_...",
                "raw_data": {...}
            }
        or {"success": False, "error": "..."}
        """
        stripe.api_key = cls._get_secret_key()

        # --- 1. Calculate discounts (mirrors paymob_service logic) ---
        from coupons.models import Coupon
        from coupons.services.coupon_service import calculate_discount

        class MockItem:
            def __init__(self, oi):
                self.id = oi.id
                self.product = oi.product
                self.product_id = oi.product_id
                self.quantity = oi.quantity
                self.unit_price = oi.price
                self.topup_package_id = oi.topup_package_id

        discount_items = [MockItem(oi) for oi in order.items.all()]

        discount_breakdown = {}
        if order.coupon_code:
            coupon = Coupon.objects.filter(code__iexact=order.coupon_code).first()
            if coupon:
                discount_info = calculate_discount(coupon, discount_items)
                for db in discount_info.get("discount_breakdown", []):
                    discount_breakdown[db["item_id"]] = db["discount"]

        # --- 2. Build line totals and calculate subtotal ---
        total_cents = 0

        for oi in order.items.all():
            item_discount_total = discount_breakdown.get(oi.id, Decimal("0.0000"))
            total_item_price = (oi.price * oi.quantity) - item_discount_total
            unit_price_cents = int(
                (
                    (total_item_price / oi.quantity) * 100
                ).quantize(Decimal("1"), rounding="ROUND_HALF_UP")
            )
            total_cents += unit_price_cents * oi.quantity

        # --- 3. Apply gateway tax ---
        gateway_tax_decimal = Decimal("0.0000")
        if gateway and gateway.tax_rate > 0:
            subtotal_decimal = Decimal(total_cents) / 100
            gateway_tax_decimal = (
                (subtotal_decimal * gateway.tax_rate) + Decimal("0.30")
            ).quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")
            gateway_tax_cents = int(gateway_tax_decimal * 100)
            total_cents += gateway_tax_cents

        # --- 4. Persist updated totals on the order ---
        order.tax = gateway_tax_decimal
        order.total_price = Decimal(total_cents) / 100
        order.save()

        # --- 5. Determine currency and convert amount for Stripe ---
        user_settings = UserSettings.objects.get(user=user)
        currency = user_settings.currency or "USD"
        
        # Convert total_cents (USD) to target currency for Stripe charging
        final_amount_cents = total_cents
        if currency.upper() != "USD":
            service = CurrencyService()
            total_usd = Decimal(total_cents) / 100
            total_converted = service.convert(total_usd, currency)
            final_amount_cents = int(
                (total_converted * 100).quantize(Decimal("1"), rounding="ROUND_HALF_UP")
            )

        # --- 6. Create PaymentIntent ---
        metadata = {
            "order_number": str(order.order_number),
            "user_id": str(user.id),
            "user_email": user.email,
        }

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': currency,
                        'product_data': {
                            'name': f"Order {order.order_number}",
                        },
                        'unit_amount': final_amount_cents,
                    },
                    'quantity': 1,
                }],
                mode='payment',
                metadata=metadata,
                customer_email=user.email,
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )
            return {
                "success": True,
                "client_secret": None,
                "payment_intent_id": session.id,
                "checkout_url": session.url,
                "amount": Decimal(final_amount_cents) / 100,
                "currency": currency.upper(),
                "raw_data": dict(session),
            }
        except stripe.error.StripeError as e:
            # logger.error("Stripe error during PaymentIntent creation", exc_info=True)
            logger.error("Stripe error during Session creation", exc_info=True)
            return {
                "success": False,
                "error": str(e.user_message or e),
            }

    @classmethod
    def verify_webhook_signature(cls, payload_bytes, sig_header):
        """
        Constructs and verifies the Stripe webhook event.
        Returns the event object on success, or raises an exception.
        """
        secret = cls._get_webhook_secret()
        if not secret:
            # In development you may skip verification — log a warning.
            logger.warning(
                "STRIPE_WEBHOOK_SECRET not set. Skipping signature verification."
            )
            import json
            return json.loads(payload_bytes)

        stripe.api_key = cls._get_secret_key()
        event = stripe.Webhook.construct_event(payload_bytes, sig_header, secret)
        return event
