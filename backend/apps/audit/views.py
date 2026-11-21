from datetime import date
from typing import Any

from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import role_permission
from common.pagination import TimelineCursorPagination

from .models import AuditLog

AuditReaders = role_permission(read=(Role.COMPANY_ADMIN, Role.AUDITOR))


class AuditLogSerializer(serializers.ModelSerializer[AuditLog]):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor_label",
            "action",
            "object_type",
            "object_id",
            "object_label",
            "before",
            "after",
            "ip",
            "user_agent",
            "created_at",
        ]
        read_only_fields = fields


class AuditLogViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet[AuditLog]
):
    """Read-only audit trail (EF-41): nobody can edit or delete an entry, not even the admin."""

    serializer_class = AuditLogSerializer
    permission_classes = [AuditReaders]
    pagination_class = TimelineCursorPagination
    queryset = AuditLog.objects.none()
    filter_backends: list[Any] = []

    def get_queryset(self) -> QuerySet[AuditLog]:
        qs = AuditLog.objects.all()
        p = self.request.query_params
        if p.get("action"):
            qs = qs.filter(action__startswith=p["action"])
        if p.get("object_id"):
            qs = qs.filter(object_id=p["object_id"])
        if p.get("date"):
            qs = qs.filter(created_at__date=date.fromisoformat(p["date"]))
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("action", str),
            OpenApiParameter("object_id", str),
            OpenApiParameter("date", date),
        ]
    )
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)
