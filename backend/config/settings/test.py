"""Test settings: fast hashing, in-memory channel layer, eager Celery."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "postgres://pointqr:pointqr@localhost:5432/pointqr")

from .base import *

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", ".localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast hashing, tests only
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
