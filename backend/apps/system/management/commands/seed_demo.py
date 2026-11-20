from typing import Any

from django.core.management.base import BaseCommand

from apps.system import demo
from apps.tenancy.models import Company


class Command(BaseCommand):
    help = "Charge les données de démonstration (2 entreprises, 150 agents, comptes par rôle)."

    def handle(self, *args: Any, **options: Any) -> None:
        if Company.objects.filter(code__in=["MINX", "PMEY"]).exists():
            self.stdout.write(
                self.style.WARNING(
                    "Les données de démonstration existent déjà (tasks.ps1 db-reset pour repartir à zéro)."
                )
            )
            return
        demos = demo.seed(extra=demo_extra())
        for d in demos:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{d.company.legal_name} : {len(d.sites)} sites, {len(d.agents)} agents"
                )
            )
        self.stdout.write(f"Mot de passe de tous les comptes : {demo.DEMO_PASSWORD}")
        self.stdout.write(f"Secret TOTP des comptes admin / RH / éditeur : {demo.DEMO_TOTP_SECRET}")


def demo_extra() -> Any:
    """Hook filled by later modules (kiosks, check-in history)."""
    try:
        from apps.attendance.demo import add_history
    except ImportError:
        return None
    return add_history
