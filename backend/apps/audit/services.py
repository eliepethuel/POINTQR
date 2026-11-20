"""Writing the audit trail. Call ``record`` from services on every sensitive action."""

import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.http import HttpRequest

from apps.tenancy.context import current_company_id

from .models import AuditLog


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def _client_ip(request: HttpRequest | None) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
    return ip or None


def record(
    action: str,
    obj: models.Model | None,
    *,
    actor: Any = None,
    actor_label: str | None = None,
    request: HttpRequest | None = None,
    before: Any = None,
    after: Any = None,
    object_type: str | None = None,
    object_id: str | None = None,
) -> AuditLog:
    company_id = current_company_id()
    user = actor if getattr(actor, "is_authenticated", False) else None
    label = actor_label or (str(user) if user else "système")
    return AuditLog.objects.create(
        company_id=company_id,
        actor_user=user,
        actor_label=label[:200],
        action=action,
        object_type=object_type or (obj._meta.label_lower if obj is not None else ""),
        object_id=object_id or (str(obj.pk) if obj is not None else ""),
        object_label=str(obj)[:255] if obj is not None else "",
        before=_jsonable(before),
        after=_jsonable(after),
        ip=_client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
    )
