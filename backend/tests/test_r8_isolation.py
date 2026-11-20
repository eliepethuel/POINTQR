"""R8 / ENF-07 — a user of company X asking for an object of company Y gets 404, on every route.

The test walks the URL resolver: every detail route (``<pk>``) and every list route is called with
company X credentials while the only object exists in company Y. A new endpoint without a factory
below makes the test fail, so isolation coverage cannot silently fall behind.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.tenancy.models import Company, Subscription
from tests import factories

pytestmark = pytest.mark.django_db

PRIVILEGED_ROLES = (Role.COMPANY_ADMIN, Role.HR, Role.MANAGER, Role.AUDITOR, Role.AGENT)

#: Models served by platform-only routes (super-admin console), out of the tenant scope.
PLATFORM_MODELS = {Company, Subscription}


def _factories() -> dict[type, Callable[[Company], Any]]:
    from tests import registry

    return registry.FACTORIES


def _walk(patterns: list[Any], prefix: str = "") -> Iterator[tuple[str, Any]]:
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p


def _api_routes() -> list[tuple[str, Any, type]]:
    routes = []
    for route, pattern in _walk(get_resolver().url_patterns):
        view_cls = getattr(pattern.callback, "cls", None)
        queryset = getattr(view_cls, "queryset", None)
        if not route.startswith("api/v1/") or queryset is None:
            continue
        routes.append((route, pattern, queryset.model))
    return routes


def _detail_url(route: str, pk: Any) -> str | None:
    if "<pk>" not in route and "(?P<pk>" not in route:
        return None
    if any(t in route for t in ("\\.(?P<format>", ".(?P<format>")):
        return None
    url = route.replace("(?P<pk>[^/.]+)", str(pk)).replace("<pk>", str(pk))
    url = url.replace("^", "").replace("$", "")
    return "/" + url if "(?P" not in url and "<" not in url else None


def test_every_tenant_model_has_an_isolation_factory():
    models = {model for _, _, model in _api_routes()} - PLATFORM_MODELS - {User}
    missing = [m.__name__ for m in models if m not in _factories()]
    assert not missing, f"Add a factory to tests/registry.py for: {missing}"


def test_r8_no_route_returns_another_company_object(company_x, company_y):
    user = factories.make_user(company_x, *PRIVILEGED_ROLES, username="curieux")
    client = APIClient()
    from apps.accounts.tokens import issue_tokens

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user, mfa=True).access}")

    checked = 0
    for route, _pattern, model in _api_routes():
        if model in PLATFORM_MODELS:
            continue
        if model is User:
            foreign = factories.make_user(company_y, Role.AGENT)
        else:
            foreign = _factories()[model](company_y)
        url = _detail_url(route, foreign.pk)
        if url is None:
            clean = route.replace("^", "").replace("$", "")
            if "<" in clean or "(?P" in clean:
                continue
            # List route: the foreign object must not appear anywhere in the payload.
            res = client.get("/" + clean)
            assert str(foreign.pk) not in res.content.decode(errors="ignore"), f"leak on {route}"
            checked += 1
            continue
        for method in ("get", "patch", "put", "delete", "post"):
            res = getattr(client, method)(url, {}, format="json")
            assert res.status_code in (403, 404, 405), (
                f"{method.upper()} {url} returned {res.status_code} for a foreign object"
            )
            if res.status_code not in (403, 405):
                checked += 1
    assert checked > 20, "the isolation test did not exercise enough routes"


def test_platform_routes_refuse_company_users(company_x):
    client = APIClient()
    user = factories.make_user(company_x, *PRIVILEGED_ROLES, username="pirate")
    from apps.accounts.tokens import issue_tokens

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user, mfa=True).access}")
    for url in (
        "/api/v1/platform/companies/",
        "/api/v1/platform/stats/",
        "/api/v1/platform/subscriptions/",
    ):
        assert client.get(url).status_code == 403
