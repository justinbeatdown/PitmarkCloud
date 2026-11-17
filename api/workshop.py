from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from services.database import Base, SessionLocal
from services.control_access import access_from_request
from utils.security import enforce_rate_limit

router = APIRouter()
ROOT = Path(__file__).resolve().parents[1]

class WorkshopState(Base):
    __tablename__ = "pitmark_workshop_state"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class UpdateState(BaseModel):
    state: dict
    revision: int | None = None

def _user(request: Request):
    access = access_from_request(request)
    if not access or not access.active or access.role not in {"owner", "admin"}:
        raise HTTPException(401, "Workshop owner/admin login required")
    return access

def _safe_origin(request: Request):
    origin = request.headers.get("origin", "")
    if origin:
        p = urlparse(origin)
        if p.scheme != 'https' or p.netloc.lower() != request.headers.get("host", "").lower():
            raise HTTPException(403, "Cross-origin writes forbidden")

def _validate(payload: dict):
    if len(json.dumps(payload,ensure_ascii=False)) > 400000:
        raise HTTPException(413, "Workshop data too large")
    if any(not isinstance(payload.get(k, []),list) or len(payload.get(k, []))>2000 for k in ('jobs','inventory','press')):
        raise HTTPException(422, "Invalid workshop records")
    if not isinstance(payload.get('checks',{}),dict) or not isinstance(payload.get('notes',''),str) or len(payload.get('notes',''))>100000:
        raise HTTPException(422, "Invalid workshop notes")

@router.get('/workshop',response_class=HTMLResponse,include_in_schema=False)
def workshop_home(request: Request):
    access = access_from_request(request)
    if not access or not access.active or access.role not in ('owner','admin'):
        return HTMLResponse("""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#101115"><title>Pitmark Workshop Login</title><link rel="icon" href="/control-logo-badge.png"><style>body{font-family:system-ui;background:#111216;color:white;margin:0;min-height:100vh;display:grid;place-items:center}main{width:min(360px,90vw);padding:28px;border:1px solid #343840;border-radius:16px;background:#1b1e24}h1{font-size:25px}small{color:#b8bcc7}input,button{box-sizing:border-box;width:100%;padding:13px;margin-top:12px;border-radius:8px;font-size:16px}input{background:#292d35;color:white;border:1px solid #555}button{border:0;background:#ff5500;color:white;font-weight:800}#error{color:#ffaaaa}</style></head><body><main><h1>🏁 Pitmark Workshop</h1><p>Sign in with your Pitmark Control Center account.</p><form id="login"><input name="username" autocomplete="username" placeholder="Username" required><input name="password" type="password" autocomplete="current-password" placeholder="Password" required><button>Sign in</button><p id="error" role="alert"></p></form><small>Your production records remain private.</small></main><script>document.querySelector('#login').onsubmit=async e=>{e.preventDefault();const f=e.target,b=f.querySelector('button');b.disabled=true;try{const r=await fetch('/api/control/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({username:f.querySelector('[name=username]').value,password:f.querySelector('[name=password]').value})});if(!r.ok)throw Error(r.status===401?'Incorrect username or password':'Login temporarily unavailable');location.reload()}catch(err){document.querySelector('#error').textContent=err.message;b.disabled=false}}</script></body></html>""",headers={'Cache-Control':'no-store','X-Robots-Tag':'noindex'})
    filepath=ROOT/'sites'/'pitmark-workshop'/'cloud.html'
    if not filepath.is_file():
        raise HTTPException(503,'Workshop interface not deployed')
    return HTMLResponse(filepath.read_text(encoding='utf-8'),headers={'Cache-Control':'no-store','X-Robots-Tag':'noindex'})

@router.get('/api/workshop/state')
def get_workshop_state(request: Request):
    user=_user(request)
    with SessionLocal() as db:
        row=db.get(WorkshopState,user.id)
        if not row:
            return JSONResponse({'state':None,'revision':0,'updated_at':None},headers={'Cache-Control':'no-store'})
        return JSONResponse({'state':json.loads(row.data_json),'revision':row.revision,'updated_at':row.updated_at.isoformat()},headers={'Cache-Control':'no-store'})

@router.put('/api/workshop/state')
def put_workshop_state(payload: UpdateState,request: Request):
    user=_user(request)
    _safe_origin(request)
    enforce_rate_limit(request,'workshop-save',120,60)
    _validate(payload.state)
    with SessionLocal() as db:
        row=db.get(WorkshopState,user.id)
        if row:
            if payload.revision is None or payload.revision != row.revision:
                raise HTTPException(409,'Changed on another device; reload before overwriting')
            row.data_json=json.dumps(payload.state,ensure_ascii=False,separators=(',',':'))
            row.revision+=1
            row.updated_at=datetime.now(timezone.utc)
        else:
            if payload.revision not in (None,0):
                raise HTTPException(409,'Workspace reset; reload first')
            row=WorkshopState(user_id=user.id,data_json=json.dumps(payload.state,ensure_ascii=False,separators=(',',':')),revision=1)
            db.add(row)
        db.commit()
        return {'ok':True,'revision':row.revision,'updated_at':row.updated_at.isoformat()}

@router.get('/api/workshop/orders')
def workshop_orders(request: Request):
    _user(request)
    enforce_rate_limit(request,'workshop-orders',20,60)
    from services.shopify_service import graphql,configured
    if not configured():
        return {'connected':False,'orders':[],'message':'PitmarkCloud Shopify credentials not configured'}
    try:
        query='query WorkshopRecentOrders { orders(first: 25, sortKey: CREATED_AT, reverse: true) { nodes { id name createdAt displayFinancialStatus displayFulfillmentStatus lineItems(first: 20) { nodes { title quantity } } } } }'
        data=graphql(query)
        output=[]
        for item in ((data.get('orders') or {}).get('nodes') or []):
            output.append({'id':item.get('id'),'name':item.get('name'),'created_at':item.get('createdAt'),'payment':item.get('displayFinancialStatus'),'fulfillment':item.get('displayFulfillmentStatus'),'items':[{'title':x.get('title'),'quantity':x.get('quantity')} for x in ((item.get('lineItems') or {}).get('nodes') or [])]})
        return JSONResponse({'connected':True,'orders':output},headers={'Cache-Control':'no-store'})
    except Exception:
        return JSONResponse({'connected':False,'orders':[],'message':'Shopify connection unavailable; workshop data is safe'},headers={'Cache-Control':'no-store'})
