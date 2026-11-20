from typing import Any

from django.db.models import Q, QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import role_permission
from apps.organization.views import AuditedModelViewSet
from common.exceptions import DomainError

from .models import PublicHoliday, Schedule, ScheduleAssignment, ScheduleException

ScheduleAdmin = role_permission(Role.COMPANY_ADMIN, Role.HR, read=(Role.MANAGER, Role.AUDITOR))


class ScheduleSerializer(serializers.ModelSerializer[Schedule]):
    is_night = serializers.BooleanField(read_only=True)
    agent_count = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = [
            "id",
            "name",
            "weekdays",
            "start_time",
            "end_time",
            "break_minutes",
            "late_tolerance_min",
            "early_tolerance_min",
            "overtime_threshold_min",
            "is_night",
            "agent_count",
        ]
        read_only_fields = ["id", "is_night", "agent_count"]

    def get_agent_count(self, obj: Schedule) -> int:
        return obj.agents.count()

    def validate_weekdays(self, value: list[int]) -> list[int]:
        cleaned = sorted(set(value))
        if not cleaned or any(d < 0 or d > 6 for d in cleaned):
            raise serializers.ValidationError(
                "Choisissez au moins un jour (0 = lundi … 6 = dimanche)."
            )
        return cleaned


class AssignmentSerializer(serializers.ModelSerializer[ScheduleAssignment]):
    class Meta:
        model = ScheduleAssignment
        fields = ["id", "agent", "schedule", "start_date", "end_date"]


class ExceptionSerializer(serializers.ModelSerializer[ScheduleException]):
    class Meta:
        model = ScheduleException
        fields = ["id", "name", "start_date", "end_date", "schedule", "org_unit"]


class HolidaySerializer(serializers.ModelSerializer[PublicHoliday]):
    national = serializers.SerializerMethodField()

    class Meta:
        model = PublicHoliday
        fields = ["id", "date", "label", "country", "is_worked", "national"]
        read_only_fields = ["id", "national"]

    def get_national(self, obj: PublicHoliday) -> bool:
        return obj.company_id is None


class ScheduleViewSet(AuditedModelViewSet):
    serializer_class = ScheduleSerializer
    permission_classes = [ScheduleAdmin]
    audit_prefix = "schedule"
    queryset = Schedule.objects.none()

    def get_queryset(self) -> QuerySet[Schedule]:
        return Schedule.objects.all()

    def perform_destroy(self, instance: Any) -> None:
        if instance.agents.exists():
            raise DomainError(
                "Horaire utilisé par des agents.", code="schedule_in_use", status_code=409
            )
        super().perform_destroy(instance)


class AssignmentViewSet(AuditedModelViewSet):
    serializer_class = AssignmentSerializer
    permission_classes = [ScheduleAdmin]
    audit_prefix = "schedule_assignment"
    queryset = ScheduleAssignment.objects.none()

    def get_queryset(self) -> QuerySet[ScheduleAssignment]:
        qs = ScheduleAssignment.objects.select_related("schedule")
        agent = self.request.query_params.get("agent")
        return qs.filter(agent_id=agent) if agent else qs


class ExceptionViewSet(AuditedModelViewSet):
    serializer_class = ExceptionSerializer
    permission_classes = [ScheduleAdmin]
    audit_prefix = "schedule_exception"
    queryset = ScheduleException.objects.none()

    def get_queryset(self) -> QuerySet[ScheduleException]:
        return ScheduleException.objects.select_related("schedule")


class HolidayViewSet(AuditedModelViewSet):
    """National holidays (read-only, shared) plus the company's own days (EF-15)."""

    serializer_class = HolidaySerializer
    permission_classes = [ScheduleAdmin]
    audit_prefix = "holiday"
    queryset = PublicHoliday.objects.none()

    def get_queryset(self) -> QuerySet[PublicHoliday]:
        qs = PublicHoliday.objects.filter(Q(company__isnull=True) | Q(company__isnull=False))
        year = self.request.query_params.get("year")
        return qs.filter(date__year=int(year)) if year and year.isdigit() else qs

    @extend_schema(parameters=[OpenApiParameter("year", int)])
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer: Any) -> None:
        holiday = PublicHoliday(**serializer.validated_data)
        holiday.company_id = request_company_id(self.request)
        holiday.save()
        serializer.instance = holiday

    def perform_update(self, serializer: Any) -> None:
        if serializer.instance.company_id is None:
            raise DomainError(
                "Les jours fériés nationaux ne se modifient pas : ajoutez une ligne "
                "propre à l'entreprise (par exemple « travaillé »).",
                code="national_holiday",
                status_code=409,
            )
        super().perform_update(serializer)

    def perform_destroy(self, instance: Any) -> None:
        if instance.company_id is None:
            raise DomainError("Jour férié national.", code="national_holiday", status_code=409)
        super().perform_destroy(instance)


def request_company_id(request: Request) -> Any:
    from common.request import company_of

    return company_of(request).id
