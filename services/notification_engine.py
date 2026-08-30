from __future__ import annotations
import hashlib
from sqlalchemy import select
from services.database import SessionLocal
from services.control_center import EcosystemNotification, NotificationPreference, utcnow
from services.command_brief import build_command_brief

PUSH_NOW = {'critical', 'action'}

def _key(item: dict) -> str:
    raw = '|'.join(str(item.get(k) or '') for k in ('priority','module','title','record_id','entity_id'))
    return hashlib.sha256(raw.encode()).hexdigest()[:40]

def sync_from_ecosystem() -> dict:
    brief = build_command_brief(); created = 0
    # Opportunities are retained in Command Brief but do not interrupt by default.
    candidates = brief['sections']['critical'] + brief['sections']['action']
    with SessionLocal() as db:
        for item in candidates:
            key=_key(item)
            if db.scalar(select(EcosystemNotification).where(EcosystemNotification.dedupe_key==key)):
                continue
            reason = ('Immediate security/operations attention is required.' if item['priority']=='critical'
                      else 'A human decision or approval is required before Pitmark proceeds.')
            db.add(EcosystemNotification(dedupe_key=key, priority=item['priority'], module=item['module'], title=item['title'], detail=item['detail'], action_view=item.get('action_view'), reason=reason))
            created += 1
        db.commit()
        unread=len(db.scalars(select(EcosystemNotification).where(EcosystemNotification.status=='unread')).all())
    return {'created':created,'unread':unread,'brief_status':brief['status']}

def list_notifications(limit:int=40):
    with SessionLocal() as db:
        rows=db.scalars(select(EcosystemNotification).order_by(EcosystemNotification.created_at.desc()).limit(limit)).all()
        return [{'id':r.id,'priority':r.priority,'module':r.module,'title':r.title,'detail':r.detail,'action_view':r.action_view,'reason':r.reason,'status':r.status,'delivery':r.delivery,'created_at':r.created_at.isoformat() if r.created_at else None} for r in rows]

def mark_read(notification_id:int):
    with SessionLocal() as db:
        row=db.get(EcosystemNotification,notification_id)
        if not row: return False
        row.status='read'; row.updated_at=utcnow(); db.commit(); return True

def preferences(user_key='admin'):
    with SessionLocal() as db:
        row=db.scalar(select(NotificationPreference).where(NotificationPreference.user_key==user_key))
        if not row:
            row=NotificationPreference(user_key=user_key); db.add(row); db.commit(); db.refresh(row)
        return {'quiet_hours_enabled':row.quiet_hours_enabled,'quiet_start':row.quiet_start,'quiet_end':row.quiet_end,'opportunity_push':row.opportunity_push}
