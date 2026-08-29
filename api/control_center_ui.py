from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pitmark Control Center</title>
<style>
:root{--bg:#080909;--panel:#111313;--panel2:#171919;--line:#3b3f3f;--orange:#ff5500;--orange2:#bd3d00;--text:#f4f2ed;--muted:#9b9d9d;--good:#7fe38c;--bad:#ff6a6a;--shadow:0 14px 40px rgba(0,0,0,.35)}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:radial-gradient(circle at 70% -10%,rgba(255,85,0,.12),transparent 30%),linear-gradient(180deg,#090a0a,#050606 70%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}body:before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.16;background-image:linear-gradient(115deg,transparent 0 47%,rgba(255,255,255,.025) 48%,transparent 49%),repeating-linear-gradient(0deg,transparent 0 12px,rgba(255,255,255,.012) 13px)}
button,input,select,textarea{font:inherit}.shell{display:grid;grid-template-columns:245px 1fr;min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;border-right:1px solid #242626;background:linear-gradient(180deg,#0b0c0c,#0a0b0b 60%,#101010);padding:26px 14px 20px}.brand{padding:8px 14px 24px;border-bottom:1px solid #242626;margin-bottom:18px}.brand-main{font-weight:1000;font-style:italic;letter-spacing:-2px;font-size:34px;line-height:.9}.brand-sub{font-size:15px;font-weight:900;font-style:italic;color:var(--orange);letter-spacing:2px;margin-top:7px}.flag{display:inline-block;margin-top:9px;color:#fff;letter-spacing:-2px}.nav{display:grid;gap:8px}.nav a{display:flex;gap:12px;align-items:center;color:#c8caca;text-decoration:none;padding:13px 14px;border:1px solid transparent;border-radius:5px;font-weight:800;text-transform:uppercase}.nav a.active{background:linear-gradient(180deg,#9e3300,#5c1e00);border-color:#d34800;color:#fff}.nav a:hover{border-color:#3a3d3d;background:#131515}.nav .ico{width:28px;text-align:center;font-size:20px}.nav small{display:block;color:#8d8f8f;text-transform:none;font-weight:500;margin-top:3px}.side-bottom{position:absolute;bottom:22px;left:28px;right:28px;color:#989a9a}.motto{font-size:25px;font-weight:1000;font-style:italic;color:#fff;transform:rotate(-4deg);margin-bottom:20px}.motto:after{content:"";display:block;width:145px;height:4px;background:var(--orange);margin-top:5px;transform:skewX(-25deg)}
.main{min-width:0}.hero{min-height:155px;border-bottom:1px solid #313434;padding:32px 30px 22px;background:linear-gradient(90deg,rgba(7,8,8,.98),rgba(16,12,9,.86)),radial-gradient(circle at 70% 60%,rgba(255,85,0,.18),transparent 26%)}.topbar{display:flex;justify-content:space-between;gap:24px;align-items:flex-start}.title{font-size:44px;font-weight:1000;font-style:italic;letter-spacing:-1.8px;line-height:1}.title span{color:var(--orange)}.subtitle{margin-top:12px;color:#aaa;font-weight:800;font-style:italic;letter-spacing:1.5px;text-transform:uppercase}.connect{display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end}.connect label{font-weight:900;text-transform:uppercase;color:#d2d2d2}.input,.select,.textarea{background:#0b0d0d;border:1px solid #474b4b;color:#fff;padding:11px 13px;border-radius:4px;outline:none}.input:focus,.select:focus,.textarea:focus{border-color:var(--orange);box-shadow:0 0 0 2px rgba(255,85,0,.12)}.connect .input{width:230px}.btn{background:linear-gradient(180deg,#ff650f,#d84400);color:#fff;border:1px solid #ff6c18;padding:11px 17px;border-radius:4px;text-transform:uppercase;font-weight:1000;cursor:pointer;box-shadow:var(--shadow)}.btn:hover{filter:brightness(1.08)}.btn.secondary{background:#111414;border-color:#777;color:#eee;box-shadow:none}.status-dot{width:9px;height:9px;border-radius:50%;background:#8c8e8e;display:inline-block}.status-dot.good{background:var(--good);box-shadow:0 0 10px rgba(127,227,140,.5)}.status-dot.bad{background:var(--bad)}#connectionText{font-weight:800;color:#a9aaaa;text-transform:uppercase;font-size:13px}.content{padding:20px 30px 42px;max-width:1500px;margin:auto}.panel{position:relative;overflow:hidden;background:linear-gradient(135deg,rgba(20,22,22,.96),rgba(8,9,9,.98));border:1px solid #545858;border-left:2px solid var(--orange);margin-bottom:14px;padding:18px 20px;box-shadow:var(--shadow)}.panel:after{content:"P";position:absolute;right:28px;top:-18px;font-size:180px;font-weight:1000;font-style:italic;color:rgba(255,255,255,.025);pointer-events:none}.panel-head{display:flex;align-items:center;gap:14px;margin-bottom:14px}.panel-icon{display:grid;place-items:center;width:62px;height:62px;border:1px solid var(--orange);color:var(--orange);font-size:30px;background:#0c0d0d;flex:0 0 auto}.panel h2{margin:0;font-size:27px;font-style:italic;text-transform:uppercase;letter-spacing:-.5px}.panel h2:after{content:"";display:block;width:180px;height:4px;background:var(--orange);margin-top:5px;transform:skewX(-30deg)}.panel p{color:#c3c4c4;max-width:780px}.fields{display:grid;grid-template-columns:170px 170px minmax(260px,1fr) auto;gap:12px;align-items:start;margin-left:76px}.fields.three{grid-template-columns:1.1fr 1.1fr 1.1fr auto auto}.fields.blog{grid-template-columns:1fr 2fr 180px auto auto}.textarea{resize:vertical;min-height:44px}.output{margin:14px 0 0 76px;white-space:pre-wrap;background:#080a0a;border:1px solid #303333;border-left:3px solid #5e6262;padding:14px;min-height:54px;color:#e9e9e9;display:none}.output.show{display:block}.approval{margin:12px 0 0 76px}.meta{display:flex;gap:18px;flex-wrap:wrap;margin-top:8px;color:#909393;font-size:12px;text-transform:uppercase}.footer{text-align:center;color:#6e7070;padding:10px 0 0;text-transform:uppercase;letter-spacing:1px;font-size:12px}.flash{animation:flash .45s ease}@keyframes flash{0%{box-shadow:0 0 0 0 rgba(255,85,0,.45)}100%{box-shadow:0 0 0 12px rgba(255,85,0,0)}}
@media(max-width:980px){.shell{grid-template-columns:1fr}.sidebar{display:none}.title{font-size:34px}.topbar{display:block}.connect{justify-content:flex-start;margin-top:22px}.fields,.fields.three,.fields.blog{grid-template-columns:1fr;margin-left:0}.output,.approval{margin-left:0}.content{padding:16px}.hero{padding:24px 18px}.panel-icon{width:48px;height:48px}.panel h2{font-size:22px}}
</style>
</head>
<body>
<div class="shell">
<aside class="sidebar">
  <div class="brand"><div class="brand-main">PITMARK</div><div class="brand-sub">RACING CO.</div><div class="flag">▦▦▦</div></div>
  <nav class="nav">
    <a class="active" href="#"><span class="ico">◉</span><span>Dashboard</span></a>
    <a href="#autopilot"><span class="ico">➤</span><span>Autopilot<small>Posts & Queue</small></span></a>
    <a href="#shield"><span class="ico">⬡</span><span>Shield<small>Email Protection</small></span></a>
    <a href="#outreach"><span class="ico">🤝</span><span>Outreach<small>Tracks & Partners</small></span></a>
    <a href="#blog"><span class="ico">▤</span><span>Blog<small>Track Spotlight</small></span></a>
  </nav>
  <div class="side-bottom"><div class="motto">LEAVE YOUR MARK</div><div>PITMARK RACING CO.</div><div>BUILT BY RACERS, FOR RACERS.</div></div>
</aside>
<main class="main">
<header class="hero">
  <div class="topbar">
    <div><div class="title">PITMARK <span>CONTROL CENTER</span></div><div class="subtitle">Autopilot + Shield + Outreach + Blog Foundation</div></div>
    <div class="connect">
      <label for="key">Admin Key</label><input class="input" id="key" type="password" autocomplete="off" placeholder="X-Pitmark-Admin-Key">
      <button class="btn" id="connectBtn" type="button">Connect</button>
      <span class="status-dot" id="statusDot"></span><span id="connectionText">Not connected</span>
    </div>
  </div>
</header>
<section class="content">
  <section class="panel" id="autopilot"><div class="panel-head"><div class="panel-icon">✎</div><div><h2>Manual Post Generator</h2><div class="meta"><span>Autopilot</span><span>Approval workflow</span></div></div></div>
    <div class="fields"><select class="select" id="platform"><option>facebook</option><option>instagram</option><option>tiktok</option><option>x</option></select><select class="select" id="goal"><option>community</option><option>education</option><option>entertainment</option><option>authority</option><option>product</option><option>partner</option></select><textarea class="textarea" id="topic" placeholder="What do you want to post about?"></textarea><button class="btn" id="generateBtn" type="button">Generate</button></div>
    <pre class="output" id="draft"></pre><div class="approval"><button class="btn secondary" id="savePostBtn" type="button">Save to Approval Queue</button></div>
  </section>
  <section class="panel" id="shield"><div class="panel-head"><div class="panel-icon">✓</div><div><h2>Pitmark Shield</h2></div></div><p>Classification history and Review queue live in Pitmark Cloud. Gmail can feed the Shield API while mailbox credentials stay out of the dashboard.</p><div class="approval"><button class="btn secondary" id="shieldBtn" type="button">Load Review Queue</button></div><pre class="output" id="shieldOutput"></pre></section>
  <section class="panel" id="outreach"><div class="panel-head"><div class="panel-icon">↔</div><div><h2>Track / Partner Outreach</h2></div></div><div class="fields three"><input class="input" id="oname" placeholder="Track / league / contact"><input class="input" id="oorg" placeholder="Organization"><input class="input" id="oemail" placeholder="Email"><button class="btn" id="addOutreachBtn" type="button">Add Prospect</button><button class="btn secondary" id="loadOutreachBtn" type="button">Refresh Pipeline</button></div><pre class="output" id="outreachOutput"></pre></section>
  <section class="panel" id="blog"><div class="panel-head"><div class="panel-icon">▤</div><div><h2>Shopify Blog / Track Spotlight</h2></div></div><div class="fields blog"><input class="input" id="btitle" placeholder="Title"><textarea class="textarea" id="bbody" placeholder="Draft HTML / copy"></textarea><select class="select" id="btype"><option>article</option><option>track_spotlight</option><option>partner_spotlight</option></select><button class="btn" id="addBlogBtn" type="button">Save Draft</button><button class="btn secondary" id="loadBlogBtn" type="button">Refresh Drafts</button></div><pre class="output" id="blogOutput"></pre></section>
  <div class="footer">PITMARK CLOUD v0.9.1 · LEAVE YOUR MARK</div>
</section>
</main></div>
<script>
let generated='';
const $=id=>document.getElementById(id);
const H=()=>({'Content-Type':'application/json','X-Pitmark-Admin-Key':$('key').value.trim()});
function show(id,value){const el=$(id);el.textContent=typeof value==='string'?value:JSON.stringify(value,null,2);el.classList.add('show')}
async function apiCall(url,opt={}){opt.headers={...(opt.headers||{}),...H()};const r=await fetch(url,opt);const t=await r.text();if(!r.ok)throw new Error(t||('HTTP '+r.status));try{return JSON.parse(t)}catch{return t}}
async function connectControlCenter(){const btn=$('connectBtn');btn.disabled=true;$('connectionText').textContent='Connecting…';try{const x=await apiCall('/api/control/status');$('statusDot').className='status-dot good';$('connectionText').textContent='Connected';btn.classList.add('flash');show('draft','Control Center connected. Autopilot is ready.');setTimeout(()=>$('draft').classList.remove('show'),1400)}catch(e){$('statusDot').className='status-dot bad';$('connectionText').textContent='Connection failed';show('draft','CONNECT ERROR: '+e.message)}finally{btn.disabled=false}}
async function composePost(){try{const p=$('platform').value,g=$('goal').value,t=$('topic').value.trim();const x=await apiCall('/api/control/autopilot/composer/generate',{method:'POST',body:JSON.stringify({platform:p,goal:g,prompt:t||'Generate a useful Pitmark post',topic:t||null})});generated=x.body;show('draft',x.body+(x.visual_suggestion?'\n\nVISUAL: '+x.visual_suggestion:''))}catch(e){show('draft','GENERATOR ERROR: '+e.message)}}
async function savePost(){if(!generated){show('draft','Generate a post first.');return}try{const x=await apiCall('/api/control/autopilot/posts',{method:'POST',body:JSON.stringify({platform:$('platform').value,body:generated,content_type:$('goal').value})});show('draft',generated+'\n\nSaved as #'+x.id+' ('+x.status+')')}catch(e){show('draft','SAVE ERROR: '+e.message)}}
async function loadShield(){try{show('shieldOutput',await apiCall('/api/control/shield/events?classification=Review'))}catch(e){show('shieldOutput','SHIELD ERROR: '+e.message)}}
async function addOutreach(){try{await apiCall('/api/control/outreach',{method:'POST',body:JSON.stringify({name:$('oname').value,organization:$('oorg').value||null,email:$('oemail').value||null})});await loadOutreach()}catch(e){show('outreachOutput','OUTREACH ERROR: '+e.message)}}
async function loadOutreach(){try{show('outreachOutput',await apiCall('/api/control/outreach'))}catch(e){show('outreachOutput','OUTREACH ERROR: '+e.message)}}
async function addBlog(){try{await apiCall('/api/control/blog/drafts',{method:'POST',body:JSON.stringify({title:$('btitle').value,body_html:$('bbody').value,content_type:$('btype').value})});await loadBlog()}catch(e){show('blogOutput','BLOG ERROR: '+e.message)}}
async function loadBlog(){try{show('blogOutput',await apiCall('/api/control/blog/drafts'))}catch(e){show('blogOutput','BLOG ERROR: '+e.message)}}
$('connectBtn').addEventListener('click',connectControlCenter);$('generateBtn').addEventListener('click',composePost);$('savePostBtn').addEventListener('click',savePost);$('shieldBtn').addEventListener('click',loadShield);$('addOutreachBtn').addEventListener('click',addOutreach);$('loadOutreachBtn').addEventListener('click',loadOutreach);$('addBlogBtn').addEventListener('click',addBlog);$('loadBlogBtn').addEventListener('click',loadBlog);$('key').addEventListener('keydown',e=>{if(e.key==='Enter')connectControlCenter()});
</script>
</body></html>'''

@router.get('/control', response_class=HTMLResponse, include_in_schema=False)
def control():
    return HTML
