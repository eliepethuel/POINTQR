import pytest
from rest_framework.test import APIClient

from apps.kiosks.models import Kiosk
from apps.tenancy.context import tenant_context
from tests import factories

pytestmark = pytest.mark.django_db


def _pair(company, admin_client, site):
    res = admin_client.post(
        "/api/v1/kiosks/pairing-codes/", {"site": str(site.id), "name": "Hall"}, format="json"
    )
    assert res.status_code == 201, res.content
    code = res.json()["code"]
    assert len(code) == 6 and code.isdigit()
    return APIClient(HTTP_X_COMPANY_CODE=company.code).post(
        "/api/v1/kiosk/pair/", {"code": code}, format="json"
    )


def test_pairing_returns_identity_key_and_token_once(company_x, admin_x):
    site = factories.SiteFactory(company=company_x)
    res = _pair(company_x, admin_x, site)
    assert res.status_code == 201, res.content
    body = res.json()
    assert body["site"]["id"] == str(site.id)
    assert len(body["secret"]) == 43  # 32 bytes, base64url without padding
    with tenant_context(company_x.id):
        kiosk = Kiosk.objects.get(id=body["kiosk_id"])
        assert body["secret"] not in kiosk.secret_key  # encrypted at rest (ENF-08)
    code_reuse = APIClient(HTTP_X_COMPANY_CODE="MINX").post(
        "/api/v1/kiosk/pair/", {"code": "000000"}, format="json"
    )
    assert code_reuse.status_code == 400


def test_heartbeat_resyncs_clock_and_delivers_rotated_key(company_x, admin_x):
    site = factories.SiteFactory(company=company_x)
    body = _pair(company_x, admin_x, site).json()
    machine = APIClient(HTTP_AUTHORIZATION=f"Kiosk {body['token']}", HTTP_X_COMPANY_CODE="MINX")
    beat = machine.post(
        "/api/v1/kiosk/heartbeat/", {"key_version": 1, "pending": 3}, format="json"
    ).json()
    assert "secret" not in beat and beat["epoch_ms"] > 0
    admin_x.post(f"/api/v1/kiosks/{body['kiosk_id']}/rotate-key/")
    beat = machine.post(
        "/api/v1/kiosk/heartbeat/", {"key_version": 1, "pending": 3}, format="json"
    ).json()
    assert beat["key_version"] == 2 and beat["secret"] != body["secret"]
    listed = admin_x.get("/api/v1/kiosks/").json()["results"][0]
    assert listed["online"] is True and listed["pending_offline"] == 3


def test_bad_machine_token_is_rejected(company_x, admin_x):
    site = factories.SiteFactory(company=company_x)
    body = _pair(company_x, admin_x, site).json()
    forged = APIClient(
        HTTP_AUTHORIZATION=f"Kiosk {body['kiosk_id']}.forged", HTTP_X_COMPANY_CODE="MINX"
    )
    assert forged.post("/api/v1/kiosk/heartbeat/", {}, format="json").status_code == 401


def test_kiosk_of_company_x_is_unknown_in_company_y(company_x, company_y, admin_x):
    site = factories.SiteFactory(company=company_x)
    body = _pair(company_x, admin_x, site).json()
    wrong_tenant = APIClient(
        HTTP_AUTHORIZATION=f"Kiosk {body['token']}", HTTP_X_COMPANY_CODE="PMEY"
    )
    assert wrong_tenant.post("/api/v1/kiosk/heartbeat/", {}, format="json").status_code == 401


def test_subscription_limits_kiosks(company_x, admin_x):
    sub = company_x.subscriptions.first()
    sub.max_kiosks = 1
    sub.save()
    site = factories.SiteFactory(company=company_x)
    assert _pair(company_x, admin_x, site).status_code == 201
    res = admin_x.post(
        "/api/v1/kiosks/pairing-codes/", {"site": str(site.id), "name": "Deux"}, format="json"
    )
    assert res.status_code == 402
    assert res.json()["code"] == "quota_exceeded"
