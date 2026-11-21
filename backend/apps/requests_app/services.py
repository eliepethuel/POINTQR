"""Approval circuit: manager then HR, configurable to 1 or 2 levels (EF-29 to EF-32)."""

from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.attendance import corrections, events, workdays
from apps.attendance.models import CheckIn
from apps.audit.services import record
from apps.notifications.models import Notification
from apps.notifications.services import managers_of, notify, notify_agent
from apps.organization.models import Agent
from apps.organization.selectors import unit_descendant_ids
from apps.tenancy.models import Company
from common.exceptions import DomainError

from .models import Request, RequestDecision

MAX_ATTACHMENT = 5 * 1024 * 1024
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}


def _validate_attachment(upload: Any) -> None:
    if upload is None:
        return
    if upload.size and upload.size > MAX_ATTACHMENT:
        raise DomainError(
            "Pièce jointe trop lourde (5 Mo maximum).", code="file_too_large", status_code=400
        )
    if upload.content_type not in ALLOWED_TYPES:
        raise DomainError(
            "Formats acceptés : PDF, JPEG, PNG, WebP.", code="file_type", status_code=400
        )


def _has_manager(agent: Agent) -> bool:
    unit = agent.org_unit
    while unit is not None:
        if unit.manager_id and unit.manager_id != agent.id:
            return True
        unit = unit.parent
    return False


def create(
    *,
    company: Company,
    agent: Agent,
    author: User,
    kind: str,
    category: str,
    target_date: Any,
    reason: str,
    attachment: Any = None,
    target_checkin: CheckIn | None = None,
    requested_direction: str = "",
    requested_time: datetime | None = None,
) -> Request:
    workdays.ensure_open(target_date)
    _validate_attachment(attachment)
    if kind == Request.Kind.CORRECTION and requested_time is None:
        raise DomainError("Indiquez l'heure à retenir.", code="time_required", status_code=400)
    if requested_time is not None and requested_time > timezone.now():
        raise DomainError(
            "L'heure demandée est dans le futur : une correction porte sur un pointage passé.",
            code="future",
            status_code=400,
        )
    if target_checkin is not None and target_checkin.agent_id != agent.id:
        raise DomainError("Pointage introuvable.", code="not_found", status_code=404)
    status = Request.Status.PENDING_MANAGER if _has_manager(agent) else Request.Status.PENDING_HR
    req = Request.objects.create(
        agent=agent,
        kind=kind,
        category=category,
        target_date=target_date,
        reason=reason,
        attachment=attachment or "",
        target_checkin=target_checkin,
        requested_direction=requested_direction,
        requested_time=requested_time,
        status=status,
        created_by=author,
    )
    approvers = managers_of(agent) if status == Request.Status.PENDING_MANAGER else _hr_users()
    notify(
        approvers,
        Notification.Kind.REQUEST,
        f"Demande de {agent.full_name}",
        f"{req.get_kind_display()} — {req.get_category_display()} du {target_date:%d/%m/%Y}",
        link=f"/app/demandes?id={req.id}",
    )
    events.publish(
        company.id,
        "request.created",
        {"id": str(req.id), "agent_name": agent.full_name, "kind": kind},
        unit_id=agent.org_unit_id,
    )
    record("request.created", req, actor=author)
    return req


def _hr_users() -> list[User]:
    return list(User.objects.filter(roles__overlap=[Role.HR, Role.COMPANY_ADMIN], is_active=True))


def can_decide(user: User, req: Request) -> bool:
    if req.status == Request.Status.PENDING_HR:
        return user.has_role(Role.HR, Role.COMPANY_ADMIN)
    if req.status != Request.Status.PENDING_MANAGER:
        return False
    if user.has_role(Role.HR, Role.COMPANY_ADMIN):
        return True
    agent = getattr(user, "agent", None)
    if agent is None or req.agent_id == agent.id:
        return False  # nobody validates their own request
    units: set[Any] = set()
    for unit in agent.managed_units.all():
        units |= unit_descendant_ids(unit.id)
    return req.agent.org_unit_id in units


def decide(
    req: Request,
    *,
    user: User,
    approve: bool,
    comment: str = "",
    company: Company,
    request: Any = None,
) -> Request:
    if not can_decide(user, req):
        raise DomainError(
            "Vous ne pouvez pas valider cette demande.", code="not_approver", status_code=403
        )
    workdays.ensure_open(req.target_date)
    # All or nothing: business errors (4xx) are committed by TenantMiddleware (refused check-ins
    # must stay on record), so a failed correction must not leave an "approved" request behind.
    with transaction.atomic():
        return _decide(
            req, user=user, approve=approve, comment=comment, company=company, request=request
        )


def _decide(
    req: Request,
    *,
    user: User,
    approve: bool,
    comment: str,
    company: Company,
    request: Any,
) -> Request:
    level = (
        RequestDecision.Level.MANAGER
        if req.status == Request.Status.PENDING_MANAGER
        else RequestDecision.Level.HR
    )
    RequestDecision.objects.create(
        request=req, level=level, decided_by=user, approved=approve, comment=comment
    )
    before = req.status
    if not approve:
        req.status = Request.Status.REJECTED
    elif level == RequestDecision.Level.MANAGER and company.approval_levels >= 2:
        req.status = Request.Status.PENDING_HR
        notify(
            _hr_users(),
            Notification.Kind.REQUEST,
            f"Demande de {req.agent.full_name} validée par le manager",
            "À valider par le service RH.",
            link=f"/app/demandes?id={req.id}",
        )
    else:
        req.status = Request.Status.APPROVED
        # Persist the approval first: recomputing the day reads approved justifications (RG-11).
        req.save(update_fields=["status", "updated_at"])
        _apply(req, user=user, company=company, request=request)
    req.save(update_fields=["status", "resulting_checkin", "updated_at"])
    record(
        f"request.{'approved' if approve else 'rejected'}",
        req,
        actor=user,
        request=request,
        before={"status": before},
        after={"status": req.status, "comment": comment},
    )
    if req.status in (Request.Status.APPROVED, Request.Status.REJECTED):
        verdict = "validée" if req.status == Request.Status.APPROVED else "refusée"
        notify_agent(
            req.agent,
            Notification.Kind.REQUEST,
            f"Votre demande a été {verdict}",
            comment or f"{req.get_kind_display()} du {req.target_date:%d/%m/%Y}",
            "/agent",
        )
    return req


def _apply(req: Request, *, user: User, company: Company, request: Any) -> None:
    """An approved correction adds a linked check-in; a justification changes the day status."""
    if req.kind == Request.Kind.CORRECTION and req.requested_time is not None:
        direction = req.requested_direction or (
            req.target_checkin.direction if req.target_checkin else "out"
        )
        line = corrections.correct(
            company=company,
            agent=req.agent,
            author=user,
            reason=req.reason,
            effective_ts=req.requested_time,
            direction=direction,
            original=req.target_checkin,
            request=request,
        )
        req.resulting_checkin = line
    else:
        workdays.recompute(req.agent, req.target_date, company=company)


def cancel(req: Request, *, user: User) -> Request:
    if req.created_by_id != user.id or req.status not in (
        Request.Status.PENDING_MANAGER,
        Request.Status.PENDING_HR,
    ):
        raise DomainError(
            "Cette demande ne peut plus être annulée.", code="not_cancellable", status_code=409
        )
    req.status = Request.Status.CANCELLED
    req.save(update_fields=["status", "updated_at"])
    record("request.cancelled", req, actor=user)
    return req
