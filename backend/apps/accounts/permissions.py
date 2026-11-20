"""Role-based permissions (section 4). MFA is required for admin and HR actions (ENF-09)."""

from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .models import MFA_REQUIRED_ROLES, Role


def _claims(request: Request) -> dict[str, Any]:
    token = request.auth
    return dict(token.payload) if token is not None and hasattr(token, "payload") else {}


def mfa_verified(request: Request) -> bool:
    return bool(_claims(request).get("mfa"))


class HasRole(BasePermission):
    """Grant access when the user holds one of ``roles``; ``read_roles`` may only read."""

    roles: frozenset[str] = frozenset()
    read_roles: frozenset[str] = frozenset()
    message = "Votre rôle ne permet pas cette action."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated or getattr(user, "is_superadmin", False):
            return False
        held = set(user.roles)
        allowed = held & self.roles
        if not allowed and request.method in SAFE_METHODS:
            allowed = held & self.read_roles
        if not allowed:
            return False
        # Privileged roles must have completed the second factor.
        return not (allowed <= MFA_REQUIRED_ROLES and not mfa_verified(request))


def role_permission(*roles: str, read: tuple[str, ...] = ()) -> type[HasRole]:
    return type(
        "HasRole_" + "_".join(roles),
        (HasRole,),
        {"roles": frozenset(roles), "read_roles": frozenset(read)},
    )


IsCompanyAdmin = role_permission(Role.COMPANY_ADMIN)
IsHrOrAdmin = role_permission(Role.COMPANY_ADMIN, Role.HR, read=(Role.AUDITOR,))
IsManagerOrAbove = role_permission(Role.COMPANY_ADMIN, Role.HR, Role.MANAGER, read=(Role.AUDITOR,))
ConfigReadable = role_permission(Role.COMPANY_ADMIN, read=(Role.HR, Role.MANAGER, Role.AUDITOR))


class IsPlatformAdmin(BasePermission):
    message = "Réservé à l'équipe PointQR."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_superadmin", False)
            and mfa_verified(request)
        )
