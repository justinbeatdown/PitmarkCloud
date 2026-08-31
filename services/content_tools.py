from __future__ import annotations

import json
import re

import httpx

from services.research_page_reader import read_page_excerpt
from utils.config import settings


def _extract_output_text(data: dict) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    chunks: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def _parse_json(text: str) -> dict:
    candidate = text.strip()
    candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.I)
    candidate = re.sub(r"\s*```$", "", candidate)
    start, end = candidate.find("{"), candidate.rfind("}")
    if start >= 0 and end > start:
        candidate = candidate[start:end + 1]
    return json.loads(candidate)


def generate_article_from_source(source_url: str, prompt: str) -> dict:
    if not settings.openai_api_key.strip():
        raise RuntimeError("OPENAI_API_KEY is not configured in Pitmark Cloud.")
    with httpx.Client(timeout=15.0) as client:
        page = read_page_excerpt(client, source_url)
    if not page.ok:
        if page.category == "shield":
            raise ValueError(f"Pitmark Shield blocked that source URL: {page.reason}.")
        status = f" (HTTP {page.status_code})" if page.status_code else ""
        raise ValueError(f"Pitmark Cloud could not read that public source page{status}: {page.reason}.")
    excerpt = page.excerpt

    instructions = """You are the editorial writer inside Pitmark Control Center for Pitmark Racing Co.
Write an ORIGINAL motorsports article grounded only in the supplied source excerpt and the user's request.
Do not copy the source's phrasing, headline, or distinctive passages. Summarize facts in fresh language and add useful Pitmark framing.
Do not invent results, dates, quotes, hometowns, car numbers, teams, series, disciplines, or biographical facts.
If a fact is not supported by the source excerpt, omit it.
Pitmark is grassroots-minded, but 'grassroots' is a perspective and visual attitude, NOT a vehicle class. Never assume dirt late model, sprint car, stock car, NASCAR, or any other discipline unless the source supports it.
Return JSON only with keys: title, body_html, seo_title, seo_description, image_prompt.
body_html should contain clean HTML paragraphs and optional h2 headings, no markdown.
image_prompt must be editorial-safe: if the exact discipline/car/person is not supported, use a neutral motorsports environment such as pits, garage, helmet, grandstands, crew, track atmosphere, or abstract race-day storytelling. Never invent a real person's likeness, car number, team livery, or class. Do not recreate Pitmark logos or wordmarks."""

    user_input = f"""SOURCE URL:\n{source_url}\n\nUSER REQUEST:\n{prompt.strip() or 'Make our own story about this article.'}\n\nSOURCE EXCERPT:\n{excerpt[:14000]}"""
    payload = {
        "model": settings.pitmark_ai_model,
        "instructions": instructions,
        "input": user_input,
        "max_output_tokens": 1800,
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key.strip()}", "Content-Type": "application/json"}
    with httpx.Client(timeout=max(45.0, settings.pitmark_ai_timeout_seconds)) as client:
        response = client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
        response.raise_for_status()
        text = _extract_output_text(response.json())
    if not text:
        raise RuntimeError("AI provider returned an empty article response.")
    result = _parse_json(text)
    result["source_url"] = source_url
    result["source_excerpt_used"] = True
    result["source_read_via"] = page.final_url
    return result
