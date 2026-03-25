from django.db import models
from django.contrib.auth.models import (
    BaseUserManager,
    AbstractBaseUser,
    PermissionsMixin,
)
import uuid
from .choices import (
    Role, 
    AUTH_PROVIDERS, 
    LANGUAGES, 
    COLOR_MODES,
    CURRENCIES
)
from django.utils import timezone

class UserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def for_user(self, user):
        if user and user.is_superuser:
            return self
        return self.active()

class CustomUserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        if not username:
            raise ValueError("Username is required")

        email = self.normalize_email(email)

        extra_fields.setdefault("role", Role.USER)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_verified", False)

        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("full_name", "Admin User")
        extra_fields.setdefault("role", Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")

        return self.create_user(email, username, password, **extra_fields)

    def get_queryset(self):
        return UserQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def for_user(self, user):
        return self.get_queryset().for_user(user)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    full_name = models.CharField(max_length=300, blank=True, null=True)

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.USER, db_index=True
    )

    avatar = models.PositiveIntegerField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)

    last_login = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    provider = models.CharField(
        max_length=50, choices=AUTH_PROVIDERS, default="email", db_index=True
    )
    google_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.username or self.email

class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        limit_choices_to={"role": Role.USER},
    )

    phone = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile - {self.user.username or self.user.email}"


class AdminProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="admin_profile",
        limit_choices_to={"role": Role.ADMIN},
    )

    support_email = models.EmailField(blank=True, null=True)
    support_whatsapp = models.CharField(max_length=20, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Admin - {self.user.username or self.user.email}"


class UserActivityLog(models.Model):
    class ActivityType(models.TextChoices):
        REGISTER = "register", "Register"
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        REFRESH_TOKEN = "refresh_token", "Refresh Token"
        CHANGE_PASSWORD = "change_password", "Change Password"
        FORGOT_PASSWORD = "forgot_password", "Forgot Password"
        RESET_PASSWORD = "reset_password", "Reset Password"
        VERIFY_EMAIL = "verify_email", "Verify Email"
        RESEND_OTP = "resend_otp", "Resend OTP"
        ORDER_CREATE = "order_create", "Order Create"
        ORDER_CANCEL = "order_cancel", "Order Cancel"
        PAYMENT_SUCCESS = "payment_success", "Payment Success"
        PAYMENT_FAIL = "payment_fail", "Payment Fail"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="activity_logs",
        db_index=True,
    )
    activity_type = models.CharField(
        max_length=50,
        choices=ActivityType.choices,
        db_index=True,
    )
    
    metadata = models.JSONField(null=True, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["activity_type", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.activity_type} - {self.timestamp}"


class UserSettings(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="settings", db_index=True
    )

    location = models.CharField(max_length=255, blank=True, null=True)
    mode = models.CharField(max_length=50, choices=COLOR_MODES.choices, default=COLOR_MODES.DARK)
    language_preference = models.CharField(
        max_length=50, choices=LANGUAGES.choices, default=LANGUAGES.EN
    )
    currency = models.CharField(max_length=4, choices=CURRENCIES.choices, default=CURRENCIES.USD)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings - {self.user.username or self.user.email}"


class EmailOTP(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="email_otps"
    )
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"OTP for {self.user.email}"