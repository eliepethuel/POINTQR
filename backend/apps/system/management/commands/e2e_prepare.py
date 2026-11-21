"""Data for the browser end-to-end tests (frontend/e2e): prints one JSON document on stdout.

A dedicated company (code E2ETEST) with one site, one kiosk, an HR account and, on every run,
fresh agents (phones are bound once, so each run needs new ones). Refuses to run unless DEBUG
is on or POINTQR_E2E=1 is set explicitly (CI against the containerised stack).
"""

import json
import os
import time
from datetime import time as clock
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.kiosks.models import Kiosk
from apps.kiosks.services import create_pairing_code
from apps.organization.models import Agent, Site
from apps.organization.services import ensure_badge_key
from apps.schedules.models import Schedule
from apps.system.demo import DEMO_PASSWORD, DEMO_TOTP_SECRET, _company, _site, _user
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Company
from common.crypto import b64url, decrypt, encrypt, new_secret_key

CODE = "E2ETEST"
LATITUDE, LONGITUDE = "5.320000", "-4.020000"


class Command(BaseCommand):
    help = "Prépare les données des tests de bout en bout (développement ou CI uniquement)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--agents", type=int, default=3)

    def handle(self, *args: Any, **options: Any) -> None:
        if not (settings.DEBUG or os.environ.get("POINTQR_E2E") == "1"):
            raise CommandError("Réservé au développement ou à la CI (DEBUG ou POINTQR_E2E=1).")
        with transaction.atomic():
            company = Company.objects.filter(code=CODE).first()
            if company is None:
                company = _company("Recette E2E", "recette-e2e", CODE, "Test", "enterprise", 500)
                company.subscriptions.update(max_kiosks=500)
            with tenant_context(company.id):
                payload = _dataset(company, options["agents"])
        self.stdout.write(json.dumps(payload))


def _dataset(company: Company, count: int) -> dict[str, Any]:
    site = Site.objects.first() or _site(
        "Siège E2E", "Plateau, Abidjan", LATITUDE, LONGITUDE, radius=300
    )
    schedule = Schedule.objects.first() or Schedule.objects.create(
        name="Journée", start_time=clock(7, 30), end_time=clock(16, 30)
    )
    if not User.objects.filter(username="rh").exists():
        _user(company, "rh", [Role.HR], display_name="RH E2E")
    kiosk = Kiosk.objects.filter(site=site, name="Borne de test").first() or Kiosk.objects.create(
        site=site,
        name="Borne de test",
        secret_key=encrypt(new_secret_key()),
        token_hash="0" * 64,
        last_seen_at=timezone.now(),
        app_version="e2e",
    )
    run = str(int(time.time() * 1000))[-9:]
    agents = []
    for i in range(count):
        agent = Agent(
            employee_number=f"E{run}{i}",
            last_name=f"Recette{run[-5:]}",  # unique per run: assertions match on names
            first_names=f"Agent{chr(65 + i)}",
            site=site,
            schedule=schedule,
        )
        ensure_badge_key(agent)
        agent.save()
        username = f"agent{run}{i}"
        _user(company, username, [Role.AGENT], agent=agent, display_name=agent.full_name)
        agents.append({"username": username, "name": agent.full_name})
    code, _ = create_pairing_code(site, f"Tablette {run}", actor=None)
    return {
        "company_code": company.code,
        "password": DEMO_PASSWORD,
        "totp_secret": DEMO_TOTP_SECRET,
        "hr": "rh",
        "agents": agents,
        "pairing_code": code,
        "site": {
            "id": str(site.id),
            "latitude": float(site.latitude),
            "longitude": float(site.longitude),
        },
        "kiosk": {"id": str(kiosk.id), "key": b64url(decrypt(kiosk.secret_key))},
    }
