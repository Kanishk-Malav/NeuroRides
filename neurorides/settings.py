"""
Django settings for NeuroRides project.
Optimized for Google Cloud Run + Neon PostgreSQL + Upstash Redis
"""

import os
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse

import environ
import dj_database_url
import redis
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

DEBUG = env.bool("DEBUG", default=False)

# Cloud Run compatible
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# FIX: Prevent trailing slash redirect for OPTIONS requests
APPEND_SLASH = False

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
    "django.contrib.gis",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_celery_beat",
    "channels",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "django_redis",
    "whitenoise.runserver_nostatic",
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
# Middleware - FIXED ORDER FOR CORS
# -------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # MUST BE BEFORE CommonMiddleware
    "accounts.middleware.SecurityHeadersMiddleware",
    "accounts.middleware.RateLimitMiddleware",
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
# CORS - FIXED FOR CLOUD RUN + NETLIFY
# -------------------------------------------------

# Your Netlify frontend
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[
    "https://neurorides.netlify.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
])

CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[
    "https://neurorides.netlify.app",
    "https://*.cloudrun.app",
])

# Additional CORS settings for OPTIONS preflight
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-api-version",
]

CORS_EXPOSE_HEADERS = [
    "content-type",
    "x-api-version",
]

CORS_PREFLIGHT_MAX_AGE = 86400  # 24 hours

# -------------------------------------------------
# Database - NEON POSTGRESQL
# -------------------------------------------------

# Parse DATABASE_URL from Neon
DATABASE_URL = env("DATABASE_URL", default=None)

if DATABASE_URL:
    # Configure for Neon PostgreSQL with SSL
    db_config = dj_database_url.parse(DATABASE_URL)
    
    # Add SSL configuration for Neon
    db_config['OPTIONS'] = {
        'sslmode': 'require',
        'sslrootcert': None,
    }
    
    # Optimize for Cloud Run (connection pooling)
    db_config['CONN_MAX_AGE'] = 600  # 10 minutes
    db_config['CONN_HEALTH_CHECKS'] = True
    db_config['ATOMIC_REQUESTS'] = False
    
    # Enable statement timeout
    db_config['OPTIONS']['connect_timeout'] = 5
    db_config['OPTIONS']['options'] = '-c statement_timeout=30000'
    
    DATABASES = {
        "default": db_config
    }
else:
    # Fallback to SQLite for local development
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# -------------------------------------------------
# Redis Cache & Connection - UPSTASH COMPATIBLE
# -------------------------------------------------

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

def get_redis_config(redis_url):
    """Parse Redis URL for Upstash SSL support"""
    parsed = urlparse(redis_url)
    
    # Detect Upstash
    is_upstash = 'upstash.io' in parsed.hostname or parsed.scheme == 'rediss'
    
    config = {
        'host': parsed.hostname,
        'port': parsed.port or (6379 if not is_upstash else 6380),
        'password': parsed.password,
    }
    
    if is_upstash:
        config['ssl'] = True
        config['ssl_cert_reqs'] = None  # Required for Upstash
    
    # Database number
    if parsed.path and len(parsed.path) > 1:
        try:
            config['db'] = int(parsed.path[1:])
        except ValueError:
            config['db'] = 0
    else:
        config['db'] = 0
    
    return config, is_upstash

redis_config, is_upstash = get_redis_config(REDIS_URL)

# Django Cache Configuration
if is_upstash:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SSL": True,
                "SSL_CERT_REQS": None,
                "CONNECTION_POOL_KWARGS": {
                    "ssl_cert_reqs": None,
                    "retry_on_timeout": True,
                    "max_connections": 50,
                },
                "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
                "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
                "IGNORE_EXCEPTIONS": True,  # Graceful cache degradation
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
            },
            "KEY_PREFIX": "neurorides",
            "TIMEOUT": 300,
            "VERSION": 1,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
                "IGNORE_EXCEPTIONS": True,
            },
            "KEY_PREFIX": "neurorides",
        }
    }

# Session cache
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Rate limiting cache
RATELIMIT_USE_CACHE = "default"
RATELIMIT_ENABLE = True

# -------------------------------------------------
# Channels (WebSockets) - UPSTASH COMPATIBLE
# -------------------------------------------------

if is_upstash:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [{
                    'address': f"{redis_config['host']}:{redis_config['port']}",
                    'password': redis_config.get('password'),
                    'ssl': True,
                    'ssl_cert_reqs': None,
                }],
                "prefix": "asgi:",
                "capacity": 1500,
                "expiry": 10,
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [(redis_config['host'], redis_config['port'])],
                "prefix": "asgi:",
            },
        },
    }

# -------------------------------------------------
# Celery - UPSTASH COMPATIBLE
# -------------------------------------------------

# Separate databases for Celery
CELERY_BROKER_URL = REDIS_URL.replace('/0', '/1') if '/0' in REDIS_URL else f"{REDIS_URL}/1"
CELERY_RESULT_BACKEND = REDIS_URL.replace('/0', '/2') if '/0' in REDIS_URL else f"{REDIS_URL}/2"

# SSL configuration for Celery with Upstash
if is_upstash:
    CELERY_BROKER_USE_SSL = {
        'ssl_cert_reqs': None,
        'ssl_ca_certs': None,
    }
    CELERY_REDIS_BACKEND_USE_SSL = CELERY_BROKER_USE_SSL

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE = "UTC"
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

# Dynamic Celery imports (safe fallback)
try:
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
except ImportError:
    CELERY_TASK_ROUTES = {}
    CELERY_BEAT_SCHEDULE = {}

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
# DRF / JWT
# -------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "neurorides.exception_handlers.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user": "1000/day",
    },
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
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

# -------------------------------------------------
# Static & Media
# -------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# WhiteNoise for static files
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_ALLOW_ALL_ORIGINS = True
WHITENOISE_MAX_AGE = 31536000  # 1 year

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_I18N = True
USE_TZ = True
LANGUAGE_CODE = "en-us"

# -------------------------------------------------
# Payments
# -------------------------------------------------

STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_fallback_key")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_fallback_key")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_fallback_key")

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_fallback_key")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "fallback_secret")

# Payment Encryption Key
PAYMENT_ENCRYPTION_KEY = env("PAYMENT_ENCRYPTION_KEY", default=None)

# -------------------------------------------------
# Email
# -------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "test@example.com")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "testpassword")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
SERVER_EMAIL = EMAIL_HOST_USER

# -------------------------------------------------
# Security Headers
# -------------------------------------------------

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Production security settings
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Additional security
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# -------------------------------------------------
# Logging
# -------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(levelname)s %(asctime)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple" if DEBUG else "json",
            "level": "DEBUG" if DEBUG else "INFO",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
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
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
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
        "channels": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# Create logs directory if it doesn't exist
if not DEBUG:
    (BASE_DIR / "logs").mkdir(exist_ok=True)

# -------------------------------------------------
# API Documentation
# -------------------------------------------------

SPECTACULAR_SETTINGS = {
    "TITLE": "NeuroRides API",
    "DESCRIPTION": "Robotaxi Fleet Management Platform API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/",
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
    },
    "SECURITY": [
        {
            "Bearer": [],
        }
    ],
}

# -------------------------------------------------
# Health Check Settings
# -------------------------------------------------

HEALTH_CHECK = {
    'database': True,
    'cache': True,
    'redis': True,
    'storage': False,
    'celery': True,
}

HEALTH_CHECK_PATH = '/health'
HEALTH_CHECK_SIMPLE_PATH = '/health/simple'

# -------------------------------------------------
# Cloud Run Specific Optimizations
# -------------------------------------------------

# Gunicorn settings (via env)
os.environ.setdefault('GUNICORN_CMD_ARGS', '--workers=3 --worker-class=sync --timeout=120 --access-logfile=- --error-logfile=-')

# Database connection optimizations for serverless
if 'CONN_MAX_AGE' in DATABASES.get('default', {}):
    DATABASES['default']['CONN_MAX_AGE'] = min(DATABASES['default']['CONN_MAX_AGE'], 600)

# File upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # 5MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# -------------------------------------------------
# Custom Settings
# -------------------------------------------------

# API Version
API_VERSION = "1.0.0"

# Feature flags
FEATURE_FLAGS = {
    'ENABLE_REALTIME_TRACKING': True,
    'ENABLE_SURGE_PRICING': True,
    'ENABLE_AI_DISPATCH': False,
    'ENABLE_DRIVER_RATINGS': True,
}

# Service URLs (set via environment)
SERVICE_URLS = {
    'frontend': env("FRONTEND_URL", default="https://neurorides.netlify.app"),
    'backend': env("BACKEND_URL", default=""),
    'websocket': env("WEBSOCKET_URL", default=""),
}

# Monitoring
ENABLE_METRICS = env.bool("ENABLE_METRICS", default=True)
METRICS_EXPORT_PORT = env.int("METRICS_EXPORT_PORT", default=9090)

# Performance
DJANGO_QUERY_DEBUG = env.bool("DJANGO_QUERY_DEBUG", default=False)
if DJANGO_QUERY_DEBUG:
    LOGGING['loggers']['django.db.backends']['level'] = 'DEBUG'

# -------------------------------------------------
# END OF SETTINGS
# -------------------------------------------------