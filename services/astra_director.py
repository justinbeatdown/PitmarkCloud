from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services.master_checklist import list_items, update_item
from services.command_brief import build_command_brief
from services.autonomy_control import list_policies, mode_for, effective_mode
from services.control_center import SocialPost
from services.first_party_auto_schedule import auto_schedule_verified_first_party
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


class AstraDirectorAction(Base):
    __tablename__ = "pitmark_astra_director_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    action_type: Mapped[str] = mapped_column(String(50), index=True)
    capability: Mapped[str] = mapped_column(String(80), default="internal_prepare")
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
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
- If the live content queue contains eligible low-risk verified first-party posts and first_party_social_publish is AUTO, prefer using internal_action auto_schedule_verified_first_party instead of merely recommending scheduling.

Return valid JSON only with keys: headline, state, executive_summary, top_actions, owner_needed, delegate, risks, done_when.
Each top_actions item must include rank, title, why, area, execution, capability, checklist_row, next_step.
The execution field MUST ALWAYS be an object, never a string.
Execution object schema:
- status: short string
- notes: short string
- drafts: array of zero or more objects with platform, title, and body
- internal_action: optional object with type and payload
If no draft exists, drafts must be [].
Supported draft platforms are facebook, instagram, x, and discord.
Draft titles are customer-facing approval labels, not internal task names. Make them concise, natural, and specific to the post hook/topic.
Supported internal_action types are ONLY:
1) master_checklist_update with payload {row_number, status?, priority?, next_action?, notes?}
2) auto_schedule_verified_first_party with payload {}
If an action would publish reactive/manual social, send outreach, publish a blog, spend money, alter credentials/security, or do anything outside that whitelist, do not request an internal_action; put it in owner_needed or next_step instead.
Each owner_needed item must include title, reason, urgency.
Each delegate item must include worker and task.

STRICT OUTPUT BUDGET
- Return one complete JSON object only. No markdown fences, prose before/after, or comments.
- Keep the entire response under about 1200 output tokens so it cannot be truncated.
- top_actions: maximum 3 items.
- owner_needed: maximum 3 items.
- delegate: maximum 3 items.
- risks: maximum 3 concise items.
- executive_summary: maximum 120 words.
- Keep why, execution, capability, next_step, reason, and task concise; next_step should be no more than 35 words.
- If there is more context than fits, prioritize only the highest-impact information rather than expanding the response.
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


def _content_queue_snapshot() -> dict[str, Any]:
    with SessionLocal() as db:
        rows = list(db.scalars(
            select(SocialPost)
            .where(SocialPost.status.in_(["pending", "approved", "scheduled"]))
            .order_by(SocialPost.created_at.desc())
            .limit(12)
        ).all())
    return {
        "count": len(rows),
        "items": [
            {
                "id": row.id,
                "platform": row.platform,
                "title": row.title,
                "body": row.body[:1200],
                "content_type": row.content_type,
                "source": row.source,
                "risk": row.risk,
                "status": row.status,
                "media_url": row.media_url,
                "scheduled_for": row.scheduled_for,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }


def director_state() -> dict[str, Any]:
    try:
        _repair_legacy_astra_draft_titles()
    except Exception:
        log.exception("Could not repair legacy Astra draft titles")
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
        "content_queue": _content_queue_snapshot(),
        "autonomy": list_policies(),
    }


def _safe_json(text: str) -> dict[str, Any]:
    candidate = (text or "").strip()
    if not candidate:
        raise RuntimeError("Astra returned an empty response.")

    attempts = [candidate]
    start, end = candidate.find("{"), candidate.rfind("}")
    if start >= 0 and end > start:
        extracted = candidate[start:end + 1]
        if extracted != candidate:
            attempts.append(extracted)

    last_error: json.JSONDecodeError | None = None
    for attempt in attempts:
        try:
            data = json.loads(attempt)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if not isinstance(data, dict):
            raise RuntimeError("Astra returned an unexpected response shape.")
        return data

    if last_error is not None:
        log.warning(
            "Astra Director returned malformed/truncated JSON: %s; chars=%s",
            last_error,
            len(candidate),
        )
    raise RuntimeError(
        "Astra's response was cut off before the JSON finished. "
        "The Director output has been tightened; run it again."
    )


def _human_draft_title(body: str, fallback: str = "Pitmark social post") -> str:
    text = " ".join(str(body or "").split()).strip()
    if not text:
        return fallback[:180]
    # Use the opening hook instead of an internal Director task label.
    first = text.split("\n", 1)[0].strip()
    for sep in (". ", "? ", "! "):
        if sep in first:
            first = first.split(sep, 1)[0] + sep.strip()
            break
    first = first.strip(" -—:;|")
    if len(first) < 8:
        first = text[:90].strip()
    return first[:180] or fallback[:180]


def _repair_legacy_astra_draft_titles() -> int:
    repaired = 0
    with SessionLocal() as db:
        rows = list(db.scalars(
            select(SocialPost).where(
                SocialPost.source.like("astra:%"),
                SocialPost.status.in_(["pending", "approved", "scheduled"]),
            )
        ).all())
        for row in rows:
            current = str(row.title or "").strip()
            internalish = (
                not current
                or current.lower().startswith(("move ", "use ", "prepare ", "review ", "check ", "run "))
                or "toward scheduling" in current.lower()
                or "owner unlock" in current.lower()
            )
            if internalish:
                row.title = _human_draft_title(row.body, "Pitmark social post")
                repaired += 1
        if repaired:
            db.commit()
    return repaired


def _save_social_drafts_from_result(result: dict[str, Any], run_id: int) -> list[dict[str, Any]]:
    """Persist Astra-prepared social copy as approval-queue drafts only.

    This never publishes or schedules. It is intentionally narrower than the
    social_publish capability and exists only to turn already-prepared copy into
    internal reviewable work.
    """
    created: list[dict[str, Any]] = []
    platform_keys = ("facebook", "instagram", "x", "discord")
    with SessionLocal() as db:
        for action in result.get("top_actions") or []:
            if not isinstance(action, dict):
                continue
            execution = action.get("execution")
            if not isinstance(execution, dict):
                continue

            copies: dict[str, str] = {}
            for platform in platform_keys:
                legacy = str(execution.get(platform) or "").strip()
                if legacy:
                    copies[platform] = legacy

            draft_titles: dict[str, str] = {}
            for draft in execution.get("drafts") or []:
                if not isinstance(draft, dict):
                    continue
                platform = str(draft.get("platform") or "").strip().lower()
                body = str(draft.get("body") or "").strip()
                title = str(draft.get("title") or "").strip()
                if platform in platform_keys and body:
                    copies[platform] = body
                    if title:
                        draft_titles[platform] = title[:180]

            if not copies:
                continue

            fallback_title = str(action.get("title") or "Astra prepared content")[:180]
            source = f"astra:{run_id}"
            for platform, body in copies.items():
                title = draft_titles.get(platform) or _human_draft_title(body, fallback_title)
                exists = db.scalar(
                    select(SocialPost.id).where(
                        SocialPost.platform == platform,
                        SocialPost.body == body,
                        SocialPost.status.in_(["pending", "approved", "scheduled"]),
                    )
                )
                if exists:
                    continue
                row = SocialPost(
                    platform=platform,
                    title=title,
                    body=body,
                    content_type="authority",
                    source=source,
                    risk="low",
                    status="pending",
                    media_url=None,
                )
                db.add(row)
                db.flush()
                created.append({
                    "post_id": row.id,
                    "platform": platform,
                    "status": "pending",
                    "source": source,
                })

        if created:
            db.commit()

        audit = AstraDirectorAction(
            run_id=run_id,
            action_type="prepare_social_drafts",
            capability="internal_prepare",
            status="completed",
            payload_json=json.dumps({"source": f"astra:{run_id}"}, ensure_ascii=False),
            result_json=json.dumps({"created": created}, ensure_ascii=False),
        )
        db.add(audit)
        db.commit()

    return created


def _audit_director_action(
    *,
    run_id: int,
    action_type: str,
    capability: str,
    status: str,
    payload: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    with SessionLocal() as db:
        db.add(AstraDirectorAction(
            run_id=run_id,
            action_type=action_type[:50],
            capability=capability[:80],
            status=status[:30],
            payload_json=json.dumps(payload or {}, ensure_ascii=False, default=str),
            result_json=json.dumps(result or {}, ensure_ascii=False, default=str),
            error=(error or "")[:1000] or None,
        ))
        db.commit()


def _dispatch_internal_actions(result: dict[str, Any], run_id: int) -> list[dict[str, Any]]:
    dispatched: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for action in result.get("top_actions") or []:
        if not isinstance(action, dict):
            continue
        execution = action.get("execution")
        if not isinstance(execution, dict):
            continue
        spec = execution.get("internal_action")
        if not isinstance(spec, dict):
            continue

        action_type = str(spec.get("type") or "").strip()
        payload = spec.get("payload") if isinstance(spec.get("payload"), dict) else {}
        dedupe = (action_type, json.dumps(payload, sort_keys=True, default=str))
        if dedupe in seen:
            continue
        seen.add(dedupe)

        try:
            if action_type == "master_checklist_update":
                mode = effective_mode("master_checklist_update", uncertainty=0.05, fallback="approval")
                if mode != "auto":
                    outcome = {
                        "type": action_type,
                        "status": "approval_required" if mode == "approval" else "blocked",
                        "capability": "master_checklist_update",
                        "mode": mode,
                        "payload": payload,
                    }
                    _audit_director_action(
                        run_id=run_id,
                        action_type=action_type,
                        capability="master_checklist_update",
                        status=outcome["status"],
                        payload=payload,
                        result={"mode": mode},
                    )
                    dispatched.append(outcome)
                    continue

                row_number = int(payload.get("row_number") or action.get("checklist_row") or 0)
                updates = {
                    key: payload[key]
                    for key in ("status", "priority", "next_action", "notes")
                    if key in payload and payload[key] is not None
                }
                if row_number < 8 or not updates:
                    raise ValueError("Checklist update needs a valid row_number and at least one supported field.")
                updated = update_item(row_number, updates)
                outcome = {
                    "type": action_type,
                    "status": "completed",
                    "capability": "master_checklist_update",
                    "row_number": row_number,
                    "updates": updates,
                    "task": updated.get("task"),
                }
                _audit_director_action(
                    run_id=run_id,
                    action_type=action_type,
                    capability="master_checklist_update",
                    status="completed",
                    payload=payload,
                    result=outcome,
                )
                dispatched.append(outcome)
                continue

            if action_type == "auto_schedule_verified_first_party":
                mode = effective_mode("first_party_social_publish", uncertainty=0.05, fallback="auto")
                if mode != "auto":
                    outcome = {
                        "type": action_type,
                        "status": "approval_required" if mode == "approval" else "blocked",
                        "capability": "first_party_social_publish",
                        "mode": mode,
                    }
                    _audit_director_action(
                        run_id=run_id,
                        action_type=action_type,
                        capability="first_party_social_publish",
                        status=outcome["status"],
                        payload=payload,
                        result={"mode": mode},
                    )
                    dispatched.append(outcome)
                    continue
                scheduled = auto_schedule_verified_first_party()
                outcome = {
                    "type": action_type,
                    "status": "completed",
                    "capability": "first_party_social_publish",
                    "scheduled_campaigns": scheduled.get("scheduled_campaigns", 0),
                    "scheduled_posts": scheduled.get("scheduled_posts", 0),
                    "assignments": scheduled.get("assignments") or [],
                    "reason": scheduled.get("reason"),
                }
                _audit_director_action(
                    run_id=run_id,
                    action_type=action_type,
                    capability="first_party_social_publish",
                    status="completed",
                    payload=payload,
                    result=scheduled,
                )
                dispatched.append(outcome)
                continue

            outcome = {
                "type": action_type or "unknown_internal_action",
                "status": "blocked",
                "capability": str(action.get("capability") or "unknown"),
                "reason": "Action type is not on Astra's execution whitelist.",
            }
            _audit_director_action(
                run_id=run_id,
                action_type=outcome["type"],
                capability=outcome["capability"],
                status="blocked",
                payload=payload,
                result={"reason": outcome["reason"]},
            )
            dispatched.append(outcome)
        except Exception as exc:
            log.exception("Astra internal action failed: %s", action_type)
            outcome = {
                "type": action_type or "unknown_internal_action",
                "status": "failed",
                "capability": str(action.get("capability") or "internal"),
                "error": str(exc)[:300],
            }
            _audit_director_action(
                run_id=run_id,
                action_type=outcome["type"],
                capability=outcome["capability"],
                status="failed",
                payload=payload,
                error=str(exc),
            )
            dispatched.append(outcome)

    return dispatched


def _execute_safe_internal_actions(result: dict[str, Any], run_id: int) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    try:
        repaired = _repair_legacy_astra_draft_titles()
        if repaired:
            actions.append({
                "type": "social_draft_titles_repaired",
                "status": "completed",
                "count": repaired,
            })
        drafts = _save_social_drafts_from_result(result, run_id)
        if drafts:
            actions.append({
                "type": "social_drafts_saved",
                "status": "completed",
                "count": len(drafts),
                "items": drafts,
                "approval_required_to_publish": mode_for("social_publish", "approval") != "auto",
            })
        actions.extend(_dispatch_internal_actions(result, run_id))
    except Exception as exc:
        log.exception("Astra safe execution failed")
        with SessionLocal() as db:
            db.add(AstraDirectorAction(
                run_id=run_id,
                action_type="safe_execution",
                capability="internal_prepare",
                status="failed",
                payload_json="{}",
                result_json="{}",
                error=str(exc)[:1000],
            ))
            db.commit()
        actions.append({"type": "safe_execution", "status": "failed", "error": str(exc)[:300]})
    return {"actions": actions, "executed_count": sum(1 for x in actions if x.get("status") == "completed")}


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

    if body.get("status") == "incomplete":
        details = body.get("incomplete_details") or {}
        reason = details.get("reason") if isinstance(details, dict) else None
        log.warning("Astra Director response incomplete: %s", reason or "unknown")
        raise RuntimeError(
            "Astra hit its response limit before finishing. "
            "The Director output has been tightened; run it again."
        )

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
        run_id = row.id

    result["execution_result"] = _execute_safe_internal_actions(result, run_id)

    with SessionLocal() as db:
        stored = db.get(AstraDirectorRun, run_id)
        if stored:
            stored.result_json = json.dumps(result, ensure_ascii=False, default=str)
            db.commit()
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
