"""QR tokens (ADR-0005). HMAC-SHA256, 30-second windows, verified without the kiosk being online.

Formats (``sig`` = base64url of the first 16 bytes of HMAC-SHA256(key, message)):

- ``PQR1.<site>.<kiosk>.<window>.<sig>``  dynamic kiosk QR, message ``PQR1|site|kiosk|window`` (A)
- ``PQRP.<agent>.<window>.<sig>``         rotating personal QR shown by the app (B)
- ``PQRB.<agent>.<version>.<sig>``        printed badge (C)
- ``PQRS.<site>.<version>.<sig>``         printed site QR, no kiosk (D)
"""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from common.crypto import b64url

WINDOW_SECONDS = 30
SIGNATURE_BYTES = 16


class TokenError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ParsedToken:
    kind: str  # PQR1 | PQRP | PQRB | PQRS
    subject: UUID  # site (PQR1, PQRS) or agent (PQRP, PQRB)
    kiosk: UUID | None
    counter: int  # window (PQR1, PQRP) or version (PQRB, PQRS)
    signature: str

    @property
    def message(self) -> str:
        if self.kind == "PQR1":
            return f"PQR1|{self.subject}|{self.kiosk}|{self.counter}"
        return f"{self.kind}|{self.subject}|{self.counter}"


def window_of(moment: datetime) -> int:
    return int(moment.timestamp()) // WINDOW_SECONDS


def signature(key: bytes, message: str) -> str:
    return b64url(hmac.new(key, message.encode(), hashlib.sha256).digest()[:SIGNATURE_BYTES])


def kiosk_token(key: bytes, site: UUID, kiosk: UUID, window: int) -> str:
    return f"PQR1.{site}.{kiosk}.{window}.{signature(key, f'PQR1|{site}|{kiosk}|{window}')}"


def personal_token(key: bytes, agent: UUID, window: int) -> str:
    return f"PQRP.{agent}.{window}.{signature(key, f'PQRP|{agent}|{window}')}"


def badge_token(key: bytes, agent: UUID, version: int) -> str:
    return f"PQRB.{agent}.{version}.{signature(key, f'PQRB|{agent}|{version}')}"


def site_token(key: bytes, site: UUID, version: int) -> str:
    return f"PQRS.{site}.{version}.{signature(key, f'PQRS|{site}|{version}')}"


def parse(raw: str) -> ParsedToken:
    parts = raw.strip().split(".")
    try:
        if parts[0] == "PQR1" and len(parts) == 5:
            return ParsedToken("PQR1", UUID(parts[1]), UUID(parts[2]), int(parts[3]), parts[4])
        if parts[0] in {"PQRP", "PQRB", "PQRS"} and len(parts) == 4:
            return ParsedToken(parts[0], UUID(parts[1]), None, int(parts[2]), parts[3])
    except ValueError:
        pass
    raise TokenError("TOKEN_INVALID")


def verify_signature(token: ParsedToken, key: bytes) -> None:
    if not hmac.compare_digest(signature(key, token.message), token.signature):
        raise TokenError("TOKEN_INVALID")


def verify_fresh(token: ParsedToken, at: datetime) -> None:
    """Accept the current window and the previous one (clock drift), nothing else (ADR-0005)."""
    current = window_of(at)
    if token.counter not in (current, current - 1):
        raise TokenError("TOKEN_EXPIRED")


def derive_personal_key(badge_key: bytes, device_fingerprint_hash: str) -> bytes:
    """Mode B key bound to the agent's phone: a copy on another phone is useless after rebinding."""
    return hmac.new(badge_key, f"PQRP|{device_fingerprint_hash}".encode(), hashlib.sha256).digest()
