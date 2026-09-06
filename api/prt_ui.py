from pathlib import Path
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, Response, RedirectResponse, StreamingResponse
from services import discord_service
from utils.config import settings
router=APIRouter(); ASSET_DIR=Path(__file__).resolve().parent

def _html(name):
    html=(ASSET_DIR/name).read_text(encoding="utf-8")
    return HTMLResponse(html.replace("{{PITMARK_VERSION}}",settings.app_version),headers={"Cache-Control":"no-store"})

@router.get("/prt",response_class=HTMLResponse,include_in_schema=False)
def prt_home(): return _html("prt.html")
@router.get("/prt/support",response_class=HTMLResponse,include_in_schema=False)
def prt_support(): return _html("prt-support.html")

@router.get("/prt/apply",include_in_schema=False)
def prt_apply():
    target=(settings.prt_early_access_form_url or "").strip()
    if target.startswith("https://docs.google.com/forms/") or target.startswith("https://forms.gle/"):
        return RedirectResponse(url=target,status_code=302)
    return RedirectResponse(url="/prt?apply=unavailable",status_code=302)
@router.get("/prt.css",include_in_schema=False)
def prt_css(): return Response((ASSET_DIR/"prt.css").read_text(encoding="utf-8"),media_type="text/css",headers={"Cache-Control":"no-store"})
@router.get("/prt.js",include_in_schema=False)
def prt_js(): return Response((ASSET_DIR/"prt.js").read_text(encoding="utf-8"),media_type="application/javascript",headers={"Cache-Control":"no-store"})
@router.get("/prt-support.css",include_in_schema=False)
def prt_support_css(): return Response((ASSET_DIR/"prt-support.css").read_text(encoding="utf-8"),media_type="text/css",headers={"Cache-Control":"no-store"})
@router.get("/prt-support.js",include_in_schema=False)
def prt_support_js(): return Response((ASSET_DIR/"prt-support.js").read_text(encoding="utf-8"),media_type="application/javascript",headers={"Cache-Control":"no-store"})
@router.get("/api/prt/status")
def prt_status():
    discord=discord_service.status()
    return {"service":"Pitmark Racing Tools","version":settings.app_version,"early_access":True,"discord":{"configured":bool(discord.get("configured")),"bot_install_available":bool(discord.get("install_url"))},"support_email":"prt@pitmarkracing.com"}
@router.get("/prt-logo.png",include_in_schema=False)
def prt_logo(): return FileResponse(ASSET_DIR/"pitmark_logo_wide.png",media_type="image/png")
@router.get("/prt-current-logo.png",include_in_schema=False)
def prt_current_logo(): return FileResponse(ASSET_DIR/"prt-current-logo.png",media_type="image/png")
@router.get("/prt-tools-logo.png",include_in_schema=False)
def prt_tools_logo(): return FileResponse(ASSET_DIR/"prt-tools-logo.png",media_type="image/png")
@router.get("/prt-app-preview.png",include_in_schema=False)
def prt_app_preview(): return FileResponse(ASSET_DIR/"prt-app-preview.png",media_type="image/png")
@router.get("/pitmark-cloud-badge.png",include_in_schema=False)
def pitmark_cloud_badge(): return FileResponse(ASSET_DIR/"pitmark-cloud-badge.png",media_type="image/png")
@router.get("/pitmark-shield-badge.png",include_in_schema=False)
def pitmark_shield_badge(): return FileResponse(ASSET_DIR/"pitmark-shield-badge.png",media_type="image/png")


def _r2_object_url(key: str) -> str:
    if not bool(getattr(settings, "prt_r2_enabled", False)):
        return ""
    base = (getattr(settings, "prt_r2_public_base_url", "") or "").strip().rstrip("/")
    normalized_key = (key or "").strip().lstrip("/")
    return f"{base}/{normalized_key}" if base and normalized_key else ""


def _r2_installer_key() -> str:
    return (getattr(settings, "prt_r2_installer_key", "prt/PRT-Setup-Latest.exe") or "").strip().lstrip("/")


def _r2_installer_url() -> str:
    return _r2_object_url(_r2_installer_key())


def _r2_manifest_url() -> str:
    installer_key = _r2_installer_key()
    prefix = installer_key.rsplit("/", 1)[0] if "/" in installer_key else ""
    manifest_key = f"{prefix}/latest.json" if prefix else "latest.json"
    return _r2_object_url(manifest_key)


def _fetch_r2_manifest(target: str) -> bytes:
    request = UrlRequest(target, headers={"User-Agent": "PitmarkCloud-R2-Bridge/1.0"})
    with urlopen(request, timeout=15) as upstream:
        data = upstream.read((64 * 1024) + 1)
        if len(data) > 64 * 1024:
            raise ValueError("R2 update manifest exceeded the allowed size")
        return data


def _open_r2_installer(target: str):
    request = UrlRequest(target, headers={"User-Agent": "PitmarkCloud-R2-Bridge/1.0"})
    return urlopen(request, timeout=45)


def _stream_upstream(upstream):
    try:
        while True:
            chunk = upstream.read(1024 * 1024)
            if not chunk:
                break
            yield chunk
    finally:
        upstream.close()


def _is_legacy_prt_updater(request: Request) -> bool:
    return "pitmarkracingtools-updater/" in (request.headers.get("user-agent") or "").lower()


# control_center_ui historically owned the stable /downloads routes. During module
# import, remove only those two release routes so this implementation is the single
# source of truth. The compatibility bridge below is intentional: PRT <= 0.16.77
# disables HTTP redirects, so the stable Pitmark URLs must return 200 to the updater.
try:
    from api import control_center_ui as _control_center_ui
    _release_paths = {"/downloads/PRT-Setup-Latest.exe", "/downloads/latest.json"}
    _control_center_ui.router.routes[:] = [
        route for route in _control_center_ui.router.routes
        if getattr(route, "path", "") not in _release_paths
    ]
except Exception:
    _control_center_ui = None


@router.get("/downloads/PRT-Setup-Latest.exe",include_in_schema=False)
def prt_windows_installer(request: Request):
    target = _r2_installer_url()
    if target:
        # Browsers/download links can go straight to R2 and avoid Render egress.
        # Existing PRT updaters explicitly reject 3xx responses, so proxy only those
        # requests until a redirect-capable updater has reached the tester base.
        if not _is_legacy_prt_updater(request):
            return RedirectResponse(url=target,status_code=307,headers={"Cache-Control":"no-store"})
        try:
            upstream = _open_r2_installer(target)
            headers = {"Cache-Control": "no-store", "Content-Disposition": 'attachment; filename="PRT-Setup-Latest.exe"'}
            content_length = upstream.headers.get("Content-Length")
            if content_length:
                headers["Content-Length"] = content_length
            return StreamingResponse(
                _stream_upstream(upstream),
                media_type="application/vnd.microsoft.portable-executable",
                headers=headers,
            )
        except Exception:
            return Response(
                "PRT installer is temporarily unavailable. Try again shortly.",
                status_code=503,
                media_type="text/plain",
                headers={"Cache-Control":"no-store"},
            )

    local = ASSET_DIR / "downloads" / "PRT-Setup-Latest.exe"
    if local.exists():
        return FileResponse(
            local,
            media_type="application/vnd.microsoft.portable-executable",
            filename="PRT-Setup-Latest.exe",
            headers={"Cache-Control":"no-store"},
        )
    return Response("PRT installer is being published. Try again shortly.",status_code=503,media_type="text/plain",headers={"Cache-Control":"no-store"})


@router.get("/downloads/latest.json",include_in_schema=False)
def prt_update_manifest():
    # Manifest requests must return 200 from the stable Pitmark host because released
    # PRT clients intentionally disable redirects. Pull the tiny manifest from R2 so it
    # cannot drift behind the installer while preserving the trusted Pitmark URL.
    target = _r2_manifest_url()
    if target:
        try:
            return Response(
                _fetch_r2_manifest(target),
                media_type="application/json",
                headers={"Cache-Control":"no-store"},
            )
        except Exception:
            pass

    local = ASSET_DIR / "downloads" / "latest.json"
    if local.exists():
        return FileResponse(local,media_type="application/json",headers={"Cache-Control":"no-store"})
    return Response("PRT update manifest is being published. Try again shortly.",status_code=503,media_type="text/plain",headers={"Cache-Control":"no-store"})


@router.get("/api/discord/install/launch",include_in_schema=False)
def prt_discord_install_launch():
    value=discord_service.install_url()
    if not value:return RedirectResponse(url="/prt?discord=unavailable",status_code=302)
    return RedirectResponse(url=value,status_code=302)


# Public Pitmark link-in-bio hub lives under the existing public PRT UI router.
from api import links_ui
router.include_router(links_ui.router)
