from datetime import date, datetime, time, timedelta
from typing import Any

from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import IsManagerOrAbove, role_permission
from apps.kiosks.views import outcome_payload
from apps.organization import selectors as org_selectors
from apps.organization.models import Agent, Device
from apps.organization.services import bind_device
from common.crypto import b64url, decrypt
from common.exceptions import DomainError
from common.pagination import TimelineCursorPagination
from common.request import company_of

from . import rules, services, tokens
from .models import CheckIn, Result
from .serializers import (
    ActivateRequestSerializer,
    CheckInOutcomeSerializer,
    CheckInSerializer,
    MobileStatusSerializer,
    PersonalKeySerializer,
    PhoneCheckInRequestSerializer,
    PrintedTokenSerializer,
)

IsAgent = role_permission(Role.AGENT)


class CheckInCursorPagination(TimelineCursorPagination):
    ordering = ("-effective_ts", "-id")  # type: ignore[assignment]


class DeviceRateThrottle(SimpleRateThrottle):
    """Throttle per phone (ENF-11), in addition to the per-IP limit."""

    scope = "checkin_device"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        device = request.data.get("device_id") if hasattr(request, "data") else None
        return self.cache_format % {"scope": self.scope, "ident": device} if device else None


class IpRateThrottle(SimpleRateThrottle):
    scope = "checkin_ip"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


def _agent_of(request: Request) -> Agent:
    agent = getattr(request.user, "agent", None)
    if agent is None:
        raise DomainError("Ce compte n'est lié à aucun agent.", code="no_agent", status_code=403)
    return agent


class MobileActivateView(APIView):
    """First connection on a phone: binds it to the agent (EF-09, RG-13)."""

    permission_classes = [IsAgent]

    @extend_schema(
        operation_id="mobile_activate",
        request=ActivateRequestSerializer,
        responses=MobileStatusSerializer,
        tags=["mobile"],
    )
    def post(self, request: Request) -> Response:
        data = ActivateRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        agent = _agent_of(request)
        bind_device(
            agent,
            data.validated_data["device_id"],
            model=data.validated_data["model"],
            os=data.validated_data["os"],
        )
        return Response(_status(agent, company_of(request)))


class MobileStatusView(APIView):
    permission_classes = [IsAgent]

    @extend_schema(
        operation_id="mobile_status",
        responses=MobileStatusSerializer,
        parameters=[OpenApiParameter("device_id", str, required=False)],
        tags=["mobile"],
    )
    def get(self, request: Request) -> Response:
        agent = _agent_of(request)
        return Response(
            _status(
                agent,
                company_of(request),
                request.query_params.get("device_id"),
            )
        )


def _status(agent: Agent, company: Any, device_id: str | None = None) -> dict[str, Any]:
    from django.utils import timezone

    from apps.organization.services import fingerprint_hash

    tz = services.tz_of(company)
    now = timezone.now()
    night = bool(agent.schedule and agent.schedule.is_night)
    today = services._accepted_today(agent, now, tz, night)
    device = Device.objects.filter(agent=agent, is_active=True).first()
    bound = device is not None and (
        device_id is None or device.fingerprint_hash == fingerprint_hash(device_id)
    )
    punches = [rules.Punch(at=c.effective_ts, direction=c.direction) for c in today]
    return {
        "agent_id": agent.id,
        "agent_name": agent.full_name,
        "employee_number": agent.employee_number,
        "device_bound": bound,
        "next_direction": rules.next_direction(punches),
        "site_name": agent.site.name if agent.site else None,
        "schedule": str(agent.schedule) if agent.schedule else None,
        "today": CheckInSerializer(today, many=True).data,
    }


class MobileCheckInView(APIView):
    """Mode A (kiosk QR) and mode D (printed site QR) scanned by the agent's phone."""

    permission_classes = [IsAgent]
    throttle_classes: list[type[BaseThrottle]] = [DeviceRateThrottle, IpRateThrottle]

    @extend_schema(
        operation_id="mobile_checkin",
        request=PhoneCheckInRequestSerializer,
        responses=CheckInOutcomeSerializer,
        tags=["mobile"],
    )
    def post(self, request: Request) -> Response:
        data = PhoneCheckInRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        outcome = services.phone_check_in(
            company_of(request),
            _agent_of(request),
            services.PhoneScan(**data.validated_data),
        )
        return Response(outcome_payload(outcome), status=201 if outcome.accepted else 200)


class MobilePersonalKeyView(APIView):
    """Key of the rotating personal QR (mode B), bound to the agent's phone."""

    permission_classes = [IsAgent]

    @extend_schema(
        operation_id="mobile_personal_key",
        responses=PersonalKeySerializer,
        parameters=[OpenApiParameter("device_id", str, required=True)],
        tags=["mobile"],
    )
    def get(self, request: Request) -> Response:
        from apps.organization.services import fingerprint_hash

        agent = _agent_of(request)
        device = Device.objects.filter(agent=agent, is_active=True).first()
        device_id = request.query_params.get("device_id", "")
        if device is None or device.fingerprint_hash != fingerprint_hash(device_id):
            raise DomainError("Téléphone non activé.", code="device_not_bound", status_code=403)
        key = tokens.derive_personal_key(decrypt(agent.badge_key), device.fingerprint_hash)
        return Response(
            {"agent_id": agent.id, "key": b64url(key), "window_seconds": tokens.WINDOW_SECONDS}
        )


class CheckInViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet[CheckIn]
):
    """Check-ins and anomalies (``result=refused``) for HR, managers (their scope) and auditors."""

    serializer_class = CheckInSerializer
    permission_classes = [IsManagerOrAbove]
    pagination_class = CheckInCursorPagination
    queryset = CheckIn.objects.none()
    filter_backends: list[Any] = []

    @extend_schema(
        parameters=[
            OpenApiParameter("result", str, enum=[r.value for r in Result]),
            OpenApiParameter("agent", str),
            OpenApiParameter("site", str),
            OpenApiParameter("date", date),
            OpenApiParameter("offline", bool),
        ]
    )
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[CheckIn]:
        qs = CheckIn.objects.select_related("agent", "site", "kiosk")
        user = self.request.user
        if not user.has_role(Role.COMPANY_ADMIN, Role.HR, Role.AUDITOR):  # type: ignore[union-attr]
            units: set[Any] = set()
            agent = getattr(user, "agent", None)
            if agent is not None:
                for unit in agent.managed_units.all():
                    units |= org_selectors.unit_descendant_ids(unit.id)
            qs = qs.filter(agent__org_unit_id__in=units)
        p = self.request.query_params
        if p.get("result"):
            qs = qs.filter(result=p["result"])
        if p.get("agent"):
            qs = qs.filter(agent_id=p["agent"])
        if p.get("site"):
            qs = qs.filter(site_id=p["site"])
        if p.get("offline") in ("true", "1"):
            qs = qs.filter(offline=True)
        if p.get("date"):
            day = date.fromisoformat(p["date"])
            tz = services.tz_of(company_of(self.request))
            start = datetime.combine(day, time.min, tzinfo=tz)
            qs = qs.filter(effective_ts__gte=start, effective_ts__lt=start + timedelta(days=1))
        return qs


class SitePrintedQrView(APIView):
    """Mode D: the static site QR to print for small structures without a kiosk."""

    permission_classes = [role_permission(Role.COMPANY_ADMIN)]

    @extend_schema(operation_id="sites_printed_qr", responses=PrintedTokenSerializer)
    def get(self, request: Request, pk: Any) -> Response:
        from apps.organization.models import Site
        from apps.organization.services import ensure_site_key

        site = Site.objects.filter(id=pk).first()
        if site is None:
            raise DomainError("Site introuvable.", code="not_found", status_code=404)
        if not site.static_qr_key:
            ensure_site_key(site)
            site.save(update_fields=["static_qr_key", "updated_at"])
        token = tokens.site_token(decrypt(site.static_qr_key), site.id, site.static_qr_version)
        return Response({"token": token, "caption": site.name})


class AgentBadgeView(APIView):
    """Mode C: the agent's printed badge QR (EF-11). Reprinting rotates it (rotate-badge)."""

    permission_classes = [role_permission(Role.COMPANY_ADMIN, Role.HR)]

    @extend_schema(operation_id="agents_badge", responses=PrintedTokenSerializer)
    def get(self, request: Request, pk: Any) -> Response:
        from apps.organization.services import ensure_badge_key

        agent = Agent.objects.filter(id=pk).first()
        if agent is None:
            raise DomainError("Agent introuvable.", code="not_found", status_code=404)
        if not agent.badge_key:
            ensure_badge_key(agent)
            agent.save(update_fields=["badge_key", "updated_at"])
        token = tokens.badge_token(decrypt(agent.badge_key), agent.id, agent.badge_version)
        return Response({"token": token, "caption": f"{agent.full_name} � {agent.employee_number}"})
