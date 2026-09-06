from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, Response, RedirectResponse
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


def _r2_installer_url() -> str:
    if not bool(getattr(settings, "prt_r2_enabled", False)):
        return ""
    base = (getattr(settings, "prt_r2_public_base_url", "") or "").strip().rstrip("/")
    key = (getattr(settings, "prt_r2_installer_key", "prt/PRT-Setup-Latest.exe") or "").strip().lstrip("/")
    return f"{base}/{key}" if base and key else ""


# control_center_ui historically owned the stable /downloads installer route. During
# module import, remove only that one route so the R2-aware replacement below is the
# single source of truth. The tiny latest.json manifest stays served locally by Cloud.
try:
    from api import control_center_ui as _control_center_ui
    _control_center_ui.router.routes[:] = [
        route for route in _control_center_ui.router.routes
        if getattr(route, "path", "") != "/downloads/PRT-Setup-Latest.exe"
    ]
except Exception:
    _control_center_ui = None


@router.get("/downloads/PRT-Setup-Latest.exe",include_in_schema=False)
def prt_windows_installer():
    target = _r2_installer_url()
    if target:
        return RedirectResponse(url=target,status_code=307,headers={"Cache-Control":"no-store"})

    # Safe migration fallback: if R2/custom-domain configuration is not live yet, keep
    # serving the repository copy so an early Cloud deploy cannot strand existing testers.
    local = ASSET_DIR / "downloads" / "PRT-Setup-Latest.exe"
    if local.exists():
        return FileResponse(
            local,
            media_type="application/vnd.microsoft.portable-executable",
            filename="PRT-Setup-Latest.exe",
            headers={"Cache-Control":"no-store"},
        )
    return Response("PRT installer is being published. Try again shortly.",status_code=503,media_type="text/plain",headers={"Cache-Control":"no-store"})

@router.get("/api/discord/install/launch",include_in_schema=False)
def prt_discord_install_launch():
    value=discord_service.install_url()
    if not value:return RedirectResponse(url="/prt?discord=unavailable",status_code=302)
    return RedirectResponse(url=value,status_code=302)


# Public Pitmark link-in-bio hub lives under the existing public PRT UI router.
from api import links_ui
router.include_router(links_ui.router)
