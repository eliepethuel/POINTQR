"""Find the company a request belongs to: JWT claim, then sub-domain, then company code header."""

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.http import HttpRequest
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import Company

REFRESH_COOKIE = "pq_refresh"
COMPANY_HEADER = "HTTP_X_COMPANY_CODE"
RESERVED_LABELS = {"www", "api", "app", "admin", "static", "media"}


@dataclass(frozen=True, slots=True)
class TenantResolution:
    company: Company | None
    platform: bool = False


def _subdomain_slug(host: str) -> str | None:
    host = host.split(":", 1)[0].lower()
    for base in settings.TENANT_BASE_DOMAINS:
        suffix = f".{base}"
        if host.endswith(suffix):
            label = host[: -len(suffix)]
            if label and "." not in label and label not in RESERVED_LABELS:
                return label
    return None


def _token_claims(request: HttpRequest) -> dict[str, Any] | None:
    header = request.META.get("HTTP_AUTHORIZATION", "")
    try:
        if header.startswith("Bearer "):
            return dict(AccessToken(header.removeprefix("Bearer ").strip()).payload)
        cookie = request.COOKIES.get(REFRESH_COOKIE)
        if cookie and request.path.startswith("/api/v1/auth/"):
            return dict(RefreshToken(cookie, verify=True).payload)  # type: ignore[arg-type]
    except TokenError:
        return None
    return None


def resolve(request: HttpRequest) -> TenantResolution:
    claims = _token_claims(request)
    if claims is not None:
        if claims.get("platform"):
            return TenantResolution(company=None, platform=True)
        company_id = claims.get("company_id")
        if company_id:
            return TenantResolution(Company.objects.filter(id=company_id).first())

    slug = _subdomain_slug(request.get_host())
    if slug:
        return TenantResolution(Company.objects.filter(slug=slug).first())

    code = request.META.get(COMPANY_HEADER, "").strip().upper()
    if code:
        return TenantResolution(Company.objects.filter(code=code).first())

    return TenantResolution(company=None)
