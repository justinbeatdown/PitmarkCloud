from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

from services.control_auth import user_from_request

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent


@router.get('/control', response_class=HTMLResponse, include_in_schema=False)
def control(request: Request):
    filename = 'control_center.html' if user_from_request(request) else 'control_login.html'
    return HTMLResponse((ASSET_DIR / filename).read_text(encoding='utf-8'))


@router.get('/control.css', include_in_schema=False)
def control_css():
    return Response((ASSET_DIR / 'control_center.css').read_text(encoding='utf-8'), media_type='text/css')


@router.get('/control.js', include_in_schema=False)
def control_js():
    return Response((ASSET_DIR / 'control_center.js').read_text(encoding='utf-8'), media_type='application/javascript')


@router.get('/control-login.js', include_in_schema=False)
def control_login_js():
    return Response((ASSET_DIR / 'control_login.js').read_text(encoding='utf-8'), media_type='application/javascript')


@router.get('/control/mobile', response_class=HTMLResponse, include_in_schema=False)
def control_mobile(request: Request):
    filename = 'control_mobile.html' if user_from_request(request) else 'control_mobile_login.html'
    return HTMLResponse((ASSET_DIR / filename).read_text(encoding='utf-8'))


@router.get('/control-mobile.css', include_in_schema=False)
def control_mobile_css():
    return Response((ASSET_DIR / 'control_mobile.css').read_text(encoding='utf-8'), media_type='text/css')


@router.get('/control-mobile.js', include_in_schema=False)
def control_mobile_js():
    return Response((ASSET_DIR / 'control_mobile.js').read_text(encoding='utf-8'), media_type='application/javascript')


@router.get('/control-mobile-login.js', include_in_schema=False)
def control_mobile_login_js():
    return Response((ASSET_DIR / 'control_mobile_login.js').read_text(encoding='utf-8'), media_type='application/javascript')


@router.get('/control.webmanifest', include_in_schema=False)
def control_manifest():
    return Response((ASSET_DIR / 'control.webmanifest').read_text(encoding='utf-8'), media_type='application/manifest+json')


@router.get('/control-sw.js', include_in_schema=False)
def control_sw():
    return Response((ASSET_DIR / 'control_sw.js').read_text(encoding='utf-8'), media_type='application/javascript', headers={'Service-Worker-Allowed':'/control/'})


@router.get('/control-logo-wide.png', include_in_schema=False)
def control_logo_wide():
    return FileResponse(ASSET_DIR / 'pitmark_logo_wide.png', media_type='image/png')


@router.get('/control-logo-badge.png', include_in_schema=False)
def control_logo_badge():
    return FileResponse(ASSET_DIR / 'pitmark_badge.png', media_type='image/png')
