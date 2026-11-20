"""Background report generation with progress, and scheduled e-mails (EF-36, EF-38)."""

import logging
import time
from datetime import date, timedelta
from typing import Any

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.utils import timezone

from apps.tenancy.context import tenant_context
from apps.tenancy.models import Company
from apps.tenancy.scoping import for_each_active_company

from . import generators
from .models import ReportJob, ReportSchedule

logger = logging.getLogger(__name__)

BUILDERS: dict[str, tuple[Any, str]] = {
    ReportJob.Kind.PUNCTUALITY: (generators.punctuality_xlsx, "xlsx"),
    ReportJob.Kind.PAYROLL: (generators.payroll_xlsx, "xlsx"),
    ReportJob.Kind.CHECKINS: (generators.checkins_csv, "csv"),
    ReportJob.Kind.MONTHLY_SHEET: (generators.monthly_sheet_pdf, "pdf"),
    ReportJob.Kind.BADGES: (generators.badges_pdf, "pdf"),
}


def build(job: ReportJob) -> ReportJob:
    company = Company.objects.get(id=job.company_id)
    builder, ext = BUILDERS[job.kind]
    started = time.perf_counter()
    job.status, job.progress = ReportJob.Status.RUNNING, 5
    job.save(update_fields=["status", "progress", "updated_at"])

    def progress(value: int) -> None:
        ReportJob.objects.filter(id=job.id).update(progress=min(99, value))

    try:
        content = builder(
            company,
            job.start,
            job.end,
            unit_id=job.org_unit_id,
            agent_id=job.agent_id,
            progress=progress,
        )
        period = f"{job.start:%Y-%m-%d}_{job.end:%Y-%m-%d}" if job.start and job.end else "complet"
        job.filename = f"{job.kind}_{company.slug}_{period}.{ext}"
        job.file.save(job.filename, ContentFile(content), save=False)
        job.status, job.progress = ReportJob.Status.DONE, 100
    except Exception as exc:  # the job is marked failed, the error is shown to the user
        logger.exception("Report %s failed", job.id)
        job.status, job.error = ReportJob.Status.FAILED, str(exc)[:500]
    job.finished_at = timezone.now()
    job.duration_ms = int((time.perf_counter() - started) * 1000)
    job.save()
    return job


@shared_task(name="reports.generate")
def generate(company_id: str, job_id: str) -> str:
    with tenant_context(company_id):
        job = ReportJob.objects.get(id=job_id)
        return build(job).status


def _period(frequency: str, today: date) -> tuple[date, date]:
    if frequency == ReportSchedule.Frequency.WEEKLY:
        end = today - timedelta(days=today.weekday() + 1)  # last Sunday
        return end - timedelta(days=6), end
    end = today.replace(day=1) - timedelta(days=1)
    return end.replace(day=1), end


@shared_task(name="reports.send_scheduled")
def send_scheduled(frequency: str) -> list[int]:
    """Monday 07:00 (previous week) and the 1st of the month (previous month)."""

    def run(company: Company) -> int:
        sent = 0
        start, end = _period(frequency, timezone.localdate())
        for schedule in ReportSchedule.objects.filter(frequency=frequency, is_active=True):
            job = build(ReportJob.objects.create(kind=schedule.kind, start=start, end=end))
            if job.status != ReportJob.Status.DONE or not schedule.recipients:
                continue
            mail = EmailMessage(
                f"[PointQR] {job.get_kind_display()} du {start:%d/%m} au {end:%d/%m/%Y}",
                f"Bonjour,\n\nVeuillez trouver ci-joint le rapport « {job.get_kind_display()} » "
                f"de {company.legal_name}.\n\nPointQR — Le pointage qui ne ment pas.",
                settings.DEFAULT_FROM_EMAIL,
                schedule.recipients,
            )
            job.file.open("rb")
            mail.attach(job.filename, job.file.read())
            job.file.close()
            mail.send(fail_silently=True)
            sent += 1
        return sent

    return for_each_active_company(run)


@shared_task(name="reports.retention_purge")
def retention_purge() -> list[dict[str, int]]:
    """Minimisation (ENF-04): raw GPS removed after N months, check-ins deleted after N years."""
    from django.db import connection

    def run(company: Company) -> dict[str, int]:
        now = timezone.now()
        gps_before = now - timedelta(days=30 * company.retention_gps_months)
        rows_before = now - timedelta(days=365 * company.retention_checkins_years)
        with connection.cursor() as cursor:
            # The append-only trigger only lets this flag through, for these two operations.
            cursor.execute("SELECT set_config('app.retention_purge', 'on', true)")
            cursor.execute(
                "UPDATE attendance_checkin SET latitude = NULL, longitude = NULL, accuracy_m = NULL "
                "WHERE effective_ts < %s AND latitude IS NOT NULL",
                [gps_before],
            )
            gps = cursor.rowcount
            cursor.execute(
                "DELETE FROM attendance_checkin WHERE effective_ts < %s "
                "AND NOT EXISTS (SELECT 1 FROM attendance_checkin c2 "
                "WHERE c2.corrects_id = attendance_checkin.id) "
                "AND NOT EXISTS (SELECT 1 FROM requests_app_request r "
                "WHERE r.target_checkin_id = attendance_checkin.id "
                "OR r.resulting_checkin_id = attendance_checkin.id)",
                [rows_before],
            )
            deleted = cursor.rowcount
            cursor.execute("SELECT set_config('app.retention_purge', '', true)")
        return {"gps_anonymised": gps, "checkins_deleted": deleted}

    return for_each_active_company(run)
