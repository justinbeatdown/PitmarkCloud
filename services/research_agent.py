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
from services.shield_ecosystem import inspect_external_url, audit_blocked_research_source
from services.racing_community import CommunityEntity, ResearchJob, CampaignParticipant, ResearchEvidence

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
        qs.extend([
            f'{n} rookie driver', f'{n} first season racing', f'{n} first year racing',
            f'{n} racing results 2026', f'{n} race results 2026',
            f'{n} speedway results', f'{n} driver profile',
            f'{n} racing Facebook', f'{n} racing Instagram',
            f'{n} race team', f'{n} car number racing'
        ])
    if entity.entity_type == 'league':
        qs.extend([f'{n} iRacing league', f'{n} racing league'])
    if entity.entity_type == 'track':
        qs.extend([f'{n} speedway track', f'{n} raceway'])
    return list(dict.fromkeys(qs))[:18]


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



def _extract_rookie_fields(name: str, strong: list[dict], corroborated: bool) -> dict:
    """Extract only conservative, source-backed rookie profile fields.
    A field is persisted only when the same normalized value appears in at
    least two strong sources from different domains.
    """
    if not corroborated:
        return {}
    candidates: dict[str, list[tuple[str,str]]] = {
        'car_number': [], 'class_division': [], 'home_track_series': [],
        'hometown_region': [], 'rookie_status': []
    }
    class_terms = [
        'late model','sprint car','modified','stock car','street stock',
        'sportsman','legend','kart','pro late model','super late model'
    ]
    for item in strong:
        text = _clean(' '.join([item.get('title',''), item.get('snippet','')]))
        low = text.lower()
        domain = (item.get('source_domain') or urlparse(item.get('url','')).netloc).lower().removeprefix('www.')
        m = re.search(r'(?:car|no\.?|#)\s*#?\s*(\d{1,3}[A-Za-z]?)\b', text, re.I)
        if m: candidates['car_number'].append((m.group(1), domain))
        for term in class_terms:
            if term in low: candidates['class_division'].append((term.title(), domain))
        m = re.search(r'\b(?:at|from)\s+([A-Z][A-Za-z0-9&.\' -]{2,60}(?:Speedway|Raceway|Motorsports Park|Motor Speedway|Racing Series|Series))\b', text)
        if m: candidates['home_track_series'].append((m.group(1).strip(), domain))
        m = re.search(r'\b(?:from|hometown[:\s]+)\s+([A-Z][A-Za-z.\' -]+,\s*[A-Z]{2})\b', text)
        if m: candidates['hometown_region'].append((m.group(1).strip(), domain))
        if re.search(r'\b(rookie|first[- ]year|first season)\b', low):
            candidates['rookie_status'].append(('Public sources identify this as a rookie/first-season campaign.', domain))
    verified={}
    for field, vals in candidates.items():
        grouped={}
        for value, domain in vals:
            key=value.strip().lower()
            grouped.setdefault(key, {'value':value.strip(),'domains':set()})['domains'].add(domain)
        winners=[v for v in grouped.values() if len(v['domains']) >= 2]
        if winners:
            winners.sort(key=lambda x: len(x['domains']), reverse=True)
            verified[field]=winners[0]['value']
    return verified



def _ai_rookie_scout(name: str, evidence: list[dict]) -> dict:
    """Turn public search evidence into a conservative pre-outreach scouting brief.
    The model is not allowed to invent facts: every populated field must cite source
    indexes supplied in the evidence packet.
    """
    from services.autopilot_ai import ai_enabled
    from utils.config import settings
    if not ai_enabled() or not evidence:
        return {}
    packet=[]
    for i,item in enumerate(evidence[:24], start=1):
        packet.append({
            'source_index': i,
            'title': item.get('title',''),
            'snippet': item.get('snippet',''),
            'url': item.get('url',''),
            'domain': item.get('source_domain',''),
            'identity_score': item.get('identity_score',0),
        })
    instructions = """You are Pitmark Racing Co.'s conservative motorsports scouting analyst.
Use ONLY the supplied public-search evidence. Never guess. Identify whether the evidence
appears to describe the named racing driver. Return JSON only. Every non-null factual field
must include source_indexes that directly support it. If identity is ambiguous, leave facts
null and say why. Evaluate feature_candidate based on public racing story value, not fame.
Good candidates include rookies, grassroots racers, compelling first seasons, community
stories, progression, unusual paths, or documented accomplishments."""
    prompt = {
        'driver_name': name,
        'task': 'Pre-outreach Rookie Year scouting. Find real-world racing facts before Pitmark contacts the driver.',
        'required_output': {
            'identity_match':'high|medium|low',
            'hometown_region':{'value':None,'source_indexes':[]},
            'class_division':{'value':None,'source_indexes':[]},
            'car_number':{'value':None,'source_indexes':[]},
            'home_track_series':{'value':None,'source_indexes':[]},
            'rookie_evidence':{'value':None,'source_indexes':[]},
            'notable_results_story':{'value':None,'source_indexes':[]},
            'public_social_or_team_presence':{'value':None,'source_indexes':[]},
            'feature_candidate':'strong|possible|insufficient_evidence|not_a_fit',
            'why_feature':[],
            'identity_notes':'',
        },
        'evidence': packet,
    }
    import json as _json
    headers={'Authorization':f'Bearer {settings.openai_api_key.strip()}','Content-Type':'application/json'}
    payload={
        'model':settings.pitmark_ai_model,
        'instructions':instructions,
        'input':_json.dumps(prompt),
        'max_output_tokens':1000,
        'text':{'format':{'type':'json_object'}},
    }
    try:
        with httpx.Client(timeout=max(30.0,settings.pitmark_ai_timeout_seconds)) as client:
            r=client.post('https://api.openai.com/v1/responses',headers=headers,json=payload)
            r.raise_for_status()
            data=r.json()
        raw=data.get('output_text')
        if not raw:
            chunks=[]
            for out in data.get('output') or []:
                for content in out.get('content') or []:
                    if isinstance(content,dict) and isinstance(content.get('text'),str):
                        chunks.append(content['text'])
            raw=''.join(chunks)
        result=_json.loads(raw or '{}')
        # Enforce source-index provenance after the model returns.
        valid=set(range(1,len(packet)+1))
        for key in ('hometown_region','class_division','car_number','home_track_series','rookie_evidence','notable_results_story','public_social_or_team_presence'):
            field=result.get(key)
            if not isinstance(field,dict):
                result[key]={'value':None,'source_indexes':[]}; continue
            refs=[x for x in field.get('source_indexes',[]) if isinstance(x,int) and x in valid]
            if field.get('value') and not refs:
                result[key]={'value':None,'source_indexes':[]}
            else:
                field['source_indexes']=refs
        result['_evidence_packet']=packet
        return result
    except Exception as exc:
        log.warning('AI rookie scouting synthesis failed for %s: %s',name,exc)
        return {}

def _profile_from_scout(scout: dict) -> dict:
    out={}
    mapping={
        'hometown_region':'hometown_region','class_division':'class_division',
        'car_number':'car_number','home_track_series':'home_track_series',
        'rookie_evidence':'rookie_status','notable_results_story':'notable_results_story',
        'public_social_or_team_presence':'public_presence'
    }
    for src,dst in mapping.items():
        field=scout.get(src)
        if isinstance(field,dict) and field.get('value'):
            out[dst]=str(field['value']).strip()
            out[dst+'_source_indexes']=field.get('source_indexes',[])
    return out

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
    items = _dedupe(items)[:80]

    # Shield protects the entire ecosystem, including URLs found by Autopilot.
    # Unsafe/local/non-web targets never enter the reusable intelligence ledger.
    safe_items = []
    blocked_count = 0
    for item in items:
        verdict = inspect_external_url(item.get('url', ''))
        if not verdict.get('safe'):
            blocked_count += 1
            audit_blocked_research_source(item.get('url', ''), verdict.get('reason', 'unsafe source'), job.id)
            continue
        item = dict(item); item['source_domain'] = verdict.get('domain')
        safe_items.append(item)

    scored = []
    for item in safe_items:
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
        # Intake and media permission are post-scouting workflow steps, not public-research gaps.

    scout = _ai_rookie_scout(entity_snapshot['name'], scored) if job.research_type == 'rookie_deep_dive' else {}
    verified_profile = _profile_from_scout(scout) if scout else (_extract_rookie_fields(entity_snapshot['name'], strong, corroborated) if job.research_type == 'rookie_deep_dive' else {})
    scout_identity = str(scout.get('identity_match') or '').lower()
    if scout_identity == 'high' and verified_profile:
        identity_conf = max(identity_conf, 85)
        verification = max(verification, 78)

    facts_used = []
    for s in strong[:6]:
        facts_used.append({'claim': s['title'], 'source': s['source'], 'url': s['url'], 'identity_score': s['identity_score']})
    facts_omitted = []
    for s in (plausible + weak)[:6]:
        facts_omitted.append({'claim': s['title'], 'reason': 'Identity match is not strong enough to use as a fact.', 'url': s['url'], 'identity_score': s['identity_score']})

    if job.research_type == 'rookie_deep_dive' and scout:
        fit = scout.get('feature_candidate','insufficient_evidence')
        if fit == 'strong':
            action='strong_feature_candidate'
            recommendation='Strong pre-outreach feature candidate. Review the sourced scouting brief, then reach out for confirmation, permission and the driver’s own story.'
        elif fit == 'possible':
            action='possible_feature_candidate'
            recommendation='Promising feature candidate. Public evidence gives Pitmark a reason to reach out; use intake to confirm details and fill the human side of the story.'
        elif fit == 'not_a_fit':
            action='not_recommended'
            recommendation='Public evidence does not currently suggest a strong Rookie Year feature fit.'
        else:
            action='insufficient_public_evidence'
            recommendation='Not enough reliable public racing evidence yet to judge this driver. Add one known detail such as track, class, car number, region or social handle and research again.'
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
        'shield_blocked_source_count': blocked_count,
        'strong_source_count': len(strong),
        'plausible_source_count': len(plausible),
        'verified_external_identity': corroborated,
        'verified_profile': verified_profile,
        'scouting': {k:v for k,v in scout.items() if k != '_evidence_packet'} if scout else {},
        'feature_candidate': scout.get('feature_candidate') if scout else 'insufficient_evidence',
        'why_feature': scout.get('why_feature',[]) if scout else [],
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

        # Shared Racing Community intelligence ledger. Reuse evidence across Campaigns,
        # Outreach and future PRT clients instead of rediscovering it in each module.
        for source in scored[:12]:
            existing = db.scalar(select(ResearchEvidence).where(
                ResearchEvidence.entity_id == entity_snapshot['id'],
                ResearchEvidence.source_url == source['url']
            ))
            status = 'verified' if corroborated and source['identity_score'] >= 75 else ('supported' if source['identity_score'] >= 55 else 'lead')
            confidence = min(100.0, float(source['identity_score']))
            if existing:
                existing.research_job_id = job.id
                existing.title = source['title']
                existing.source_name = source.get('source')
                existing.source_domain = source.get('source_domain') or urlparse(source['url']).netloc.lower().removeprefix('www.')
                existing.identity_score = float(source['identity_score'])
                existing.verification_status = status
                existing.confidence = confidence
                existing.last_verified_at = utcnow()
                existing.updated_at = utcnow()
            else:
                db.add(ResearchEvidence(
                    entity_id=entity_snapshot['id'], research_job_id=job.id, title=source['title'],
                    source_name=source.get('source'), source_url=source['url'],
                    source_domain=source.get('source_domain') or urlparse(source['url']).netloc.lower().removeprefix('www.'),
                    identity_score=float(source['identity_score']), verification_status=status, confidence=confidence,
                    last_verified_at=utcnow(), updated_at=utcnow()
                ))

        entity_row = db.get(CommunityEntity, entity_snapshot['id'])
        if entity_row:
            # Research can raise confidence only when corroborated; otherwise it records
            # evidence without pretending an uncertain identity is verified.
            entity_row.identity_confidence = max(float(entity_row.identity_confidence or 0), float(identity_conf))
            if corroborated or (scout_identity == 'high' and verified_profile):
                entity_row.verification_status = 'supported'
                entity_row.last_verified_at = utcnow()
            if verified_profile:
                try:
                    public_data = json.loads(entity_row.public_data_json or '{}')
                except Exception:
                    public_data = {}
                public_data.setdefault('rookie_year', {}).update(verified_profile)
                public_data['rookie_year']['research_job_id'] = job.id
                public_data['rookie_year']['verification'] = 'source_cited_public_scouting'
                entity_row.public_data_json = json.dumps(public_data)
                if verified_profile.get('hometown_region') and not entity_row.region:
                    entity_row.region = verified_profile['hometown_region']
            entity_row.updated_at = utcnow()

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
