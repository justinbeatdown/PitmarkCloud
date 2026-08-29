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
        # Render/Supabase-style URLs are sometimes supplied as postgres://.
        if raw.startswith("postgres://"):
            raw = "postgresql+psycopg://" + raw[len("postgres://"):]
        elif raw.startswith("postgresql://"):
            raw = "postgresql+psycopg://" + raw[len("postgresql://"):]
        return raw

    # Local development fallback only. Render's filesystem is ephemeral, so production
    # multi-server deployments should always set DATABASE_URL.
    Path("data").mkdir(exist_ok=True)
    return "sqlite:///./data/pitmark-dev.db"


DATABASE_URL = _normalized_url()
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_database() -> None:
    # Import model modules before create_all so SQLAlchemy knows all tables.
    from services import persistent_store  # noqa: F401
    from services import control_center  # noqa: F401
    from services import control_auth  # noqa: F401
    from services import racing_community  # noqa: F401

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
            else "Pitmark Cloud is using local SQLite. Configure DATABASE_URL before public multi-server use so guild settings, Discord links, and race results survive deploys/restarts."
        ),
    }
