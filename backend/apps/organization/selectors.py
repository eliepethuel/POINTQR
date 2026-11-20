"""Read-side queries for the organisation (no business rules)."""

from collections import defaultdict
from typing import Any
from uuid import UUID

from django.db.models import Count, Exists, OuterRef, QuerySet

from .models import Agent, Device, OrgUnit, Site


def sites_with_counts() -> QuerySet[Site]:
    return Site.objects.annotate(agent_count=Count("agents")).order_by("name")


def agents_list() -> QuerySet[Agent]:
    active_device = Device.objects.filter(agent=OuterRef("pk"), is_active=True)
    return Agent.objects.select_related("site", "org_unit").annotate(
        has_device=Exists(active_device)
    )


def unit_descendant_ids(unit_id: UUID) -> set[UUID]:
    """The unit and all units below it (a manager sees their whole sub-tree)."""
    children: dict[UUID | None, list[UUID]] = defaultdict(list)
    for uid, parent in OrgUnit.objects.values_list("id", "parent_id"):
        children[parent].append(uid)
    result, stack = set(), [unit_id]
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(children.get(current, []))
    return result


def org_tree() -> list[dict[str, Any]]:
    units = list(OrgUnit.objects.select_related("manager").annotate(agent_count=Count("agents")))
    nodes: dict[UUID, dict[str, Any]] = {
        u.id: {
            "id": u.id,
            "name": u.name,
            "kind": u.kind,
            "manager_name": u.manager.full_name if u.manager else None,
            "agent_count": u.agent_count,
            "children": [],
        }
        for u in units
    }
    roots: list[dict[str, Any]] = []
    for u in units:
        if u.parent_id and u.parent_id in nodes:
            nodes[u.parent_id]["children"].append(nodes[u.id])
        else:
            roots.append(nodes[u.id])
    return roots
