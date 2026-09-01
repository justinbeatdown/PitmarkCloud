from contextlib import asynccontextmanager
import asyncio
import hmac
import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from utils.security import SecurityHeadersMiddleware, security_summary

from api import device, discord, discord_bot, entitlements, health, live_session, results, shopify, control_center, control_center_v19, control_center_v195, control_access_v191, control_center_ui, social_publish, social_context_v191, email_center, email_center_v19, prt_analytics_v191, content_tools, prt_ui
from utils.config import settings
from utils.logger import configure_logging
from services import discord_gateway_service
from services.database import init_database, database_status
from services.autopilot_intelligence import scheduler_loop
from services.autopilot_multiplatform import scheduler_loop as multiplatform_scheduler_loop
from services.research_agent import research_worker_loop
from services.social_publish_worker import social_publish_worker_loop
from services.shield_mail_cleanup import purge_orphaned_mail_events
from services.shield_mail import sync_gmail_mail_protected
from services.control_access import access_from_request, permission_for_path

configure_logging()
log = logging.getLogger("pitmark.gmail_sync")


async def gmail_sync_loop():
    interval = max(30, int(os.getenv("PITMARK_GMAIL_SYNC_SECONDS") or "60"))
    while True:
        try:
            await asyncio.to_thread(sync_gmail_mail_protected)
        except Exception as exc:  # noqa: BLE001 - keep the background worker alive
            log.warning("Google Workspace Gmail sync failed: %s", exc)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    # One-time repair of old Shield live-queue rows whose Pitmark Mail messages
    # were already deleted. Audit history remains intact.
    try:
        purge_orphaned_mail_events()
    except Exception:
        pass
    await discord_gateway_service.start()
    autopilot_task = asyncio.create_task(scheduler_loop())
    multiplatform_task = asyncio.create_task(multiplatform_scheduler_loop())
    research_task = asyncio.create_task(research_worker_loop())
    social_publish_task = asyncio.create_task(social_publish_worker_loop())
    gmail_task = asyncio.create_task(gmail_sync_loop())
    try:
        yield
    finally:
        autopilot_task.cancel()
        multiplatform_task.cancel()
        research_task.cancel()
        social_publish_task.cancel()
        gmail_task.cancel()
        await discord_gateway_service.stop()


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
