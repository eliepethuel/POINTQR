"""Which schedule applies to an agent on a given day (rotation → exception → default)."""

from datetime import date
from zoneinfo import ZoneInfo

from django.db.models import Q

from apps.attendance.rules import DaySchedule, day_schedule_from
from apps.organization.models import Agent

from .models import PublicHoliday, Schedule, ScheduleAssignment, ScheduleException


def schedule_for(agent: Agent, day: date) -> Schedule | None:
    assignment = (
        ScheduleAssignment.objects.filter(agent=agent, start_date__lte=day, end_date__gte=day)
        .select_related("schedule")
        .order_by("-start_date")
        .first()
    )
    if assignment is not None:
        return assignment.schedule
    exception = (
        ScheduleException.objects.filter(start_date__lte=day, end_date__gte=day)
        .filter(Q(org_unit__isnull=True) | Q(org_unit_id=agent.org_unit_id))
        .select_related("schedule")
        .order_by("org_unit_id")  # unit-specific exceptions first (NULLs sort last)
        .first()
    )
    if exception is not None:
        return exception.schedule
    return agent.schedule


def day_schedule(agent: Agent, day: date, tz: ZoneInfo) -> DaySchedule | None:
    schedule = schedule_for(agent, day)
    if schedule is None:
        return None
    return day_schedule_from(
        day=day,
        weekdays=schedule.weekdays,
        start=schedule.start_time,
        end=schedule.end_time,
        tz=tz,
        break_minutes=schedule.break_minutes,
        late_tolerance_min=schedule.late_tolerance_min,
        early_tolerance_min=schedule.early_tolerance_min,
        overtime_threshold_min=schedule.overtime_threshold_min,
    )


def is_holiday(day: date, country: str = "CI") -> bool:
    """Company-specific rows override the national list (a day can be marked as worked)."""
    rows = list(
        PublicHoliday.objects.filter(date=day, country=country).values("company_id", "is_worked")
    )
    own = [r for r in rows if r["company_id"] is not None]
    if own:
        return not own[0]["is_worked"]
    return any(not r["is_worked"] for r in rows)
