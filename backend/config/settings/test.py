"""Test settings: fast hashing, in-memory channel layer, eager Celery."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "postgres://pointqr:pointqr@localhost:5432/pointqr")

from .base import *

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", ".localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast hashing, tests only
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Second-factor throttling waits between attempts; tests assert codes, not timing.
OTP_TOTP_THROTTLE_FACTOR = 0
# Async tests (WebSocket) run queries in worker threads: never keep their connections open.
DATABASES["default"]["CONN_MAX_AGE"] = 0
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="pointqr-test-media-"))
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
