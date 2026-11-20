"""Kiosk lifecycle: pairing by 6-digit code, machine token, key rotation, revocation (EF-42)."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.attendance import events
from apps.audit.services import record
from apps.organization.models import Site
from apps.tenancy.models import Company
from apps.tenancy.services import check_quota
from common.crypto import b64url, decrypt, encrypt, new_secret_key
from common.exceptions import DomainError

from .models import Kiosk, KioskPairingCode

PAIRING_TTL = timedelta(minutes=15)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_pairing_code(
    site: Site, name: str, *, actor: Any, request: Any = None
) -> tuple[str, KioskPairingCode]:
    company = Company.objects.get(id=site.company_id)
    check_quota(company, "kiosks", Kiosk.objects.filter(status=Kiosk.Status.ACTIVE).count())
    for _ in range(10):
        code = f"{secrets.randbelow(1_000_000):06d}"
        if not KioskPairingCode.objects.filter(
            code_hash=_hash(code), used_at__isnull=True
        ).exists():
            break
    pairing = KioskPairingCode.objects.create(
        site=site,
        name=name,
        code_hash=_hash(code),
        expires_at=timezone.now() + PAIRING_TTL,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    record(
        "kiosk.pairing_code_created",
        pairing,
        actor=actor,
        request=request,
        after={"site": site.name, "name": name},
    )
    return code, pairing


@dataclass(frozen=True, slots=True)
class PairingResult:
    kiosk: Kiosk
    secret: str  # base64url raw HMAC key, shown once to the tablet
    token: str  # machine token "<kiosk_id>.<random>"


def pair(code: str) -> PairingResult:
    """Called by the tablet inside its company's tenant context."""
    pairing = (
        KioskPairingCode.objects.select_for_update()
        .select_related("site")
        .filter(code_hash=_hash(code.strip()), used_at__isnull=True)
        .first()
    )
    if pairing is None or pairing.expires_at < timezone.now():
        raise DomainError(
            "Code d'appairage invalide ou expiré.", code="pairing_invalid", status_code=400
        )
    raw_key = new_secret_key()
    raw_token = secrets.token_urlsafe(32)
    with transaction.atomic():
        kiosk = Kiosk.objects.create(
            site=pairing.site,
            name=pairing.name,
            secret_key=encrypt(raw_key),
            token_hash=_hash(raw_token),
            last_seen_at=timezone.now(),
        )
        pairing.used_at = timezone.now()
        pairing.kiosk = kiosk
        pairing.save(update_fields=["used_at", "kiosk", "updated_at"])
    record("kiosk.paired", kiosk, actor_label=f"Borne {kiosk.name}")
    return PairingResult(kiosk=kiosk, secret=b64url(raw_key), token=f"{kiosk.id}.{raw_token}")


def authenticate(raw: str) -> Kiosk | None:
    kiosk_id, _, secret = raw.partition(".")
    if not kiosk_id or not secret:
        return None
    kiosk = (
        Kiosk.objects.select_related("site").filter(id=kiosk_id).first()
        if _is_uuid(kiosk_id)
        else None
    )
    if kiosk is None or not hmac.compare_digest(kiosk.token_hash, _hash(secret)):
        return None
    return kiosk


def _is_uuid(value: str) -> bool:
    from uuid import UUID

    try:
        UUID(value)
    except ValueError:
        return False
    return True


def heartbeat(kiosk: Kiosk, *, app_version: str, pending: int, key_version: int) -> dict[str, Any]:
    """Keeps the status online, resynchronises the clock and delivers a rotated key."""
    was_offline = kiosk.last_seen_at is None or timezone.now() - kiosk.last_seen_at > timedelta(
        minutes=2
    )
    kiosk.last_seen_at = timezone.now()
    kiosk.app_version = app_version[:32]
    kiosk.pending_offline = max(0, pending)
    kiosk.save(update_fields=["last_seen_at", "app_version", "pending_offline", "updated_at"])
    if was_offline:
        events.publish(
            kiosk.company_id,
            "kiosk.status",
            {"id": str(kiosk.id), "name": kiosk.name, "online": True, "pending": pending},
        )
    body: dict[str, Any] = {"status": kiosk.status, "key_version": kiosk.key_version}
    if kiosk.is_active and key_version != kiosk.key_version:
        body["secret"] = b64url(decrypt(kiosk.secret_key))
    return body


def rotate_key(kiosk: Kiosk, *, actor: Any, request: Any = None) -> Kiosk:
    """Old QR codes stop working at once; the tablet picks the new key on its next heartbeat."""
    kiosk.secret_key = encrypt(new_secret_key())
    kiosk.key_version += 1
    kiosk.save(update_fields=["secret_key", "key_version", "updated_at"])
    record(
        "kiosk.key_rotated",
        kiosk,
        actor=actor,
        request=request,
        after={"key_version": kiosk.key_version},
    )
    return kiosk


def revoke(kiosk: Kiosk, *, actor: Any, request: Any = None) -> Kiosk:
    """Stolen or moved tablet: every QR and machine call is refused from now on."""
    kiosk.status = Kiosk.Status.REVOKED
    kiosk.revoked_at = timezone.now()
    kiosk.save(update_fields=["status", "revoked_at", "updated_at"])
    record("kiosk.revoked", kiosk, actor=actor, request=request)
    events.publish(
        kiosk.company_id,
        "kiosk.status",
        {"id": str(kiosk.id), "name": kiosk.name, "online": False, "revoked": True},
    )
    return kiosk
