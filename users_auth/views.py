from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from permissions.custom import AdminPermission
from rest_framework.response import Response
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.conf import settings
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from cart.utils.helpers import merge_cookie_cart_to_db

from users_auth.utils import recored_access_labels
from .serializers import (
    RegisterSerializer,
    ChangePasswordSerializer,
    ResetPasswordSerializer,
    ResendOTPSerializer
)
from users.serializers import UserSimpleSerializer, UserPublicSerializer
from django.contrib.auth import authenticate
from users.utils import (
    generate_otp,
    otp_expiry_time,
    send_html_email,
    rate_limit,
    get_client_ip,
    is_login_locked,
    record_login_failure,
    reset_login_failures,
)
from users.models import EmailOTP
from django.contrib.auth import get_user_model
from .authentication import CookieJWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from users.models import UserActivityLog
from users.utils import (
    log_user_activity,
)
from .utils import set_auth_cookies
# generators
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.core.cache import cache
from rest_framework.exceptions import Throttled
from django.utils import timezone

User = get_user_model()
token_generator = PasswordResetTokenGenerator()


# CSRF Token Exempt View
class GetCSRFTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        token = get_token(request)
        response = JsonResponse({"csrfToken": token})
        response.set_cookie(
            "csrftoken",
            token,
            max_age=60 * 60 * 24,
            secure=getattr(settings, "CSRF_COOKIE_SECURE", False),
            httponly=False,
            samesite=getattr(settings, "CSRF_COOKIE_SAMESITE", "None"),
            path="/",
        )
        return response


# User Registration View
class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        data = request.data
        username = data.get("username")
        email = data.get("email")

        # 🔒 RATE LIMIT (OTP SEND)
        try:
            ip = get_client_ip(request)
            rate_limit(
                key=f"otp:send:email:{email}",
                limit=3,
                ttl=15 * 60  # 15 minutes
            )
            rate_limit(
                key=f"otp:send:ip:{ip}",
                limit=10,
                ttl=15 * 60
            )
        except Throttled as e:
            return Response(
                {"error": str(e.detail)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        
        serializer = RegisterSerializer(data=data, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        # generate otp
        otp_code = generate_otp()

        EmailOTP.objects.create(
            user=user,
            otp=otp_code,
            expires_at=otp_expiry_time(5),
        )

        # send email
        send_html_email(
            subject="Verify your account",
            to_email=email,
            context={
                "user": user,
                "otp": otp_code,
                "date": timezone.now().strftime("%d %B, %Y"),
            },
            email_type="otp",
        )

        return Response(
            {
                "data": {"id": user.id, "username": username, "email": email},
                "message": "Account created successfully. Please check your email for OTP.",
            },
            status=status.HTTP_201_CREATED,
        )


# User Verification View
class VerifyEmailOTPView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")

        if not email or not otp:
            return Response(
                {"message": "Email and OTP are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
            
        # 🔒 RATE LIMIT (OTP VERIFY)
        try:
            ip = get_client_ip(request)
            rate_limit(
                key=f"otp:verify:email:{email}",
                limit=5,
                ttl=10 * 60  # 10 minutes
            )
            rate_limit(
                key=f"otp:verify:ip:{ip}",
                limit=20,
                ttl=10 * 60
            )
        except Throttled as e:
            return Response(
                {"error": str(e.detail)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"message": "If the email exists, an OTP has been sent."},
                status=status.HTTP_200_OK,
            )

        if user.is_verified:
            return Response(
                {"message": "User is already verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )
            
        key = f"otp:{user.id}"
        attempts = cache.get(key, 0)

        if attempts >= 5:
            return Response(
                {"error": "Too many OTP attempts. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            otp_obj = EmailOTP.objects.filter(
                user=user,
                otp=otp,
                is_used=False,
            ).latest("created_at")
        except EmailOTP.DoesNotExist:
            cache.set(key, attempts + 1, timeout=10 * 60)
            return Response(
                {"message": "Invalid OTP"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_obj.is_expired():
            cache.set(key, attempts + 1, timeout=10 * 60)
            return Response(
                {"message": "OTP has expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # success
        EmailOTP.objects.filter(user=user, is_used=False).update(is_used=True)
        user.is_verified = True
        user.is_active = True
        user.save()

        cache.delete(key)
        cache.delete(f"otp:verify:email:{email}")
        cache.delete(f"otp:verify:ip:{ip}")
        
        # generate tokens
        refresh = RefreshToken.for_user(user)
        access = recored_access_labels(refresh.access_token, user)

        response = Response(
            {
                "message": "Account verified successfully",
                "data": {"user": UserPublicSerializer(user).data},
            },
            status=status.HTTP_200_OK,
        )

        set_auth_cookies(response, {"access": access, "refresh": refresh})
        merge_cookie_cart_to_db(request, response, user) # merge cookie cart to db
        # record verification activity
        log_user_activity(
            user=user,
            activity_type=UserActivityLog.ActivityType.VERIFY_EMAIL,
            request=request,
            metadata={
                "auth": {
                    "flow": "verify_email",
                    "method": "unauthenticated",
                    "status": "success",
                },
                "details": {
                    "request": "request to verify email with otp",
                    "message": "Email has been verified successfully"
                }
            },
        )
        return response

# resend otp
class OTPResendView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # 🔒 RATE LIMIT (OTP SEND)
        try:
            ip = get_client_ip(request)
            rate_limit(
                key=f"otp:send:email:{email}",
                limit=3,
                ttl=15 * 60  # 15 minutes
            )
            rate_limit(
                key=f"otp:send:ip:{ip}",
                limit=10,
                ttl=15 * 60
            )
        except Throttled as e:
            return Response(
                {"error": str(e.detail)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"message": "If the email exists, an OTP has been sent."},
                status=status.HTTP_200_OK
            )

        if user.is_verified:
            return Response(
                {"message": "User is already verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # delete old otps
        EmailOTP.objects.filter(user=user).delete()
        
        # generate new otp
        otp_code = generate_otp()

        EmailOTP.objects.create(
            user=user,
            otp=otp_code,
            expires_at=otp_expiry_time(5),
        )

        # send email
        send_html_email(
            subject="Verify your account",
            to_email=email,
            context={
                "user": user,
                "otp": otp_code,
                "date": timezone.now().strftime("%d %B, %Y"),
            },
            email_type="otp",
        )

        # record resend otp activity
        log_user_activity(
            user=user,
            activity_type=UserActivityLog.ActivityType.RESEND_OTP,
            request=request,
            metadata={
                "auth": {
                    "flow": "resend_otp",
                    "method": "unauthenticated",
                    "status": "success",
                },
                "details": {
                    "request": "request to resend otp",
                    "message": "OTP has been resent successfully"
                }
            },
        )

        return Response(
            {
                "message":"OTP send successfully, Please check your email for OTP."
            },
            status=status.HTTP_200_OK
        )


# User Login View
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        data = request.data
        email = data.get("email")
        password = data.get("password")

        if is_login_locked(email):
            return Response(
                {"error": "Account temporarily locked. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        
        try:
            user = authenticate(request, email=email, password=password)
            if user is None:
                result = record_login_failure(email)

                if result["locked"]:
                    return Response(
                        {"error": "Too many failed attempts. Account locked temporarily."},
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                    
                return Response(
                    {"error": "Invalid email or password"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if not user.is_active:
                return Response(
                    {"error": "User account is disabled"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if not user.is_verified:
                # 🔒 RATE LIMIT (OTP RESEND)
                try:
                    ip = get_client_ip(request)
                    rate_limit(
                        key=f"otp:send:email:{user.email}",
                        limit=3,
                        ttl=15 * 60
                    )
                    rate_limit(
                        key=f"otp:send:ip:{ip}",
                        limit=10,
                        ttl=15 * 60
                    )
                except Throttled as e:
                    return Response(
                        {"error": str(e.detail)},
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
            
                otp_code = generate_otp()

                EmailOTP.objects.create(
                    user=user,
                    otp=otp_code,
                    expires_at=otp_expiry_time(5),
                )

                send_html_email(
                    subject="Verify your account",
                    to_email=user.email,
                    context={
                        "user": user,
                        "otp": otp_code,
                        "date": timezone.now().strftime("%d %B, %Y"),
                    },
                    email_type="otp",
                )

                return Response(
                    {
                        "message": "Account not verified. A new OTP has been sent to your email."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            refresh = RefreshToken.for_user(user)
            access = recored_access_labels(refresh.access_token, user)
            
            reset_login_failures(email)
            cache.delete(f"otp:send:email:{email}")
            cache.delete(f"otp:send:ip:{get_client_ip(request)}") 

            # record login activity
            log_user_activity(
                user=user,
                activity_type=UserActivityLog.ActivityType.LOGIN,
                request=request,
                metadata={
                    "auth": {
                        "flow": "login",
                        "status": "success",
                        "via": "password",
                        "provider": "email",
                    },
                    "details": {
                        "request": "request to login user via email and password",
                        "message": "User logged in successfully"
                    }
                },
            )

            response = Response(
                {
                    "message": "Login successful",
                    "data": {"user": UserPublicSerializer(user).data},
                },
                status=status.HTTP_200_OK,
            )
            set_auth_cookies(response, {"access": access, "refresh": refresh})
            merge_cookie_cart_to_db(request, response, user) # merge cookie cart to db
            return response
            

        except Exception as e:
            import logging
            logger = logging.getLogger("django")
            logger.error("Login error", exc_info=True)
            return Response(
                {"error": "An error occurred during login"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# User Logout View
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, *args, **kwargs):
        # use token blacklist if you enabled it in settings.py
        refresh_token = request.COOKIES.get("refresh")
        user = request.user
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()  # blacklist the refresh token
            except Exception:
                pass
        ## clear cookies
        response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
        response.delete_cookie("access", path="/", domain=None, samesite="None")
        response.delete_cookie("refresh", path="/", domain=None, samesite="None")
        response.delete_cookie(
            "sessionid", path="/", domain=None, samesite="None"
        )
        # record logout activity
        log_user_activity(
            user=user,
            activity_type=UserActivityLog.ActivityType.LOGOUT,
            request=request,
            metadata={
                "auth": {
                    "flow": "logout",
                    "status": "success",
                },
                "security": {
                    "tokens_revoked": True,
                    "logout_type": "manual",
                    "refresh_blacklisted": bool(refresh_token),
                },
                "details": {
                    "request": "request to logout user",
                    "message": "User logged out successfully",
                },
            },
        )
        return response


# Token Refresh View (**with rotation)
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
class RefreshTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token not provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            old_refresh = RefreshToken(refresh_token)
            user_id = old_refresh["user_id"]
        except TokenError:
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user.is_active:
            return Response(
                {"error": "User account is disabled"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not user.is_verified:
            return Response(
                {"error": "User account is not verified"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access = serializer.validated_data["access"]
        new_refresh = serializer.validated_data.get("refresh")

        response = Response(
            {
                "message": "Access token refreshed successfully",
                "data": {"user": UserPublicSerializer(user).data},
            },
            status=status.HTTP_200_OK,
        )

        set_auth_cookies(response, {"access": access, "refresh": new_refresh})

        return response


# password management views
# change password view
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def put(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        reset_login_failures(request.user.email)

        # blacklisting refresh token
        refresh_token = request.COOKIES.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()  # blacklist the refresh token
            except Exception:
                pass

        # record password change activity
        user = request.user
        log_user_activity(
            user=user,
            activity_type=UserActivityLog.ActivityType.CHANGE_PASSWORD,
            request=request,
            metadata={
                "auth": {
                    "flow": "change_password",
                    "method": "authenticated",
                    "status": "success",
                },
                "security": {
                    "tokens_revoked": True,
                },
                "details": {
                    "request": "request to change password",
                    "message": "Password changed successfully"
                }
            },
        )

        response = Response(
            {"message": "Password updated successfully"}, status=status.HTTP_200_OK
        )
        # clear cookies
        response.delete_cookie("access", path="/", samesite="None")
        response.delete_cookie("refresh", path="/", samesite="None")
        return response


# forgot password
class ForgotPasswordRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
            )
            
        # 🔒 RATE LIMIT (RESET PASSWORD)
        try:
            ip = get_client_ip(request)
            rate_limit(
                key=f"reset:email:{email}",
                limit=3,
                ttl=60 * 60  # 1 hour
            )
            rate_limit(
                key=f"reset:ip:{ip}",
                limit=10,
                ttl=60 * 60
            )
        except Throttled as e:
            return Response(
                {"error": str(e.detail)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "If this email exists, you will receive a reset link"},
                status=status.HTTP_200_OK,
            )

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        
        reset_link = request.build_absolute_uri(
            f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}"
        )
        
        send_html_email(
            subject="Reset your password",
            to_email=user.email,
            context={
                "username": user.username,
                "email": user.email,
                "reset_link": reset_link,
                "date": timezone.now().strftime("%d %B, %Y"),
            },
            email_type="reset",
        )
        
        # record forgot password activity
        log_user_activity(
            user=user,
            activity_type=UserActivityLog.ActivityType.FORGOT_PASSWORD,
            request=request,
            metadata={
                "auth": {
                    "flow": "forgot_password",
                    "method": "unauthenticated",
                    "status": "success",
                },
                "security": {
                    "reset_link_sent": True,
                },
                "details": {
                    "request": "request to send password reset link via email",
                    "message": "Password reset link sent to email"
                }
            },
        )

        return Response(
            {"detail": "If this email exists, you will receive a reset link"},
            status=status.HTTP_200_OK,
        )


# reset password
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get_user_from_uid(self, uidb64):
        """Helper method to decode uid and get user instance."""
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            return User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None

    def get(self, request, uidb64, token):
        """Check if reset link (token) is valid."""
        user = self.get_user_from_uid(uidb64)

        if user is None or not token_generator.check_token(user, token):
            return Response(
                {"error": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Password reset link is valid"}, status=status.HTTP_200_OK
        )

    def post(self, request, uidb64, token):
        """Reset the user's password if token is valid."""
        user = self.get_user_from_uid(uidb64)

        if user is None or not token_generator.check_token(user, token):
            return Response(
                {"error": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ResetPasswordSerializer(
            data=request.data, context={"request": request, "user": user}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        
        cache.delete(f"reset:email:{user.email}")
        cache.delete(f"login:fail:{user.email}") 
        cache.delete(f"login:lock:{user.email}") 
        cache.delete(f"login:level:{user.email}")
        
        # record password reset activity
        log_user_activity(
            user=user,
            activity_type=UserActivityLog.ActivityType.RESET_PASSWORD,
            request=request,
            metadata={
                "auth": {
                    "flow": "reset_password",
                    "method": "unauthenticated",
                    "status": "success",
                },
                "security": {
                    "reset_link_validated": True,
                },
                "details": {
                    "request": "request to reset password",
                    "message": "Password has been reset successfully"
                }
            },
        )

        return Response(
            {"detail": "Password has been reset successfully"},
            status=status.HTTP_200_OK,
        )


class TestView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        user = request.user
        return Response(
            {
                "data": {"user": UserSimpleSerializer(user).data},
                "message": "You have accessed a protected endpoint."
            },
            status=status.HTTP_200_OK,
        )
        
class ClearCacheView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request):
        from django.core.cache import cache
        cache.clear()
        return Response({"message": "Cache cleared"})
