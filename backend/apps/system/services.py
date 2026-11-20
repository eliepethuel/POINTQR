"""Platform health checks and server clock (kiosks resynchronise their clock from it, RG-01)."""

from dataclasses import dataclass
from datetime import datetime

import redis
from django.conf import settings
from django.db import connection
from django.utils import timezone


@dataclass(frozen=True, slots=True)
class HealthReport:
    status: str
    version: str
    server_time: datetime
    epoch_ms: int
    database: bool
    cache: bool


def _database_ok() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row: tuple[int, ...] | None = cursor.fetchone()
            return row == (1,)
    except Exception:
        return False


def _cache_ok() -> bool:
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=0.5)
        return bool(client.ping())
    except redis.RedisError:
        return False


def server_now() -> datetime:
    return timezone.now()


def health_report() -> HealthReport:
    now = server_now()
    database = _database_ok()
    cache = _cache_ok()
    return HealthReport(
        status="ok" if database and cache else "degraded",
        version=settings.APP_VERSION,
        server_time=now,
        epoch_ms=int(now.timestamp() * 1000),
        database=database,
        cache=cache,
    )
