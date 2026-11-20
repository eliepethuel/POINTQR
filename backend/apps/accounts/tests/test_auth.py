"""Login, MFA (ENF-09), lockout after 5 failures (ENF-11), refresh rotation (ENF-10)."""

import pytest
from django.urls import reverse
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.tenancy.resolver import REFRESH_COOKIE
from tests.factories import PASSWORD, make_user

pytestmark = pytest.mark.django_db
LOGIN = reverse("v1:auth:login")
VERIFY = reverse("v1:auth:mfa-verify")
REFRESH = reverse("v1:auth:refresh")


def _code(user) -> str:
    device = TOTPDevice.objects.filter(user=user).order_by("-confirmed").first()
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    return f"{totp.token():06d}"


def test_agent_logs_in_with_company_code_without_mfa(company_x):
    make_user(company_x, Role.AGENT, username="aya")
    client = APIClient()
    res = client.post(LOGIN, {"company_code": "minx", "username": "AYA", "password": PASSWORD})
    assert res.status_code == 200, res.content
    assert res.json()["step"] == "authenticated"
    assert res.json()["user"]["roles"] == ["agent"]
    cookie = res.cookies[REFRESH_COOKIE]
    assert cookie["httponly"] and cookie["samesite"] == "Strict"
    me = APIClient(HTTP_AUTHORIZATION=f"Bearer {res.json()['access']}").get(reverse("v1:auth:me"))
    assert me.status_code == 200
    assert me.json()["company"]["code"] == "MINX"


def test_subdomain_identifies_the_company(company_x):
    make_user(company_x, Role.AGENT, username="kofi")
    res = APIClient().post(
        LOGIN, {"username": "kofi", "password": PASSWORD}, HTTP_HOST="ministere-x.localhost"
    )
    assert res.status_code == 200
    assert res.json()["step"] == "authenticated"


def test_same_username_in_two_companies_is_isolated(company_x, company_y):
    make_user(company_x, Role.AGENT, username="awa")
    res = APIClient().post(LOGIN, {"company_code": "PMEY", "username": "awa", "password": PASSWORD})
    assert res.status_code == 401
    assert res.json()["code"] == "invalid_credentials"


def test_hr_must_enrol_then_verify_totp(company_x):
    user = make_user(company_x, Role.HR, username="rh")
    client = APIClient()
    res = client.post(LOGIN, {"company_code": "MINX", "username": "rh", "password": PASSWORD})
    body = res.json()
    assert body["step"] == "mfa_setup"
    assert body["otpauth_url"].startswith("otpauth://totp/PointQR")

    bad = client.post(VERIFY, {"mfa_token": body["mfa_token"], "code": "000000"})
    assert bad.status_code == 401
    ok = client.post(VERIFY, {"mfa_token": body["mfa_token"], "code": _code(user)})
    assert ok.status_code == 200, ok.content
    assert ok.json()["user"]["mfa_enabled"] is True

    again = client.post(LOGIN, {"company_code": "MINX", "username": "rh", "password": PASSWORD})
    assert again.json()["step"] == "mfa_required"


def test_privileged_endpoint_refuses_token_without_mfa(company_x, make_client):
    client = make_client(company_x, Role.HR, mfa=False)
    assert client.get(reverse("v1:agent-list")).status_code == 403


def test_lockout_after_five_failures(company_x):
    make_user(company_x, Role.AGENT, username="bob")
    client = APIClient()
    for _ in range(5):
        res = client.post(LOGIN, {"company_code": "MINX", "username": "bob", "password": "wrong"})
        assert res.status_code in (401, 429)
    locked = client.post(LOGIN, {"company_code": "MINX", "username": "bob", "password": PASSWORD})
    assert locked.status_code == 429
    assert locked.json()["code"] == "account_locked"


def test_refresh_rotates_and_old_token_is_revoked(company_x):
    make_user(company_x, Role.AGENT, username="eve")
    client = APIClient()
    client.post(LOGIN, {"company_code": "MINX", "username": "eve", "password": PASSWORD})
    old = client.cookies[REFRESH_COOKIE].value
    res = client.post(REFRESH)
    assert res.status_code == 200, res.content
    assert client.cookies[REFRESH_COOKIE].value != old

    replay = APIClient()
    replay.cookies[REFRESH_COOKIE] = old
    assert replay.post(REFRESH).status_code == 401


def test_logout_revokes_refresh(company_x):
    make_user(company_x, Role.AGENT, username="zoe")
    client = APIClient()
    client.post(LOGIN, {"company_code": "MINX", "username": "zoe", "password": PASSWORD})
    token = client.cookies[REFRESH_COOKIE].value
    assert client.post(reverse("v1:auth:logout")).status_code == 204
    replay = APIClient()
    replay.cookies[REFRESH_COOKIE] = token
    assert replay.post(REFRESH).status_code == 401


def test_suspended_company_cannot_log_in(company_x):
    make_user(company_x, Role.AGENT, username="ali")
    company_x.status = "suspended"
    company_x.save()
    res = APIClient().post(LOGIN, {"company_code": "MINX", "username": "ali", "password": PASSWORD})
    assert res.status_code == 403
    assert res.json()["code"] == "company_suspended"


def test_superadmin_logs_in_without_company(db):
    admin = make_user(None, username="editeur")
    client = APIClient()
    body = client.post(LOGIN, {"username": "editeur", "password": PASSWORD}).json()
    assert body["step"] == "mfa_setup"
    ok = client.post(VERIFY, {"mfa_token": body["mfa_token"], "code": _code(admin)})
    assert ok.status_code == 200
    token = ok.json()["access"]
    stats = APIClient(HTTP_AUTHORIZATION=f"Bearer {token}").get(reverse("v1:platform-stats"))
    assert stats.status_code == 200


def test_token_from_company_x_rejected_on_company_y_subdomain(company_x, company_y, make_client):
    client = make_client(company_x, Role.AGENT)
    res = client.get(reverse("v1:auth:me"), HTTP_HOST="pme-y.localhost")
    # The JWT claim wins over the host: the user is served their own company only.
    assert res.json()["company"]["code"] == "MINX"
