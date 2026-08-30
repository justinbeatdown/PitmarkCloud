from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, Float, Boolean, select, or_
from sqlalchemy.orm import Mapped, mapped_column
from services.database import Base, SessionLocal


def utcnow():
    return datetime.now(timezone.utc)


class CommunityEntity(Base):
    __tablename__ = "racing_community_entities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)  # racer/team/track/league/series/event/org
    name: Mapped[str] = mapped_column(String(240), index=True)
    slug: Mapped[str | None] = mapped_column(String(260), nullable=True, index=True)
    community_lane: Mapped[str] = mapped_column(String(30), default="real", index=True)  # real/sim/crossover
    platform: Mapped[str | None] = mapped_column(String(60), nullable=True)  # iracing/etc
    external_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    region: Mapped[str | None] = mapped_column(String(180), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_data_json: Mapped[str] = mapped_column(Text, default="{}")
    pitmark_tags_json: Mapped[str] = mapped_column(Text, default="[]")
    visibility: Mapped[str] = mapped_column(String(30), default="internal")  # internal/community/public
    claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    identity_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommunityRelationship(Base):
    __tablename__ = "racing_community_relationships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(Integer, index=True)
    predicate: Mapped[str] = mapped_column(String(80), index=True)
    object_id: Mapped[int] = mapped_column(Integer, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="active")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommunityClaim(Base):
    __tablename__ = "racing_community_claims"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    claimant_key: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    verification_method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchJob(Base):
    __tablename__ = "autopilot_research_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    opportunity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    research_type: Mapped[str] = mapped_column(String(60), default="entity_deep_dive")
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    completeness: Mapped[float] = mapped_column(Float, default=0.0)
    verification_score: Mapped[float] = mapped_column(Float, default=0.0)
    brief_json: Mapped[str] = mapped_column(Text, default="{}")
    facts_used_json: Mapped[str] = mapped_column(Text, default="[]")
    facts_omitted_json: Mapped[str] = mapped_column(Text, default="[]")
    source_urls_json: Mapped[str] = mapped_column(Text, default="[]")
    recommended_action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outreach_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def _json(value, fallback):
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def serialize_entity(row: CommunityEntity) -> dict:
    return {
        "id": row.id, "entity_type": row.entity_type, "name": row.name, "slug": row.slug,
        "community_lane": row.community_lane, "platform": row.platform, "external_id": row.external_id,
        "region": row.region, "summary": row.summary, "public_data": _json(row.public_data_json, {}),
        "pitmark_tags": _json(row.pitmark_tags_json, []), "visibility": row.visibility, "claimed": row.claimed,
        "verification_status": row.verification_status, "identity_confidence": row.identity_confidence,
        "source_url": row.source_url, "source_name": row.source_name,
        "first_observed_at": row.first_observed_at.isoformat() if row.first_observed_at else None,
        "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None,
    }


def search_entities(q: str = "", entity_type: str | None = None, lane: str | None = None, limit: int = 50):
    with SessionLocal() as db:
        stmt = select(CommunityEntity)
        if q.strip():
            term = f"%{q.strip()}%"
            stmt = stmt.where(or_(CommunityEntity.name.ilike(term), CommunityEntity.summary.ilike(term)))
        if entity_type: stmt = stmt.where(CommunityEntity.entity_type == entity_type)
        if lane: stmt = stmt.where(CommunityEntity.community_lane == lane)
        rows = db.scalars(stmt.order_by(CommunityEntity.updated_at.desc()).limit(min(limit, 100))).all()
        return [serialize_entity(x) for x in rows]


def entity_detail(entity_id: int):
    with SessionLocal() as db:
        row = db.get(CommunityEntity, entity_id)
        if not row: return None
        relationships = db.scalars(select(CommunityRelationship).where(or_(CommunityRelationship.subject_id == entity_id, CommunityRelationship.object_id == entity_id)).limit(200)).all()
        result = serialize_entity(row)
        result["relationships"] = [{
            "id": r.id, "subject_id": r.subject_id, "predicate": r.predicate, "object_id": r.object_id,
            "confidence": r.confidence, "status": r.status, "source_url": r.source_url,
            "last_verified_at": r.last_verified_at.isoformat() if r.last_verified_at else None,
        } for r in relationships]
        return result

class OutreachPrep(Base):
    __tablename__ = "autopilot_outreach_preps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    research_job_id: Mapped[int] = mapped_column(Integer, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(40), default="ready_for_approval", index=True)
    goal: Mapped[str] = mapped_column(String(180))
    recommended_channel: Mapped[str] = mapped_column(String(180))
    why_message: Mapped[str] = mapped_column(Text)
    facts_used_json: Mapped[str] = mapped_column(Text, default="[]")
    facts_excluded_json: Mapped[str] = mapped_column(Text, default="[]")
    draft_message: Mapped[str] = mapped_column(Text)
    risk_notes_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Campaign(Base):
    __tablename__ = "pitmark_campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    campaign_type: Mapped[str] = mapped_column(String(60), default="custom", index=True)
    cohort: Mapped[str | None] = mapped_column(String(80), nullable=True)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    autonomy: Mapped[str] = mapped_column(String(30), default="approval")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CampaignParticipant(Base):
    __tablename__ = "pitmark_campaign_participants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    stage: Mapped[str] = mapped_column(String(50), default="prospect", index=True)
    intake_status: Mapped[str] = mapped_column(String(30), default="not_sent")
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    media_permission: Mapped[str] = mapped_column(String(30), default="pending")
    guardian_status: Mapped[str] = mapped_column(String(30), default="not_required")
    story_readiness: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def ensure_rookie_year_campaign(db, year: str = "2026"):
    row = db.scalar(select(Campaign).where(Campaign.campaign_type == "rookie_year", Campaign.cohort == year))
    if not row:
        row = Campaign(name=f"Rookie Year {year}", campaign_type="rookie_year", cohort=year,
                       objective="Celebrate first-season racers and build long-term racing relationships.", status="active", autonomy="approval")
        db.add(row); db.commit(); db.refresh(row)
    return row
