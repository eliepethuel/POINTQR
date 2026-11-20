"""In-app notifications (EF-27, EF-28). SMS/WhatsApp come in V2 (PQR-004)."""

from django.db import models

from common.models import TenantModel


class Notification(TenantModel):
    class Kind(models.TextChoices):
        MISSING_EXIT = "missing_exit", "Oubli de sortie"
        ABSENT_ALERT = "absent_alert", "Absence à H+30"
        EARLY_LEAVE = "early_leave", "Départ anticipé"
        FRAUD = "fraud", "Tentative de fraude"
        REQUEST = "request", "Demande"
        REPORT = "report", "Rapport prêt"

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=255, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "notification"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "user", "read_at"])]

    def __str__(self) -> str:
        return self.title
