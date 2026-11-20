"""Authentication flows: password step, TOTP enrolment / verification, refresh rotation."""

import contextlib
from dataclasses import dataclass, field
from typing import Literal

from django.contrib.auth import authenticate
from django.core import signing
from django.http import HttpRequest
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import status
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.services import record
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Company
from common.exceptions import DomainError

from .models import User, build_login
from .tokens import IssuedTokens, issue_tokens, mfa_challenge, read_mfa_challenge

MFA_ISSUER = "PointQR"


@dataclass(slots=True)
class LoginOutcome:
    step: Literal["authenticated", "mfa_required", "mfa_setup"]
    user: User
    tokens: IssuedTokens | None = None
    mfa_token: str | None = None
    otpauth_url: str | None = None
    secret: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


def _invalid() -> DomainError:
    return DomainError(
        "Identifiant ou mot de passe incorrect.",
        code="invalid_credentials",
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


def resolve_login_company(request_company: Company | None, company_code: str) -> Company | None:
    """Company from the sub-domain, else from the code typed on the login form (None = platform)."""
    if request_company is not None:
        return request_company
    code = company_code.strip().upper()
    if not code:
        return None
    company = Company.objects.filter(code=code).first()
    if company is None:
        raise DomainError("Code entreprise inconnu.", code="unknown_company", status_code=404)
    return company


def login(
    request: HttpRequest, *, company: Company | None, username: str, password: str
) -> LoginOutcome:
    if company is not None and not company.is_active:
        raise DomainError(
            "Cette entreprise est suspendue.", code="company_suspended", status_code=403
        )

    login_name = build_login(company.slug if company else None, username)
    outcome: LoginOutcome | None = None
    # Super-admin lookup needs the platform scope; company users are looked up inside their tenant.
    # Errors are raised *after* the block so the failed-attempt counter (django-axes) is committed.
    with tenant_context(company.id if company else None, platform=company is None):
        user = authenticate(request, username=login_name, password=password)
        locked = bool(getattr(request, "axes_locked_out", False))
        valid = (
            isinstance(user, User)
            and user.is_active
            and (company is not None or user.is_superadmin)
        )
        if valid and not locked and isinstance(user, User):
            outcome = _second_step(request, user)

    if locked:
        raise DomainError(
            "Compte bloqué après 5 échecs. Réessayez dans 15 minutes.",
            code="account_locked",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    if outcome is None:
        raise _invalid()
    return outcome


def _second_step(request: HttpRequest, user: User) -> LoginOutcome:
    if not user.mfa_required:
        record("auth.login", user, actor=user, request=request)
        return LoginOutcome("authenticated", user, tokens=issue_tokens(user, mfa=False))

    if TOTPDevice.objects.filter(user=user, confirmed=True).exists():
        return LoginOutcome("mfa_required", user, mfa_token=mfa_challenge(user))

    # First privileged login: enrol a new TOTP device, confirmed by the first valid code.
    TOTPDevice.objects.filter(user=user, confirmed=False).delete()
    device = TOTPDevice.objects.create(user=user, name="PointQR", confirmed=False)
    return LoginOutcome(
        "mfa_setup",
        user,
        mfa_token=mfa_challenge(user),
        otpauth_url=_otpauth_url(device, user),
        secret=_b32_secret(device),
    )


def _b32_secret(device: TOTPDevice) -> str:
    import base64

    return base64.b32encode(device.bin_key).decode().rstrip("=")


def _otpauth_url(device: TOTPDevice, user: User) -> str:
    from urllib.parse import quote

    label = quote(f"{MFA_ISSUER}:{user.login}")
    return (
        f"otpauth://totp/{label}?secret={_b32_secret(device)}&issuer={MFA_ISSUER}"
        f"&digits={device.digits}&period={device.step}"
    )


def verify_mfa(request: HttpRequest, *, mfa_token: str, code: str) -> User:
    try:
        data = read_mfa_challenge(mfa_token)
    except signing.BadSignature as exc:
        raise DomainError(
            "Session de vérification expirée, reconnectez-vous.",
            code="mfa_expired",
            status_code=401,
        ) from exc

    company_id = data.get("cid") or None
    verified = False
    # As for passwords, the failure counter (TOTP throttling) must be committed: raise afterwards.
    with tenant_context(company_id, platform=company_id is None):
        user = User.objects.filter(id=data["uid"], is_active=True).first()
        device = (
            TOTPDevice.objects.filter(user=user).order_by("-confirmed").first() if user else None
        )
        if user is not None and device is not None and device.verify_token(code.strip()):
            verified = True
            if not device.confirmed:
                device.confirmed = True
                device.save(update_fields=["confirmed"])
                record("auth.mfa_enrolled", user, actor=user, request=request)
            record("auth.login", user, actor=user, request=request)
    if not verified or user is None:
        raise DomainError("Code incorrect.", code="invalid_mfa_code", status_code=401)
    return user


def rotate_refresh(raw: str | None) -> tuple[User, IssuedTokens]:
    """Blacklist the presented refresh token and issue a new pair (rotation, ENF-10)."""
    if not raw:
        raise DomainError("Session expirée.", code="no_session", status_code=401)
    try:
        refresh = RefreshToken(raw)  # type: ignore[arg-type]  # also checks the blacklist
    except TokenError as exc:
        raise DomainError("Session expirée.", code="session_expired", status_code=401) from exc

    company_id = refresh.get("company_id")
    with tenant_context(company_id, platform=bool(refresh.get("platform"))):
        user = User.objects.filter(id=refresh["user_id"], is_active=True).first()
        if user is None:
            raise DomainError("Session expirée.", code="session_expired", status_code=401)
        mfa = bool(refresh.get("mfa"))
        refresh.blacklist()
        return user, issue_tokens(user, mfa=mfa)


def logout(raw: str | None) -> None:
    if not raw:
        return
    with contextlib.suppress(TokenError):
        RefreshToken(raw).blacklist()  # type: ignore[arg-type]
