from typing import Any

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from . import services
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer[Notification]):
    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "link", "read_at", "created_at"]
        read_only_fields = fields


class MarkReadSerializer(serializers.Serializer[Any]):
    ids = serializers.ListField(child=serializers.UUIDField(), required=False)


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[Notification]):
    """The current user's notifications."""

    serializer_class = NotificationSerializer
    queryset = Notification.objects.none()

    def get_queryset(self) -> QuerySet[Notification]:
        qs = Notification.objects.filter(user=self.request.user)
        if self.request.query_params.get("unread") in ("1", "true"):
            qs = qs.filter(read_at__isnull=True)
        return qs

    @extend_schema(
        operation_id="notifications_mark_read", request=MarkReadSerializer, responses={200: None}
    )
    @action(detail=False, methods=["post"], url_path="mark-read")
    def mark_read(self, request: Request) -> Response:
        data = MarkReadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        count = services.mark_read(request.user, data.validated_data.get("ids"))  # type: ignore[arg-type]
        return Response({"updated": count})
