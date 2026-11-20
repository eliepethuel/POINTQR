from typing import Any

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import ConfigReadable, IsPlatformAdmin
from apps.audit.services import record

from . import services
from .models import Company, Subscription
from .serializers import (
    CompanySerializer,
    CompanySettingsSerializer,
    OnboardingSerializer,
    PlatformStatsSerializer,
    SubscriptionSerializer,
)


class CompanyViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet[Company],
):
    """Super-admin console: companies and their status."""

    serializer_class = CompanySerializer
    permission_classes = [IsPlatformAdmin]
    search_fields = ["legal_name", "slug", "code"]
    queryset = Company.objects.all()

    @extend_schema(
        operation_id="platform_companies_onboard",
        request=OnboardingSerializer,
        responses=CompanySerializer,
    )
    @action(detail=False, methods=["post"])
    def onboard(self, request: Request) -> Response:
        payload = OnboardingSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        company = services.onboard_company(
            payload.validated_data, actor=request.user, request=request._request
        )
        return Response(CompanySerializer(company).data, status=201)

    @extend_schema(
        operation_id="platform_companies_suspend", request=None, responses=CompanySerializer
    )
    @action(detail=True, methods=["post"])
    def suspend(self, request: Request, pk: Any = None) -> Response:
        company = services.set_status(
            self.get_object(),
            Company.Status.SUSPENDED,
            actor=request.user,
            request=request._request,
        )
        return Response(CompanySerializer(company).data)

    @extend_schema(
        operation_id="platform_companies_reactivate", request=None, responses=CompanySerializer
    )
    @action(detail=True, methods=["post"])
    def reactivate(self, request: Request, pk: Any = None) -> Response:
        company = services.set_status(
            self.get_object(), Company.Status.ACTIVE, actor=request.user, request=request._request
        )
        return Response(CompanySerializer(company).data)


class SubscriptionViewSet(viewsets.ModelViewSet[Subscription]):
    serializer_class = SubscriptionSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = Subscription.objects.select_related("company")

    def get_queryset(self) -> QuerySet[Subscription]:
        qs = super().get_queryset()
        company = self.request.query_params.get("company")
        return qs.filter(company_id=company) if company else qs


class PlatformStatsView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(operation_id="platform_stats", responses=PlatformStatsSerializer)
    def get(self, request: Request) -> Response:
        from django.utils import timezone

        from apps.organization.models import Agent

        stats: dict[str, int] = {
            "companies": Company.objects.count(),
            "active_companies": Company.objects.filter(status=Company.Status.ACTIVE).count(),
            # Platform scope (RLS SELECT policy) lets the editor read aggregates, never modify.
            "agents": Agent.objects.count(),
            "checkins_today": 0,
        }
        try:
            from apps.attendance.models import CheckIn

            stats["checkins_today"] = CheckIn.objects.filter(
                server_ts__date=timezone.localdate()
            ).count()
        except ImportError:  # pragma: no cover
            pass
        return Response(stats)


class CompanySettingsView(APIView):
    """GET for every member (branding), PATCH for the company administrator."""

    permission_classes = [ConfigReadable]

    def get_permissions(self) -> Any:
        if self.request.method == "GET":
            from rest_framework.permissions import IsAuthenticated

            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(operation_id="company_settings_get", responses=CompanySettingsSerializer)
    def get(self, request: Request) -> Response:
        return Response(CompanySettingsSerializer(request._request.company).data)  # type: ignore[attr-defined]

    @extend_schema(
        operation_id="company_settings_update",
        request=CompanySettingsSerializer,
        responses=CompanySettingsSerializer,
    )
    def patch(self, request: Request) -> Response:
        company = request._request.company  # type: ignore[attr-defined]
        before = CompanySettingsSerializer(company).data
        serializer = CompanySettingsSerializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record(
            "company.settings_updated",
            company,
            actor=request.user,
            request=request._request,
            before=before,
            after=serializer.data,
        )
        return Response(serializer.data)
