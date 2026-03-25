from decimal import Decimal
from payments.models import ExchangeRateSnapshot
from users.utils import get_client_ip, get_user_location

class CurrencyService:
    def __init__(self):
        self.snapshot = ExchangeRateSnapshot.objects.first()
        self.rates = self.snapshot.rates if self.snapshot else {}

    def convert(self, amount, to_currency, from_currency="USD"):
        if not amount:
            return amount

        amount = Decimal(amount)

        if to_currency == from_currency:
            return amount

        try:
            # Helper to get rate, defaulting USD to 1.0
            def get_rate(curr):
                if curr == "USD":
                    return Decimal("1.0")
                return Decimal(self.rates[curr])

            if from_currency == "USD":
                return amount * get_rate(to_currency)

            amount_in_usd = amount / get_rate(from_currency)
            return amount_in_usd * get_rate(to_currency)

        except (KeyError, ZeroDivisionError, Exception):
            return amount  # fallback

    def get_supported_currency(self, currency):
        if not currency or str(currency).upper() == "USD":
            return "USD"
        
        target = str(currency).upper()
        if target in self.rates or f"USD{target}" in self.rates:
            return target
        
        return "USD"

def get_user_currency(request):
    user = getattr(request, "user", None)
    currency = "USD"

    if user and user.is_authenticated:
        currency = getattr(user.settings, "currency", "USD")
    else:
        ip_address = get_client_ip(request) if request else None
        location = get_user_location(ip_address) if ip_address else None
        try:
            country = location.split(",")[1].strip() if (location and "," in location) else location
            from users.utils import COUNTRY_CURRENCY_MAP
            currency = COUNTRY_CURRENCY_MAP.get(country, "USD")
        except Exception:
            currency = "USD"
    
    # Validate currency against available rates
    try:
        service = CurrencyService()
        return service.get_supported_currency(currency)
    except Exception:
        return "USD"


