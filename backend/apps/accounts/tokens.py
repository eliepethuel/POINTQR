"""JWT issuance: short access token kept in memory (15 min), rotating refresh in a cookie."""

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.http import HttpResponse
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenancy.resolver import REFRESH_COOKIE

from .models import User

MFA_SALT = "pointqr.mfa"
REFRESH_LIFETIME: timedelta = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]  # type: ignore[assignment]
MFA_TOKEN_MAX_AGE = 300


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access: str
    refresh: str


def issue_tokens(user: User, *, mfa: bool) -> IssuedTokens:
    refresh = RefreshToken.for_user(user)
    refresh["company_id"] = str(user.company_id) if user.company_id else None
    refresh["platform"] = user.is_superadmin
    refresh["roles"] = list(user.roles)
    refresh["mfa"] = mfa
    access = refresh.access_token
    return IssuedTokens(access=str(access), refresh=str(refresh))


def set_refresh_cookie(response: HttpResponse, refresh: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=int(REFRESH_LIFETIME.total_seconds()),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="Strict",
        path="/api/v1/auth/",
    )


def clear_refresh_cookie(response: HttpResponse) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth/", samesite="Strict")


def mfa_challenge(user: User) -> str:
    """Short-lived signed proof that the password step succeeded."""
    return signing.dumps(
        {"uid": str(user.id), "cid": str(user.company_id or "")}, salt=MFA_SALT, compress=True
    )


def read_mfa_challenge(token: str) -> dict[str, str]:
    data: dict[str, str] = signing.loads(token, salt=MFA_SALT, max_age=MFA_TOKEN_MAX_AGE)
    return data
