from __future__ import annotations
import json, secrets
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from services.database import SessionLocal
from services.control_center import SocialPost, ShieldEvent, OutreachContact, BlogDraft, classify, fingerprint, compose_fallback, serialize, utcnow
from utils.config import settings

router=APIRouter()

def admin(x_pitmark_admin_key:str|None):
    expected=(settings.pitmark_admin_key or '').strip()
    if not expected or not x_pitmark_admin_key or not secrets.compare_digest(expected,x_pitmark_admin_key):
        raise HTTPException(401,'Invalid Pitmark admin key.')

class ComposeRequest(BaseModel):
    platform:str='facebook'; prompt:str=Field(default='Generate a useful Pitmark social post',min_length=1,max_length=3000)
    topic:str|None=None; goal:str='community'; tone:str='natural'; use_context:bool=True
class SavePost(BaseModel):
    platform:str='facebook'; title:str|None=None; body:str=Field(min_length=1,max_length=5000); content_type:str='community'; source:str='manual_composer'; risk:str='low'; scheduled_for:str|None=None
class Decision(BaseModel): action:str; note:str|None=None
class ShieldIngest(BaseModel): source_message_id:str; sender:str; subject:str=''; body:str=''
class ShieldAction(BaseModel): action:str; acknowledged:bool=False
class OutreachCreate(BaseModel): name:str; organization:str|None=None; contact_type:str='track'; email:str|None=None; stage:str='prospect'; supporter_status:str='unverified'; next_follow_up:str|None=None; notes:str|None=None
class OutreachUpdate(BaseModel): stage:str|None=None; supporter_status:str|None=None; next_follow_up:str|None=None; notes:str|None=None
class BlogCreate(BaseModel): title:str; body_html:str; content_type:str='article'; seo_title:str|None=None; seo_description:str|None=None; featured_image_url:str|None=None; scheduled_for:str|None=None
class BlogDecision(BaseModel): action:str

@router.get('/status')
def status(x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    with SessionLocal() as db:
        return {"service":"Pitmark Control Center","autopilot":True,"shield":True,"social_pending":len(db.scalars(select(SocialPost).where(SocialPost.status=='pending')).all()),"shield_review":len(db.scalars(select(ShieldEvent).where(ShieldEvent.classification=='Review')).all()),"outreach_contacts":len(db.scalars(select(OutreachContact)).all()),"blog_drafts":len(db.scalars(select(BlogDraft).where(BlogDraft.status=='draft')).all())}

@router.post('/autopilot/composer/generate')
def compose(req:ComposeRequest,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    result=compose_fallback(req.platform,req.goal,req.topic or req.prompt)
    result['tone']=req.tone; result['context_used']=req.use_context
    return result

@router.post('/autopilot/posts')
def save_post(req:SavePost,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    with SessionLocal() as db:
        p=SocialPost(platform=req.platform,title=req.title,body=req.body,content_type=req.content_type,source=req.source,risk=req.risk,status='pending',scheduled_for=req.scheduled_for)
        db.add(p); db.commit(); db.refresh(p); return serialize(p)

@router.get('/autopilot/posts')
def posts(status:str|None=None,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    with SessionLocal() as db:
        q=select(SocialPost).order_by(SocialPost.id.desc())
        if status: q=q.where(SocialPost.status==status)
        return [serialize(x) for x in db.scalars(q).all()]

@router.post('/autopilot/posts/{post_id}/decision')
def decide(post_id:int,req:Decision,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    if req.action not in {'approve','reject'}: raise HTTPException(400,'action must be approve or reject')
    with SessionLocal() as db:
        p=db.get(SocialPost,post_id)
        if not p: raise HTTPException(404,'Post not found')
        p.status='approved' if req.action=='approve' else 'rejected'; p.updated_at=utcnow(); db.commit(); db.refresh(p); return serialize(p)

@router.post('/shield/ingest')
def shield_ingest(req:ShieldIngest,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key); result=classify(req.sender,req.subject,req.body); fp=fingerprint(req.subject,req.body)
    action='archive' if result['classification']=='Spam' and not result['protected'] else 'leave-accessible'
    with SessionLocal() as db:
        ev=ShieldEvent(source_message_id=req.source_message_id,sender=req.sender,subject=req.subject,fingerprint=fp,classification=result['classification'],confidence=result['confidence'],protected=result['protected'],reasons_json=json.dumps(result['reasons']),action_taken=action)
        db.add(ev); db.commit(); db.refresh(ev); return serialize(ev)

@router.get('/shield/events')
def shield_events(classification:str|None=None,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    with SessionLocal() as db:
        q=select(ShieldEvent).order_by(ShieldEvent.id.desc())
        if classification: q=q.where(ShieldEvent.classification==classification)
        return [serialize(x) for x in db.scalars(q).all()]

@router.post('/shield/events/{event_id}/action')
def shield_action(event_id:int,req:ShieldAction,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    with SessionLocal() as db:
        ev=db.get(ShieldEvent,event_id)
        if not ev: raise HTTPException(404,'Shield event not found')
        ev.action_taken=req.action; ev.acknowledged=req.acknowledged; db.commit(); db.refresh(ev); return serialize(ev)

@router.post('/outreach')
def outreach_create(req:OutreachCreate,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    with SessionLocal() as db:
        o=OutreachContact(**req.model_dump()); db.add(o); db.commit(); db.refresh(o); return serialize(o)

@router.get('/outreach')
def outreach_list(stage:str|None=None,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    with SessionLocal() as db:
        q=select(OutreachContact).order_by(OutreachContact.id.desc())
        if stage: q=q.where(OutreachContact.stage==stage)
        return [serialize(x) for x in db.scalars(q).all()]

@router.patch('/outreach/{contact_id}')
def outreach_update(contact_id:int,req:OutreachUpdate,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    with SessionLocal() as db:
        o=db.get(OutreachContact,contact_id)
        if not o: raise HTTPException(404,'Contact not found')
        for k,v in req.model_dump(exclude_none=True).items(): setattr(o,k,v)
        o.updated_at=utcnow(); db.commit(); db.refresh(o); return serialize(o)

@router.post('/blog/drafts')
def blog_create(req:BlogCreate,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    with SessionLocal() as db:
        b=BlogDraft(**req.model_dump(),status='draft'); db.add(b); db.commit(); db.refresh(b); return serialize(b)

@router.get('/blog/drafts')
def blog_list(status:str|None=None,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    with SessionLocal() as db:
        q=select(BlogDraft).order_by(BlogDraft.id.desc())
        if status: q=q.where(BlogDraft.status==status)
        return [serialize(x) for x in db.scalars(q).all()]

@router.post('/blog/drafts/{draft_id}/decision')
def blog_decide(draft_id:int,req:BlogDecision,x_pitmark_admin_key:str|None=Header(default=None)):
    admin(x_pitmark_admin_key)
    if req.action not in {'approve','reject'}: raise HTTPException(400,'action must be approve or reject')
    with SessionLocal() as db:
        b=db.get(BlogDraft,draft_id)
        if not b: raise HTTPException(404,'Draft not found')
        b.status='approved' if req.action=='approve' else 'rejected'; b.updated_at=utcnow(); db.commit(); db.refresh(b); return serialize(b)
