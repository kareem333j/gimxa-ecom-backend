from django.db.models import QuerySet
from rest_framework import serializers
from django.contrib.auth import get_user_model
from users.models import UserSettings, UserProfile, AdminProfile, UserActivityLog
from users.choices import Role
from users.utils import log_user_activity

User = get_user_model()

class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "full_name",
            "avatar",
            "role",
        )

class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = (
            "language_preference",
            "mode",
            "location",
        )

class UserPublicSerializer(serializers.ModelSerializer):
    settings = UserSettingsSerializer()
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "full_name",
            "role",
            "avatar",
            "is_verified",
            "provider",
            "settings"
        )

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["phone", "country", "city", "created_at", "updated_at"]

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ("phone", "country", "city")

class AdminProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminProfile
        fields = ["support_email", "support_whatsapp", "created_at"]

class AdminProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminProfile
        fields = ("support_email", "support_whatsapp")

class MyProfileSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    settings = UserSettingsSerializer()
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "full_name",
            "role",
            "avatar",
            "is_verified",
            "provider",
            "last_login",
            "date_joined",
            "last_updated",
            "profile",
            "settings"
        )
    
    def get_profile(self, obj):
        if obj.role == Role.ADMIN and hasattr(obj, "admin_profile"):
            return AdminProfileSerializer(obj.admin_profile).data

        if obj.role == Role.USER and hasattr(obj, "profile"):
            return UserProfileSerializer(obj.profile).data

        return None

class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActivityLog
        fields = [
            "id",
            "activity_type",
            "metadata",
            "timestamp",
            "ip_address",
            "user_agent",
        ]

class UserUpdateSerializer(serializers.ModelSerializer):
    settings = UserSettingsSerializer(required=False)
    profile = serializers.JSONField(required=False)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "full_name",
            "avatar",
            "profile",
            "settings",
        )

    def update(self, instance, validated_data):

        profile_data = validated_data.pop("profile", None)
        settings_data = validated_data.pop("settings", None)

        # update user
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # update settings
        if settings_data:
            serializer = UserSettingsSerializer(
                instance.settings,
                data=settings_data,
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

        # update profile
        if profile_data:
            if instance.role == Role.ADMIN:
                serializer = AdminProfileUpdateSerializer(
                    instance.admin_profile,
                    data=profile_data,
                    partial=True
                )
            else:
                serializer = UserProfileUpdateSerializer(
                    instance.profile,
                    data=profile_data,
                    partial=True
                )

            serializer.is_valid(raise_exception=True)
            serializer.save()

        return instance

class UserAdminListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "full_name",
            "role",
            "avatar",
            "is_verified",
            "provider",
            "last_login",
            "date_joined",
            "last_updated",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_hidden",
        )


class AdminCreateUserSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    is_superuser = serializers.BooleanField(required=False, default=False)
    is_staff = serializers.BooleanField(required=False, default=False)
    is_verified = serializers.BooleanField(required=False, default=False)
    is_active = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = User
        fields = (
            "email",
            "username",
            "password",
            "confirm_password",
            "full_name",
            "role",
            "is_superuser",
            "is_staff",
            "is_verified",
            "is_active",
            "avatar",
        )
        extra_kwargs = {
            "email": {"required": True},
            "username": {"required": True},
            "role": {"required": False},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        # Auto-set is_superuser and is_staff to True when role is admin
        role = data.get("role", Role.USER)
        if role == Role.ADMIN:
            data["is_superuser"] = True
            data["is_staff"] = True

        return data

    def create(self, validated_data):
        from django.db import transaction
        from users.utils import initialize_new_user

        validated_data.pop("confirm_password")
        password = validated_data.pop("password")

        if not validated_data.get("full_name"):
            validated_data["full_name"] = validated_data.get("username")

        with transaction.atomic():
            user = User.objects.create_user(password=password, **validated_data)

            initialize_new_user(
                user=user,
                request=self.context.get("request"),
                provider="email",
                via="admin_create",
            )

            # Log registration activity
            log_user_activity(
                user=user,
                activity_type=UserActivityLog.ActivityType.REGISTER,
                request=self.context.get("request"),
                metadata={
                    "auth": {
                        "flow": "register",
                        "status": "success",
                        "provider": "email",
                        "via": "admin_create",
                    }
                },
            )

            return user