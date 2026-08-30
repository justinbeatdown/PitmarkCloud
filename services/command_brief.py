from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select

from services.database import SessionLocal, database_status
from services.control_center import SocialPost, ShieldEvent, OutreachContact, BlogDraft, AutopilotOpportunity, OpportunitySourceMeta
from services.racing_community import ResearchJob, OutreachPrep, CampaignParticipant, CommunityEntity
from utils.config import settings
from utils.security import security_summary


def utcnow():
    return datetime.now(timezone.utc)


def _item(priority: str, module: str, title: str, detail: str, *, action_view: str | None = None, entity_id: int | None = None, record_id: int | None = None) -> dict:
    return {
        'priority': priority,
        'module': module,
        'title': title,
        'detail': detail,
        'action_view': action_view,
        'entity_id': entity_id,
        'record_id': record_id,
    }


def build_command_brief() -> dict:
    critical: list[dict] = []
    action: list[dict] = []
    opportunities: list[dict] = []
    info: list[dict] = []

    with SessionLocal() as db:
        # Synthetic Shield harness events intentionally never reach the production brief.
        shield_reviews = db.scalars(
            select(ShieldEvent).where(
                ShieldEvent.classification == 'Review',
                ShieldEvent.acknowledged == False,  # noqa: E712
                ~ShieldEvent.source_message_id.like('shield-test:%'),
            ).order_by(ShieldEvent.id.desc()).limit(20)
        ).all()
        for ev in shield_reviews:
            target = critical if ev.protected else action
            target.append(_item(
                'critical' if ev.protected else 'action',
                'Shield',
                'Protected message needs review' if ev.protected else 'Message needs review',
                f"{ev.subject or '(no subject)'} · {ev.sender}",
                action_view='shield', record_id=ev.id,
            ))

        pending_posts = db.scalars(select(SocialPost).where(SocialPost.status == 'pending').order_by(SocialPost.id.desc()).limit(8)).all()
        if pending_posts:
            action.append(_item('action', 'Autopilot', f'{len(pending_posts)} post approval' + ('s' if len(pending_posts) != 1 else '') + ' waiting', 'Review queued social content before anything is published.', action_view='autopilot'))

        outreach_preps = db.scalars(select(OutreachPrep).where(OutreachPrep.status == 'ready_for_approval').order_by(OutreachPrep.updated_at.desc()).limit(8)).all()
        for prep in outreach_preps:
            entity = db.get(CommunityEntity, prep.entity_id)
            action.append(_item('action', 'Autopilot', 'Outreach ready for approval', f"{entity.name if entity else 'Racing contact'} · {prep.goal}", action_view='campaigns', entity_id=prep.entity_id, record_id=prep.id))

        failed_jobs = db.scalars(select(ResearchJob).where(ResearchJob.status == 'failed').order_by(ResearchJob.updated_at.desc()).limit(5)).all()
        for job in failed_jobs:
            entity = db.get(CommunityEntity, job.entity_id) if job.entity_id else None
            action.append(_item('action', 'Autopilot', 'Research job needs attention', f"{entity.name if entity else 'Research job'} · Job #{job.id} failed.", action_view='campaigns', entity_id=job.entity_id, record_id=job.id))

        received = db.scalars(select(CampaignParticipant).where(CampaignParticipant.intake_status == 'received').order_by(CampaignParticipant.updated_at.desc()).limit(8)).all()
        for participant in received:
            if participant.stage in {'published', 'alumni'}:
                continue
            entity = db.get(CommunityEntity, participant.entity_id)
            opportunities.append(_item('opportunity', 'Campaigns', 'Rookie intake ready to review', f"{entity.name if entity else 'Racer'} has returned intake information.", action_view='campaigns', entity_id=participant.entity_id, record_id=participant.id))

        candidate_ops = db.scalars(select(AutopilotOpportunity).where(AutopilotOpportunity.status == 'new').order_by(AutopilotOpportunity.id.desc()).limit(20)).all()
        for op in candidate_ops:
            meta = db.scalar(select(OpportunitySourceMeta).where(OpportunitySourceMeta.opportunity_id == op.id))
            if not meta or meta.age_hours is None or meta.age_hours > 96:
                continue
            opportunities.append(_item('opportunity', 'Autopilot', op.headline, (op.reason or 'New racing signal detected by Autopilot Intelligence.') + f' · {meta.age_hours}h old', action_view='autopilot', record_id=op.id))
            if len(opportunities) >= 3:
                break

        draft_count = len(db.scalars(select(BlogDraft).where(BlogDraft.status == 'draft')).all())
        contact_count = len(db.scalars(select(OutreachContact)).all())
        active_research = len(db.scalars(select(ResearchJob).where(ResearchJob.status.in_(['queued','researching','verifying']))).all())

    sec = security_summary(
        environment=settings.environment,
        signing_secret=settings.pitmark_signing_secret,
        admin_key=settings.pitmark_admin_key,
        cors_origins=settings.cors_origin_list,
    )
    dbs = database_status()
    if not sec.get('ready'):
        critical.append(_item('critical', 'Shield', 'Security posture needs attention', 'One or more production security controls are not hardened. Open Shield for the posture summary.', action_view='shield'))
    else:
        info.append(_item('info', 'Shield', 'Core security controls healthy', 'Signed sessions, security headers, rate limiting, request limits and protected secrets are active.', action_view='shield'))
    if not dbs.get('durable_for_render'):
        critical.append(_item('critical', 'Pitmark Cloud', 'Persistent database is not production-ready', dbs.get('warning') or 'Configure a durable PostgreSQL database.', action_view='settings'))

    # Mailbox integration is deliberately informational until a provider is connected.
    info.append(_item('info', 'Shield', 'Communications protection is staged', 'Shield classification is active, but the production mailbox connector is not connected yet.', action_view='shield'))
    if active_research:
        info.append(_item('info', 'Autopilot', f'{active_research} research job' + ('s' if active_research != 1 else '') + ' running', 'Autopilot Research Agent is working in the background.', action_view='campaigns'))
    if draft_count:
        info.append(_item('info', 'Blog', f'{draft_count} blog draft' + ('s' if draft_count != 1 else '') + ' saved', 'Drafts remain internal until approved and publishing is connected.', action_view='blog'))
    info.append(_item('info', 'Outreach', f'{contact_count} relationship record' + ('s' if contact_count != 1 else '') + ' tracked', 'Pitmark relationship history remains available to Campaigns and Autopilot.', action_view='outreach'))

    needs_attention = len(critical) + len(action)
    status = 'attention' if needs_attention else ('opportunities' if opportunities else 'caught_up')
    headline = (
        f'{needs_attention} thing' + ('s' if needs_attention != 1 else '') + ' need you' if needs_attention
        else (f'{len(opportunities)} opportunit' + ('ies' if len(opportunities) != 1 else 'y') + ' available' if opportunities else 'Pitmark is caught up')
    )
    return {
        'generated_at': utcnow().isoformat(),
        'status': status,
        'headline': headline,
        'counts': {'critical': len(critical), 'action': len(action), 'opportunities': len(opportunities), 'info': len(info)},
        'sections': {'critical': critical, 'action': action, 'opportunities': opportunities, 'info': info},
        'caught_up': needs_attention == 0,
    }
