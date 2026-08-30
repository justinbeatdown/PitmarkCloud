from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from sqlalchemy import String, Text, Float, Integer, DateTime, Boolean, select
from sqlalchemy.orm import Mapped, mapped_column
from services.database import Base, SessionLocal


def utcnow(): return datetime.now(timezone.utc)

class SocialPost(Base):
    __tablename__ = "autopilot_social_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str | None] = mapped_column(String(180), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(50), default="community")
    source: Mapped[str] = mapped_column(String(50), default="manual")
    risk: Mapped[str] = mapped_column(String(20), default="low")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class AutopilotOpportunity(Base):
    __tablename__ = "autopilot_opportunities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    headline: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance: Mapped[str] = mapped_column(String(20), default="review", index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="new", index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class AutopilotRun(Base):
    __tablename__ = "autopilot_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(30), default="started")
    found_count: Mapped[int] = mapped_column(Integer, default=0)
    queued_count: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class ShieldEvent(Base):
    __tablename__ = "shield_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_message_id: Mapped[str] = mapped_column(String(255), index=True)
    sender: Mapped[str] = mapped_column(String(320), index=True)
    subject: Mapped[str] = mapped_column(Text, default="")
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    classification: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    protected: Mapped[bool] = mapped_column(Boolean, default=False)
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    action_taken: Mapped[str] = mapped_column(String(80), default="none")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class SecurityAuditEvent(Base):
    __tablename__ = "shield_security_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="info", index=True)
    actor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="control_center")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class OutreachContact(Base):
    __tablename__ = "marketing_outreach_contacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    organization: Mapped[str | None] = mapped_column(String(240), nullable=True)
    contact_type: Mapped[str] = mapped_column(String(50), default="track")
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    stage: Mapped[str] = mapped_column(String(50), default="prospect", index=True)
    supporter_status: Mapped[str] = mapped_column(String(50), default="unverified")
    next_follow_up: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class BlogDraft(Base):
    __tablename__ = "autopilot_blog_drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(240))
    body_html: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(60), default="article")
    seo_title: Mapped[str | None] = mapped_column(String(240), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    featured_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    scheduled_for: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

PROTECTED = {"order","payment","refund","chargeback","security","password","domain","dns","tax","legal","invoice","customer service","fraud","shopify","tiktok","google","printify"}
SPAM = ["your store has potential","increase your sales","increase traffic","increase conversions","speak with the owner","seo services","marketing agency","right strategy","grow your sales","improve the store"]
BAIT = ["is this the owner","can we talk briefly","is anyone there","nice store","is this inbox active","who runs the store"]
SYSTEM_DOMAINS = ["shopify.com","tiktok.com","google.com","printify.com"]


def fingerprint(subject:str, body:str)->str:
    text=(subject+' '+body).lower()
    text=re.sub(r'https?://\S+','<url>',text)
    text=re.sub(r'\b\d+\b','<n>',text)
    text=re.sub(r'\s+',' ',text).strip()
    return hashlib.sha256(text.encode()).hexdigest()

def classify(sender:str, subject:str, body:str)->dict:
    text=(subject+' '+body).lower(); sender_l=sender.lower()
    protected=any(x in text for x in PROTECTED)
    if any(d in sender_l for d in SYSTEM_DOMAINS):
        return {"classification":"System","confidence":0.98,"protected":True,"reasons":["trusted-operational-sender"]}
    spam_hits=[x for x in SPAM if x in text]; bait_hits=[x for x in BAIT if x in text]
    score=min(1.0, .28*len(spam_hits)+.12*len(bait_hits))
    legit_terms=["my order","tracking","size question","return request","exchange","bought from pitmark","purchase from pitmark"]
    if any(x in text for x in legit_terms) and not spam_hits:
        return {"classification":"Legit","confidence":0.90,"protected":True,"reasons":["customer-intent"]}
    if protected:
        return {"classification":"Review","confidence":0.90,"protected":True,"reasons":["protected-topic"]+spam_hits+bait_hits}
    if score>=.70:
        return {"classification":"Spam","confidence":round(min(.99,.72+score/4),2),"protected":False,"reasons":["solicitation-pattern"]+spam_hits+bait_hits}
    if score>0:
        return {"classification":"Review","confidence":round(.55+score/3,2),"protected":False,"reasons":["suspicious-pattern"]+spam_hits+bait_hits}
    return {"classification":"Review","confidence":0.40,"protected":False,"reasons":["insufficient-evidence"]}

FALLBACKS={
 "community":["Unlimited budget. One race car. What are you building? 🏁","Roll call: what's your home track? Drop the track + state below. 🏁"],
 "education":["Racing term, plain English: loose means the rear wants to rotate more; tight means the front resists turning. What term should Pitmark break down next?"],
 "entertainment":["POV: you said racing was going to be your cheap hobby. 💸🏁"],
 "authority":["A racing brand should feel like it belongs at the track—not in a boardroom. Cars, garages, people, and race culture. Leave Your Mark."],
 "product":["Would you actually wear this to the track? Be ruthless. Rate the design 1–10. 🏁"],
 "partner":["Racing grows when the community grows together. Pitmark is always looking for leagues, tracks, teams, and creators who want to build something useful together."],
}

def compose_fallback(platform:str, goal:str, topic:str|None=None)->dict:
    body=FALLBACKS.get(goal,FALLBACKS['community'])[0]
    if topic: body=f"{topic.strip().rstrip('.')} — {body}"
    visual=None
    if platform=='tiktok': visual="Faceless text-over-racing-image, carousel, or simple motion graphic with the hook on frame 1."
    return {"platform":platform,"goal":goal,"body":body,"visual_suggestion":visual,"provider":"pitmark-fallback","warnings":[]}

def serialize(obj):
    d={c.name:getattr(obj,c.name) for c in obj.__table__.columns}
    for k,v in list(d.items()):
        if isinstance(v,datetime): d[k]=v.isoformat()
    if 'reasons_json' in d:
        try: d['reasons']=json.loads(d.pop('reasons_json'))
        except Exception: pass
    return d

class EcosystemNotification(Base):
    __tablename__ = "pitmark_notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    priority: Mapped[str] = mapped_column(String(20), default="info", index=True)
    module: Mapped[str] = mapped_column(String(60), default="Pitmark", index=True)
    title: Mapped[str] = mapped_column(String(240))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_view: Mapped[str | None] = mapped_column(String(60), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="unread", index=True)
    delivery: Mapped[str] = mapped_column(String(40), default="in_app")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class NotificationPreference(Base):
    __tablename__ = "pitmark_notification_preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_key: Mapped[str] = mapped_column(String(120), unique=True, index=True, default="admin")
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_start: Mapped[str] = mapped_column(String(5), default="21:00")
    quiet_end: Mapped[str] = mapped_column(String(5), default="08:00")
    opportunity_push: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class OpportunitySourceMeta(Base):
    __tablename__ = "autopilot_opportunity_source_meta"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    age_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
