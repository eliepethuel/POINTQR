"""Justifications and correction requests with their approval circuit (EF-29 to EF-32)."""

from django.db import models

from common.models import TenantModel


class Request(TenantModel):
    class Kind(models.TextChoices):
        JUSTIFICATION = "justification", "Justificatif"
        CORRECTION = "correction", "Correction de pointage"
        OVERTIME = "overtime", "Heures supplémentaires"

    class Category(models.TextChoices):
        LATE = "late", "Retard"
        ABSENCE = "absence", "Absence"
        EARLY_LEAVE = "early_leave", "Départ anticipé"
        MISSING_CHECKIN = "missing_checkin", "Oubli de pointage"
        WRONG_CHECKIN = "wrong_checkin", "Pointage erroné"
        OVERTIME = "overtime", "Heures supplémentaires"

    class Status(models.TextChoices):
        PENDING_MANAGER = "pending_manager", "En attente du manager"
        PENDING_HR = "pending_hr", "En attente du RH"
        APPROVED = "approved", "Validée"
        REJECTED = "rejected", "Refusée"
        CANCELLED = "cancelled", "Annulée"

    agent = models.ForeignKey(
        "organization.Agent", on_delete=models.CASCADE, related_name="requests"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    category = models.CharField(max_length=20, choices=Category.choices)
    target_date = models.DateField("date concernée")
    #: Correction of an existing check-in (wrong direction/time) — the original is never altered.
    target_checkin = models.ForeignKey(
        "attendance.CheckIn", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    requested_direction = models.CharField(max_length=16, blank=True)
    requested_time = models.DateTimeField(null=True, blank=True)
    reason = models.TextField("motif")
    attachment = models.FileField("pièce jointe", upload_to="justificatifs/%Y/%m/", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_MANAGER)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    resulting_checkin = models.ForeignKey(
        "attendance.CheckIn", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = "demande"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "agent", "target_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.agent} {self.target_date}"


class RequestDecision(TenantModel):
    class Level(models.TextChoices):
        MANAGER = "manager", "Manager"
        HR = "hr", "RH"

    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name="decisions")
    level = models.CharField(max_length=8, choices=Level.choices)
    decided_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    approved = models.BooleanField()
    comment = models.TextField(blank=True)

    class Meta:
        verbose_name = "décision"
        ordering = ["created_at"]
