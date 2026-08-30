from __future__ import annotations

import asyncio
import html as html_lib
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import httpx
from sqlalchemy import select

from services.database import SessionLocal
from services.racing_community import CommunityEntity, ResearchJob, CampaignParticipant

log = logging.getLogger('pitmark.autopilot.research')
GOOGLE_NEWS = 'https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en'
DDG_HTML = 'https://html.duckduckgo.com/html/?q={}'
BING_RSS = 'https://www.bing.com/search?format=rss&q={}'
RACING_TERMS = (
    'racing','race','racer','speedway','motorsport','motorsports','iracing','sim racing',
    'late model','sprint car','modified','stock car','kart','nascar','indycar','imsa','dirt','oval','road course'
)


def utcnow():
    return datetime.now(timezone.utc)


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', html_lib.unescape(re.sub(r'<[^>]+>', ' ', text or ''))).strip()


def _tag(raw: str, tag: str) -> str:
    m = re.search(fr'<{tag}[^>]*>(.*?)</{tag}>', raw, re.I | re.S)
    return _clean(m.group(1)) if m else ''


def _unwrap_ddg(url: str) -> str:
    try:
        q = parse_qs(urlparse(url).query)
        if 'uddg' in q and q['uddg']:
            return unquote(q['uddg'][0])
    except Exception:
        pass
    return url


def _google_news_search(client: httpx.Client, query: str, limit: int = 8) -> list[dict]:
    out = []
    try:
        r = client.get(GOOGLE_NEWS.format(quote_plus(query)))
        r.raise_for_status()
        for raw in re.findall(r'<item>(.*?)</item>', r.text, re.I | re.S)[:limit]:
            title = _tag(raw, 'title')
            url = _tag(raw, 'link')
            desc = _tag(raw, 'description')
            source = _tag(raw, 'source') or 'Google News'
            if title and url:
                out.append({'title': title, 'url': url, 'snippet': desc, 'source': source, 'search': query})
    except Exception as exc:
        log.info('Google News research search failed for %s: %s', query, exc)
    return out


def _ddg_search(client: httpx.Client, query: str, limit: int = 8) -> list[dict]:
    out = []
    try:
        r = client.get(DDG_HTML.format(quote_plus(query)), headers={'User-Agent': 'Mozilla/5.0 PitmarkAutopilot/0.12'})
        r.raise_for_status()
        # DuckDuckGo HTML result blocks. Keep parsing intentionally conservative.
        blocks = re.findall(r'<div[^>]+class="[^"]*result[^"]*"[^>]*>(.*?)</div>\s*</div>', r.text, re.I | re.S)
        if not blocks:
            blocks = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.I | re.S)
            for href, title_html in blocks[:limit]:
                out.append({'title': _clean(title_html), 'url': _unwrap_ddg(html_lib.unescape(href)), 'snippet': '', 'source': 'Web search', 'search': query})
            return out
        for block in blocks[:limit]:
            a = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.I | re.S)
            if not a:
                continue
            s = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', block, re.I | re.S)
            out.append({'title': _clean(a.group(2)), 'url': _unwrap_ddg(html_lib.unescape(a.group(1))), 'snippet': _clean(s.group(1)) if s else '', 'source': 'Web search', 'search': query})
    except Exception as exc:
        log.info('Web research search failed for %s: %s', query, exc)
    return out



def _bing_search(client: httpx.Client, query: str, limit: int = 8) -> list[dict]:
    out = []
    try:
        r = client.get(BING_RSS.format(quote_plus(query)), headers={'User-Agent': 'Mozilla/5.0 PitmarkAutopilot/0.12.5'})
        r.raise_for_status()
        for raw in re.findall(r'<item>(.*?)</item>', r.text, re.I | re.S)[:limit]:
            title = _tag(raw, 'title')
            url = _tag(raw, 'link')
            desc = _tag(raw, 'description')
            if title and url:
                out.append({'title': title, 'url': url, 'snippet': desc, 'source': 'Bing Web', 'search': query})
    except Exception as exc:
        log.info('Bing research search failed for %s: %s', query, exc)
    return out

def _dedupe(items: list[dict]) -> list[dict]:
    seen = set(); out = []
    for item in items:
        key = (item.get('url') or '').strip().lower() or (item.get('title') or '').strip().lower()
        if not key or key in seen:
            continue
        seen.add(key); out.append(item)
    return out


def _evidence_score(name: str, item: dict, entity: CommunityEntity) -> tuple[int, list[str]]:
    text = ' '.join([item.get('title',''), item.get('snippet','')]).lower()
    reasons = []
    score = 0
    if name.lower() in text:
        score += 45; reasons.append('exact name match')
    parts = [p for p in re.split(r'\W+', name.lower()) if len(p) > 2]
    if parts and all(p in text for p in parts):
        score += 15; reasons.append('all name tokens present')
    if any(t in text for t in RACING_TERMS):
        score += 20; reasons.append('racing context')
    if entity.platform and entity.platform.lower() in text:
        score += 10; reasons.append(f'{entity.platform} context')
    if entity.region and entity.region.lower() in text:
        score += 10; reasons.append('region match')
    return min(score, 100), reasons


def _queries(entity: CommunityEntity, research_type: str) -> list[str]:
    n = f'"{entity.name}"'
    qs = [
        f'{n} racing',
        f'{n} race car',
        f'{n} driver',
        f'{n} speedway',
        f'{n} race results',
        f'{n} motorsports',
    ]
    if entity.region:
        qs.extend([f'{n} racing {entity.region}', f'{n} driver {entity.region}'])
    if entity.platform:
        qs.append(f'{n} {entity.platform}')
    if entity.community_lane in ('sim','crossover') or entity.platform:
        qs.extend([f'{n} iRacing', f'{n} sim racing'])
    if research_type == 'rookie_deep_dive':
        qs.extend([f'{n} rookie driver', f'{n} first season racing', f'{n} first year racing'])
    if entity.entity_type == 'league':
        qs.extend([f'{n} iRacing league', f'{n} racing league'])
    if entity.entity_type == 'track':
        qs.extend([f'{n} speedway track', f'{n} raceway'])
    return list(dict.fromkeys(qs))[:12]


def _participant_context(db, entity_id: int) -> dict:
    row = db.scalar(select(CampaignParticipant).where(CampaignParticipant.entity_id == entity_id).order_by(CampaignParticipant.updated_at.desc()))
    if not row:
        return {}
    return {
        'campaign_stage': row.stage,
        'intake_status': row.intake_status,
        'verification_status': row.verification_status,
        'media_permission': row.media_permission,
        'guardian_status': row.guardian_status,
    }


def process_job(job_id: int) -> dict:
    with SessionLocal() as db:
        job = db.get(ResearchJob, job_id)
        if not job:
            raise ValueError('Research job not found')
        if job.status == 'complete':
            return {'job_id': job.id, 'status': job.status}
        entity = db.get(CommunityEntity, job.entity_id) if job.entity_id else None
        if not entity:
            job.status = 'failed'; job.brief_json = json.dumps({'error':'Entity research currently requires an entity record.'}); job.updated_at = utcnow(); db.commit()
            return {'job_id': job.id, 'status': job.status}
        job.status = 'researching'; job.updated_at = utcnow(); db.commit()
        entity_snapshot = {
            'id': entity.id, 'name': entity.name, 'entity_type': entity.entity_type,
            'community_lane': entity.community_lane, 'platform': entity.platform, 'region': entity.region,
            'summary': entity.summary, 'source_url': entity.source_url, 'source_name': entity.source_name,
            'verification_status': entity.verification_status, 'identity_confidence': entity.identity_confidence,
        }
        ctx = _participant_context(db, entity.id)

    queries = _queries(entity, job.research_type)
    items = []
    with httpx.Client(timeout=14, follow_redirects=True) as client:
        for q in queries:
            items.extend(_bing_search(client, q, 8))
            items.extend(_google_news_search(client, q, 5))
            items.extend(_ddg_search(client, q, 5))
    items = _dedupe(items)[:40]

    scored = []
    for item in items:
        score, reasons = _evidence_score(entity_snapshot['name'], item, entity)
        item = dict(item); item['identity_score'] = score; item['match_reasons'] = reasons
        if score >= 35:
            scored.append(item)
    scored.sort(key=lambda x: x['identity_score'], reverse=True)

    strong = [x for x in scored if x['identity_score'] >= 75]
    plausible = [x for x in scored if 55 <= x['identity_score'] < 75]
    weak = [x for x in scored if x['identity_score'] < 55]

    # External identity is only considered verified when multiple independent-looking sources strongly match.
    strong_domains = {urlparse(x['url']).netloc.lower().removeprefix('www.') for x in strong if x.get('url')}
    corroborated = len(strong) >= 2 and len(strong_domains) >= 2
    identity_conf = 92 if corroborated else (72 if strong else (50 if plausible else 25))
    verification = 88 if corroborated else (62 if strong else (40 if plausible else 20))

    known = []
    if entity_snapshot.get('platform'): known.append(f"Platform: {entity_snapshot['platform']}")
    if entity_snapshot.get('region'): known.append(f"Region: {entity_snapshot['region']}")
    if entity_snapshot.get('summary'): known.append(entity_snapshot['summary'])
    if ctx:
        known.extend([
            f"Rookie Year stage: {ctx.get('campaign_stage')}",
            f"Intake: {ctx.get('intake_status')}",
            f"Media permission: {ctx.get('media_permission')}",
        ])

    gaps = []
    if not entity_snapshot.get('region'): gaps.append('hometown / racing region')
    if not entity_snapshot.get('platform') and entity_snapshot.get('community_lane') in ('sim','crossover'): gaps.append('sim platform / iRacing identity')
    if job.research_type == 'rookie_deep_dive':
        gaps.extend(['class / division', 'car number', 'home track / series', 'rookie-status confirmation'])
        if ctx.get('intake_status') != 'received': gaps.append('completed Rookie Year intake')
        if ctx.get('media_permission') != 'approved': gaps.append('approved media / photo permission')

    facts_used = []
    for s in strong[:6]:
        facts_used.append({'claim': s['title'], 'source': s['source'], 'url': s['url'], 'identity_score': s['identity_score']})
    facts_omitted = []
    for s in (plausible + weak)[:6]:
        facts_omitted.append({'claim': s['title'], 'reason': 'Identity match is not strong enough to use as a fact.', 'url': s['url'], 'identity_score': s['identity_score']})

    if job.research_type == 'rookie_deep_dive' and ctx.get('intake_status') == 'sent':
        action = 'wait_for_intake_then_verify'
        recommendation = 'Jon is already in the intake stage. Wait for his answers, then use them to target a second verification pass before story drafting.' if entity_snapshot['name'].lower() == 'jon russel' else 'Wait for the driver intake, then use those details to run a targeted verification pass before story drafting.'
    elif corroborated:
        action = 'review_verified_research'
        recommendation = 'Strong public-source identity evidence found. Review the source ledger before using the facts in outreach or content.'
    elif strong or plausible:
        action = 'research_more'
        recommendation = 'Some relevant public evidence was found, but identity is not sufficiently corroborated. Add known racing details or run Research More.'
    else:
        action = 'needs_more_context'
        recommendation = 'No safe identity match was established from the current information. Add class, car number, track, league, region, or social handle before deeper outreach research.'

    brief = {
        'subject': entity_snapshot['name'],
        'entity_type': entity_snapshot['entity_type'],
        'research_type': job.research_type,
        'status_summary': 'Research completed without making external contact.',
        'what_we_know': known,
        'identity_confidence': identity_conf,
        'verification_score': verification,
        'source_count': len(scored),
        'strong_source_count': len(strong),
        'plausible_source_count': len(plausible),
        'verified_external_identity': corroborated,
        'strengths': ([f'{len(strong)} strong public-source match(es) found'] if strong else []) + (['Existing Pitmark campaign context is available'] if ctx else []),
        'weaknesses': gaps,
        'recommended_action': action,
        'recommendation': recommendation,
        'research_more_supported': True,
        'search_queries': queries,
        'sources': scored[:12],
        'safety_note': 'Public search results are leads until identity is corroborated. Uncertain facts are omitted from outreach/content.',
    }

    # Outreach draft only uses current internal facts. For an intake-sent rookie, no redundant pitch is generated.
    outreach = None
    if job.research_type != 'rookie_deep_dive' and corroborated:
        outreach = f"Hey! I’m with Pitmark Racing Co. I was checking out {entity_snapshot['name']} and wanted to introduce ourselves. We’re building tools and community projects around racers and racing organizations, and there looks like there may be a natural fit. If you’re open to it, I’d love to learn a little more about what you’re doing and see where Pitmark might be useful. 🏁"

    completeness = min(100, 35 + min(len(scored), 8) * 5 + (15 if ctx else 0) + (10 if corroborated else 0))
    source_urls = [{'title': x['title'], 'url': x['url'], 'source': x['source'], 'identity_score': x['identity_score']} for x in scored[:12]]

    with SessionLocal() as db:
        job = db.get(ResearchJob, job_id)
        job.status = 'verifying'; job.updated_at = utcnow(); db.commit()
        job.status = 'complete'
        job.completeness = float(completeness)
        job.verification_score = float(verification)
        job.brief_json = json.dumps(brief)
        job.facts_used_json = json.dumps(facts_used)
        job.facts_omitted_json = json.dumps(facts_omitted)
        job.source_urls_json = json.dumps(source_urls)
        job.recommended_action = action
        job.outreach_draft = outreach
        job.updated_at = utcnow()
        db.commit()
    return {'job_id': job_id, 'status': 'complete', 'verification_score': verification, 'completeness': completeness}


def process_queued(limit: int = 2) -> int:
    with SessionLocal() as db:
        ids = list(db.scalars(select(ResearchJob.id).where(ResearchJob.status == 'queued').order_by(ResearchJob.created_at.asc()).limit(limit)).all())
    done = 0
    for job_id in ids:
        try:
            process_job(job_id); done += 1
        except Exception as exc:
            log.exception('Research job %s failed', job_id)
            with SessionLocal() as db:
                row = db.get(ResearchJob, job_id)
                if row:
                    row.status = 'failed'; row.brief_json = json.dumps({'error': str(exc)[:500]}); row.updated_at = utcnow(); db.commit()
    return done


async def research_worker_loop():
    await asyncio.sleep(8)
    while True:
        try:
            await asyncio.to_thread(process_queued, 2)
        except Exception:
            log.exception('Autopilot Research Agent worker failed')
        await asyncio.sleep(15)
