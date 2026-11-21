"""Read model of the real-time dashboard (EF-25, EF-37): today's KPIs, sites, units, live feed."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db.models import Count, Q
from django.utils import timezone

from apps.kiosks.models import Kiosk
from apps.organization.models import Agent, OrgUnit, Site
from apps.schedules.selectors import day_schedule
from apps.tenancy.models import Company

from .models import CheckIn, Result, WorkDay

LATE_STATUSES = (WorkDay.Status.LATE, WorkDay.Status.LATE_JUSTIFIED)


def _expected_by_now(agent: Agent, day: date, now: datetime, tz: ZoneInfo) -> bool:
    planned = day_schedule(agent, day, tz)
    return bool(planned and planned.works and planned.start and planned.start <= now)


def today(company: Company, unit_ids: set[UUID] | None = None) -> dict[str, Any]:
    tz = ZoneInfo(company.timezone or "Africa/Abidjan")
    now = timezone.now().astimezone(tz)
    day = now.date()
    agents = Agent.objects.filter(status=Agent.Status.ACTIVE).select_related("schedule", "site")
    if unit_ids is not None:
        agents = agents.filter(org_unit_id__in=unit_ids)
    agent_list = list(agents)
    days = {w.agent_id: w for w in WorkDay.objects.filter(date=day, agent__in=agent_list)}

    present = late = left_early = on_site = absent = expected = 0
    per_site: dict[UUID | None, dict[str, int]] = defaultdict(
        lambda: {"present": 0, "late": 0, "absent": 0}
    )
    for agent in agent_list:
        wd = days.get(agent.id)
        site_stats = per_site[agent.site_id]
        if wd and wd.first_in:
            present += 1
            site_stats["present"] += 1
            if wd.status in LATE_STATUSES:
                late += 1
                site_stats["late"] += 1
            if wd.early_leave_minutes:
                left_early += 1
            if wd.last_out is None or (wd.first_in and wd.last_out < wd.first_in):
                on_site += 1
            expected += 1
        elif _expected_by_now(agent, day, now, tz):
            expected += 1
            absent += 1
            site_stats["absent"] += 1

    sites = [
        {
            "id": s.id,
            "name": s.name,
            "latitude": float(s.latitude),
            "longitude": float(s.longitude),
            "radius_m": s.radius_m,
            **per_site.get(s.id, {"present": 0, "late": 0, "absent": 0}),
        }
        for s in Site.objects.filter(is_active=True)
    ]
    start = datetime.combine(day, time.min, tzinfo=tz)
    checkins = CheckIn.objects.filter(effective_ts__gte=start).select_related("agent", "site")
    if unit_ids is not None:
        checkins = checkins.filter(agent__org_unit_id__in=unit_ids)
    recent = [
        {
            "id": c.id,
            "agent_name": c.agent.full_name if c.agent else "Inconnu",
            "site": c.site.name if c.site else None,
            "direction": c.direction,
            "mode": c.mode,
            "at": c.effective_ts,
            "result": c.result,
            "refusal_code": c.refusal_code,
        }
        for c in checkins.order_by("-effective_ts")[:25]
    ]
    anomalies = checkins.filter(result=Result.REFUSED).count()
    hourly = _hourly_arrivals(day, tz, unit_ids)
    return {
        "date": day,
        "server_time": now,
        "kpis": {
            "present": present,
            "late": late,
            "absent": absent,
            "left_early": left_early,
            "on_site": on_site,
            "expected": expected,
            "anomalies": anomalies,
            "agents": len(agent_list),
        },
        "sites": sites,
        "units": unit_ranking(day - timedelta(days=29), day, unit_ids),
        "recent": recent,
        "arrivals_by_hour": hourly,
        "kiosks": [
            {
                "id": k.id,
                "name": k.name,
                "site": k.site.name,
                "status": k.status,
                "online": bool(
                    k.last_seen_at and timezone.now() - k.last_seen_at < timedelta(minutes=2)
                ),
                "pending": k.pending_offline,
            }
            for k in Kiosk.objects.select_related("site")
        ],
    }


def _hourly_arrivals(day: date, tz: ZoneInfo, unit_ids: set[UUID] | None) -> list[dict[str, Any]]:
    start = datetime.combine(day, time.min, tzinfo=tz)
    qs = CheckIn.objects.filter(
        effective_ts__gte=start,
        effective_ts__lt=start + timedelta(days=1),
        result=Result.ACCEPTED,
        direction="in",
    )
    if unit_ids is not None:
        qs = qs.filter(agent__org_unit_id__in=unit_ids)
    buckets: dict[int, int] = defaultdict(int)
    for ts in qs.values_list("effective_ts", flat=True):
        buckets[ts.astimezone(tz).hour] += 1
    # Office hours by default, widened to every hour that had arrivals (night shifts, RG-08).
    first = min([5, *buckets])
    last = max([20, *buckets])
    return [{"hour": h, "count": buckets.get(h, 0)} for h in range(first, last + 1)]


def unit_ranking(start: date, end: date, unit_ids: set[UUID] | None = None) -> list[dict[str, Any]]:
    """Services ranked by punctuality rate over a period (EF-37)."""
    qs = WorkDay.objects.filter(
        date__gte=start, date__lte=end, first_in__isnull=False, agent__org_unit__isnull=False
    )
    if unit_ids is not None:
        qs = qs.filter(agent__org_unit_id__in=unit_ids)
    rows = qs.values("agent__org_unit_id").annotate(
        days=Count("id"), late=Count("id", filter=Q(status__in=LATE_STATUSES))
    )
    names = dict(OrgUnit.objects.values_list("id", "name"))
    ranking = [
        {
            "id": r["agent__org_unit_id"],
            "name": names.get(r["agent__org_unit_id"], "—"),
            "days": r["days"],
            "late": r["late"],
            "punctuality": round(100 * (r["days"] - r["late"]) / r["days"], 1)
            if r["days"]
            else 100.0,
        }
        for r in rows
    ]
    return sorted(ranking, key=lambda r: (-r["punctuality"], r["name"]))
