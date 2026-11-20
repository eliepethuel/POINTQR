"""Sites, organisation chart, agents and their bound phones (EF-05 to EF-10)."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from common.models import TenantModel


class Site(TenantModel):
    name = models.CharField("nom", max_length=120)
    address = models.CharField("adresse", max_length=255, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    radius_m = models.PositiveIntegerField(
        "rayon de géorepérage (m)",
        default=150,
        validators=[MinValueValidator(20), MaxValueValidator(5000)],
    )
    allowed_wifi = models.JSONField(
        "Wi-Fi autorisés",
        default=list,
        blank=True,
        help_text="Liste de SSID ou BSSID acceptés comme second facteur.",
    )
    # Mode D (printed QR without kiosk): static token signed with this key (ADR-0005).
    static_qr_key = models.TextField(editable=False, blank=True)
    static_qr_version = models.PositiveIntegerField(default=1, editable=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "site"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["company", "name"], name="site_unique_name")]

    def __str__(self) -> str:
        return self.name


class OrgUnit(TenantModel):
    class Kind(models.TextChoices):
        DIRECTION = "direction", "Direction"
        SERVICE = "service", "Service"
        TEAM = "team", "Équipe"

    name = models.CharField("nom", max_length=120)
    kind = models.CharField("type", max_length=16, choices=Kind.choices, default=Kind.SERVICE)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    manager = models.ForeignKey(
        "Agent", on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_units"
    )

    class Meta:
        verbose_name = "unité"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Agent(TenantModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Actif"
        INACTIVE = "inactive", "Inactif"

    employee_number = models.CharField("matricule", max_length=32)
    last_name = models.CharField("nom", max_length=100)
    first_names = models.CharField("prénoms", max_length=150)
    job_title = models.CharField("fonction", max_length=120, blank=True)
    phone = models.CharField("téléphone", max_length=32, blank=True)
    email = models.EmailField("e-mail", blank=True)
    site = models.ForeignKey(
        Site, on_delete=models.PROTECT, null=True, blank=True, related_name="agents"
    )
    org_unit = models.ForeignKey(
        OrgUnit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="agents",
        verbose_name="unité",
    )
    schedule = models.ForeignKey(
        "schedules.Schedule",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="agents",
        verbose_name="horaire",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    # Personal QR (modes B and C): HMAC key, rotated when a badge is reprinted (ADR-0005).
    badge_key = models.TextField(editable=False, blank=True)
    badge_version = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        verbose_name = "agent"
        ordering = ["last_name", "first_names"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee_number"], name="agent_unique_employee_number"
            ),
        ]
        indexes = [
            models.Index(fields=["company", "org_unit"]),
            models.Index(fields=["company", "site"]),
        ]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_names} {self.last_name}".strip()


class Device(TenantModel):
    """The single phone allowed to check in for an agent (RG-13)."""

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="devices")
    fingerprint_hash = models.CharField(max_length=64, db_index=True)
    model = models.CharField("modèle", max_length=120, blank=True)
    os = models.CharField("système", max_length=60, blank=True)
    bound_at = models.DateTimeField("lié le", auto_now_add=True)
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "appareil"
        ordering = ["-bound_at"]
        constraints = [
            # One active phone per agent, and one agent per phone within a company.
            models.UniqueConstraint(
                fields=["agent"], condition=Q(is_active=True), name="device_one_active_per_agent"
            ),
            models.UniqueConstraint(
                fields=["company", "fingerprint_hash"],
                condition=Q(is_active=True),
                name="device_one_agent_per_phone",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.model or 'Téléphone'} — {self.agent}"


class DeviceChangeRequest(TenantModel):
    """A phone change must be approved by HR (EF-10)."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Validée"
        REJECTED = "rejected", "Refusée"

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="device_requests")
    fingerprint_hash = models.CharField(max_length=64)
    model = models.CharField(max_length=120, blank=True)
    os = models.CharField(max_length=60, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "demande de changement de téléphone"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["agent"], condition=Q(status="pending"), name="device_request_one_pending"
            ),
        ]
