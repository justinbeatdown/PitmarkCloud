from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent


def _javascript(filename: str) -> Response:
    return Response(
        (ASSET_DIR / filename).read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/control-center-app.js", include_in_schema=False)
def control_center_app_js():
    return _javascript("control_center_app.js")


@router.get("/control-center-api.js", include_in_schema=False)
def control_center_api_js():
    return _javascript("control_center_api.js")


@router.get("/control-center-views.js", include_in_schema=False)
def control_center_views_js():
    return _javascript("control_center_views.js")
