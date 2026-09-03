from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import asyncio
import ctypes
import gc
import hmac
import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from utils.security import SecurityHeadersMiddleware, security_summary

from api import device, discord, discord_bot, entitlements, health, live_session, results, shopify, control_center, control_center_v19, control_center_v195, control_access_v191, control_center_ui, social_publish, social_context_v191, email_center, email_center_v19, prt_analytics_v191, content_tools, prt_ui, early_access_admin
from utils.config import settings
from utils.logger import configure_logging
from services import discord_gateway_service
from services.database import init_database, database_status
from services.autopilot_intelligence import scheduler_loop
from services.autopilot_multiplatform import scheduler_loop as multiplatform_scheduler_loop
from services.research_agent import research_worker_loop
from services.social_publish_worker import social_publish_worker_loop
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
    # Shield does not need inbox-client-level polling. Bound both cadence and batch
    # size so Google Workspace protection remains useful without recreating a full
    # mail client workload inside the 512 MB Cloud service.
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
        except Exception as exc:  # noqa: BLE001 - keep the background worker alive
            log.warning("Google Workspace Gmail sync failed: %s", exc)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # asyncio.to_thread() is used by several always-on workers. The default Python
    # executor can grow much larger than a 0.5 CPU / 512 MB Render service needs,
    # so keep the background thread pool deliberately small and predictable.
    loop = asyncio.get_running_loop()
    background_threads = _env_int("PITMARK_BACKGROUND_THREADS", 4, 2, 6)
    executor = ThreadPoolExecutor(
        max_workers=background_threads,
        thread_name_prefix="pitmark-bg",
    )
    loop.set_default_executor(executor)

    init_database()
    # One-time repair of old Shield live-queue rows whose Pitmark Mail messages
    # were already deleted. Audit history remains intact.
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
        asyncio.create_task(gmail_sync_loop(), name="gmail-shield"),
        asyncio.create_task(runtime_maintenance_loop(), name="runtime-memory-maintenance"),
    ]
    log.info(
        "Pitmark Cloud runtime started: background_threads=%s gmail_sync_min=%ss gmail_batch<=%s",
        background_threads,
        _env_int("PITMARK_GMAIL_SYNC_SECONDS", 120, 120, 3600),
        _env_int("PITMARK_GMAIL_SYNC_LIMIT", 25, 5, 25),
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
app.include_router(social_context_v191.router, prefix="/api/control/social", tags=["social-context-v191"])
app.include_router(social_publish.router, prefix="/api/control/social", tags=["social-publishing"])
app.include_router(social_publish.public_router, tags=["public-social-assets"])
app.include_router(email_center_v19.router, prefix="/api/control/email", tags=["email-v19"])
app.include_router(email_center.router, prefix="/api/control/email", tags=["email"])
app.include_router(prt_analytics_v191.router, prefix="/api/prt/analytics", tags=["prt-analytics-v191"])
app.include_router(content_tools.router, prefix="/api/control/content", tags=["content-tools"])
app.include_router(control_center_ui.router)
app.include_router(prt_ui.router)
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


def _prt_root_target(request: Request) -> str | None:
    host = (request.url.hostname or "").lower().rstrip(".")
    return "/prt" if host == "prt.pitmarkracing.com" else None


@app.get("/")
async def root(request: Request):
    dashboard_target = _dashboard_root_target(request)
    if dashboard_target:
        return RedirectResponse(url=dashboard_target, status_code=302)

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
