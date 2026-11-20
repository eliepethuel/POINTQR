"""Shared factories. Tenant-scoped objects are created inside their company's tenant context."""

import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from typing import Any

import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import Role, User
from apps.organization.models import Agent, Device, DeviceChangeRequest, OrgUnit, Site
from apps.organization.services import fingerprint_hash
from apps.schedules.models import PublicHoliday, Schedule, ScheduleAssignment, ScheduleException
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Company, Subscription
from common.crypto import encrypt, new_secret_key

PASSWORD = "Pointqr-Test-2026!"


class CompanyFactory(DjangoModelFactory[Company]):
    class Meta:
        model = Company

    legal_name = factory.Sequence(lambda n: f"Entreprise {n}")
    slug = factory.Sequence(lambda n: f"entreprise-{n}")
    code = factory.Sequence(lambda n: f"ENT{n:04d}")

    @factory.post_generation
    def subscription(obj: Company, create: bool, extracted: Any, **kwargs: Any) -> None:
        if create:
            Subscription.objects.create(
                company=obj,
                plan="business",
                max_agents=1000,
                max_sites=20,
                max_kiosks=20,
                start_date=date.today() - timedelta(days=30),
                end_date=date.today() + timedelta(days=335),
            )


class TenantFactory(DjangoModelFactory[Any]):
    """Pass ``company=`` explicitly; creation happens in that company's RLS scope."""

    class Meta:
        abstract = True

    @classmethod
    def _create(cls, model_class: Any, *args: Any, **kwargs: Any) -> Any:
        company = kwargs.pop("company")
        with tenant_context(company.id):
            obj = model_class(*args, **kwargs)
            obj.company = company
            obj.save()
            return obj


class SiteFactory(TenantFactory):
    class Meta:
        model = Site

    name = factory.Sequence(lambda n: f"Site {n}")
    address = "Plateau, Abidjan"
    latitude = Decimal("5.319000")
    longitude = Decimal("-4.016000")
    radius_m = 150
    static_qr_key = factory.LazyFunction(lambda: encrypt(new_secret_key()))


class OrgUnitFactory(TenantFactory):
    class Meta:
        model = OrgUnit

    name = factory.Sequence(lambda n: f"Service {n}")
    kind = OrgUnit.Kind.SERVICE


class ScheduleFactory(TenantFactory):
    class Meta:
        model = Schedule

    name = factory.Sequence(lambda n: f"Horaire {n}")
    start_time = time(7, 30)
    end_time = time(16, 30)


class AgentFactory(TenantFactory):
    class Meta:
        model = Agent

    employee_number = factory.Sequence(lambda n: f"M{n:05d}")
    last_name = factory.Sequence(lambda n: f"KOUASSI{n}")
    first_names = "Aya"
    badge_key = factory.LazyFunction(lambda: encrypt(new_secret_key()))


class DeviceFactory(TenantFactory):
    class Meta:
        model = Device

    fingerprint_hash = factory.Sequence(lambda n: fingerprint_hash(f"device-{n}"))
    model = "Tecno Spark"
    os = "Android 12"


class DeviceChangeRequestFactory(TenantFactory):
    class Meta:
        model = DeviceChangeRequest

    fingerprint_hash = factory.Sequence(lambda n: fingerprint_hash(f"new-device-{n}"))


class ScheduleAssignmentFactory(TenantFactory):
    class Meta:
        model = ScheduleAssignment

    start_date = factory.LazyFunction(date.today)
    end_date = factory.LazyFunction(lambda: date.today() + timedelta(days=7))


class ScheduleExceptionFactory(TenantFactory):
    class Meta:
        model = ScheduleException

    name = "Ramadan"
    start_date = factory.LazyFunction(date.today)
    end_date = factory.LazyFunction(lambda: date.today() + timedelta(days=30))


class HolidayFactory(TenantFactory):
    class Meta:
        model = PublicHoliday

    date = factory.Sequence(lambda n: date(2030, 1, 1) + timedelta(days=n))
    label = "Jour férié d'entreprise"


def make_user(
    company: Company | None,
    *roles: str,
    username: str | None = None,
    agent: Agent | None = None,
    password: str = PASSWORD,
) -> User:
    name = username or f"user-{uuid.uuid4().hex[:10]}"
    with tenant_context(company.id if company else None, platform=company is None):
        if company is None:
            return User.objects.create_superadmin(name, password)
        return User.objects.create_user(
            name, password, company=company, roles=list(roles), agent=agent, display_name=name
        )


__all__ = ["PASSWORD", "Role"]
