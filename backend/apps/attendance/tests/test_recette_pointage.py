"""Acceptance scenarios R1 to R5 (CDC section 12) plus the other anti-fraud controls."""

import uuid
from datetime import timedelta

import pytest
import time_machine
from django.db import connection, transaction
from django.db.utils import DatabaseError

from apps.attendance import tokens
from apps.attendance.models import CheckIn
from apps.tenancy.context import tenant_context
from common.crypto import decrypt
from tests import factories

from .conftest import HOME_LAT, HOME_LNG, at

pytestmark = pytest.mark.django_db


def test_R1_agent_in_zone_at_0752_is_22_minutes_late(scene):
    moment = at(7, 52)
    with time_machine.travel(moment, tick=False):
        res = scene.scan(moment)
    assert res.status_code == 201, res.content
    body = res.json()
    assert body["result"] == "accepted"
    assert body["direction"] == "in"
    assert body["late_minutes"] == 22
    assert body["message"] == "Retard de 22 min"
    assert len(res.content) < 5_000  # ENF-21: under 5 KB per check-in


def test_R1_bis_on_time_within_tolerance(scene):
    moment = at(7, 39)
    with time_machine.travel(moment, tick=False):
        body = scene.scan(moment).json()
    assert (body["result"], body["message"], body["late_minutes"]) == ("accepted", "À l'heure", 0)


def test_R2_photo_scanned_two_minutes_later_from_home_is_refused(scene):
    shown = at(7, 50)
    with time_machine.travel(shown + timedelta(minutes=2), tick=False):
        body = scene.scan(shown, lat=HOME_LAT, lng=HOME_LNG).json()
    assert body["result"] == "refused"
    assert body["refusal_code"] == "TOKEN_EXPIRED"
    assert {"TOKEN_EXPIRED", "OUT_OF_ZONE"} <= set(body["refusal_details"])
    with tenant_context(scene.company.id):
        anomaly = CheckIn.objects.get(id=body["id"])
        assert anomaly.distance_m > 5_000  # visible to HR in the anomalies log (EF-21)


def test_R3_agent_a_uses_phone_bound_to_agent_b(scene):
    moment = at(7, 40)
    with time_machine.travel(moment, tick=False):
        body = scene.scan(moment, device="phone-kofi").json()
    assert (body["result"], body["refusal_code"]) == ("refused", "DEVICE_MISMATCH")


def test_R4_phone_clock_ahead_is_ignored(scene):
    real = at(7, 35)
    with time_machine.travel(real, tick=False):
        # Even a forged client time field is ignored: only the server clock is read (RG-01).
        body = scene.scan(real, client_time=(real + timedelta(minutes=30)).isoformat()).json()
    assert body["result"] == "accepted"
    assert body["effective_ts"].startswith("2026-11-16T07:35:00")


def test_R5_offline_kiosk_uploads_40_badges_marked_offline(scene):
    agents = [factories.AgentFactory(company=scene.company, site=scene.site) for _ in range(40)]
    outage_start = at(7, 15)
    items = []
    for i, agent in enumerate(agents):
        key = decrypt(agent.badge_key)
        items.append(
            {
                "token": tokens.badge_token(key, agent.id, agent.badge_version),
                "client_uuid": str(uuid.uuid4()),
                "scanned_at": (outage_start + timedelta(minutes=2 * i)).isoformat(),
                "offline": True,
            }
        )
    with time_machine.travel(outage_start + timedelta(hours=2), tick=False):
        res = scene.kiosk_client.post(
            "/api/v1/kiosk/checkins/batch/", {"items": items}, format="json"
        )
        again = scene.kiosk_client.post(
            "/api/v1/kiosk/checkins/batch/", {"items": items}, format="json"
        )
    assert res.status_code == 200, res.content
    assert res.json() == {**res.json(), "received": 40, "accepted": 40}
    assert again.json()["accepted"] == 40  # idempotent re-send, nothing duplicated
    with tenant_context(scene.company.id):
        rows = CheckIn.objects.filter(kiosk=scene.kiosk, offline=True)
        assert rows.count() == 40
        first = rows.order_by("effective_ts").first()
        assert first.effective_ts == outage_start  # kiosk clock kept, marked offline


def test_qr_cannot_be_replayed_by_the_same_phone(scene):
    moment = at(7, 31)
    with time_machine.travel(moment, tick=False):
        first = scene.scan(moment).json()
    with time_machine.travel(moment + timedelta(minutes=3), tick=False):
        token = scene.qr(moment)  # same QR window replayed later from the same phone
        replay = scene.agent_client.post(
            "/api/v1/mobile/checkins/",
            {
                "token": token,
                "device_id": "phone-aya",
                "latitude": 5.3197,
                "longitude": -4.0164,
            },
            format="json",
        ).json()
    assert first["result"] == "accepted"
    assert replay["result"] == "refused"
    assert replay["refusal_code"] in ("TOKEN_EXPIRED", "TOKEN_REPLAYED")


def test_same_qr_window_used_twice_quickly_is_replay(scene):
    moment = at(7, 31, 5)
    with time_machine.travel(moment, tick=False):
        scene.scan(moment)
        second = scene.scan(moment).json()
    assert second["refusal_code"] == "TOKEN_REPLAYED"


def test_two_agents_can_scan_the_same_kiosk_qr(scene):
    moment = at(7, 32)
    with time_machine.travel(moment, tick=False):
        a = scene.scan(moment).json()
        b = scene.scan(moment, device="phone-kofi", client=scene.other_client).json()
    assert a["result"] == b["result"] == "accepted"


def test_RG06_second_scan_within_two_minutes_is_ignored(scene):
    first = at(7, 30)
    with time_machine.travel(first, tick=False):
        scene.scan(first)
    with time_machine.travel(first + timedelta(seconds=70), tick=False):
        body = scene.scan(first + timedelta(seconds=70)).json()
    assert (body["result"], body["refusal_code"]) == ("ignored", "DUPLICATE")


def test_RG07_direction_alternates(scene):
    with time_machine.travel(at(7, 30), tick=False):
        assert scene.scan(at(7, 30)).json()["direction"] == "in"
    with time_machine.travel(at(16, 40), tick=False):
        body = scene.scan(at(16, 40)).json()
    assert (body["direction"], body["message"]) == ("out", "Sortie enregistrée")


def test_out_of_zone_and_mock_location(scene):
    # One QR window per scan: a phone may use a given window only once.
    with time_machine.travel(at(7, 40), tick=False):
        far = scene.scan(at(7, 40), lat=HOME_LAT, lng=HOME_LNG).json()
    with time_machine.travel(at(7, 41), tick=False):
        fake = scene.scan(at(7, 41), mock_location=True).json()
    with time_machine.travel(at(7, 42), tick=False):
        none = scene.scan(at(7, 42), lat=None, lng=None).json()
    assert far["refusal_code"] == "OUT_OF_ZONE"
    assert fake["refusal_code"] == "MOCK_LOCATION"
    assert none["refusal_code"] == "LOCATION_MISSING"


def test_wifi_second_factor_when_enabled(scene):
    scene.company.wifi_check_enabled = True
    scene.company.save()
    with tenant_context(scene.company.id):
        scene.site.allowed_wifi = ["MINX-WIFI"]
        scene.site.save()
    with time_machine.travel(at(7, 40), tick=False):
        refused = scene.scan(at(7, 40)).json()
    with time_machine.travel(at(7, 41), tick=False):
        accepted = scene.scan(at(7, 41), wifi="minx-wifi").json()
    assert refused["refusal_code"] == "WIFI_NOT_ALLOWED"
    assert accepted["result"] == "accepted"


def test_revoked_kiosk_qr_is_refused(scene):
    with tenant_context(scene.company.id):
        from apps.kiosks.services import revoke

        revoke(scene.kiosk, actor=None)
    with time_machine.travel(at(7, 40), tick=False):
        assert scene.scan(at(7, 40)).json()["refusal_code"] == "KIOSK_REVOKED"
    assert (
        scene.kiosk_client.post("/api/v1/kiosk/heartbeat/", {}, format="json").json()["status"]
        == "revoked"
    )


def test_unbound_phone_is_refused(scene):
    agent = factories.AgentFactory(company=scene.company, site=scene.site)
    from apps.accounts.models import Role
    from conftest import client_for

    user = factories.make_user(scene.company, Role.AGENT, agent=agent)
    with time_machine.travel(at(7, 40), tick=False):
        client = client_for(user, mfa=False)
        body = scene.scan(at(7, 40), device="new-phone", client=client).json()
    assert body["refusal_code"] == "DEVICE_NOT_BOUND"


def test_suspended_company_blocks_checkins(scene):
    scene.company.status = "suspended"
    scene.company.save()
    with time_machine.travel(at(7, 40), tick=False):
        res = scene.scan(at(7, 40))
    assert res.status_code == 401  # tokens of a suspended company are rejected outright


def test_mode_b_personal_rotating_qr_scanned_by_kiosk(scene):
    key_res = scene.agent_client.get("/api/v1/mobile/personal-key/", {"device_id": "phone-aya"})
    from common.crypto import b64url_decode

    key = b64url_decode(key_res.json()["key"])
    moment = at(7, 45)
    with time_machine.travel(moment, tick=False):
        token = tokens.personal_token(key, scene.agent.id, tokens.window_of(moment))
        body = scene.kiosk_client.post(
            "/api/v1/kiosk/checkins/", {"token": token}, format="json"
        ).json()
    assert body["result"] == "accepted"
    with tenant_context(scene.company.id):
        assert CheckIn.objects.get(id=body["id"]).mode == "B"


def test_mode_c_reprinted_badge_invalidates_the_old_one(scene, hr_x):
    old = scene.kiosk_client  # noqa: F841 - readability
    old_token = hr_x.get(f"/api/v1/agents/{scene.agent.id}/badge/").json()["token"]
    hr_x.post(f"/api/v1/agents/{scene.agent.id}/rotate-badge/")
    with time_machine.travel(at(7, 40), tick=False):
        body = scene.kiosk_client.post(
            "/api/v1/kiosk/checkins/", {"token": old_token}, format="json"
        ).json()
    assert body["refusal_code"] == "BADGE_REVOKED"


def test_mode_d_printed_site_qr(scene, admin_x):
    token = admin_x.get(f"/api/v1/sites/{scene.site.id}/printed-qr/").json()["token"]
    with time_machine.travel(at(7, 38), tick=False):
        body = scene.agent_client.post(
            "/api/v1/mobile/checkins/",
            {
                "token": token,
                "device_id": "phone-aya",
                "latitude": 5.3197,
                "longitude": -4.0164,
            },
            format="json",
        ).json()
    assert body["result"] == "accepted"
    with tenant_context(scene.company.id):
        row = CheckIn.objects.get(id=body["id"])
        assert (row.mode, row.trust) == ("D", "medium")


def test_checkins_are_append_only_in_the_database(scene):
    with time_machine.travel(at(7, 40), tick=False):
        checkin_id = scene.scan(at(7, 40)).json()["id"]
    for sql in (
        "UPDATE attendance_checkin SET direction = 'out' WHERE id = %s",
        "DELETE FROM attendance_checkin WHERE id = %s",
    ):
        with (
            tenant_context(scene.company.id),
            pytest.raises(DatabaseError),
            transaction.atomic(),
            connection.cursor() as cur,
        ):
            cur.execute(sql, [checkin_id])


def test_hr_sees_anomalies(scene, hr_x):
    with time_machine.travel(at(7, 40), tick=False):
        scene.scan(at(7, 40), lat=HOME_LAT, lng=HOME_LNG)
    with time_machine.travel(at(7, 41), tick=False):
        scene.scan(at(7, 41))
    refused = hr_x.get("/api/v1/checkins/", {"result": "refused"}).json()["results"]
    assert [r["refusal_code"] for r in refused] == ["OUT_OF_ZONE"]
    assert refused[0]["refusal_label"] == "Hors zone"
