"""Work days, periods (RG-14) and the live dashboard API."""

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from django.db.models import Count, Q, QuerySet, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import IsCompanyAdmin, IsHrOrAdmin, IsManagerOrAbove
from apps.audit.services import record
from apps.organization import selectors as org_selectors
from apps.organization.models import Agent
from common.exceptions import DomainError
from common.request import company_of

from . import dashboard, workdays
from .models import Period, WorkDay


def manager_scope(request: Request) -> set[UUID] | None:
    """None = whole company (admin, HR, auditor); otherwise the managed sub-tree."""
    user = request.user
    if user.has_role(Role.COMPANY_ADMIN, Role.HR, Role.AUDITOR):  # type: ignore[union-attr]
        return None
    units: set[UUID] = set()
    agent = getattr(user, "agent", None)
    if agent is not None:
        for unit in agent.managed_units.all():
            units |= org_selectors.unit_descendant_ids(unit.id)
    return units


class WorkDaySerializer(serializers.ModelSerializer[WorkDay]):
    agent_name = serializers.CharField(source="agent.full_name", read_only=True)
    employee_number = serializers.CharField(source="agent.employee_number", read_only=True)
    unit_name = serializers.CharField(source="agent.org_unit.name", read_only=True, default=None)

    class Meta:
        model = WorkDay
        fields = [
            "id",
            "agent",
            "agent_name",
            "employee_number",
            "unit_name",
            "date",
            "status",
            "first_in",
            "last_out",
            "planned_start",
            "planned_end",
            "late_minutes",
            "early_leave_minutes",
            "worked_minutes",
            "overtime_minutes",
            "overtime_validated",
            "incomplete",
            "computed_at",
        ]
        read_only_fields = fields


class WorkDaySummarySerializer(serializers.Serializer[Any]):
    days = serializers.IntegerField()
    present = serializers.IntegerField()
    late_count = serializers.IntegerField()
    late_minutes = serializers.IntegerField()
    early_leave_count = serializers.IntegerField()
    early_leave_minutes = serializers.IntegerField()
    absences = serializers.IntegerField()
    justified_absences = serializers.IntegerField()
    incomplete = serializers.IntegerField()
    worked_minutes = serializers.IntegerField()
    overtime_minutes = serializers.IntegerField()


class RecomputeSerializer(serializers.Serializer[Any]):
    start = serializers.DateField()
    end = serializers.DateField()
    agent = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["end"] < attrs["start"] or (attrs["end"] - attrs["start"]).days > 62:
            raise serializers.ValidationError("Période de 62 jours maximum.")
        return attrs


def _period_filters(qs: QuerySet[WorkDay], params: Any) -> QuerySet[WorkDay]:
    if params.get("agent"):
        qs = qs.filter(agent_id=params["agent"])
    if params.get("start"):
        qs = qs.filter(date__gte=date.fromisoformat(params["start"]))
    if params.get("end"):
        qs = qs.filter(date__lte=date.fromisoformat(params["end"]))
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("unit"):
        qs = qs.filter(agent__org_unit_id=params["unit"])
    return qs


PERIOD_PARAMS = [
    OpenApiParameter("agent", str),
    OpenApiParameter("start", date),
    OpenApiParameter("end", date),
    OpenApiParameter("status", str),
    OpenApiParameter("unit", str),
]


class WorkDayViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[WorkDay]):
    serializer_class = WorkDaySerializer
    permission_classes = [IsManagerOrAbove]
    queryset = WorkDay.objects.none()
    filter_backends: list[Any] = []

    def get_queryset(self) -> QuerySet[WorkDay]:
        qs = WorkDay.objects.select_related("agent", "agent__org_unit").order_by(
            "-date", "agent__last_name"
        )
        scope = manager_scope(self.request)
        if scope is not None:
            qs = qs.filter(agent__org_unit_id__in=scope)
        return _period_filters(qs, self.request.query_params)

    @extend_schema(parameters=PERIOD_PARAMS)
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(
        operation_id="workdays_summary",
        parameters=PERIOD_PARAMS,
        responses=WorkDaySummarySerializer,
    )
    @action(detail=False, methods=["get"], pagination_class=None)
    def summary(self, request: Request) -> Response:
        """Cumulative lateness, absences and hours (agent file, EF-26)."""
        qs = self.get_queryset()
        totals = qs.aggregate(
            days=Count("id"),
            present=Count("id", filter=Q(first_in__isnull=False)),
            late_count=Count("id", filter=Q(late_minutes__gt=0)),
            late_minutes=Sum("late_minutes"),
            early_leave_count=Count("id", filter=Q(early_leave_minutes__gt=0)),
            early_leave_minutes=Sum("early_leave_minutes"),
            absences=Count("id", filter=Q(status=WorkDay.Status.ABSENT)),
            justified_absences=Count("id", filter=Q(status=WorkDay.Status.ABSENT_JUSTIFIED)),
            incomplete=Count("id", filter=Q(incomplete=True)),
            worked_minutes=Sum("worked_minutes"),
            overtime_minutes=Sum("overtime_minutes", filter=Q(overtime_validated=True)),
        )
        return Response({k: v or 0 for k, v in totals.items()})

    @extend_schema(
        operation_id="workdays_recompute", request=RecomputeSerializer, responses={200: None}
    )
    @action(detail=False, methods=["post"], permission_classes=[IsHrOrAdmin])
    def recompute(self, request: Request) -> Response:
        data = RecomputeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        agents = None
        if data.validated_data.get("agent"):
            agents = list(Agent.objects.filter(id=data.validated_data["agent"]))
        count = workdays.recompute_range(
            data.validated_data["start"], data.validated_data["end"], agents=agents
        )
        return Response({"recomputed": count})


class PeriodSerializer(serializers.ModelSerializer[Period]):
    class Meta:
        model = Period
        fields = ["id", "month", "status", "closed_at", "closed_by", "reopen_reason"]
        read_only_fields = ["id", "status", "closed_at", "closed_by", "reopen_reason"]


class ReopenSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(min_length=5)


class PeriodViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet[Period]
):
    """Monthly closing for payroll; reopening is traced in the audit log (RG-14)."""

    serializer_class = PeriodSerializer
    permission_classes = [IsHrOrAdmin]
    queryset = Period.objects.none()

    def get_queryset(self) -> QuerySet[Period]:
        return Period.objects.all()

    def perform_create(self, serializer: Any) -> None:
        month = serializer.validated_data["month"].replace(day=1)
        if Period.objects.filter(month=month).exists():
            raise DomainError("Cette période existe déjà.", code="period_exists", status_code=409)
        serializer.save(month=month)

    @extend_schema(operation_id="periods_close", request=None, responses=PeriodSerializer)
    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: Any = None) -> Response:
        period = self.get_object()
        last = (period.month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        workdays.recompute_range(period.month, min(last, timezone.localdate()))
        period.status = Period.Status.CLOSED
        period.closed_at = timezone.now()
        period.closed_by = request.user  # type: ignore[assignment]
        period.save()
        record("period.closed", period, actor=request.user, request=request._request)
        return Response(PeriodSerializer(period).data)

    @extend_schema(
        operation_id="periods_reopen", request=ReopenSerializer, responses=PeriodSerializer
    )
    @action(detail=True, methods=["post"], permission_classes=[IsCompanyAdmin])
    def reopen(self, request: Request, pk: Any = None) -> Response:
        period = self.get_object()  # 404 before validating the body (no existence oracle)
        data = ReopenSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        period.status = Period.Status.OPEN
        period.reopen_reason = data.validated_data["reason"]
        period.save()
        record(
            "period.reopened",
            period,
            actor=request.user,
            request=request._request,
            after={"reason": period.reopen_reason},
        )
        return Response(PeriodSerializer(period).data)


class _Kpis(serializers.Serializer[Any]):
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    absent = serializers.IntegerField()
    left_early = serializers.IntegerField()
    on_site = serializers.IntegerField()
    expected = serializers.IntegerField()
    anomalies = serializers.IntegerField()
    agents = serializers.IntegerField()


class _SiteStat(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    radius_m = serializers.IntegerField()
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    absent = serializers.IntegerField()


class _UnitStat(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    days = serializers.IntegerField()
    late = serializers.IntegerField()
    punctuality = serializers.FloatField()


class _Recent(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    agent_name = serializers.CharField()
    site = serializers.CharField(allow_null=True)
    direction = serializers.CharField(allow_blank=True)
    mode = serializers.CharField()
    at = serializers.DateTimeField()
    result = serializers.CharField()
    refusal_code = serializers.CharField(allow_blank=True)


class _Hour(serializers.Serializer[Any]):
    hour = serializers.IntegerField()
    count = serializers.IntegerField()


class _KioskStat(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    site = serializers.CharField()
    status = serializers.CharField()
    online = serializers.BooleanField()
    pending = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer[Any]):
    date = serializers.DateField()
    server_time = serializers.DateTimeField()
    kpis = _Kpis()
    sites = _SiteStat(many=True)
    units = _UnitStat(many=True)
    recent = _Recent(many=True)
    arrivals_by_hour = _Hour(many=True)
    kiosks = _KioskStat(many=True)


class DashboardView(APIView):
    """Today at a glance, for the whole company or the manager's teams (EF-25)."""

    permission_classes = [IsManagerOrAbove]

    @extend_schema(operation_id="dashboard_today", responses=DashboardSerializer)
    def get(self, request: Request) -> Response:
        return Response(dashboard.today(company_of(request), manager_scope(request)))
