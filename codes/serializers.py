from rest_framework import serializers
from codes.models import FulfillmentCode


class FulfillmentCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FulfillmentCode
        fields = ["id", "code", "is_used", "used_at", "created_at"]
        read_only_fields = ["id", "is_used", "used_at", "created_at"]


class PackageWithCodesSerializer(serializers.Serializer):
    """
    Serializer used when returning all TopUpPackage objects
    along with their associated FulfillmentCodes.
    """
    package_id = serializers.IntegerField()
    package_name = serializers.CharField()
    total_codes = serializers.IntegerField()
    available_codes = serializers.IntegerField()
    codes = FulfillmentCodeSerializer(many=True)


# Legacy serializer kept for backward compatibility with existing endpoints
class CodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FulfillmentCode
        fields = ["id", "code", "is_used", "used_at", "created_at"]
        read_only_fields = ["id", "is_used", "used_at", "created_at"]