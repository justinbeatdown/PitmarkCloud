from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import DateTime, Float, Integer, String, Text, select, text
from sqlalchemy.orm import Mapped, mapped_column

from services.autopilot_ai import _extract_output_text
from services.blog_image_service import generate_and_stage_blog_image
from services.control_center import BlogDraft, EcosystemNotification, ShopifyPublishRecord, utcnow
from services.database import Base, SessionLocal, engine, DATABASE_URL
from services.first_party_models import queue_event
from services.persistent_store import get_runtime_state, set_runtime_state
from services.racing_community import CommunityEntity
from services.racing_culture_conversion import append_racing_culture_conversion_cta
from services.racing_events import get_racing_event_hub
from services.research_agent import _bing_search, _ddg_search, _google_news_search
from services.research_page_reader import enrich_ranked_sources
from services import shopify_service
from utils.config import settings

log = logging.getLogger("pitmark.results_sweep")
ET = ZoneInfo("America/New_York")

DEFAULT_LOCAL_TRACKS = (
    "Lernerville Speedway",
    "Pittsburgh's Pennsylvania Motor Speedway",
    "Michael's Mercer Raceway",
    "Sharon Speedway",
    "Eriez Speedway",
    "Dog Hollow Speedway",
    "Latrobe Speedway",
    "Path Valley Speedway Park",
    "Bedford Speedway",
    "Hummingbird Speedway",
    "Port Royal Speedway",
    "Williams Grove Speedway",
    "Grandview Speedway",
    "Selinsgrove Speedway",
    "Lincoln Speedway",
    "BAPS Motor Speedway",
    "Tri-City Raceway Park",
    "RUSH Racing Series",
)

TRUSTED = (
    "myracepass.com", "dirtondirt.com", "nascar.com", "arcaracing.com",
    "imsa.com", "indycar.com", "worldofoutlaws.com", "lucasdirt.com",
    "highlimitracing.com", "usacracing.com", "nhra.com", "formula1.com",
    "motogp.com", "worldsbk.com", "supercars.com", "fiawec.com",
    "fiaformulae.com", "race-monitor.com",
)
RESULT_WORDS = ("results", "winner", "wins", "won", "victory", "feature", "checkered", "podium", "final", "recap")
RESULTS_SWEEP_LOCK_KEY = 739245118


class ResultsSweepItem(Base):
    __tablename__ = "pitmark_results_sweep_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    weekend_key: Mapped[str] = mapped_column(String(16), index=True)
    entity_name: Mapped[str] = mapped_column(String(240), index=True)
    event_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    event_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    class_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    winner: Mapped[str | None] = mapped_column(String(180), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_urls_json: Mapped[str] = mapped_column(Text, default="[]")
    source_names_json: Mapped[str] = mapped_column(Text, default="[]")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="uncovered", index=True)
    article_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResultsSweepRun(Base):
    __tablename__ = "pitmark_results_sweep_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    weekend_key: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(40), default="running", index=True)
    targets_checked: Mapped[int] = mapped_column(Integer, default=0)
    results_found: Mapped[int] = mapped_column(Integer, default=0)
    uncovered_count: Mapped[int] = mapped_column(Integer, default=0)
    published_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name) or default)
    except Exception:
        value = default
    return max(low, min(high, value))


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except Exception:
        return default


def _weekend(now: datetime | None = None):
    now = now or datetime.now(ET)
    days = (now.weekday() - 4) % 7
    friday = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    if now.weekday() < 4:
        friday -= timedelta(days=7)
    sunday = friday + timedelta(days=2, hours=23, minutes=59, seconds=59)
    return friday, min(now, sunday), friday.date().isoformat()


def _domain(url: str) -> str:
    return (urlparse(url or "").hostname or "").lower().removeprefix("www.")


def _trusted(url: str) -> bool:
    host = _domain(url)
    return any(host == d or host.endswith("." + d) for d in TRUSTED)


def _tokens(name: str):
    drop = {"the", "speedway", "raceway", "racing", "series", "motorsports", "motor", "park", "championship", "tour", "national", "world", "and"}
    return [x for x in re.findall(r"[a-z0-9]+", name.lower()) if len(x) >= 3 and x not in drop][:6]


def _score(name: str, item: dict, year: int) -> int:
    text = " ".join(str(item.get(k) or "") for k in ("title", "snippet", "source", "url")).lower()
    score = min(30, sum(8 for t in _tokens(name) if t in text))
    if any(word in text for word in RESULT_WORDS):
        score += 30
    if str(year) in text:
        score += 5
    if _trusted(str(item.get("url") or "")):
        score += 25
    host = _domain(str(item.get("url") or ""))
    if any(t in host for t in _tokens(name)[:2]):
        score += 15
    return score


def _search(name: str, start: datetime, end: datetime, local: bool) -> list[dict]:
    date_text = f"{start.strftime('%B')} {start.day}-{end.day} {start.year}"
    queries = [f'"{name}" results {date_text}', f'"{name}" winner {start.strftime("%B")} {start.year}']
    rows = []
    with httpx.Client(timeout=12.0, follow_redirects=True) as client:
        for q in queries:
            rows.extend(_bing_search(client, q, limit=8))
            rows.extend(_google_news_search(client, q, limit=8))
            if local:
                rows.extend(_ddg_search(client, q, limit=8))

        # Local dirt-track results are frequently published to specialist result
        # aggregators instead of track websites or email lists. Search those
        # sources explicitly, and always include the Pennsylvania weekly-results
        # roundup as a fallback source for the local-track lane.
        if local:
            for q in (
                f'site:dirtondirt.com/results.php "{name}" {start.strftime("%B")} {start.year}',
                f'site:myracepass.com "{name}" results {start.year}',
            ):
                rows.extend(_bing_search(client, q, limit=8))
            rows.append({
                "title": f"Pennsylvania Weekly Late Model Results — {name}",
                "source": "Dirt on Dirt",
                "url": "https://www.dirtondirt.com/results.php?month=all&search=true&state=PA&track=all",
                "snippet": (
                    f"Trusted Pennsylvania weekly race-results roundup. "
                    f"Check {name} for {start.date().isoformat()} through {end.date().isoformat()}."
                ),
            })
    keep = {}
    for item in rows:
        key = (item.get("url") or item.get("title") or "").strip().lower()
        score = _score(name, item, start.year)
        if not key or score < 24:
            continue
        row = dict(item)
        row["_score"] = score
        if key not in keep or score > keep[key]["_score"]:
            keep[key] = row
    ranked = sorted(keep.values(), key=lambda x: x["_score"], reverse=True)[:8]
    return enrich_ranked_sources(ranked, limit=min(5, len(ranked)))


def _series_this_weekend(start: datetime, end: datetime) -> list[str]:
    try:
        catalog = get_racing_event_hub(force=False).get("catalog") or []
    except Exception:
        return []
    out = []
    for item in catalog:
        raw = (item.get("event") or {}).get("start")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(ET)
        except Exception:
            continue
        if start.date() <= dt.date() <= end.date() and item.get("series_name"):
            out.append(str(item["series_name"]))
    return list(dict.fromkeys(out))


def _targets(start: datetime, end: datetime):
    rows = [(x, True) for x in DEFAULT_LOCAL_TRACKS]
    try:
        with SessionLocal() as db:
            entities = db.scalars(
                select(CommunityEntity).where(
                    CommunityEntity.community_lane.in_(["real", "crossover"]),
                    CommunityEntity.entity_type.in_(["track", "series", "league", "event", "org"]),
                ).order_by(CommunityEntity.updated_at.desc()).limit(120)
            ).all()
            rows.extend((e.name, e.entity_type == "track") for e in entities if e.name)
    except Exception:
        log.exception("Results Sweep could not load community watch targets")
    rows.extend((x, False) for x in _series_this_weekend(start, end))
    seen, out = set(), []
    for name, local in rows:
        key = re.sub(r"\W+", " ", str(name).lower()).strip()
        if key and key not in seen:
            seen.add(key)
            out.append((str(name), local))
    return out[:_int("PITMARK_RESULTS_SWEEP_MAX_TARGETS", 60, 10, 120)]


def _ask_json(prompt: str) -> dict:
    last_error: Exception | None = None
    with httpx.Client(timeout=max(30.0, float(settings.pitmark_ai_timeout_seconds))) as client:
        for attempt in range(2):
            payload = {
                "model": settings.pitmark_ai_model,
                "instructions": (
                    "You are Pitmark Results Desk. Use only supplied public evidence. "
                    "Never invent results. Return one complete valid JSON object only. "
                    "Keep every string concise and never truncate the JSON."
                ),
                "input": prompt + (
                    "\nIMPORTANT: Your previous response was invalid JSON. Return ONLY a complete valid JSON object."
                    if attempt else ""
                ),
                "max_output_tokens": 1200,
            }
            r = client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            r.raise_for_status()
            raw = _extract_output_text(r.json()).strip()
            fence = chr(96) * 3
            if raw.startswith(fence):
                raw = re.sub(r"^.{3}(?:json)?\s*|\s*.{3}$", "", raw, flags=re.I | re.S)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                last_error = exc
                log.warning("Results Sweep JSON extraction retry %s/2: %s", attempt + 1, exc)
                continue
            if not isinstance(data, dict):
                last_error = RuntimeError("Results extractor returned non-object JSON")
                continue
            return data
    raise RuntimeError(f"Results extractor returned invalid JSON twice: {last_error}")


def _extract(name: str, start: datetime, end: datetime, sources: list[dict]) -> dict:
    evidence = [{
        "title": str(x.get("title") or "")[:500],
        "source": str(x.get("source") or "")[:180],
        "url": str(x.get("url") or "")[:1000],
        "snippet": str(x.get("snippet") or "")[:1500],
        "page_excerpt": str(x.get("page_excerpt") or "")[:4500],
    } for x in sources[:6]]
    prompt = f"""Entity: {name}
Weekend: {start.date().isoformat()} through {end.date().isoformat()}
Determine if these sources confirm racing activity in this exact weekend.
PRIORITY RULE: if ANY completed race result for this entity exists inside the weekend window, status MUST be "completed" and you must report that completed result, even if a different event at the same track was later cancelled, postponed, or rained out. Use "cancelled" or "postponed" only when NO completed result is supported for the entity during the weekend.
If multiple classes or completed nights ran, choose the most newsworthy completed headline winner and mention other confirmed weekend winners/results in the summary.
Return keys: event_found(boolean), status(completed|cancelled|postponed|unknown), event_date(YYYY-MM-DD or empty), event_name, winner, class_name, summary(1-3 factual sentences), confidence(0-1), source_urls(array), source_names(array).
Evidence: {json.dumps(evidence, ensure_ascii=False)}"""
    data = _ask_json(prompt)
    data["entity_name"] = name
    data["confidence"] = max(0.0, min(1.0, float(data.get("confidence") or 0)))
    data["source_urls"] = [str(x) for x in data.get("source_urls") or [] if str(x).startswith(("http://", "https://"))][:6]
    data["source_names"] = [str(x)[:180] for x in data.get("source_names") or []][:6]
    return data


def _shopify_articles():
    try:
        q = """query SweepArticles { blogs(first:12){nodes{handle articles(first:80){nodes{id title handle publishedAt}}}}}"""
        data = shopify_service.graphql(q)
        out = []
        for blog in (data.get("blogs") or {}).get("nodes") or []:
            for article in (blog.get("articles") or {}).get("nodes") or []:
                row = dict(article); row["blog_handle"] = blog.get("handle"); out.append(row)
        return out
    except Exception as exc:
        log.warning("Results Sweep Shopify duplicate read failed: %s", exc)
        return []


def _duplicate(result: dict, articles: list[dict]) -> bool:
    winner = str(result.get("winner") or "").lower()
    tokens = _tokens(str(result.get("entity_name") or ""))
    with SessionLocal() as db:
        drafts = db.scalars(select(BlogDraft).where(BlogDraft.status.in_(["published", "approved", "draft"])).order_by(BlogDraft.id.desc()).limit(120)).all()
        for d in drafts:
            hay = f"{d.title} {d.body_html}".lower()
            if winner and winner in hay and (not tokens or any(t in hay for t in tokens)):
                return True
    for a in articles:
        hay = str(a.get("title") or "").lower()
        if winner and winner in hay and (not tokens or any(t in hay for t in tokens)):
            return True
    return False


def _fingerprint(result: dict, weekend_key: str):
    raw = "|".join(str(x).lower().strip() for x in (
        weekend_key, result.get("entity_name") or "", result.get("event_date") or "",
        result.get("class_name") or "", result.get("winner") or "", result.get("status") or "",
    ))
    return hashlib.sha256(raw.encode()).hexdigest()


def _target_state_key(weekend_key: str, entity_name: str) -> str:
    # v2 invalidates the first live pass after adding trusted local-result sources
    # and the completed-result-over-cancellation priority rule.
    digest = hashlib.sha256(entity_name.strip().lower().encode("utf-8")).hexdigest()[:24]
    return f"results_target:v2:{weekend_key}:{digest}"


def _quality(result: dict):
    urls = [str(x) for x in result.get("source_urls") or []]
    domains = {_domain(x) for x in urls if _domain(x)}
    trusted = sum(1 for x in urls if _trusted(x))
    return len(domains), trusted


def _autopublish(result: dict):
    if not _bool("PITMARK_RESULTS_SWEEP_AUTOPUBLISH", True) or result.get("status") != "completed" or not result.get("winner"):
        return False
    domains, trusted = _quality(result)
    return float(result.get("confidence") or 0) >= _float("PITMARK_RESULTS_SWEEP_AUTOPUBLISH_CONFIDENCE", 0.90) and (trusted >= 1 or domains >= 2)


def _title(result: dict):
    winner, entity, cls = str(result.get("winner") or "").strip(), str(result.get("entity_name") or "").strip(), str(result.get("class_name") or "").strip()
    return (f"{winner} Wins {cls} at {entity}" if cls and cls.lower() not in entity.lower() else f"{winner} Wins at {entity}")[:235]


def _article(result: dict):
    winner = html.escape(str(result.get("winner") or ""))
    entity = html.escape(str(result.get("entity_name") or ""))
    summary = html.escape(str(result.get("summary") or ""))
    event = html.escape(str(result.get("event_name") or ""))
    cls = html.escape(str(result.get("class_name") or ""))
    date = html.escape(str(result.get("event_date") or ""))
    body = f"<p><strong>{winner}</strong> earned the headline result at <strong>{entity}</strong>{' on ' + date if date else ''}.</p>"
    if summary: body += f"<p>{summary}</p>"
    body += "<h2>Weekend result</h2><ul>"
    body += f"<li><strong>Track / series:</strong> {entity}</li>"
    if event: body += f"<li><strong>Event:</strong> {event}</li>"
    if cls: body += f"<li><strong>Class:</strong> {cls}</li>"
    if date: body += f"<li><strong>Date:</strong> {date}</li>"
    body += f"<li><strong>Winner:</strong> {winner}</li></ul>"
    body += "<p>Pitmark Racing Co. found this result through its Sunday Night Results Sweep, which checks public racing sources even when no release reaches the Pitmark inbox.</p>"
    names = list(result.get("source_names") or [])
    links = []
    for i, url in enumerate(result.get("source_urls") or []):
        label = names[i] if i < len(names) and names[i] else _domain(url)
        links.append(f'<li><a href="{html.escape(str(url), quote=True)}" rel="noopener">{html.escape(str(label))}</a></li>')
    if links: body += "<h2>Sources</h2><ul>" + "".join(links) + "</ul>"
    return body


def _publish(result: dict, fp: str):
    title, body = _title(result), _article(result)
    blogs = shopify_service.list_blogs()
    if not blogs: raise RuntimeError("No Shopify blog is available")
    blog = next((x for x in blogs if str(x.get("handle") or "").lower() == "racing-culture"), blogs[0])
    if str(blog.get("handle") or "").lower() == "racing-culture":
        body = append_racing_culture_conversion_cta(body, title)
    image_url = None
    if _bool("PITMARK_RESULTS_SWEEP_GENERATE_IMAGES", True):
        try:
            staged = generate_and_stage_blog_image(title=title, body_html=body, content_type="race_results")
            base = (os.getenv("PITMARK_CLOUD_PUBLIC_URL") or "https://pitmarkcloud.onrender.com").rstrip("/")
            image_url = f"{base}/api/control/auth/blog/generated-image/{staged.token}"
        except Exception as exc:
            log.warning("Results Sweep hero image failed for %s: %s", title, exc)
    article = shopify_service.publish_article(blog_id=str(blog["id"]), title=title, body_html=body, image_url=image_url)
    handle = str(article.get("handle") or "")
    url = f"https://pitmarkracing.com/blogs/{blog.get('handle')}/{handle}" if handle else "https://pitmarkracing.com/blogs/racing-culture"
    durable = (((article.get("image") or {}).get("originalSrc") or "") if isinstance(article.get("image"), dict) else "") or image_url
    with SessionLocal() as db:
        draft = BlogDraft(title=title, body_html=body, content_type="race_results", seo_title=title, seo_description=str(result.get("summary") or "")[:320] or None, featured_image_url=durable, status="published")
        db.add(draft); db.flush()
        db.add(ShopifyPublishRecord(draft_id=draft.id, shopify_article_id=str(article.get("id") or ""), title=title, url=url, status="published"))
        db.commit()
    queue_event(event_key=f"results-sweep:{fp}", event_type="blog_publish", title=title, summary=str(result.get("summary") or ""), url=url, media_url=durable, payload={"source":"sunday_results_sweep","entity":result.get("entity_name"),"event_date":result.get("event_date"),"winner":result.get("winner")})
    return str(article.get("id") or ""), url


def _notify(key: str, title: str, detail: str, priority: str = "action"):
    dedupe = hashlib.sha256(key.encode()).hexdigest()[:40]
    with SessionLocal() as db:
        if db.scalar(select(EcosystemNotification).where(EcosystemNotification.dedupe_key == dedupe)):
            return
        db.add(EcosystemNotification(dedupe_key=dedupe, priority=priority, module="Results Sweep", title=title[:240], detail=detail[:3000], action_view="content", reason="Public race coverage was found outside the Pitmark inbox."))
        db.commit()


def _save(result: dict, weekend_key: str, status: str, detail: str = ""):
    fp = _fingerprint(result, weekend_key)
    with SessionLocal() as db:
        # A later verified completed result supersedes an earlier cancellation-only
        # interpretation for the same track/weekend.
        if status not in {"cancelled", "postponed"}:
            prior_cancellations = db.scalars(
                select(ResultsSweepItem).where(
                    ResultsSweepItem.weekend_key == weekend_key,
                    ResultsSweepItem.entity_name == str(result.get("entity_name") or "")[:240],
                    ResultsSweepItem.status.in_(["cancelled", "postponed"]),
                )
            ).all()
            for prior in prior_cancellations:
                prior.status = "superseded"
                prior.updated_at = utcnow()
        row = db.scalar(select(ResultsSweepItem).where(ResultsSweepItem.fingerprint == fp))
        if row is None:
            row = ResultsSweepItem(fingerprint=fp, weekend_key=weekend_key, entity_name=str(result.get("entity_name") or "")[:240])
            db.add(row)
        row.event_name = str(result.get("event_name") or "")[:300] or None
        row.event_date = str(result.get("event_date") or "")[:32] or None
        row.class_name = str(result.get("class_name") or "")[:180] or None
        row.winner = str(result.get("winner") or "")[:180] or None
        row.summary = str(result.get("summary") or "")[:5000] or None
        row.source_urls_json = json.dumps(result.get("source_urls") or [])[:12000]
        row.source_names_json = json.dumps(result.get("source_names") or [])[:6000]
        row.confidence = float(result.get("confidence") or 0)
        row.status = status; row.detail = detail[:5000] or None; row.updated_at = utcnow()
        db.commit(); db.refresh(row)
        return row


def _run_sweep_impl(force: bool = False):
    start, end, weekend_key = _weekend()
    state_key = f"results_sweep:{weekend_key}"
    if not force and get_runtime_state(state_key) == "complete":
        return {"ran":False,"reason":"already_complete","weekend_key":weekend_key}
    with SessionLocal() as db:
        stale_runs = db.scalars(
            select(ResultsSweepRun).where(
                ResultsSweepRun.weekend_key == weekend_key,
                ResultsSweepRun.status == "running",
            )
        ).all()
        for stale in stale_runs:
            stale.status = "interrupted"
            stale.note = "Interrupted by a service restart; the next pass resumes from the last completed target."
            stale.completed_at = utcnow()
        run = ResultsSweepRun(weekend_key=weekend_key)
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
    targets, articles = _targets(start, end), _shopify_articles()
    c = {"targets_checked":0,"results_found":0,"uncovered_count":0,"published_count":0,"duplicate_count":0,"cancelled_count":0,"error_count":0}
    for name, local in targets:
        target_state = _target_state_key(weekend_key, name)
        if not force and get_runtime_state(target_state) == "checked":
            continue
        c["targets_checked"] += 1
        try:
            evidence = _search(name, start, end, local)
            if not evidence:
                set_runtime_state(target_state, "checked")
                continue
            result = _extract(name, start, end, evidence)
            if not result.get("event_found"):
                set_runtime_state(target_state, "checked")
                continue
            c["results_found"] += 1
            status, fp = str(result.get("status") or "unknown").lower(), _fingerprint(result, weekend_key)
            if status in {"cancelled","postponed"}:
                _save(result, weekend_key, status)
                c["cancelled_count"] += 1
                set_runtime_state(target_state, "checked")
                continue
            if status != "completed":
                _save(result, weekend_key, "needs_review")
                c["uncovered_count"] += 1
                _notify(f"review:{fp}", f"UNCOVERED RESULTS — {name}", str(result.get("summary") or "Possible result needs verification."))
                set_runtime_state(target_state, "checked")
                continue
            if _duplicate(result, articles):
                _save(result, weekend_key, "duplicate")
                c["duplicate_count"] += 1
                set_runtime_state(target_state, "checked")
                continue
            if _autopublish(result):
                row = _save(result, weekend_key, "publishing")
                try:
                    article_id, article_url = _publish(result, fp)
                    with SessionLocal() as db:
                        current = db.get(ResultsSweepItem, row.id)
                        if current:
                            current.status="published"; current.article_id=article_id; current.article_url=article_url; current.updated_at=utcnow(); db.commit()
                    c["published_count"] += 1
                    _notify(f"published:{fp}", f"Results Sweep published — {name}", f"{_title(result)}\n{article_url}", "info")
                    set_runtime_state(target_state, "checked")
                except Exception as exc:
                    c["uncovered_count"] += 1; c["error_count"] += 1
                    with SessionLocal() as db:
                        current = db.get(ResultsSweepItem, row.id)
                        if current:
                            current.status="needs_review"; current.detail=f"Automatic publish failed: {type(exc).__name__}: {exc}"[:5000]; current.updated_at=utcnow(); db.commit()
                    _notify(f"failed:{fp}", f"UNCOVERED RESULTS — {name}", f"{result.get('summary') or ''}\nAutomatic publish failed.")
                    set_runtime_state(target_state, "checked")
            else:
                domains, trusted = _quality(result)
                detail = f"Confidence {float(result.get('confidence') or 0):.0%}; {domains} supporting domain(s); {trusted} trusted result source(s)."
                _save(result, weekend_key, "uncovered", detail)
                c["uncovered_count"] += 1
                _notify(f"uncovered:{fp}", f"UNCOVERED RESULTS — {name}", f"{result.get('summary') or ''}\n{detail}")
                set_runtime_state(target_state, "checked")
        except Exception as exc:
            c["error_count"] += 1
            log.warning("Results Sweep failed for %s: %s", name, exc)
    final_status = "partial" if c["error_count"] else "complete"
    with SessionLocal() as db:
        run = db.get(ResultsSweepRun, run_id)
        if run:
            for key, value in c.items():
                setattr(run, key, value)
            run.status = final_status
            run.completed_at = utcnow()
            run.note = (
                f"Checked {c['targets_checked']} targets; published {c['published_count']}; "
                f"uncovered {c['uncovered_count']}; duplicates {c['duplicate_count']}; "
                f"errors {c['error_count']}."
            )
            db.commit()
    set_runtime_state(state_key, final_status)
    return {"ran":True,"weekend_key":weekend_key,"status":final_status,**c}



def run_sweep(force: bool = False):
    """Run one sweep with a cross-instance Postgres advisory lock.

    Render rolling deploys can briefly keep old and new instances alive together.
    The lock guarantees that only one instance can discover/publish results at a time.
    """
    if DATABASE_URL.startswith("sqlite"):
        return _run_sweep_impl(force=force)

    with engine.connect() as lock_conn:
        acquired = bool(
            lock_conn.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": RESULTS_SWEEP_LOCK_KEY},
            )
        )
        if not acquired:
            return {"ran": False, "reason": "already_running_elsewhere"}
        try:
            return _run_sweep_impl(force=force)
        finally:
            try:
                lock_conn.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": RESULTS_SWEEP_LOCK_KEY},
                )
            except Exception:
                log.exception("Results Sweep advisory lock release failed")


def run_if_due():
    if not _bool("PITMARK_RESULTS_SWEEP_ENABLED", True):
        return {"ran":False,"reason":"disabled"}
    now = datetime.now(ET)
    due = (now.weekday() == 6 and now.hour >= _int("PITMARK_RESULTS_SWEEP_SUNDAY_HOUR", 21, 17, 23)) or (now.weekday() == 0 and now.hour >= _int("PITMARK_RESULTS_SWEEP_MONDAY_CATCHUP_HOUR", 8, 5, 12))
    return run_sweep(False) if due else {"ran":False,"reason":"not_due"}


def list_items(limit: int = 100, status: str | None = None):
    with SessionLocal() as db:
        stmt = select(ResultsSweepItem)
        if status: stmt = stmt.where(ResultsSweepItem.status == status)
        rows = db.scalars(stmt.order_by(ResultsSweepItem.id.desc()).limit(max(1,min(limit,250)))).all()
        out=[]
        for x in rows:
            try: urls=json.loads(x.source_urls_json or "[]")
            except Exception: urls=[]
            out.append({"id":x.id,"weekend_key":x.weekend_key,"entity_name":x.entity_name,"event_name":x.event_name,"event_date":x.event_date,"class_name":x.class_name,"winner":x.winner,"summary":x.summary,"source_urls":urls,"confidence":x.confidence,"status":x.status,"article_url":x.article_url,"detail":x.detail,"created_at":x.created_at.isoformat() if x.created_at else None})
        return out


def latest_run():
    with SessionLocal() as db:
        x = db.scalar(select(ResultsSweepRun).order_by(ResultsSweepRun.id.desc()).limit(1))
        return None if not x else {"id":x.id,"weekend_key":x.weekend_key,"status":x.status,"targets_checked":x.targets_checked,"results_found":x.results_found,"uncovered_count":x.uncovered_count,"published_count":x.published_count,"duplicate_count":x.duplicate_count,"cancelled_count":x.cancelled_count,"error_count":x.error_count,"note":x.note,"created_at":x.created_at.isoformat() if x.created_at else None,"completed_at":x.completed_at.isoformat() if x.completed_at else None}
