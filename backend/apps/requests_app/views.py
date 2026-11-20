from typing import Any, cast

from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request as DrfRequest
from rest_framework.response import Response

from apps.accounts.models import Role, User
from apps.attendance.days_views import manager_scope
from apps.attendance.models import CheckIn, Direction
from apps.organization.models import Agent
from common.downloads import signed_url
from common.exceptions import DomainError
from common.request import company_of

from . import services
from .models import Request, RequestDecision


class DecisionSerializer(serializers.ModelSerializer[RequestDecision]):
    decided_by_name = serializers.CharField(source="decided_by.__str__", read_only=True)

    class Meta:
        model = RequestDecision
        fields = ["id", "level", "approved", "comment", "decided_by_name", "created_at"]
        read_only_fields = fields


class RequestSerializer(serializers.ModelSerializer[Request]):
    agent_name = serializers.CharField(source="agent.full_name", read_only=True)
    decisions = DecisionSerializer(many=True, read_only=True)
    attachment_url = serializers.SerializerMethodField()
    can_decide = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = [
            "id",
            "agent",
            "agent_name",
            "kind",
            "category",
            "target_date",
            "target_checkin",
            "requested_direction",
            "requested_time",
            "reason",
            "status",
            "decisions",
            "attachment_url",
            "can_decide",
            "resulting_checkin",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "agent_name",
            "status",
            "decisions",
            "attachment_url",
            "can_decide",
            "resulting_checkin",
            "created_at",
        ]

    def get_attachment_url(self, obj: Request) -> str | None:
        if not obj.attachment:
            return None
        return signed_url(obj.attachment.name or "", (obj.attachment.name or "").rsplit("/", 1)[-1])

    def get_can_decide(self, obj: Request) -> bool:
        user = self.context["request"].user
        return services.can_decide(user, obj)


class RequestCreateSerializer(serializers.Serializer[Any]):
    agent = serializers.UUIDField(
        required=False, help_text="RH uniquement : demande pour un agent."
    )
    kind = serializers.ChoiceField(choices=Request.Kind.choices)
    category = serializers.ChoiceField(choices=Request.Category.choices)
    target_date = serializers.DateField()
    reason = serializers.CharField(max_length=2000)
    target_checkin = serializers.UUIDField(required=False, allow_null=True)
    requested_direction = serializers.ChoiceField(
        choices=Direction.choices, required=False, allow_blank=True
    )
    requested_time = serializers.DateTimeField(required=False, allow_null=True)
    attachment = serializers.FileField(required=False, allow_null=True)


class DecideSerializer(serializers.Serializer[Any]):
    approve = serializers.BooleanField()
    comment = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class RequestViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet[Request],
):
    """Justifications, corrections and overtime: agents see theirs, managers their teams, HR all."""

    serializer_class = RequestSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    queryset = Request.objects.none()
    filter_backends: list[Any] = []

    def get_queryset(self) -> QuerySet[Request]:
        qs = Request.objects.select_related("agent").prefetch_related("decisions__decided_by")
        user = self.request.user
        if user.has_role(Role.COMPANY_ADMIN, Role.HR, Role.AUDITOR):  # type: ignore[union-attr]
            pass
        elif user.has_role(Role.MANAGER):  # type: ignore[union-attr]
            scope = manager_scope(self.request) or set()
            own = getattr(user, "agent_id", None)
            qs = qs.filter(agent__org_unit_id__in=scope) | qs.filter(agent_id=own)
        else:
            qs = qs.filter(agent_id=getattr(user, "agent_id", None))
        status = self.request.query_params.get("status")
        if status == "pending":
            qs = qs.filter(status__in=[Request.Status.PENDING_MANAGER, Request.Status.PENDING_HR])
        elif status:
            qs = qs.filter(status=status)
        return qs

    @extend_schema(parameters=[OpenApiParameter("status", str)])
    def list(self, request: DrfRequest, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(
        operation_id="requests_create",
        request={
            "multipart/form-data": RequestCreateSerializer,
            "application/json": RequestCreateSerializer,
        },
        responses=RequestSerializer,
    )
    def create(self, request: DrfRequest, *args: Any, **kwargs: Any) -> Response:
        data = RequestCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = cast(User, request.user)
        if v.get("agent") and user.has_role(Role.HR, Role.COMPANY_ADMIN):
            agent = Agent.objects.filter(id=v["agent"]).first()
        else:
            agent = getattr(user, "agent", None)
        if agent is None:
            raise DomainError("Aucun agent lié à ce compte.", code="no_agent", status_code=403)
        checkin = (
            CheckIn.objects.filter(id=v["target_checkin"]).first()
            if v.get("target_checkin")
            else None
        )
        req = services.create(
            company=company_of(request),
            agent=agent,
            author=user,
            kind=v["kind"],
            category=v["category"],
            target_date=v["target_date"],
            reason=v["reason"],
            attachment=v.get("attachment"),
            target_checkin=checkin,
            requested_direction=v.get("requested_direction", ""),
            requested_time=v.get("requested_time"),
        )
        return Response(RequestSerializer(req, context={"request": request}).data, status=201)

    @extend_schema(
        operation_id="requests_decide", request=DecideSerializer, responses=RequestSerializer
    )
    @action(detail=True, methods=["post"], parser_classes=[JSONParser])
    def decide(self, request: DrfRequest, pk: Any = None) -> Response:
        req = self.get_object()
        data = DecideSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        req = services.decide(
            req,
            user=cast(User, request.user),
            approve=data.validated_data["approve"],
            comment=data.validated_data.get("comment", ""),
            company=company_of(request),
            request=request._request,
        )
        req = self.get_queryset().get(id=req.id)  # fresh decisions, not the prefetched ones
        return Response(RequestSerializer(req, context={"request": request}).data)

    @extend_schema(operation_id="requests_cancel", request=None, responses=RequestSerializer)
    @action(detail=True, methods=["post"], parser_classes=[JSONParser])
    def cancel(self, request: DrfRequest, pk: Any = None) -> Response:
        req = services.cancel(self.get_object(), user=cast(User, request.user))
        return Response(RequestSerializer(req, context={"request": request}).data)
