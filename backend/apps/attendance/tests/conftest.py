"""A realistic Plateau site: kiosk, agent with bound phone, 07:30 schedule with 10 min tolerance."""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tokens import issue_tokens
from apps.attendance import tokens
from apps.kiosks import services as kiosk_services
from apps.organization.services import bind_device
from apps.tenancy.context import tenant_context
from common.crypto import b64url_decode
from tests import factories

ABIDJAN = ZoneInfo("Africa/Abidjan")
SITE_LAT, SITE_LNG = 5.3197, -4.0164
HOME_LAT, HOME_LNG = 5.3600, -3.9900  # Cocody, ~5 km away


@dataclass
class Scene:
    company: Any
    site: Any
    kiosk: Any
    kiosk_key: bytes
    kiosk_token: str
    agent: Any
    agent_user: Any
    other_agent: Any
    other_user: Any
    kiosk_client: APIClient

    # Clients are built on access so JWTs are issued at the (travelled) current time.
    @property
    def agent_client(self) -> APIClient:
        return APIClient(
            HTTP_AUTHORIZATION=f"Bearer {issue_tokens(self.agent_user, mfa=False).access}"
        )

    @property
    def other_client(self) -> APIClient:
        return APIClient(
            HTTP_AUTHORIZATION=f"Bearer {issue_tokens(self.other_user, mfa=False).access}"
        )

    def qr(self, at: datetime) -> str:
        return tokens.kiosk_token(self.kiosk_key, self.site.id, self.kiosk.id, tokens.window_of(at))

    def scan(
        self,
        at: datetime,
        *,
        device: str = "phone-aya",
        lat: float = SITE_LAT,
        lng: float = SITE_LNG,
        client: APIClient | None = None,
        **extra: Any,
    ) -> Any:
        body = {
            "token": self.qr(at),
            "device_id": device,
            "latitude": lat,
            "longitude": lng,
            "accuracy_m": 12,
            **extra,
        }
        return (client or self.agent_client).post("/api/v1/mobile/checkins/", body, format="json")


def at(hour: int, minute: int, second: int = 0, day: int = 16) -> datetime:
    """Monday 16 November 2026, Abidjan time."""
    return datetime(2026, 11, day, hour, minute, second, tzinfo=ABIDJAN)


@pytest.fixture
def scene(company_x) -> Scene:
    site = factories.SiteFactory(
        company=company_x, name="Plateau", latitude=SITE_LAT, longitude=SITE_LNG, radius_m=150
    )
    schedule = factories.ScheduleFactory(
        company=company_x, start_time=time(7, 30), end_time=time(16, 30), late_tolerance_min=10
    )
    agent = factories.AgentFactory(
        company=company_x, site=site, schedule=schedule, first_names="Aya", last_name="KOUASSI"
    )
    other = factories.AgentFactory(
        company=company_x, site=site, schedule=schedule, first_names="Kofi", last_name="YAO"
    )
    with tenant_context(company_x.id):
        bind_device(agent, "phone-aya", model="Tecno Spark")
        bind_device(other, "phone-kofi", model="Itel A70")
        code, _ = kiosk_services.create_pairing_code(site, "Entrée principale", actor=None)
        paired = kiosk_services.pair(code)
    agent_user = factories.make_user(company_x, Role.AGENT, agent=agent)
    other_user = factories.make_user(company_x, Role.AGENT, agent=other)
    kiosk_client = APIClient(HTTP_AUTHORIZATION=f"Kiosk {paired.token}", HTTP_X_COMPANY_CODE="MINX")
    return Scene(
        company_x,
        site,
        paired.kiosk,
        b64url_decode(paired.secret),
        paired.token,
        agent,
        agent_user,
        other,
        other_user,
        kiosk_client,
    )
