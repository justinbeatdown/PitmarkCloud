import asyncio, hashlib, html, logging, re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse
import httpx
from sqlalchemy import select
from services.database import SessionLocal
from services.control_center import AutopilotOpportunity, AutopilotRun, SocialPost, OpportunitySourceMeta
from services.autopilot_ai import compose_with_ai
from utils.config import settings
log=logging.getLogger('pitmark.autopilot.intelligence')
FEED='https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en'
TERMS=('racing','race','motorsport','speedway','nascar','indycar','imsa','sprint car','late model','modified','sim racing','iracing','dirt','short track','kart','league')
COMMUNITY=('grassroots','local','short track','dirt','speedway','sprint','late model','modified','kart','sim racing','iracing','league','rookie','first season','track','club')
MAJOR=('nascar.com','formula 1','f1','indycar','cup series','motogp')
LOW_SIGNAL=('farm and dairy','drag bike news')

def tag(x,t):
 m=re.search(fr'<{t}[^>]*>(.*?)</{t}>',x,re.I|re.S); return html.unescape(re.sub('<[^>]+>','',m.group(1))).strip() if m else ''

def _story_key(title:str)->str:
 s=title.lower(); s=re.sub(r'\s+-\s+[^-]{2,80}$','',s); s=re.sub(r'[^a-z0-9 ]+',' ',s); s=re.sub(r'\s+',' ',s).strip(); return hashlib.sha256(s.encode()).hexdigest()

def _quality(title:str, description:str)->tuple[int,str]:
 text=(title+' '+description).lower(); community=sum(x in text for x in COMMUNITY); major=sum(x in text for x in MAJOR); low=sum(x in text for x in LOW_SIGNAL)
 score=community*18 - major*12 - low*25
 if 'rookie' in text or 'first season' in text: score+=30
 if 'iracing' in text or 'sim racing' in text or 'league' in text: score+=24
 if any(x in text for x in ('local','grassroots','short track','dirt','speedway')): score+=18
 reason='strong Pitmark community fit' if score>=45 else ('possible community fit; verify relevance' if score>=20 else 'broad motorsports signal; low Pitmark fit')
 return score,reason

def scan_now():
 run=AutopilotRun()
 with SessionLocal() as db: db.add(run); db.commit(); db.refresh(run); rid=run.id
 found=queued=filtered=duplicates=0
 try:
  queries=[settings.autopilot_scan_query,'rookie racer OR first season racing OR local speedway OR short track racing','iRacing league OR sim racing league OR grassroots motorsports']
  raws=[]
  with httpx.Client(timeout=20,follow_redirects=True,headers={'User-Agent':'PitmarkAutopilot/0.12.8'}) as c:
   for q in queries:
    try: raws.extend(re.findall(r'<item>(.*?)</item>',c.get(FEED.format(quote_plus(q))).text,re.I|re.S)[:18])
    except Exception as e: log.warning('feed query failed: %s',e)
  seen_story=set()
  with SessionLocal() as db:
   for raw in raws:
    title,url,desc=tag(raw,'title'),tag(raw,'link'),tag(raw,'description'); pub=tag(raw,'pubDate'); text=(title+' '+desc).lower()
    published=None; age_hours=None
    if pub:
     try:
      published=parsedate_to_datetime(pub)
      if published.tzinfo is None: published=published.replace(tzinfo=timezone.utc)
      age_hours=max(0,int((datetime.now(timezone.utc)-published.astimezone(timezone.utc)).total_seconds()//3600))
     except Exception: pass
    # Current opportunity feed: seven-day hard ceiling. Older material belongs to Research Agent background context.
    if age_hours is not None and age_hours > 168: filtered+=1; continue
    if not title or not url or not any(x in text for x in TERMS): continue
    story=_story_key(title)
    if story in seen_story: duplicates+=1; continue
    seen_story.add(story)
    fp=hashlib.sha256((story+'|'+url).encode()).hexdigest()
    if db.scalar(select(AutopilotOpportunity).where(AutopilotOpportunity.fingerprint==fp)): continue
    # Also suppress near-identical headlines already persisted from earlier scans.
    recent=list(db.scalars(select(AutopilotOpportunity).order_by(AutopilotOpportunity.id.desc()).limit(80)).all())
    if any(_story_key(x.headline)==story for x in recent): duplicates+=1; continue
    score,reason=_quality(title,desc)
    if age_hours is None:
     score-=15; reason += '; publication date unverified'
    elif age_hours<=72:
     score+=18; reason += f'; fresh ({age_hours}h old)'
    else:
     score-=8; reason += f'; recent ({age_hours//24}d old)'
    if score<20: filtered+=1; continue
    rel='high' if score>=45 else 'medium'
    op=AutopilotOpportunity(headline=title,source_name='Google News',source_url=url,relevance=rel,reason=reason,fingerprint=fp); db.add(op); db.flush();
    freshness='fresh' if age_hours is not None and age_hours<=72 else ('recent' if age_hours is not None else 'unknown')
    db.add(OpportunitySourceMeta(opportunity_id=op.id,published_at=published,age_hours=age_hours,freshness=freshness)); found+=1
    # Approval queue is intentionally stricter than discovery.
    if score>=45 and queued<3:
     try:
      ai=compose_with_ai(platform='facebook',goal='community',prompt=f'Create a Pitmark Racing Co. community-first post inspired by this current racing headline: {title}. Do not invent facts or imply Pitmark involvement. Focus on grassroots racers, leagues, tracks, rookie journeys, or racing community value.',tone='pitmark')
      db.add(SocialPost(platform='facebook',body=ai.body,content_type='community',source=f'intelligence:{op.id}',risk='low',status='pending')); op.status='drafted'; queued+=1
     except Exception as e: log.warning('AI candidate failed: %s',e)
   db.commit(); rr=db.get(AutopilotRun,rid); rr.status='completed'; rr.found_count=found; rr.queued_count=queued; rr.note=f'Pitmark Intelligence V2: filtered={filtered}; story_duplicates={duplicates}; queries={len(queries)}'; db.commit()
  return {'ok':True,'found':found,'queued':queued,'filtered':filtered,'duplicates':duplicates}
 except Exception as e:
  with SessionLocal() as db: rr=db.get(AutopilotRun,rid); rr.status='failed'; rr.note=str(e)[:400]; db.commit()
  raise

def status():
 with SessionLocal() as db:
  r=db.scalar(select(AutopilotRun).order_by(AutopilotRun.id.desc()).limit(1)); return {'enabled':settings.autopilot_intelligence_enabled,'interval_hours':settings.autopilot_scan_hours,'version':'v2.1-freshness','last_run':None if not r else {'status':r.status,'found':r.found_count,'queued':r.queued_count,'note':r.note,'created_at':r.created_at.isoformat()}}
async def scheduler_loop():
 await asyncio.sleep(30)
 while True:
  if settings.autopilot_intelligence_enabled:
   try: await asyncio.to_thread(scan_now)
   except Exception: log.exception('Autopilot scan failed')
  await asyncio.sleep(max(1,settings.autopilot_scan_hours)*3600)
