"""Smoke test of the containerised stack (CI job `docker`): python3 smoke-docker.py <base-url>."""

import base64
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1].rstrip("/")
failures: list[str] = []


def get(path: str, data: bytes | None = None) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def check(label: str, ok: bool) -> None:
    print(("ok   " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


status, _, body = get("/api/v1/health/")
health = json.loads(body)
check(
    "health: database and cache up",
    status == 200 and health["database"] and health["cache"],
)

status, headers, body = get("/")
html = body.decode()
check("landing page served", status == 200 and "<pq-root" in html)
csp = headers.get("Content-Security-Policy", "")
inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>", html)
hashes = [
    "'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
    for s in inline
]
check(
    "CSP allows exactly the inline scripts of index.html", all(h in csp for h in hashes)
)
check("frame and sniffing protections", headers.get("X-Frame-Options") == "DENY")

status, _, body = get("/kiosk")
check("SPA fallback for deep links", status == 200 and b"<pq-root" in body)

status, headers, body = get(
    "/api/v1/auth/login/",
    json.dumps({"company_code": "NONE", "username": "nobody", "password": "x"}).encode(),
)
check(
    "bad login answers a 4xx problem document",
    400 <= status < 500 and "problem+json" in headers.get("Content-Type", ""),
)

status, _, body = get("/api/schema/")
check("OpenAPI schema served", status == 200 and b"openapi" in body[:200])

if failures:
    sys.exit(f"{len(failures)} smoke check(s) failed")
