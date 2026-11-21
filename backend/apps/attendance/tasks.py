"""Scheduled jobs (Celery beat): absences, missing exits, H+30 alerts (RG-04, RG-05, EF-27)."""

from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from celery import shared_task
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import managers_of, notify, notify_agent
from apps.organization.models import Agent
from apps.schedules.selectors import day_schedule
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Company
from apps.tenancy.scoping import for_each_active_company

from . import workdays
from .models import Period, WorkDay

ALERT_DELAY = timedelta(minutes=30)


def _today(company: Company) -> date:
    return timezone.now().astimezone(ZoneInfo(company.timezone)).date()


@shared_task(name="attendance.close_day")
def close_day() -> list[int]:
    """End of the working day: absences become final (RG-04)."""

    def run(company: Company) -> int:
        return workdays.recompute_range(_today(company), _today(company))

    return for_each_active_company(run)


@shared_task(name="attendance.missing_exits")
def missing_exits() -> list[int]:
    """After midnight: yesterday's open entries become « incomplete », agent notified (RG-05)."""

    def run(company: Company) -> int:
        yesterday = _today(company) - timedelta(days=1)
        workdays.recompute_range(yesterday, yesterday)
        count = 0
        for wd in WorkDay.objects.filter(date=yesterday, incomplete=True).select_related("agent"):
            already = Notification.objects.filter(
                kind=Notification.Kind.MISSING_EXIT,
                link=f"/agent?jour={yesterday}",
                user__agent=wd.agent,
            ).exists()
            if already:
                continue
            notify_agent(
                wd.agent,
                Notification.Kind.MISSING_EXIT,
                "Sortie non pointée",
                f"Vous n'avez pas pointé votre sortie le {yesterday:%d/%m/%Y}. "
                "Envoyez une demande de correction.",
                link=f"/agent?jour={yesterday}",
            )
            count += 1
        return count

    return for_each_active_company(run)


@shared_task(name="attendance.absence_alerts")
def absence_alerts() -> list[int]:
    """Manager alert when an expected agent has not checked in 30 minutes after start (EF-27)."""

    def run(company: Company) -> int:
        tz = ZoneInfo(company.timezone)
        now = timezone.now().astimezone(tz)
        today = now.date()
        present = set(
            WorkDay.objects.filter(date=today, first_in__isnull=False).values_list(
                "agent_id", flat=True
            )
        )
        sent = 0
        agents = Agent.objects.filter(status=Agent.Status.ACTIVE).select_related(
            "schedule", "org_unit", "org_unit__manager"
        )
        for agent in agents:
            if agent.id in present:
                continue
            planned = day_schedule(agent, today, tz)
            if planned is None or not planned.works or planned.start is None:
                continue
            if not planned.start + ALERT_DELAY <= now < planned.start + ALERT_DELAY * 3:
                continue
            link = f"/app/agents/{agent.id}?jour={today}"
            if Notification.objects.filter(kind=Notification.Kind.ABSENT_ALERT, link=link).exists():
                continue
            notify(
                managers_of(agent),
                Notification.Kind.ABSENT_ALERT,
                f"{agent.full_name} n'a pas pointé",
                f"Attendu à {planned.start:%H:%M}, aucun pointage à {now:%H:%M}.",
                link,
            )
            sent += 1
        return sent

    return for_each_active_company(run)


@shared_task(name="attendance.recompute")
def recompute_task(
    company_id: str, start: str, end: str, agent_ids: list[str] | None = None
) -> int:
    """On-demand recomputation (HR action, rule change)."""
    with tenant_context(company_id):
        agents = Agent.objects.filter(id__in=agent_ids) if agent_ids else None
        return workdays.recompute_range(
            date.fromisoformat(start), date.fromisoformat(end), agents=agents
        )


def beat_schedule() -> dict[str, dict[str, Any]]:
    from celery.schedules import crontab

    return {
        "close-day": {"task": "attendance.close_day", "schedule": crontab(hour=23, minute=30)},
        "missing-exits": {
            "task": "attendance.missing_exits",
            "schedule": crontab(hour=0, minute=20),
        },
        "absence-alerts": {
            "task": "attendance.absence_alerts",
            "schedule": crontab(minute="*/15", hour="5-12"),
        },
    }


@shared_task(name="attendance.close_period")
def close_period(company_id: str, period_id: str, user_id: str) -> str:
    """Monthly closing (RG-14): recompute every day of the month, then freeze it."""
    from apps.accounts.models import User
    from apps.audit.services import record

    with tenant_context(company_id):
        period = Period.objects.get(id=period_id)
        if period.status == Period.Status.CLOSED:
            return period.status
        first = period.month
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        workdays.recompute_range(first, min(last, timezone.localdate()))
        actor = User.objects.get(id=user_id)
        period.status = Period.Status.CLOSED
        period.closed_at = timezone.now()
        period.closed_by = actor
        period.save()
        record("period.closed", period, actor=actor)
        return period.status
