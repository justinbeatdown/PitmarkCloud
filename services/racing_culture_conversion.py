from __future__ import annotations

import re


CTA_MARKER = 'data-pitmark-racing-culture-cta="1"'


def _utm_content(title: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", str(title or "").lower()).strip("_")
    return value[:80] or "racing_culture_article"


def append_racing_culture_conversion_cta(body_html: str | None, title: str | None) -> str:
    body = str(body_html or "")
    if CTA_MARKER in body:
        return body

    content = _utm_content(str(title or ""))
    query = (
        "utm_source=racing_culture&amp;"
        "utm_medium=article&amp;"
        "utm_campaign=keep_local_racing_visible&amp;"
        f"utm_content={content}"
    )
    cta = (
        '<div data-pitmark-racing-culture-cta="1">\n'
        '<hr>\n'
        '<h2>Keep Local Racing Visible</h2>\n'
        '<p>Pitmark Racing Co. covers racing culture and builds gear for the people who live it. '
        'If that sounds like you, check out the '
        f'<a href="/products/support-your-local-track-t-shirt-racing-garage-crew-tee?{query}">Support Your Local Track Garage Crew Tee</a>, '
        f'the <a href="/products/support-your-local-track-t-shirt-racing-sunset-graphic-tee?{query}">Sunset Tee</a>, or '
        f'<a href="/collections/all?{query}">shop Pitmark Racing Co.</a></p>\n'
        '</div>'
    )
    separator = "\n" if body and not body.endswith("\n") else ""
    return f"{body}{separator}{cta}"
