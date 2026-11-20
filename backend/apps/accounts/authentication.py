"""JWT authentication bound to the tenant resolved by the middleware."""

from typing import Any

from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from .models import User


class PointQRJWTAuthentication(JWTAuthentication):
    def authenticate(self, request: Request) -> Any:
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        if not isinstance(user, User):
            raise AuthenticationFailed("Utilisateur inconnu.", code="user_not_found")
        company = getattr(request._request, "company", None)
        if not user.is_superadmin and (company is None or company.id != user.company_id):
            raise AuthenticationFailed("Jeton émis pour une autre entreprise.", code="wrong_tenant")
        if company is not None and not company.is_active and not user.is_superadmin:
            raise AuthenticationFailed("Entreprise suspendue.", code="company_suspended")
        return user, token
