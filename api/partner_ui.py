from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent


def _html(name: str) -> HTMLResponse:
    return HTMLResponse(
        (ASSET_DIR / name).read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/partners", response_class=HTMLResponse, include_in_schema=False)
def partner_guide():
    return _html("partner_guide.html")


@router.get("/partner-guide", response_class=HTMLResponse, include_in_schema=False)
def partner_guide_alias():
    return _html("partner_guide.html")


@router.get("/partner-guide.css", include_in_schema=False)
def partner_guide_css():
    return Response(
        (ASSET_DIR / "partner_guide.css").read_text(encoding="utf-8"),
        media_type="text/css",
        headers={"Cache-Control": "no-store"},
    )
