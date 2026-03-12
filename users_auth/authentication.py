from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.contrib.auth import get_user_model

User = get_user_model()


class CookieJWTAuthentication(JWTAuthentication):
    """
    Authentication class that authenticates requests using JWT tokens stored in cookies.
    """
    def authenticate(self, request):
        access_token = request.COOKIES.get("access")

        if not access_token:
            raise AuthenticationFailed("Authentication credentials were not provided.!")

        try:
            validated_token = self.get_validated_token(access_token)
        except InvalidToken:
            raise AuthenticationFailed("Invalid token")
        except TokenError:
            raise AuthenticationFailed("Token has expired")
        except AuthenticationFailed as e:
            raise AuthenticationFailed(str(e))
        except Exception:
            raise AuthenticationFailed(
                "Authentication failed due to an unexpected error."
            )
        user = self.get_user(validated_token)
        
        return user, validated_token


from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

class OptionalJWTAuthentication(BaseAuthentication):
    """
    Try JWT auth but allow anonymous users.
    """
    def authenticate(self, request):
        jwt_auth = JWTAuthentication()
        auth_header = request.META.get("HTTP_AUTHORIZATION", None)
        cookie_token = request.COOKIES.get("access")

        # use cookie token if no header
        if cookie_token and not auth_header:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {cookie_token}"

        try:
            return jwt_auth.authenticate(request)
        except Exception:
            return None  # never fail, allow anonymous users