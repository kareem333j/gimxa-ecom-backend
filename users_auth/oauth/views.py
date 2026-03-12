from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    GoogleAuthSerializer,
)
from django.conf import settings
from users_auth.utils import set_auth_cookies


class GoogleSocialAuthView(APIView):
    permission_classes = []
    authentication_classes = []
    serializer_class = GoogleAuthSerializer

    def post(self, request):
        """
        POST with "auth_token"
        Send an id_token as from google to get user information
        """
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data["auth_token"]

        response = Response(data, status=status.HTTP_200_OK)

        set_auth_cookies(response, {"access": data["data"]["tokens"]["access"], "refresh": data["data"]["tokens"]["refresh"]})

        return response