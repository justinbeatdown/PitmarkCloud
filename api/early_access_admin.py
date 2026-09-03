from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse

from services.control_auth import require_control_user

router = APIRouter()


@router.get('/control/early-access', response_class=HTMLResponse, include_in_schema=False)
def early_access_admin(
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    require_control_user(request, x_pitmark_admin_key)
    return HTMLResponse(ADMIN_HTML, headers={'Cache-Control': 'no-store'})


ADMIN_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PRT Early Access</title>
<style>
:root{color-scheme:dark;--bg:#090b0c;--panel:#111518;--panel2:#0d1012;--line:#343a3f;--text:#f5f6f7;--muted:#9da4aa;--orange:#ff5500;--orange2:#ff6a1a;--green:#63df8a;--red:#ff6969}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Arial,Helvetica,sans-serif}.wrap{max-width:1180px;margin:0 auto;padding:32px 24px 60px}.top{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:24px}.eyebrow{color:var(--orange);font-size:12px;font-weight:900;letter-spacing:.16em}.title{font-size:34px;font-weight:950;font-style:italic;margin:7px 0 4px}.muted{color:var(--muted);font-size:13px;line-height:1.5}.back{color:#fff;text-decoration:none;border:1px solid var(--line);padding:11px 15px;font-weight:800}.grid{display:grid;grid-template-columns:390px 1fr;gap:20px}.card{background:var(--panel);border:1px solid var(--line);padding:22px}.card h2{margin:0 0 18px;font-size:18px}.field{margin:0 0 14px}.field label{display:block;color:var(--muted);font-size:11px;font-weight:900;letter-spacing:.08em;margin-bottom:6px}.field input,.field textarea{width:100%;background:var(--panel2);color:#fff;border:1px solid var(--line);padding:11px 12px;font:inherit}.field textarea{min-height:90px;resize:vertical}.field input:focus,.field textarea:focus{outline:1px solid var(--orange);border-color:var(--orange)}button{border:0;background:var(--orange);color:#fff;padding:12px 16px;font-weight:900;cursor:pointer}button:hover{background:var(--orange2)}button.secondary{background:transparent;border:1px solid var(--line)}button.danger{background:transparent;border:1px solid #753333;color:#ff8c8c;padding:8px 10px}.result{display:none;margin-top:18px;padding:16px;background:#0b0f0c;border:1px solid #285f38}.code{font:900 19px Consolas,monospace;color:var(--green);letter-spacing:.04em;word-break:break-all}.copyrow{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}.message{white-space:pre-wrap;background:#080a0b;border:1px solid var(--line);padding:12px;margin-top:12px;color:#dfe3e5;font-size:12px;line-height:1.45;max-height:260px;overflow:auto}.toolbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:12px}.tablewrap{overflow:auto;border:1px solid var(--line)}table{width:100%;border-collapse:collapse;min-width:760px}th,td{text-align:left;padding:11px 10px;border-bottom:1px solid #272c30;font-size:12px}th{color:var(--muted);font-size:10px;letter-spacing:.08em;background:#0d1012}td strong{font-size:13px}.status{font-weight:900;text-transform:uppercase;font-size:10px}.status.redeemed{color:var(--green)}.status.revoked,.status.expired{color:var(--red)}.hint{font:700 11px Consolas,monospace;color:#c7ccd0}.empty{padding:28px;color:var(--muted);text-align:center}.flash{min-height:18px;color:var(--muted);font-size:12px;margin-top:10px}@media(max-width:850px){.grid{grid-template-columns:1fr}.top{align-items:flex-start;flex-direction:column}.wrap{padding:22px 14px 48px}}
</style>
</head>
<body><main class="wrap">
<div class="top"><div><div class="eyebrow">PITMARK RACING TOOLS</div><div class="title">EARLY ACCESS ADMIN</div><div class="muted">Issue one-time tester codes. Gmail stays in Gmail; this page only manages PRT access.</div></div><a class="back" href="/control">← CONTROL CENTER</a></div>
<div class="grid">
<section class="card"><h2>CREATE TESTER INVITE</h2>
<form id="inviteForm">
<div class="field"><label>APPLICANT NAME</label><input id="name" maxlength="180" required></div>
<div class="field"><label>EMAIL</label><input id="email" type="email" maxlength="254" required></div>
<div class="field"><label>DISCORD (OPTIONAL)</label><input id="discord" maxlength="120"></div>
<div class="field"><label>CODE VALID FOR (DAYS)</label><input id="days" type="number" min="1" max="90" value="14" required></div>
<div class="field"><label>NOTES (OPTIONAL)</label><textarea id="notes" maxlength="1000"></textarea></div>
<button type="submit" id="createBtn">GENERATE EARLY ACCESS CODE</button>
<div class="flash" id="flash"></div>
</form>
<div class="result" id="result"><div class="muted">CODE — shown in full only now</div><div class="code" id="code"></div><div class="copyrow"><button type="button" id="copyCode">COPY CODE</button><button type="button" class="secondary" id="copyMessage">COPY ACCEPTANCE MESSAGE</button></div><div class="message" id="message"></div></div>
</section>
<section class="card"><div class="toolbar"><div><h2 style="margin:0">TESTER INVITES</h2><div class="muted">Issued, redeemed and revoked codes.</div></div><button type="button" class="secondary" id="refresh">REFRESH</button></div><div class="tablewrap" id="tablewrap"><div class="empty">Loading…</div></div></section>
</div></main>
<script>
const $=id=>document.getElementById(id); let lastMessage='';
async function api(url,opts={}){const r=await fetch(url,{credentials:'same-origin',headers:{'Content-Type':'application/json',...(opts.headers||{})},...opts});const data=await r.json().catch(()=>({}));if(!r.ok)throw new Error(data.detail||('Request failed: '+r.status));return data}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function load(){try{const d=await api('/api/entitlements/admin/early-access');const rows=d.items||[];if(!rows.length){$('tablewrap').innerHTML='<div class="empty">No tester invites yet.</div>';return}let h='<table><thead><tr><th>TESTER</th><th>CODE</th><th>STATUS</th><th>DEVICE</th><th>CREATED</th><th></th></tr></thead><tbody>';for(const x of rows){h+=`<tr><td><strong>${esc(x.applicant_name)}</strong><br><span class="muted">${esc(x.email)}</span></td><td><span class="hint">${esc(x.code_hint)}</span></td><td><span class="status ${esc(x.status)}">${esc(x.status)}</span><br><span class="muted">${esc(x.tester_status)}</span></td><td><span class="hint">${esc(x.bound_device_id||'—')}</span></td><td>${esc((x.created_at||'').replace('T',' ').slice(0,16))}</td><td>${x.status!=='revoked'?`<button type="button" class="danger" data-revoke="${x.id}">REVOKE</button>`:''}</td></tr>`}h+='</tbody></table>';$('tablewrap').innerHTML=h;document.querySelectorAll('[data-revoke]').forEach(b=>b.addEventListener('click',async()=>{if(!confirm('Revoke this Early Access invite?'))return;try{await api('/api/entitlements/admin/early-access/'+b.dataset.revoke+'/revoke',{method:'POST'});await load()}catch(e){alert(e.message)}}))}catch(e){$('tablewrap').innerHTML='<div class="empty">'+esc(e.message)+'</div>'}}
$('inviteForm').addEventListener('submit',async e=>{e.preventDefault();$('createBtn').disabled=true;$('flash').textContent='Generating…';try{const d=await api('/api/entitlements/admin/early-access',{method:'POST',body:JSON.stringify({applicant_name:$('name').value,email:$('email').value,discord:$('discord').value,expires_days:Number($('days').value),notes:$('notes').value})});$('code').textContent=d.code;const first=($('name').value.trim().split(/\s+/)[0]||'there');lastMessage=`Hey ${first},\n\nYou’re in — your Pitmark Racing Tools Early Access application has been accepted.\n\nEARLY ACCESS CODE: ${d.code}\n\nInstall/open PRT v0.16.48 or newer, go to Settings → PRT Early Access, paste the code, and choose ACTIVATE EARLY ACCESS. The code is personal and binds to your PRT device when activated.\n\nEarly Access builds may contain bugs or unfinished features. Please use PRT during normal racing, keep private builds/codes private, and send us honest feedback when something breaks or could be better.\n\nThanks for helping build PRT.\n\nLeave your mark.\nPitmark Racing Co.`;$('message').textContent=lastMessage;$('result').style.display='block';$('flash').textContent='Invite created.';$('inviteForm').reset();$('days').value='14';await load()}catch(e){$('flash').textContent=e.message}finally{$('createBtn').disabled=false}})
async function copy(text,button){try{await navigator.clipboard.writeText(text);const old=button.textContent;button.textContent='COPIED';setTimeout(()=>button.textContent=old,1200)}catch{prompt('Copy:',text)}}
$('copyCode').addEventListener('click',()=>copy($('code').textContent,$('copyCode')));$('copyMessage').addEventListener('click',()=>copy(lastMessage,$('copyMessage')));$('refresh').addEventListener('click',load);load();
</script></body></html>'''
