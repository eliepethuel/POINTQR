from django.http import Http404
from rest_framework import exceptions

from common.exceptions import DomainError, problem_exception_handler


def test_not_found_becomes_problem_details():
    response = problem_exception_handler(Http404(), {})
    assert response is not None
    assert response.status_code == 404
    assert response.data["code"] == "not_found"
    assert response.data["type"].endswith("/not-found")
    assert set(response.data) == {"type", "title", "status", "detail", "code"}


def test_validation_error_lists_field_errors():
    exc = exceptions.ValidationError({"email": ["Adresse invalide."]})
    response = problem_exception_handler(exc, {})
    assert response is not None
    assert response.status_code == 400
    assert response.data["code"] == "validation_error"
    assert response.data["errors"]["email"] == ["Adresse invalide."]


def test_domain_error_keeps_business_code():
    exc = DomainError("QR expiré.", code="token_expired")
    response = problem_exception_handler(exc, {})
    assert response is not None
    assert response.status_code == 422
    assert response.data["code"] == "token_expired"
    assert response.data["detail"] == "QR expiré."


def test_problem_content_type():
    response = problem_exception_handler(exceptions.NotAuthenticated(), {})
    assert response is not None
    assert response.content_type == "application/problem+json"
