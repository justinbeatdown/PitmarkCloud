from __future__ import annotations
from sqlalchemy import select
from services.database import SessionLocal
from services.control_center import AutonomyPolicy, utcnow

DEFAULTS = [
    ('intelligence_discovery','auto','Find and score racing opportunities.','standard'),
    ('research_agent','auto','Research public/authorized sources and prepare verified briefs.','standard'),
    ('outreach_prepare','auto','Prepare outreach drafts without sending them.','standard'),
    ('outreach_send','approval','Send first-contact or relationship outreach.','external'),
    ('social_publish','approval','Publish social content to connected platforms.','external'),
    ('blog_publish','approval','Publish blog content to connected platforms.','external'),
    ('shield_monitoring','auto','Monitor ecosystem security and communications.','security'),
    ('shield_response','approval','Apply non-destructive security response actions.','security'),
    ('money_legal_security_override','human_only','Money, contracts, refunds, legal/tax, security overrides, permission overrides.','red_zone'),
]
ALLOWED={'off','approval','auto','human_only'}

def ensure_defaults():
    with SessionLocal() as db:
        existing={r.capability for r in db.scalars(select(AutonomyPolicy)).all()}
        for cap,mode,desc,safety in DEFAULTS:
            if cap not in existing:
                db.add(AutonomyPolicy(capability=cap,mode=mode,description=desc,safety_class=safety))
        db.commit()

def list_policies():
    ensure_defaults()
    with SessionLocal() as db:
        rows=db.scalars(select(AutonomyPolicy).order_by(AutonomyPolicy.id)).all()
        return [{'capability':r.capability,'mode':r.mode,'description':r.description,'safety_class':r.safety_class,'updated_at':r.updated_at.isoformat() if r.updated_at else None} for r in rows]

def set_policy(capability:str, mode:str):
    ensure_defaults()
    if mode not in ALLOWED: raise ValueError('Invalid autonomy mode')
    with SessionLocal() as db:
        r=db.scalar(select(AutonomyPolicy).where(AutonomyPolicy.capability==capability))
        if not r: raise KeyError(capability)
        if r.safety_class=='red_zone' and mode!='human_only':
            raise PermissionError('Red-zone capabilities are permanently HUMAN ONLY')
        r.mode=mode; r.updated_at=utcnow(); db.commit()
        return {'capability':r.capability,'mode':r.mode,'description':r.description,'safety_class':r.safety_class}

def mode_for(capability:str, fallback='approval'):
    ensure_defaults()
    with SessionLocal() as db:
        r=db.scalar(select(AutonomyPolicy).where(AutonomyPolicy.capability==capability))
        return r.mode if r else fallback


RANK = {'off':0,'approval':1,'auto':2,'human_only':-1}

def effective_mode(capability:str, uncertainty:float=0.0, fallback='approval'):
    """Return policy after safety downgrade. Uncertainty can only reduce autonomy."""
    mode=mode_for(capability,fallback)
    if mode in {'off','human_only'}: return mode
    try: u=max(0.0,min(1.0,float(uncertainty)))
    except Exception: u=0.0
    if mode=='auto' and u>=0.35: return 'approval'
    return mode

def enforce(capability:str, *, uncertainty:float=0.0, allow_approval:bool=True):
    mode=effective_mode(capability,uncertainty)
    if mode=='off': raise PermissionError(f'{capability} is OFF in Autonomy Control Center')
    if mode=='human_only': raise PermissionError(f'{capability} is HUMAN ONLY')
    if mode=='approval' and not allow_approval: raise PermissionError(f'{capability} requires human approval')
    return mode
