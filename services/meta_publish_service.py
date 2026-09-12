from __future__ import annotations

import time
import httpx

from utils.config import settings


class MetaPublishError(RuntimeError):
    pass



def _base_token() -> str:
    """Prefer a Business Manager System User token for production server auth."""
    return (settings.meta_system_user_access_token or settings.meta_page_access_token).strip()

def _page_token() -> str:
    """Resolve a Page token from the production System User token when configured.
    Fall back to the legacy Page token only for backwards compatibility.
    """
    system = settings.meta_system_user_access_token.strip()
    if not system:
        return settings.meta_page_access_token.strip()
    if not settings.meta_page_id.strip():
        return system
    try:
        r=httpx.get(
            _graph_url(settings.meta_page_id),
            params={'fields':'access_token','access_token':system},
            timeout=12.0
        )
        data=_decode(r)
        return str(data.get('access_token') or system).strip()
    except Exception:
        # Some system-user configurations can act directly on assigned Page assets.
        return system


def configured() -> bool:
    return facebook_configured()


def facebook_configured() -> bool:
    return bool(settings.meta_page_id.strip() and _base_token())


def instagram_configured() -> bool:
    return bool(settings.meta_instagram_account_id.strip() and _base_token())


def connection_status() -> dict:
    return facebook_connection_status()



def _live_meta_health() -> dict:
    if not _base_token():
        return {"connected": False, "healthy": False, "error": "Page access token is not configured."}
    token = _page_token()
    try:
        r = httpx.get(
            _graph_url(settings.meta_page_id or "me"),
            params={"fields": "id,name", "access_token": token},
            timeout=12.0,
        )
        data = _decode(r)
        expected = settings.meta_page_id.strip()
        actual = str(data.get("id") or "")
        if expected and actual and actual != expected:
            return {"connected": False, "healthy": False, "error": "Token resolves to a different Meta Page.", "resolved_id": actual}
        return {"connected": True, "healthy": True, "page_name": data.get("name"), "resolved_id": actual}
    except Exception as exc:
        return {"connected": False, "healthy": False, "error": str(exc)[:300]}


def facebook_connection_status() -> dict:
    health = _live_meta_health() if facebook_configured() else {"connected": False, "healthy": False}
    return {"configured": facebook_configured(), **health, "page_id_set": bool(settings.meta_page_id.strip()), "page_access_token_set": bool(settings.meta_page_access_token.strip()), "system_user_token_set": bool(settings.meta_system_user_access_token.strip()), "auth_mode": "system_user" if settings.meta_system_user_access_token.strip() else "legacy_page_token", "graph_version": settings.meta_graph_version}


def instagram_connection_status() -> dict:
    health = _live_meta_health() if instagram_configured() else {"connected": False, "healthy": False}
    return {"configured": instagram_configured(), **health, "instagram_account_id_set": bool(settings.meta_instagram_account_id.strip()), "page_access_token_set": bool(settings.meta_page_access_token.strip()), "system_user_token_set": bool(settings.meta_system_user_access_token.strip()), "auth_mode": "system_user" if settings.meta_system_user_access_token.strip() else "legacy_page_token", "system_user_token_set": bool(settings.meta_system_user_access_token.strip()), "auth_mode": "system_user" if settings.meta_system_user_access_token.strip() else "legacy_page_token", "graph_version": settings.meta_graph_version, "requires_media": True}


def _graph_url(object_id: str, edge: str | None = None) -> str:
    base = f"https://graph.facebook.com/{settings.meta_graph_version.strip('/')}/{object_id.strip()}"
    return f"{base}/{edge.strip('/')}" if edge else base


def _decode(response: httpx.Response) -> dict:
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.is_error:
        err = data.get("error") if isinstance(data, dict) else None
        detail = (err or {}).get("message") if isinstance(err, dict) else response.text
        raise MetaPublishError(f"Meta rejected the request ({response.status_code}): {detail}")
    return data


def publish_facebook_post(message: str) -> dict:
    if not facebook_configured():
        raise MetaPublishError("Facebook publishing is not configured. Set META_PAGE_ID and META_PAGE_ACCESS_TOKEN on the server.")
    body = (message or "").strip()
    if not body:
        raise MetaPublishError("Facebook post body is empty.")
    try:
        response = httpx.post(_graph_url(settings.meta_page_id, "feed"), data={"message": body, "access_token": _page_token()}, timeout=30.0)
    except httpx.HTTPError as exc:
        raise MetaPublishError(f"Meta request failed: {exc}") from exc
    data = _decode(response)
    post_id = data.get("id") if isinstance(data, dict) else None
    if not post_id:
        raise MetaPublishError("Meta returned success without a Facebook post id.")
    return {"ok": True, "platform": "facebook", "external_post_id": post_id, "raw": data}


def _wait_for_instagram_container(creation_id: str, timeout_seconds: float = 25.0) -> None:
    deadline = time.time() + timeout_seconds
    token = _page_token()
    while time.time() < deadline:
        try:
            response = httpx.get(_graph_url(creation_id), params={"fields": "status_code,status", "access_token": token}, timeout=15.0)
            data = _decode(response)
        except httpx.HTTPError as exc:
            raise MetaPublishError(f"Instagram container status check failed: {exc}") from exc
        status_code = str(data.get("status_code") or "").upper()
        if status_code in {"FINISHED", "PUBLISHED"}:
            return
        if status_code in {"ERROR", "EXPIRED"}:
            raise MetaPublishError(f"Instagram media container failed: {data.get('status') or status_code}")
        time.sleep(1.5)


def publish_instagram_post(*, caption: str, image_url: str) -> dict:
    if not instagram_configured():
        raise MetaPublishError("Instagram publishing is not configured. Set META_INSTAGRAM_ACCOUNT_ID and META_PAGE_ACCESS_TOKEN on the server.")
    body = (caption or "").strip()
    media = (image_url or "").strip()
    if not media.startswith(("https://", "http://")):
        raise MetaPublishError("Instagram requires a publicly reachable image URL.")
    token = _page_token()
    ig_id = settings.meta_instagram_account_id.strip()
    try:
        create_response = httpx.post(_graph_url(ig_id, "media"), data={"image_url": media, "caption": body, "access_token": token}, timeout=30.0)
    except httpx.HTTPError as exc:
        raise MetaPublishError(f"Instagram media creation failed: {exc}") from exc
    create_data = _decode(create_response)
    creation_id = create_data.get("id")
    if not creation_id:
        raise MetaPublishError("Meta created no Instagram media container id.")
    _wait_for_instagram_container(str(creation_id))
    try:
        publish_response = httpx.post(_graph_url(ig_id, "media_publish"), data={"creation_id": creation_id, "access_token": token}, timeout=30.0)
    except httpx.HTTPError as exc:
        raise MetaPublishError(f"Instagram publish request failed: {exc}") from exc
    publish_data = _decode(publish_response)
    post_id = publish_data.get("id")
    if not post_id:
        raise MetaPublishError("Meta returned success without an Instagram post id.")
    return {"ok": True, "platform": "instagram", "external_post_id": post_id, "creation_id": creation_id, "media_url": media, "raw": publish_data}


def fetch_facebook_page_comments(*, limit_posts: int = 12, limit_comments: int = 50) -> list[dict]:
    """Return recent comments on Pitmark-owned Facebook posts.

    This uses only the existing Page token. Missing read permissions are surfaced to the
    caller so Social Operator can degrade to posting-only mode instead of guessing.
    """
    if not facebook_configured():
        return []
    token = _page_token()
    fields = (
        "id,message,created_time,"
        f"comments.limit({max(1, min(100, limit_comments))})"
        "{id,message,created_time,from{id,name},can_reply}"
    )
    response = httpx.get(
        _graph_url(settings.meta_page_id, "published_posts"),
        params={"fields": fields, "limit": max(1, min(50, limit_posts)), "access_token": token},
        timeout=25.0,
    )
    data = _decode(response)
    page_id = settings.meta_page_id.strip()
    items: list[dict] = []
    for post in data.get("data") or []:
        post_id = str(post.get("id") or "")
        for comment in ((post.get("comments") or {}).get("data") or []):
            author = comment.get("from") or {}
            # Do not ingest a top-level comment authored by the Page itself.
            if str(author.get("id") or "") == page_id:
                continue
            items.append(
                {
                    "id": str(comment.get("id") or ""),
                    "post_id": post_id,
                    "message": str(comment.get("message") or ""),
                    "author_name": str(author.get("name") or ""),
                    "created_time": comment.get("created_time"),
                    "can_reply": comment.get("can_reply", True),
                }
            )
    return items


def reply_facebook_comment(comment_id: str, message: str) -> dict:
    if not facebook_configured():
        raise MetaPublishError("Facebook publishing is not configured.")
    body = (message or "").strip()
    if not comment_id.strip() or not body:
        raise MetaPublishError("Facebook comment reply needs a comment id and message.")
    response = httpx.post(
        _graph_url(comment_id, "comments"),
        data={"message": body, "access_token": _page_token()},
        timeout=25.0,
    )
    data = _decode(response)
    return {"ok": True, "platform": "facebook", "external_reply_id": data.get("id"), "raw": data}


def fetch_instagram_comments(*, limit_media: int = 12, limit_comments: int = 50) -> list[dict]:
    if not instagram_configured():
        return []
    token = _page_token()
    ig_id = settings.meta_instagram_account_id.strip()
    fields = (
        "id,caption,timestamp,"
        f"comments.limit({max(1, min(100, limit_comments))})"
        "{id,text,timestamp,username}"
    )
    response = httpx.get(
        _graph_url(ig_id, "media"),
        params={"fields": fields, "limit": max(1, min(50, limit_media)), "access_token": token},
        timeout=25.0,
    )
    data = _decode(response)
    items: list[dict] = []
    for media in data.get("data") or []:
        media_id = str(media.get("id") or "")
        for comment in ((media.get("comments") or {}).get("data") or []):
            items.append(
                {
                    "id": str(comment.get("id") or ""),
                    "media_id": media_id,
                    "message": str(comment.get("text") or ""),
                    "author_name": str(comment.get("username") or ""),
                    "created_time": comment.get("timestamp"),
                }
            )
    return items


def reply_instagram_comment(comment_id: str, message: str) -> dict:
    if not instagram_configured():
        raise MetaPublishError("Instagram publishing is not configured.")
    body = (message or "").strip()
    if not comment_id.strip() or not body:
        raise MetaPublishError("Instagram comment reply needs a comment id and message.")
    response = httpx.post(
        _graph_url(comment_id, "replies"),
        data={"message": body, "access_token": _page_token()},
        timeout=25.0,
    )
    data = _decode(response)
    return {"ok": True, "platform": "instagram", "external_reply_id": data.get("id"), "raw": data}
