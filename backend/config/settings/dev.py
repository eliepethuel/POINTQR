"""Local development settings (docker compose)."""

from .base import *

DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", ".localhost", "backend"])
