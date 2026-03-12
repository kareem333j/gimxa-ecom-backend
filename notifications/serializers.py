from rest_framework import serializers
from .models import Notification

class NotificationPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "subject",
            "message",
            "is_read",
            "created_at",
            "readed_at",
        ]

class NotificationAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'