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

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
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
        data = [json.loads(row.data_json) for row in rows]
    finished = [row for row in data if int(row.get("finishing_position") or 0) > 0]
    return {
        "private": True, "sessions": len(data),
        "laps": sum(int(row.get("laps") or 0) for row in data),
        "wins": sum(int(row.get("finishing_position") or 0) == 1 for row in finished),
        "top_fives": sum(int(row.get("finishing_position") or 0) <= 5 for row in finished),
        "best_lap": min((float(row.get("best_lap") or 0) for row in data if float(row.get("best_lap") or 0) > 0), default=0),
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


@router.get("/race-center/prt-connect", response_class=HTMLResponse)
def prt_connect_page(request: Request, code: str = ""):
    account = race_center_accounts.account_from_request(request)
    clean = html.escape(re.sub(r"[^A-Z0-9]", "", (code or "").upper())[:8], quote=True)
    account_label = html.escape(account.display_name or account.email, quote=True) if account else ""
    signed = bool(account)
    form = (
        '<p>Signed in as <b>' + account_label + '</b></p>'
        '<label>Code shown in PRT <input id="code" maxlength="8" value="' + clean + '"></label>'
        '<p><label><input id="consent" type="checkbox"> Allow PRT to upload my selected race history as private data.</label></p>'
        '<button id="approve">Approve this computer</button><p id="feedback" role="status"></p>'
        '<script>document.getElementById("approve").onclick=async()=>{const b=document.getElementById("approve");b.disabled=true;try{const r=await fetch("/api/public/race-center/prt/link/approve",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({code:document.getElementById("code").value,consent_private_history:document.getElementById("consent").checked})});const j=await r.json();document.getElementById("feedback").textContent=r.ok?"PRT connected. Return to the desktop app.":(j.detail||"Connection failed.");}catch(e){document.getElementById("feedback").textContent="Connection failed. Try again.";}finally{b.disabled=false;}};</script>'
    ) if signed else (
        '<p>Sign in to your Race Center account, then return to this page to approve PRT.</p>'
        '<a href="/race-center">Sign in / create a Race Center account</a>'
    )
    return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Connect PRT — Race Center</title><style>body{font:16px system-ui;background:#0a0d10;color:#fff;max-width:590px;margin:48px auto;padding:22px}h1{color:#ff5500}input,button{font:inherit;padding:12px;background:#181d23;border:1px solid #535860;color:white}button{background:#ff5500;color:#100900;font-weight:bold;cursor:pointer}p{line-height:1.5}</style><h1>Connect PRT to Race Center</h1><p>Approve only the PRT application running on your computer. Race sessions remain private unless you later choose to publish them. You can revoke this device and delete your history.</p>' + form + '</html>')
