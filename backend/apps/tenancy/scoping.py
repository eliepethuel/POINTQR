"""Helpers so Celery tasks run inside a tenant context (same RLS mechanism as requests)."""

from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from .context import tenant_context
from .models import Company

P = ParamSpec("P")
R = TypeVar("R")


def for_each_active_company[R](fn: Callable[[Company], R]) -> list[R]:
    """Run ``fn`` once per active company, each time in that company's tenant context."""
    results = []
    for company in Company.objects.filter(status=Company.Status.ACTIVE):
        with tenant_context(company.id):
            results.append(fn(company))
    return results


def in_tenant[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Decorate a task whose first argument is ``company_id``."""

    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        company_id: Any = kwargs.get("company_id", args[0] if args else None)
        with tenant_context(company_id):
            return fn(*args, **kwargs)

    return wrapper
