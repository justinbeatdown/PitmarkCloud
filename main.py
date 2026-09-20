from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import asyncio
import ctypes
import gc
import hmac
import json
import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from utils.security import SecurityHeadersMiddleware, security_summary

from api import device, discord, discord_bot, entitlements, health, live_session, results, shopify, control_center, control_center_2026, control_center_v19, control_center_v195, control_access_v191, control_center_ui, social_publish, social_context_v191, social_operator, email_center, email_center_v19, prt_analytics_v191, content_tools, prt_ui, prt_testimonial_asset, early_access_admin, astra_director
from utils.config import settings
from utils.logger import configure_logging
from services import discord_gateway_service, prt_access_bans, prt_licensing_store
from services.database import init_database, database_status
from services.founders_race_activation import backfill_hub_emails
from services.autopilot_intelligence import scheduler_loop
from services.autopilot_multiplatform import scheduler_loop as multiplatform_scheduler_loop
from services.research_agent import research_worker_loop
from services.social_publish_worker import social_publish_worker_loop
from services.social_operator import social_operator_loop
from services.shield_mail_cleanup import purge_orphaned_mail_events
from services.shield_mail_worker import sync_gmail_shield_worker
from services.control_access import access_from_request, permission_for_path

configure_logging()
log = logging.getLogger("pitmark.runtime")


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name) or str(default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _current_rss_mb() -> float | None:
    """Return current resident memory on Linux/Render without adding psutil."""
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as handle:
            resident_pages = int(handle.read().split()[1])
        return (resident_pages * os.sysconf("SC_PAGE_SIZE")) / (1024 * 1024)
    except (OSError, ValueError, IndexError):
        return None


def _trim_process_memory() -> tuple[int, bool]:
    """Collect Python cycles and ask glibc to return free heap pages to Render."""
    collected = gc.collect()
    trimmed = False
    try:
        libc = ctypes.CDLL("libc.so.6")
        malloc_trim = libc.malloc_trim
        malloc_trim.argtypes = [ctypes.c_size_t]
        malloc_trim.restype = ctypes.c_int
        trimmed = bool(malloc_trim(0))
    except (OSError, AttributeError):
        pass
    return collected, trimmed


async def runtime_maintenance_loop() -> None:
    interval = _env_int("PITMARK_MEMORY_TRIM_SECONDS", 600, 300, 3600)
    while True:
        await asyncio.sleep(interval)
        try:
            collected, trimmed = await asyncio.to_thread(_trim_process_memory)
            rss = _current_rss_mb()
            if rss is None:
                log.info("Runtime memory maintenance: gc=%s malloc_trim=%s", collected, trimmed)
            else:
                log.info(
                    "Runtime memory maintenance: rss=%.1f MB gc=%s malloc_trim=%s",
                    rss,
                    collected,
                    trimmed,
                )
        except Exception:  # noqa: BLE001 - maintenance must never stop Cloud
            log.exception("Runtime memory maintenance failed")


async def gmail_sync_loop() -> None:
    interval = _env_int("PITMARK_GMAIL_SYNC_SECONDS", 120, 120, 3600)
    limit = _env_int("PITMARK_GMAIL_SYNC_LIMIT", 25, 5, 25)
    while True:
        try:
            result = await asyncio.to_thread(sync_gmail_shield_worker, limit)
            if result.get("synced") or result.get("shield_protected"):
                log.info(
                    "Gmail/Shield sync: checked=%s synced=%s protected=%s",
                    result.get("checked", 0),
                    result.get("synced", 0),
                    result.get("shield_protected", 0),
                )
        except Exception as exc:
            log.warning("Google Workspace Gmail sync failed: %s", exc)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    background_threads = _env_int("PITMARK_BACKGROUND_THREADS", 4, 2, 6)
    executor = ThreadPoolExecutor(
        max_workers=background_threads,
        thread_name_prefix="pitmark-bg",
    )
    loop.set_default_executor(executor)

    init_database()
    maintenance_invite_id = (os.getenv("PRT_ONE_TIME_REISSUE_INVITE_ID") or "").strip()
    maintenance_reissue_hash = (os.getenv("PRT_ONE_TIME_REISSUE_CODE_HASH") or "").strip()
    maintenance_reissue_hint = (os.getenv("PRT_ONE_TIME_REISSUE_CODE_HINT") or "").strip()
    if maintenance_invite_id and maintenance_reissue_hash and maintenance_reissue_hint:
        try:
            maintenance_result = await asyncio.to_thread(
                prt_licensing_store.reissue_early_access_invite_prehashed,
                int(maintenance_invite_id),
                code_hash=maintenance_reissue_hash,
                code_hint=maintenance_reissue_hint,
            )
            if maintenance_result is None:
                log.error("PRT Early Access maintenance reissue invite #%s was not found.", maintenance_invite_id)
            elif maintenance_result.get("already_applied"):
                log.info("PRT Early Access maintenance reissue already applied for invite #%s.", maintenance_invite_id)
            else:
                log.warning("PRT Early Access maintenance reissue applied for invite #%s.", maintenance_invite_id)
        except Exception:
            log.exception("PRT Early Access maintenance reissue failed for invite #%s.", maintenance_invite_id)
    if settings.astra_director_self_test:
        try:
            from services.astra_director import startup_self_test
            await asyncio.to_thread(startup_self_test)
        except Exception:
            log.exception("Astra startup self-test crashed")
    try:
        seeded_bans = prt_access_bans.seed_from_environment()
        if seeded_bans:
            log.warning("Loaded %s permanent PRT Discord access ban(s).", seeded_bans)
    except Exception:
        log.exception("Failed to seed permanent PRT Discord access bans")
    try:
        await asyncio.to_thread(backfill_hub_emails)
    except Exception as exc:
        log.warning("Founder’s Race hub-email startup backfill failed: %s", exc)
    try:
        purge_orphaned_mail_events()
    except Exception:
        pass

    await discord_gateway_service.start()
    tasks = [
        asyncio.create_task(scheduler_loop(), name="autopilot-intelligence"),
        asyncio.create_task(multiplatform_scheduler_loop(), name="autopilot-multiplatform"),
        asyncio.create_task(research_worker_loop(), name="autopilot-research"),
        asyncio.create_task(social_publish_worker_loop(), name="social-publish"),
        asyncio.create_task(social_operator_loop(), name="social-operator"),
        asyncio.create_task(gmail_sync_loop(), name="gmail-shield"),
        asyncio.create_task(runtime_maintenance_loop(), name="runtime-memory-maintenance"),
    ]
    log.info(
        "Pitmark Cloud runtime started: background_threads=%s gmail_sync_min=%ss gmail_batch<=%s social_operator=%s",
        background_threads,
        _env_int("PITMARK_GMAIL_SYNC_SECONDS", 120, 120, 3600),
        _env_int("PITMARK_GMAIL_SYNC_LIMIT", 25, 5, 25),
        settings.social_operator_enabled,
    )
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await discord_gateway_service.stop()
        executor.shutdown(wait=False, cancel_futures=True)


_production = settings.environment.strip().lower() == "production"
app = FastAPI(
    title="Pitmark Cloud API",
    description="Pitmark Cloud backend for Racing Tools, Autopilot, Shield, marketing workflows, licensing, and integrations.",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url=None if _production else "/docs",
    redoc_url=None if _production else "/redoc",
    openapi_url=None if _production else "/openapi.json",
)

app.add_middleware(SecurityHeadersMiddleware)


async def _prt_access_identity(request: Request) -> tuple[str, str]:
    """Return any device/Discord identity exposed by a PRT access request."""
    path = request.url.path
    device_id = ""
    discord_user_id = ""

    if path.startswith("/api/entitlements/current/"):
        device_id = path.rsplit("/", 1)[-1].strip()
    elif path.startswith("/api/discord/"):
        device_id = str(request.query_params.get("device_id") or "").strip()

    if (
        path.startswith("/api/entitlements/")
        and request.method.upper() in {"POST", "PUT", "PATCH"}
        and "application/json" in (request.headers.get("content-type") or "").lower()
    ):
        try:
            raw = await request.body()
            payload = json.loads(raw) if raw else {}
            if isinstance(payload, dict):
                device_id = str(payload.get("device_id") or device_id).strip()
                discord_user_id = str(payload.get("discord") or "").strip()
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    return device_id, discord_user_id


@app.middleware("http")
async def prt_permanent_ban_guard(request: Request, call_next):
    path = request.url.path
    device_id, discord_user_id = await _prt_access_identity(request)

    if discord_user_id and prt_access_bans.is_discord_banned(discord_user_id):
        return JSONResponse({"detail": prt_access_bans.DENIED_MESSAGE}, status_code=403)

    if device_id and prt_access_bans.enforce_device_ban_if_linked(device_id):
        return JSONResponse({"detail": prt_access_bans.DENIED_MESSAGE}, status_code=403)

    response = await call_next(request)

    # Discord OAuth is the moment we can reliably bind a Discord snowflake to a
    # PRT device. If that identity is denylisted, poison the link/device after
    # Discord identifies it and replace the success page with a hard denial.
    if path == "/api/discord/oauth/callback":
        state = str(request.query_params.get("state") or "")
        try:
            from services import discord_service

            payload = discord_service.read_state(state)
            linked_device_id = str(payload.get("device_id") or "").strip()
        except Exception:
            linked_device_id = ""
        if linked_device_id and prt_access_bans.enforce_device_ban_if_linked(linked_device_id):
            return HTMLResponse(
                "<!doctype html><html><head><meta charset='utf-8'><title>PRT access denied</title></head>"
                "<body style='background:#08090a;color:#f4f1eb;font-family:Segoe UI,Arial,sans-serif;"
                "display:grid;place-items:center;min-height:100vh;margin:0'>"
                "<main style='max-width:560px;padding:32px;border:1px solid #292d31;background:#111315'>"
                "<h1 style='color:#ff5500'>PRT ACCESS DENIED</h1>"
                "<p>Access to Pitmark Racing Tools is not available for this account.</p>"
                "</main></body></html>",
                status_code=403,
            )

    return response


@app.middleware("http")
async def control_center_role_guard(request: Request, call_next):
    path = request.url.path
    permission = permission_for_path(path)
    if permission:
        supplied_admin = request.headers.get("X-Pitmark-Admin-Key", "")
        service_admin = bool(
            supplied_admin
            and settings.pitmark_admin_key
            and hmac.compare_digest(supplied_admin, settings.pitmark_admin_key)
        )
        if not service_admin:
            access = access_from_request(request)
            if not access or not access.active:
                return JSONResponse({"detail": "Control Center authentication required."}, status_code=401)
            if access.role not in {"owner", "admin"} and permission not in access.permissions:
                return JSONResponse(
                    {"detail": f"Your Control Center role does not include {permission} access."},
                    status_code=403,
                )
    return await call_next(request)

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Pitmark-Admin-Key", "X-Signature-Ed25519", "X-Signature-Timestamp"],
    )

app.include_router(health.router)
app.include_router(device.router, prefix="/api/device", tags=["device-security"])
app.include_router(entitlements.router, prefix="/api/entitlements", tags=["entitlements"])
app.include_router(discord.router, prefix="/api/discord", tags=["discord"])
app.include_router(discord_bot.router, prefix="/api/discord", tags=["discord-bot"])
app.include_router(live_session.router, prefix="/api/discord/session", tags=["discord-session"])
app.include_router(results.router, prefix="/api/discord", tags=["discord-results"])
app.include_router(shopify.router, prefix="/api/shopify", tags=["shopify"])
app.include_router(control_access_v191.router, prefix="/api/control", tags=["control-access-v191"])
app.include_router(control_center_v19.router, prefix="/api/control", tags=["control-center-v19"])
app.include_router(control_center_v195.router, prefix="/api/control", tags=["control-center-v195"])
app.include_router(control_center.router, prefix="/api/control", tags=["control-center"])
app.include_router(control_center_2026.router, tags=["control-center-2026"])
app.include_router(astra_director.router, prefix="/api/control/director", tags=["astra-director"])
app.include_router(social_context_v191.router, prefix="/api/control/social", tags=["social-context-v191"])
app.include_router(social_publish.router, prefix="/api/control/social", tags=["social-publishing"])
app.include_router(social_operator.router, prefix="/api/control/social/operator", tags=["social-operator"])
app.include_router(social_publish.public_router, tags=["public-social-assets"])
app.include_router(email_center_v19.router, prefix="/api/control/email", tags=["email-v19"])
app.include_router(email_center.router, prefix="/api/control/email", tags=["email"])
app.include_router(prt_analytics_v191.router, prefix="/api/prt/analytics", tags=["prt-analytics-v191"])
app.include_router(content_tools.router, prefix="/api/control/content", tags=["content-tools"])
app.include_router(control_center_ui.router)
app.include_router(prt_ui.router)
app.include_router(prt_testimonial_asset.router)
app.include_router(early_access_admin.router)


def _dashboard_root_target(request: Request) -> str | None:
    host = (request.url.hostname or "").lower().rstrip(".")
    if host != "dashboard.pitmarkracing.com":
        return None

    user_agent = request.headers.get("user-agent", "").lower()
    mobile_tokens = (
        "android",
        "iphone",
        "ipad",
        "ipod",
        "mobile",
        "windows phone",
    )
    return "/control/mobile" if any(token in user_agent for token in mobile_tokens) else "/control"


def _target_with_query(target: str, request: Request) -> str:
    query = request.url.query
    return f"{target}?{query}" if query else target


def _prt_root_target(request: Request) -> str | None:
    host = (request.url.hostname or "").lower().rstrip(".")
    if host != "prt.pitmarkracing.com":
        return None

    is_raceproof_campaign = request.query_params.get("utm_campaign") == "prt_raceproof_202609"
    is_meta_click = bool(request.query_params.get("fbclid"))
    target = "/prt/apply" if is_raceproof_campaign or is_meta_click else "/prt"
    return _target_with_query(target, request)


def _links_root_target(request: Request) -> str | None:
    host = (request.url.hostname or "").lower().rstrip(".")
    return "/links" if host == "links.pitmarkracing.com" else None


@app.get("/")
async def root(request: Request):
    dashboard_target = _dashboard_root_target(request)
    if dashboard_target:
        return RedirectResponse(url=dashboard_target, status_code=302)

    links_target = _links_root_target(request)
    if links_target:
        return RedirectResponse(url=links_target, status_code=302)

    prt_target = _prt_root_target(request)
    if prt_target:
        return RedirectResponse(url=prt_target, status_code=302)

    return {
        "service": "Pitmark Cloud",
        "status": "online",
        "version": settings.app_version,
        "health": "/health",
        "docs": None if _production else "/docs",
        "discord_install": "/api/discord/install",
        "database": database_status(),
    }


@app.get("/api/security/status")
async def security_status() -> dict:
    return security_summary(
        environment=settings.environment,
        signing_secret=settings.pitmark_signing_secret,
        admin_key=settings.pitmark_admin_key,
        cors_origins=settings.cors_origin_list,
    )
