from __future__ import annotations
import json, re
from sqlalchemy import select
from services.database import SessionLocal
from services.control_center import AutopilotOpportunity, OutreachContact

ROOKIE = ('rookie','first season','first year racing','first year behind the wheel','rookie of the year')
GRASS = ('grassroots','local','short track','dirt','speedway','sprint','late model','modified','kart','iracing','sim racing','league')
MAJOR = ('nascar','indycar','imsa','formula 1','f1','nhra','world of outlaws')
MILESTONE = ('first win','first victory','champion','championship','wins','victory','debut','moves to','moving to')
RISK = ('rumor','alleged','unconfirmed','tragic','death','fatal','lawsuit','arrest')

def _clamp(n): return max(0,min(100,int(n)))
def _terms(text, words): return [w for w in words if w in text]

def evaluate(op: AutopilotOpportunity, contacts: list[OutreachContact] | None=None) -> dict:
    text=' '.join(filter(None,[op.headline,op.reason,op.source_name])).lower()
    contacts=contacts or []
    rookie=_terms(text,ROOKIE); grass=_terms(text,GRASS); major=_terms(text,MAJOR); milestones=_terms(text,MILESTONE); risks=_terms(text,RISK)
    related=[]
    for c in contacts:
        needles=[c.name or '', c.organization or '']
        if any(n and len(n.strip())>=4 and n.lower() in text for n in needles): related.append(c)
    pitmark=_clamp(48 + 8*len(grass) + 12*len(rookie) + 8*len(milestones) + (18 if related else 0) - (8 if major and not grass else 0))
    relationship=_clamp(20 + (65 if related else 0))
    story=_clamp(45 + 12*len(rookie) + 10*len(milestones) + 5*len(grass))
    verification=72 if op.source_url else 38
    timeliness=75
    balance=78
    risk=_clamp(10 + 24*len(risks))
    total=_clamp(round(pitmark*.30 + relationship*.15 + story*.20 + verification*.15 + timeliness*.10 + balance*.10 - risk*.20))
    types=[]
    if rookie: types += ['rookie','relationship','content']
    else: types += ['content']
    if related: types += ['relationship']
    if grass: types += ['community']
    types=list(dict.fromkeys(types))
    strengths=[]; weaknesses=[]
    if rookie: strengths.append('Rookie/first-season language detected — strong Rookie Year lead.')
    if grass: strengths.append('Strong grassroots/community racing fit.')
    if related: strengths.append('Existing Pitmark relationship detected: '+', '.join((c.organization or c.name) for c in related[:3])+'.')
    if milestones: strengths.append('Meaningful racing milestone/story hook detected.')
    if not related: weaknesses.append('No existing Pitmark relationship detected yet.')
    if verification < 75: weaknesses.append('Needs stronger primary-source verification before factual publishing.')
    if risks: weaknesses.append('Sensitive/unverified language detected; human review required.')
    action='watch'
    if total>=75 and rookie: action='research_and_draft_outreach'
    elif total>=80: action='create_content_candidate'
    elif total>=65: action='review'
    elif total<50: action='no_action'
    pitch_angle=None
    if rookie:
        hook='their first-season racing journey'
        if grass: hook='their grassroots rookie-season story'
        pitch_angle=f'Invite them to Rookie Year around {hook}; personalize only with verified public facts from the source and any approved Pitmark relationship context.'
    return {'opportunity_id':op.id,'score':total,'types':types,'recommended_action':action,'scores':{'pitmark_relevance':pitmark,'relationship_relevance':relationship,'story_strength':story,'verification':verification,'timeliness':timeliness,'content_balance':balance,'risk':risk},'strengths':strengths,'weaknesses':weaknesses,'personalized_pitch_angle':pitch_angle,'source_url':op.source_url}

def evaluate_recent(limit=30):
    with SessionLocal() as db:
        contacts=list(db.scalars(select(OutreachContact)).all())
        ops=list(db.scalars(select(AutopilotOpportunity).order_by(AutopilotOpportunity.id.desc()).limit(limit)).all())
        return [evaluate(op,contacts) for op in ops]
