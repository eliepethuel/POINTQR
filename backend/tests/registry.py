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


def _phase3_registry() -> None:
    from datetime import date

    from apps.attendance.models import Period, WorkDay
    from apps.notifications.models import Notification
    from apps.schedules.models import PublicHoliday, Schedule, ScheduleAssignment, ScheduleException
    from apps.tenancy.context import tenant_context

    def workday(company: Company) -> Any:
        agent = factories.AgentFactory(company=company)
        with tenant_context(company.id):
            return WorkDay.objects.create(agent=agent, date=date(2026, 11, 16), status="present")

    months = iter(range(1, 10_000))

    def period(company: Company) -> Any:
        n = next(months)
        with tenant_context(company.id):
            return Period.objects.create(month=date(2000 + n // 12, n % 12 + 1, 1))

    def assignment(company: Company) -> Any:
        return factories.ScheduleAssignmentFactory(
            company=company,
            agent=factories.AgentFactory(company=company),
            schedule=factories.ScheduleFactory(company=company),
        )

    def exception(company: Company) -> Any:
        return factories.ScheduleExceptionFactory(
            company=company, schedule=factories.ScheduleFactory(company=company)
        )

    def notification(company: Company) -> Any:
        user = factories.make_user(company, "agent")
        with tenant_context(company.id):
            return Notification.objects.create(user=user, kind="request", title="Test")

    FACTORIES.update(
        {
            WorkDay: workday,
            Period: period,
            Schedule: lambda c: factories.ScheduleFactory(company=c),
            ScheduleAssignment: assignment,
            ScheduleException: exception,
            PublicHoliday: lambda c: factories.HolidayFactory(company=c),
            Notification: notification,
        }
    )


_phase3_registry()
