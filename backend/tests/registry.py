"""Model → factory used by the R8 isolation test. Every API model must be listed here."""

from collections.abc import Callable
from typing import Any

from apps.organization.models import Agent, Device, DeviceChangeRequest, OrgUnit, Site
from apps.tenancy.models import Company
from tests import factories


def _device(company: Company) -> Any:
    return factories.DeviceFactory(company=company, agent=factories.AgentFactory(company=company))


def _device_request(company: Company) -> Any:
    return factories.DeviceChangeRequestFactory(
        company=company, agent=factories.AgentFactory(company=company)
    )


def _kiosk(company: Company) -> Any:
    from apps.kiosks.models import Kiosk
    from apps.tenancy.context import tenant_context
    from common.crypto import encrypt, new_secret_key

    site = factories.SiteFactory(company=company)
    with tenant_context(company.id):
        return Kiosk.objects.create(
            site=site, name="Borne", secret_key=encrypt(new_secret_key()), token_hash="0" * 64
        )


def _checkin(company: Company) -> Any:
    from django.utils import timezone

    from apps.attendance.models import CheckIn
    from apps.tenancy.context import tenant_context

    agent = factories.AgentFactory(company=company)
    with tenant_context(company.id):
        now = timezone.now()
        checkin = CheckIn(
            agent=agent,
            mode="A",
            trust="high",
            server_ts=now,
            effective_ts=now,
            result="accepted",
            direction="in",
        )
        checkin.save()
        return checkin


FACTORIES: dict[type, Callable[[Company], Any]] = {
    Site: lambda c: factories.SiteFactory(company=c),
    OrgUnit: lambda c: factories.OrgUnitFactory(company=c),
    Agent: lambda c: factories.AgentFactory(company=c),
    Device: _device,
    DeviceChangeRequest: _device_request,
}


def _late_registry() -> None:
    from apps.attendance.models import CheckIn
    from apps.kiosks.models import Kiosk

    FACTORIES[Kiosk] = _kiosk
    FACTORIES[CheckIn] = _checkin


_late_registry()
