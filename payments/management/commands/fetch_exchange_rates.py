import json
import logging
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from payments.models import ExchangeRateSnapshot
# from django.utils import timezone

logger = logging.getLogger(__name__)

CURRENCIES = [
    "USD", "EUR", "GBP", "EGP", "CHF", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF",
    "RON", "CAD", "BRL", "MXN", "ARS", "CLP", "JPY", "KRW", "CNY", "HKD", "TWD",
    "SGD", "MYR", "THB", "INR", "IDR", "PHP", "VND", "SAR", "AED", "QAR", "KWD",
    "BHD", "OMR", "TRY", "ZAR", "NGN"
]

class Command(BaseCommand):
    help = 'Fetches daily exchange rates from exchangerate.host and updates the ExchangeRateSnapshot model'

    def handle(self, *args, **options):
        api_key = getattr(settings, 'EXCHANGERATE_API_KEY', None)
        if not api_key:
            self.stdout.write(self.style.ERROR("Error: EXCHANGERATE_API_KEY is not set in settings."))
            return

        currencies_list = ",".join(CURRENCIES)
        base_currency = "USD"
        
        url = f"http://api.exchangerate.host/live?access_key={api_key}&currencies={currencies_list}&source={base_currency}"

        self.stdout.write(f"Fetching exchange rates from {url}...")
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get('success'):
                # API returns quotes like {"USDUSD": 1, "USDEUR": 0.85}
                # We can strip the 'USD' prefix for the keys if we want, or store as is.
                rates = {}
                quotes = data.get('quotes', {})
                for key, val in quotes.items():
                    # If base is USD, key will be like USDXXX. We can just take the last 3 chars or store as is
                    if key.startswith(base_currency) and len(key) == 6:
                        rates[key[3:]] = val
                    else:
                        rates[key] = val

                # Get or create the snapshot instance. Since we only take snapshot once, 
                # we can either create a new one, or update the single row (base="USD").
                # Depends on if we are keeping history. The model looks like it might hold one latest snapshot or keeping history.
                # Let's see model def: "ExchangeRateSnapshot(base, rates, last_updated)". No Unique constraints.
                # Usually we can get_or_create by base="USD" and just update rates to keep it 1 row.
                
                snapshot, created = ExchangeRateSnapshot.objects.get_or_create(base=base_currency, defaults={'rates': rates})
                if not created:
                    snapshot.rates = rates
                    snapshot.save()

                self.stdout.write(self.style.SUCCESS(f"Successfully updated exchange rates for {len(rates)} currencies. (Created recent snapshot: {created})"))
            else:
                error_info = data.get('error', {})
                self.stdout.write(self.style.ERROR(f"Failed to fetch rates: {error_info.get('info', 'Unknown error')}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Exception occurred while fetching exchange rates: {e}"))
            logger.exception("Failed to fetch exchange rates")
