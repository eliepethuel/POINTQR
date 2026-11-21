"""Agent onboarding (EF-09): invitation by e-mail (or link / QR shown by HR), first password.

The phone itself is bound at the first sign-in of the agent app (RG-13), not here.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record
from apps.organization.models import Agent
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Company
from common.exceptions import DomainError

from .models import ActivationInvite, Role, User


@dataclass(frozen=True, slots=True)
class Invitation:
    agent: Agent
    username: str
    link: str
    expires_at: datetime
    sent_to: str


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def account_state(user: User | None) -> str:
    """none (no account yet) · invited (link pending) · active (password chosen)."""
    if user is None:
        return "none"
    if user.has_usable_password():
        return "active"
    pending = user.invites.filter(used_at__isnull=True, expires_at__gt=timezone.now()).exists()
    return "invited" if pending else "none"


def _account_for(agent: Agent) -> User:
    user = User.objects.filter(agent=agent).first()
    if user is not None:
        return user
    company = Company.objects.get(id=agent.company_id)
    username = agent.employee_number.strip().lower()
    if User.objects.filter(username=username).exists():
        raise DomainError(
            f"L'identifiant « {username} » est déjà pris : créez le compte depuis Utilisateurs.",
            code="username_taken",
            status_code=409,
        )
    return User.objects.create_user(
        username,
        None,  # unusable until the agent chooses it from the link
        company=company,
        roles=[Role.AGENT],
        agent=agent,
        email=agent.email,
        display_name=agent.full_name,
    )


def invite(agent: Agent, *, actor: Any, request: Any = None) -> Invitation:
    if agent.status != Agent.Status.ACTIVE:
        raise DomainError("Cet agent est inactif.", code="agent_inactive", status_code=409)
    user = _account_for(agent)
    if user.has_usable_password():
        raise DomainError(
            "Ce compte est déjà activé : l'agent se connecte avec son identifiant.",
            code="already_active",
            status_code=409,
        )
    now = timezone.now()
    # A new link replaces the previous ones.
    user.invites.filter(used_at__isnull=True, expires_at__gt=now).update(expires_at=now)
    token = secrets.token_urlsafe(24)
    company = Company.objects.get(id=agent.company_id)
    invitation = ActivationInvite.objects.create(
        user=user,
        token_hash=_hash(token),
        expires_at=now + timedelta(days=settings.ACTIVATION_DAYS),
        sent_to=agent.email,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    link = f"{settings.FRONTEND_URL}/activation?entreprise={company.code}&jeton={token}"
    if agent.email:
        from .tasks import send_invitation

        args = (
            agent.email,
            agent.first_names,
            company.legal_name,
            user.username,
            link,
            invitation.expires_at.strftime("%d/%m/%Y"),
        )
        transaction.on_commit(lambda: send_invitation.delay(*args))
    record(
        "agent.invited",
        agent,
        actor=actor,
        request=request,
        after={"username": user.username, "sent_to": agent.email or "lien affiché"},
    )
    return Invitation(agent, user.username, link, invitation.expires_at, agent.email)


def invite_all(*, actor: Any, request: Any = None) -> dict[str, int]:
    """Invites every active agent who has no active account and no pending link."""
    counts = {"invited": 0, "emailed": 0, "without_email": 0, "skipped": 0}
    agents = Agent.objects.filter(status=Agent.Status.ACTIVE).order_by("employee_number")
    for agent in agents:
        if account_state(User.objects.filter(agent=agent).first()) != "none":
            counts["skipped"] += 1
            continue
        try:
            with transaction.atomic():
                invitation = invite(agent, actor=actor, request=request)
        except DomainError:
            counts["skipped"] += 1
            continue
        counts["invited"] += 1
        counts["emailed" if invitation.sent_to else "without_email"] += 1
    return counts


def _pending(token: str) -> ActivationInvite:
    invitation = (
        ActivationInvite.objects.select_related("user", "user__agent")
        .filter(token_hash=_hash(token.strip()), used_at__isnull=True)
        .first()
    )
    if invitation is None or invitation.expires_at <= timezone.now():
        raise DomainError(
            "Ce lien d'activation est invalide ou expiré : demandez-en un nouveau au service RH.",
            code="activation_invalid",
            status_code=400,
        )
    return invitation


def check(company: Company, token: str) -> dict[str, str]:
    """What the activation page shows before the agent chooses a password."""
    with tenant_context(company.id):
        user = _pending(token).user
        return {
            "first_name": user.agent.first_names if user.agent else user.display_name,
            "username": user.username,
            "company": company.legal_name,
        }


def activate(company: Company, token: str, password: str, *, request: Any = None) -> User:
    """Sets the first password; the link can be used only once."""
    if not company.is_active:
        raise DomainError(
            "Cette entreprise est suspendue.", code="company_suspended", status_code=403
        )
    with tenant_context(company.id):
        invitation = _pending(token)
        user = invitation.user
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise DomainError(
                " ".join(exc.messages), code="weak_password", status_code=400
            ) from exc
        user.set_password(password)
        user.save(update_fields=["password"])
        invitation.used_at = timezone.now()
        invitation.save(update_fields=["used_at", "updated_at"])
        record("agent.activated", user, actor=user, request=request)
        return user
