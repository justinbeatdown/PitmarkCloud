from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent


@router.get('/prt-timmy-logo.jpg', include_in_schema=False)
def timmy_neutron_logo():
    return FileResponse(
        ASSET_DIR / 'timmyneutron020-logo.jpg',
        media_type='image/jpeg',
        headers={'Cache-Control': 'public, max-age=3600'},
    )
