from pathlib import Path
from datetime import timedelta
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-rx!usebp&ftsad&vl$&q79@t&5j5ss857u+7yh38y=dr5oe+y+64fz#e6'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
ALLOWED_HOSTS = []


# Application definition
INSTALLED_APPS = [
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'users',
    'users_auth',
    'rest_framework',
    'rest_framework_simplejwt',
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    'catalog',
    'topup',
    'cart',
    'notifications',
    'orders',
    'codes',
    'coupons',
    'payments',
    'django_cleanup.apps.CleanupConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
# main settings & variables
AUTH_USER_MODEL = 'users.User'
GEOIP_PATH = BASE_DIR / "geoip"
FRONTEND_URL = "http://localhost:5173"
WEBSITE_NAME = "Gimxa"
MAIN_DOMAIN = "gimxa.com"
API_DOMAIN = "api.gimxa.com"
BUSINESS_EMAIL = "gimxa@gmail.com"
HELP_CENTER_LINK = "https://help.gimxa.com"
COMPANY_ADDRESS = "Cairo, Egypt"
FACEBOOK_LINK = "https://facebook.com/gimxa"
INSTAGRAM_LINK = "https://instagram.com/gimxa"
TWITTER_LINK = "https://twitter.com/gimxa"
YOUTUBE_LINK = "https://youtube.com/gimxa"
# OAUTH2
SOCIAL_SECRET_KEY = "4k1zq8z@8z3z$y5v1f3h3v3x8y7z6y5x4w3v2u1t0s9r8q7p6o5n4m3l2k1j0i"
GOOGLE_CLIENT_ID = "9424209735-i59dqr7kmkptahe1vtuuhml8057op3bc.apps.googleusercontent.com"
# reset link timeout
PASSWORD_RESET_TIMEOUT = 60 * 60 * 1

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, "static")

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# CORS Settings
# CORS_ALLOW_ALL_ORIGINS = True # use this to allow all origins if you don't use cookies httpOnly
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]

# REST Framework and JWT settings
ACCESS_TOKEN_LIFETIME_SECONDS = 60 * 15  # 15 minutes
REFRESH_TOKEN_LIFETIME_SECONDS = 60 * 60 * 24 * 7  # 7 day
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",    
        "users_auth.authentication.CookieJWTAuthentication",    
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", # use drf spectacular for schema generation
    # 'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
    
    # pagination settings
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(seconds=ACCESS_TOKEN_LIFETIME_SECONDS),
    "REFRESH_TOKEN_LIFETIME": timedelta(seconds=REFRESH_TOKEN_LIFETIME_SECONDS),
    # Rotation & Blacklist
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    # Security
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    # Token validation
    "LEEWAY": 5,
    "JTI_CLAIM": "jti",
    # Sliders
    "UPDATE_LAST_LOGIN": True,
}

# CSRF
CSRF_COOKIE_SAMESITE = "None" # to allow cross-site cookies
CSRF_COOKIE_SECURE = True # to allow HTTPS only cookies
CSRF_COOKIE_HTTPONLY = False

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "None"

# Email settings
# aws
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = "email-smtp.eu-west-1.amazonaws.com" 
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = "AKIA6ODU7HTW5TAMVY7K"
# EMAIL_HOST_PASSWORD = "BBjcFQ94nsilhNyXFsHUIU9UVInPiBnEvr5juNGuSNiv"
# DEFAULT_FROM_EMAIL = "Deals4Gamer <noreply@deals4gamer.com>"
# brevo
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp-relay.brevo.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "a41dad001@smtp-brevo.com"
EMAIL_HOST_PASSWORD = "nyd7N1wtqJ0MhFCS"
DEFAULT_FROM_EMAIL = "Gimxa <noreply@gimxa.com>"






# DRF Spectacular Settings
SPECTACULAR_SETTINGS = {
    "TITLE": "Gimxa API",
    "DESCRIPTION": "Gimxa API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}


# cache settings -> production use redis or memcached
# default cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}
# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": "redis://127.0.0.1:6379/1",  # عدل حسب إعدادات سيرفرك
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#         }
#     }
# }
