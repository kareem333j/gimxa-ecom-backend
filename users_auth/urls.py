from django.urls import path
from .views import *
from .oauth.views import GoogleSocialAuthView

urlpatterns = [
    # auth
    path('csrf-token/', GetCSRFTokenView.as_view(), name='get_csrf_token'),
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email-otp/', VerifyEmailOTPView.as_view(), name='verify-email-otp'),
    path('resend-email-otp/', OTPResendView.as_view(), name='resend-email-otp'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('refresh/', RefreshTokenView.as_view(), name='refresh'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path("forgot-password/", ForgotPasswordRequestView.as_view(), name="forgot-password"),
    path("reset-password/<uidb64>/<token>/", ResetPasswordView.as_view(), name="forgot-password-confirm"),
    
    # oauth
    path('o2/google/', GoogleSocialAuthView.as_view(), name='google-oauth'),
    
    # test and utility
    path('test/', TestView.as_view(), name='test'),
    path('clear-cache/', ClearCacheView.as_view(), name='clear-cache'),
]