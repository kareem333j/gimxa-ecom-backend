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
from rest_framework import status
from .services.paymob_service import PaymobService
from .services.stripe_service import StripeService
from rest_framework.permissions import IsAuthenticated
import logging
from users.utils import log_user_activity
from users.models import UserActivityLog
from permissions.custom import IsOwnerOrAdmin
from .serializers import (
    PaymentGatewaySerializer, PaymentSerializer, 
    AdminPaymentSimpleSerializer,AdminPaymentDetailSerializer, AdminPaymentGatewaySerializer
)
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from core.response_schema import get_response_schema_1
from permissions.custom import AdminPermission
from core.pagination import DynamicPageNumberPagination
from django.db.models import Q

User = get_user_model()

logger = logging.getLogger(__name__)


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
    Unified payment init endpoint.
    Dispatches to the correct gateway handler based on gateway_type.
    Payload: {"order_id": "...", "gateway_code": "..."}
    """
    order_id = request.data.get("order_id")
    gateway_code = request.data.get("gateway_code")

    if not order_id or not gateway_code:
        return Response({"error": "order_id and gateway_code are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order = Order.objects.get(order_number=order_id)
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    is_admin = getattr(request.user, "role", None) == "admin"
    if order.user != request.user and not (request.user.is_staff or is_admin):
        return Response({"error": "Access denied. Only the owner of this order can complete the payment."}, status=status.HTTP_403_FORBIDDEN)

    try:
        gateway = PaymentGateway.objects.get(gateway_code=gateway_code)
    except PaymentGateway.DoesNotExist:
        return Response({"error": "Gateway not found"}, status=status.HTTP_404_NOT_FOUND)

    if order.status != OrderStatus.PENDING:
        return Response(
            {"error": f"Cannot initiate payment for order in {order.status} state."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Cancel any existing pending or intended payments for this order
    Payment.objects.filter(
        order=order, 
        status__in=["pending", "intended"]
    ).update(status="cancelled")

    # ------------------------------------------------------------------ #
    #  Paymob                                                              #
    # ------------------------------------------------------------------ #
    if gateway.gateway_type == "paymob":
        notification_url = "https://formatively-lictorian-thresa.ngrok-free.dev/api/v1/payments/webhook/?gateway=paymob"
        redirection_url = request.data.get("redirection_url", "https://example.com/payment/success")

        result = PaymobService.create_intention(order, request.user, notification_url, redirection_url, gateway)

        if not result.get("success"):
            return Response({"error": result.get("error")}, status=status.HTTP_400_BAD_REQUEST)

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
            amount=result.get("amount", order.total_price),
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

    # ------------------------------------------------------------------ #
    #  Stripe                                                              #
    # ------------------------------------------------------------------ #
    if gateway.gateway_type == "stripe":
        result = StripeService.create_payment_intent(order, request.user, gateway)

        if not result.get("success"):
            return Response({"error": result.get("error")}, status=status.HTTP_400_BAD_REQUEST)

        payment = Payment.objects.create(
            order=order,
            gateway=gateway,
            payment_intent_id=result.get("payment_intent_id"),
            client_secret=result.get("client_secret"),
            amount=result.get("amount", order.total_price),
            currency=result.get("currency", "USD"),
            status="intended",
            raw_response=result.get("raw_data")
        )

        return Response({
            "client_secret": payment.client_secret,
            "payment_intent_id": payment.payment_intent_id,
            "checkout_url": result.get("checkout_url"),
        }, status=status.HTTP_200_OK)

    return Response({"error": "Gateway not implemented"}, status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def payment_webhook(request):
    gateway_type = request.GET.get('gateway', 'stripe')

    # ------------------------------------------------------------------ #
    #  Paymob webhook                                                      #
    # ------------------------------------------------------------------ #
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
                        
                        # Log Paymob success
                        log_user_activity(
                            user=payment.order.user,
                            activity_type=UserActivityLog.ActivityType.PAYMENT_SUCCESS,
                            request=request,
                            metadata={
                                "payment": {
                                    "gateway": "paymob",
                                    "transaction_id": payment.transaction_id,
                                    "amount": str(payment.amount),
                                    "order_number": str(payment.order.order_number),
                                }
                            }
                        )
                    elif success is False:
                        payment.status = "failed"
                        payment.order.status = OrderStatus.FAILED
                        payment.order.save()

                        # Log Paymob failure
                        log_user_activity(
                            user=payment.order.user,
                            activity_type=UserActivityLog.ActivityType.PAYMENT_FAIL,
                            request=request,
                            metadata={
                                "payment": {
                                    "gateway": "paymob",
                                    "error": obj.get("data", {}).get("message", "Unknown error"),
                                    "order_number": str(payment.order.order_number),
                                }
                            }
                        )

                payment.save()

        except Payment.DoesNotExist:
            logger.error(f"Payment with intent {payment_intent_id} not found")
            return Response({"error": "Payment not found"}, status=404)
        except Exception as e:
            logger.error(f"Error processing Paymob webhook: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=500)

        return Response(status=200)

    # ------------------------------------------------------------------ #
    #  Stripe webhook                                                      #
    # ------------------------------------------------------------------ #
    if gateway_type == 'stripe':
        raw_body = request.body
        sig_header = request.headers.get("Stripe-Signature")

        try:
            event = StripeService.verify_webhook_signature(raw_body, sig_header)
        except Exception as e:
            logger.error(f"Stripe webhook signature verification failed: {e}")
            return Response({"error": "Invalid signature"}, status=400)

        if isinstance(event, dict):
            event_type = event.get("type")
            data_obj = event.get("data", {}).get("object", {})
        else:
            event_type = getattr(event, "type", None) or event.get("type")
            data_obj = getattr(getattr(event, "data", None), "object", None)
            if data_obj is None:
                data_obj = event.get("data", {}).get("object", {})
                
        payment_intent_id = getattr(data_obj, "id", None) if not isinstance(data_obj, dict) else data_obj.get("id")

        if not payment_intent_id:
            logger.error(f"Stripe: Missing payment_intent or session ID in event {event_type}")
            return Response({"error": "Missing payment_intent id"}, status=400)

        try:
            with transaction.atomic():
                # Try to find the payment by ID (Session ID or PaymentIntent ID)
                payment = Payment.objects.select_for_update().filter(
                    payment_intent_id=payment_intent_id
                ).first()

                if payment:
                    logger.info(f"Stripe: Found payment {payment.id} by ID {payment_intent_id}")
                else:
                    # Fallback 1: Find by metadata if ID lookup fails
                    metadata = data_obj.get("metadata", {}) if isinstance(data_obj, dict) else getattr(data_obj, "metadata", {})
                    order_number = metadata.get("order_number")
                    if order_number:
                        payment = Payment.objects.select_for_update().filter(
                            order__order_number=order_number,
                            gateway__gateway_type="stripe"
                        ).order_by("-created_at").first()
                        
                        if payment:
                            logger.info(f"Stripe: Found payment {payment.id} for order {order_number} via metadata fallback (event ID: {payment_intent_id})")
                    
                    # Fallback 2: Look in payment_details.order_reference (Checkout Session ID)
                    if not payment:
                        payment_details = data_obj.get("payment_details", {}) if isinstance(data_obj, dict) else getattr(data_obj, "payment_details", {})
                        if payment_details:
                            session_id = payment_details.get("order_reference")
                            if session_id:
                                payment = Payment.objects.select_for_update().filter(
                                    payment_intent_id=session_id
                                ).first()
                                if payment:
                                    logger.info(f"Stripe: Found payment {payment.id} via order_reference fallback ({session_id})")

                if not payment:
                    logger.error(f"Stripe: Payment with ID {payment_intent_id} not found even with fallbacks. Metadata: {metadata}")
                    return Response(status=200) # Still 200 to satisfy Stripe

                logger.info(f"Stripe: Processing event {event_type} for payment {payment.id} (status: {payment.status})")
                if payment.status == "success":
                    logger.info(f"Stripe: Payment {payment.id} already marked as success. Skipping.")
                    return Response(status=200)

                payment.raw_response = data_obj

                # Handle both PaymentIntent and Session events
                if event_type in ("payment_intent.succeeded"):
                    # For checkout session, ensure payment is successful before marking as paid
                    payment_status = getattr(data_obj, "payment_status", None) if not isinstance(data_obj, dict) else data_obj.get("payment_status")
                    
                    if event_type == "checkout.session.completed":
                        # If we found it by Session ID, update it with the actual PaymentIntent ID for future events
                        actual_pi = getattr(data_obj, "payment_intent", None) if not isinstance(data_obj, dict) else data_obj.get("payment_intent")
                        if actual_pi and payment.payment_intent_id != actual_pi:
                            payment.payment_intent_id = actual_pi
                            logger.info(f"Stripe: Updated Payment {payment.id} with actual PaymentIntent ID {actual_pi}")

                        if payment_status != "paid":
                            # If payment status is not paid, wait for payment_intent.succeeded or ignore
                            payment.save()
                            return Response(status=200)

                    payment.status = "success"
                    
                    # Safe getters for Stripe object fields
                    latest_charge = getattr(data_obj, "latest_charge", None) if not isinstance(data_obj, dict) else data_obj.get("latest_charge")
                    intent_id = getattr(data_obj, "payment_intent", None) if not isinstance(data_obj, dict) else data_obj.get("payment_intent")
                    
                    payment.transaction_id = latest_charge or intent_id or str(payment_intent_id)
                    
                    # Update order status explicitly
                    order = payment.order
                    order.status = OrderStatus.PAID
                    order.save()
                    logger.info(f"Stripe: Order {order.order_number} status updated to {order.status}")

                    # Mark payment as success and save
                    payment.status = "success"
                    payment.save()
                    logger.info(f"Stripe: Payment {payment.id} marked as success")

                    # Log Stripe success
                    log_user_activity(
                        user=order.user,
                        activity_type=UserActivityLog.ActivityType.PAYMENT_SUCCESS,
                        request=request,
                        metadata={
                            "payment": {
                                "gateway": "stripe",
                                "transaction_id": payment.transaction_id,
                                "amount": str(payment.amount),
                                "order_number": str(order.order_number),
                            }
                        }
                    )

                elif event_type in ("payment_intent.payment_failed", "payment_intent.canceled", "checkout.session.expired", "payment_intent.requires_payment_method"):
                    payment.status = "failed"
                    payment.order.status = OrderStatus.FAILED
                    payment.order.save()

                    # Log Stripe failure
                    log_user_activity(
                        user=payment.order.user,
                        activity_type=UserActivityLog.ActivityType.PAYMENT_FAIL,
                        request=request,
                        metadata={
                            "payment": {
                                "gateway": "stripe",
                                "event_type": event_type,
                                "order_number": str(payment.order.order_number),
                            }
                        }
                    )
                
                elif event_type in ("payment_intent.processing", "checkout.session.async_payment_succeeded"):
                    payment.status = "processing"
                    payment.order.status = OrderStatus.PROCESSING
                    payment.order.save()

                    # Log Stripe processing
                    log_user_activity(
                        user=payment.order.user,
                        activity_type=UserActivityLog.ActivityType.PAYMENT_PROCESSING,
                        request=request,
                        metadata={
                            "payment": {
                                "gateway": "stripe",
                                "event_type": event_type,
                                "order_number": str(payment.order.order_number),
                            }
                        }
                    )

                payment.save()

        except Payment.DoesNotExist:
            logger.error(f"Stripe: Payment with intent {payment_intent_id} not found")
            # Return 200 so Stripe doesn't keep retrying for unknown intents
            return Response(status=200)
        except Exception as e:
            logger.error(f"Error processing Stripe webhook: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=500)

        return Response(status=200)
    
    return Response({"error": "Unknown gateway"}, status=400)

class UserPaymentListView(APIView):
    permission_classes = [IsOwnerOrAdmin]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, _request, user_id):
        try:
            user = User.objects.get(id=user_id)
            if not user.is_superuser and str(user.id) != str(user_id):
                return Response(get_response_schema_1(
                    data=None,
                    message="You are not authorized to view this page",
                    status=403
                ), status=403)
            payments = Payment.objects.filter(order__user_id=user_id).order_by("-created_at")
            serializer = PaymentSerializer(payments, many=True)
            return Response(get_response_schema_1(
                data=serializer.data,
                message="Payments retrieved successfully",
                status  =200
            ), status=200)
        except:
            return Response(get_response_schema_1(
                data=None,
                message="User not found",
                status=404
            ), status=404)

class OrderPaymentListView(APIView):
    permission_classes = [IsOwnerOrAdmin]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, _request, order_number):
        try:
            order = Order.objects.get(order_number=order_number)
            if not order.user.is_superuser and str(order.user.id) != str(_request.user.id):
                return Response(get_response_schema_1(
                    data=None,
                    message="You are not authorized to view this page",
                    status=403
                ), status=403)
            payments = Payment.objects.filter(order_id=order.id).order_by("-created_at")
            serializer = PaymentSerializer(payments, many=True)
            return Response(get_response_schema_1(
                data=serializer.data,
                message="Payments retrieved successfully",
                status=200
            ), status=200)
        except:
            return Response(get_response_schema_1(
                data=None,
                message="Order not found",
                status=404
            ), status=404)

# ------------------------------------------------------------------ #
#  Admin Views                                                       #
# ------------------------------------------------------------------ #

class AdminPaymentGatewayListView(generics.ListAPIView):
    queryset = PaymentGateway.objects.all().order_by("id")
    serializer_class = AdminPaymentGatewaySerializer
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

class AdminPaymentListView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        queryset = Payment.objects.all().order_by("-created_at")

        # Filtering
        user_filter = request.query_params.get("user")
        if user_filter:
            queryset = queryset.filter(
                Q(order__user__username__icontains=user_filter) |
                Q(order__user__email__icontains=user_filter) |
                Q(order__user__full_name__icontains=user_filter)
            )

        currency_filter = request.query_params.get("currency")
        if currency_filter:
            queryset = queryset.filter(currency=currency_filter.upper())

        country_filter = request.query_params.get("country")
        if country_filter:
            queryset = queryset.filter(order__user__profile__country__icontains=country_filter)

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        gateway_filter = request.query_params.get("gateway")
        if gateway_filter:
            queryset = queryset.filter(gateway__name__iexact=gateway_filter)

        # Ordering
        ordering = request.query_params.get("ordering")
        if ordering in ["amount", "-amount", "created_at", "-created_at"]:
            queryset = queryset.order_by(ordering)

        # Pagination
        paginator = DynamicPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = AdminPaymentSimpleSerializer(page, many=True)
            paginated_data = paginator.get_paginated_response(serializer.data).data
            return Response(get_response_schema_1(
                data=paginated_data,
                message="Payments retrieved successfully",
                status=200
            ), status=200)

        serializer = AdminPaymentSimpleSerializer(queryset, many=True)
        return Response(get_response_schema_1(
            data=serializer.data,
            message="Payments retrieved successfully",
            status=200
        ), status=200)

class AdminPaymentStatusUpdateView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def patch(self, request, payment_id):
        new_status = request.data.get("status")
        if not new_status:
            return Response(get_response_schema_1(
                data=None,
                message="Status is required",
                status=400
            ), status=400)

        try:
            payment = Payment.objects.get(id=payment_id)
            if new_status in Payment.StatusChoices:
                payment.status = new_status
                payment.save()
            else:
                return Response(get_response_schema_1(
                    data=None,
                    message="Invalid status",
                    status=400
                ), status=400)
            
            serializer = AdminPaymentSimpleSerializer(payment)
            return Response(get_response_schema_1(
                data=serializer.data,
                message=f"Payment status updated to {new_status}",
                status=200
            ), status=200)
        except:
            return Response(get_response_schema_1(
                data=None,
                message="Payment not found",
                status=404
            ), status=404)

class AdminPaymentDetailView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id)
            serializer = AdminPaymentDetailSerializer(payment, context={"request": request})
            return Response(get_response_schema_1(
                data=serializer.data,
                message="Payment details retrieved successfully",
                status=200
            ), status=200)
        except:
            return Response(get_response_schema_1(
                data=None,
                message="Payment not found",
                status=404
            ), status=404)