from rest_framework import generics
from rest_framework.permissions import AllowAny
from .models import PaymentGateway
from .serializers import PaymentGatewaySerializer
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from payments.models import Payment
from decimal import Decimal
from orders.models import OrderStatus

class PaymentGatewayListView(generics.ListAPIView):
    queryset = PaymentGateway.objects.filter(is_active=True)
    serializer_class = PaymentGatewaySerializer
    permission_classes = [AllowAny]



@api_view(["POST"])
@permission_classes([AllowAny])
def payment_webhook(request):
    event = request.data

    payment_intent_id = event.get("id")
    status = event.get("status")
    paid_amount = Decimal(str(event.get("amount")))
    currency = event.get("currency")

    try:
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(
                payment_intent_id=payment_intent_id
            )

            # Idempotency check
            if payment.status == "success":
                return Response(status=200)

            # Verify amount
            if paid_amount != payment.amount:
                payment.status = "failed"
                payment.raw_response = event
                payment.save()
                return Response(status=400)

            # Verify currency if stored
            if currency != payment.currency:
                payment.status = "failed"
                payment.save()
                return Response(status=400)

            if status == "paid":
                payment.status = "success"
                payment.raw_response = event
                payment.save()

                order = payment.order
                order.status = OrderStatus.PAID
                order.save()

    except Payment.DoesNotExist:
        return Response(status=404)

    return Response(status=200)