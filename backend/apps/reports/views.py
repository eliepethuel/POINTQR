from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from rest_framework import mixins, serializers, viewsets

from apps.accounts.models import Role
from apps.accounts.permissions import role_permission
from common.downloads import signed_url
from common.request import company_of

from . import tasks
from .models import ReportJob, ReportSchedule

ReportUsers = role_permission(Role.COMPANY_ADMIN, Role.HR, read=(Role.AUDITOR,))


class ReportJobSerializer(serializers.ModelSerializer[ReportJob]):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ReportJob
        fields = [
            "id",
            "kind",
            "start",
            "end",
            "org_unit",
            "agent",
            "status",
            "progress",
            "filename",
            "error",
            "download_url",
            "created_at",
            "finished_at",
            "duration_ms",
        ]
        read_only_fields = [
            "id",
            "status",
            "progress",
            "filename",
            "error",
            "download_url",
            "created_at",
            "finished_at",
            "duration_ms",
        ]

    def get_download_url(self, obj: ReportJob) -> str | None:
        if obj.status != ReportJob.Status.DONE or not obj.file:
            return None
        return signed_url(obj.file.name or "", obj.filename)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["kind"] != ReportJob.Kind.BADGES:
            start, end = attrs.get("start"), attrs.get("end")
            if not start or not end or end < start:
                raise serializers.ValidationError("Indiquez une période valide.")
            if (end - start).days > 370:
                raise serializers.ValidationError("Période d'un an maximum.")
        return attrs


class ReportJobViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet[ReportJob],
):
    """Requesting a report starts a Celery job; the page polls its progress (EF-34 to EF-36)."""

    serializer_class = ReportJobSerializer
    permission_classes = [ReportUsers]
    queryset = ReportJob.objects.none()

    def get_queryset(self) -> QuerySet[ReportJob]:
        return ReportJob.objects.all()

    def perform_create(self, serializer: Any) -> None:
        job = serializer.save(requested_by=self.request.user)
        company = company_of(self.request)
        transaction.on_commit(lambda: tasks.generate.delay(str(company.id), str(job.id)))


class ReportScheduleSerializer(serializers.ModelSerializer[ReportSchedule]):
    class Meta:
        model = ReportSchedule
        fields = ["id", "kind", "frequency", "recipients", "is_active"]

    def validate_recipients(self, value: Any) -> list[str]:
        from django.core.validators import validate_email

        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("Au moins une adresse e-mail.")
        for email in value:
            validate_email(email)
        return value


class ReportScheduleViewSet(viewsets.ModelViewSet[ReportSchedule]):
    serializer_class = ReportScheduleSerializer
    permission_classes = [ReportUsers]
    queryset = ReportSchedule.objects.none()

    def get_queryset(self) -> QuerySet[ReportSchedule]:
        return ReportSchedule.objects.all()
