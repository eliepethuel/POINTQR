"""Organisation business rules: site keys, phone binding (RG-13) and phone changes (EF-10)."""

import hashlib
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import record
from common.crypto import encrypt, new_secret_key
from common.exceptions import DomainError

from .models import Agent, Device, DeviceChangeRequest, Site


def fingerprint_hash(raw: str) -> str:
    """Phones are identified by a hash of their installation identifier, never the raw value."""
    return hashlib.sha256(raw.strip().encode()).hexdigest()


def ensure_site_key(site: Site) -> None:
    if not site.static_qr_key:
        site.static_qr_key = encrypt(new_secret_key())


def ensure_badge_key(agent: Agent) -> None:
    if not agent.badge_key:
        agent.badge_key = encrypt(new_secret_key())


def rotate_badge(agent: Agent, *, actor: Any, request: Any = None) -> Agent:
    """Reprinting a badge invalidates the previous one (lost or lent card)."""
    agent.badge_key = encrypt(new_secret_key())
    agent.badge_version += 1
    agent.save(update_fields=["badge_key", "badge_version", "updated_at"])
    record(
        "agent.badge_rotated",
        agent,
        actor=actor,
        request=request,
        after={"badge_version": agent.badge_version},
    )
    return agent


def active_device(agent: Agent) -> Device | None:
    return agent.devices.filter(is_active=True).first()


def bind_device(agent: Agent, raw_fingerprint: str, *, model: str = "", os: str = "") -> Device:
    """First activation binds the phone. Afterwards a different phone needs HR approval."""
    digest = fingerprint_hash(raw_fingerprint)
    current = active_device(agent)
    if current is not None:
        if current.fingerprint_hash == digest:
            return current
        DeviceChangeRequest.objects.get_or_create(
            agent=agent,
            status=DeviceChangeRequest.Status.PENDING,
            defaults={"fingerprint_hash": digest, "model": model, "os": os},
        )
        raise DomainError(
            "Ce téléphone n'est pas celui lié à votre compte. Une demande de changement a été "
            "envoyée au service RH.",
            code="device_change_pending",
            status_code=409,
        )
    if Device.objects.filter(fingerprint_hash=digest, is_active=True).exclude(agent=agent).exists():
        raise DomainError(
            "Ce téléphone est déjà lié à un autre agent.", code="device_taken", status_code=409
        )
    try:
        with transaction.atomic():
            device = Device.objects.create(agent=agent, fingerprint_hash=digest, model=model, os=os)
    except IntegrityError as exc:  # concurrent activation
        raise DomainError(
            "Activation concurrente, réessayez.", code="device_conflict", status_code=409
        ) from exc
    record("device.bound", device, actor_label=agent.full_name, after={"model": model, "os": os})
    return device


def decide_device_change(
    change: DeviceChangeRequest, *, approve: bool, actor: Any, request: Any = None
) -> DeviceChangeRequest:
    if change.status != DeviceChangeRequest.Status.PENDING:
        raise DomainError("Demande déjà traitée.", code="already_decided", status_code=409)
    now = timezone.now()
    with transaction.atomic():
        if approve:
            Device.objects.filter(agent=change.agent, is_active=True).update(
                is_active=False, revoked_at=now
            )
            Device.objects.filter(fingerprint_hash=change.fingerprint_hash, is_active=True).update(
                is_active=False, revoked_at=now
            )
            Device.objects.create(
                agent=change.agent,
                fingerprint_hash=change.fingerprint_hash,
                model=change.model,
                os=change.os,
            )
        change.status = (
            DeviceChangeRequest.Status.APPROVED if approve else DeviceChangeRequest.Status.REJECTED
        )
        change.decided_by = actor
        change.decided_at = now
        change.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    record(
        "device.change_" + ("approved" if approve else "rejected"),
        change,
        actor=actor,
        request=request,
    )
    return change


def revoke_device(device: Device, *, actor: Any, request: Any = None) -> Device:
    """Remote sign-out of a phone (ENF-10). The agent re-activates on their next phone."""
    device.is_active = False
    device.revoked_at = timezone.now()
    device.save(update_fields=["is_active", "revoked_at", "updated_at"])
    record("device.revoked", device, actor=actor, request=request)
    return device
