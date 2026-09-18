from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services.master_checklist import list_items
from services.command_brief import build_command_brief
from services.autonomy_control import list_policies
from utils.config import settings

log = logging.getLogger("pitmark.astra_director")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AstraDirectorRun(Base):
    __tablename__ = "pitmark_astra_director_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String(30), default="operator", index=True)
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    request_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    model: Mapped[str] = mapped_column(String(80), default="gpt-6-astra")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


DIRECTOR_INSTRUCTIONS = """You are Pitmark Director, the executive operating intelligence for Pitmark Racing Co.

Your job is to understand the current operating state, identify the highest-impact work, and reduce how much the owner has to manually coordinate.

OPERATING RULES
- Bias toward action, completion, simplification, reliability, and revenue-enabling work.
- The Pitmark Master Checklist is the source of truth for company work.
- Respect the supplied autonomy policies exactly.
- Never authorize or execute money movement, purchases, refunds, contracts, tax/legal decisions, credential/security overrides, or permission overrides.
- Never claim an external action happened unless the supplied state says it happened.
- Prefer fixing root causes over layering more code or process on top.
- Preserve PRT as an iRacing-only product unless the supplied state explicitly changes that.
- Do not expose email content in Control Center.
- Keep recommendations concrete and small enough to execute.
- Escalate to the owner only when human approval, credentials, desktop/iRacing hardware, judgment, or an irreversible external action is truly needed.
- Cost discipline matters. Astra is the director; routine work should be delegated to cheaper models or deterministic code.

Return valid JSON only with keys: headline, state, executive_summary, top_actions, owner_needed, delegate, risks, done_when.
Each top_actions item must include rank, title, why, area, execution, capability, checklist_row, next_step.
Each owner_needed item must include title, reason, urgency.
Each delegate item must include worker and task.
"""


def _extract_output_text(data: dict[str, Any]) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    chunks: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                chunks.append(content["text"].strip())
    return "\n".join(x for x in chunks if x).strip()


def _trim_checklist(snapshot: dict[str, Any]) -> dict[str, Any]:
    items = list(snapshot.get("items") or [])
    open_items = [x for x in items if x.get("bucket") != "completed"]
    priority = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    open_items.sort(key=lambda x: (
        priority.get(str(x.get("priority") or "").upper(), 9),
        0 if x.get("bucket") in {"blocked", "active"} else 1,
        int(x.get("row_number") or 99999),
    ))
    return {
        "source": snapshot.get("source"),
        "stale": bool(snapshot.get("stale")),
        "error": snapshot.get("error"),
        "summary": snapshot.get("summary") or {},
        "items": open_items[:50],
    }


def director_state() -> dict[str, Any]:
    try:
        checklist = _trim_checklist(list_items())
    except Exception as exc:
        checklist = {"source": "google_sheets", "stale": True, "error": str(exc)[:600], "summary": {}, "items": []}
    try:
        brief = build_command_brief()
    except Exception as exc:
        brief = {"status": "attention", "headline": "Command brief unavailable", "error": str(exc)[:600]}
    return {
        "generated_at": utcnow().isoformat(),
        "control_center_version": settings.app_version,
        "director": {
            "enabled": bool(settings.astra_director_enabled),
            "model": settings.astra_director_model,
            "mode": settings.astra_director_mode,
            "max_output_tokens": settings.astra_director_max_output_tokens,
            "background_enabled": False,
            "cost_posture": "on_demand_only",
        },
        "master_checklist": checklist,
        "command_brief": brief,
        "autonomy": list_policies(),
    }


def _safe_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("Astra returned non-JSON output.")
        data = json.loads(candidate[start:end + 1])
    if not isinstance(data, dict):
        raise RuntimeError("Astra returned an unexpected response shape.")
    return data


def run_director(request_text: str = "", *, mode: str | None = None) -> dict[str, Any]:
    if not settings.astra_director_enabled:
        raise RuntimeError("Pitmark Director is disabled.")
    if not settings.openai_api_key.strip():
        raise RuntimeError("OPENAI_API_KEY is not configured in Pitmark Cloud.")

    state = director_state()
    run_mode = (mode or settings.astra_director_mode or "operator").strip().lower()
    user_request = request_text.strip() or (
        "Review Pitmark's current operating state. Decide what matters most now, what can proceed without the owner, "
        "what should be delegated to cheaper workers, and exactly where the owner must intervene."
    )
    payload = {
        "model": settings.astra_director_model,
        "instructions": DIRECTOR_INSTRUCTIONS,
        "input": (
            f"Director mode: {run_mode}\n\nOwner request:\n{user_request}\n\n"
            "Current Pitmark state (authoritative snapshot):\n"
            + json.dumps(state, ensure_ascii=False, default=str)
        ),
        "reasoning": {"effort": settings.astra_director_reasoning_effort},
        "max_output_tokens": settings.astra_director_max_output_tokens,
        "metadata": {"app": "pitmark-control-center", "role": "director"},
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key.strip()}", "Content-Type": "application/json"}
    with httpx.Client(timeout=settings.astra_director_timeout_seconds) as client:
        response = client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()

    result = _safe_json(_extract_output_text(body))
    result["_meta"] = {
        "model": settings.astra_director_model,
        "mode": run_mode,
        "generated_at": utcnow().isoformat(),
        "background_enabled": False,
        "source": "live_pitmark_state",
    }
    with SessionLocal() as db:
        row = AstraDirectorRun(
            mode=run_mode,
            status="completed",
            request_text=request_text[:4000] if request_text else None,
            result_json=json.dumps(result, ensure_ascii=False, default=str),
            model=settings.astra_director_model,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        result["_meta"]["run_id"] = row.id
    return result


def recent_runs(limit: int = 10) -> list[dict[str, Any]]:
    safe_limit = max(1, min(50, int(limit)))
    with SessionLocal() as db:
        rows = list(db.scalars(select(AstraDirectorRun).order_by(AstraDirectorRun.id.desc()).limit(safe_limit)).all())
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            result = json.loads(row.result_json or "{}")
        except json.JSONDecodeError:
            result = {}
        out.append({
            "id": row.id,
            "mode": row.mode,
            "status": row.status,
            "request_text": row.request_text,
            "model": row.model,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "headline": result.get("headline"),
            "state": result.get("state"),
            "owner_needed": result.get("owner_needed") or [],
        })
    return out


def startup_self_test() -> dict[str, Any]:
    """Tiny, opt-in Astra entitlement probe. Never runs unless explicitly enabled."""
    if not settings.astra_director_self_test:
        return {"enabled": False}
    if not settings.openai_api_key.strip():
        log.error("ASTRA_SELF_TEST failed: OPENAI_API_KEY is not configured")
        return {"enabled": True, "ok": False, "error": "missing_openai_api_key"}
    payload = {
        "model": settings.astra_director_model,
        "input": "Reply with exactly OK.",
        "max_output_tokens": 16,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key.strip()}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=min(settings.astra_director_timeout_seconds, 30.0)) as client:
            response = client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
            response.raise_for_status()
            text = _extract_output_text(response.json())
        log.info("ASTRA_SELF_TEST ok model=%s output=%s", settings.astra_director_model, text[:40] or "<empty>")
        return {"enabled": True, "ok": True, "model": settings.astra_director_model}
    except Exception as exc:
        detail = str(exc)
        if isinstance(exc, httpx.HTTPStatusError):
            try:
                detail = exc.response.json().get("error", {}).get("message") or detail
            except Exception:
                pass
        log.error("ASTRA_SELF_TEST failed model=%s error=%s", settings.astra_director_model, detail[:500])
        return {"enabled": True, "ok": False, "model": settings.astra_director_model, "error": detail[:500]}
