"""WebSocket ``/ws/dashboard/?token=<access JWT>``: live events for one company and the manager's
scope only (checkin.accepted, checkin.refused, kiosk.status, request.created)."""

from typing import Any
from urllib.parse import parse_qs
from uuid import UUID

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .events import company_group, unit_group

STAFF = {"company_admin", "hr", "manager", "auditor"}
WIDE = {"company_admin", "hr", "auditor"}


@database_sync_to_async
def _scope_for(user_id: str, company_id: str) -> list[str] | None:
    from apps.accounts.models import User
    from apps.organization.selectors import unit_descendant_ids
    from apps.tenancy.context import tenant_context
    from apps.tenancy.models import Company

    with tenant_context(company_id):
        company = Company.objects.filter(id=company_id, status=Company.Status.ACTIVE).first()
        user = User.objects.filter(id=user_id, is_active=True, company_id=company_id).first()
        if company is None or user is None or not set(user.roles) & STAFF:
            return None
        if set(user.roles) & WIDE:
            return [company_group(company_id)]
        units: set[UUID] = set()
        if user.agent is not None:
            for unit in user.agent.managed_units.all():
                units |= unit_descendant_ids(unit.id)
        return [unit_group(u) for u in units]


class DashboardConsumer(AsyncJsonWebsocketConsumer):
    groups_joined: list[str]

    async def connect(self) -> None:
        self.groups_joined = []
        query = parse_qs(self.scope.get("query_string", b"").decode())
        raw = (query.get("token") or [""])[0]
        try:
            token = AccessToken(raw)
        except TokenError:
            await self.close(code=4401)
            return
        company_id = token.get("company_id")
        if not company_id:
            await self.close(code=4403)
            return
        groups = await _scope_for(str(token["user_id"]), str(company_id))
        if groups is None:
            await self.close(code=4403)
            return
        for group in groups:
            await self.channel_layer.group_add(group, self.channel_name)
        self.groups_joined = groups
        await self.accept()
        await self.send_json({"event": "hello", "payload": {"groups": len(groups)}})

    async def disconnect(self, code: int) -> None:
        for group in getattr(self, "groups_joined", []):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def dashboard_event(self, message: dict[str, Any]) -> None:
        await self.send_json({"event": message["event"], "payload": message["payload"]})
