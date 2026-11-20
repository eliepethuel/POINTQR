import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.organization.models import Agent, Device, DeviceChangeRequest
from apps.organization.services import bind_device
from apps.tenancy.context import tenant_context
from common.exceptions import DomainError
from tests.factories import AgentFactory, OrgUnitFactory, SiteFactory, make_user

pytestmark = pytest.mark.django_db


def _xlsx(rows: list[list[str]]) -> SimpleUploadedFile:
    wb = Workbook()
    sheet = wb.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return SimpleUploadedFile("agents.xlsx", buffer.getvalue())


def test_admin_creates_site_and_it_is_audited(admin_x, company_x):
    res = admin_x.post(
        reverse("v1:site-list"),
        {
            "name": "Plateau",
            "latitude": "5.3190",
            "longitude": "-4.0160",
            "radius_m": 200,
            "allowed_wifi": ["MINX-WIFI"],
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    with tenant_context(company_x.id):
        assert AuditLog.objects.filter(action="site.created").count() == 1


def test_hr_cannot_change_site_configuration(hr_x, company_x):
    site = SiteFactory(company=company_x)
    res = hr_x.patch(reverse("v1:site-detail", args=[site.id]), {"radius_m": 999}, format="json")
    assert res.status_code == 403
    assert hr_x.get(reverse("v1:site-list")).status_code == 200


def test_org_tree_nests_units(admin_x, company_x):
    root = OrgUnitFactory(company=company_x, name="Direction générale", kind="direction")
    OrgUnitFactory(company=company_x, name="RH", parent=root)
    tree = admin_x.get(reverse("v1:org-unit-tree")).json()
    assert tree[0]["name"] == "Direction générale"
    assert tree[0]["children"][0]["name"] == "RH"


def test_unit_cannot_be_its_own_ancestor(admin_x, company_x):
    root = OrgUnitFactory(company=company_x)
    child = OrgUnitFactory(company=company_x, parent=root)
    res = admin_x.patch(
        reverse("v1:org-unit-detail", args=[root.id]), {"parent": str(child.id)}, format="json"
    )
    assert res.status_code == 400


def test_import_reports_errors_line_by_line_and_writes_nothing(hr_x, company_x):
    upload = _xlsx(
        [
            ["Matricule", "Nom", "Prénoms", "Email", "Site"],
            ["A1", "Kouassi", "Aya", "aya@example.ci", ""],
            ["A2", "", "Kofi", "pas-un-email", ""],
            ["A1", "Doublon", "X", "", ""],
            ["A3", "Traoré", "Awa", "", "Site inconnu"],
        ]
    )
    res = hr_x.post(reverse("v1:agent-import-file"), {"file": upload}, format="multipart")
    assert res.status_code == 400
    errors = {(e["line"], e["field"]) for e in res.json()["line_errors"]}
    assert {(3, "nom"), (3, "email"), (4, "matricule"), (5, "site")} <= errors
    with tenant_context(company_x.id):
        assert Agent.objects.count() == 0


def test_import_creates_then_updates_by_employee_number(hr_x, company_x):
    SiteFactory(company=company_x, name="Plateau")
    rows = [
        ["matricule", "nom", "prenoms", "fonction", "site"],
        ["A1", "kouassi", "Aya", "Secrétaire", "plateau"],
    ]
    first = hr_x.post(reverse("v1:agent-import-file"), {"file": _xlsx(rows)}, format="multipart")
    assert first.json()["created"] == 1
    rows[1][3] = "Cheffe de service"
    second = hr_x.post(reverse("v1:agent-import-file"), {"file": _xlsx(rows)}, format="multipart")
    assert second.json()["updated"] == 1
    with tenant_context(company_x.id):
        agent = Agent.objects.get(employee_number="A1")
        assert agent.last_name == "KOUASSI" and agent.job_title == "Cheffe de service"


def test_csv_import_with_semicolons(hr_x, company_x):
    content = "Matricule;Nom;Prénoms\nC1;Bamba;Issa\n".encode()
    upload = SimpleUploadedFile("agents.csv", content)
    res = hr_x.post(reverse("v1:agent-import-file"), {"file": upload}, format="multipart")
    assert res.status_code == 200, res.content
    assert res.json()["created"] == 1


def test_manager_sees_only_their_units(company_x, make_client):
    unit = OrgUnitFactory(company=company_x)
    other = OrgUnitFactory(company=company_x)
    manager_agent = AgentFactory(company=company_x, org_unit=unit)
    with tenant_context(company_x.id):
        unit.manager = manager_agent
        unit.save()
    mine = AgentFactory(company=company_x, org_unit=unit)
    AgentFactory(company=company_x, org_unit=other)
    client = make_client(company_x, Role.MANAGER, agent=manager_agent)
    ids = {a["id"] for a in client.get(reverse("v1:agent-list")).json()["results"]}
    assert str(mine.id) in ids and len(ids) == 2


def test_agents_are_deactivated_not_deleted(hr_x, company_x):
    agent = AgentFactory(company=company_x)
    assert hr_x.delete(reverse("v1:agent-detail", args=[agent.id])).status_code == 204
    with tenant_context(company_x.id):
        assert Agent.objects.get(id=agent.id).status == "inactive"


def test_one_phone_per_agent_and_change_needs_hr(company_x, hr_x):
    agent = AgentFactory(company=company_x)
    with tenant_context(company_x.id):
        bind_device(agent, "phone-1", model="Tecno")
        assert bind_device(agent, "phone-1").agent_id == agent.id  # same phone: fine
        with pytest.raises(DomainError) as exc:
            bind_device(agent, "phone-2")
        assert exc.value.get_codes() == "device_change_pending"
        change = DeviceChangeRequest.objects.get(agent=agent)
    res = hr_x.post(reverse("v1:device-request-approve", args=[change.id]))
    assert res.status_code == 200
    with tenant_context(company_x.id):
        active = Device.objects.get(agent=agent, is_active=True)
        assert active.fingerprint_hash == change.fingerprint_hash


def test_phone_cannot_be_shared_by_two_agents(company_x):
    a, b = AgentFactory(company=company_x), AgentFactory(company=company_x)
    with tenant_context(company_x.id):
        bind_device(a, "shared-phone")
        with pytest.raises(DomainError) as exc:
            bind_device(b, "shared-phone")
        assert exc.value.get_codes() == "device_taken"


def test_company_settings_branding(admin_x, company_x, make_client):
    res = admin_x.patch(reverse("v1:company-settings"), {"primary_color": "#112233"}, format="json")
    assert res.status_code == 200
    agent_client = make_client(company_x, Role.AGENT)
    assert agent_client.get(reverse("v1:company-settings")).json()["primary_color"] == "#112233"
    assert (
        agent_client.patch(
            reverse("v1:company-settings"), {"primary_color": "#000000"}, format="json"
        ).status_code
        == 403
    )


def test_users_management_by_admin(admin_x, company_x):
    res = admin_x.post(
        reverse("v1:user-list"),
        {
            "username": "Manager1",
            "password": "Tres-secret-2026",
            "roles": ["manager", "agent"],
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.json()["roles"] == ["agent", "manager"]
    make_user(company_x, Role.AGENT, username="other")
    names = {u["username"] for u in admin_x.get(reverse("v1:user-list")).json()["results"]}
    assert {"manager1", "other"} <= names
