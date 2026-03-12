from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from core.response_schema import get_response_schema_1
from orders.models import Order, OrderStatus
from permissions.custom import AdminPermission
from users_auth.authentication import CookieJWTAuthentication
from orders.serializers import OrderDetailSerializer, OrderListSerializer
from django.db.models import Q
from core.pagination import DynamicPageNumberPagination
from notifications.serializers import NotificationAdminSerializer
from notifications.services.email_services import create_notification
from django.utils import timezone
from notifications.models import Notification

class AdminOrderListView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    ALLOWED_FILTERS = ["status", "user", "total_price", "created_at", "subtotal", "discount_total", "coupon_code"]

    def get(self, request):
        filter_params = request.query_params.get('filter', None)
        search_query = request.query_params.get('search', None)
        paginator = DynamicPageNumberPagination()

        filter_dict = {}
        if filter_params:
            for pair in filter_params.split(','):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    if k in self.ALLOWED_FILTERS:
                        filter_dict[k] = v

        queryset = Order.objects.all()

        if filter_dict:
            queryset = queryset.filter(**filter_dict)
        
        if search_query:
            queryset = queryset.filter(
                Q(user__username__icontains=search_query) | 
                Q(user__full_name__icontains=search_query) | 
                Q(user__email__icontains=search_query)
            )

        # pagination
        page = paginator.paginate_queryset(queryset, request)
        serializer = OrderListSerializer(page, many=True)
        data = paginator.get_paginated_response(serializer.data).data

        return Response(
            get_response_schema_1(data, 200, "Orders fetched successfully")
            , status=200
        )


class AdminOrderDetailView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, _request, order_number):
        order = Order.objects.filter(order_number=order_number).first()
        if not order:
            return Response(get_response_schema_1(data=None, status=404, message="Order not found"), status=404)

        return Response(
            get_response_schema_1(data=OrderDetailSerializer(order).data, status=200, message="Order fetched successfully"),
            status=200
        )

    def patch(self, request, order_number):
        new_status = request.data.get("status")
        send_notification = request.data.get("send_notification", False)

        order = Order.objects.select_for_update().filter(order_number=order_number).first()
        if not order:
            return Response(get_response_schema_1(data=None, status=404, message="Order not found"), status=404)

        with transaction.atomic():
            if new_status in [choice[0] for choice in OrderStatus.choices]:
                order.status = new_status
                order.save()
                notification_data = request.data.get("notification_data", {})
                if not notification_data:
                    return Response(get_response_schema_1(data=None, status=400, message="notification_data is required"), status=400)
                notification_data["user"] = order.user.id
                if send_notification:
                    serializer = NotificationAdminSerializer(data=notification_data)
                    if serializer.is_valid(raise_exception=True):
                        notification = serializer.save()
                        create_notification(
                            serializer,
                            user=notification.user,
                            subject=notification.subject,
                            message=notification.message
                        )
                        email_type = serializer.validated_data.get("email_type", "none")
                        if email_type != "none":
                            notification.is_emailed = True
                            notification.emailed_at = timezone.now()
                            notification.save()

        return Response(
            get_response_schema_1(data=OrderDetailSerializer(order).data, status=200, message="Order status updated"),
            status=200
        )

    def delete(self, _request, order_number):
        order = Order.objects.filter(order_number=order_number).first()
        if not order:
            return Response(get_response_schema_1(data=None, status=404, message="Order not found"), status=404)

        with transaction.atomic():
            order.delete()

        return Response(
            get_response_schema_1(data=None, status=200, message="Order deleted successfully"),
            status=200
        )
