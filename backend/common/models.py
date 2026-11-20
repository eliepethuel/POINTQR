"""Base models shared by every app."""

import uuid
from typing import Any, ClassVar

from django.core.exceptions import ImproperlyConfigured
from django.db import models

from apps.tenancy.context import current_company_id


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        abstract = True


class TenantQuerySet(models.QuerySet[Any]):
    pass


class TenantManager(models.Manager[Any]):
    """ORM-side tenant filter. Row level security remains the real barrier."""

    def get_queryset(self) -> models.QuerySet[Any]:
        qs = super().get_queryset()
        company_id = current_company_id()
        return qs.filter(company_id=company_id) if company_id else qs


class SharedTenantManager(models.Manager[Any]):
    """Like TenantManager, plus shared reference rows (company NULL), e.g. national holidays."""

    def get_queryset(self) -> models.QuerySet[Any]:
        qs = super().get_queryset()
        company_id = current_company_id()
        if company_id is None:
            return qs
        return qs.filter(models.Q(company_id=company_id) | models.Q(company_id__isnull=True))


class TenantModel(TimeStampedModel):
    """Every business table carries ``company_id`` and is protected by RLS (ADR-0004)."""

    company = models.ForeignKey(
        "tenancy.Company",
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
        verbose_name="entreprise",
    )

    objects: ClassVar[TenantManager] = TenantManager()
    unscoped: ClassVar[models.Manager[Any]] = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.company_id is None:
            company_id = current_company_id()
            if company_id is None:
                raise ImproperlyConfigured(
                    f"{type(self).__name__} saved outside of a tenant context."
                )
            self.company_id = company_id
        super().save(*args, **kwargs)


class TenantAppendOnlyModel(models.Model):
    """Tenant row that is only ever inserted (check-ins): no ``updated_at`` on purpose."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.PROTECT, related_name="+", editable=False
    )
    created_at = models.DateTimeField("enregistré le", auto_now_add=True, db_index=True)

    objects: ClassVar[TenantManager] = TenantManager()
    unscoped: ClassVar[models.Manager[Any]] = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise PermissionError(f"{type(self).__name__} is append-only.")
        if self.company_id is None:
            company_id = current_company_id()
            if company_id is None:
                raise ImproperlyConfigured(f"{type(self).__name__} saved outside a tenant context.")
            self.company_id = company_id
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise PermissionError(f"{type(self).__name__} is append-only.")


class AppendOnlyModel(models.Model):
    """Rows that are never updated nor deleted (CheckIn, AuditLog). Enforced by a DB trigger too."""

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise PermissionError(f"{type(self).__name__} is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise PermissionError(f"{type(self).__name__} is append-only.")
