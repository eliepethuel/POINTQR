"""Project-wide pytest fixtures: two isolated companies and authenticated clients per role."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.tokens import issue_tokens
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Company
from tests import factories


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def company_x(db: Any) -> Company:
    return factories.CompanyFactory(legal_name="Ministère X", slug="ministere-x", code="MINX")


@pytest.fixture
def company_y(db: Any) -> Company:
    return factories.CompanyFactory(legal_name="PME Y", slug="pme-y", code="PMEY")


@pytest.fixture
def in_tenant() -> Callable[[Company], Any]:
    return lambda company: tenant_context(company.id)


def client_for(user: User, *, mfa: bool = True) -> APIClient:
    client = APIClient()
    tokens = issue_tokens(user, mfa=mfa)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.access}")
    return client


@pytest.fixture
def make_client() -> Callable[..., APIClient]:
    def _make(company: Company | None, *roles: str, mfa: bool = True, **kwargs: Any) -> APIClient:
        user = factories.make_user(company, *roles, **kwargs)
        return client_for(user, mfa=mfa)

    return _make


@pytest.fixture
def admin_x(company_x: Company, make_client: Callable[..., APIClient]) -> APIClient:
    return make_client(company_x, Role.COMPANY_ADMIN)


@pytest.fixture
def hr_x(company_x: Company, make_client: Callable[..., APIClient]) -> APIClient:
    return make_client(company_x, Role.HR)
