"""Encryption at rest for secrets (kiosk keys, badge keys) — ENF-08."""

import base64
import secrets
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if not key:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is not set.")
    return Fernet(key.encode() if isinstance(key, str) else key)


def new_secret_key() -> bytes:
    """32 random bytes, the HMAC-SHA256 key size."""
    return secrets.token_bytes(32)


def encrypt(raw: bytes) -> str:
    return _fernet().encrypt(raw).decode()


def decrypt(token: str) -> bytes:
    try:
        return _fernet().decrypt(token.encode())
    except InvalidToken as exc:  # pragma: no cover - only with a rotated/wrong key
        raise ImproperlyConfigured("Secret cannot be decrypted with FIELD_ENCRYPTION_KEY.") from exc


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
