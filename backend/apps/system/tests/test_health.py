from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_returns_server_clock():
    response = APIClient().get(reverse("v1:health"))
    assert response.status_code == 200
    body = response.json()
    assert body["database"] is True
    assert body["version"]
    server_time = body["epoch_ms"] / 1000
    assert abs(server_time - timezone.now().timestamp()) < timedelta(seconds=5).total_seconds()


@pytest.mark.django_db
def test_health_reports_degraded_when_cache_down(monkeypatch):
    monkeypatch.setattr("apps.system.services._cache_ok", lambda: False)
    body = APIClient().get(reverse("v1:health")).json()
    assert body["status"] == "degraded"
    assert body["cache"] is False


@pytest.mark.django_db
def test_schema_is_served(client):
    response = client.get(reverse("schema"))
    assert response.status_code == 200
    assert b"/api/v1/health/" in response.content
