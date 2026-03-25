from rest_framework.views import APIView
from permissions.custom import AdminPermission
from users_auth.authentication import CookieJWTAuthentication
from users.serializers import (
    UserAdminListSerializer,
    AdminCreateUserSerializer,
    UserUpdateSerializer,
    MyProfileSerializer
)
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Q
from core.pagination import DynamicPageNumberPagination
from core.response_schema import get_response_schema_1
from cache.utils import format_filter_value
from rest_framework import status
import uuid

User = get_user_model()


class UserListView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]
    ALLOWED_FILTERS = ["role", "is_active", "provider", "is_verified"]
    
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
                        filter_dict[k] = format_filter_value(v)
                    else:
                        return Response(get_response_schema_1(
                            message="Invalid filter parameter",
                            status=400
                        ), status=400)

        queryset = User.objects.all()
        if filter_dict:
            queryset = queryset.filter(**filter_dict)
        if search_query:
            search_filter = (
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(full_name__icontains=search_query)
            )

            try:
                uuid.UUID(search_query)
                search_filter |= Q(id=search_query)
            except ValueError:
                pass

            queryset = queryset.filter(search_filter)

        page = paginator.paginate_queryset(queryset, request)

        serializer = UserAdminListSerializer(page, many=True)
        data = paginator.get_paginated_response(serializer.data).data
        
        return Response(get_response_schema_1(
            message="Users retrieved successfully",
            status=200,
            data=data
        ), status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AdminCreateUserSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        return Response(get_response_schema_1(
            message="User created successfully",
            status=201,
            data=UserAdminListSerializer(user).data
        ), status=status.HTTP_201_CREATED)


class UserDetail(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def patch(self, request, user_id):
        try:
            user = User.objects.get(id = user_id)
        except:
            return Response(
                get_response_schema_1(
                    data=None,
                    message="User not found",
                    status=404
                ), status=status.HTTP_404_NOT_FOUND
            )

        serializer = UserUpdateSerializer(
            user,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        user_serializer = MyProfileSerializer(user)

        return Response(
            get_response_schema_1(
                data=user_serializer.data,
                message="Profile updated successfully",
                status=200
            ), status=status.HTTP_200_OK
        )

    def delete(self, _request, user_id):
        try:
            user = User.objects.get(id = user_id)
        except:
            return Response(
                get_response_schema_1(
                    data=None,
                    message="User not found",
                    status=404
                ), status=status.HTTP_404_NOT_FOUND
            )

        user.delete()
        return Response(
            get_response_schema_1(
                data=None,
                message="User deleted successfully",
                status=200
            ), status=status.HTTP_200_OK
        )