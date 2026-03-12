from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from users_auth.authentication import CookieJWTAuthentication
from notifications.models import Notification
from notifications.serializers import NotificationAdminSerializer
from core.response_schema import get_response_schema_1
from core.pagination import DynamicPageNumberPagination
from cache.utils import get_notification_list_cache_page_key, get_notification_cache_timeout, format_filter_value
from django.core.cache import cache
from django.db.models import Q
from django.db import transaction
from notifications.services.email_services import create_notification
from rest_framework.views import APIView
from django.utils import timezone

class NotificationAdminListView(APIView):
    permission_classes = [IsAdminUser]  
    authentication_classes = [CookieJWTAuthentication]
    ALLOWED_FILTERS = {"user", "is_read", "is_deleted", "is_active", "is_emailed", "created_at", "updated_at", "emailed_at", "readed_at"}


    def get(self, request):
        page_number = request.query_params.get('page', 1)
        filter_params = request.query_params.get('filter', None)
        search_query = request.query_params.get('search', None)

        paginator = DynamicPageNumberPagination()
        page_size = paginator.get_page_size(request)
        
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

        cache_key = get_notification_list_cache_page_key(
            page_number=page_number,
            page_size=page_size,
            filter_params=','.join([f"{k}={v}" for k, v in filter_dict.items()]) if filter_dict else None,
            search_query=search_query,
        )
        
        data = cache.get(cache_key)

        if data:
            return Response(get_response_schema_1(
                data=data,
                status=status.HTTP_200_OK,
                message="Notifications retrieved successfully (cached)"
            ), status=status.HTTP_200_OK)

        queryset = Notification.objects.all()
        if filter_dict:
            try:
                queryset = queryset.filter(**filter_dict)
            except Exception as e:
                return Response(get_response_schema_1(
                    message="Notification not found",
                    status=404
                ), status=404)

        if search_query:
            try:
                queryset = queryset.filter(
                    Q(user__username__icontains=search_query) |
                    Q(user__email__icontains=search_query) |
                    Q(user__full_name__icontains=search_query) |
                    Q(subject__icontains=search_query) |
                    Q(message__icontains=search_query) |
                    Q(email_type__icontains=search_query)
                )
            except Exception as e:
                return Response(get_response_schema_1(
                    message="Notification not found",
                    status=404
                ), status=404)

        # pagination
        page = paginator.paginate_queryset(queryset, request)

        serializer = NotificationAdminSerializer(page, many=True)
        data = paginator.get_paginated_response(serializer.data).data

        cache.set(cache_key, data, get_notification_cache_timeout())

        return Response(
            get_response_schema_1(
                data=data,
                status=status.HTTP_200_OK,
                message="Notifications retrieved successfully"
            ),
            status=status.HTTP_200_OK
        )

    def post(self, request):
        serializer = NotificationAdminSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                serializer.save()
                create_notification(
                    serializer,
                    user=serializer.instance.user,
                    subject=serializer.instance.subject,
                    message=serializer.instance.message
                )
                email_type = serializer.validated_data.get("email_type", "none")
                if email_type != "none":
                    notification = Notification.objects.get(id=serializer.instance.id)
                    notification.is_emailed = True
                    notification.emailed_at = timezone.now()
                    notification.save()

            return Response(
                get_response_schema_1(
                    data=serializer.data,
                    status=status.HTTP_201_CREATED,
                    message="Notification created successfully"
                ),
                status=status.HTTP_201_CREATED
            )

        return Response(
            get_response_schema_1(
                data=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                message="Invalid data"
            ),
            status=status.HTTP_400_BAD_REQUEST
        ) 

    def delete(self, request):
        notifications = Notification.objects.all()
        notifications.delete()
        return Response(
            get_response_schema_1(
                data=None,
                status=status.HTTP_204_NO_CONTENT,
                message="Notifications deleted successfully"
            ),
            status=status.HTTP_204_NO_CONTENT
        )

class NotificationAdminDetailView(APIView):
    permission_classes = [IsAdminUser]  
    authentication_classes = [CookieJWTAuthentication]

    def get(self, _request, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id)
        except:
            return Response(
                get_response_schema_1(
                    message="Notification not found",
                    status=404
                ),
                status=404
            )
        serializer = NotificationAdminSerializer(notification)
        return Response(
            get_response_schema_1(
                data=serializer.data,
                status=status.HTTP_200_OK,
                message="Notification retrieved successfully"
            ),
            status=status.HTTP_200_OK
        )

    def delete(self, _request, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id)
        except:
            return Response(
                get_response_schema_1(
                    message="Notification not found",
                    status=404
                ),
                status=404
            )
        notification.delete()
        return Response(
            get_response_schema_1(
                data=None,
                status=status.HTTP_204_NO_CONTENT,
                message="Notification deleted successfully"
            ),
            status=status.HTTP_204_NO_CONTENT
        )