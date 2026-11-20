"""Entrance kiosks (tablets) and their pairing codes (EF-17, EF-42)."""

from django.db import models
from django.db.models import Q

from common.models import TenantModel


class Kiosk(TenantModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Révoquée"

    site = models.ForeignKey("organization.Site", on_delete=models.PROTECT, related_name="kiosks")
    name = models.CharField("nom", max_length=120)
    #: HMAC-SHA256 key of the dynamic QR, Fernet-encrypted at rest (ADR-0005, ENF-08).
    secret_key = models.TextField(editable=False)
    key_version = models.PositiveIntegerField(default=1, editable=False)
    #: SHA-256 of the machine token the kiosk sends with each API call.
    token_hash = models.CharField(max_length=64, editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    last_seen_at = models.DateTimeField("dernière connexion", null=True, blank=True)
    app_version = models.CharField(max_length=32, blank=True)
    pending_offline = models.PositiveIntegerField("pointages en attente", default=0)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "borne"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE


class KioskPairingCode(TenantModel):
    """6-digit code typed on the tablet to register it (valid 15 minutes, single use)."""

    site = models.ForeignKey("organization.Site", on_delete=models.CASCADE, related_name="+")
    name = models.CharField(max_length=120)
    code_hash = models.CharField(max_length=64, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    kiosk = models.OneToOneField(
        Kiosk, on_delete=models.SET_NULL, null=True, blank=True, related_name="pairing"
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        verbose_name = "code d'appairage"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code_hash"],
                condition=Q(used_at__isnull=True),
                name="pairing_code_unique_unused",
            ),
        ]
