from payments.models import Payment

class PaymentService:

    @staticmethod
    def create_payment(order, gateway, payment_intent_id):
        return Payment.objects.create(
            order=order,
            gateway=gateway,
            payment_intent_id=payment_intent_id,
            amount=order.total_price,
            status="pending"
        )