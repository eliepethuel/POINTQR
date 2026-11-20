"""30 days of realistic check-ins for the demo (lateness, absences, missing exits, fraud attempts)."""

import random
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.kiosks.models import Kiosk
from apps.organization.models import Agent, Device
from apps.organization.services import fingerprint_hash
from apps.schedules.selectors import day_schedule, is_holiday
from common.crypto import encrypt, new_secret_key

from . import workdays
from .models import CheckIn, Mode, RefusalCode, Result, Trust

DAYS = 30


def _kiosks(demo: Any) -> dict[Any, Kiosk]:
    kiosks = {}
    for site in demo.sites:
        kiosks[site.id] = Kiosk.objects.create(
            site=site,
            name=f"Entrée {site.name}",
            secret_key=encrypt(new_secret_key()),
            token_hash="0" * 64,
            last_seen_at=timezone.now(),
            app_version="web-1.0",
        )
    return kiosks


def _devices(agents: list[Agent], rng: random.Random) -> dict[Any, Device]:
    devices = {}
    for agent in agents:
        if rng.random() < 0.8:  # the others use a badge (no smartphone)
            devices[agent.id] = Device.objects.create(
                agent=agent,
                fingerprint_hash=fingerprint_hash(f"demo-{agent.id}"),
                model=rng.choice(["Tecno Spark 10", "Itel A70", "Samsung A14", "Infinix Hot 30"]),
                os=rng.choice(["Android 12", "Android 13", "Android 11"]),
            )
    return devices


def _row(
    company_id: Any,
    agent: Agent,
    at: datetime,
    direction: str,
    kiosk: Kiosk,
    device: Device | None,
    rng: random.Random,
    **extra: Any,
) -> CheckIn:
    mode = Mode.KIOSK_QR if device else Mode.BADGE
    if device and rng.random() < 0.1:
        mode = Mode.PERSONAL_QR
    return CheckIn(
        company_id=company_id,
        agent=agent,
        site=kiosk.site,
        kiosk=kiosk,
        device=device if mode != Mode.BADGE else None,
        direction=direction,
        mode=mode,
        trust=Trust.MEDIUM if mode == Mode.BADGE else Trust.HIGH,
        server_ts=at,
        effective_ts=at,
        latitude=kiosk.site.latitude,
        longitude=kiosk.site.longitude,
        distance_m=rng.randint(3, 60) if device else None,
        accuracy_m=rng.randint(5, 30),
        result=extra.pop("result", Result.ACCEPTED),
        **extra,
    )


def add_history(demo: Any, rng: random.Random) -> None:
    company = demo.company
    tz = ZoneInfo(company.timezone)
    kiosks = _kiosks(demo)
    devices = _devices(demo.agents, rng)
    now = timezone.now().astimezone(tz)
    start = now.date() - timedelta(days=DAYS)
    rows: list[CheckIn] = []
    day = start
    while day <= now.date():
        holiday = is_holiday(day, company.country)
        for agent in demo.agents:
            planned = day_schedule(agent, day, tz)
            if (
                holiday
                or planned is None
                or not planned.works
                or planned.start is None
                or planned.end is None
            ):
                continue
            if rng.random() > 0.93:  # absent
                continue
            kiosk = kiosks[agent.site_id]
            device = devices.get(agent.id)
            offset = rng.gauss(-8, 9)
            if rng.random() < 0.12:
                offset = rng.uniform(15, 45)  # late
            arrival = planned.start + timedelta(minutes=max(-40, min(75, offset)))
            if arrival > now:
                continue
            rows.append(_row(company.id, agent, arrival, "in", kiosk, device, rng))
            if rng.random() < 0.03:
                continue  # forgot to check out (RG-05)
            departure = planned.end + timedelta(minutes=rng.gauss(6, 12))
            if rng.random() < 0.05:
                departure = planned.end - timedelta(minutes=rng.uniform(25, 90))  # early leave
            if departure <= now:
                rows.append(_row(company.id, agent, departure, "out", kiosk, device, rng))
        # A few fraud attempts every day, refused and visible to HR (EF-21).
        for _ in range(rng.randint(1, 3)):
            agent = rng.choice(demo.agents)
            kiosk = kiosks[agent.site_id]
            at = datetime.combine(day, datetime.min.time(), tzinfo=tz) + timedelta(
                hours=7, minutes=rng.randint(20, 70)
            )
            if at > now:
                continue
            code, details, distance = rng.choice(
                [
                    (
                        RefusalCode.TOKEN_EXPIRED,
                        [RefusalCode.TOKEN_EXPIRED, RefusalCode.OUT_OF_ZONE],
                        5300,
                    ),
                    (RefusalCode.OUT_OF_ZONE, [RefusalCode.OUT_OF_ZONE], rng.randint(400, 3000)),
                    (RefusalCode.DEVICE_MISMATCH, [RefusalCode.DEVICE_MISMATCH], 20),
                ]
            )
            rows.append(
                _row(
                    company.id,
                    agent,
                    at,
                    "",
                    kiosk,
                    devices.get(agent.id),
                    rng,
                    result=Result.REFUSED,
                    refusal_code=code,
                    refusal_details=details,
                )
            )
            rows[-1].distance_m = distance
        day += timedelta(days=1)
    CheckIn.objects.bulk_create(rows, batch_size=2000)
    workdays.recompute_range(start, now.date(), agents=demo.agents)


__all__ = ["DAYS", "add_history", "date"]
