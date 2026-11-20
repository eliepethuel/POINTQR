"""Opens the request transaction and scopes it to the resolved company (replaces ATOMIC_REQUESTS).

DRF does not roll back 4xx responses: refused check-ins must stay recorded (EF-21).
Server errors (5xx) are rolled back.
"""

from collections.abc import Callable

from django.db import transaction
from django.http import HttpRequest, HttpResponse

from .context import tenant_context
from .resolver import resolve


class TenantMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        resolution = resolve(request)
        request.company = resolution.company  # type: ignore[attr-defined]
        request.platform_admin = resolution.platform  # type: ignore[attr-defined]
        company_id = resolution.company.id if resolution.company else None
        with tenant_context(company_id, platform=resolution.platform):
            response = self.get_response(request)
            if response.status_code >= 500:
                transaction.set_rollback(True)
            return response
