import hmac
import hashlib
import requests
from django.conf import settings
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class PaymobService:
    @staticmethod
    def _get_api_key():
        return settings.PAYMOB_API_KEY
    
    @staticmethod
    def _get_secret_key():
        return settings.PAYMOB_SECRET_KEY

    @staticmethod
    def _get_hmac_secret():
        return settings.PAYMOB_HMAC

    @classmethod
    def create_intention(cls, order, user, notification_url, redirection_url, gateway):
        url = "https://accept.paymob.com/v1/intention"
        
        integration_id = gateway.integration_id if gateway else None
        if not integration_id:
            return {
                "success": False,
                "error": "Integration ID missing"
            }

        # 1. Prepare items and calculate discounts
        from coupons.models import Coupon
        from coupons.services.coupon_service import calculate_discount
        
        # Prepare a list of items for calculate_discount (expects unit_price, quantity, product, etc.)
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

        # 2. Build Paymob items with applied discounts
        items = []
        total_cents = 0
        
        for oi in order.items.all():
            item_discount_total = discount_breakdown.get(oi.id, Decimal("0.0000"))
            total_item_price_decimal = (oi.price * oi.quantity) - item_discount_total
            
            # Amount per unit in cents
            # We calculate this as (total_item_price / quantity) * 100
            # To ensure consistency, we round the unit price in cents to the nearest integer
            unit_price_cents = int(((total_item_price_decimal / oi.quantity) * 100).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))
            
            items.append({
                "name": oi.product_name[:100],
                "amount": unit_price_cents,
                "description": f"Payment for {oi.product_name} {'after discount' if item_discount_total > 0 else ''}"[:200],
                "quantity": oi.quantity
            })
            total_cents += (unit_price_cents * oi.quantity)

        # 3. Handle Gateway Tax
        gateway_tax_decimal = Decimal("0.0000")
        if gateway and gateway.tax_rate > 0:
            # Calculate tax based on the subtotal we just calculated in cents
            subtotal_after_discount_decimal = Decimal(total_cents) / 100
            gateway_tax_decimal = ((subtotal_after_discount_decimal * gateway.tax_rate) + Decimal("3.00")).quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")
            gateway_tax_cents = int(gateway_tax_decimal * 100)
            
            if gateway_tax_cents > 0:
                items.append({
                    "name": "Payment Fee",
                    "amount": gateway_tax_cents, 
                    "description": "Payment gateway processing fee",
                    "quantity": 1
                })
                total_cents += gateway_tax_cents

        # 4. Final Totals
        # The sum of items MUST match final_total_amount in cents
        final_total_amount = total_cents
        
        # Update order totals based on the selected gateway
        order.tax = gateway_tax_decimal
        order.total_price = Decimal(total_cents) / 100
        order.save()

        billing_data = {
            "first_name": getattr(user, "first_name", "Customer") or "Customer", 
            "last_name": getattr(user, "last_name", str(user.id)[:10]) or str(user.id)[:10],
            "phone_number": "NA", 
            "email": user.email,
            "country": "NA",
            "City": "NA",
        }

        if hasattr(user, 'profile'):
            if user.profile.phone:
                billing_data["phone_number"] = user.profile.phone
            if user.profile.country:
                billing_data["country"] = user.profile.country#[:2].upper()
            if user.profile.city:
                billing_data["City"] = user.profile.city

        payment_methods = []
        try:
            payment_methods.append(int(integration_id))
        except ValueError:
            return {
                "success": False,
                "error": "Invalid Integration ID"
            }

        payload = {
            "amount": final_total_amount,
            "currency": "EGP",
            "payment_methods": payment_methods,
            "items": items,
            "billing_data": billing_data,
            "notification_url": notification_url,
            "redirection_url": redirection_url
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {cls._get_secret_key()}"
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "client_secret": data.get("client_secret"),
                "payment_keys": data.get("payment_keys"),
                "payment_intent_id": data.get("id"),
                "amount": Decimal(final_total_amount) / 100,
                "currency": "EGP",
                "raw_data": data
            }
        except requests.exceptions.RequestException as e:
            logger.error("Paymob error", exc_info=True)
            message = str(e)
            if hasattr(e, 'response') and e.response is not None:
                message += f" - Response: {e.response.text}"
            return {
                "success": False,
                "error": message
            }

    @classmethod
    def verify_webhook_hmac(cls, payload, received_hmac):
        """
        Verify the HMAC signature from Paymob Intention webhook.
        Paymob sends the HMAC in the Authorization header.
        Actually, Intention webhook HMAC validation method typically 
        sha512(payload) with HMAC secret or standard paymob concatenations.
        The documentation for Intention v1 webhook HMAC states it uses sha512.
        
        Often It's calculated by sorting some parameters, but for Intention webhooks, it might be standard HMAC SHA512 of the raw body. 
        Assuming standard Paymob Intention Webhook Signature:
        "Authorization" header contains the HMAC or "hmac" in query params.
        """
        if not received_hmac:
            return False

        secret = cls._get_hmac_secret().encode('utf-8')
        
        # Try hashing the raw payload
        if isinstance(payload, bytes):
            raw_body = payload
        elif isinstance(payload, str):
            raw_body = payload.encode('utf-8')
        else:
            return False

        calculated_hmac = hmac.new(secret, raw_body, hashlib.sha512).hexdigest()
        
        return hmac.compare_digest(calculated_hmac.lower(), received_hmac.lower())
