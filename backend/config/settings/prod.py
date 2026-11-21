"""Production settings. `python manage.py check --deploy` must pass without warnings."""

from .base import *

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# Outgoing e-mail (reports, notifications): smtp://user:password@host:port, smtp+tls://...
vars().update(env.email_url("EMAIL_URL", default="smtp://localhost:25"))

# Client IP behind the reverse proxy (throttling ENF-11): trust the last N X-Forwarded-For hops.
REST_FRAMEWORK["NUM_PROXIES"] = env.int("NUM_PROXIES", default=1)

# Files on any S3-compatible service (ADR-0009); local disk if no endpoint is configured.
if env("S3_ENDPOINT_URL", default=""):
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "endpoint_url": env("S3_ENDPOINT_URL"),
                "bucket_name": env("S3_BUCKET", default="pointqr"),
                "access_key": env("S3_ACCESS_KEY", default=""),
                "secret_key": env("S3_SECRET_KEY", default=""),
                "default_acl": "private",
                "querystring_auth": True,
                "file_overwrite": False,
            },
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
