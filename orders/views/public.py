from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from cart.serializers import AddToCartSerializer
from cart.utils.helpers import get_or_create_cart
from core.response_schema import get_response_schema_1
from orders.serializers import OrderDetailSerializer, OrderListSerializer
from users_auth.authentication import CookieJWTAuthentication
from topup.models import TopUpPackage
from orders.services.services import OrderService, OrderItemData
from payments.models import PaymentGateway
from orders.models import Order
import uuid
from orders.utils.choices import OrderStatus
from cache.utils import format_filter_value
from users_auth.authentication import OptionalJWTAuthentication
from payments.services.currency_service import get_user_currency

class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request, order_number):
        try:
            order_number = uuid.UUID(order_number)
        except ValueError:
            return Response(get_response_schema_1(data=None, status=400, message="Invalid order number"), status=400)
        
        order = Order.objects.filter(order_number=order_number, user=request.user).prefetch_related("items").first()
        if not order:
            return Response(get_response_schema_1(data=None, status=404, message="Order not found"), status=404)

        return Response(
            get_response_schema_1(data=OrderDetailSerializer(order, context={"request": request}).data, status=200, message="Order fetched successfully"),
            status=200
        )

class OrderListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]
    ALLOWED_FILTERS = ["status"]

    def get(self, request):
        filter_params = request.query_params.get('filter', None)
        orders = Order.objects.filter(user=request.user).prefetch_related("items").order_by("-created_at")

        filter_dict = {}
        if filter_params:
            for pair in filter_params.split(','):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    if k in self.ALLOWED_FILTERS:
                        filter_dict[k] = format_filter_value(v)
                    else:
                        return Response(get_response_schema_1(
                            message="Invalid filter parameter",
                            status=400
                        ), status=400)

        if filter_dict:
            orders = orders.filter(**filter_dict)

        return Response(
            get_response_schema_1(data=OrderListSerializer(orders, many=True, context={"request": request}).data, status=200, message="Orders fetched successfully"),
            status=200
        )

class CancelOrderView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, order_number):
        try:
            order_number = uuid.UUID(order_number)
        except ValueError:
            return Response(get_response_schema_1(data=None, status=400, message="Invalid order number"), status=400)
        
        order = Order.objects.filter(order_number=order_number, user=request.user).first()
        if not order:
            return Response(get_response_schema_1(data=None, status=404, message="Order not found"), status=404)

        if order.status != OrderStatus.PENDING:
            return Response(get_response_schema_1(data=None, status=400, message="Order cannot be cancelled now, it's already processed"), status=400)

        order.status = OrderStatus.CANCELLED
        order.save()

        # Log order cancellation
        from users.utils import log_user_activity
        from users.models import UserActivityLog
        log_user_activity(
            user=request.user,
            activity_type=UserActivityLog.ActivityType.ORDER_CANCEL,
            request=request,
            metadata={
                "order": {
                    "order_number": str(order.order_number),
                }
            }
        )

        return Response(
            get_response_schema_1(data=None, status=200, message="Order cancelled successfully"),
            status=200
        )

class BuyNowCheckoutView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = serializer.validated_data["product"]
        quantity = serializer.validated_data["quantity"]
        is_topup = serializer.validated_data["is_topup"]
        is_topup = serializer.validated_data["is_topup"]
        coupon_code = request.data.get("coupon_code")
        payment_gateway_id = request.data.get("payment_gateway_id")
        
        payment_gateway = None
        if payment_gateway_id:
            try:
                payment_gateway = PaymentGateway.objects.get(id=payment_gateway_id, is_active=True)
            except PaymentGateway.DoesNotExist:
                 return Response(
                    get_response_schema_1(data=None, status=400, message="Invalid or inactive payment gateway"),
                    status=400
                )

        unit_price = product.price
        topup_package = None

        if is_topup:
            topup_package = TopUpPackage.public.get(
                id=serializer.validated_data["topup_package_id"],
                game__product=product
            )
            unit_price = topup_package.price

        # Prepare item data
        item_data = OrderItemData(
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            is_topup=is_topup,
            topup_package=topup_package,
            topup_data=serializer.validated_data.get("topup_data", {}),
        )

        try:
            # Create Order using Service
            order, total_price, error_message = OrderService.create_order(
                user=request.user,
                items_data=[item_data],
                coupon_code=coupon_code,
                payment_gateway=payment_gateway
            )

            if error_message:
                return Response(
                    get_response_schema_1(data=None, status=400, message=error_message),
                    status=400
                )
            
            return Response(
                get_response_schema_1(
                    data=OrderDetailSerializer(order, context={"request": request}).data,
                    status=201,
                    message="Order created"
                ),
                status=201
            )

        except Exception as e:
             return Response(
                get_response_schema_1(data=None, status=500, message=f"An error occurred: {str(e)}"),
                status=500
            )


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request):
        cart = get_or_create_cart(request.user)
        coupon_code = cart.coupon.code if cart.coupon else None
        payment_gateway_id = request.data.get("payment_gateway_id")

        payment_gateway = None
        if payment_gateway_id:
            try:
                payment_gateway = PaymentGateway.objects.get(id=payment_gateway_id, is_active=True)
            except PaymentGateway.DoesNotExist:
                 return Response(
                    get_response_schema_1(data=None, status=400, message="Invalid or inactive payment gateway"),
                    status=400
                )

        if not cart.items.exists():
            return Response(
                get_response_schema_1(data=None, status=400, message="Cart is empty"),
                status=400
            )

        cart_items = list(cart.items.select_related("product", "topup_package").prefetch_related("product__category"))
        
        # Prepare items data
        items_data = []
        for item in cart_items:
            items_data.append(OrderItemData(
                product=item.product,
                quantity=item.quantity,
                unit_price=item.unit_price,
                is_topup=item.is_topup,
                topup_package=item.topup_package,
                topup_data=item.topup_data or {},
            ))

        try:
            # Create Order using Service
            order, total_price, error_message = OrderService.create_order(
                user=request.user,
                items_data=items_data,
                coupon_code=coupon_code,
                payment_gateway=payment_gateway
            )

            if error_message:
                return Response(
                    get_response_schema_1(data=None, status=400, message=error_message),
                    status=400
                )

            # Clear cart after successful order creation
            cart.delete()

            serializer = OrderDetailSerializer(order, context={"request": request})
            return Response(
                get_response_schema_1(data=serializer.data, status=201, message="Order created"),
                status=201
            )

        except Exception as e:
            return Response(
                get_response_schema_1(data=None, status=500, message=f"An error occurred: {str(e)}"),
                status=500
            )
