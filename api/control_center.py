from __future__ import annotations

import hmac
import json
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from services.database import SessionLocal
from services.control_center import SocialPost, ShieldEvent, OutreachContact, BlogDraft, classify, fingerprint, compose_fallback, serialize, utcnow
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
    if req.action not in {'approve', 'reject'}:
        raise HTTPException(400, 'action must be approve or reject')
    with SessionLocal() as db:
        b = db.get(BlogDraft, draft_id)
        if not b:
            raise HTTPException(404, 'Draft not found')
        b.status = 'approved' if req.action == 'approve' else 'rejected'; b.updated_at = utcnow(); db.commit(); db.refresh(b)
        return serialize(b)
