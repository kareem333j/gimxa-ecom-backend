from rest_framework import serializers
from payments.services.currency_service import CurrencyService, get_user_currency


class CurrencySerializerMixin(serializers.Serializer):
    currency = serializers.SerializerMethodField()

    PRICE_FIELDS = []  # تحددها في كل serializer

    def _convert_prices(self, data):
        request = self.context.get("request")
        currency = get_user_currency(request)

        service = CurrencyService()

        for field in self.PRICE_FIELDS:
            if field in data and data[field] is not None:
                data[field] = str(
                    round(service.convert(data[field], currency), 2)
                )

        return data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data = self._convert_prices(data)
        data["currency"] = self.get_currency(instance)
        return data

    def get_currency(self, obj):
        request = self.context.get("request")
        return get_user_currency(request)