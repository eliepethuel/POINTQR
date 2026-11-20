"""Companies (tenants) and subscriptions — the only tables without row level security."""

import uuid

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models


class Company(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspendue"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_name = models.CharField("raison sociale", max_length=200)
    slug = models.SlugField(
        "sous-domaine",
        max_length=63,
        unique=True,
        help_text="ministere-x → ministere-x.pointqr.ci",
    )
    code = models.CharField(
        "code entreprise",
        max_length=12,
        unique=True,
        validators=[RegexValidator(r"^[A-Z0-9]{4,12}$", "4 à 12 lettres majuscules ou chiffres.")],
        help_text="Saisi dans l'application mobile et sur la borne.",
    )
    sector = models.CharField("secteur", max_length=120, blank=True)
    country = models.CharField("pays", max_length=2, default="CI")
    timezone = models.CharField("fuseau horaire", max_length=64, default="Africa/Abidjan")
    contact_name = models.CharField("contact", max_length=120, blank=True)
    contact_email = models.EmailField("e-mail du contact", blank=True)
    contact_phone = models.CharField("téléphone du contact", max_length=32, blank=True)
    logo = models.FileField("logo", upload_to="logos/", blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    # Settings (all values are defaults the company can change)
    primary_color = models.CharField(max_length=7, default="#7C5CFF")
    highlight_color = models.CharField(max_length=7, default="#D4FF3A")
    default_radius_m = models.PositiveIntegerField(
        "rayon de géorepérage par défaut (m)",
        default=150,
        validators=[MinValueValidator(20), MaxValueValidator(5000)],
    )
    approval_levels = models.PositiveSmallIntegerField(
        "niveaux de validation",
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(2)],
        help_text="1 = manager seul, 2 = manager puis RH (EF-31).",
    )
    wifi_check_enabled = models.BooleanField("contrôle Wi-Fi", default=False)
    break_checkins_enabled = models.BooleanField("pointage des pauses", default=False)
    retention_checkins_years = models.PositiveSmallIntegerField(default=5)
    retention_gps_months = models.PositiveSmallIntegerField(default=12)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "entreprise"
        ordering = ["legal_name"]

    def __str__(self) -> str:
        return self.legal_name

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE


class Subscription(models.Model):
    class Plan(models.TextChoices):
        STARTER = "starter", "Essentiel"
        BUSINESS = "business", "Entreprise"
        ENTERPRISE = "enterprise", "Grand compte"

    class Status(models.TextChoices):
        ACTIVE = "active", "Actif"
        EXPIRED = "expired", "Expiré"
        CANCELLED = "cancelled", "Résilié"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.CharField(max_length=16, choices=Plan.choices, default=Plan.STARTER)
    max_agents = models.PositiveIntegerField(default=50)
    max_sites = models.PositiveIntegerField(default=1)
    max_kiosks = models.PositiveIntegerField(default=1)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "abonnement"
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="subscription_dates_ordered",
            )
        ]

    def __str__(self) -> str:
        return f"{self.company} — {self.get_plan_display()}"
