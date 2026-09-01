from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from services.control_access import require_permission
from services.prt_analytics import record_download, summary
from utils.security import enforce_rate_limit

router = APIRouter()


class DownloadPing(BaseModel):
    source: str = "website"
    version: str = ""


@router.get("/summary")
def analytics_summary(request: Request):
    require_permission(request, "analytics")
    return summary()


@router.post("/download")
def track_download(req: DownloadPing, request: Request):
    # Public metric endpoint intended for the PRT download button/installer.
    # It records no IP, user agent, email, or Discord identity.
    enforce_rate_limit(request, "prt-download-analytics", 40, 300)
    return record_download(source=req.source, version=req.version)
