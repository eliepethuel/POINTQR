"""Settings shared by every environment. Values come from the environment (.env)."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR.parent / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS: list[str] = env.list("DJANGO_ALLOWED_HOSTS", default=[])
APP_VERSION = env("APP_VERSION", default="0.1.0")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "channels",
    "django_celery_beat",
    "rest_framework_simplejwt.token_blacklist",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "axes",
    # PointQR
    "common",
    "apps.system",
    "apps.tenancy",
    "apps.accounts",
    "apps.audit",
    "apps.organization",
    "apps.schedules",
    "apps.kiosks",
    "apps.attendance",
    "apps.requests_app",
    "apps.notifications",
    "apps.reports",
]

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # Opens the request transaction and sets app.current_tenant (ADR-0004, ADR-0011).
    "apps.tenancy.middleware.TenantMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

# --- Multi-tenancy ------------------------------------------------------------------------------
TENANT_BASE_DOMAINS: list[str] = env.list(
    "TENANT_BASE_DOMAINS", default=["pointqr.ci", "localhost"]
)
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")

# --- Authentication (ENF-09 to ENF-11) ----------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_HEADER_TYPES": ("Bearer",),
}
REFRESH_COOKIE_SECURE = env.bool("REFRESH_COOKIE_SECURE", default=not DEBUG)
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["username"]
# Locking by IP would lock a whole office behind one NAT address; IPs are rate-limited by DRF.
SILENCED_SYSTEM_CHECKS = ["axes.W006"]
AXES_RESET_ON_SUCCESS = True
AXES_USERNAME_FORM_FIELD = "username"
AXES_VERBOSE = False
AXES_LOCKOUT_CALLABLE = "apps.accounts.lockout.lockout_response"
OTP_TOTP_ISSUER = "PointQR"

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database -----------------------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL")}
# Transactions are opened by TenantMiddleware (ADR-0011), not ATOMIC_REQUESTS.
# Under ASGI, persistent per-thread connections pile up until Postgres refuses clients (seen in
# the R10 load test): a psycopg pool is used instead. Tenant settings are transaction-local
# (set_config(..., true)), so a pooled connection never leaks one company's scope (ADR-0012).
DATABASES["default"]["CONN_MAX_AGE"] = 0
if env.bool("DB_POOL", default=True):
    DATABASES["default"].setdefault("OPTIONS", {})["pool"] = {
        "min_size": env.int("DB_POOL_MIN", default=2),
        "max_size": env.int("DB_POOL_MAX", default=10),
        "timeout": env.int("DB_POOL_TIMEOUT", default=10),
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Passwords (ENF-09) -------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N / time (RG-01: server time, company timezone applied in services) --------------------
LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", "Français"), ("en", "English")]
TIME_ZONE = "Africa/Abidjan"
USE_I18N = True
USE_TZ = True

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- REST framework -----------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.PointQRJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "EXCEPTION_HANDLER": "common.exceptions.problem_exception_handler",
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "auth": "20/min",
        "refresh": "60/min",
        "checkin_device": "12/min",
        "checkin_ip": env("CHECKIN_IP_RATE", default="600/min"),
        "kiosk": "1200/min",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "PointQR API",
    "DESCRIPTION": "API de pointage par QR code dynamique — « Le pointage qui ne ment pas. »",
    "VERSION": APP_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+",
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "HealthStatusEnum": ["ok", "degraded"],
        "CompanyStatusEnum": "apps.tenancy.models.Company.Status",
        "SubscriptionStatusEnum": "apps.tenancy.models.Subscription.Status",
        "AgentStatusEnum": "apps.organization.models.Agent.Status",
        "DeviceRequestStatusEnum": "apps.organization.models.DeviceChangeRequest.Status",
        "RoleEnum": "apps.accounts.models.Role",
        "DirectionEnum": "apps.attendance.models.Direction",
        "RequestKindEnum": "apps.requests_app.models.Request.Kind",
        "RequestCategoryEnum": "apps.requests_app.models.Request.Category",
        "ReportKindEnum": "apps.reports.models.ReportJob.Kind",
        "NotificationKindEnum": "apps.notifications.models.Notification.Kind",
    },
}

# --- CORS: frontend origin only -----------------------------------------------------------------
CORS_ALLOWED_ORIGINS: list[str] = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOWED_ORIGIN_REGEXES: list[str] = env.list("CORS_ALLOWED_ORIGIN_REGEXES", default=[])
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS: list[str] = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --- Redis, Channels, Celery --------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
# Cache (replay protection SET NX, throttling): Redis protocol, database 1.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("CACHE_URL", default=REDIS_URL.rsplit("/", 1)[0] + "/1"),
        "KEY_PREFIX": "pointqr",
    }
}
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.pubsub.RedisPubSubChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    },
}
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"


def _beat_schedule() -> dict[str, Any]:
    from celery.schedules import crontab

    return {
        # RG-04: absences become final at the end of the working day.
        "close-day": {"task": "attendance.close_day", "schedule": crontab(hour=23, minute=30)},
        # RG-05: entries without exit become incomplete after midnight.
        "missing-exits": {
            "task": "attendance.missing_exits",
            "schedule": crontab(hour=0, minute=20),
        },
        # EF-27: alert managers 30 minutes after the expected arrival.
        # EF-38: scheduled reports, previous week on Mondays and previous month on the 1st.
        "weekly-reports": {
            "task": "reports.send_scheduled",
            "schedule": crontab(hour=7, minute=0, day_of_week=1),
            "args": ("weekly",),
        },
        "monthly-reports": {
            "task": "reports.send_scheduled",
            "schedule": crontab(hour=7, minute=30, day_of_month=1),
            "args": ("monthly",),
        },
        # ENF-04: GPS minimisation and retention, every night.
        "retention-purge": {
            "task": "reports.retention_purge",
            "schedule": crontab(hour=2, minute=0),
        },
        "absence-alerts": {
            "task": "attendance.absence_alerts",
            "schedule": crontab(minute="*/15", hour="5-12"),
        },
    }


CELERY_BEAT_SCHEDULE = _beat_schedule()
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="PointQR <no-reply@pointqr.ci>")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
