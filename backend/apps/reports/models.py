"""Report jobs generated in the background (EF-34 to EF-38)."""

from django.db import models

from common.models import TenantModel


class ReportJob(TenantModel):
    class Kind(models.TextChoices):
        PUNCTUALITY = "punctuality", "Ponctualité (Excel)"
        MONTHLY_SHEET = "monthly_sheet", "Feuille de présence mensuelle (PDF)"
        PAYROLL = "payroll", "Éléments variables de paie (Excel)"
        CHECKINS = "checkins", "Pointages (CSV)"
        BADGES = "badges", "Planche de badges QR (PDF)"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        RUNNING = "running", "En cours"
        DONE = "done", "Terminé"
        FAILED = "failed", "Échec"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    start = models.DateField(null=True, blank=True)
    end = models.DateField(null=True, blank=True)
    org_unit = models.ForeignKey(
        "organization.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    agent = models.ForeignKey(
        "organization.Agent", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    progress = models.PositiveSmallIntegerField(default=0)
    file = models.FileField(upload_to="rapports/%Y/%m/", blank=True)
    filename = models.CharField(max_length=200, blank=True)
    error = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "rapport"
        ordering = ["-created_at"]


class ReportSchedule(TenantModel):
    """Reports e-mailed automatically, every Monday or every month end (EF-38)."""

    class Frequency(models.TextChoices):
        WEEKLY = "weekly", "Chaque lundi (semaine écoulée)"
        MONTHLY = "monthly", "Chaque fin de mois"

    kind = models.CharField(max_length=20, choices=ReportJob.Kind.choices)
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    recipients = models.JSONField(default=list, help_text="Adresses e-mail")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "rapport programmé"
        ordering = ["kind"]
