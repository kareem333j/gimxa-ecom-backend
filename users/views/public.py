from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from users.models import User
from users.serializers import (
    UserPublicSerializer,
    ActivityLogSerializer,
    MyProfileSerializer,
    UserUpdateSerializer
)
from rest_framework.permissions import IsAuthenticated
from permissions.custom import IsOwnerOrAdmin
from users_auth.authentication import CookieJWTAuthentication
from core.response_schema import get_response_schema_1
from users.models import UserActivityLog
from core.pagination import DynamicPageNumberPagination

class UserSimpleView(APIView):
    permission_classes = [IsOwnerOrAdmin]
    authentication_classes = [CookieJWTAuthentication]
    
    def get(self, request, user_id):
        try:
            if request.user.is_superuser:
                user = User.objects.get(id=user_id)
            else:
                user = User.objects.for_user(request.user).get(id=user_id)
            serializer = UserPublicSerializer(user)
            return Response(serializer.data)
        except:
            return Response(get_response_schema_1(
                data=None,
                message="User not found",
                status=404
            ), status=status.HTTP_404_NOT_FOUND)

class UserSelfProfileView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]
    
    def get(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response(get_response_schema_1(
                data=None,
                message="User not found",
                status=404
            ), status=404)

        serializer = MyProfileSerializer(user)
        return Response(get_response_schema_1(
            data=serializer.data,
            message="User profile fetched successfully",
            status=200
        ))

    def patch(self, request):

        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        user_serializer = MyProfileSerializer(request.user)

        return Response(
            get_response_schema_1(
                data=user_serializer.data,
                message="Profile updated successfully",
                status=200
            )
        )

class UserProfileView(APIView):
    permission_classes = [IsOwnerOrAdmin]
    authentication_classes = [CookieJWTAuthentication]
    
    def get(self, request, user_id):
        try:
            if request.user.is_superuser:
                user = User.objects.get(id=user_id)
            else:
                user = User.objects.for_user(request.user).get(id=user_id)
            serializer = MyProfileSerializer(user)
            return Response(get_response_schema_1(
                data=serializer.data,
                message="User profile fetched successfully",
                status=200
            ))
        except:
            return Response(get_response_schema_1(
                data=None,
                message="User not found",
                status=404
            ), status=status.HTTP_404_NOT_FOUND)


class UserActivityLogsView(APIView):
    permission_classes = [IsOwnerOrAdmin]
    authentication_classes = [CookieJWTAuthentication]
    
    def get(self, request, user_id):
        try:
            if request.user.is_superuser:
                user = User.objects.get(id=user_id)
            else:
                user = User.objects.for_user(request.user).get(id=user_id)

            # get logs
            logs = UserActivityLog.objects.filter(user=user)

            # paginate
            paginator = DynamicPageNumberPagination(page_size=24)
            paginated_logs = paginator.paginate_queryset(logs, request)
            serializer = ActivityLogSerializer(paginated_logs, many=True)
            data = paginator.get_paginated_response(serializer.data).data

            return Response(get_response_schema_1(
                data=data,
                message="User activity logs fetched successfully",
                status=200
            ), status=status.HTTP_200_OK)
        except:
            return Response(get_response_schema_1(
                data=None,
                message="User not found",
                status=404
            ), status=status.HTTP_404_NOT_FOUND)