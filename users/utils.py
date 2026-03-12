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
    
def log_user_activity(*, user, activity_type, request, metadata=None):
    ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    device_info = parse_user_agent(user_agent)

    UserActivityLog.objects.create(
        user=user,
        activity_type=activity_type,
        ip_address=ip,
        user_agent=user_agent,
        metadata={
            "device": device_info,
            "geo": {
                "location": get_user_location(ip),
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
        # Create Profile based on role
        if user.role == Role.USER:
            UserProfile.objects.get_or_create(user=user)

        elif user.role == Role.ADMIN:
            AdminProfile.objects.get_or_create(user=user)

        # Create Settings
        UserSettings.objects.get_or_create(
            user=user,
            defaults={"location": location},
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