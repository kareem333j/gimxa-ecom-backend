from django.contrib.gis.geoip2 import GeoIP2
from geoip2.errors import AddressNotFoundError
import random
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from .models import UserActivityLog

def generate_otp():
    return str(random.randint(100000, 999999))

def otp_expiry_time(minutes=10):
    return timezone.now() + timedelta(minutes=minutes)


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip

def get_user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")


def get_user_location(ip_address):
    try:
        geo = GeoIP2()
        data = geo.city(ip_address)

        country = data.get("country_name")
        city = data.get("city")

        if city and country:
            return f"{city}, {country}"
        return country

    except AddressNotFoundError:
        return None
    except Exception:
        return None

from user_agents import parse

def parse_user_agent(user_agent_string: str):
    user_agent = parse(user_agent_string)

    return {
        "device": (
            "mobile" if user_agent.is_mobile else
            "tablet" if user_agent.is_tablet else
            "pc"
        ),
        "os": f"{user_agent.os.family} {user_agent.os.version_string}",
        "browser": f"{user_agent.browser.family} {user_agent.browser.version_string}",
        "is_bot": user_agent.is_bot,
    }
    
def log_user_activity(*, user, activity_type, request=None, metadata=None):
    ip = get_client_ip(request) if request else "0.0.0.0"
    user_agent = get_user_agent(request) if request else "internal/system"
    device_info = parse_user_agent(user_agent) if request else {}

    UserActivityLog.objects.create(
        user=user,
        activity_type=activity_type,
        ip_address=ip if ip != "0.0.0.0" else None,
        user_agent=user_agent if user_agent != "internal/system" else None,
        metadata={
            "device": device_info,
            "geo": {
                "location": get_user_location(ip) if ip != "0.0.0.0" else None,
                "ip": ip,
            },
            **(metadata or {}),
        },
    )

# import to sending html email
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
    
def send_html_email(subject, to_email, context, email_type="welcome"):
    template_map = {
        "welcome": "emails/default/notification.html",
        "otp": "emails/auth/otp.html",
        "reset": "emails/auth/reset.html",
    }

    html_template = template_map.get(email_type, "emails/default/notification.html")
    context["domain"] = getattr(settings, "MAIN_DOMAIN", "")
    context["website_name"] = settings.WEBSITE_NAME
    context["website_url"] = settings.FRONTEND_URL
    context["BUSINESS_EMAIL"] = settings.BUSINESS_EMAIL
    context["HELP_CENTER_LINK"] = settings.HELP_CENTER_LINK
    context["COMPANY_ADDRESS"] = settings.COMPANY_ADDRESS
    context["FACEBOOK_LINK"] = settings.FACEBOOK_LINK
    context["INSTAGRAM_LINK"] = settings.INSTAGRAM_LINK
    context["TWITTER_LINK"] = settings.TWITTER_LINK
    context["YOUTUBE_LINK"] = settings.YOUTUBE_LINK
    html_content = render_to_string(html_template, context)
    text_content = "Please check your email."

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    

# rate limiting utility
from django.core.cache import cache
from rest_framework.exceptions import Throttled


def rate_limit(*, key: str, limit: int, ttl: int):
    current = cache.get(key, 0)

    if current >= limit:
        raise Throttled(detail="Too many requests. Please try again later.")

    if current == 0:
        cache.set(key, 1, ttl)
    else:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, ttl)
 
        
# login lockout levels
LOGIN_LOCKOUT_LEVELS = {
    0: {"attempts": 5, "lock_time": 30 * 60},
    1: {"attempts": 3, "lock_time": 60 * 60},
    2: {"attempts": 3, "lock_time": 2 * 60 * 60},
    3: {"attempts": 3, "lock_time": 6 * 60 * 60},
}

def is_login_locked(email):
    return cache.get(f"login:lock:{email}") is True


def record_login_failure(email):
    fail_key = f"login:fail:{email}"
    level_key = f"login:level:{email}"
    lock_key = f"login:lock:{email}"

    level = cache.get(level_key, 0)
    max_level_key = max(LOGIN_LOCKOUT_LEVELS)
    config = LOGIN_LOCKOUT_LEVELS.get(level, LOGIN_LOCKOUT_LEVELS[max_level_key])

    # attempt safe increment
    attempts = cache.get(fail_key)
    if attempts is None:
        cache.set(fail_key, 1, timeout=24 * 60 * 60)  # 1 day ttl
        attempts = 1
    else:
        try:
            attempts = cache.incr(fail_key)
        except ValueError:
            cache.set(fail_key, 1, timeout=24 * 60 * 60)
            attempts = 1

    if attempts >= config["attempts"]:
        cache.set(lock_key, True, timeout=config["lock_time"])  # lock user
        cache.delete(fail_key)
        cache.set(level_key, level + 1, timeout=7 * 24 * 60 * 60)  # escalation TTL
        return {
            "locked": True,
            "lock_time": config["lock_time"],
        }

    return {"locked": False}


def reset_login_failures(email):
    cache.delete_many([
        f"login:fail:{email}",
        f"login:lock:{email}",
        f"login:level:{email}",
    ])
    
    
    
# initialize new user
from django.db import transaction

from users.models import (
    UserProfile,
    AdminProfile,
    UserSettings,
    UserActivityLog,
)
from users.models import Role
from users.utils import log_user_activity
from users.utils import get_client_ip, get_user_location
from users.models import CURRENCIES

COUNTRY_CURRENCY_MAP = {
    "Egypt": CURRENCIES.EGP,
    "EG": CURRENCIES.EGP,
    "Saudi Arabia": CURRENCIES.SAR,
    "SA": CURRENCIES.SAR,
    "United Arab Emirates": CURRENCIES.AED,
    "AE": CURRENCIES.AED,
    "Qatar": CURRENCIES.QAR,
    "QA": CURRENCIES.QAR,
    "Kuwait": CURRENCIES.KWD,
    "KW": CURRENCIES.KWD,
    "Bahrain": CURRENCIES.BHD,
    "BH": CURRENCIES.BHD,
    "Oman": CURRENCIES.OMR,
    "OM": CURRENCIES.OMR,
    "Turkey": CURRENCIES.TRY,
    "TR": CURRENCIES.TRY,
    "Japan": CURRENCIES.JPY,
    "JP": CURRENCIES.JPY,
    "South Korea": CURRENCIES.KRW,
    "KR": CURRENCIES.KRW,
    "China": CURRENCIES.CNY,
    "CN": CURRENCIES.CNY,
    "Hong Kong": CURRENCIES.HKD,
    "HK": CURRENCIES.HKD,
    "Taiwan": CURRENCIES.TWD,
    "TW": CURRENCIES.TWD,
    "Singapore": CURRENCIES.SGD,
    "SG": CURRENCIES.SGD,
    "Malaysia": CURRENCIES.MYR,
    "MY": CURRENCIES.MYR,
    "Thailand": CURRENCIES.THB,
    "TH": CURRENCIES.THB,
    "India": CURRENCIES.INR,
    "IN": CURRENCIES.INR,
    "Indonesia": CURRENCIES.IDR,
    "ID": CURRENCIES.IDR,
    "Philippines": CURRENCIES.PHP,
    "PH": CURRENCIES.PHP,
    "Vietnam": CURRENCIES.VND,
    "VN": CURRENCIES.VND,
    "United Kingdom": CURRENCIES.GBP,
    "GB": CURRENCIES.GBP,
    "Switzerland": CURRENCIES.CHF,
    "CH": CURRENCIES.CHF,
    "Sweden": CURRENCIES.SEK,
    "SE": CURRENCIES.SEK,
    "Norway": CURRENCIES.NOK,
    "NO": CURRENCIES.NOK,
    "Denmark": CURRENCIES.DKK,
    "DK": CURRENCIES.DKK,
    "Poland": CURRENCIES.PLN,
    "PL": CURRENCIES.PLN,
    "Czech Republic": CURRENCIES.CZK,
    "CZ": CURRENCIES.CZK,
    "Hungary": CURRENCIES.HUF,
    "HU": CURRENCIES.HUF,
    "Romania": CURRENCIES.RON,
    "RO": CURRENCIES.RON,
    "Canada": CURRENCIES.CAD,
    "CA": CURRENCIES.CAD,
    "Brazil": CURRENCIES.BRL,
    "BR": CURRENCIES.BRL,
    "Mexico": CURRENCIES.MXN,
    "MX": CURRENCIES.MXN,
    "Argentina": CURRENCIES.ARS,
    "AR": CURRENCIES.ARS,
    "Chile": CURRENCIES.CLP,
    "CL": CURRENCIES.CLP,
    "South Africa": CURRENCIES.ZAR,
    "ZA": CURRENCIES.ZAR,
    "Nigeria": CURRENCIES.NGN,
    "NG": CURRENCIES.NGN,
    "United States": CURRENCIES.USD,
    "US": CURRENCIES.USD,
    # Eurozone
    "Germany": CURRENCIES.EUR, "DE": CURRENCIES.EUR,
    "France": CURRENCIES.EUR, "FR": CURRENCIES.EUR,
    "Italy": CURRENCIES.EUR, "IT": CURRENCIES.EUR,
    "Spain": CURRENCIES.EUR, "ES": CURRENCIES.EUR,
    "Netherlands": CURRENCIES.EUR, "NL": CURRENCIES.EUR,
    "Belgium": CURRENCIES.EUR, "BE": CURRENCIES.EUR,
    "Austria": CURRENCIES.EUR, "AT": CURRENCIES.EUR,
    "Portugal": CURRENCIES.EUR, "PT": CURRENCIES.EUR,
    "Greece": CURRENCIES.EUR, "GR": CURRENCIES.EUR,
    "Finland": CURRENCIES.EUR, "FI": CURRENCIES.EUR,
    "Ireland": CURRENCIES.EUR, "IE": CURRENCIES.EUR,
}


def initialize_new_user(user, request=None, provider="email", via="password"):
    """
    Initialize user after creation:
    - profile
    - settings
    - activity log
    """

    ip_address = get_client_ip(request) if request else None
    location = get_user_location(ip_address) if ip_address else None

    with transaction.atomic():
        settings_defaults = {"location": location}
        # Create Profile based on role
        if user.role == Role.USER:
            UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "country": location.split(",")[1].strip() if location else None,
                    "city": location.split(",")[0].strip() if location else None,
                }
            )


        elif user.role == Role.ADMIN:
            AdminProfile.objects.get_or_create(user=user)

        # Create Settings
        # Map location to currency
        try:
            user_country = location.split(",")[1].strip() if (location and "," in location) else location
            settings_defaults["currency"] = COUNTRY_CURRENCY_MAP.get(user_country, CURRENCIES.USD)
        except Exception:
            settings_defaults["currency"] = CURRENCIES.USD

        UserSettings.objects.get_or_create(
            user=user,
            defaults=settings_defaults
        )

        # Log registration activity
        log_user_activity(
            user=user,
            activity_type=UserActivityLog.ActivityType.REGISTER,
            request=request,
            metadata={
                "auth": {
                    "flow": "register",
                    "status": "success",
                    "provider": provider,
                    "via": via,
                }
            },
        )
####