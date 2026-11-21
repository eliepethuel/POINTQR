"""R10 load test: 2,000 check-ins per minute, 95 % answered in under 500 ms.

    uv run python manage.py prepare_loadtest --agents 300      # from backend/
    uv run locust -f ../infra/locust/locustfile.py --host http://127.0.0.1:8000 \
        --headless -u 300 -r 50 -t 3m --csv ../infra/locust/r10

Each simulated phone scans the live kiosk QR (signed exactly like the kiosk does) every
~9 s, so 300 users give ~2,000 check-ins per minute. The run fails (exit code 1) when the
p95 exceeds 500 ms or more than 1 % of requests error.
"""

import base64
import hashlib
import hmac
import itertools
import json
import os
import random
import time
from pathlib import Path

from locust import HttpUser, between, events, task

DATA = json.loads(
    Path(
        os.environ.get("LOADTEST_DATA", Path(__file__).with_name(".loadtest.json"))
    ).read_text(encoding="utf-8")
)
KEY = base64.urlsafe_b64decode(DATA["kiosk_key"] + "=" * (-len(DATA["kiosk_key"]) % 4))
AGENTS = itertools.cycle(DATA["agents"])
WINDOW_SECONDS = 30


def kiosk_token(now: float) -> str:
    window = int(now) // WINDOW_SECONDS
    message = f"PQR1|{DATA['site_id']}|{DATA['kiosk_id']}|{window}"
    sig = hmac.new(KEY, message.encode(), hashlib.sha256).digest()[:16]
    encoded = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"PQR1.{DATA['site_id']}.{DATA['kiosk_id']}.{window}.{encoded}"


class Phone(HttpUser):
    wait_time = between(7, 11)

    def on_start(self) -> None:
        agent = next(AGENTS)
        self.device_id = agent["device_id"]
        self.client.headers.update(
            {
                "Authorization": f"Bearer {agent['access']}",
                "X-Company-Code": DATA["company_code"],
            }
        )

    @task
    def check_in(self) -> None:
        jitter = random.uniform(-0.0004, 0.0004)
        with self.client.post(
            "/api/v1/mobile/checkins/",
            json={
                "token": kiosk_token(time.time()),
                "device_id": self.device_id,
                "latitude": DATA["latitude"] + jitter,
                "longitude": DATA["longitude"] + jitter,
                "accuracy_m": 15,
            },
            name="POST /mobile/checkins/",
            catch_response=True,
        ) as response:
            # Accepted (201) or business refusal / duplicate (200) are both correct answers.
            if response.status_code in (200, 201):
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}: {response.text[:120]}")


@events.quitting.add_listener
def _r10_gate(environment, **_kwargs) -> None:
    stats = environment.stats.total
    p95 = stats.get_response_time_percentile(0.95)
    print(
        f"R10 : {stats.num_requests} requêtes, {stats.total_rps * 60:.0f}/min, "
        f"p95 {p95:.0f} ms, échecs {stats.fail_ratio:.2%}"
    )
    if p95 > 500 or stats.fail_ratio > 0.01:
        environment.process_exit_code = 1
