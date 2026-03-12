from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from notifications.models import Notification
from notifications.serializers import NotificationPublicSerializer
from users_auth.authentication import CookieJWTAuthentication
from rest_framework.permissions import IsAuthenticated
from core.response_schema import get_response_schema_1
from django.core.cache import cache
from cache.utils import get_notifications_cache_key, get_notification_cache_timeout, get_notification_cache_key
from django.utils import timezone

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]  
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        cache_key = get_notifications_cache_key(request.user)
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(
                get_response_schema_1(
                    data=cached_data,
                    status=status.HTTP_200_OK,
                    message="Notifications retrieved successfully (cached)"
                ),
                status=status.HTTP_200_OK
            )

        notifications = Notification.public_manager.filter(user=request.user)
        serializer = NotificationPublicSerializer(notifications, many=True)
        cache.set(cache_key, serializer.data, get_notification_cache_timeout())
        return Response(
            get_response_schema_1(
                data=serializer.data,
                status=status.HTTP_200_OK,
                message="Notifications retrieved successfully"
            ),
            status=status.HTTP_200_OK
        )

class NotificationDetailView(APIView):
    permission_classes = [IsAuthenticated]  
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request, notification_id):
        cache_key = get_notification_cache_key(notification_id, request.user)
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(
                get_response_schema_1(
                    data=cached_data,
                    status=status.HTTP_200_OK,
                    message="Notification retrieved successfully (cached)"
                ),
                status=status.HTTP_200_OK
            )

        try:
            notification = Notification.public_manager.get(id=notification_id, user=request.user)
        except:
            return Response(
                get_response_schema_1(
                    data=None,
                    status=status.HTTP_404_NOT_FOUND,
                    message="Notification not found"
                ),
                status=status.HTTP_404_NOT_FOUND
            )

        notification.is_read = True
        notification.readed_at = timezone.now()
        notification.save(update_fields=["is_read", "readed_at"])
        serializer = NotificationPublicSerializer(notification)

        cache.set(cache_key, serializer.data, get_notification_cache_timeout())

        return Response(
            get_response_schema_1(
                data=serializer.data,
                status=status.HTTP_200_OK,
                message="Notification retrieved successfully"
            ),
            status=status.HTTP_200_OK
        )

    def delete(self, request, notification_id):
        try:
            notification = Notification.public_manager.get(id=notification_id, user=request.user)
        except Notification.DoesNotExist:
            return Response(
                get_response_schema_1(
                    data=None,
                    status=status.HTTP_404_NOT_FOUND,
                    message="Notification not found"
                ),
                status=status.HTTP_404_NOT_FOUND
            )

        notification.is_deleted = True
        notification.save()
        notification.deleted_at = timezone.now()
        notification.save()

        return Response(
            get_response_schema_1(
                data=None,
                status=status.HTTP_204_NO_CONTENT,
                message="Notification deleted successfully"
            ),
            status=status.HTTP_204_NO_CONTENT
        )

class NotificationDeleteView(APIView):
    permission_classes = [IsAuthenticated]  
    authentication_classes = [CookieJWTAuthentication]

    def delete(self, request):
        Notification.public_manager.filter(user=request.user).update(is_deleted=True, deleted_at=timezone.now())
        
        return Response(
            get_response_schema_1(
                data=None,
                status=status.HTTP_204_NO_CONTENT,
                message="Notifications deleted successfully"
            ),
            status=status.HTTP_204_NO_CONTENT
        )