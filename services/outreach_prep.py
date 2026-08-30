from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlalchemy import select

from services.database import SessionLocal
from services.racing_community import CommunityEntity, ResearchJob, CampaignParticipant, OutreachPrep, _json


def utcnow():
    return datetime.now(timezone.utc)


def _participant_context(db, entity_id: int) -> dict:
    row = db.scalar(select(CampaignParticipant).where(CampaignParticipant.entity_id == entity_id).order_by(CampaignParticipant.updated_at.desc()))
    if not row:
        return {}
    return {
        'stage': row.stage,
        'intake_status': row.intake_status,
        'verification_status': row.verification_status,
        'media_permission': row.media_permission,
    }


def prepare_outreach(research_job_id: int) -> dict:
    with SessionLocal() as db:
        job = db.get(ResearchJob, research_job_id)
        if not job:
            raise ValueError('Research job not found')
        if job.status != 'complete':
            raise ValueError('Research must be complete before outreach can be prepared')
        if not job.entity_id:
            raise ValueError('Outreach Prep currently requires a Racing Community entity')
        entity = db.get(CommunityEntity, job.entity_id)
        if not entity:
            raise ValueError('Community entity not found')

        # Reuse a prepared package for the same completed research job instead of creating duplicates.
        existing = db.scalar(select(OutreachPrep).where(OutreachPrep.research_job_id == job.id).order_by(OutreachPrep.updated_at.desc()))
        if existing:
            return serialize_outreach(existing)

        brief = _json(job.brief_json, {})
        used = _json(job.facts_used_json, [])
        omitted = _json(job.facts_omitted_json, [])
        ctx = _participant_context(db, entity.id)

        if job.research_type == 'rookie_deep_dive':
            goal = 'Rookie Year eligibility / feature conversation'
            if ctx.get('intake_status') == 'received':
                why = f"{entity.name} is already in the Rookie Year intake workflow. The next message should acknowledge the intake and only request missing verification or story details."
                channel = 'Existing conversation channel'
                draft = (
                    f"Hey {entity.name.split()[0]}! Thanks for sending your Rookie Year info over. I’m going through everything now so we can build your feature accurately. "
                    "If I need to verify a racing detail or grab one more piece of the story, I’ll reach back out before anything gets published. 🏁"
                )
            elif ctx.get('intake_status') == 'sent':
                why = f"{entity.name} is already marked as having a Rookie Year intake sent. Avoid a duplicate invitation; use a light follow-up only if the existing conversation needs one."
                channel = 'Existing conversation channel'
                draft = (
                    f"Hey {entity.name.split()[0]}! Just checking in on the Rookie Year info I sent over. No rush — I just wanted to make sure it came through. "
                    "If you have any questions about the feature or what photos/info we’re looking for, just let me know. 🏁"
                )
            else:
                why = f"{entity.name} is a Rookie Year prospect, but rookie status is not yet verified. The safest first contact is an eligibility conversation, not a claim that they are a rookie."
                channel = 'Instagram DM or email after a contact method is confirmed'
                draft = (
                    f"Hey {entity.name.split()[0]}! I’m with Pitmark Racing Co. We’re putting together Rookie Year 2026, a series highlighting drivers working through their first season. "
                    "I wanted to reach out and see if this is your rookie season. If it is, we’d love to hear a little about your year and potentially feature your story. 🏁"
                )
        else:
            goal = 'Pitmark introduction / relationship conversation'
            why = f"Autopilot found enough context around {entity.name} to prepare a low-pressure Pitmark introduction, but nothing will be sent without approval."
            channel = 'DM or email after a contact method is confirmed'
            draft = (
                f"Hey! I’m with Pitmark Racing Co. I’ve been checking out what {entity.name} is doing in racing and wanted to introduce ourselves. "
                "We’re building racing tools, community features, and partnership projects around grassroots and sim racing. If you’re open to it, I’d love to learn a little more about what you’re working on and see if there’s a natural fit. 🏁"
            )

        # Only strong/corroborated facts are eligible for use. Everything else stays explicitly excluded.
        fact_lines = []
        for item in used:
            if isinstance(item, dict):
                fact_lines.append({
                    'claim': item.get('claim') or '',
                    'source': item.get('source') or 'Public source',
                    'url': item.get('url'),
                    'identity_score': item.get('identity_score', 0),
                })
        excluded = list(omitted)
        if not brief.get('verified_external_identity'):
            excluded.insert(0, {
                'claim': 'Unverified public identity details',
                'reason': 'Autopilot did not establish a corroborated external identity, so public-search details are not used in the message.'
            })

        prep = OutreachPrep(
            research_job_id=job.id,
            entity_id=entity.id,
            status='ready_for_approval',
            goal=goal,
            recommended_channel=channel,
            why_message=why,
            facts_used_json=json.dumps(fact_lines),
            facts_excluded_json=json.dumps(excluded[:12]),
            draft_message=draft,
            risk_notes_json=json.dumps([
                'No message has been sent.',
                'Do not use unverified identity details as facts.',
                'Human approval is required before external contact.'
            ]),
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(prep)
        db.commit()
        db.refresh(prep)
        return serialize_outreach(prep)


def serialize_outreach(row: OutreachPrep) -> dict:
    return {
        'id': row.id,
        'research_job_id': row.research_job_id,
        'entity_id': row.entity_id,
        'status': row.status,
        'goal': row.goal,
        'recommended_channel': row.recommended_channel,
        'why_message': row.why_message,
        'facts_used': _json(row.facts_used_json, []),
        'facts_excluded': _json(row.facts_excluded_json, []),
        'draft_message': row.draft_message,
        'risk_notes': _json(row.risk_notes_json, []),
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }
