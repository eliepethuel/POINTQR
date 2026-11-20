"""Single error format for the whole API: RFC 7807 « problem details ».

Every error body has: ``type``, ``title``, ``status``, ``detail``, ``code`` and, for validation
errors, ``errors`` (field -> list of messages).
"""

from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

PROBLEM_BASE_URI = "https://pointqr.ci/problems/"
PROBLEM_CONTENT_TYPE = "application/problem+json"

_TITLES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "Requête invalide",
    status.HTTP_401_UNAUTHORIZED: "Authentification requise",
    status.HTTP_403_FORBIDDEN: "Accès refusé",
    status.HTTP_404_NOT_FOUND: "Ressource introuvable",
    status.HTTP_405_METHOD_NOT_ALLOWED: "Méthode non autorisée",
    status.HTTP_409_CONFLICT: "Conflit",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "Traitement impossible",
    status.HTTP_429_TOO_MANY_REQUESTS: "Trop de requêtes",
}


class DomainError(exceptions.APIException):
    """Business rule violation raised by services, with a stable machine-readable code."""

    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "domain_error"
    default_detail = "Opération impossible."

    def __init__(
        self, detail: str | None = None, code: str | None = None, status_code: int | None = None
    ) -> None:
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=detail, code=code)


def _flatten_codes(codes: Any) -> str:
    if isinstance(codes, str):
        return codes
    if isinstance(codes, list) and codes:
        return _flatten_codes(codes[0])
    if isinstance(codes, dict) and codes:
        return "validation_error"
    return "error"


def problem(
    status_code: int, detail: str, code: str, errors: dict[str, Any] | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": f"{PROBLEM_BASE_URI}{code.replace('_', '-')}",
        "title": _TITLES.get(status_code, "Erreur"),
        "status": status_code,
        "detail": detail,
        "code": code,
    }
    if errors:
        body["errors"] = errors
    return body


def problem_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None or not isinstance(exc, exceptions.APIException):
        return response

    if isinstance(exc, exceptions.ValidationError):
        errors: dict[str, Any] = (
            {str(k): v for k, v in exc.detail.items()}
            if isinstance(exc.detail, dict)
            else {"non_field_errors": exc.detail}
        )
        body = problem(
            response.status_code,
            "Les données envoyées sont invalides.",
            "validation_error",
            errors=errors,
        )
    else:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        body = problem(response.status_code, str(detail), _flatten_codes(exc.get_codes()))

    response.data = body
    response.content_type = PROBLEM_CONTENT_TYPE
    return response
