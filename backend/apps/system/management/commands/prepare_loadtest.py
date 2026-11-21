"""Dataset for the R10 load test (``infra/locust``): one company, one kiosk, N phone agents.

Development only: it writes the kiosk key and agent access tokens to a local JSON file.
"""

import json
from datetime import time, timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role, User
from apps.kiosks.models import Kiosk
from apps.organization.models import Agent, Device, Site
from apps.organization.services import ensure_badge_key, fingerprint_hash
from apps.schedules.models import Schedule
from apps.system.demo import _company, _site
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Company
from common.crypto import b64url, decrypt, encrypt, new_secret_key

CODE = "LOAD"
DEFAULT_OUT = Path(settings.BASE_DIR).parent / "infra" / "locust" / ".loadtest.json"


class Command(BaseCommand):
    help = "Prépare les données du test de charge R10 (développement uniquement)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--agents", type=int, default=300)
        parser.add_argument("--hours", type=int, default=2, help="Durée de vie des jetons.")
        parser.add_argument("--out", type=Path, default=DEFAULT_OUT)

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG:
            raise CommandError("Commande réservée au développement (DEBUG=True).")
        count: int = options["agents"]
        with transaction.atomic():
            company = Company.objects.filter(code=CODE).first()
            if company is None:
                company = _company(
                    "Test de charge", "test-charge", CODE, "Test", "enterprise", 5000
                )
            with tenant_context(company.id):
                payload = _dataset(company, count, timedelta(hours=options["hours"]))
        out: Path = options["out"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"{count} agents prêts : {out}"))


def _dataset(company: Company, count: int, lifetime: timedelta) -> dict[str, Any]:
    site = Site.objects.first()
    if site is None:
        site = _site("Plateau – Charge", "Plateau, Abidjan", "5.320000", "-4.020000", radius=300)
    schedule = Schedule.objects.first() or Schedule.objects.create(
        name="Journée", start_time=time(7, 30), end_time=time(16, 30)
    )
    kiosk = Kiosk.objects.filter(site=site).first() or Kiosk.objects.create(
        site=site,
        name="Borne charge",
        secret_key=encrypt(new_secret_key()),
        token_hash="0" * 64,
        last_seen_at=timezone.now(),
        app_version="locust",
    )
    agents = []
    for i in range(count):
        number = f"LT{i + 1:05d}"
        agent = Agent.objects.filter(employee_number=number).first()
        if agent is None:
            agent = Agent(
                employee_number=number,
                last_name="Charge",
                first_names=f"Agent {i + 1}",
                site=site,
                schedule=schedule,
            )
            ensure_badge_key(agent)
            agent.save()
        device_id = f"locust-device-{number}"
        if not Device.objects.filter(agent=agent, is_active=True).exists():
            Device.objects.create(agent=agent, fingerprint_hash=fingerprint_hash(device_id))
        user = User.objects.filter(agent=agent).first() or User.objects.create_user(
            number.lower(), None, company=company, roles=[Role.AGENT], agent=agent
        )
        agents.append({"device_id": device_id, "access": _access(user, lifetime)})
    return {
        "company_code": company.code,
        "site_id": str(site.id),
        "kiosk_id": str(kiosk.id),
        "kiosk_key": b64url(decrypt(kiosk.secret_key)),
        "latitude": float(site.latitude),
        "longitude": float(site.longitude),
        "agents": agents,
    }


def _access(user: User, lifetime: timedelta) -> str:
    refresh = RefreshToken.for_user(user)
    refresh["company_id"] = str(user.company_id)
    refresh["platform"] = False
    refresh["roles"] = list(user.roles)
    refresh["mfa"] = False
    access = refresh.access_token
    access.set_exp(lifetime=lifetime)
    return str(access)
