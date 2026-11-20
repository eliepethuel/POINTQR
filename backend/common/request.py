"""Typed access to what TenantMiddleware attaches to the request."""

from typing import Any

from apps.tenancy.models import Company
from common.exceptions import DomainError


def company_of(request: Any) -> Company:
    """The company resolved for this request (DRF ``Request`` or Django ``HttpRequest``)."""
    raw = getattr(request, "_request", request)
    company = getattr(raw, "company", None)
    if not isinstance(company, Company):
        raise DomainError("Entreprise inconnue.", code="unknown_company", status_code=400)
    return company
