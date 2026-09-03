from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from utils.config import settings

log = logging.getLogger("pitmark.database")


class Base(DeclarativeBase):
    pass


def _normalized_url() -> str:
    raw = (settings.database_url or "").strip()
    if raw:
        if raw.startswith("postgres://"):
            raw = "postgresql+psycopg://" + raw[len("postgres://"):]
        elif raw.startswith("postgresql://"):
            raw = "postgresql+psycopg://" + raw[len("postgresql://"):]
        return raw

    Path("data").mkdir(exist_ok=True)
    return "sqlite:///./data/pitmark-dev.db"


DATABASE_URL = _normalized_url()
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
_engine_options = {
    "pool_pre_ping": True,
    "connect_args": _connect_args,
}

# The default SQLAlchemy QueuePool can hold more idle/overflow connections than
# Pitmark Cloud needs on a 512 MB single-instance service. Keep PostgreSQL's pool
# deliberately compact while still allowing short bursts from background workers.
if not DATABASE_URL.startswith("sqlite"):
    _engine_options.update(
        pool_size=3,
        max_overflow=2,
        pool_timeout=20,
        pool_recycle=300,
        pool_use_lifo=True,
    )

engine = create_engine(DATABASE_URL, **_engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_database() -> None:
    from services import persistent_store  # noqa: F401
    from services import discord_hq_store  # noqa: F401
    from services import control_center  # noqa: F401
    from services import control_auth  # noqa: F401
    from services import racing_community  # noqa: F401
    from services import social_asset_pool  # noqa: F401
    from services import pitmark_mail_preferences  # noqa: F401
    from services import pitmark_mail_auto_reply  # noqa: F401
    from services import control_access  # noqa: F401
    from services import prt_analytics  # noqa: F401
    from services import prt_licensing_store  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if not settings.database_url:
        log.warning(
            "DATABASE_URL is not configured. Using local SQLite fallback; this is NOT persistent on Render."
        )


def database_status() -> dict:
    configured = bool((settings.database_url or "").strip())
    is_sqlite = DATABASE_URL.startswith("sqlite")
    return {
        "configured": configured,
        "backend": "sqlite" if is_sqlite else "postgresql",
        "durable_for_render": configured and not is_sqlite,
        "warning": (
            None
            if configured and not is_sqlite
            else "Pitmark Cloud is using local SQLite. Configure DATABASE_URL before public multi-server use so guild settings, Discord links, race results, HQ tickets, moderation records, and PRT licenses survive deploys/restarts."
        ),
    }
