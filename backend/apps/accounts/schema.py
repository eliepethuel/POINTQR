"""OpenAPI description of the PointQR JWT scheme (loaded by AccountsConfig.ready)."""

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class PointQRJWTScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "apps.accounts.authentication.PointQRJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
