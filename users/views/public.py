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
from users.utils import get_client_ip, get_user_location
from users.models import UserSettings, UserProfile
from users.choices import Role
from users.choices import CURRENCIES

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

class UserLocationView(APIView):
    permission_classes = [IsOwnerOrAdmin]
    authentication_classes = [CookieJWTAuthentication]
    
    def get(self, request, user_id):
        try:
            if request.user.is_superuser:
                user = User.objects.get(id=user_id)
            else:
                user = User.objects.for_user(request.user).get(id=user_id)

            ip_address = get_client_ip(request) if request else None
            location = get_user_location(ip_address) if ip_address else None

            user_settings = UserSettings.objects.filter(user=user).first()

            data = {
                "current":{
                    "country": location.split(",")[1].strip() if location else None,
                    "city": location.split(",")[0].strip() if location else None,
                    "ip": ip_address
                },
                "in-settings": {
                    "country": user_settings.location.split(",")[1].strip() if user_settings.location else None,
                    "city": user_settings.location.split(",")[0].strip() if user_settings.location else None,
                }
            }

            if user.role == Role.USER:
                user_profile = UserProfile.objects.filter(user=user).first()
                data["in-profile"] = {
                    "country": user_profile.country,
                    "city": user_profile.city,
                }

            return Response(get_response_schema_1(
                data=data,
                message="User location fetched successfully",
                status=200
            ))
        except:
            return Response(get_response_schema_1(
                data=None,
                message="User not found",
                status=404
            ), status=status.HTTP_404_NOT_FOUND)

class UserProfileCurrencyView(APIView):
    permission_classes = [IsOwnerOrAdmin]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request, user_id):
        try:
            if request.user.is_superuser:
                user = User.objects.get(id=user_id)
            else:
                user = User.objects.for_user(request.user).get(id=user_id)

            user_settings = UserSettings.objects.filter(user=user).first()

            data = {
                "currency": user_settings.currency,
            }

            return Response(get_response_schema_1(
                data=data,
                message="User currency fetched successfully",
                status=200
            ))
        except:
            return Response(get_response_schema_1(
                data=None,
                message="User not found",
                status=404
            ), status=status.HTTP_404_NOT_FOUND)

    def put(self, request, user_id):
        try:
            if request.user.is_superuser:
                user = User.objects.get(id=user_id)
            else:
                user = User.objects.for_user(request.user).get(id=user_id)

            user_settings = UserSettings.objects.filter(user=user).first()

            new_currency = request.data.get("currency")
            if not new_currency:
                return Response(get_response_schema_1(
                    data=None,
                    message="Currency is required",
                    status=400
                ), status=status.HTTP_400_BAD_REQUEST)

            if new_currency not in CURRENCIES:
                return Response(get_response_schema_1(
                    data=None,
                    message="Invalid currency",
                    status=400
                ), status=status.HTTP_400_BAD_REQUEST)
            
            user_settings.currency = new_currency
            user_settings.save()

            data = {
                "currency": user_settings.currency,
            }

            return Response(get_response_schema_1(
                data=data,
                message="User currency updated successfully",
                status=200
            ))
        except:
            return Response(get_response_schema_1(
                data=None,
                message="User not found",
                status=404
            ), status=status.HTTP_404_NOT_FOUND)