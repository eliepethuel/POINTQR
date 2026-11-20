"""Corrections never replace the original check-in: they add a linked line (RG-12, EF-32, R7)."""

from datetime import datetime
from typing import Any

from django.utils import timezone

from apps.audit.services import record
from apps.organization.models import Agent
from apps.tenancy.models import Company
from common.exceptions import DomainError

from . import workdays
from .models import CheckIn, Direction, Mode, Result, Trust


def correct(
    *,
    company: Company,
    agent: Agent,
    author: Any,
    reason: str,
    effective_ts: datetime,
    direction: str,
    original: CheckIn | None = None,
    request: Any = None,
) -> CheckIn:
    """Adds a correction line. ``original`` given = replaces that check-in in the computations;
    otherwise the line adds a missed check-in (forgotten exit, RG-05)."""
    if direction not in Direction.values:
        raise DomainError("Sens de pointage invalide.", code="invalid_direction", status_code=400)
    if not reason.strip():
        raise DomainError("Le motif est obligatoire.", code="reason_required", status_code=400)
    if effective_ts > timezone.now():
        raise DomainError(
            "Une correction ne peut pas être dans le futur.", code="future", status_code=400
        )
    if original is not None and original.agent_id != agent.id:
        raise DomainError(
            "Ce pointage appartient à un autre agent.", code="wrong_agent", status_code=400
        )
    day = workdays.work_date_of(
        original or CheckIn(agent=agent, effective_ts=effective_ts), company
    )
    workdays.ensure_open(day)  # RG-14

    line = CheckIn(
        agent=agent,
        site=original.site if original else agent.site,
        kiosk=None,
        direction=direction,
        mode=original.mode if original else Mode.KIOSK_QR,
        trust=Trust.MEDIUM,
        server_ts=timezone.now(),
        effective_ts=effective_ts,
        result=Result.ACCEPTED,
        corrects=original,
        is_correction=True,
        reason=reason.strip(),
        author=author if getattr(author, "is_authenticated", False) else None,
    )
    line.save()
    record(
        "checkin.corrected",
        line,
        actor=author,
        request=request,
        before=(
            {
                "id": str(original.id),
                "direction": original.direction,
                "effective_ts": original.effective_ts.isoformat(),
                "result": original.result,
            }
            if original
            else None
        ),
        after={"direction": direction, "effective_ts": effective_ts.isoformat(), "reason": reason},
    )
    workdays.recompute(agent, day, company=company)
    return line
