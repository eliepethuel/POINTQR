from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import HealthSerializer


class HealthView(APIView):
    """Public liveness probe; also returns the authoritative server clock."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(operation_id="system_health", responses=HealthSerializer, tags=["system"])
    def get(self, request: Request) -> Response:
        report = services.health_report()
        return Response(HealthSerializer(report).data)
