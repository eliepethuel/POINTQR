"""Check-ins: the raw, append-only proof of presence (RG-12). Never updated, never deleted."""

from django.db import models
from django.db.models import Q

from common.models import TenantAppendOnlyModel, TenantModel


class Direction(models.TextChoices):
    IN = "in", "Entrée"
    OUT = "out", "Sortie"
    BREAK_OUT = "break_out", "Début de pause"
    BREAK_IN = "break_in", "Fin de pause"


class Mode(models.TextChoices):
    KIOSK_QR = "A", "Borne + téléphone"
    PERSONAL_QR = "B", "QR personnel scanné par la borne"
    BADGE = "C", "Badge imprimé"
    PRINTED_SITE_QR = "D", "QR du site sans borne"


class Trust(models.TextChoices):
    HIGH = "high", "Élevé"
    MEDIUM = "medium", "Moyen"


class Result(models.TextChoices):
    ACCEPTED = "accepted", "Accepté"
    REFUSED = "refused", "Refusé"
    IGNORED = "ignored", "Ignoré (doublon)"


class RefusalCode(models.TextChoices):
    COMPANY_SUSPENDED = "COMPANY_SUSPENDED", "Entreprise suspendue"
    TOKEN_INVALID = "TOKEN_INVALID", "QR invalide"
    TOKEN_EXPIRED = "TOKEN_EXPIRED", "QR expiré"
    TOKEN_REPLAYED = "TOKEN_REPLAYED", "QR déjà utilisé"
    KIOSK_REVOKED = "KIOSK_REVOKED", "Borne révoquée"
    BADGE_REVOKED = "BADGE_REVOKED", "Badge remplacé"
    AGENT_INACTIVE = "AGENT_INACTIVE", "Agent inactif"
    DEVICE_NOT_BOUND = "DEVICE_NOT_BOUND", "Téléphone non activé"
    DEVICE_MISMATCH = "DEVICE_MISMATCH", "Appareil non autorisé"
    LOCATION_MISSING = "LOCATION_MISSING", "Position absente"
    MOCK_LOCATION = "MOCK_LOCATION", "Position simulée"
    OUT_OF_ZONE = "OUT_OF_ZONE", "Hors zone"
    WIFI_NOT_ALLOWED = "WIFI_NOT_ALLOWED", "Wi-Fi non autorisé"
    OFFLINE_TOO_OLD = "OFFLINE_TOO_OLD", "Pointage hors-ligne trop ancien"
    DUPLICATE = "DUPLICATE", "Doublon (moins de 2 minutes)"
    PERIOD_CLOSED = "PERIOD_CLOSED", "Période clôturée"


class CheckIn(TenantAppendOnlyModel):
    agent = models.ForeignKey(
        "organization.Agent", on_delete=models.PROTECT, null=True, related_name="checkins"
    )
    site = models.ForeignKey(
        "organization.Site", on_delete=models.PROTECT, null=True, related_name="checkins"
    )
    kiosk = models.ForeignKey(
        "kiosks.Kiosk", on_delete=models.PROTECT, null=True, blank=True, related_name="checkins"
    )
    device = models.ForeignKey(
        "organization.Device",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="checkins",
    )
    direction = models.CharField(max_length=16, choices=Direction.choices, blank=True)
    mode = models.CharField(max_length=1, choices=Mode.choices)
    trust = models.CharField(max_length=8, choices=Trust.choices)
    #: Server reception time — the only time that counts (RG-01).
    server_ts = models.DateTimeField("heure serveur", db_index=True)
    #: Time used by the rules: server_ts, or the kiosk's synchronised clock when offline.
    effective_ts = models.DateTimeField("heure retenue", db_index=True)
    offline = models.BooleanField("hors-ligne", default=False)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy_m = models.PositiveIntegerField(null=True, blank=True)
    distance_m = models.PositiveIntegerField("distance au site (m)", null=True, blank=True)
    result = models.CharField(max_length=16, choices=Result.choices)
    refusal_code = models.CharField(max_length=32, choices=RefusalCode.choices, blank=True)
    #: Every failed control (R2: an old QR scanned from home is both expired and out of zone).
    refusal_details = models.JSONField(default=list, blank=True)
    client_uuid = models.UUIDField(null=True, blank=True)
    #: Correction lines point to the check-in they correct (RG-12, EF-32).
    corrects = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="corrections"
    )
    is_correction = models.BooleanField(default=False)
    reason = models.TextField("motif", blank=True)
    author = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = "pointage"
        ordering = ["-effective_ts"]
        indexes = [
            models.Index(fields=["company", "agent", "-effective_ts"]),
            models.Index(fields=["company", "result", "-effective_ts"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["kiosk", "client_uuid"],
                condition=Q(client_uuid__isnull=False),
                name="checkin_unique_client_uuid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.agent} {self.get_direction_display()} {self.effective_ts:%Y-%m-%d %H:%M}"


class WorkDay(TenantModel):
    """Computed view of one agent's day, recomputable at any time from the check-ins (CDC §10)."""

    class Status(models.TextChoices):
        PENDING = "pending", "En cours"
        PRESENT = "present", "Présent"
        LATE = "late", "En retard"
        LATE_JUSTIFIED = "late_justified", "Retard justifié"
        ABSENT = "absent", "Absent"
        ABSENT_JUSTIFIED = "absent_justified", "Absence justifiée"
        INCOMPLETE = "incomplete", "Incomplète"
        HOLIDAY = "holiday", "Jour férié"
        OFF = "off", "Non travaillé"

    agent = models.ForeignKey(
        "organization.Agent", on_delete=models.CASCADE, related_name="workdays"
    )
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    first_in = models.DateTimeField(null=True, blank=True)
    last_out = models.DateTimeField(null=True, blank=True)
    planned_start = models.DateTimeField(null=True, blank=True)
    planned_end = models.DateTimeField(null=True, blank=True)
    late_minutes = models.PositiveIntegerField(default=0)
    early_leave_minutes = models.PositiveIntegerField(default=0)
    worked_minutes = models.PositiveIntegerField(default=0)
    overtime_minutes = models.PositiveIntegerField(default=0)
    overtime_validated = models.BooleanField(default=False)
    incomplete = models.BooleanField(default=False)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "journée"
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["agent", "date"], name="workday_unique_agent_date")
        ]
        indexes = [models.Index(fields=["company", "date", "status"])]

    def __str__(self) -> str:
        return f"{self.agent} {self.date} {self.get_status_display()}"


class Period(TenantModel):
    """A month handed over to payroll: closed periods can no longer change (RG-14)."""

    class Status(models.TextChoices):
        OPEN = "open", "Ouverte"
        CLOSED = "closed", "Clôturée"

    month = models.DateField(help_text="Premier jour du mois")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reopen_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "période"
        ordering = ["-month"]
        constraints = [
            models.UniqueConstraint(fields=["company", "month"], name="period_unique_month")
        ]

    def __str__(self) -> str:
        return f"{self.month:%m/%Y} ({self.get_status_display()})"
