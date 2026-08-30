from __future__ import annotations

import hmac
import json
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from services.database import SessionLocal
from services.control_center import SocialPost, ShieldEvent, OutreachContact, BlogDraft, AutopilotOpportunity, classify, fingerprint, compose_fallback, serialize, utcnow
from services.opportunity_engine import evaluate_recent
from services.autopilot_ai import compose_with_ai
from services.control_auth import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    admin_user_exists,
    authenticate_password,
    change_password,
    create_initial_admin,
    issue_session,
    require_control_user,
    user_from_request,
)
from utils.config import settings
from utils.security import enforce_rate_limit
from services.autopilot_intelligence import scan_now, status as intelligence_status_data

router = APIRouter()


def auth(request: Request, admin_key: str | None):
    return require_control_user(request, admin_key)


def set_session_cookie(response: Response, token: str):
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.environment.strip().lower() == 'production',
        samesite='strict',
        path='/',
    )


class LoginRequest(BaseModel):
    username: str
    password: str


class BootstrapRequest(BaseModel):
    username: str = 'admin'
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ComposeRequest(BaseModel):
    platform: str = 'facebook'
    goal: str = 'community'
    prompt: str = ''
    topic: str | None = None
    tone: str = 'pitmark'
    use_context: bool = True


class SavePost(BaseModel):
    platform: str
    body: str
    title: str | None = None
    content_type: str = 'community'
    source: str = 'manual'
    risk: str = 'low'
    scheduled_for: str | None = None


class Decision(BaseModel):
    action: str
    scheduled_for: str | None = None


class PostUpdate(BaseModel):
    body: str | None = None
    title: str | None = None
    content_type: str | None = None
    scheduled_for: str | None = None


class ShieldIngest(BaseModel):
    source_message_id: str
    sender: str
    subject: str = ''
    body: str = ''


class ShieldAction(BaseModel):
    action: str
    acknowledged: bool = False


class ShieldTestRequest(BaseModel):
    clear_previous_tests: bool = False


class OutreachCreate(BaseModel):
    name: str
    organization: str | None = None
    contact_type: str = 'track'
    email: str | None = None
    stage: str = 'prospect'
    supporter_status: str = 'unverified'
    next_follow_up: str | None = None
    notes: str | None = None


class OutreachUpdate(BaseModel):
    organization: str | None = None
    contact_type: str | None = None
    email: str | None = None
    stage: str | None = None
    supporter_status: str | None = None
    next_follow_up: str | None = None
    notes: str | None = None


class BlogCreate(BaseModel):
    title: str
    body_html: str
    content_type: str = 'article'
    seo_title: str | None = None
    seo_description: str | None = None
    featured_image_url: str | None = None
    scheduled_for: str | None = None


class BlogDecision(BaseModel):
    action: str
    scheduled_for: str | None = None


class BlogGenerate(BaseModel):
    subject: str
    content_type: str = 'track_spotlight'
    notes: str | None = None


@router.get('/auth/state')
def auth_state(request: Request):
    user = user_from_request(request)
    return {
        'authenticated': bool(user),
        'setup_required': not admin_user_exists(),
        'username': user.username if user else None,
    }


@router.post('/auth/bootstrap')
def bootstrap(req: BootstrapRequest, request: Request, response: Response, x_pitmark_admin_key: str | None = Header(default=None)):
    enforce_rate_limit(request, 'control-bootstrap', 5, 300)
    if admin_user_exists():
        raise HTTPException(409, 'Control Center is already initialized.')
    if not settings.pitmark_admin_key or not x_pitmark_admin_key or not hmac.compare_digest(x_pitmark_admin_key, settings.pitmark_admin_key):
        raise HTTPException(401, 'Pitmark Admin Key is required for first-time setup.')
    try:
        user = create_initial_admin(req.username, req.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    token = issue_session(authenticate_password(user.username, req.password))
    set_session_cookie(response, token)
    return {'ok': True, 'username': user.username}


@router.post('/auth/login')
def login(req: LoginRequest, request: Request, response: Response):
    enforce_rate_limit(request, 'control-login', 8, 300)
    if not admin_user_exists():
        raise HTTPException(409, 'Control Center setup is required.')
    user = authenticate_password(req.username, req.password)
    if not user:
        raise HTTPException(401, 'Invalid username or password.')
    set_session_cookie(response, issue_session(user))
    return {'ok': True, 'username': user.username}


@router.post('/auth/logout')
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path='/', samesite='strict')
    return {'ok': True}


@router.get('/auth/me')
def me(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    user = auth(request, x_pitmark_admin_key)
    return {'authenticated': True, 'username': user.username if user else 'service-admin'}


@router.post('/auth/change-password')
def change_control_password(req: ChangePasswordRequest, request: Request, response: Response, x_pitmark_admin_key: str | None = Header(default=None)):
    user = auth(request, x_pitmark_admin_key)
    if not user:
        raise HTTPException(400, 'Password changes require a signed-in Control Center user.')
    try:
        change_password(user.id, req.current_password, req.new_password)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    response.delete_cookie(SESSION_COOKIE, path='/', samesite='strict')
    return {'ok': True, 'reauthenticate': True}


@router.get('/status')
def status(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    user = auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        return {
            'service': 'Pitmark Control Center',
            'username': user.username if user else 'service-admin',
            'autopilot': True,
            'shield': True,
            'social_pending': len(db.scalars(select(SocialPost).where(SocialPost.status == 'pending')).all()),
            'shield_review': len(db.scalars(select(ShieldEvent).where(ShieldEvent.classification == 'Review')).all()),
            'outreach_contacts': len(db.scalars(select(OutreachContact)).all()),
            'blog_drafts': len(db.scalars(select(BlogDraft).where(BlogDraft.status == 'draft')).all()),
        }


@router.post('/autopilot/composer/generate')
def compose(req: ComposeRequest, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    request_text = (req.topic or req.prompt).strip()
    try:
        ai = compose_with_ai(platform=req.platform, goal=req.goal, prompt=request_text, tone=req.tone)
        result = {
            'platform': req.platform,
            'goal': req.goal,
            'body': ai.body,
            'visual_suggestion': None,
            'provider': ai.provider,
            'model': ai.model,
            'warnings': [],
        }
    except Exception as exc:
        result = compose_fallback(req.platform, req.goal, request_text)
        result['warnings'] = [f'AI unavailable: {type(exc).__name__}']
    result['tone'] = req.tone
    result['context_used'] = req.use_context
    return result


@router.post('/autopilot/posts')
def save_post(req: SavePost, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        p = SocialPost(platform=req.platform, title=req.title, body=req.body, content_type=req.content_type, source=req.source, risk=req.risk, status='pending', scheduled_for=req.scheduled_for)
        db.add(p); db.commit(); db.refresh(p)
        return serialize(p)


@router.get('/autopilot/posts')
def posts(request: Request, status: str | None = None, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        q = select(SocialPost).order_by(SocialPost.id.desc())
        if status:
            q = q.where(SocialPost.status == status)
        return [serialize(x) for x in db.scalars(q).all()]


@router.patch('/autopilot/posts/{post_id}')
def update_post(post_id: int, req: PostUpdate, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        p = db.get(SocialPost, post_id)
        if not p:
            raise HTTPException(404, 'Post not found')
        for key, value in req.model_dump(exclude_unset=True).items():
            setattr(p, key, value)
        p.updated_at = utcnow(); db.commit(); db.refresh(p)
        return serialize(p)


@router.post('/autopilot/posts/{post_id}/decision')
def decide(post_id: int, req: Decision, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    allowed = {'approve', 'reject', 'schedule', 'archive'}
    if req.action not in allowed:
        raise HTTPException(400, f'action must be one of: {", ".join(sorted(allowed))}')
    with SessionLocal() as db:
        p = db.get(SocialPost, post_id)
        if not p:
            raise HTTPException(404, 'Post not found')
        if req.action == 'schedule':
            if not req.scheduled_for:
                raise HTTPException(400, 'scheduled_for is required to schedule a post')
            p.status = 'scheduled'; p.scheduled_for = req.scheduled_for
        elif req.action == 'approve':
            p.status = 'approved'
        elif req.action == 'reject':
            p.status = 'rejected'
        else:
            p.status = 'archived'
        p.updated_at = utcnow(); db.commit(); db.refresh(p)
        return serialize(p)


@router.post('/shield/ingest')
def shield_ingest(req: ShieldIngest, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    result = classify(req.sender, req.subject, req.body); fp = fingerprint(req.subject, req.body)
    action_taken = 'archive' if result['classification'] == 'Spam' and not result['protected'] else 'leave-accessible'
    with SessionLocal() as db:
        ev = ShieldEvent(source_message_id=req.source_message_id, sender=req.sender, subject=req.subject, fingerprint=fp, classification=result['classification'], confidence=result['confidence'], protected=result['protected'], reasons_json=json.dumps(result['reasons']), action_taken=action_taken)
        db.add(ev); db.commit(); db.refresh(ev)
        return serialize(ev)


@router.post('/shield/test')
def shield_test(req: ShieldTestRequest, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    enforce_rate_limit(request, 'shield-test', 6, 300)
    samples = [
        ('legit', 'customer@example.com', 'Question about my order', 'Hi, I bought from Pitmark and had a size question about my order.'),
        ('review', 'hello@example.net', 'Quick question', 'Is this the owner? I wanted to talk briefly about the store.'),
        ('spam', 'growth@example.biz', 'Store growth question', 'Your store has potential. We can increase conversions and increase your sales with our SEO services and marketing agency.'),
        ('system', 'no-reply@shopify.com', 'Shopify security notification', 'Security notice for your Shopify account.'),
    ]
    created = []
    stamp = str(int(__import__('time').time() * 1000))
    with SessionLocal() as db:
        if req.clear_previous_tests:
            for ev in db.scalars(select(ShieldEvent).where(ShieldEvent.source_message_id.like('shield-test:%'))).all():
                db.delete(ev)
            db.commit()
        for kind, sender, subject, body in samples:
            result = classify(sender, subject, body)
            ev = ShieldEvent(
                source_message_id=f'shield-test:{stamp}:{kind}', sender=sender, subject=subject,
                fingerprint=fingerprint(subject, body), classification=result['classification'],
                confidence=result['confidence'], protected=result['protected'],
                reasons_json=json.dumps(result['reasons']),
                action_taken='archive' if result['classification'] == 'Spam' and not result['protected'] else 'leave-accessible',
            )
            db.add(ev); db.flush(); created.append(serialize(ev))
        db.commit()
    return {'ok': True, 'created': created, 'summary': {x['classification']: sum(1 for y in created if y['classification'] == x['classification']) for x in created}}


@router.get('/shield/events')
def shield_events(request: Request, classification: str | None = None, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        q = select(ShieldEvent).order_by(ShieldEvent.id.desc())
        if classification:
            q = q.where(ShieldEvent.classification == classification)
        return [serialize(x) for x in db.scalars(q).all()]


@router.post('/shield/events/{event_id}/action')
def shield_action(event_id: int, req: ShieldAction, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        ev = db.get(ShieldEvent, event_id)
        if not ev:
            raise HTTPException(404, 'Shield event not found')
        ev.action_taken = req.action; ev.acknowledged = req.acknowledged
        db.commit(); db.refresh(ev)
        return serialize(ev)


@router.post('/outreach')
def outreach_create(req: OutreachCreate, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        o = OutreachContact(**req.model_dump()); db.add(o); db.commit(); db.refresh(o)
        return serialize(o)


@router.get('/outreach')
def outreach_list(request: Request, stage: str | None = None, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        q = select(OutreachContact).order_by(OutreachContact.id.desc())
        if stage:
            q = q.where(OutreachContact.stage == stage)
        return [serialize(x) for x in db.scalars(q).all()]


@router.patch('/outreach/{contact_id}')
def outreach_update(contact_id: int, req: OutreachUpdate, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        o = db.get(OutreachContact, contact_id)
        if not o:
            raise HTTPException(404, 'Contact not found')
        for k, v in req.model_dump(exclude_none=True).items():
            setattr(o, k, v)
        o.updated_at = utcnow(); db.commit(); db.refresh(o)
        return serialize(o)


@router.post('/blog/generate')
def blog_generate(req: BlogGenerate, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    subject = req.subject.strip()
    if not subject:
        raise HTTPException(400, 'A subject is required.')
    notes = (req.notes or '').strip()
    prompt = f"""Write a Pitmark Racing Co. blog draft. Content type: {req.content_type}. Subject: {subject}.
Keep it community-first, grounded, and useful. Do not invent facts. If details are missing, write around what is known instead of making claims.
Return a finished article draft with a strong title on the first line, then a blank line, then the body.
Extra notes: {notes or 'none'}"""
    ai = compose_with_ai(platform='facebook', goal='authority', prompt=prompt, tone='editorial')
    lines = [x.strip() for x in ai.body.splitlines()]
    title = next((x.lstrip('# ').strip() for x in lines if x.strip()), subject)
    body_lines = lines[lines.index(next(x for x in lines if x.strip())) + 1:] if any(x.strip() for x in lines) else []
    body = '\n'.join(body_lines).strip() or ai.body.strip()
    return {'title': title[:240], 'body_html': body, 'content_type': req.content_type, 'provider': ai.provider, 'model': ai.model}


@router.post('/blog/drafts')
def blog_create(req: BlogCreate, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        b = BlogDraft(**req.model_dump(), status='draft'); db.add(b); db.commit(); db.refresh(b)
        return serialize(b)


@router.get('/blog/drafts')
def blog_list(request: Request, status: str | None = None, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        q = select(BlogDraft).order_by(BlogDraft.id.desc())
        if status:
            q = q.where(BlogDraft.status == status)
        return [serialize(x) for x in db.scalars(q).all()]


@router.post('/blog/drafts/{draft_id}/decision')
def blog_decide(draft_id: int, req: BlogDecision, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    if req.action not in {'approve', 'reject', 'schedule', 'archive'}:
        raise HTTPException(400, 'action must be approve, reject, schedule or archive')
    with SessionLocal() as db:
        b = db.get(BlogDraft, draft_id)
        if not b:
            raise HTTPException(404, 'Draft not found')
        if req.action == 'schedule':
            if not req.scheduled_for:
                raise HTTPException(400, 'scheduled_for is required')
            b.status = 'scheduled'; b.scheduled_for = req.scheduled_for
        elif req.action == 'approve':
            b.status = 'approved'
        elif req.action == 'reject':
            b.status = 'rejected'
        else:
            b.status = 'archived'
        b.updated_at = utcnow(); db.commit(); db.refresh(b)
        return serialize(b)

@router.get('/settings/connections')
def connection_readiness(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    return {
        'facebook': {'connected': False, 'ready': bool(settings.meta_app_id and settings.meta_app_secret), 'label': 'Meta OAuth'},
        'instagram': {'connected': False, 'ready': bool(settings.meta_app_id and settings.meta_app_secret), 'label': 'Meta OAuth'},
        'tiktok': {'connected': False, 'ready': bool(settings.tiktok_client_key and settings.tiktok_client_secret), 'label': 'TikTok OAuth'},
        'x': {'connected': False, 'ready': bool(settings.x_client_id and settings.x_client_secret), 'label': 'X OAuth'},
    }


@router.get('/autopilot/intelligence/status')
def intelligence_status(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key); return intelligence_status_data()

@router.get('/autopilot/opportunities')
def opportunities(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db: return [serialize(x) for x in db.scalars(select(AutopilotOpportunity).order_by(AutopilotOpportunity.id.desc()).limit(30)).all()]

@router.get('/autopilot/opportunity-engine')
def opportunity_engine(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    rows=evaluate_recent(30)
    return {'count':len(rows),'high_priority':sum(1 for x in rows if x['score']>=80),'review':sum(1 for x in rows if 65<=x['score']<80),'watching':sum(1 for x in rows if 50<=x['score']<65),'no_action':sum(1 for x in rows if x['score']<50),'opportunities':rows}

@router.post('/autopilot/intelligence/run')
def run_intelligence(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key); enforce_rate_limit(request,'autopilot-intelligence',4,300)
    try: return scan_now()
    except Exception as exc: raise HTTPException(502, f'Intelligence scan failed: {type(exc).__name__}')

# --- Racing Community / PRT-ready foundation (v0.12.2) ---
class CommunityEntityCreate(BaseModel):
    entity_type: str
    name: str
    community_lane: str = 'real'
    platform: str | None = None
    external_id: str | None = None
    region: str | None = None
    summary: str | None = None
    visibility: str = 'internal'
    source_url: str | None = None
    source_name: str | None = None

class CommunityRelationshipCreate(BaseModel):
    subject_id: int
    predicate: str
    object_id: int
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_url: str | None = None
    source_name: str | None = None

class ResearchPrepareRequest(BaseModel):
    entity_id: int | None = None
    opportunity_id: int | None = None
    research_type: str = 'entity_deep_dive'

class CampaignParticipantCreate(BaseModel):
    name: str
    campaign_year: str = '2026'
    community_lane: str = 'real'
    platform: str | None = None
    stage: str = 'interested'
    intake_status: str = 'sent'
    notes: str | None = None


class CampaignParticipantUpdate(BaseModel):
    stage: str | None = None
    intake_status: str | None = None
    verification_status: str | None = None
    media_permission: str | None = None
    guardian_status: str | None = None
    story_readiness: float | None = None
    notes: str | None = None


@router.get('/community/entities')
def community_entities(request: Request, q: str = '', entity_type: str | None = None, lane: str | None = None, limit: int = 50, x_admin_key: str | None = Header(default=None)):
    auth(request, x_admin_key)
    from services.racing_community import search_entities
    return {'items': search_entities(q, entity_type, lane, limit)}

@router.get('/community/entities/{entity_id}')
def community_entity(entity_id: int, request: Request, x_admin_key: str | None = Header(default=None)):
    auth(request, x_admin_key)
    from services.racing_community import entity_detail
    item = entity_detail(entity_id)
    if not item: raise HTTPException(404, 'Community entity not found')
    return item

@router.post('/community/entities')
def community_entity_create(payload: CommunityEntityCreate, request: Request, x_admin_key: str | None = Header(default=None)):
    auth(request, x_admin_key)
    from services.racing_community import CommunityEntity, serialize_entity, utcnow
    allowed_types = {'racer','person','team','track','league','series','event','organization','community'}
    allowed_lanes = {'real','sim','crossover'}
    if payload.entity_type not in allowed_types: raise HTTPException(400, 'Unsupported entity_type')
    if payload.community_lane not in allowed_lanes: raise HTTPException(400, 'community_lane must be real, sim, or crossover')
    with SessionLocal() as db:
        row = CommunityEntity(**payload.model_dump(), updated_at=utcnow())
        db.add(row); db.commit(); db.refresh(row)
        return serialize_entity(row)

@router.post('/community/relationships')
def community_relationship_create(payload: CommunityRelationshipCreate, request: Request, x_admin_key: str | None = Header(default=None)):
    auth(request, x_admin_key)
    from services.racing_community import CommunityEntity, CommunityRelationship
    with SessionLocal() as db:
        if not db.get(CommunityEntity, payload.subject_id) or not db.get(CommunityEntity, payload.object_id):
            raise HTTPException(400, 'Both community entities must exist')
        row = CommunityRelationship(**payload.model_dump())
        db.add(row); db.commit(); db.refresh(row)
        return {'id': row.id, 'subject_id': row.subject_id, 'predicate': row.predicate, 'object_id': row.object_id, 'confidence': row.confidence}

@router.post('/community/research/prepare')
def community_research_prepare(payload: ResearchPrepareRequest, request: Request, x_admin_key: str | None = Header(default=None)):
    auth(request, x_admin_key)
    from services.racing_community import CommunityEntity, ResearchJob
    from services.control_center import AutopilotOpportunity
    if not payload.entity_id and not payload.opportunity_id:
        raise HTTPException(400, 'entity_id or opportunity_id is required')
    with SessionLocal() as db:
        entity = db.get(CommunityEntity, payload.entity_id) if payload.entity_id else None
        opp = db.get(AutopilotOpportunity, payload.opportunity_id) if payload.opportunity_id else None
        if payload.entity_id and not entity: raise HTTPException(404, 'Community entity not found')
        if payload.opportunity_id and not opp: raise HTTPException(404, 'Opportunity not found')
        # Foundation deliberately queues a durable job. Live web research is connected in the next integration layer.
        seed = entity.name if entity else opp.headline
        row = ResearchJob(entity_id=payload.entity_id, opportunity_id=payload.opportunity_id,
                          research_type=payload.research_type, status='queued',
                          brief_json=json.dumps({'subject': seed, 'research_more_supported': True,
                                                 'required_outputs': ['verified facts','source ledger','strengths','weaknesses','PRT fit','Pitmark fit','recommended action','personalized outreach']}))
        db.add(row); db.commit(); db.refresh(row)
        return {'job_id': row.id, 'status': row.status, 'subject': seed, 'message': 'Research & Prepare queued. No outreach will be sent without approval.'}

@router.get('/community/research/{job_id}')
def community_research_job(job_id: int, request: Request, x_admin_key: str | None = Header(default=None)):
    auth(request, x_admin_key)
    from services.racing_community import ResearchJob, _json
    with SessionLocal() as db:
        row = db.get(ResearchJob, job_id)
        if not row: raise HTTPException(404, 'Research job not found')
        return {'id': row.id, 'entity_id': row.entity_id, 'opportunity_id': row.opportunity_id, 'research_type': row.research_type,
                'status': row.status, 'completeness': row.completeness, 'verification_score': row.verification_score,
                'brief': _json(row.brief_json, {}), 'facts_used': _json(row.facts_used_json, []),
                'facts_omitted': _json(row.facts_omitted_json, []), 'sources': _json(row.source_urls_json, []),
                'recommended_action': row.recommended_action, 'outreach_draft': row.outreach_draft}


@router.get('/campaigns/rookie-year')
def rookie_year_campaign(request: Request, year: str = '2026', x_admin_key: str | None = Header(default=None)):
    auth(request, x_admin_key)
    from services.racing_community import CampaignParticipant, CommunityEntity, ensure_rookie_year_campaign
    with SessionLocal() as db:
        campaign = ensure_rookie_year_campaign(db, year)
        rows = db.scalars(select(CampaignParticipant).where(CampaignParticipant.campaign_id == campaign.id).order_by(CampaignParticipant.updated_at.desc())).all()
        items=[]
        from services.racing_community import ResearchJob
        for r in rows:
            e=db.get(CommunityEntity,r.entity_id)
            job = db.scalars(select(ResearchJob).where(ResearchJob.entity_id == r.entity_id).order_by(ResearchJob.created_at.desc())).first()
            research = ({'id': job.id, 'status': job.status, 'completeness': job.completeness, 'verification_score': job.verification_score} if job else None)
            items.append({'id':r.id,'entity_id':r.entity_id,'name':e.name if e else 'Unknown','stage':r.stage,'intake_status':r.intake_status,'verification_status':r.verification_status,'media_permission':r.media_permission,'guardian_status':r.guardian_status,'story_readiness':r.story_readiness,'notes':r.notes,'research_job':research})
        return {'campaign':{'id':campaign.id,'name':campaign.name,'year':campaign.cohort,'status':campaign.status,'autonomy':campaign.autonomy,'objective':campaign.objective},'participants':items}

@router.post('/campaigns/rookie-year/participants')
def rookie_year_add(payload: CampaignParticipantCreate, request: Request, x_admin_key: str | None = Header(default=None)):
    auth(request, x_admin_key)
    from services.racing_community import CampaignParticipant, CommunityEntity, ensure_rookie_year_campaign, utcnow
    if not payload.name.strip(): raise HTTPException(400,'Driver name is required')
    with SessionLocal() as db:
        campaign=ensure_rookie_year_campaign(db,payload.campaign_year)
        entity=CommunityEntity(entity_type='racer',name=payload.name.strip(),community_lane=payload.community_lane,platform=payload.platform,visibility='internal',pitmark_tags_json=json.dumps(['rookie_year']))
        db.add(entity); db.flush()
        row=CampaignParticipant(campaign_id=campaign.id,entity_id=entity.id,stage=payload.stage,intake_status=payload.intake_status,notes=payload.notes,updated_at=utcnow())
        db.add(row); db.commit(); db.refresh(row)
        return {'id':row.id,'entity_id':entity.id,'name':entity.name,'stage':row.stage}

@router.post('/campaigns/rookie-year/participants/{participant_id}')
def rookie_year_update(participant_id: int, payload: CampaignParticipantUpdate, request: Request, x_admin_key: str | None = Header(default=None)):
    auth(request, x_admin_key)
    from services.racing_community import CampaignParticipant, utcnow
    with SessionLocal() as db:
        row=db.get(CampaignParticipant,participant_id)
        if not row: raise HTTPException(404,'Participant not found')
        for k,v in payload.model_dump(exclude_none=True).items(): setattr(row,k,v)
        row.updated_at=utcnow(); db.commit(); db.refresh(row)
        return {'id':row.id,'stage':row.stage,'intake_status':row.intake_status,'verification_status':row.verification_status,'media_permission':row.media_permission,'guardian_status':row.guardian_status,'story_readiness':row.story_readiness}
