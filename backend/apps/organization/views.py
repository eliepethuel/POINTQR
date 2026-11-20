from typing import Any

from django.db.models import QuerySet
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from openpyxl import Workbook
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import ConfigReadable, IsHrOrAdmin, IsManagerOrAbove
from apps.audit.services import record

from . import selectors, services
from .importer import import_agents
from .models import Agent, Device, DeviceChangeRequest, OrgUnit, Site
from .serializers import (
    AgentSerializer,
    DeviceChangeRequestSerializer,
    DeviceSerializer,
    ImportReportSerializer,
    ImportRequestSerializer,
    OrgTreeNodeSerializer,
    OrgUnitSerializer,
    SiteSerializer,
)


class AuditedModelViewSet(viewsets.ModelViewSet[Any]):
    audit_prefix = ""

    def perform_create(self, serializer: Any) -> None:
        obj = serializer.save()
        record(
            f"{self.audit_prefix}.created",
            obj,
            actor=self.request.user,
            request=self.request._request,
            after=serializer.data,
        )

    def perform_update(self, serializer: Any) -> None:
        before = type(serializer)(serializer.instance).data
        obj = serializer.save()
        record(
            f"{self.audit_prefix}.updated",
            obj,
            actor=self.request.user,
            request=self.request._request,
            before=before,
            after=serializer.data,
        )

    def perform_destroy(self, instance: Any) -> None:
        record(
            f"{self.audit_prefix}.deleted",
            instance,
            actor=self.request.user,
            request=self.request._request,
        )
        instance.delete()


class SiteViewSet(AuditedModelViewSet):
    serializer_class = SiteSerializer
    permission_classes = [ConfigReadable]
    audit_prefix = "site"
    search_fields = ["name", "address"]
    queryset = Site.objects.none()

    def get_queryset(self) -> QuerySet[Site]:
        return selectors.sites_with_counts()

    def perform_create(self, serializer: Any) -> None:
        site = Site(**serializer.validated_data)
        services.ensure_site_key(site)
        site.save()
        serializer.instance = site
        record("site.created", site, actor=self.request.user, request=self.request._request)


class OrgUnitViewSet(AuditedModelViewSet):
    serializer_class = OrgUnitSerializer
    permission_classes = [ConfigReadable]
    audit_prefix = "org_unit"
    queryset = OrgUnit.objects.none()

    def get_queryset(self) -> QuerySet[OrgUnit]:
        return OrgUnit.objects.select_related("manager")

    @extend_schema(operation_id="org_units_tree", responses=OrgTreeNodeSerializer(many=True))
    @action(detail=False, methods=["get"], pagination_class=None)
    def tree(self, request: Request) -> Response:
        return Response(selectors.org_tree())


class AgentViewSet(AuditedModelViewSet):
    serializer_class = AgentSerializer
    permission_classes = [IsManagerOrAbove]
    audit_prefix = "agent"
    search_fields = ["employee_number", "last_name", "first_names", "job_title"]
    ordering_fields = ["last_name", "employee_number", "created_at"]
    queryset = Agent.objects.none()

    def get_permissions(self) -> Any:
        if self.action in {"list", "retrieve", "devices"}:
            return [IsManagerOrAbove()]
        return [IsHrOrAdmin()]

    def get_queryset(self) -> QuerySet[Agent]:
        qs = selectors.agents_list()
        user = self.request.user
        if not user.has_role(Role.COMPANY_ADMIN, Role.HR, Role.AUDITOR):  # type: ignore[union-attr]
            # A manager only sees the agents of the units they manage, and below (section 4).
            agent = getattr(user, "agent", None)
            units: set[Any] = set()
            if agent is not None:
                for unit in agent.managed_units.all():
                    units |= selectors.unit_descendant_ids(unit.id)
            qs = qs.filter(org_unit_id__in=units)
        params = self.request.query_params
        for field in ("site", "org_unit", "status"):
            if params.get(field):
                qs = qs.filter(**{f"{field}_id" if field != "status" else field: params[field]})
        return qs

    def perform_create(self, serializer: Any) -> None:
        agent = Agent(**serializer.validated_data)
        services.ensure_badge_key(agent)
        agent.save()
        serializer.instance = agent
        record("agent.created", agent, actor=self.request.user, request=self.request._request)

    def perform_destroy(self, instance: Agent) -> None:
        # Agents are never deleted (their check-ins are kept for 5 years): deactivate instead.
        instance.status = Agent.Status.INACTIVE
        instance.save(update_fields=["status", "updated_at"])
        record(
            "agent.deactivated", instance, actor=self.request.user, request=self.request._request
        )

    @extend_schema(
        operation_id="agents_import",
        request={"multipart/form-data": ImportRequestSerializer},
        responses=ImportReportSerializer,
    )
    @action(
        detail=False,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
        url_path="import",
    )
    def import_file(self, request: Request) -> Response:
        payload = ImportRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        upload = payload.validated_data["file"]
        try:
            report = import_agents(upload.name, upload, dry_run=payload.validated_data["dry_run"])
        except ValueError as exc:
            return Response(
                {
                    "total": 0,
                    "created": 0,
                    "updated": 0,
                    "dry_run": True,
                    "line_errors": [{"line": 0, "field": "fichier", "message": str(exc)}],
                },
                status=400,
            )
        if not report.dry_run and not report.errors:
            record(
                "agent.imported",
                None,
                actor=request.user,
                request=request._request,
                object_type="organization.agent",
                object_id="import",
                after={"created": report.created, "updated": report.updated},
            )
        data = ImportReportSerializer(report).data
        return Response(data, status=400 if report.errors else 200)

    @extend_schema(
        operation_id="agents_import_template", responses={(200, "application/octet-stream"): bytes}
    )
    @action(detail=False, methods=["get"], url_path="import-template")
    def import_template(self, request: Request) -> HttpResponse:
        workbook = Workbook()
        sheet = workbook.active
        if sheet is None:  # pragma: no cover - a new workbook always has a sheet
            sheet = workbook.create_sheet()
        sheet.title = "Agents"
        sheet.append(
            ["Matricule", "Nom", "Prénoms", "Fonction", "Téléphone", "Email", "Site", "Unité"]
        )
        sheet.append(
            [
                "A0001",
                "KOUASSI",
                "Aya Marie",
                "Secrétaire",
                "+225 07 00 00 00 01",
                "aya.kouassi@example.ci",
                "",
                "",
            ]
        )
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="modele-import-agents.xlsx"'
        workbook.save(response)
        return response

    @extend_schema(operation_id="agents_devices", responses=DeviceSerializer(many=True))
    @action(detail=True, methods=["get"], pagination_class=None)
    def devices(self, request: Request, pk: Any = None) -> Response:
        agent = self.get_object()
        return Response(DeviceSerializer(agent.devices.all(), many=True).data)

    @extend_schema(operation_id="agents_rotate_badge", request=None, responses=AgentSerializer)
    @action(detail=True, methods=["post"], url_path="rotate-badge")
    def rotate_badge(self, request: Request, pk: Any = None) -> Response:
        agent = services.rotate_badge(
            self.get_object(), actor=request.user, request=request._request
        )
        return Response(AgentSerializer(agent).data)


class DeviceViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet[Device]):
    serializer_class = DeviceSerializer
    permission_classes = [IsHrOrAdmin]
    queryset = Device.objects.none()

    def get_queryset(self) -> QuerySet[Device]:
        return Device.objects.select_related("agent")

    @extend_schema(operation_id="devices_revoke", request=None, responses=DeviceSerializer)
    @action(detail=True, methods=["post"])
    def revoke(self, request: Request, pk: Any = None) -> Response:
        device = services.revoke_device(
            self.get_object(), actor=request.user, request=request._request
        )
        return Response(DeviceSerializer(device).data)


class DeviceChangeRequestViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet[DeviceChangeRequest]
):
    serializer_class = DeviceChangeRequestSerializer
    permission_classes = [IsHrOrAdmin]
    queryset = DeviceChangeRequest.objects.none()

    def get_queryset(self) -> QuerySet[DeviceChangeRequest]:
        qs = DeviceChangeRequest.objects.select_related("agent")
        status = self.request.query_params.get("status")
        return qs.filter(status=status) if status else qs

    def _decide(self, request: Request, approve: bool) -> Response:
        change = services.decide_device_change(
            self.get_object(), approve=approve, actor=request.user, request=request._request
        )
        return Response(DeviceChangeRequestSerializer(change).data)

    @extend_schema(
        operation_id="device_requests_approve",
        request=None,
        responses=DeviceChangeRequestSerializer,
    )
    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: Any = None) -> Response:
        return self._decide(request, True)

    @extend_schema(
        operation_id="device_requests_reject", request=None, responses=DeviceChangeRequestSerializer
    )
    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk: Any = None) -> Response:
        return self._decide(request, False)
