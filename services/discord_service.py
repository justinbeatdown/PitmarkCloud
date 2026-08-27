from utils.config import settings


def status() -> dict:
    configured = bool(settings.discord_client_id and settings.discord_client_secret)
    return {
        "configured": configured,
        "connected": False,
        "message": (
            "Discord credentials are configured; OAuth/bot wiring is the next integration step."
            if configured
            else "Discord integration scaffold is ready. Credentials have not been configured yet."
        ),
    }
