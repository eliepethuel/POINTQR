"""Justifications, corrections and the approval circuit (EF-29 to EF-32), acceptance R7."""

from datetime import date, time

import pytest
import time_machine
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import Role
from apps.attendance.models import CheckIn, WorkDay
from apps.attendance.tests.conftest import at, scene  # noqa: F401  (shared fixture)
from apps.audit.models import AuditLog
from apps.notifications.models import Notification
from apps.tenancy.context import tenant_context
from tests import factories

pytestmark = pytest.mark.django_db
DAY = date(2026, 11, 16)


@pytest.fixture
def team(scene, make_client):
    """Aya's unit has a manager (Kofi); HR exists."""
    unit = factories.OrgUnitFactory(company=scene.company, name="Informatique")
    with tenant_context(scene.company.id):
        scene.agent.org_unit = unit
        scene.agent.save()
        scene.other_agent.org_unit = unit
        scene.other_agent.save()
        unit.manager = scene.other_agent
        unit.save()
    scene.other_user.roles = [Role.MANAGER, Role.AGENT]
    with tenant_context(scene.company.id):
        scene.other_user.save()
    hr_user = factories.make_user(scene.company, Role.HR, username="rh")
    return scene, hr_user


def test_R7_hr_correction_keeps_the_original_and_is_audited(scene, hr_x):
    with time_machine.travel(at(7, 52), tick=False):
        original = scene.scan(at(7, 52)).json()
    res = hr_x.post(
        "/api/v1/corrections/",
        {
            "checkin": original["id"],
            "effective_ts": at(7, 35).isoformat(),
            "direction": "in",
            "reason": "Panne de la borne : arrivée constatée par le chef de service à 7 h 35.",
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    with tenant_context(scene.company.id):
        kept = CheckIn.objects.get(id=original["id"])
        assert kept.effective_ts == at(7, 52)  # never modified
        line = CheckIn.objects.get(id=res.json()["id"])
        assert (line.is_correction, line.corrects_id) == (True, kept.id)
        audit = AuditLog.objects.get(action="checkin.corrected")
        assert audit.before["effective_ts"].startswith("2026-11-16T07:52")
        assert audit.after["reason"].startswith("Panne")
        day = WorkDay.objects.get(agent=scene.agent, date=DAY)
        assert day.late_minutes == 0


def test_two_level_circuit_manager_then_hr(team):
    scene, hr_user = team
    with time_machine.travel(at(8, 10), tick=False):
        scene.scan(at(8, 10))
    with time_machine.travel(at(9, 0), tick=False):
        created = scene.agent_client.post(
            "/api/v1/requests/",
            {
                "kind": "justification",
                "category": "late",
                "target_date": "2026-11-16",
                "reason": "Embouteillage sur le pont HKB",
                "attachment": SimpleUploadedFile(
                    "attestation.pdf", b"%PDF-1.4 test", "application/pdf"
                ),
            },
            format="multipart",
        )
        assert created.status_code == 201, created.content
        req = created.json()
        assert req["status"] == "pending_manager" and req["attachment_url"]
        # The agent cannot validate their own request; the manager can.
        assert (
            scene.agent_client.post(
                f"/api/v1/requests/{req['id']}/decide/", {"approve": True}, format="json"
            ).status_code
            == 403
        )
        step1 = scene.other_client.post(
            f"/api/v1/requests/{req['id']}/decide/", {"approve": True}, format="json"
        ).json()
        assert step1["status"] == "pending_hr"
        from conftest import client_for

        final = (
            client_for(hr_user)
            .post(
                f"/api/v1/requests/{req['id']}/decide/",
                {"approve": True, "comment": "Justifié"},
                format="json",
            )
            .json()
        )
    assert final["status"] == "approved"
    assert [d["level"] for d in final["decisions"]] == ["manager", "hr"]
    with tenant_context(scene.company.id):
        day = WorkDay.objects.get(agent=scene.agent, date=DAY)
        assert (day.status, day.late_minutes) == ("late_justified", 40)  # RG-11: minutes kept
        assert Notification.objects.filter(
            user=scene.agent_user, title__contains="validée"
        ).exists()


def test_single_level_circuit(team):
    scene, _ = team
    scene.company.approval_levels = 1
    scene.company.save()
    with time_machine.travel(at(9, 0), tick=False):
        req = scene.agent_client.post(
            "/api/v1/requests/",
            {
                "kind": "justification",
                "category": "absence",
                "target_date": "2026-11-16",
                "reason": "Rendez-vous médical",
            },
            format="json",
        ).json()
        final = scene.other_client.post(
            f"/api/v1/requests/{req['id']}/decide/", {"approve": True}, format="json"
        ).json()
    assert final["status"] == "approved"


def test_forgotten_exit_correction_request(team):
    """R6 continued: the agent asks to add the missing exit, the circuit validates it."""
    scene, hr_user = team
    scene.company.approval_levels = 1
    scene.company.save()
    with time_machine.travel(at(7, 30), tick=False):
        scene.scan(at(7, 30))
    with time_machine.travel(at(8, 0, day=17), tick=False):
        req = scene.agent_client.post(
            "/api/v1/requests/",
            {
                "kind": "correction",
                "category": "missing_checkin",
                "target_date": "2026-11-16",
                "requested_direction": "out",
                "requested_time": at(16, 35).isoformat(),
                "reason": "Oubli de pointer ma sortie",
            },
            format="json",
        ).json()
        final = scene.other_client.post(
            f"/api/v1/requests/{req['id']}/decide/", {"approve": True}, format="json"
        ).json()
    assert final["resulting_checkin"]
    with tenant_context(scene.company.id):
        day = WorkDay.objects.get(agent=scene.agent, date=DAY)
        assert day.status == "present" and not day.incomplete


def test_rejected_request_changes_nothing(team):
    scene, _ = team
    with time_machine.travel(at(9, 0), tick=False):
        req = scene.agent_client.post(
            "/api/v1/requests/",
            {
                "kind": "justification",
                "category": "absence",
                "target_date": "2026-11-16",
                "reason": "Raison",
            },
            format="json",
        ).json()
        res = scene.other_client.post(
            f"/api/v1/requests/{req['id']}/decide/",
            {"approve": False, "comment": "Non recevable"},
            format="json",
        )
    assert res.json()["status"] == "rejected"


def test_attachment_type_and_size_are_checked(scene):
    with time_machine.travel(at(9, 0), tick=False):
        res = scene.agent_client.post(
            "/api/v1/requests/",
            {
                "kind": "justification",
                "category": "late",
                "target_date": "2026-11-16",
                "reason": "x",
                "attachment": SimpleUploadedFile("virus.exe", b"MZ", "application/octet-stream"),
            },
            format="multipart",
        )
    assert res.status_code == 400 and res.json()["code"] == "file_type"


def test_agent_sees_only_their_requests_and_can_cancel(team):
    scene, _ = team
    with time_machine.travel(at(9, 0), tick=False):
        mine = scene.agent_client.post(
            "/api/v1/requests/",
            {
                "kind": "justification",
                "category": "late",
                "target_date": "2026-11-16",
                "reason": "x",
            },
            format="json",
        ).json()
        assert (
            scene.agent_client.post(f"/api/v1/requests/{mine['id']}/cancel/").json()["status"]
            == "cancelled"
        )
        other = factories.AgentFactory(company=scene.company)
        from conftest import client_for

        stranger = client_for(
            factories.make_user(scene.company, Role.AGENT, agent=other), mfa=False
        )
        assert stranger.get("/api/v1/requests/").json()["count"] == 0


def test_closed_period_refuses_new_requests(scene, hr_x):
    with tenant_context(scene.company.id):
        from apps.attendance.models import Period

        Period.objects.create(month=date(2026, 11, 1), status="closed")
    with time_machine.travel(at(9, 0), tick=False):
        res = scene.agent_client.post(
            "/api/v1/requests/",
            {
                "kind": "justification",
                "category": "late",
                "target_date": "2026-11-16",
                "reason": "x",
            },
            format="json",
        )
    assert res.status_code == 409 and res.json()["code"] == "period_closed"


def test_agent_exports_their_history_as_csv(scene):
    with time_machine.travel(at(7, 31), tick=False):
        scene.scan(at(7, 31))
        res = scene.agent_client.get("/api/v1/me/export/")
        history = scene.agent_client.get("/api/v1/me/history/").json()
    content = res.content.decode("utf-8-sig")
    assert content.splitlines()[0].startswith("Date et heure;Sens")
    assert "16/11/2026 07:31:00;Entrée" in content
    assert len(history["checkins"]) == 1


def test_audit_log_is_read_only_and_restricted(scene, admin_x, hr_x, make_client):
    hr_x.post(
        "/api/v1/sites/", {"name": "Tentative", "latitude": "1", "longitude": "1"}, format="json"
    )
    admin_x.post(
        "/api/v1/sites/", {"name": "Annexe", "latitude": "5.3", "longitude": "-4.0"}, format="json"
    )
    auditor = make_client(scene.company, Role.AUDITOR)
    rows = auditor.get("/api/v1/audit-logs/").json()["results"]
    assert any(r["action"] == "site.created" for r in rows)
    assert hr_x.get("/api/v1/audit-logs/").status_code == 403
    entry = rows[0]["id"]
    assert admin_x.delete(f"/api/v1/audit-logs/{entry}/").status_code in (403, 405)
    assert (
        auditor.post(
            "/api/v1/sites/", {"name": "x", "latitude": "1", "longitude": "1"}, format="json"
        ).status_code
        == 403
    )


def test_schedule_time_used_in_lateness(scene):
    assert scene.agent.schedule.start_time == time(7, 30)
