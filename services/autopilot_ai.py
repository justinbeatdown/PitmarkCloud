from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from utils.config import settings

log = logging.getLogger(__name__)


@dataclass
class AIComposeResult:
    body: str
    provider: str
    model: str | None = None
    warning: str | None = None


PLATFORM_GUIDANCE = {
    "facebook": "Write like an organic Facebook post. Use natural paragraph spacing. Usually 45-120 words unless the request calls for shorter copy.",
    "instagram": "Write an Instagram-ready caption with a strong first line, natural paragraph spacing, and no hashtag dump. Use at most 3 genuinely useful hashtags only when they help.",
    "tiktok": "Write a short TikTok caption or post copy with a fast hook and conversational race-culture energy. Keep it compact.",
    "x": "Write for X. Be punchy and comfortably under 280 characters unless the user explicitly asks for a thread.",
}

GOAL_GUIDANCE = {
    "community": "Prioritize conversation, participation, and racing-community identity. Give people a natural reason to reply.",
    "education": "Teach one useful racing idea clearly without sounding like a textbook.",
    "entertainment": "Make it fun, relatable, and rooted in real racing culture without forced meme language.",
    "authority": "Sound knowledgeable and credible without corporate chest-thumping.",
    "product": "Product can be promoted, but racing culture comes first. Avoid generic ecommerce hype and fake urgency.",
    "partner": "Emphasize genuine collaboration with tracks, leagues, teams, drivers, creators, or racing communities.",
}

SYSTEM_PROMPT = """You are the social-content writer inside Pitmark Autopilot for Pitmark Racing Co.

Pitmark Racing Co. is a grassroots American motorsports brand built around racing culture: dirt tracks, short tracks, sim racing, garages, race teams, fans, drivers, leagues, and the wider racing community. The brand motto is "Leave Your Mark."

VOICE:
- Sound like a real racing person, not a marketing agency.
- Confident, energetic, grounded, slightly gritty, and conversational.
- Community and racing culture first; products second.
- Avoid corporate filler, generic motivational copy, fake hype, and phrases like "rev up," "fuel your passion," or "ultimate racing experience."
- Do not invent race results, partnerships, dates, discounts, product details, track facts, or current events that were not supplied by the user.
- Do not imply Pitmark is sponsoring, partnered with, or attending something unless the request explicitly says so.
- Use emojis sparingly. Racing/checkered-flag emojis are okay when natural.
- "Leave Your Mark" may be used when it lands naturally, but do not force it into every post.

OUTPUT RULES:
- Return ONLY finished post copy ready to paste. No preamble, analysis, headings such as "Caption:", alternatives, or explanation.
- Follow the user's requested subject faithfully instead of replacing it with a canned prompt.
- If the request asks a question of followers, make the question clear and easy to answer.
"""


def _extract_output_text(data: dict) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    chunks: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    return "\n".join(chunks).strip()


def ai_enabled() -> bool:
    return settings.pitmark_ai_provider.lower().strip() == "openai" and bool(settings.openai_api_key.strip())


def compose_with_ai(*, platform: str, goal: str, prompt: str, tone: str = "natural") -> AIComposeResult:
    provider = settings.pitmark_ai_provider.lower().strip()
    if provider != "openai":
        raise RuntimeError(f"AI provider '{provider or 'disabled'}' is not configured for live generation.")
    if not settings.openai_api_key.strip():
        raise RuntimeError("OPENAI_API_KEY is not configured in Pitmark Cloud.")

    platform_key = platform.lower().strip()
    goal_key = goal.lower().strip()
    user_input = f"""Platform: {platform_key}
Content goal: {goal_key}
Requested tone: {tone}
Platform guidance: {PLATFORM_GUIDANCE.get(platform_key, 'Write clean social copy appropriate for the named platform.')}
Goal guidance: {GOAL_GUIDANCE.get(goal_key, GOAL_GUIDANCE['community'])}

User request:
{prompt.strip()}
"""

    payload = {
        "model": settings.pitmark_ai_model,
        "instructions": SYSTEM_PROMPT,
        "input": user_input,
        "max_output_tokens": 600,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key.strip()}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=settings.pitmark_ai_timeout_seconds) as client:
        response = client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
        response.raise_for_status()
        body = _extract_output_text(response.json())
    if not body:
        raise RuntimeError("AI provider returned an empty response.")
    return AIComposeResult(body=body, provider="openai", model=settings.pitmark_ai_model)
