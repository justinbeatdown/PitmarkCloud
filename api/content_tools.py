from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.content_tools import generate_article_from_source
from services.control_auth import require_control_user
from utils.security import enforce_rate_limit

router = APIRouter()


class ArticleFromSourceRequest(BaseModel):
    source_url: str
    prompt: str = "Make our own story about this article."


@router.post("/article-from-source")
def article_from_source(req: ArticleFromSourceRequest, request: Request):
    require_control_user(request, None)
    enforce_rate_limit(request, "article-from-source", 8, 300)
    try:
        return generate_article_from_source(req.source_url.strip(), req.prompt.strip())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Article generation failed: {exc}") from exc
