"""Check-in pipeline (CDC section 5, EF-17 to EF-22, RG-01, RG-06 to RG-08).

Controls run in order and each failure has a refusal code. Every refusal is recorded (EF-21),
pushed in real time to HR and never creates a presence status (RG-08). The retained time is always
the server's (RG-01), except for kiosk check-ins made offline, which keep the kiosk's clock.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone

from apps.kiosks.models import Kiosk
from apps.organization.models import Agent, Device, Site
from apps.organization.services import fingerprint_hash
from apps.schedules.selectors import day_schedule
from apps.tenancy.models import Company
from common.crypto import decrypt

from . import events, rules, tokens
from .geo import haversine_m
from .models import CheckIn, Direction, Mode, RefusalCode, Result, Trust

REPLAY_TTL_SECONDS = 90
OFFLINE_MAX_AGE = timedelta(days=7)
OFFLINE_MAX_FUTURE = timedelta(minutes=5)


@dataclass(slots=True)
class Outcome:
    checkin: CheckIn
    message: str
    late_minutes: int = 0
    details: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.checkin.result == Result.ACCEPTED


class Refusal(Exception):
    def __init__(self, code: str, *details: str) -> None:
        super().__init__(code)
        self.code = code
        self.details = [code, *[d for d in details if d != code]]


MESSAGES = {c.value: c.label for c in RefusalCode}


def tz_of(company: Company) -> ZoneInfo:
    return ZoneInfo(company.timezone or "Africa/Abidjan")


# --- helpers ---------------------------------------------------------------------------------------


def _replay_once(kiosk_id: UUID, window: int, device_hash: str) -> bool:
    """One use per (QR window, phone): several agents scan the same kiosk QR (ADR-0005)."""
    return bool(cache.add(f"pqr:replay:{kiosk_id}:{window}:{device_hash}", 1, REPLAY_TTL_SECONDS))


def _accepted_today(agent: Agent, moment: datetime, tz: ZoneInfo, night: bool) -> list[CheckIn]:
    work_date = rules.work_date_for(moment.astimezone(tz), night_shift=night)
    start = datetime.combine(work_date, datetime.min.time(), tzinfo=tz)
    end = start + timedelta(days=1, hours=12 if night else 0)
    return list(
        CheckIn.objects.filter(
            agent=agent, result=Result.ACCEPTED, effective_ts__gte=start, effective_ts__lt=end
        ).order_by("effective_ts")
    )


def _decide_direction(
    agent: Agent, moment: datetime, tz: ZoneInfo, requested: str | None, company: Company
) -> str:
    allowed = {Direction.IN, Direction.OUT}
    if company.break_checkins_enabled:
        allowed |= {Direction.BREAK_OUT, Direction.BREAK_IN}
    if requested in allowed:
        return str(requested)
    schedule = agent.schedule
    today = _accepted_today(agent, moment, tz, bool(schedule and schedule.is_night))
    punches = [rules.Punch(at=c.effective_ts, direction=c.direction) for c in today]
    return rules.next_direction(punches)


def _last_accepted(agent: Agent) -> CheckIn | None:
    return (
        CheckIn.objects.filter(agent=agent, result=Result.ACCEPTED)
        .order_by("-effective_ts")
        .first()
    )


def _status(agent: Agent, moment: datetime, direction: str, tz: ZoneInfo) -> tuple[str, int]:
    local = moment.astimezone(tz)
    schedule = agent.schedule
    work_date = rules.work_date_for(local, night_shift=bool(schedule and schedule.is_night))
    planned = day_schedule(agent, work_date, tz)
    return rules.arrival_message(planned, local, direction)


def _record(**fields: Any) -> CheckIn:
    checkin = CheckIn(**fields)
    checkin.save()
    return checkin


def _publish(checkin: CheckIn, agent: Agent | None, message: str) -> None:
    accepted = checkin.result == Result.ACCEPTED
    events.publish(
        checkin.company_id,
        "checkin.accepted" if accepted else "checkin.refused",
        {
            "id": str(checkin.id),
            "agent_id": str(agent.id) if agent else None,
            "agent_name": agent.full_name if agent else "Inconnu",
            "site": checkin.site.name if checkin.site else None,
            "direction": checkin.direction,
            "mode": checkin.mode,
            "at": checkin.effective_ts.isoformat(),
            "result": checkin.result,
            "refusal_code": checkin.refusal_code,
            "message": message,
        },
        unit_id=agent.org_unit_id if agent else None,
    )


def _finish(
    agent: Agent,
    *,
    company: Company,
    moment: datetime,
    base: dict[str, Any],
    requested_direction: str | None,
) -> Outcome:
    """Shared tail: duplicate check (RG-06), direction (RG-07), status (EF-20)."""
    tz = tz_of(company)
    previous = _last_accepted(agent)
    if rules.is_duplicate(previous.effective_ts if previous else None, moment):
        checkin = _record(
            **base,
            agent=agent,
            result=Result.IGNORED,
            refusal_code=RefusalCode.DUPLICATE,
            refusal_details=[RefusalCode.DUPLICATE],
            direction=previous.direction if previous else "",
        )
        return Outcome(checkin, "Déjà pointé il y a moins de 2 minutes.")
    direction = _decide_direction(agent, moment, tz, requested_direction, company)
    message, minutes = _status(agent, moment, direction, tz)
    checkin = _record(**base, agent=agent, result=Result.ACCEPTED, direction=direction)
    _publish(checkin, agent, message)
    # Keep the computed day current for the live dashboard (it stays recomputable at any time).
    from .workdays import recompute, work_date_of

    recompute(agent, work_date_of(checkin, company), company=company, now=moment)
    return Outcome(checkin, message, late_minutes=minutes)


def _refuse(refusal: Refusal, *, agent: Agent | None, base: dict[str, Any]) -> Outcome:
    message = MESSAGES.get(refusal.code, "Pointage refusé")
    checkin = _record(
        **base,
        agent=agent,
        result=Result.REFUSED,
        refusal_code=refusal.code,
        refusal_details=refusal.details,
    )
    _publish(checkin, agent, message)
    return Outcome(checkin, message, details=refusal.details)


# --- Mode A and D: the agent's phone scans a QR -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class PhoneScan:
    token: str
    device_id: str
    latitude: float | None
    longitude: float | None
    accuracy_m: int | None = None
    mock_location: bool = False
    wifi: str | None = None
    direction: str | None = None


def phone_check_in(company: Company, agent: Agent, scan: PhoneScan) -> Outcome:
    now = timezone.now()  # RG-01: the phone's clock is never read
    device_hash = fingerprint_hash(scan.device_id)
    base: dict[str, Any] = {
        "server_ts": now,
        "effective_ts": now,
        "mode": Mode.KIOSK_QR,
        "trust": Trust.HIGH,
        "latitude": _dec(scan.latitude),
        "longitude": _dec(scan.longitude),
        "accuracy_m": scan.accuracy_m,
    }
    try:
        if not company.is_active:
            raise Refusal(RefusalCode.COMPANY_SUSPENDED)
        if agent.status != Agent.Status.ACTIVE:
            raise Refusal(RefusalCode.AGENT_INACTIVE)
        site, kiosk, window = _check_scanned_token(scan.token, now, base)
        base["site"], base["kiosk"] = site, kiosk
        # Order of the specification: valid token → not replayed → bound phone → position.
        if kiosk is not None and not _replay_once(kiosk.id, window, device_hash):
            raise Refusal(RefusalCode.TOKEN_REPLAYED)
        device = _check_device(agent, device_hash, base)
        _check_location(site, scan, base, pending=[])
        _check_wifi(company, site, scan)
        base["device"] = device
    except Refusal as refusal:
        _add_location_details(refusal, scan, base)
        return _refuse(refusal, agent=agent, base=base)
    return _finish(
        agent, company=company, moment=now, base=base, requested_direction=scan.direction
    )


def _check_scanned_token(
    raw: str, now: datetime, base: dict[str, Any]
) -> tuple[Site, Kiosk | None, int]:
    try:
        token = tokens.parse(raw)
    except tokens.TokenError as exc:
        raise Refusal(exc.code) from exc
    if token.kind == "PQR1":
        kiosk = (
            Kiosk.objects.select_related("site")
            .filter(id=token.kiosk, site_id=token.subject)
            .first()
        )
        if kiosk is None:
            raise Refusal(RefusalCode.TOKEN_INVALID)
        base["site"], base["kiosk"] = kiosk.site, kiosk
        if not kiosk.is_active:
            raise Refusal(RefusalCode.KIOSK_REVOKED)
        try:
            tokens.verify_signature(token, decrypt(kiosk.secret_key))
            tokens.verify_fresh(token, now)
        except tokens.TokenError as exc:
            raise Refusal(exc.code) from exc
        return kiosk.site, kiosk, token.counter
    if token.kind == "PQRS":
        site = Site.objects.filter(id=token.subject, is_active=True).first()
        if site is None or not site.static_qr_key:
            raise Refusal(RefusalCode.TOKEN_INVALID)
        base["site"], base["mode"], base["trust"] = site, Mode.PRINTED_SITE_QR, Trust.MEDIUM
        try:
            tokens.verify_signature(token, decrypt(site.static_qr_key))
        except tokens.TokenError as exc:
            raise Refusal(exc.code) from exc
        if token.counter != site.static_qr_version:
            raise Refusal(RefusalCode.TOKEN_EXPIRED)
        return site, None, token.counter
    raise Refusal(RefusalCode.TOKEN_INVALID)


def _check_device(agent: Agent, device_hash: str, base: dict[str, Any]) -> Device:
    """A phone checks in for one agent only, and an agent from one phone only (CDC §5, RG-13)."""
    own = Device.objects.filter(agent=agent, is_active=True).first()
    if own is None:
        raise Refusal(RefusalCode.DEVICE_NOT_BOUND)
    if own.fingerprint_hash != device_hash:
        other = Device.objects.filter(fingerprint_hash=device_hash, is_active=True).first()
        if other is not None:
            base["device"] = other
        raise Refusal(RefusalCode.DEVICE_MISMATCH)
    return own


def _check_location(site: Site, scan: PhoneScan, base: dict[str, Any], pending: list[str]) -> None:
    if scan.mock_location:
        raise Refusal(RefusalCode.MOCK_LOCATION)
    if scan.latitude is None or scan.longitude is None:
        raise Refusal(RefusalCode.LOCATION_MISSING)
    distance = haversine_m(
        scan.latitude, scan.longitude, float(site.latitude), float(site.longitude)
    )
    base["distance_m"] = round(distance)
    if distance > site.radius_m:
        raise Refusal(RefusalCode.OUT_OF_ZONE)


def _add_location_details(refusal: Refusal, scan: PhoneScan, base: dict[str, Any]) -> None:
    """R2: a photographed QR scanned from home is reported as expired *and* out of zone."""
    site = base.get("site")
    if refusal.code in (RefusalCode.OUT_OF_ZONE, RefusalCode.LOCATION_MISSING) or site is None:
        return
    if scan.latitude is None or scan.longitude is None:
        return
    distance = haversine_m(
        scan.latitude, scan.longitude, float(site.latitude), float(site.longitude)
    )
    base["distance_m"] = round(distance)
    if distance > site.radius_m and RefusalCode.OUT_OF_ZONE not in refusal.details:
        refusal.details.append(RefusalCode.OUT_OF_ZONE)


def _check_wifi(company: Company, site: Site, scan: PhoneScan) -> None:
    if not company.wifi_check_enabled or not site.allowed_wifi:
        return
    allowed = {w.lower() for w in site.allowed_wifi}
    if not scan.wifi or scan.wifi.lower() not in allowed:
        raise Refusal(RefusalCode.WIFI_NOT_ALLOWED)


def _dec(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(round(value, 6)))


# --- Modes B and C: the kiosk scans the agent's QR or badge ----------------------------------------


@dataclass(frozen=True, slots=True)
class BadgeScan:
    token: str
    client_uuid: UUID | None = None
    scanned_at: datetime | None = None  # kiosk clock, offline only
    offline: bool = False


def kiosk_check_in(company: Company, kiosk: Kiosk, scan: BadgeScan) -> Outcome:
    """Idempotent on (kiosk, client_uuid): an offline batch can be re-sent safely (R5)."""
    if scan.client_uuid is not None:
        existing = CheckIn.objects.filter(kiosk=kiosk, client_uuid=scan.client_uuid).first()
        if existing is not None:
            return Outcome(existing, "Déjà synchronisé")

    now = timezone.now()
    moment = now
    if scan.offline and scan.scanned_at is not None:
        moment = scan.scanned_at  # RG-01 exception: offline kiosk clock, marked as such
    base: dict[str, Any] = {
        "server_ts": now,
        "effective_ts": moment,
        "offline": scan.offline,
        "kiosk": kiosk,
        "site": kiosk.site,
        "client_uuid": scan.client_uuid,
        "mode": Mode.BADGE,
        "trust": Trust.MEDIUM,
    }
    agent: Agent | None = None
    try:
        if not company.is_active:
            raise Refusal(RefusalCode.COMPANY_SUSPENDED)
        if not kiosk.is_active:
            raise Refusal(RefusalCode.KIOSK_REVOKED)
        if scan.offline and (now - moment > OFFLINE_MAX_AGE or moment - now > OFFLINE_MAX_FUTURE):
            raise Refusal(RefusalCode.OFFLINE_TOO_OLD)
        if scan.offline:
            from .workdays import is_closed

            if is_closed(moment.astimezone(tz_of(company)).date()):
                raise Refusal(RefusalCode.PERIOD_CLOSED)
        try:
            token = tokens.parse(scan.token)
        except tokens.TokenError as exc:
            raise Refusal(exc.code) from exc
        if token.kind not in ("PQRB", "PQRP"):
            raise Refusal(RefusalCode.TOKEN_INVALID)
        agent = Agent.objects.filter(id=token.subject).first()
        if agent is None or not agent.badge_key:
            raise Refusal(RefusalCode.TOKEN_INVALID)
        if agent.status != Agent.Status.ACTIVE:
            raise Refusal(RefusalCode.AGENT_INACTIVE)
        badge_key = decrypt(agent.badge_key)
        if token.kind == "PQRB":
            _verify(token, badge_key)
            if token.counter != agent.badge_version:
                raise Refusal(RefusalCode.BADGE_REVOKED)
        else:
            device = Device.objects.filter(agent=agent, is_active=True).first()
            if device is None:
                raise Refusal(RefusalCode.DEVICE_NOT_BOUND)
            _verify(token, tokens.derive_personal_key(badge_key, device.fingerprint_hash))
            try:
                tokens.verify_fresh(token, moment)
            except tokens.TokenError as exc:
                raise Refusal(exc.code) from exc
            base["mode"], base["trust"], base["device"] = Mode.PERSONAL_QR, Trust.HIGH, device
    except Refusal as refusal:
        return _refuse(refusal, agent=agent, base=base)
    return _finish(agent, company=company, moment=moment, base=base, requested_direction=None)


def _verify(token: tokens.ParsedToken, key: bytes) -> None:
    try:
        tokens.verify_signature(token, key)
    except tokens.TokenError as exc:
        raise Refusal(exc.code) from exc
