from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import ConfigReadable
from apps.attendance import services as attendance
from apps.attendance.serializers import (
    BadgeBatchRequestSerializer,
    BadgeScanRequestSerializer,
    BatchResultSerializer,
    CheckInOutcomeSerializer,
)
from apps.organization.models import Site
from common.exceptions import DomainError
from common.request import company_of

from . import services
from .authentication import IsKiosk, KioskAuthentication, kiosk_of
from .models import Kiosk
from .serializers import (
    HeartbeatRequestSerializer,
    HeartbeatResponseSerializer,
    KioskSerializer,
    PairingCodeRequestSerializer,
    PairingCodeSerializer,
    PairRequestSerializer,
    PairResponseSerializer,
)


def outcome_payload(outcome: attendance.Outcome) -> dict[str, Any]:
    c = outcome.checkin
    return {
        "id": c.id,
        "result": c.result,
        "direction": c.direction,
        "refusal_code": c.refusal_code,
        "refusal_details": c.refusal_details or [],
        "message": outcome.message,
        "late_minutes": outcome.late_minutes,
        "effective_ts": c.effective_ts,
        "offline": c.offline,
        "agent_name": c.agent.full_name if c.agent else None,
    }


class KioskViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet[Kiosk]
):
    """Back-office management of the entrance tablets (company administrator)."""

    serializer_class = KioskSerializer
    permission_classes = [ConfigReadable]
    queryset = Kiosk.objects.none()

    def get_queryset(self) -> QuerySet[Kiosk]:
        return Kiosk.objects.select_related("site")

    @extend_schema(
        operation_id="kiosks_pairing_code",
        request=PairingCodeRequestSerializer,
        responses=PairingCodeSerializer,
    )
    @action(detail=False, methods=["post"], url_path="pairing-codes")
    def pairing_code(self, request: Request) -> Response:
        data = PairingCodeRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        site = Site.objects.filter(id=data.validated_data["site"]).first()
        if site is None:
            raise DomainError("Site introuvable.", code="site_not_found", status_code=404)
        code, pairing = services.create_pairing_code(
            site, data.validated_data["name"], actor=request.user, request=request._request
        )
        return Response(
            {"code": code, "expires_at": pairing.expires_at, "site_name": site.name}, status=201
        )

    @extend_schema(operation_id="kiosks_revoke", request=None, responses=KioskSerializer)
    @action(detail=True, methods=["post"])
    def revoke(self, request: Request, pk: Any = None) -> Response:
        kiosk = services.revoke(self.get_object(), actor=request.user, request=request._request)
        return Response(KioskSerializer(kiosk).data)

    @extend_schema(operation_id="kiosks_rotate_key", request=None, responses=KioskSerializer)
    @action(detail=True, methods=["post"], url_path="rotate-key")
    def rotate_key(self, request: Request, pk: Any = None) -> Response:
        kiosk = services.rotate_key(self.get_object(), actor=request.user, request=request._request)
        return Response(KioskSerializer(kiosk).data)


class KioskPairView(APIView):
    """The tablet exchanges the 6-digit code for its identity, key and machine token."""

    authentication_classes: list[Any] = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(
        operation_id="kiosk_pair",
        request=PairRequestSerializer,
        responses=PairResponseSerializer,
        tags=["kiosk"],
    )
    def post(self, request: Request) -> Response:
        company = getattr(request._request, "company", None)
        if company is None:
            raise DomainError(
                "Code entreprise manquant (en-tête X-Company-Code).",
                code="unknown_company",
                status_code=400,
            )
        if not company.is_active:
            raise DomainError("Entreprise suspendue.", code="company_suspended", status_code=403)
        data = PairRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            result = services.pair(data.validated_data["code"])
        site = result.kiosk.site
        return Response(
            {
                "kiosk_id": result.kiosk.id,
                "kiosk_name": result.kiosk.name,
                "token": result.token,
                "secret": result.secret,
                "key_version": result.kiosk.key_version,
                "site": {
                    "id": site.id,
                    "name": site.name,
                    "latitude": float(site.latitude),
                    "longitude": float(site.longitude),
                    "radius_m": site.radius_m,
                },
                "company": {
                    "legal_name": company.legal_name,
                    "code": company.code,
                    "timezone": company.timezone,
                    "primary_color": company.primary_color,
                    "highlight_color": company.highlight_color,
                },
                "epoch_ms": int(timezone.now().timestamp() * 1000),
            },
            status=201,
        )


class KioskMachineView(APIView):
    authentication_classes = [KioskAuthentication]
    permission_classes = [IsKiosk]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "kiosk"


class KioskHeartbeatView(KioskMachineView):
    @extend_schema(
        operation_id="kiosk_heartbeat",
        request=HeartbeatRequestSerializer,
        responses=HeartbeatResponseSerializer,
        tags=["kiosk"],
    )
    def post(self, request: Request) -> Response:
        data = HeartbeatRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        body = services.heartbeat(kiosk_of(request), **data.validated_data)
        body["epoch_ms"] = int(timezone.now().timestamp() * 1000)
        return Response(body)


class KioskCheckInView(KioskMachineView):
    """Badge (mode C) or personal rotating QR (mode B) scanned by the tablet camera."""

    @extend_schema(
        operation_id="kiosk_checkin",
        request=BadgeScanRequestSerializer,
        responses=CheckInOutcomeSerializer,
        tags=["kiosk"],
    )
    def post(self, request: Request) -> Response:
        data = BadgeScanRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        outcome = attendance.kiosk_check_in(
            company_of(request),
            kiosk_of(request),
            attendance.BadgeScan(**data.validated_data),
        )
        return Response(outcome_payload(outcome), status=201 if outcome.accepted else 200)


class KioskBatchView(KioskMachineView):
    """Offline queue upload (up to 7 days, R5): idempotent per client_uuid."""

    @extend_schema(
        operation_id="kiosk_checkins_batch",
        request=BadgeBatchRequestSerializer,
        responses=BatchResultSerializer,
        tags=["kiosk"],
    )
    def post(self, request: Request) -> Response:
        data = BadgeBatchRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        company = company_of(request)
        results, accepted = [], 0
        for item in sorted(
            data.validated_data["items"], key=lambda i: i.get("scanned_at") or timezone.now()
        ):
            with transaction.atomic():
                outcome = attendance.kiosk_check_in(
                    company, kiosk_of(request), attendance.BadgeScan(**item)
                )
            accepted += int(outcome.accepted)
            results.append(
                {
                    "client_uuid": item.get("client_uuid"),
                    "result": outcome.checkin.result,
                    "refusal_code": outcome.checkin.refusal_code,
                }
            )
        return Response({"received": len(results), "accepted": accepted, "items": results})
