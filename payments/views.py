from users_auth.authentication import CookieJWTAuthentication
from rest_framework import generics
from rest_framework.permissions import AllowAny
from .models import PaymentGateway
from .serializers import PaymentGatewaySerializer
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from payments.models import Payment
from decimal import Decimal
from orders.models import OrderStatus, Order
from django.shortcuts import get_object_or_404
from rest_framework import status
from .services.paymob_service import PaymobService
from rest_framework.permissions import IsAuthenticated

class PaymentGatewayListView(generics.ListAPIView):
    queryset = PaymentGateway.objects.filter(is_active=True).order_by("id")
    serializer_class = PaymentGatewaySerializer
    permission_classes = [AllowAny]
    authentication_classes = []



@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([CookieJWTAuthentication])
def init_payment(request):
    """
    Initializes a payment for a given order and gateway.
    Payload: {"order_id": "...uuid...", "gateway_code": "paymob"}
    """
    order_id = request.data.get("order_id")
    gateway_code = request.data.get("gateway_code")
    notification_url = "https://formatively-lictorian-thresa.ngrok-free.dev/api/v1/payments/webhook/?gateway=paymob"
    redirection_url = request.data.get("redirection_url", "https://example.com/payment/success")

    if not order_id or not gateway_code:
        return Response({"error": "order_id and gateway_code are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order = Order.objects.get(order_number=order_id)
    except:
        return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    try:
        gateway = PaymentGateway.objects.get(gateway_code=gateway_code)
    except:
        return Response({"error": "Gateway not found"}, status=status.HTTP_404_NOT_FOUND)

    if order.status != OrderStatus.PENDING:
        return Response({"error": f"Cannot initiate payment for order in {order.status} state."}, status=status.HTTP_400_BAD_REQUEST)

    if gateway.gateway_type == "paymob":
        result = PaymobService.create_intention(order, request.user, notification_url, redirection_url, gateway)

        if not result.get("success"):
            return Response({"error": result.get("error")}, status=status.HTTP_400_BAD_REQUEST)

        # Create Payment Record
        gateway_order_id = None
        payment_keys = result.get("payment_keys", [])
        if payment_keys:
            gateway_order_id = payment_keys[0].get("order_id")

        payment = Payment.objects.create(
            order=order,
            gateway=gateway,
            payment_intent_id=result.get("payment_intent_id"),
            client_secret=result.get("client_secret"),
            gateway_order_id=str(gateway_order_id) if gateway_order_id else None,
            amount=order.total_price,
            currency="EGP",
            status="intended",
            raw_response=result.get("raw_data")
        )

        return Response({
            "client_secret": payment.client_secret,
            "payment_intent_id": payment.payment_intent_id,
            "gateway_order_id": payment.gateway_order_id,
            "payment_keys": result.get("payment_keys")
        }, status=status.HTTP_200_OK)

    return Response({"error": "Gateway not implemented"}, status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def payment_webhook(request):
    gateway_type = request.GET.get('gateway', 'stripe')
    
    if gateway_type == 'paymob':
        raw_body = request.body
        received_hmac = (
            request.headers.get("Authorization")
            or request.headers.get("X-Hmac")
            or request.GET.get("hmac")
        )

        if not received_hmac:
            return Response({"error": "Missing HMAC"}, status=400)
        
        event = request.data
        event_type = event.get("type")
        obj = event.get("obj", {})
        
        transaction_id = obj.get("id")
        
        payment_intent_id = None
        if event_type == "TOKEN":
            payment_intent_id = obj.get("next_payment_intention")
        elif event_type == "TRANSACTION":
            payment_intent_id = obj.get("payment_key_claims", {}).get("next_payment_intention")
        
        if not payment_intent_id:
            payment_intent_id = obj.get("intention") or obj.get("payment_intent")

        if not payment_intent_id:
            logger.error(f"Could not find payment_intent_id in Paymob webhook: {event}")
            return Response({"error": "payment_intent_id not found"}, status=400)

        try:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(
                    payment_intent_id=payment_intent_id
                )

                if payment.status == "success":
                    return Response(status=200)

                payment.raw_response = event
                
                paymob_order_id = obj.get("order", {}).get("id") or obj.get("order_id")
                if paymob_order_id:
                    payment.gateway_order_id = str(paymob_order_id)

                if event_type == "TRANSACTION":

                    success = obj.get("success")
                    payment.transaction_id = str(transaction_id)
                    
                    if success is True:
                        payment.status = "success"
                        payment.order.status = OrderStatus.PAID
                        payment.order.save()
                    elif success is False:
                        payment.status = "failed"
                        payment.order.status = OrderStatus.FAILED
                        payment.order.save()
                
                payment.save()

        except Payment.DoesNotExist:
            logger.error(f"Payment with intent {payment_intent_id} not found")
            return Response({"error": "Payment not found"}, status=404)
        except Exception as e:
            logger.error(f"Error processing Paymob webhook: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=500)
            
        return Response(status=200)


    else:
        event = request.data

        payment_intent_id = event.get("id")
        status_event = event.get("status")
        paid_amount = Decimal(str(event.get("amount") or 0))
        currency = event.get("currency")

        try:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(
                    payment_intent_id=payment_intent_id
                )

                if payment.status == "success":
                    return Response(status=200)

                if status_event == "paid" or status_event == "succeeded":
                    payment.status = "success"
                    payment.raw_response = event
                    payment.save()

                    order = payment.order
                    order.status = OrderStatus.PAID
                    order.save()
                else:
                    payment.status = "failed"
                    payment.save()

        except Payment.DoesNotExist:
            return Response(status=404)

        return Response(status=200)