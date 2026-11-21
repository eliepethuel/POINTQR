"""Short-lived signed download links (reports, attachments): usable in a plain <a href>."""

from typing import Any

from django.core import signing
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

SALT = "pointqr.download"
MAX_AGE = 600  # seconds


def signed_url(path: str, filename: str) -> str:
    token = signing.dumps({"p": path, "n": filename}, salt=SALT, compress=True)
    return f"/api/v1/files/?t={token}"


class SignedDownloadView(APIView):
    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="files_download",
        parameters=[OpenApiParameter("t", str, required=True)],
        responses={(200, "application/octet-stream"): bytes},
    )
    def get(self, request: Request) -> FileResponse:
        try:
            data = signing.loads(request.query_params.get("t", ""), salt=SALT, max_age=MAX_AGE)
        except signing.BadSignature as exc:
            raise Http404 from exc
        path = str(data["p"])
        if not default_storage.exists(path):
            raise Http404
        return FileResponse(
            default_storage.open(path, "rb"), as_attachment=True, filename=str(data["n"])
        )
