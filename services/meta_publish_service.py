from __future__ import annotations

import httpx

from utils.config import settings


class MetaPublishError(RuntimeError):
    pass


def configured() -> bool:
    return bool(
        settings.meta_page_id.strip()
        and settings.meta_page_access_token.strip()
    )


def connection_status() -> dict:
    return {
        "configured": configured(),
        "page_id_set": bool(settings.meta_page_id.strip()),
        "page_access_token_set": bool(settings.meta_page_access_token.strip()),
        "graph_version": settings.meta_graph_version,
    }


def publish_facebook_post(message: str) -> dict:
    if not configured():
        raise MetaPublishError(
            "Facebook publishing is not configured. "
            "Set META_PAGE_ID and META_PAGE_ACCESS_TOKEN on the server."
        )

    body = (message or "").strip()
    if not body:
        raise MetaPublishError("Facebook post body is empty.")

    url = (
        f"https://graph.facebook.com/"
        f"{settings.meta_graph_version.strip('/')}/"
        f"{settings.meta_page_id.strip()}/feed"
    )
    payload = {
        "message": body,
        "access_token": settings.meta_page_access_token.strip(),
    }

    try:
        response = httpx.post(url, data=payload, timeout=30.0)
    except httpx.HTTPError as exc:
        raise MetaPublishError(f"Meta request failed: {exc}") from exc

    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}

    if response.is_error:
        err = data.get("error") if isinstance(data, dict) else None
        detail = (
            (err or {}).get("message")
            if isinstance(err, dict)
            else response.text
        )
        raise MetaPublishError(
            f"Meta rejected the post ({response.status_code}): {detail}"
        )

    post_id = data.get("id") if isinstance(data, dict) else None
    if not post_id:
        raise MetaPublishError("Meta returned success without a post id.")

    return {
        "ok": True,
        "platform": "facebook",
        "external_post_id": post_id,
        "raw": data,
    }
