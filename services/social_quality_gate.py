from __future__ import annotations

import re

_AUTOMATIC_PREFIXES = ("dailycampaign:", "firstparty:", "intelligence:")
_AUTOMATIC_EXACT = {"operator:growth-loop", "control_center:auto"}

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "co", "for", "from", "in",
    "is", "it", "of", "on", "or", "our", "the", "this", "to", "with", "your",
    "pitmark", "racing", "race", "racer", "racers", "track", "local", "weekend",
    "roundup", "blog", "publish", "post", "update",
}

_INTERNAL_MARKERS = (
    "blog publish",
    "todo",
    "tbd",
    "[insert",
    "{{",
    "}}",
)


def is_automatic_source(source: str | None) -> bool:
    raw = str(source or "").strip().lower()
    return raw in _AUTOMATIC_EXACT or raw.startswith(_AUTOMATIC_PREFIXES)


def _tokens(value: str | None) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if len(token) >= 3
    }


def _title_anchors(title: str | None) -> set[str]:
    return {
        token
        for token in _tokens(title)
        if token not in _STOPWORDS and len(token) >= 4
    }


def _looks_truncated(title: str | None) -> bool:
    clean = re.sub(r"\s+", " ", str(title or "")).strip()
    if not clean:
        return True
    if re.search(r"(?:\band|\bor)\s+[A-Za-z]$", clean, re.I):
        return True
    if re.search(r"[,;:/\-–—]$", clean):
        return True
    return False


def assess_automatic_post_quality(
    *,
    platform: str | None,
    title: str | None,
    body: str | None,
    source: str | None,
    media_url: str | None = None,
) -> dict:
    """Fail closed for automatic Pitmark publishing."""
    if not is_automatic_source(source):
        return {"ok": True, "reasons": []}

    reasons: list[str] = []
    clean_title = re.sub(r"\s+", " ", str(title or "")).strip()
    clean_body = re.sub(r"\s+", " ", str(body or "")).strip()
    platform_name = str(platform or "").strip().lower()

    if len(clean_body) < 30:
        reasons.append("copy is too short for unattended publishing")

    lowered = f"{clean_title} {clean_body}".lower()
    if any(marker in lowered for marker in _INTERNAL_MARKERS):
        reasons.append("internal placeholder/automation language is visible")

    # Some automation lanes publish caption-only posts and historically did not
    # persist an internal title. Absence of a title is not the same thing as a
    # truncated title; keep the body/placeholder checks active and only apply
    # title-specific validation when a title is actually present.
    if clean_title:
        if _looks_truncated(clean_title):
            reasons.append("title appears truncated or unfinished")

        anchors = _title_anchors(clean_title)
        body_tokens = _tokens(clean_body)
        if len(anchors) >= 2 and not (anchors & body_tokens):
            reasons.append("caption does not reference the post topic")

    if platform_name == "instagram" and not str(media_url or "").strip():
        reasons.append("automatic Instagram post has no assigned campaign/source image")

    return {"ok": not reasons, "reasons": reasons}
