"""Machine authentication for kiosks: ``Authorization: Kiosk <kiosk_id>.<token>``.

The company is resolved first by the middleware (``X-Company-Code`` header).
"""

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from . import services
from .models import Kiosk


class KioskPrincipal:
    """``request.user`` for machine calls: authenticated, holds no role."""

    is_authenticated = True
    is_superadmin = False
    roles: tuple[str, ...] = ()

    def __init__(self, kiosk: Kiosk) -> None:
        self.kiosk = kiosk
        self.pk = kiosk.pk  # used by DRF throttling as the identity

    def __str__(self) -> str:
        return f"Borne {self.kiosk.name}"

    def has_role(self, *roles: str) -> bool:
        return False


class KioskAuthentication(BaseAuthentication):
    keyword = b"kiosk"

    def authenticate(self, request: Request) -> tuple[KioskPrincipal, Kiosk] | None:
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword:
            return None
        if len(parts) != 2 or getattr(request._request, "company", None) is None:
            raise AuthenticationFailed("Identifiants de borne invalides.", code="kiosk_auth")
        kiosk = services.authenticate(parts[1].decode(errors="ignore"))
        if kiosk is None:
            raise AuthenticationFailed("Identifiants de borne invalides.", code="kiosk_auth")
        return KioskPrincipal(kiosk), kiosk

    def authenticate_header(self, request: Request) -> str:
        return "Kiosk"


class IsKiosk(BasePermission):
    message = "Réservé aux bornes appairées."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return isinstance(request.auth, Kiosk)


class KioskScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "apps.kiosks.authentication.KioskAuthentication"
    name = "kioskAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Kiosk <kiosk_id>.<token>",
        }


def kiosk_of(request: Request) -> Kiosk:
    kiosk = request.auth
    if not isinstance(kiosk, Kiosk):
        raise AuthenticationFailed("Borne non authentifiée.", code="kiosk_auth")
    return kiosk
