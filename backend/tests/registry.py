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


FACTORIES: dict[type, Callable[[Company], Any]] = {
    Site: lambda c: factories.SiteFactory(company=c),
    OrgUnit: lambda c: factories.OrgUnitFactory(company=c),
    Agent: lambda c: factories.AgentFactory(company=c),
    Device: _device,
    DeviceChangeRequest: _device_request,
}
