from __future__ import annotations

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://pitmarkcloud.onrender.com").rstrip("/")


def request(path: str, method: str = "GET", body: bytes | None = None, content_type: str | None = None):
    headers = {"User-Agent": "PitmarkCloud-SmokeTest/0.5.0"}
    if content_type:
        headers["Content-Type"] = content_type
    req = Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=75) as response:
            data = response.read().decode("utf-8")
            return response.status, data
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")
    except URLError as exc:
        raise SystemExit(f"Could not reach {BASE}: {exc}") from exc


def expect(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}{' — ' + detail if detail else ''}")
    if not condition:
        raise SystemExit(1)


status, body = request("/health")
health = json.loads(body)
expect("Health endpoint", status == 200 and health.get("status") == "online", f"HTTP {status}")

status, body = request("/api/discord/bot/status")
bot = json.loads(body)
expect("Discord bot status", status == 200 and "gateway_presence" in bot, f"HTTP {status}")

status, body = request("/api/entitlements/development")
entitlements = json.loads(body)
expect("Development entitlements", status == 200 and entitlements.get("development_mode") is True, f"HTTP {status}")

status, _ = request(
    "/api/discord/session/update?device_id=smoke-test-unlinked",
    method="POST",
    body=b"{bad",
    content_type="application/json",
)
expect("Malformed telemetry rejected", status == 422, f"HTTP {status}")

status, _ = request(
    "/api/discord/session/update?device_id=smoke-test-unlinked",
    method="POST",
    body=b'{"track_name":"Smoke Test"}',
    content_type="application/json",
)
expect("Unlinked telemetry rejected", status == 403, f"HTTP {status}")


status, _ = request(
    "/api/discord/result/publish?device_id=smoke-test-unlinked",
    method="POST",
    body=b'{"track_name":"Smoke Test","laps":1}',
    content_type="application/json",
)
expect("Unlinked completed result rejected", status == 403, f"HTTP {status}")

status, _ = request(
    "/api/discord/result/publish?device_id=smoke-test-unlinked",
    method="POST",
    body=b'{"laps":-1}',
    content_type="application/json",
)
expect("Invalid completed result rejected", status == 422, f"HTTP {status}")

print(f"\nPitmark Cloud smoke test passed against {BASE}")
