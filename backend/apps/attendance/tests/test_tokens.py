from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from apps.attendance import tokens
from apps.attendance.geo import haversine_m

KEY = bytes(range(32))
SITE = UUID("11111111-1111-4111-8111-111111111111")
KIOSK = UUID("22222222-2222-4222-8222-222222222222")
AGENT = UUID("33333333-3333-4333-8333-333333333333")

#: Shared with frontend/src/app/kiosk/qr-token.spec.ts: the tablet (WebCrypto) and the server
#: (Python hmac) must produce the very same token.
VECTOR_KIOSK = (
    "PQR1.11111111-1111-4111-8111-111111111111.22222222-2222-4222-8222-222222222222"
    ".59866666.MkC1r8KnJjqr91esqEC3ZA"
)
VECTOR_PERSONAL = "PQRP.33333333-3333-4333-8333-333333333333.59866666.vkZfWjvmwM4TD5h3UfUw7w"


def test_cross_language_vectors():
    assert tokens.kiosk_token(KEY, SITE, KIOSK, 59866666) == VECTOR_KIOSK
    assert tokens.personal_token(KEY, AGENT, 59866666) == VECTOR_PERSONAL


def test_parse_and_verify_round_trip():
    token = tokens.parse(VECTOR_KIOSK)
    assert (token.kind, token.subject, token.kiosk, token.counter) == (
        "PQR1",
        SITE,
        KIOSK,
        59866666,
    )
    tokens.verify_signature(token, KEY)


def test_tampered_token_is_invalid():
    token = tokens.parse(VECTOR_KIOSK.replace("59866666", "59866667"))
    with pytest.raises(tokens.TokenError) as exc:
        tokens.verify_signature(token, KEY)
    assert exc.value.code == "TOKEN_INVALID"


@pytest.mark.parametrize(
    "raw", ["", "PQR1.x", "PQR1.a.b.c.d", "XXXX.1.2.3", "PQRB.not-a-uuid.1.sig"]
)
def test_malformed_tokens(raw):
    with pytest.raises(tokens.TokenError):
        tokens.parse(raw)


def test_only_current_and_previous_windows_are_fresh():
    now = datetime(2026, 11, 20, 7, 52, 10, tzinfo=UTC)
    current = tokens.window_of(now)
    for window in (current, current - 1):
        tokens.verify_fresh(tokens.parse(tokens.kiosk_token(KEY, SITE, KIOSK, window)), now)
    for window in (current - 2, current + 1, current - 4):  # 2 minutes old = -4 windows (R2)
        with pytest.raises(tokens.TokenError) as exc:
            tokens.verify_fresh(tokens.parse(tokens.kiosk_token(KEY, SITE, KIOSK, window)), now)
        assert exc.value.code == "TOKEN_EXPIRED"


def test_window_is_thirty_seconds():
    t0 = datetime(2026, 11, 20, 7, 0, 0, tzinfo=UTC)
    assert tokens.window_of(t0 + timedelta(seconds=29)) == tokens.window_of(t0)
    assert tokens.window_of(t0 + timedelta(seconds=30)) == tokens.window_of(t0) + 1


def test_personal_key_depends_on_the_phone():
    assert tokens.derive_personal_key(KEY, "phone-a") != tokens.derive_personal_key(KEY, "phone-b")


def test_haversine_plateau_to_cocody():
    distance = haversine_m(5.3197, -4.0164, 5.3600, -3.9900)
    assert 5_000 < distance < 5_600
    assert haversine_m(5.3197, -4.0164, 5.3197, -4.0164) == 0
