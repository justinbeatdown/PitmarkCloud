"""Consent-based pairing and private session import from PRT desktop.

No iRacing passwords or customer IDs are transferred. Device credentials are
stored as one-way digests and may be revoked from the Race Center website.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import re
import secrets
import time
from urllib.parse import urlparse
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint, delete, func, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services import race_center_accounts
from utils.config import settings

router = APIRouter()
PAIR_TTL = 600
DEVICE_TTL = 90 * 86400
CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class PrtPair(Base):
    __tablename__ = "race_center_prt_pairs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    expires_at: Mapped[float] = mapped_column(Float)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("race_center_users.id"), nullable=True)
    consent_private_history: Mapped[bool] = mapped_column(Boolean, default=False)


class PrtDevice(Base):
    __tablename__ = "race_center_prt_devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[float] = mapped_column(Float)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    can_upload_private_history: Mapped[bool] = mapped_column(Boolean, default=False)


class PrtSession(Base):
    __tablename__ = "race_center_prt_sessions"
    __table_args__ = (UniqueConstraint("user_id", "source_id", name="uq_rc_prt_session"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id"), index=True)
    source_id: Mapped[str] = mapped_column(String(50))
    data_json: Mapped[str] = mapped_column(Text)


class PrtPublicSharing(Base):
    """Separate, revocable consent for displaying PRT sessions on a public page."""
    __tablename__ = "race_center_prt_public_sharing"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("race_center_users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    changed_at: Mapped[float] = mapped_column(Float, default=time.time)


class PublicSharingChoice(BaseModel):
    public: bool


class LinkApproval(BaseModel):
    code: str = Field(min_length=6, max_length=12)
    consent_private_history: bool = False


class PairPoll(BaseModel):
    device_code: str = Field(min_length=32, max_length=160)


class SessionRow(BaseModel):
    id: str = Field(min_length=12, max_length=50)
    date: str = Field(max_length=48)
    track: str = Field(max_length=160)
    car: str = Field(max_length=160)
    series: str = Field(default="", max_length=160)
    driver_name: str = Field(default="", max_length=100)
    laps: int = Field(ge=0, le=20000)
    incidents: int = Field(ge=0, le=5000)
    finishing_position: int = Field(ge=0, le=1500)
    starting_position: int = Field(ge=0, le=1500)
    best_lap: float = Field(ge=0, le=86400)
    strength_of_field: int = Field(default=0, ge=0, le=20000)


class SessionBatch(BaseModel):
    sessions: list[SessionRow] = Field(min_length=1, max_length=50)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _secret() -> bytes:
    configured = str(settings.pitmark_signing_secret or settings.pitmark_admin_key or "")
    if len(configured) < 24:
        raise HTTPException(status_code=503, detail="Race Center signing is not configured")
    return hashlib.sha256(("prt-device-v1:" + configured).encode()).digest()


def _token_for(pair: PrtPair, device_code: str) -> str:
    message = (str(pair.id) + ":" + str(pair.user_id) + ":" + device_code).encode()
    return "prt_" + hmac.new(_secret(), message, hashlib.sha256).hexdigest()


def _same_site(request: Request) -> None:
    origin = request.headers.get("origin", "")
    host = (request.headers.get("host", "") or "").split(":")[0].lower()
    allowed = {"racecenter.pitmarkracing.com", "pitmarkcloud.onrender.com"}
    parsed = urlparse(origin)
    if not origin or parsed.scheme != "https" or parsed.hostname not in allowed or host not in allowed:
        raise HTTPException(status_code=403, detail="Open this action from Race Center")


def _account(request: Request):
    account = race_center_accounts.account_from_request(request)
    if not account:
        raise HTTPException(status_code=401, detail="Sign in to Race Center first")
    return account


def _device(request: Request, for_upload: bool = False) -> PrtDevice:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer prt_"):
        raise HTTPException(status_code=401, detail="Connect PRT to Race Center first")
    with SessionLocal() as db:
        token = db.scalar(select(PrtDevice).where(
            PrtDevice.token_digest == _digest(header[7:]),
            PrtDevice.revoked.is_(False),
            PrtDevice.expires_at > time.time(),
        ))
        if not token:
            raise HTTPException(status_code=401, detail="Race Center connection expired or disconnected")
        if for_upload and not token.can_upload_private_history:
            raise HTTPException(status_code=403, detail="Private history upload was not authorized when this device was linked")
        db.expunge(token)
        return token


def _bearer(request: Request, for_upload: bool = False) -> int:
    return _device(request, for_upload).user_id


@router.post("/api/public/race-center/prt/link/start")
def prt_link_start(request: Request):
    # Link requests cannot reveal or create a Race Center identity.
    code = "".join(secrets.choice(CODE_CHARS) for _ in range(8))
    device_code = secrets.token_urlsafe(40)
    with SessionLocal() as db:
        db.add(PrtPair(device_digest=_digest(device_code), code_digest=_digest(code),
                       expires_at=time.time() + PAIR_TTL))
        db.commit()
    return {
        "device_code": device_code, "user_code": code, "expires_in": PAIR_TTL,
        "verification_url": "https://racecenter.pitmarkracing.com/race-center/prt-connect?code=" + code,
    }


@router.post("/api/public/race-center/prt/link/approve")
def prt_link_approve(request: Request, body: LinkApproval):
    _same_site(request)
    user = _account(request)
    code = re.sub(r"[^A-Z0-9]", "", body.code.upper())
    with SessionLocal() as db:
        pair = db.scalar(select(PrtPair).where(
            PrtPair.code_digest == _digest(code), PrtPair.expires_at > time.time()
        ).with_for_update())
        if not pair or pair.user_id is not None:
            raise HTTPException(status_code=404, detail="That pairing code expired or was already used")
        pair.user_id = user.id
        pair.consent_private_history = bool(body.consent_private_history)
        db.commit()
    profile = race_center_accounts.ensure_profile(user.id)
    return {"ok": True, "handle": profile["handle"], "private_history": True}


@router.post("/api/public/race-center/prt/link/token")
def prt_link_token(body: PairPoll):
    with SessionLocal() as db:
        pair = db.scalar(select(PrtPair).where(
            PrtPair.device_digest == _digest(body.device_code),
            PrtPair.expires_at > time.time()
        ))
        if not pair:
            raise HTTPException(status_code=410, detail="Pairing expired; begin again")
        if pair.user_id is None:
            return {"status": "pending"}
        value = _token_for(pair, body.device_code)
        token = db.scalar(select(PrtDevice).where(PrtDevice.token_digest == _digest(value)))
        if token is None:
            db.add(PrtDevice(user_id=pair.user_id, token_digest=_digest(value),
                             expires_at=time.time() + DEVICE_TTL,
                             can_upload_private_history=pair.consent_private_history))
            db.commit()
        elif token.revoked:
            raise HTTPException(status_code=401, detail="This device was disconnected")
        return {"status": "linked", "access_token": value, "expires_in": DEVICE_TTL,
                "private_history_allowed": pair.consent_private_history}


@router.get("/api/public/race-center/prt/device")
def prt_device(request: Request):
    device = _device(request)
    user_id = device.user_id
    with SessionLocal() as db:
        count = db.scalar(select(func.count(PrtSession.id)).where(PrtSession.user_id == user_id))
    profile = race_center_accounts.ensure_profile(user_id)
    return {"connected": True, "handle": profile["handle"], "session_count": count,
            "can_upload_private_history": device.can_upload_private_history, "visibility": "private"}


@router.put("/api/public/race-center/prt/sessions")
def prt_upload_sessions(request: Request, body: SessionBatch):
    user_id = _bearer(request, for_upload=True)
    imported = 0
    with SessionLocal() as db:
        for item in body.sessions:
            if not re.fullmatch(r"[a-fA-F0-9-]{32,40}", item.id):
                raise HTTPException(status_code=422, detail="Invalid PRT session ID")
            data = item.model_dump()
            record = db.scalar(select(PrtSession).where(
                PrtSession.user_id == user_id, PrtSession.source_id == item.id
            ))
            if record is None:
                db.add(PrtSession(user_id=user_id, source_id=item.id,
                                  data_json=json.dumps(data, separators=(",", ":"))))
                imported += 1
            else:
                record.data_json = json.dumps(data, separators=(",", ":"))
        db.commit()
        total = db.scalar(select(func.count(PrtSession.id)).where(PrtSession.user_id == user_id))
    return {"ok": True, "imported": imported, "session_count": total,
            "visibility": "private"}


@router.post("/api/public/race-center/prt/device/revoke")
def prt_revoke_this_device(request: Request):
    device = _device(request)
    with SessionLocal() as db:
        persisted = db.get(PrtDevice, device.id)
        if persisted:
            persisted.revoked = True
            db.commit()
    return {"ok": True}


@router.get("/api/public/race-center/prt/my-sessions")
def prt_my_sessions(request: Request):
    user = _account(request)
    with SessionLocal() as db:
        records = db.scalars(select(PrtSession).where(
            PrtSession.user_id == user.id).order_by(PrtSession.id.desc()).limit(200)).all()
        return {"sessions": [json.loads(r.data_json) for r in records], "visibility": "private"}


@router.get("/api/public/race-center/prt/my-summary")
def prt_my_summary(request: Request):
    user = _account(request)
    with SessionLocal() as db:
        rows = db.scalars(select(PrtSession).where(PrtSession.user_id == user.id)).all()
        device_count = db.scalar(select(func.count(PrtDevice.id)).where(
            PrtDevice.user_id == user.id,
            PrtDevice.revoked.is_(False),
            PrtDevice.expires_at > time.time(),
        )) or 0
        data = [json.loads(row.data_json) for row in rows]
    finished = [row for row in data if int(row.get("finishing_position") or 0) > 0]
    return {
        "private": True, "sessions": len(data), "connected_devices": int(device_count),
        "laps": sum(int(row.get("laps") or 0) for row in data),
        "wins": sum(int(row.get("finishing_position") or 0) == 1 for row in finished),
        "top_fives": sum(int(row.get("finishing_position") or 0) <= 5 for row in finished),
        "best_lap": min((float(row.get("best_lap") or 0) for row in data if float(row.get("best_lap") or 0) > 0), default=0),
    }


PUBLIC_SESSION_FIELDS = (
    "date", "track", "car", "series", "laps", "incidents",
    "finishing_position", "starting_position", "best_lap", "strength_of_field",
)


def _public_session(row: dict) -> dict:
    # Important: never publish iRacing identifiers, device tokens or raw source IDs.
    return {key: row.get(key) for key in PUBLIC_SESSION_FIELDS}


def _public_summary(data: list[dict]) -> dict:
    finished = [row for row in data if int(row.get("finishing_position") or 0) > 0]
    return {
        "sessions": len(data),
        "laps": sum(int(row.get("laps") or 0) for row in data),
        "wins": sum(int(row.get("finishing_position") or 0) == 1 for row in finished),
        "top_fives": sum(0 < int(row.get("finishing_position") or 0) <= 5 for row in finished),
        "best_lap": min(
            (float(row.get("best_lap") or 0) for row in data if float(row.get("best_lap") or 0) > 0),
            default=0,
        ),
    }


@router.get("/api/public/race-center/prt/sharing")
def prt_get_sharing(request: Request):
    owner = _account(request)
    with SessionLocal() as db:
        record = db.get(PrtPublicSharing, owner.id)
        return {"public": bool(record and record.enabled)}


@router.put("/api/public/race-center/prt/sharing")
def prt_set_sharing(request: Request, choice: PublicSharingChoice):
    _same_site(request)
    owner = _account(request)
    with SessionLocal() as db:
        record = db.get(PrtPublicSharing, owner.id)
        if record is None:
            record = PrtPublicSharing(user_id=owner.id)
            db.add(record)
        record.enabled = bool(choice.public)
        record.changed_at = time.time()
        db.commit()
    return {"public": choice.public, "ok": True}


@router.get("/api/public/race-center/prt/public/{handle}")
def prt_public_racing_history(handle: str, limit: int = 25, offset: int = 0):
    """Explicitly published results only. Everyone else receives no race data."""
    if limit < 1 or limit > 100 or offset < 0 or offset > 100000:
        raise HTTPException(status_code=422, detail="Invalid public race page")
    profile = race_center_accounts.public_profile_by_handle(handle)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    user_id = int(profile["id"])
    with SessionLocal() as db:
        share = db.get(PrtPublicSharing, user_id)
        if not share or not share.enabled:
            return {"public": False}
        rows = db.scalars(select(PrtSession).where(PrtSession.user_id == user_id)).all()
        data = [json.loads(row.data_json) for row in rows]
    data.sort(key=lambda item: str(item.get("date") or ""), reverse=True)
    summary = _public_summary(data)
    visible = [_public_session(row) for row in data[offset:offset + limit]]
    return {
        "public": True,
        "summary": summary,
        "sessions": visible,
        "offset": offset,
        "next_offset": offset + len(visible) if offset + len(visible) < len(data) else None,
    }


@router.post("/api/public/race-center/prt/unlink")
def prt_unlink(request: Request):
    _same_site(request)
    user = _account(request)
    with SessionLocal() as db:
        db.query(PrtDevice).filter(PrtDevice.user_id == user.id).update({"revoked": True})
        db.commit()
    return {"ok": True}


@router.delete("/api/public/race-center/prt/my-sessions")
def prt_delete_history(request: Request):
    _same_site(request)
    user = _account(request)
    with SessionLocal() as db:
        db.execute(delete(PrtSession).where(PrtSession.user_id == user.id))
        db.commit()
    return {"ok": True}


@router.get("/race-center/me", include_in_schema=False)
def race_center_my_profile(request: Request):
    """Stable, bookmarkable route to the signed-in user's own profile."""
    account = race_center_accounts.account_from_request(request)
    if not account:
        return RedirectResponse(url="/race-center", status_code=303)
    profile = race_center_accounts.ensure_profile(account.id)
    return RedirectResponse(
        url="/race-center/u/" + profile["handle"] + "#prt-history",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/race-center-prt-profile.css", include_in_schema=False)
def prt_private_profile_css():
    return Response(
        Path(__file__).with_name("race_center_prt_profile.css").read_text(encoding="utf-8"),
        media_type="text/css", headers={"Cache-Control": "no-store"},
    )


@router.get("/prt-connect.css", include_in_schema=False)
def prt_connect_css():
    return Response(
        Path(__file__).with_name("prt_connect.css").read_text(encoding="utf-8"),
        media_type="text/css", headers={"Cache-Control": "no-store"},
    )


@router.get("/prt-connect.js", include_in_schema=False)
def prt_connect_js():
    return Response(
        Path(__file__).with_name("prt_connect.js").read_text(encoding="utf-8"),
        media_type="application/javascript", headers={"Cache-Control": "no-store"},
    )


@router.get("/race-center/prt-connect", response_class=HTMLResponse)
def prt_connect_page(request: Request, code: str = ""):
    account = race_center_accounts.account_from_request(request)
    clean_code = html.escape(re.sub(r"[^A-Z0-9]", "", (code or "").upper())[:8], quote=True)
    if account:
        account_label = html.escape(account.display_name or account.email, quote=True)
        content = f"""
            <section class="panel highlight" aria-labelledby="pair-title">
              <div class="step">Step 2 of 2 · Approve your computer</div>
              <h2 id="pair-title">Link this PRT installation</h2>
              <div class="identity">Signed in as <strong>{account_label}</strong></div>
              <label class="field-label" for="code">Pairing code shown in PRT</label>
              <input class="code" id="code" name="code" value="{clean_code}"
                maxlength="8" autocomplete="off" spellcheck="false" aria-describedby="code-help">
              <p class="helper" id="code-help">
                Use the eight-character code currently shown on your PRT Profile screen.
                Codes expire after 10 minutes; start a new connection in PRT if needed.
              </p>
              <label class="checkrow" for="consent">
                <input id="consent" type="checkbox">
                <span><strong>Allow private racing-history uploads</strong>
                <span class="helper"> — optional. Your imported sessions stay visible only to you,
                not the public Race Center feed.</span></span>
              </label>
              <div class="actions"><button type="button" class="primary" id="approve">Approve this computer</button><a class="button" id="viewMyProfile" href="/race-center/me">Open my racer profile</a></div>
              <p class="status" id="feedback" role="status" aria-live="polite"></p>
            </section>
            <section class="panel secondary" aria-labelledby="manage-title">
              <h2 id="manage-title">Manage connected PRT computers</h2>
              <p class="helper">Disconnect all desktop devices without deleting your account,
                or permanently remove the racing history you previously uploaded.</p>
              <div class="actions">
                <button type="button" id="unlink">Disconnect all PRT computers</button>
                <button type="button" class="danger" id="erase">Delete imported history</button>
              </div>
              <p class="status" id="historyStatus" role="status" aria-live="polite"></p>
            </section>"""
    else:
        content = """
            <section class="panel highlight">
              <div class="step">Step 1 of 2 · Sign in</div>
              <h2>Sign in to approve PRT</h2>
              <p class="helper">Sign in or create a Race Center account first, then reopen
              the pairing link shown in PRT to approve this computer.</p>
              <div class="actions"><a class="button" href="/race-center">Sign in / create account</a></div>
            </section>"""
    markup = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#080b0f">
<title>Connect PRT · Pitmark Race Center</title>
<link rel="stylesheet" href="/prt-connect.css?v=2">
<script src="/prt-connect.js?v=2" defer></script>
</head>
<body>
<main class="shell">
<a class="brand" href="/race-center"><span class="brand-mark" aria-hidden="true">P</span> PITMARK · RACE CENTER</a>
<span class="eyebrow">PRT + Race Center</span>
<h1>Connect your racing profile.</h1>
<p class="lead">Securely link Pitmark Racing Tools to your Race Center account.
You control whether PRT can upload race history, and imported records remain
private unless you explicitly publish them later.</p>
{content}
</main>
</body>
</html>"""
    return HTMLResponse(markup, headers={"Cache-Control": "no-store"})
