from __future__ import annotations
import json
from datetime import datetime, timezone
from sqlalchemy import select
from services.database import SessionLocal
from services.control_center import AutopilotPlan, SocialPost, AutopilotOpportunity, OpportunitySourceMeta, OutreachContact, BlogDraft
from services.racing_community import CampaignParticipant
from services.autonomy_control import mode_for


def utcnow(): return datetime.now(timezone.utc)

def _task(kind,title,why,priority='normal',source_id=None):
    return {'kind':kind,'title':title,'why':why,'priority':priority,'source_id':source_id}

def build_plan(save=True):
    tasks=[]; notes=[]
    with SessionLocal() as db:
        pending=db.scalars(select(SocialPost).where(SocialPost.status=='pending').order_by(SocialPost.id.desc())).all()
        if pending:
            tasks.append(_task('approval',f'Review {len(pending)} queued post'+('s' if len(pending)!=1 else ''),'Existing approval work comes before generating more content.','high'))
        fresh=[]
        for op in db.scalars(select(AutopilotOpportunity).where(AutopilotOpportunity.status=='new').order_by(AutopilotOpportunity.id.desc()).limit(30)).all():
            meta=db.scalar(select(OpportunitySourceMeta).where(OpportunitySourceMeta.opportunity_id==op.id))
            if meta and meta.age_hours is not None and meta.age_hours <= 96:
                fresh.append((op,meta))
        if fresh and len(pending)<3:
            op,meta=fresh[0]
            tasks.append(_task('content_candidate',op.headline,f'Fresh racing signal ({meta.age_hours}h old). Prepare only if it adds something useful to Pitmark.','normal',op.id))
        rookie_ready=db.scalars(select(CampaignParticipant).where(CampaignParticipant.intake_status=='received').order_by(CampaignParticipant.updated_at.desc()).limit(1)).first()
        if rookie_ready:
            tasks.append(_task('campaign','Review returned Rookie Year intake','Campaign work outranks generic filler content.','high',rookie_ready.id))
        contacts=len(db.scalars(select(OutreachContact)).all())
        drafts=len(db.scalars(select(BlogDraft).where(BlogDraft.status=='draft')).all())
        if contacts: notes.append(f'{contacts} relationship records are available for partner/community planning.')
        if drafts: notes.append(f'{drafts} blog draft(s) already exist; avoid creating duplicate work.')
        if not tasks:
            tasks.append(_task('hold','No new content required','Pitmark has no higher-value work that justifies manufacturing a post.','normal'))
        if len(pending)>=3:
            notes.append('Content generation suppressed while the approval queue already has 3 or more posts.')
        modes={'intelligence':mode_for('intelligence_discovery','auto'),'social_publish':mode_for('social_publish','approval'),'outreach_send':mode_for('outreach_send','approval')}
        summary='Prioritize existing work.' if pending else ('Pitmark has useful work to prepare.' if tasks[0]['kind']!='hold' else 'Pitmark can stay quiet.')
        payload={'generated_at':utcnow().isoformat(),'summary':summary,'tasks':tasks[:5],'notes':notes,'autonomy':modes,'principle':'Do useful work, not busy work. Doing nothing is a valid plan.'}
        if save:
            row=AutopilotPlan(status='current',summary=summary,plan_json=json.dumps(payload),created_at=utcnow())
            db.add(row); db.commit(); db.refresh(row); payload['id']=row.id
        return payload

def latest_plan():
    with SessionLocal() as db:
        row=db.scalars(select(AutopilotPlan).order_by(AutopilotPlan.id.desc())).first()
        if not row: return build_plan(save=True)
        try: data=json.loads(row.plan_json)
        except Exception: data={'summary':row.summary,'tasks':[],'notes':[]}
        data['id']=row.id; return data
