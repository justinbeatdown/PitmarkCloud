from __future__ import annotations

import time
from typing import Any

import httpx

from utils.config import settings

_TOKEN: str | None = None
_TOKEN_EXPIRES_AT: float = 0.0
API_VERSION = "2026-07"


def _shop_host() -> str:
    raw = (settings.shopify_shop_domain or "").strip()
    if not raw:
        return ""
    if raw.startswith("https://"):
        raw = raw[8:]
    elif raw.startswith("http://"):
        raw = raw[7:]
    return raw.strip("/")


def configured() -> bool:
    return bool(_shop_host() and settings.shopify_client_id and settings.shopify_client_secret)


def status() -> dict:
    return {
        "configured": configured(),
        "message": (
            "Shopify credentials are configured; live authentication is available."
            if configured()
            else "Shopify integration is ready. Credentials have not been configured yet."
        ),
    }


def get_access_token(force_refresh: bool = False) -> str:
    global _TOKEN, _TOKEN_EXPIRES_AT
    if not configured():
        raise RuntimeError("Shopify credentials are not configured")
    now = time.time()
    if not force_refresh and _TOKEN and now < (_TOKEN_EXPIRES_AT - 60):
        return _TOKEN
    url = f"https://{_shop_host()}/admin/oauth/access_token"
    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": settings.shopify_client_id,
                "client_secret": settings.shopify_client_secret,
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Shopify token request failed ({response.status_code})")
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Shopify token response did not include an access token")
    expires_in = int(data.get("expires_in") or 86399)
    _TOKEN = token
    _TOKEN_EXPIRES_AT = now + expires_in
    return token


def graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    token = get_access_token()
    url = f"https://{_shop_host()}/admin/api/{API_VERSION}/graphql.json"
    with httpx.Client(timeout=25.0) as client:
        response = client.post(
            url,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": token,
            },
            json={"query": query, "variables": variables or {}},
        )
    if response.status_code == 401:
        token = get_access_token(force_refresh=True)
        with httpx.Client(timeout=25.0) as client:
            response = client.post(
                url,
                headers={"Content-Type": "application/json", "X-Shopify-Access-Token": token},
                json={"query": query, "variables": variables or {}},
            )
    if response.status_code >= 400:
        raise RuntimeError(f"Shopify API request failed ({response.status_code})")
    payload = response.json()
    if payload.get("errors"):
        msg = "; ".join(str(e.get("message", "GraphQL error")) for e in payload["errors"][:3])
        raise RuntimeError(f"Shopify GraphQL error: {msg}")
    return payload.get("data") or {}


def connection_test() -> dict[str, Any]:
    data = graphql("query PitmarkShopifyConnection { shop { name myshopifyDomain } }")
    shop = data.get("shop") or {}
    return {
        "configured": True,
        "authenticated": bool(shop.get("myshopifyDomain")),
        "shop_name": shop.get("name"),
        "shop_domain": shop.get("myshopifyDomain"),
        "api_version": API_VERSION,
    }


def list_blogs() -> list[dict[str, Any]]:
    data = graphql("query PitmarkBlogs { blogs(first: 25) { nodes { id title handle } } }")
    blogs = list(((data.get("blogs") or {}).get("nodes") or []))
    preferred_handles = {"racing-culture", "news", "pitmark", "track-spotlight"}
    return sorted(
        blogs,
        key=lambda blog: 0 if (blog.get("handle") or "").lower() in preferred_handles else 1,
    )


def publish_article(*, blog_id: str, title: str, body_html: str, author: str = "Pitmark Racing Co.", image_url: str | None = None) -> dict[str, Any]:
    mutation = """
    mutation PitmarkPublishArticle($article: ArticleCreateInput!) {
      articleCreate(article: $article) {
        article { id title handle isPublished }
        userErrors { code field message }
      }
    }
    """
    article: dict[str, Any] = {
        "blogId": blog_id,
        "title": title,
        "author": {"name": author},
        "body": body_html,
        "isPublished": True,
    }
    if image_url:
        article["image"] = {"url": image_url, "altText": title}
    data = graphql(mutation, {"article": article})
    result = data.get("articleCreate") or {}
    errors = result.get("userErrors") or []
    if errors:
        raise RuntimeError("Shopify article rejected: " + "; ".join(str(e.get("message", "Unknown error")) for e in errors[:3]))
    created = result.get("article")
    if not created:
        raise RuntimeError("Shopify did not return the created article")
    return created
