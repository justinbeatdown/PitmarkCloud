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


@router.get("/links", response_class=HTMLResponse, include_in_schema=False)
def pitmark_links():
    return _html("links.html")


@router.get("/links.css", include_in_schema=False)
def pitmark_links_css():
    return Response(
        (ASSET_DIR / "links.css").read_text(encoding="utf-8"),
        media_type="text/css",
        headers={"Cache-Control": "no-store"},
    )
