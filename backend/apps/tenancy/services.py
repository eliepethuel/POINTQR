"""Company lifecycle (super-admin) — EF-01 to EF-03."""

from typing import Any

from django.db import transaction

from apps.audit.services import record

from .context import tenant_context
from .models import Company, Subscription


def onboard_company(data: dict[str, Any], *, actor: Any, request: Any = None) -> Company:
    from apps.accounts.models import Role, User

    with transaction.atomic():
        company = Company.objects.create(
            legal_name=data["legal_name"],
            slug=data["slug"],
            code=data["code"],
            sector=data.get("sector", ""),
            timezone=data.get("timezone", "Africa/Abidjan"),
            contact_name=data.get("contact_name", ""),
            contact_email=data.get("contact_email", ""),
        )
        Subscription.objects.create(
            company=company,
            plan=data["plan"],
            max_agents=data["max_agents"],
            max_sites=data["max_sites"],
            max_kiosks=data["max_kiosks"],
            start_date=data["start_date"],
            end_date=data["end_date"],
        )
        with tenant_context(company.id):
            User.objects.create_user(
                data["admin_username"],
                data["admin_password"],
                company=company,
                email=data.get("admin_email", ""),
                display_name="Administrateur",
                roles=[Role.COMPANY_ADMIN],
            )
            record("company.onboarded", company, actor=actor, request=request)
    return company


def set_status(company: Company, status: str, *, actor: Any, request: Any = None) -> Company:
    """Suspension blocks logins and check-ins; data is kept (EF-03)."""
    before = company.status
    company.status = status
    company.save(update_fields=["status", "updated_at"])
    with tenant_context(company.id):
        record(
            f"company.{status}",
            company,
            actor=actor,
            request=request,
            before={"status": before},
            after={"status": status},
        )
    return company


def check_quota(company: Company, resource: str, current: int) -> None:
    """Subscription limits (EF-02): number of agents, sites and kiosks."""
    from common.exceptions import DomainError

    sub = company.subscriptions.filter(status=Subscription.Status.ACTIVE).first()
    if sub is None:
        raise DomainError("Aucun abonnement actif.", code="no_subscription", status_code=402)
    limit = {"agents": sub.max_agents, "sites": sub.max_sites, "kiosks": sub.max_kiosks}[resource]
    if current >= limit:
        raise DomainError(
            f"Limite de l'abonnement atteinte ({limit} {resource}).",
            code="quota_exceeded",
            status_code=402,
        )
