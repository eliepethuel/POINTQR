"""django-axes lockout answer in the API error format (RFC 7807) instead of an HTML page."""

from typing import Any

from django.http import HttpRequest, JsonResponse

from common.exceptions import PROBLEM_CONTENT_TYPE, problem


def lockout_response(
    request: HttpRequest, original_response: Any = None, credentials: Any = None
) -> JsonResponse:
    body = problem(
        429, "Compte bloqué après 5 échecs. Réessayez dans 15 minutes.", "account_locked"
    )
    return JsonResponse(body, status=429, content_type=PROBLEM_CONTENT_TYPE)
