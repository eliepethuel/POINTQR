"""Current tenant (company) for the running request, task or consumer.

Two layers enforce isolation (ADR-0004, ADR-0011):
- PostgreSQL row level security reads ``app.current_tenant`` / ``app.platform_admin``;
- a ContextVar lets the ORM ``TenantManager`` filter as well (defence in depth).

``tenant_context`` always runs inside a transaction and uses ``set_config(..., is_local => true)``,
so a value can never leak to another request sharing the same database connection.
"""

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from uuid import UUID

from django.db import DatabaseError, connections, transaction

_current_company: ContextVar[UUID | None] = ContextVar("pq_current_company", default=None)
_platform_admin: ContextVar[bool] = ContextVar("pq_platform_admin", default=False)

TENANT_SETTING = "app.current_tenant"
PLATFORM_SETTING = "app.platform_admin"


def current_company_id() -> UUID | None:
    return _current_company.get()


def is_platform_admin() -> bool:
    return _platform_admin.get()


def _read_settings(using: str) -> tuple[str, str]:
    with connections[using].cursor() as cursor:
        cursor.execute(
            "SELECT coalesce(current_setting(%s, true), ''), "
            "coalesce(current_setting(%s, true), '')",
            [TENANT_SETTING, PLATFORM_SETTING],
        )
        row = cursor.fetchone()
    return (row[0], row[1]) if row else ("", "")


def _write_settings(using: str, tenant: str, platform: str) -> None:
    with connections[using].cursor() as cursor:
        cursor.execute(
            "SELECT set_config(%s, %s, true), set_config(%s, %s, true)",
            [TENANT_SETTING, tenant, PLATFORM_SETTING, platform],
        )


@contextmanager
def tenant_context(
    company_id: UUID | str | None, *, platform: bool = False, using: str = "default"
) -> Iterator[None]:
    """Scope database access to one company (or to the platform for super-admin reads)."""
    company_uuid = UUID(str(company_id)) if company_id else None
    company_token = _current_company.set(company_uuid)
    platform_token = _platform_admin.set(platform)
    try:
        with transaction.atomic(using=using):
            previous = _read_settings(using)
            _write_settings(using, str(company_uuid or ""), "on" if platform else "")
            try:
                yield
            finally:
                # Restore the outer scope (nested contexts inside one transaction, e.g. tests).
                # A broken transaction is rolled back, which discards the local settings anyway.
                with suppress(DatabaseError):
                    _write_settings(using, *previous)
    finally:
        _current_company.reset(company_token)
        _platform_admin.reset(platform_token)
