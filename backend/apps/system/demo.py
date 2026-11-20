"""Demonstration data (``python manage.py seed_demo``): 2 companies, 3 sites, 150 agents, accounts.

Demo credentials are documented in the README. They are for local demonstrations only.
"""

import base64
import random
from dataclasses import dataclass, field
from datetime import time
from decimal import Decimal
from typing import Any

from django.db import transaction
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts.models import Role, User
from apps.organization.models import Agent, OrgUnit, Site
from apps.organization.services import ensure_badge_key, ensure_site_key
from apps.schedules.models import Schedule
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Company, Subscription

DEMO_PASSWORD = "Demo-PointQR-2026"
#: Shared TOTP secret of the privileged demo accounts (add it once to an authenticator app).
DEMO_TOTP_SECRET = "PQRDEMOPQRDEMOPQRDEMOPQRDEMOPQRD"

LAST_NAMES = [
    "KOUASSI",
    "KONÉ",
    "TRAORÉ",
    "OUATTARA",
    "YAO",
    "N'GUESSAN",
    "BAMBA",
    "COULIBALY",
    "DIABATÉ",
    "KOFFI",
    "AKA",
    "TOURÉ",
    "DIALLO",
    "SANGARÉ",
    "GBAGBO",
    "AHOUA",
    "BROU",
    "KACOU",
    "SORO",
    "DOSSO",
    "FOFANA",
    "N'DRI",
    "ASSI",
    "GNAGNE",
    "TANOH",
    "ZADI",
    "LOBA",
    "SERI",
    "TAPÉ",
    "BEUGRÉ",
]
FIRST_NAMES = [
    "Aya",
    "Kofi",
    "Awa",
    "Issa",
    "Mariam",
    "Yao",
    "Adjoua",
    "Moussa",
    "Fatou",
    "Koffi",
    "Aïcha",
    "Ibrahim",
    "Affoué",
    "Seydou",
    "Amenan",
    "Drissa",
    "Akissi",
    "Lassina",
    "Ange",
    "Grâce",
    "Christelle",
    "Hervé",
    "Serge",
    "Nadège",
    "Didier",
    "Salimata",
    "Bakary",
    "Esther",
    "Jean-Marc",
]
JOBS = [
    "Secrétaire",
    "Agent administratif",
    "Comptable",
    "Chargé d'études",
    "Assistant RH",
    "Technicien",
    "Chauffeur",
    "Agent d'accueil",
    "Juriste",
    "Informaticien",
    "Archiviste",
]


@dataclass(slots=True)
class DemoCompany:
    company: Company
    sites: list[Site] = field(default_factory=list)
    units: dict[str, OrgUnit] = field(default_factory=dict)
    agents: list[Agent] = field(default_factory=list)
    schedules: dict[str, Schedule] = field(default_factory=dict)


def _totp_key() -> str:
    return base64.b32decode(DEMO_TOTP_SECRET).hex()


def _user(
    company: Company | None,
    username: str,
    roles: list[str],
    *,
    agent: Agent | None = None,
    display_name: str = "",
) -> User:
    if company is None:
        user = User.objects.create_superadmin(username, DEMO_PASSWORD, display_name=display_name)
    else:
        user = User.objects.create_user(
            username,
            DEMO_PASSWORD,
            company=company,
            roles=roles,
            agent=agent,
            display_name=display_name or username,
        )
    if user.mfa_required:
        TOTPDevice.objects.create(user=user, name="Démo", key=_totp_key(), confirmed=True)
    return user


def _company(legal_name: str, slug: str, code: str, sector: str, plan: str, agents: int) -> Company:
    from datetime import date, timedelta

    company = Company.objects.create(
        legal_name=legal_name,
        slug=slug,
        code=code,
        sector=sector,
        contact_name="Direction",
        contact_email=f"contact@{slug}.ci",
    )
    Subscription.objects.create(
        company=company,
        plan=plan,
        max_agents=agents,
        max_sites=5,
        max_kiosks=5,
        start_date=date.today() - timedelta(days=60),
        end_date=date.today() + timedelta(days=305),
    )
    return company


def _site(name: str, address: str, lat: str, lng: str, radius: int = 150) -> Site:
    site = Site(
        name=name, address=address, latitude=Decimal(lat), longitude=Decimal(lng), radius_m=radius
    )
    ensure_site_key(site)
    site.save()
    return site


def _agents(demo: DemoCompany, count: int, prefix: str, rng: random.Random) -> None:
    units = list(demo.units.values())
    default_schedule = next(iter(demo.schedules.values()))
    for i in range(count):
        agent = Agent(
            employee_number=f"{prefix}{i + 1:04d}",
            last_name=rng.choice(LAST_NAMES),
            first_names=rng.choice(FIRST_NAMES),
            job_title=rng.choice(JOBS),
            phone=f"+225 07 {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)}",
            site=demo.sites[i % len(demo.sites)],
            org_unit=units[i % len(units)],
            schedule=demo.schedules.get("nuit")
            if units[i % len(units)].name == "Sécurité"
            else default_schedule,
        )
        agent.email = (
            f"{agent.first_names.split('-')[0].lower()}.{prefix.lower()}{i + 1}@example.ci"
        )
        ensure_badge_key(agent)
        agent.save()
        demo.agents.append(agent)


def _ministere(rng: random.Random) -> DemoCompany:
    company = _company(
        "Ministère X – Site Plateau",
        "ministere-x",
        "MINX",
        "Administration publique",
        "enterprise",
        500,
    )
    demo = DemoCompany(company)
    with tenant_context(company.id):
        demo.sites = [
            _site(
                "Plateau – Siège",
                "Avenue Franchet d'Espérey, Plateau, Abidjan",
                "5.319700",
                "-4.016400",
            ),
            _site(
                "Plateau – Annexe",
                "Rue du Commerce, Plateau, Abidjan",
                "5.324000",
                "-4.019700",
                200,
            ),
        ]
        demo.schedules = {
            "admin": Schedule.objects.create(
                name="Administratif",
                start_time=time(7, 30),
                end_time=time(16, 30),
                break_minutes=60,
            ),
            "nuit": Schedule.objects.create(
                name="Garde de nuit",
                start_time=time(20, 0),
                end_time=time(6, 0),
                break_minutes=30,
                weekdays=[0, 1, 2, 3, 4, 5, 6],
            ),
        }
        dg = OrgUnit.objects.create(name="Direction générale", kind="direction")
        for name in (
            "Direction des ressources humaines",
            "Direction financière",
            "Service informatique",
            "Service courrier",
            "Sécurité",
        ):
            demo.units[name] = OrgUnit.objects.create(name=name, kind="service", parent=dg)
        _agents(demo, 110, "MX", rng)
        manager_agent = next(
            a for a in demo.agents if a.org_unit and a.org_unit.name == "Service informatique"
        )
        unit = demo.units["Service informatique"]
        unit.manager = manager_agent
        unit.save(update_fields=["manager"])
        agent_user = next(
            a for a in demo.agents if a.org_unit_id == unit.id and a.id != manager_agent.id
        )
        _user(company, "admin", [Role.COMPANY_ADMIN], display_name="Administrateur MINX")
        _user(company, "rh", [Role.HR], display_name="Service du personnel")
        _user(
            company,
            "manager",
            [Role.MANAGER, Role.AGENT],
            agent=manager_agent,
            display_name=manager_agent.full_name,
        )
        _user(company, "agent", [Role.AGENT], agent=agent_user, display_name=agent_user.full_name)
        _user(company, "auditeur", [Role.AUDITOR], display_name="Inspection générale")
    return demo


def _pme(rng: random.Random) -> DemoCompany:
    company = _company("PME Y – Cocody", "pme-y", "PMEY", "Services", "business", 60)
    demo = DemoCompany(company)
    with tenant_context(company.id):
        demo.sites = [
            _site("Cocody – Bureau", "Boulevard Latrille, Cocody, Abidjan", "5.360000", "-3.990000")
        ]
        demo.schedules = {
            "bureau": Schedule.objects.create(
                name="Bureau", start_time=time(8, 0), end_time=time(17, 0)
            )
        }
        direction = OrgUnit.objects.create(name="Direction", kind="direction")
        for name in ("Commercial", "Technique"):
            demo.units[name] = OrgUnit.objects.create(name=name, kind="service", parent=direction)
        _agents(demo, 40, "PY", rng)
        _user(company, "admin", [Role.COMPANY_ADMIN], display_name="Gérant PME Y")
        _user(
            company,
            "agent",
            [Role.AGENT],
            agent=demo.agents[0],
            display_name=demo.agents[0].full_name,
        )
    return demo


def seed(*, extra: Any = None) -> list[DemoCompany]:
    """Create the demo dataset. ``extra(demo, rng)`` lets later modules add kiosks and check-ins."""
    rng = random.Random(2026)  # deterministic demo
    with transaction.atomic():
        with tenant_context(None, platform=True):
            _user(None, "editeur", [], display_name="Équipe PointQR")
        demos = [_ministere(rng), _pme(rng)]
        if extra is not None:
            for demo in demos:
                with tenant_context(demo.company.id):
                    extra(demo, rng)
    return demos
