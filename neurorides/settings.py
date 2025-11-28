"""
Django settings for NeuroRides project.
Simplified & Render-friendly version.
"""

import os
from pathlib import Path
from datetime import timedelta

import environ
from celery.schedules import crontab
from kombu import Queue

# -------------------------------------------------
# Base paths & env
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

# Local .env (ignored if not present in production)
environ.Env.read_env(BASE_DIR / ".env")

# -------------------------------------------------
# Core settings
# -------------------------------------------------

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    env("SECRET_KEY", default="dev-fallback-secret-key"),
)

DEBUG = env("DEBUG")

# In case ALLOWED_HOSTS env missing, allow all (so Render works)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# -------------------------------------------------
# Apps
# -------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # "django.contrib.gis",  # PostGIS (disabled for now)
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_celery_beat",
    "channels",
    # "rest_framework_simplejwt",  # if you want to disable JWT auth
    # "corsheaders",
    # "drf_spectacular",
]

LOCAL_APPS = [
    "accounts",
    "rides",
    "fleet",
    "dispatch",
    "payments",
    "analytics",
    "notifications",
    "realtime",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# -------------------------------------------------
# Middleware
# -------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # "whitenoise.middleware.WhiteNoiseMiddleware",
    "accounts.middleware.SecurityHeadersMiddleware",
    "accounts.middleware.RateLimitMiddleware",
    # "corsheaders.middleware.CorsMiddleware",
    "accounts.middleware.CORSMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.RequestLoggingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.APIVersionMiddleware",
]

ROOT_URLCONF = "neurorides.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "neurorides.wsgi.application"
ASGI_APPLICATION = "neurorides.asgi.application"

# -------------------------------------------------
# Database
# (sqlite for now – safe for local & simple Render deploy)
# Later you can swap to Postgres/Neon using env vars.
# -------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# -------------------------------------------------
# Auth
# -------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# -------------------------------------------------
# I18N
# -------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# -------------------------------------------------
# Static & Media
# -------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------
# DRF / JWT
# -------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME", default=60)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_REFRESH_TOKEN_LIFETIME", default=1440)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# -------------------------------------------------
# CORS (kept flexible)
# -------------------------------------------------

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

# -------------------------------------------------
# Redis / Channels / Celery
# -------------------------------------------------

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_IGNORE_RESULT = False
CELERY_TASK_STORE_EAGER_RESULT = True

CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes
CELERY_TASK_TIME_LIMIT = 600       # 10 minutes

CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
CELERY_WORKER_DISABLE_RATE_LIMITS = False

CELERY_RESULT_EXPIRES = 3600  # 1 hour
CELERY_RESULT_COMPRESSION = "gzip"

CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_DEFAULT_EXCHANGE = "default"
CELERY_TASK_DEFAULT_EXCHANGE_TYPE = "direct"
CELERY_TASK_DEFAULT_ROUTING_KEY = "default"

CELERY_TASK_QUEUES = (
    Queue("default", routing_key="default"),
    Queue("dispatch_high", routing_key="dispatch_high"),
    Queue("dispatch_medium", routing_key="dispatch_medium"),
    Queue("dispatch_low", routing_key="dispatch_low"),
    Queue("realtime_high", routing_key="realtime_high"),
    Queue("realtime_medium", routing_key="realtime_medium"),
    Queue("realtime_low", routing_key="realtime_low"),
    Queue("realtime_monitoring", routing_key="realtime_monitoring"),
    Queue("analytics_high", routing_key="analytics_high"),
    Queue("analytics_medium", routing_key="analytics_medium"),
    Queue("analytics_low", routing_key="analytics_low"),
    Queue("fleet_high", routing_key="fleet_high"),
    Queue("fleet_medium", routing_key="fleet_medium"),
    Queue("fleet_low", routing_key="fleet_low"),
    Queue("payments_high", routing_key="payments_high"),
    Queue("payments_medium", routing_key="payments_medium"),
    Queue("payments_low", routing_key="payments_low"),
)

CELERY_SEND_TASK_EVENTS = True
CELERY_SEND_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True

from dispatch.celery_config import DISPATCH_TASK_ROUTES, DISPATCH_BEAT_SCHEDULE
from realtime.celery_config import REALTIME_TASK_ROUTES, REALTIME_BEAT_SCHEDULE
from analytics.celery_config import ANALYTICS_TASK_ROUTES, ANALYTICS_BEAT_SCHEDULE
from fleet.celery_config import FLEET_TASK_ROUTES, FLEET_BEAT_SCHEDULE
from payments.celery_config import PAYMENTS_TASK_ROUTES, PAYMENTS_BEAT_SCHEDULE

CELERY_TASK_ROUTES = {
    **DISPATCH_TASK_ROUTES,
    **REALTIME_TASK_ROUTES,
    **ANALYTICS_TASK_ROUTES,
    **FLEET_TASK_ROUTES,
    **PAYMENTS_TASK_ROUTES,
    "neurorides.celery.health_check": {"queue": "default"},
    "neurorides.celery.debug_task": {"queue": "default"},
}

CELERY_BEAT_SCHEDULE = {
    **DISPATCH_BEAT_SCHEDULE,
    **REALTIME_BEAT_SCHEDULE,
    **ANALYTICS_BEAT_SCHEDULE,
    **FLEET_BEAT_SCHEDULE,
    **PAYMENTS_BEAT_SCHEDULE,
    "system-health-check": {
        "task": "neurorides.celery.health_check",
        "schedule": crontab(minute="*/5"),
    },
}

# -------------------------------------------------
# Payments / Email
# -------------------------------------------------

STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_fallback_key")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_fallback_key")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_fallback_key")

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_fallback_key")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "fallback_secret")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "test@example.com")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "testpassword")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Payment Encryption Key (optional – encryption.py will fall back to SECRET_KEY)
PAYMENT_ENCRYPTION_KEY = env("PAYMENT_ENCRYPTION_KEY", default=None)

# -------------------------------------------------
# Security
# -------------------------------------------------

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# -------------------------------------------------
# Rate limiting / Cache
# -------------------------------------------------

RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# -------------------------------------------------
# Logging (console-only; Render/Heroku friendly)
# -------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "simple": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "INFO",
        },
    },

    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },

    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "neurorides": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "accounts": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "rides": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "payments": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "realtime": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# -------------------------------------------------
# API docs (optional; harmless even if drf_spectacular disabled)
# -------------------------------------------------

SPECTACULAR_SETTINGS = {
    "TITLE": "NeuroRides API",
    "DESCRIPTION": "Robotaxi Fleet Management Platform API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
