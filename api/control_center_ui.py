from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, Response

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent

@router.get('/control', response_class=HTMLResponse, include_in_schema=False)
def control():
    return HTMLResponse((ASSET_DIR / 'control_center.html').read_text(encoding='utf-8'))

@router.get('/control.css', include_in_schema=False)
def control_css():
    return Response((ASSET_DIR / 'control_center.css').read_text(encoding='utf-8'), media_type='text/css')

@router.get('/control.js', include_in_schema=False)
def control_js():
    return Response((ASSET_DIR / 'control_center.js').read_text(encoding='utf-8'), media_type='application/javascript')

@router.get('/control-logo-wide.png', include_in_schema=False)
def control_logo_wide():
    return FileResponse(ASSET_DIR / 'pitmark_logo_wide.png', media_type='image/png')

@router.get('/control-logo-badge.png', include_in_schema=False)
def control_logo_badge():
    return FileResponse(ASSET_DIR / 'pitmark_badge.png', media_type='image/png')
