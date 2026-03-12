from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model

from . import google
from django.conf import settings
from .register import register_social_user
import re

User = get_user_model()

class GoogleAuthSerializer(serializers.Serializer):
    auth_token = serializers.CharField()
    
    def validate_auth_token(self, auth_token):
        user_data = google.Google.validate(auth_token)
        request = self.context.get('request')
        
        if not user_data:
            raise serializers.ValidationError('The token is invalid or expired. Please login again.')
        
        email_verified = user_data.get("email_verified", False)
        
        if not email_verified:
            raise AuthenticationFailed("Google email not verified")
        
        if user_data['aud'] != settings.GOOGLE_CLIENT_ID:
            raise AuthenticationFailed('Audience does not match')
        
        user_id = user_data['sub']
        email = user_data['email']
        name = user_data.get('name', '') 
        
        # get base username from email
        base_username = email.split('@')[0]
        # remove any characters that are not alphanumeric, dot, underscore, or hyphen
        base_username = re.sub(r'[^a-zA-Z0-9._-]', '', base_username)

        username = base_username
        
        if User.objects.filter(username=username).exists():
            username = f"{username}_{user_id[:6]}"

        return register_social_user(
            user_id=user_id,
            username=username,
            email=email,
            name=name,
            request=request
        )