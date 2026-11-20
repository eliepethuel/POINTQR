"""Append-only audit trail (EF-41, ENF-12): who did what, when, from where, before/after."""

import uuid

from django.db import models

from common.models import AppendOnlyModel, TenantManager


class AuditLog(AppendOnlyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Nullable: platform-level events (super-admin) belong to no company.
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.PROTECT, null=True, related_name="+"
    )
    actor_user = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, related_name="+"
    )
    actor_label = models.CharField("acteur", max_length=200)
    action = models.CharField(max_length=64, db_index=True)
    object_type = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64)
    object_label = models.CharField(max_length=255, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "entrée du journal d'audit"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_label} {self.action}"
