"""Notify users in the app and by e-mail (console backend in development)."""

import logging
from collections.abc import Iterable
from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from apps.accounts.models import Role, User
from apps.organization.models import Agent

from .models import Notification

logger = logging.getLogger(__name__)


def notify(
    users: Iterable[User],
    kind: str,
    title: str,
    body: str = "",
    link: str = "",
    *,
    email: bool = False,
) -> list[Notification]:
    created = [
        Notification.objects.create(user=u, kind=kind, title=title[:200], body=body, link=link)
        for u in users
    ]
    if email:
        recipients = sorted({u.email for u in users if u.email})
        if recipients:

            def _send() -> None:
                try:
                    send_mail(
                        f"[PointQR] {title}",
                        body,
                        settings.DEFAULT_FROM_EMAIL,
                        recipients,
                        fail_silently=False,
                    )
                except Exception:
                    logger.warning("E-mail notification failed", exc_info=True)

            transaction.on_commit(_send)
    return created


def notify_agent(
    agent: Agent, kind: str, title: str, body: str = "", link: str = ""
) -> list[Notification]:
    user = getattr(agent, "user", None)
    return notify([user], kind, title, body, link, email=True) if user else []


def managers_of(agent: Agent) -> list[User]:
    """Responsible of the agent's unit and its parents, then HR as a fallback."""
    managers: list[User] = []
    unit = agent.org_unit
    while unit is not None and not managers:
        manager = unit.manager
        if manager is not None and getattr(manager, "user", None) and manager.id != agent.id:
            managers.append(manager.user)
        unit = unit.parent
    if not managers:
        managers = list(User.objects.filter(roles__contains=[Role.HR], is_active=True))
    return managers


def mark_read(user: User, ids: Iterable[Any] | None = None) -> int:
    from django.utils import timezone

    qs = Notification.objects.filter(user=user, read_at__isnull=True)
    if ids is not None:
        qs = qs.filter(id__in=list(ids))
    return qs.update(read_at=timezone.now())
