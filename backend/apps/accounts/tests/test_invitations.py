"""EF-09: HR invites agents, the agent activates their access from the link, then binds a phone."""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
import time_machine
from django.core import mail
from django.utils import timezone

from apps.accounts.models import ActivationInvite, Role, User
from apps.audit.models import AuditLog
from apps.tenancy.context import tenant_context
from tests import factories

pytestmark = pytest.mark.django_db
PASSWORD = "Un-mot-de-passe-solide-2026"


def _token(link: str) -> str:
    return parse_qs(urlparse(link).query)["jeton"][0]


@pytest.fixture
def agent(company_x):
    return factories.AgentFactory(
        company=company_x, employee_number="MX0042", first_names="Aya", email="aya@example.ci"
    )


def test_invite_creates_the_account_and_emails_a_single_use_link(
    company_x, hr_x, agent, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        res = hr_x.post(f"/api/v1/agents/{agent.id}/invite/")
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["username"] == "mx0042"
    assert body["sent_to"] == "aya@example.ci"
    assert "/activation?entreprise=MINX&jeton=" in body["link"]
    assert len(mail.outbox) == 1 and body["link"] in mail.outbox[0].body
    assert "mx0042" in mail.outbox[0].body
    with tenant_context(company_x.id):
        user = User.objects.get(agent=agent)
        assert user.roles == [Role.AGENT] and not user.has_usable_password()
        # Only the hash of the token is stored.
        invite = ActivationInvite.objects.get(user=user)
        assert _token(body["link"]) not in invite.token_hash
        assert AuditLog.objects.filter(action="agent.invited").exists()
    listed = hr_x.get(f"/api/v1/agents/{agent.id}/").json()
    assert listed["account"] == "invited"


def test_agent_activates_with_the_link_and_is_signed_in(company_x, hr_x, agent, client):
    link = hr_x.post(f"/api/v1/agents/{agent.id}/invite/").json()["link"]
    token = _token(link)
    info = client.get("/api/v1/auth/activation/", {"entreprise": "MINX", "jeton": token})
    assert info.status_code == 200
    assert info.json() == {"first_name": "Aya", "username": "mx0042", "company": "Ministère X"}

    res = client.post(
        "/api/v1/auth/activation/",
        {"company_code": "MINX", "token": token, "password": PASSWORD},
        content_type="application/json",
    )
    assert res.status_code == 200, res.content
    assert res.json()["step"] == "authenticated" and res.json()["access"]
    assert hr_x.get(f"/api/v1/agents/{agent.id}/").json()["account"] == "active"
    # The link cannot be used twice, and the password now works on the normal sign-in.
    again = client.post(
        "/api/v1/auth/activation/",
        {"company_code": "MINX", "token": token, "password": PASSWORD},
        content_type="application/json",
    )
    assert again.status_code == 400 and again.json()["code"] == "activation_invalid"
    login = client.post(
        "/api/v1/auth/login/",
        {"company_code": "MINX", "username": "mx0042", "password": PASSWORD},
        content_type="application/json",
    )
    assert login.json()["step"] == "authenticated"


def test_weak_password_is_refused_and_the_link_stays_valid(hr_x, agent, client):
    token = _token(hr_x.post(f"/api/v1/agents/{agent.id}/invite/").json()["link"])
    res = client.post(
        "/api/v1/auth/activation/",
        {"company_code": "MINX", "token": token, "password": "123"},
        content_type="application/json",
    )
    assert res.status_code == 400 and res.json()["code"] == "weak_password"
    ok = client.get("/api/v1/auth/activation/", {"entreprise": "MINX", "jeton": token})
    assert ok.status_code == 200


def test_expired_or_replaced_links_are_refused(hr_x, agent, client):
    first = _token(hr_x.post(f"/api/v1/agents/{agent.id}/invite/").json()["link"])
    second = _token(hr_x.post(f"/api/v1/agents/{agent.id}/invite/").json()["link"])
    replaced = client.get("/api/v1/auth/activation/", {"entreprise": "MINX", "jeton": first})
    assert replaced.status_code == 400
    with time_machine.travel(timezone.now() + timedelta(days=8)):
        expired = client.get("/api/v1/auth/activation/", {"entreprise": "MINX", "jeton": second})
    assert expired.status_code == 400 and expired.json()["code"] == "activation_invalid"


def test_a_link_of_another_company_is_useless(company_y, hr_x, agent, client):
    token = _token(hr_x.post(f"/api/v1/agents/{agent.id}/invite/").json()["link"])
    res = client.get("/api/v1/auth/activation/", {"entreprise": "PMEY", "jeton": token})
    assert res.status_code == 400


def test_an_active_account_is_not_invited_again(hr_x, agent, client):
    token = _token(hr_x.post(f"/api/v1/agents/{agent.id}/invite/").json()["link"])
    client.post(
        "/api/v1/auth/activation/",
        {"company_code": "MINX", "token": token, "password": PASSWORD},
        content_type="application/json",
    )
    res = hr_x.post(f"/api/v1/agents/{agent.id}/invite/")
    assert res.status_code == 409 and res.json()["code"] == "already_active"


def test_invite_all_skips_active_and_pending_accounts(company_x, hr_x, agent, client):
    factories.AgentFactory(company=company_x, employee_number="MX0100", email="")
    factories.AgentFactory(company=company_x, employee_number="MX0101", email="b@example.ci")
    factories.AgentFactory(company=company_x, employee_number="MX0102", status="inactive")
    hr_x.post(f"/api/v1/agents/{agent.id}/invite/")  # already pending
    res = hr_x.post("/api/v1/agents/invite-all/")
    assert res.status_code == 200
    assert res.json() == {"invited": 2, "emailed": 1, "without_email": 1, "skipped": 1}
    assert hr_x.post("/api/v1/agents/invite-all/").json()["invited"] == 0


def test_only_hr_and_admin_can_invite(company_x, make_client, agent):
    manager = make_client(company_x, Role.MANAGER)
    assert manager.post(f"/api/v1/agents/{agent.id}/invite/").status_code == 403
