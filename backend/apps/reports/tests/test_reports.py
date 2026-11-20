"""Reports (EF-34 to EF-38) and acceptance R9: 500 agents monthly report in < 30 s, exact figures."""

import io
import time
from datetime import date, datetime, timedelta
from datetime import time as dtime
from zoneinfo import ZoneInfo

import pytest
from django.core import mail
from openpyxl import load_workbook

from apps.attendance.models import CheckIn, WorkDay
from apps.organization.models import Agent
from apps.reports import generators, tasks
from apps.reports.models import ReportJob, ReportSchedule
from apps.tenancy.context import tenant_context
from tests import factories

pytestmark = pytest.mark.django_db
TZ = ZoneInfo("Africa/Abidjan")
START, END = date(2026, 10, 1), date(2026, 10, 31)


def _month_of_workdays(company, agents: list[Agent]) -> dict[str, int]:
    """Deterministic month; returns the control totals computed independently."""
    rows, control = [], {"late_count": 0, "late_minutes": 0, "absences": 0, "present": 0}
    day = START
    while day <= END:
        if day.weekday() < 5:
            for i, agent in enumerate(agents):
                if (i + day.day) % 11 == 0:
                    rows.append(
                        WorkDay(company_id=company.id, agent=agent, date=day, status="absent")
                    )
                    control["absences"] += 1
                    continue
                late = 20 if (i + day.day) % 7 == 0 else 0
                start = datetime.combine(day, dtime(7, 30), tzinfo=TZ) + timedelta(minutes=late)
                rows.append(
                    WorkDay(
                        company_id=company.id,
                        agent=agent,
                        date=day,
                        status="late" if late else "present",
                        first_in=start,
                        last_out=start + timedelta(hours=9),
                        late_minutes=late,
                        worked_minutes=480,
                    )
                )
                control["present"] += 1
                if late:
                    control["late_count"] += 1
                    control["late_minutes"] += late
        day += timedelta(days=1)
    with tenant_context(company.id):
        WorkDay.objects.bulk_create(rows, batch_size=5000)
    return control


def test_R9_monthly_report_for_500_agents_under_30_seconds(company_x):
    with tenant_context(company_x.id):
        agents = Agent.objects.bulk_create(
            [
                Agent(
                    company_id=company_x.id,
                    employee_number=f"R{i:04d}",
                    last_name=f"NOM{i}",
                    first_names="Test",
                )
                for i in range(500)
            ]
        )
    control = _month_of_workdays(company_x, agents)
    with tenant_context(company_x.id):
        started = time.perf_counter()
        totals = generators.punctuality(START, END)
        xlsx = generators.punctuality_xlsx(company_x, START, END)
        pdf = generators.monthly_sheet_pdf(company_x, START, END)
        elapsed = time.perf_counter() - started
    assert elapsed < 30, f"{elapsed:.1f} s"
    assert len(totals) == 500
    assert sum(t.late_count for t in totals) == control["late_count"]
    assert sum(t.late_minutes for t in totals) == control["late_minutes"]
    assert sum(t.absences for t in totals) == control["absences"]
    assert sum(t.present for t in totals) == control["present"]
    sheet = load_workbook(io.BytesIO(xlsx)).active
    assert sheet.max_row == 501
    assert sum(row[6].value for row in sheet.iter_rows(min_row=2)) == control["late_minutes"]
    assert pdf.startswith(b"%PDF") and pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 1


def test_report_job_runs_in_background_and_gives_a_signed_link(
    hr_x, company_x, client, django_capture_on_commit_callbacks
):
    agent = factories.AgentFactory(company=company_x)
    with tenant_context(company_x.id):
        WorkDay.objects.create(agent=agent, date=START, status="late", late_minutes=15)
    with django_capture_on_commit_callbacks(execute=True):
        res = hr_x.post(
            "/api/v1/reports/",
            {"kind": "payroll", "start": "2026-10-01", "end": "2026-10-31"},
            format="json",
        )
    assert res.status_code == 201, res.content
    job = hr_x.get(f"/api/v1/reports/{res.json()['id']}/").json()
    assert (job["status"], job["progress"]) == ("done", 100)
    download = client.get(job["download_url"])
    assert download.status_code == 200
    assert b"".join(download.streaming_content)[:2] == b"PK"  # xlsx (zip)
    assert client.get(job["download_url"].replace("t=", "t=x")).status_code == 404


@pytest.mark.parametrize("kind", ["punctuality", "checkins", "monthly_sheet", "badges"])
def test_every_report_kind_builds(hr_x, company_x, kind, django_capture_on_commit_callbacks):
    factories.AgentFactory(company=company_x)
    body = {"kind": kind, "start": "2026-10-01", "end": "2026-10-31"}
    with django_capture_on_commit_callbacks(execute=True):
        job = hr_x.post("/api/v1/reports/", body, format="json").json()
    assert hr_x.get(f"/api/v1/reports/{job['id']}/").json()["status"] == "done"


def test_scheduled_monthly_report_is_emailed(company_x):
    with tenant_context(company_x.id):
        ReportSchedule.objects.create(
            kind="punctuality", frequency="monthly", recipients=["drh@ministere-x.ci"]
        )
    tasks.send_scheduled("monthly")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].attachments[0][0].endswith(".xlsx")
    with tenant_context(company_x.id):
        assert ReportJob.objects.filter(status="done").count() == 1


def test_retention_purge_anonymises_gps_then_deletes(company_x):
    import time_machine

    agent = factories.AgentFactory(company=company_x)
    old = datetime(2020, 1, 6, 7, 30, tzinfo=TZ)
    recent = datetime(2025, 6, 2, 7, 30, tzinfo=TZ)  # 17 months old: kept, GPS removed
    with tenant_context(company_x.id):
        for moment in (old, recent):
            CheckIn(
                agent=agent,
                mode="A",
                trust="high",
                server_ts=moment,
                effective_ts=moment,
                result="accepted",
                direction="in",
                latitude=5.3,
                longitude=-4.0,
            ).save()
    with time_machine.travel(datetime(2026, 11, 20, 2, 0, tzinfo=TZ), tick=False):
        tasks.retention_purge()
    with tenant_context(company_x.id):
        remaining = list(CheckIn.objects.all())
        assert len(remaining) == 1  # older than 5 years: deleted
        assert remaining[0].latitude is None  # older than 12 months: GPS removed
