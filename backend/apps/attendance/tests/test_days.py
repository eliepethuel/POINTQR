"""R6, work days, periods (RG-14), dashboard, WebSocket and scheduled jobs."""

from datetime import date, time, timedelta

import pytest
import time_machine
from channels.testing import WebsocketCommunicator

from apps.accounts.models import Role
from apps.accounts.tokens import issue_tokens
from apps.attendance import tasks
from apps.attendance.models import WorkDay
from apps.notifications.models import Notification
from apps.tenancy.context import tenant_context
from config.asgi import application
from tests import factories

from .conftest import at

pytestmark = pytest.mark.django_db


def test_R6_forgotten_exit_marks_the_day_incomplete_and_notifies(scene):
    with time_machine.travel(at(7, 31), tick=False):
        assert scene.scan(at(7, 31)).json()["result"] == "accepted"
    with time_machine.travel(at(0, 25, day=17), tick=False):
        tasks.missing_exits()
    with tenant_context(scene.company.id):
        day = WorkDay.objects.get(agent=scene.agent, date=date(2026, 11, 16))
        assert (day.status, day.incomplete) == ("incomplete", True)
        note = Notification.objects.get(kind="missing_exit", user=scene.agent_user)
        assert "16/11/2026" in note.body
    with time_machine.travel(at(0, 40, day=17), tick=False):
        tasks.missing_exits()  # idempotent: no second notification
    with tenant_context(scene.company.id):
        assert Notification.objects.filter(kind="missing_exit").count() == 1


def test_accepted_checkin_updates_the_live_workday(scene, hr_x):
    with time_machine.travel(at(7, 52), tick=False):
        scene.scan(at(7, 52))
    rows = hr_x.get("/api/v1/workdays/", {"agent": str(scene.agent.id)}).json()["results"]
    assert rows[0]["late_minutes"] == 22 and rows[0]["status"] == "late"


def test_absences_are_final_at_end_of_day(scene, hr_x):
    with time_machine.travel(at(23, 35), tick=False):
        tasks.close_day()
    summary = hr_x.get("/api/v1/workdays/summary/", {"agent": str(scene.other_agent.id)}).json()
    assert summary["absences"] == 1


def test_summary_cumulates_lateness(scene, hr_x):
    for day in (16, 17, 18):
        moment = at(7, 45, day=day)
        with time_machine.travel(moment, tick=False):
            scene.scan(moment)
    summary = hr_x.get("/api/v1/workdays/summary/", {"agent": str(scene.agent.id)}).json()
    assert (summary["late_count"], summary["late_minutes"]) == (3, 45)


def test_rg14_closed_period_is_frozen_until_reopened(scene, admin_x, hr_x, make_client):
    period = hr_x.post("/api/v1/periods/", {"month": "2026-11-01"}, format="json").json()
    with time_machine.travel(at(23, 50, day=30), tick=False):
        hr = make_client(scene.company, Role.HR)
        assert hr.post(f"/api/v1/periods/{period['id']}/close/").status_code == 200
        frozen = hr.post(
            "/api/v1/workdays/recompute/",
            {"start": "2026-11-16", "end": "2026-11-16"},
            format="json",
        )
    assert frozen.status_code == 200
    assert (
        hr_x.post(
            f"/api/v1/periods/{period['id']}/reopen/", {"reason": "Erreur"}, format="json"
        ).status_code
        == 403
    )
    res = admin_x.post(
        f"/api/v1/periods/{period['id']}/reopen/", {"reason": "Erreur de paie"}, format="json"
    )
    assert res.json()["status"] == "open"
    from apps.audit.models import AuditLog

    with tenant_context(scene.company.id):
        assert AuditLog.objects.filter(action="period.reopened").exists()


def test_dashboard_today_kpis(scene, make_client):
    with time_machine.travel(at(7, 52), tick=False):
        scene.scan(at(7, 52))
    with time_machine.travel(at(9, 0), tick=False):
        body = make_client(scene.company, Role.HR).get("/api/v1/dashboard/today/").json()
    assert body["kpis"]["present"] == 1
    assert body["kpis"]["late"] == 1
    assert body["kpis"]["absent"] == 1  # the other agent was expected at 07:30
    assert body["recent"][0]["agent_name"].startswith("Aya")
    assert body["sites"][0]["present"] == 1


def test_manager_dashboard_is_limited_to_their_units(scene, make_client):
    unit = factories.OrgUnitFactory(company=scene.company)
    manager = factories.AgentFactory(company=scene.company, org_unit=unit)
    with tenant_context(scene.company.id):
        unit.manager = manager
        unit.save()
    with time_machine.travel(at(7, 52), tick=False):
        scene.scan(at(7, 52))
        client = make_client(scene.company, Role.MANAGER, agent=manager)
        assert client.get("/api/v1/dashboard/today/").json()["kpis"]["present"] == 0


def test_absence_alert_at_h_plus_30(scene, hr_x):
    with time_machine.travel(at(8, 5), tick=False):
        tasks.absence_alerts()
        tasks.absence_alerts()
    with tenant_context(scene.company.id):
        alerts = Notification.objects.filter(kind="absent_alert")
        assert alerts.count() == 2  # both agents, once each, to HR (no unit manager)


@pytest.mark.asyncio
async def test_websocket_requires_a_staff_token():
    communicator = WebsocketCommunicator(
        application,
        "/ws/dashboard/?token=invalid",
        headers=[(b"origin", b"http://localhost"), (b"host", b"localhost")],
    )
    connected, _code = await communicator.connect()
    assert not connected
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_websocket_receives_checkin_events(company_x):
    from asgiref.sync import sync_to_async
    from channels.layers import get_channel_layer

    from apps.attendance.events import company_group

    user = await sync_to_async(factories.make_user)(company_x, Role.HR)
    token = (await sync_to_async(issue_tokens)(user, mfa=True)).access
    communicator = WebsocketCommunicator(
        application,
        f"/ws/dashboard/?token={token}",
        headers=[(b"origin", b"http://localhost"), (b"host", b"localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected
    assert (await communicator.receive_json_from())["event"] == "hello"
    await get_channel_layer().group_send(
        company_group(company_x.id),
        {"type": "dashboard.event", "event": "checkin.accepted", "payload": {"agent_name": "Aya"}},
    )
    message = await communicator.receive_json_from()
    assert message == {"event": "checkin.accepted", "payload": {"agent_name": "Aya"}}
    await communicator.disconnect()


def test_schedule_assignment_and_exception_precedence(company_x):
    from apps.schedules.selectors import schedule_for

    default = factories.ScheduleFactory(company=company_x, name="Normal")
    ramadan = factories.ScheduleFactory(company=company_x, name="Ramadan", start_time=time(8))
    night = factories.ScheduleFactory(
        company=company_x, name="Nuit", start_time=time(20), end_time=time(6)
    )
    agent = factories.AgentFactory(company=company_x, schedule=default)
    today = date(2026, 11, 16)
    factories.ScheduleExceptionFactory(
        company=company_x, schedule=ramadan, start_date=today, end_date=today + timedelta(days=10)
    )
    with tenant_context(company_x.id):
        assert schedule_for(agent, today) == ramadan
        assert schedule_for(agent, today - timedelta(days=1)) == default
    factories.ScheduleAssignmentFactory(
        company=company_x, agent=agent, schedule=night, start_date=today, end_date=today
    )
    with tenant_context(company_x.id):
        assert schedule_for(agent, today) == night


def test_national_holidays_are_read_only_but_company_days_editable(admin_x, company_x):
    rows = admin_x.get("/api/v1/holidays/", {"year": 2026}).json()["results"]
    national = next(r for r in rows if r["label"] == "Fête de l'Indépendance")
    assert national["national"] is True and national["date"] == "2026-08-07"
    assert (
        admin_x.patch(
            f"/api/v1/holidays/{national['id']}/", {"label": "x"}, format="json"
        ).status_code
        == 409
    )
    own = admin_x.post(
        "/api/v1/holidays/", {"date": "2026-12-24", "label": "Veille de Noël"}, format="json"
    )
    assert own.status_code == 201 and own.json()["national"] is False


def test_holiday_overrides_lateness(scene):
    factories.HolidayFactory(company=scene.company, date=date(2026, 11, 16), label="Pont")
    with time_machine.travel(at(9, 0), tick=False):
        scene.scan(at(9, 0))
    with tenant_context(scene.company.id):
        day = WorkDay.objects.get(agent=scene.agent, date=date(2026, 11, 16))
        assert (day.status, day.late_minutes) == ("holiday", 0)
