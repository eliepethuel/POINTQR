"""Native local development settings (ADR-0010)."""

from .base import *

DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", ".localhost", "127.0.0.1"])

# Files on the local disk; S3-compatible storage outside development (ADR-0009).
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

# E-mails are printed in the server console.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Garnet (local Redis protocol server, ADR-0010) never answers the EVALSHA of Celery's remote
# control channel: the worker would hang at start-up. Real Redis (CI, Docker) keeps it.
CELERY_WORKER_ENABLE_REMOTE_CONTROL = env.bool("CELERY_REMOTE_CONTROL", default=False)
