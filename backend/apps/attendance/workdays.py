"""Builds WorkDay rows from check-ins with the pure rules (RG-01 to RG-15)."""

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone

from apps.organization.models import Agent
from apps.schedules.selectors import day_schedule, is_holiday
from apps.tenancy.models import Company
from common.exceptions import DomainError

from . import rules
from .models import CheckIn, Period, Result, WorkDay


def _justifications(agent: Agent, day: date) -> rules.Justifications:
    """Approved requests change the status without erasing the check-ins (RG-11, RG-10)."""
    from apps.requests_app.models import Request

    approved = set(
        Request.objects.filter(
            agent=agent, target_date=day, status=Request.Status.APPROVED
        ).values_list("category", flat=True)
    )
    return rules.Justifications(
        late=Request.Category.LATE in approved,
        absence=Request.Category.ABSENCE in approved,
        overtime_validated=Request.Category.OVERTIME in approved,
    )


def is_closed(day: date) -> bool:
    return Period.objects.filter(month=day.replace(day=1), status=Period.Status.CLOSED).exists()


def ensure_open(day: date) -> None:
    """Closed periods (handed over to payroll) can no longer change (RG-14)."""
    if is_closed(day):
        raise DomainError(
            f"La période {day:%m/%Y} est clôturée : demandez sa réouverture à l'administrateur.",
            code="period_closed",
            status_code=409,
        )


def punches_for(agent: Agent, day: date, tz: ZoneInfo, night: bool) -> list[rules.Punch]:
    start = datetime.combine(day, time.min, tzinfo=tz)
    # A night shift reaches into the next morning (RG-15).
    end = start + (timedelta(days=1, hours=12) if night else timedelta(days=1))
    rows = CheckIn.objects.filter(
        agent=agent, result=Result.ACCEPTED, effective_ts__gte=start, effective_ts__lt=end
    ).order_by("effective_ts")
    punches = []
    for c in rows:
        local = c.effective_ts.astimezone(tz)
        if rules.work_date_for(local, night_shift=night) != day:
            continue
        punches.append(
            rules.Punch(
                at=local,
                direction=c.direction,
                id=str(c.id),
                corrects=str(c.corrects_id) if c.corrects_id else None,
            )
        )
    return punches


def recompute(
    agent: Agent,
    day: date,
    *,
    company: Company | None = None,
    now: datetime | None = None,
    force: bool = False,
) -> WorkDay | None:
    """(Re)computes one agent's day. Closed periods are left untouched unless ``force``."""
    if not force and is_closed(day):
        return WorkDay.objects.filter(agent=agent, date=day).first()
    company = company or Company.objects.get(id=agent.company_id)
    tz = ZoneInfo(company.timezone or "Africa/Abidjan")
    planned = day_schedule(agent, day, tz) or rules.DaySchedule(works=False)
    night = bool(planned.start and planned.end and planned.end.date() > planned.start.date())
    result = rules.compute_day(
        planned,
        punches_for(agent, day, tz, night),
        now=(now or timezone.now()).astimezone(tz),
        holiday=is_holiday(day, company.country),
        justifications=_justifications(agent, day),
    )
    defaults: dict[str, Any] = {
        "status": result.status.value,
        "first_in": result.first_in,
        "last_out": result.last_out,
        "planned_start": planned.start,
        "planned_end": planned.end,
        "late_minutes": result.late_minutes,
        "early_leave_minutes": result.early_leave_minutes,
        "worked_minutes": result.worked_minutes,
        "overtime_minutes": result.overtime_minutes,
        "overtime_validated": result.overtime_validated,
        "incomplete": result.incomplete,
    }
    workday, _ = WorkDay.objects.update_or_create(agent=agent, date=day, defaults=defaults)
    return workday


def recompute_range(
    start: date, end: date, *, agents: Iterable[Agent] | None = None, now: datetime | None = None
) -> int:
    count = 0
    agent_list = (
        list(agents)
        if agents is not None
        else list(
            Agent.objects.filter(status=Agent.Status.ACTIVE).select_related("schedule", "org_unit")
        )
    )
    if not agent_list:
        return 0
    company = Company.objects.get(id=agent_list[0].company_id)
    day = start
    while day <= end:
        for agent in agent_list:
            if recompute(agent, day, company=company, now=now) is not None:
                count += 1
        day += timedelta(days=1)
    return count


def work_date_of(checkin: CheckIn, company: Company) -> date:
    tz = ZoneInfo(company.timezone or "Africa/Abidjan")
    night = bool(checkin.agent and checkin.agent.schedule and checkin.agent.schedule.is_night)
    return rules.work_date_for(checkin.effective_ts.astimezone(tz), night_shift=night)


def today_queryset(day: date) -> Any:
    return WorkDay.objects.filter(date=day).select_related(
        "agent", "agent__site", "agent__org_unit"
    )


def scope_filter(unit_ids: set[Any] | None) -> Q:
    return Q() if unit_ids is None else Q(agent__org_unit_id__in=unit_ids)
