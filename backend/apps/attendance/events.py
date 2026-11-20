"""Real-time events pushed to dashboards (WebSocket groups), sent after the transaction commits."""

import logging
from typing import Any
from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

logger = logging.getLogger(__name__)


def company_group(company_id: UUID | str) -> str:
    return f"company.{company_id}"


def unit_group(unit_id: UUID | str) -> str:
    return f"unit.{unit_id}"


def publish(
    company_id: UUID | str, event: str, payload: dict[str, Any], unit_id: UUID | str | None = None
) -> None:
    """``event`` ∈ checkin.accepted | checkin.refused | kiosk.status | request.created."""

    def send() -> None:
        layer = get_channel_layer()
        if layer is None:
            return
        message = {"type": "dashboard.event", "event": event, "payload": payload}
        try:
            async_to_sync(layer.group_send)(company_group(company_id), message)
            if unit_id:
                async_to_sync(layer.group_send)(unit_group(unit_id), message)
        except Exception:  # real time is best effort: never fail a check-in because of it
            logger.warning("Real-time event %s could not be delivered", event, exc_info=True)

    transaction.on_commit(send)
