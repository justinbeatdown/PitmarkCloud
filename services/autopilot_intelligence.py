import asyncio, hashlib, html, logging, re
from urllib.parse import quote_plus
import httpx
from sqlalchemy import select
from services.database import SessionLocal
from services.control_center import AutopilotOpportunity, AutopilotRun, SocialPost
from services.autopilot_ai import compose_with_ai
from utils.config import settings
log=logging.getLogger('pitmark.autopilot.intelligence')
FEED='https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en'
TERMS=('racing','race','motorsport','speedway','nascar','indycar','imsa','sprint car','late model','modified','sim racing','iracing','dirt','short track')
GRASS=('grassroots','local','short track','dirt','speedway','sprint','late model','modified','sim racing','iracing','league')
def tag(x,t):
 m=re.search(fr'<{t}[^>]*>(.*?)</{t}>',x,re.I|re.S); return html.unescape(re.sub('<[^>]+>','',m.group(1))).strip() if m else ''
def scan_now():
 run=AutopilotRun();
 with SessionLocal() as db: db.add(run); db.commit(); db.refresh(run); rid=run.id
 found=queued=0
 try:
  with httpx.Client(timeout=20,follow_redirects=True,headers={'User-Agent':'PitmarkAutopilot/0.11'}) as c: xml=c.get(FEED.format(quote_plus(settings.autopilot_scan_query))).text
  with SessionLocal() as db:
   for raw in re.findall(r'<item>(.*?)</item>',xml,re.I|re.S)[:25]:
    title,url=tag(raw,'title'),tag(raw,'link'); text=(title+' '+tag(raw,'description')).lower()
    if not title or not url or not any(x in text for x in TERMS): continue
    fp=hashlib.sha256((title+'|'+url).encode()).hexdigest()
    if db.scalar(select(AutopilotOpportunity).where(AutopilotOpportunity.fingerprint==fp)): continue
    hits=sum(x in text for x in GRASS); rel='high' if hits>=2 else ('medium' if hits else 'review'); reason='strong grassroots/community fit' if hits>=2 else ('relevant racing/community topic' if hits else 'motorsports topic; verify relevance')
    op=AutopilotOpportunity(headline=title,source_name='Google News',source_url=url,relevance=rel,reason=reason,fingerprint=fp); db.add(op); db.flush(); found+=1
    if rel in ('high','medium') and queued<3:
     try:
      ai=compose_with_ai(platform='facebook',goal='community',prompt=f'Create a Pitmark Racing Co. community-first post inspired by this current racing headline: {title}. Do not invent facts or imply Pitmark involvement. Make it useful even without the article.',tone='pitmark')
      db.add(SocialPost(platform='facebook',body=ai.body,content_type='community',source=f'intelligence:{op.id}',risk='low',status='pending')); op.status='drafted'; queued+=1
     except Exception as e: log.warning('AI candidate failed: %s',e)
   db.commit(); rr=db.get(AutopilotRun,rid); rr.status='completed'; rr.found_count=found; rr.queued_count=queued; rr.note='public racing-news scan'; db.commit()
  return {'ok':True,'found':found,'queued':queued}
 except Exception as e:
  with SessionLocal() as db: rr=db.get(AutopilotRun,rid); rr.status='failed'; rr.note=str(e)[:400]; db.commit()
  raise
def status():
 with SessionLocal() as db:
  r=db.scalar(select(AutopilotRun).order_by(AutopilotRun.id.desc()).limit(1)); return {'enabled':settings.autopilot_intelligence_enabled,'interval_hours':settings.autopilot_scan_hours,'last_run':None if not r else {'status':r.status,'found':r.found_count,'queued':r.queued_count,'created_at':r.created_at.isoformat()}}
async def scheduler_loop():
 await asyncio.sleep(30)
 while True:
  if settings.autopilot_intelligence_enabled:
   try: await asyncio.to_thread(scan_now)
   except Exception: log.exception('Autopilot scan failed')
  await asyncio.sleep(max(1,settings.autopilot_scan_hours)*3600)
