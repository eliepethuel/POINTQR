"""Database-level isolation (ENF-07): RLS must hold even if the ORM filter is bypassed."""

import pytest
from django.apps import apps
from django.db import connection
from django.db.utils import DatabaseError

from apps.organization.models import Agent, Site
from apps.tenancy.context import tenant_context
from common.models import TenantModel
from tests.factories import AgentFactory, SiteFactory

pytestmark = pytest.mark.django_db


def _tenant_tables() -> list[str]:
    tables = [m._meta.db_table for m in apps.get_models() if issubclass(m, TenantModel)]
    tables += ["accounts_user", "audit_auditlog", "schedules_publicholiday"]
    return sorted(set(tables))


def test_every_tenant_table_has_forced_rls_and_policies():
    with connection.cursor() as cursor:
        for table in _tenant_tables():
            cursor.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
                [table],
            )
            assert cursor.fetchone() == (True, True), f"RLS not forced on {table}"
            cursor.execute("SELECT count(*) FROM pg_policies WHERE tablename = %s", [table])
            assert cursor.fetchone()[0] == 4, f"missing policies on {table}"


def test_rls_hides_other_company_rows_even_with_raw_sql(company_x, company_y):
    AgentFactory(company=company_x)
    AgentFactory(company=company_y)
    with tenant_context(company_x.id), connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT company_id FROM organization_agent")
        assert [row[0] for row in cursor.fetchall()] == [company_x.id]


def test_unscoped_manager_still_filtered_by_database(company_x, company_y):
    AgentFactory(company=company_y)
    with tenant_context(company_x.id):
        assert Agent.unscoped.count() == 0


def test_no_tenant_means_no_rows(company_x):
    SiteFactory(company=company_x)
    with tenant_context(None):
        assert Site.unscoped.count() == 0


def test_cannot_write_rows_for_another_company(company_x, company_y):
    with tenant_context(company_x.id), pytest.raises(DatabaseError):
        site = Site(name="Intrus", latitude=0, longitude=0)
        site.company = company_y
        site.save()


def test_platform_scope_reads_but_cannot_write(company_x):
    SiteFactory(company=company_x)
    with tenant_context(None, platform=True):
        assert Site.unscoped.count() == 1
        # UPDATE policy only matches the current tenant: the editor cannot alter client data.
        assert Site.unscoped.update(name="modifié") == 0


def test_nested_context_restores_outer_tenant(company_x, company_y):
    SiteFactory(company=company_x)
    with tenant_context(company_x.id):
        with tenant_context(company_y.id):
            assert Site.unscoped.count() == 0
        assert Site.unscoped.count() == 1


def test_application_role_has_no_bypass():
    """The runtime role defined in infra/postgres/create-roles.sql must be restricted."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        assert cursor.fetchone() == (False, False)
