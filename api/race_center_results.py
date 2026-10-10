"""Source-backed public results and protected internal import endpoint."""
import os
import secrets
from datetime import date
from typing import Literal
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, HttpUrl, model_validator
from pathlib import Path
from services import race_center_results as store
from utils.security import enforce_rate_limit

router = APIRouter()

class Entry(BaseModel):
    finish: int = Field(ge=1, le=5000)
    start: int | None = Field(default=None, ge=1, le=5000)
    driver: str = Field(min_length=1, max_length=180)
    car_number: str | None = Field(default=None, max_length=32)
    laps: int | None = Field(default=None, ge=0, le=100000)
    result_status: Literal["finished", "dnf", "dns", "dq", "unknown"] = "finished"

class Session(BaseModel):
    class_name: str = Field(min_length=1, max_length=160)
    session_name: str = Field(min_length=1, max_length=160)
    entries: list[Entry] = Field(min_length=1, max_length=500)
    @model_validator(mode="after")
    def validate_finishes(self):
        finishes = [e.finish for e in self.entries]
        if len(finishes) != len(set(finishes)):
            raise ValueError("Finishing positions must be unique within a session")
        return self

class VerifiedEvent(BaseModel):
    source_name: str = Field(min_length=2, max_length=180)
    external_id: str = Field(min_length=1, max_length=180)
    source_url: HttpUrl
    track: str = Field(min_length=2, max_length=180)
    series: str = Field(min_length=2, max_length=180)
    event_name: str = Field(min_length=2, max_length=220)
    race_date: date
    status: Literal["official", "provisional"]
    sessions: list[Session] = Field(min_length=1, max_length=100)
    @model_validator(mode="after")
    def validate_sessions(self):
        pairs = [(s.class_name.casefold(), s.session_name.casefold()) for s in self.sessions]
        if len(pairs) != len(set(pairs)):
            raise ValueError("Duplicate class/session")
        return self

@router.get("/api/public/race-center/results", include_in_schema=False)
def results_index(request: Request, q: str = "", track: str = "", series: str = "", limit: int = 30):
    enforce_rate_limit(request, "race-center-results-list", 120)
    return {"results": store.list_events(q[:120], track[:120], series[:120], limit)}

@router.get("/api/public/race-center/results/driver", include_in_schema=False)
def results_driver(request: Request, name: str, limit: int = 20):
    enforce_rate_limit(request, "race-center-results-driver", 120)
    if not name.strip() or len(name) > 180:
        raise HTTPException(400, "A driver name is required")
    return {"results": store.driver_results(name, limit)}

@router.get("/api/public/race-center/results/{key}", include_in_schema=False)
def results_event(request: Request, key: str):
    enforce_rate_limit(request, "race-center-results-event", 120)
    result = store.get_event(key)
    if result is None:
        raise HTTPException(404, "Results not found")
    return {"event": result}

@router.post("/api/internal/race-center/results/import", include_in_schema=False)
def import_results(request: Request, body: VerifiedEvent, x_pitmark_results_token: str | None = Header(default=None)):
    enforce_rate_limit(request, "race-center-results-import", 30)
    expected = os.getenv("PITMARK_RESULTS_IMPORT_TOKEN", "")
    if not expected or not x_pitmark_results_token or not secrets.compare_digest(expected, x_pitmark_results_token):
        raise HTTPException(403, "Importer access denied")
    data = body.model_dump(mode="json")
    data["race_date"] = body.race_date
    for session in data["sessions"]:
        for entry in session["entries"]:
            entry["result_status"] = entry.pop("result_status")
    return {"key": store.upsert_verified(data), "imported": True}

@router.get("/race-center/results", response_class=HTMLResponse, include_in_schema=False)
def results_page():
    page = (Path(__file__).resolve().parent / "race_center_results.html").read_text(encoding="utf-8")
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})
