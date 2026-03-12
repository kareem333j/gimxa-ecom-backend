from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from django.contrib.auth.password_validation import validate_password as dj_validate_password
from users.utils import initialize_new_user

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}, required=True
    )

    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'confirm_password', 'full_name')
        extra_kwargs = {
            "password": {
                "write_only": True,
                "error_messages": {
                    "blank": "Password field cannot be empty or whitespace.",
                    "required": "Password field is required.",
                },
            },
            "email": {
                "required": True,
                "allow_blank": False,
                "allow_null": False,
                "error_messages": {
                    "blank": "email field cannot be empty or whitespace.",
                    "required": "email field is required.",
                },
            },
            "username": {
                "required": True,
                "allow_blank": False,
                "allow_null": False,
                "max_length": 150,
                "error_messages": {
                    "blank": "username field cannot be empty or whitespace.",
                    "required": "username field is required."
                }
            },
        }
        
    def validate_email(self, email):
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("Email already exists.")
        return email

    def validate_username(self, username):
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError("Username already exists.")
        return username
    
    def validate_password(self, password):
        if len(password) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        return password
        
    def validate(self, data):
        # validate passwords match
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match.")
        
        return data

    def create(self, validated_data):
        request = self.context.get("request")

        password = validated_data.pop("password")
        validated_data.pop("confirm_password")

        try:
            with transaction.atomic():
                # create user
                user = User.objects.create_user(
                    password=password,
                    **validated_data
                )

                # set default full_name if not provided
                if not user.full_name:
                    user.full_name = user.username
                    user.save(update_fields=["full_name"])

                initialize_new_user(
                    user=user,
                    request=request,
                    provider="email",
                    via="password",
                )

                return user

        except Exception:
            raise serializers.ValidationError(
                "User could not be created, please try again."
            )
            
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    
    def validate_old_password(self, value):
        if not value.strip():
            raise serializers.ValidationError("Old password field cannot be empty or whitespace.")
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    
    def validate_new_password(self, value):
        user = self.context['request'].user
        dj_validate_password(value, user=user)
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Password fields didn't match."})
        if attrs['new_password'] == attrs['old_password']:
            raise serializers.ValidationError({"new_password": "New password cannot be the same as the old password."})
        return attrs
    
    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
    
class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    
    def validate_new_password(self, value):
        user = self.context['request'].user
        dj_validate_password(value, user=user)
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Password fields didn't match."})
        return attrs
    
    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user

class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()