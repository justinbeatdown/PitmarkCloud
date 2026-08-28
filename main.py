from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import discord, discord_bot, entitlements, health, live_session, results, shopify
from utils.config import settings
from utils.logger import configure_logging
from services import discord_gateway_service
from services.database import init_database, database_status

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    await discord_gateway_service.start()
    try:
        yield
    finally:
        await discord_gateway_service.stop()


app = FastAPI(
    title="Pitmark Cloud API",
    description="Backend foundation for Pitmark Racing Tools licensing and integrations.",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(entitlements.router, prefix="/api/entitlements", tags=["entitlements"])
app.include_router(discord.router, prefix="/api/discord", tags=["discord"])
app.include_router(discord_bot.router, prefix="/api/discord", tags=["discord-bot"])
app.include_router(live_session.router, prefix="/api/discord/session", tags=["discord-session"])
app.include_router(results.router, prefix="/api/discord", tags=["discord-results"])
app.include_router(shopify.router, prefix="/api/shopify", tags=["shopify"])


@app.get("/")
async def root() -> dict:
    return {
        "service": "Pitmark Cloud",
        "status": "online",
        "version": settings.app_version,
        "health": "/health",
        "docs": "/docs",
        "discord_install": "/api/discord/install",
        "database": database_status(),
    }
