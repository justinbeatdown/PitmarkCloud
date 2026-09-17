from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
import threading
import time
from typing import Any
from urllib.parse import quote

SPREADSHEET_ID = "18k0Lnc4Dh8WsWssLDbOobE5lCXIQO1FjlAEKcHJ-UtI"
SHEET_NAME = "Master Checklist"
READ_RANGE = "'Master Checklist'!A7:H1000"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
CACHE_SECONDS = 60

_cache_lock = threading.Lock()
_cache: dict[str, Any] | None = None
_cache_monotonic = 0.0

_COMPLETE = {"done", "complete", "completed", "closed"}
_ACTIVE = {"active", "in progress", "in-progress", "working"}
_WAITING = {"waiting", "awaiting", "pending external"}
_MONITORING = {"monitoring", "monitor"}
_BLOCKED = {"blocked", "blocker"}
_ROADMAP = {"later", "planned", "paused", "backlog", "roadmap", "future"}

_DESKTOP_PATTERNS = (
    r"\bdesktop\b",
    r"\bwindows pc\b",
    r"\brequires? (?:a )?pc\b",
    r"\bcomputer required\b",
    r"\biracing\b",
    r"\bvr headset\b",
    r"\blive telemetry\b",
    r"\blocal prt build\b",
    r"\bapps script authorization\b",
)
_PHONE_PATTERNS = (
    r"\bphone[- ]only\b",
    r"\bphone[- ]actionable\b",
    r"\bmobile[- ]actionable\b",
    r"\bcan (?:be )?do(?:ne)? from (?:a |the )?phone\b",
    r"\bdo from (?:a |the )?phone\b",
)

_ALLOWED_UPDATES = {
    "status": "B",
    "priority": "C",
    "next_action": "F",
    "notes": "G",
}


def _cell(row: list[Any], index: int) -> str:
    if index >= len(row) or row[index] is None:
        return ""
    return str(row[index]).strip()


def _checkbox(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "1", "checked", "done"}


def _explicit_context(text: str, patterns: tuple[str, ...]) -> bool:
    value = " ".join(text.lower().split())
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def normalize_row(row: list[Any], *, row_number: int) -> dict[str, Any]:
    done = _checkbox(_cell(row, 0))
    status = _cell(row, 1)
    priority = _cell(row, 2)
    area = _cell(row, 3)
    task = _cell(row, 4)
    next_action = _cell(row, 5)
    notes = _cell(row, 6)
    last_updated = _cell(row, 7)
    context_text = " ".join((task, next_action, notes))
    return {
        "row_number": int(row_number),
        "done": done,
        "status": status,
        "priority": priority,
        "area": area,
        "task": task,
        "next_action": next_action,
        "notes": notes,
        "last_updated": last_updated,
        "desktop_required": _explicit_context(context_text, _DESKTOP_PATTERNS),
        "phone_actionable": _explicit_context(context_text, _PHONE_PATTERNS),
    }


def bucket_for(item: dict[str, Any]) -> str:
    if bool(item.get("done")):
        return "completed"
    status = str(item.get("status") or "").strip().lower()
    if status in _COMPLETE:
        return "completed"
    if status in _BLOCKED:
        return "blocked"
    if status in _WAITING:
        return "waiting"
    if status in _MONITORING:
        return "monitoring"
    if status in _ROADMAP:
        return "roadmap"
    if status in _ACTIVE:
        return "active"
    return "other"


def _google_runtime():
    # Keep parsing/classification lightweight and testable without importing the
    # HTTP/OAuth stack until an actual Google request is made.
    import httpx
    from services.google_workspace_auth import authorization_headers, workspace_credentials_configured

    return httpx, authorization_headers, workspace_credentials_configured


def _authorization_error() -> RuntimeError:
    return RuntimeError(
        "Master Checklist is disconnected from Google Sheets. A Sheets-capable Google Workspace authorization is required."
    )


def _sheet_values() -> list[list[Any]]:
    httpx, authorization_headers, workspace_credentials_configured = _google_runtime()
    if not workspace_credentials_configured():
        raise _authorization_error()
    encoded = quote(READ_RANGE, safe="")
    url = f"{SHEETS_API}/{SPREADSHEET_ID}/values/{encoded}"
    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            url,
            headers=authorization_headers(),
            params={"majorDimension": "ROWS", "valueRenderOption": "FORMATTED_VALUE"},
        )
    if response.status_code >= 400:
        if response.status_code in {401, 403}:
            raise _authorization_error()
        raise RuntimeError(f"Master Checklist read failed ({response.status_code}).")
    payload = response.json()
    rows = payload.get("values") if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "active": 0,
        "waiting": 0,
        "monitoring": 0,
        "blocked": 0,
        "completed": 0,
        "roadmap": 0,
        "other": 0,
    }
    for item in items:
        counts[bucket_for(item)] += 1
    counts["open"] = len(items) - counts["completed"]
    counts["total"] = len(items)
    counts["p0"] = sum(1 for item in items if str(item.get("priority") or "").upper() == "P0" and bucket_for(item) != "completed")
    counts["p1"] = sum(1 for item in items if str(item.get("priority") or "").upper() == "P1" and bucket_for(item) != "completed")
    return counts


def _build_snapshot(rows: list[list[Any]]) -> dict[str, Any]:
    # A7:H includes the row-7 header. Data begins on row 8.
    has_header = bool(rows) and any(str(cell).strip().lower() == "status" for cell in rows[0])
    data_rows = rows[1:] if has_header else rows
    first_row_number = 8 if has_header else 7
    items: list[dict[str, Any]] = []
    for offset, row in enumerate(data_rows):
        item = normalize_row(row, row_number=first_row_number + offset)
        if not item["task"] and not item["area"] and not item["status"]:
            continue
        item["bucket"] = bucket_for(item)
        items.append(item)
    now = datetime.now(timezone.utc).isoformat()
    return {
        "source": "google_sheets",
        "spreadsheet_id": SPREADSHEET_ID,
        "sheet_name": SHEET_NAME,
        "fetched_at": now,
        "stale": False,
        "items": items,
        "summary": _summary(items),
    }


def list_items(*, force: bool = False) -> dict[str, Any]:
    global _cache, _cache_monotonic
    with _cache_lock:
        if not force and _cache is not None and time.monotonic() - _cache_monotonic < CACHE_SECONDS:
            return deepcopy(_cache)

    try:
        snapshot = _build_snapshot(_sheet_values())
    except Exception as exc:
        with _cache_lock:
            if _cache is not None:
                stale = deepcopy(_cache)
                stale["stale"] = True
                stale["error"] = str(exc)[:1000]
                return stale
        raise

    with _cache_lock:
        _cache = deepcopy(snapshot)
        _cache_monotonic = time.monotonic()
    return snapshot


def invalidate_cache() -> None:
    global _cache, _cache_monotonic
    with _cache_lock:
        _cache = None
        _cache_monotonic = 0.0


def update_item(row_number: int, updates: dict[str, Any]) -> dict[str, Any]:
    if row_number < 8:
        raise ValueError("Master Checklist data rows begin at row 8.")
    if not updates:
        raise ValueError("At least one update is required.")

    unknown = sorted(set(updates) - set(_ALLOWED_UPDATES))
    if unknown:
        raise ValueError(f"Unsupported Master Checklist fields: {', '.join(unknown)}")

    httpx, authorization_headers, workspace_credentials_configured = _google_runtime()
    if not workspace_credentials_configured():
        raise _authorization_error()

    data: list[dict[str, Any]] = []
    for field, value in updates.items():
        column = _ALLOWED_UPDATES[field]
        data.append(
            {
                "range": f"'{SHEET_NAME}'!{column}{row_number}",
                "values": [["" if value is None else str(value)]],
            }
        )

    if "status" in updates:
        status = str(updates.get("status") or "").strip().lower()
        done = status in _COMPLETE
        data.append({"range": f"'{SHEET_NAME}'!A{row_number}", "values": [[done]]})

    data.append(
        {
            "range": f"'{SHEET_NAME}'!H{row_number}",
            "values": [[datetime.now(timezone.utc).date().isoformat()]],
        }
    )

    url = f"{SHEETS_API}/{SPREADSHEET_ID}/values:batchUpdate"
    body = {
        "valueInputOption": "USER_ENTERED",
        "includeValuesInResponse": False,
        "data": data,
    }
    with httpx.Client(timeout=20.0) as client:
        response = client.post(url, headers=authorization_headers(), json=body)
    if response.status_code >= 400:
        if response.status_code in {401, 403}:
            raise _authorization_error()
        raise RuntimeError(f"Master Checklist update failed ({response.status_code}).")

    invalidate_cache()
    snapshot = list_items(force=True)
    item = next((row for row in snapshot["items"] if row["row_number"] == row_number), None)
    if item is None:
        raise RuntimeError("Master Checklist updated but the row could not be reloaded.")
    return item
