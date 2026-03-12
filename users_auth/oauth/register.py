import re

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import UserActivityLog
from users.serializers import UserPublicSerializer
from users.utils import log_user_activity, initialize_new_user
from users_auth.utils import recored_access_labels

User = get_user_model()


EMAIL_REGEX = r"[^@]+@[^@]+\.[^@]+"


def _generate_tokens(user):
    refresh = RefreshToken.for_user(user)
    access = recored_access_labels(refresh.access_token, user)
    return {
        "access": str(access),
        "refresh": str(refresh),
    }


def _log_activity(user, activity_type, request, metadata):
    log_user_activity(
        user=user,
        activity_type=activity_type,
        request=request,
        metadata=metadata,
    )


def register_social_user(user_id, username, email, name, request=None):
    if not re.match(EMAIL_REGEX, email):
        raise AuthenticationFailed(
            "No valid email returned from provider, Please sign up using your email and password."
        )

    user = User.objects.filter(email=email).first()

    if user:
        if user.provider != "google":
            raise AuthenticationFailed(
                "This email is registered with email/password login."
            )

        if user.google_id and user.google_id != user_id:
            raise AuthenticationFailed("Invalid Google account for this user.")

        tokens = _generate_tokens(user)

        _log_activity(
            user=user,
            activity_type=UserActivityLog.ActivityType.LOGIN,
            request=request,
            metadata={
                "auth": {
                    "flow": "login",
                    "status": "success",
                    "provider": "google",
                    "via": "google",
                },
                "details": {
                    "request": "request to login user via google",
                    "message": "User logged in successfully",
                },
            },
        )

    else:
        user = User.objects.create_user(
            username=username,
            email=email,
            provider="google",
            google_id=user_id,
            is_active=True,
            is_verified=True,
        )

        user.set_unusable_password()
        user.full_name = name or username
        user.save()

        initialize_new_user(
            user=user,
            request=request,
            provider="google",
            via="google",
        )

        tokens = _generate_tokens(user)
        
    return {
        "data": {
            "tokens": tokens,
            "user": UserPublicSerializer(user).data,
        },
        "message": "Login successful",
    }
