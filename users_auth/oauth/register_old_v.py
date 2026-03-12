from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed
import re

from users.models import UserActivityLog
from users.serializers import UserSimpleSerializer
from users.utils import log_user_activity
from users_auth.utils import recored_access_labels

User = get_user_model()

def register_social_user(user_id, username, email, name, request=None):
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise AuthenticationFailed(
            detail='No valid email returned from provider, Please sign up using your email and password.'
        )
        
    filtered_user_by_email = User.objects.filter(email=email)

    if filtered_user_by_email.exists():
        user = User.objects.get(email=email)
        
        if user.provider != "google":
            raise AuthenticationFailed(
                "This email is registered with email/password login."
            )
        
        if user.google_id and user.google_id != user_id:
            raise AuthenticationFailed("Invalid Google account for this user.")
        
        refresh = RefreshToken.for_user(user)
        access = recored_access_labels(refresh.access_token, user)

        # record login activity
        log_user_activity(
            user=user,
            activity_type=UserActivityLog.ActivityType.LOGIN,
            request=request,
            metadata={
                "auth": {
                    "flow": "login",
                    "status": "success",
                    "via": "google",
                    "provider": "google",
                },
                "details": {
                    "request": "request to login user via google",
                    "message": "User logged in successfully"
                }
            },
        )
        
        return {
            "data":{
                "tokens":{
                    'access': str(access),
                    'refresh': str(refresh),
                },
                "user": UserSimpleSerializer(user).data
            },
            'message': 'Login successful'
        }
    else:
        user = User.objects.create_user(
            username=username,
            email=email,
            provider='google',
            google_id=user_id
        )
        user.set_unusable_password()
        user.is_active = True
        if not name:
            user.full_name = user.username
        else:
            user.full_name = name
        user.save()
        

        refresh = RefreshToken.for_user(user)
        access = recored_access_labels(refresh.access_token, user)
        
        # record registration activity
        log_user_activity(
            user=user,
            activity_type=UserActivityLog.ActivityType.REGISTER,
            request=request,
            metadata={
                "auth": {
                    "flow": "register",
                    "status": "success",
                    "provider": "google",
                    "via": "google"
                }
            },
        )

        return {
            "data":{
                "tokens":{
                    'access': str(access),
                    'refresh': str(refresh),
                },
                "user": UserSimpleSerializer(user).data
            },
            'message': 'Login successful'
        }