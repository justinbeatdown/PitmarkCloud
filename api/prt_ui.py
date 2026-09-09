from pathlib import Path
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from services import discord_service
from services.prt_applications import record_funnel_event, submit_application
from utils.config import settings
from utils.security import enforce_rate_limit

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent

_CAMPAIGN = "prt_raceproof_202609"
_CAMPAIGN_SOURCES = {"facebook", "tiktok", "instagram", "x", "discord", "league", "creator"}
_CAMPAIGN_ASSETS = {"race", "feedback", "invite"}
_PREVIEW_BOT_TOKENS = (
    "facebookexternalhit",
    "facebot",
    "meta-externalagent",
    "meta-externalfetcher",
    "twitterbot",
    "discordbot",
    "slackbot",
    "linkedinbot",
    "googlebot",
    "bingbot",
)
_ROB_PROOF_URL = (
    "https://m.facebook.com/story.php?"
    "story_fbid=pfbid0UcrWErhjzdsWgJNcyfciUctEqgDF5dsV9kpDtJaT6u9cTmpiPQfDUBsLiwhNJriol"
    "&id=61593441036636"
)


def _html(name: str) -> HTMLResponse:
    html = (ASSET_DIR / name).read_text(encoding="utf-8")
    return HTMLResponse(
        html.replace("{{PITMARK_VERSION}}", settings.app_version),
        headers={"Cache-Control": "no-store"},
    )


def _is_preview_bot(request: Request) -> bool:
    user_agent = (request.headers.get("user-agent") or "").lower()
    return any(token in user_agent for token in _PREVIEW_BOT_TOKENS)


def _campaign_context(
    *,
    campaign: str = "",
    source: str = "",
    asset: str = "",
) -> tuple[str, str, str]:
    clean_campaign = _CAMPAIGN if (campaign or "").strip() == _CAMPAIGN else ""
    clean_source = (source or "").strip().lower()
    clean_asset = (asset or "").strip().lower()
    if not clean_campaign or clean_source not in _CAMPAIGN_SOURCES or clean_asset not in _CAMPAIGN_ASSETS:
        return "", "website", ""
    return clean_campaign, clean_source, clean_asset


def _request_campaign_context(request: Request) -> tuple[str, str, str]:
    return _campaign_context(
        campaign=request.query_params.get("utm_campaign", ""),
        source=request.query_params.get("utm_source", ""),
        asset=request.query_params.get("utm_content", ""),
    )


@router.get("/prt", response_class=HTMLResponse, include_in_schema=False)
def prt_home():
    return _html("prt.html")


@router.get("/prt/support", response_class=HTMLResponse, include_in_schema=False)
def prt_support():
    return _html("prt-support.html")


@router.get("/prt/apply", response_class=HTMLResponse, include_in_schema=False)
def prt_apply(request: Request):
    if not _is_preview_bot(request):
        campaign, source, asset = _request_campaign_context(request)
        try:
            record_funnel_event(
                stage="apply_view",
                placement="quick-apply",
                campaign=campaign,
                source=source,
                asset=asset,
            )
        except Exception:
            pass
    return _html("prt-apply.html")


@router.get("/prt/apply/google", include_in_schema=False)
def prt_apply_google(request: Request):
    target = (settings.prt_early_access_form_url or "").strip()
    if not (target.startswith("https://docs.google.com/forms/") or target.startswith("https://forms.gle/")):
        return RedirectResponse(url="/prt?apply=unavailable", status_code=302)
    if not _is_preview_bot(request):
        campaign, source, asset = _request_campaign_context(request)
        try:
            record_funnel_event(
                stage="google_form_fallback",
                placement="quick-apply-fallback",
                campaign=campaign,
                source=source,
                asset=asset,
            )
        except Exception:
            pass
    return RedirectResponse(url=target, status_code=302, headers={"Cache-Control": "no-store"})


@router.get("/prt/proof/rob", include_in_schema=False)
def prt_rob_proof(request: Request):
    if not _is_preview_bot(request):
        campaign, source, asset = _request_campaign_context(request)
        try:
            record_funnel_event(
                stage="proof_click",
                placement="rob-race-proof",
                campaign=campaign,
                source=source,
                asset=asset,
            )
        except Exception:
            pass
    return RedirectResponse(url=_ROB_PROOF_URL, status_code=302, headers={"Cache-Control": "no-store"})


class FunnelPing(BaseModel):
    stage: str = "cta_click"
    placement: str = ""
    campaign: str = ""
    source: str = "website"
    asset: str = ""


class QuickApplyRequest(BaseModel):
    full_name: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=200)
    discord_username: str = Field(default="", max_length=100)
    iracing_name: str = Field(default="", max_length=120)
    disciplines: list[str] = Field(default_factory=list, max_length=12)
    race_frequency: str = Field(default="", max_length=80)
    current_tools: str = Field(default="", max_length=320)
    goals: str = Field(default="", max_length=1200)
    can_test: bool = False
    bug_reports: bool = False
    honest_feedback: bool = False
    expectations_agreed: bool = False
    company_website: str = Field(default="", max_length=300)
    campaign: str = ""
    source: str = "website"
    asset: str = ""
    placement: str = "quick-apply"


@router.post("/api/prt/funnel")
def prt_funnel_ping(req: FunnelPing, request: Request):
    enforce_rate_limit(request, "prt-funnel-analytics", 80, 300)
    if _is_preview_bot(request):
        return {"ok": True, "ignored": True}
    if (req.stage or "").strip() != "cta_click":
        return {"ok": True, "ignored": True}
    campaign, source, asset = _campaign_context(
        campaign=req.campaign,
        source=req.source,
        asset=req.asset,
    )
    return record_funnel_event(
        stage="cta_click",
        placement=(req.placement or "")[:60],
        campaign=campaign,
        source=source,
        asset=asset,
    )


@router.post("/api/prt/apply")
def prt_quick_apply(req: QuickApplyRequest, request: Request):
    enforce_rate_limit(request, "prt-quick-apply", 8, 900)
    # Simple honeypot. Return a normal-looking success so bots get no useful signal.
    if (req.company_website or "").strip():
        return {"ok": True, "duplicate": False, "application_id": None}

    campaign, source, asset = _campaign_context(
        campaign=req.campaign,
        source=req.source,
        asset=req.asset,
    )
    try:
        return submit_application(
            full_name=req.full_name,
            email=req.email,
            discord_username=req.discord_username,
            iracing_name=req.iracing_name,
            disciplines=", ".join(x.strip() for x in req.disciplines if x and x.strip())[:320],
            race_frequency=req.race_frequency,
            current_tools=req.current_tools,
            goals=req.goals,
            can_test=req.can_test,
            bug_reports=req.bug_reports,
            honest_feedback=req.honest_feedback,
            expectations_agreed=req.expectations_agreed,
            campaign=campaign,
            source=source,
            asset=asset,
            placement=(req.placement or "quick-apply")[:60],
        )
    except ValueError as exc:
        return JSONResponse(
            {"detail": str(exc)},
            status_code=400,
            headers={"Cache-Control": "no-store"},
        )


@router.get("/prt.css", include_in_schema=False)
def prt_css():
    return Response(
        (ASSET_DIR / "prt.css").read_text(encoding="utf-8"),
        media_type="text/css",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/prt-growth.css", include_in_schema=False)
def prt_growth_css():
    return Response(
        (ASSET_DIR / "prt-growth.css").read_text(encoding="utf-8"),
        media_type="text/css",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/prt.js", include_in_schema=False)
def prt_js():
    return Response(
        (ASSET_DIR / "prt.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/prt-growth.js", include_in_schema=False)
def prt_growth_js():
    return Response(
        (ASSET_DIR / "prt-growth.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/prt-apply.js", include_in_schema=False)
def prt_apply_js():
    return Response(
        (ASSET_DIR / "prt-apply.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/prt-downloads.js", include_in_schema=False)
def prt_downloads_js():
    return Response(
        (ASSET_DIR / "prt-downloads.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/prt-support.css", include_in_schema=False)
def prt_support_css():
    return Response(
        (ASSET_DIR / "prt-support.css").read_text(encoding="utf-8"),
        media_type="text/css",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/prt-support.js", include_in_schema=False)
def prt_support_js():
    return Response(
        (ASSET_DIR / "prt-support.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/prt/status")
def prt_status():
    discord = discord_service.status()
    return {
        "service": "Pitmark Racing Tools",
        "version": settings.app_version,
        "early_access": True,
        "quick_apply": True,
        "discord": {
            "configured": bool(discord.get("configured")),
            "bot_install_available": bool(discord.get("install_url")),
        },
        "support_email": "prt@pitmarkracing.com",
    }


@router.get("/prt-logo.png", include_in_schema=False)
def prt_logo():
    return FileResponse(ASSET_DIR / "pitmark_logo_wide.png", media_type="image/png")


@router.get("/prt-current-logo.png", include_in_schema=False)
def prt_current_logo():
    return FileResponse(ASSET_DIR / "prt-current-logo.png", media_type="image/png")


@router.get("/prt-tools-logo.png", include_in_schema=False)
def prt_tools_logo():
    return FileResponse(ASSET_DIR / "prt-tools-logo.png", media_type="image/png")


@router.get("/prt-app-preview.png", include_in_schema=False)
def prt_app_preview():
    return FileResponse(ASSET_DIR / "prt-app-preview.png", media_type="image/png")


@router.get("/pitmark-cloud-badge.png", include_in_schema=False)
def pitmark_cloud_badge():
    return FileResponse(ASSET_DIR / "pitmark-cloud-badge.png", media_type="image/png")


@router.get("/pitmark-shield-badge.png", include_in_schema=False)
def pitmark_shield_badge():
    return FileResponse(ASSET_DIR / "pitmark-shield-badge.png", media_type="image/png")


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
        route
        for route in _control_center_ui.router.routes
        if getattr(route, "path", "") not in _release_paths
    ]
except Exception:
    _control_center_ui = None


@router.get("/downloads/PRT-Setup-Latest.exe", include_in_schema=False)
def prt_windows_installer(request: Request):
    target = _r2_installer_url()
    if target:
        # Browsers/download links can go straight to R2 and avoid Render egress.
        # Existing PRT updaters explicitly reject 3xx responses, so proxy only those
        # requests until a redirect-capable updater has reached the tester base.
        if not _is_legacy_prt_updater(request):
            return RedirectResponse(url=target, status_code=307, headers={"Cache-Control": "no-store"})
        try:
            upstream = _open_r2_installer(target)
            headers = {
                "Cache-Control": "no-store",
                "Content-Disposition": 'attachment; filename="PRT-Setup-Latest.exe"',
            }
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
                headers={"Cache-Control": "no-store"},
            )

    local = ASSET_DIR / "downloads" / "PRT-Setup-Latest.exe"
    if local.exists():
        return FileResponse(
            local,
            media_type="application/vnd.microsoft.portable-executable",
            filename="PRT-Setup-Latest.exe",
            headers={"Cache-Control": "no-store"},
        )
    return Response(
        "PRT installer is being published. Try again shortly.",
        status_code=503,
        media_type="text/plain",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/downloads/latest.json", include_in_schema=False)
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
                headers={"Cache-Control": "no-store"},
            )
        except Exception:
            pass

    local = ASSET_DIR / "downloads" / "latest.json"
    if local.exists():
        return FileResponse(local, media_type="application/json", headers={"Cache-Control": "no-store"})
    return Response(
        "PRT update manifest is being published. Try again shortly.",
        status_code=503,
        media_type="text/plain",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/discord/install/launch", include_in_schema=False)
def prt_discord_install_launch():
    value = discord_service.install_url()
    if not value:
        return RedirectResponse(url="/prt?discord=unavailable", status_code=302)
    return RedirectResponse(url=value, status_code=302)


# Public Pitmark link-in-bio hub lives under the existing public PRT UI router.
from api import links_ui

router.include_router(links_ui.router)
