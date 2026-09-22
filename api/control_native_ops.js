const $=s=>document.querySelector(s);
const $$=s=>[...document.querySelectorAll(s)];
const esc=(v='')=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const num=v=>Number(v||0).toLocaleString();
const money=v=>'$'+Number(v||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
let days=30;
const initialTab=(location.hash||'').replace(/^#/,'').toLowerCase() || new URLSearchParams(location.search).get('tab');
let tab=initialTab==='social'?'social':'analytics';

function toast(message){const el=$('#toast');el.textContent=message;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),2600)}
async function request(url,options={}){
  const r=await fetch(url,{credentials:'same-origin',...options});
  if(r.status===401||r.status===403){location.assign('/control');throw new Error('Control Center login required.')}
  const text=await r.text();let data=null;try{data=text?JSON.parse(text):null}catch{data=text}
  if(!r.ok)throw new Error(data?.detail||data?.error||text||('HTTP '+r.status));
  return data;
}
function badge(value){
  const raw=String(value||'unknown');const lower=raw.toLowerCase();
  const tone=(lower==='live'||lower==='ok'||lower==='healthy'||lower==='published')?'good':(lower.includes('error')||lower.includes('fail')||lower.includes('degraded'))?'bad':'warn';
  return '<span class="badge '+tone+'">'+esc(raw)+'</span>';
}
function metric(label,value,small=''){return '<div class="card metric"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong><small>'+esc(small)+'</small></div>'}
function rows(items,emptyText='Nothing to show.'){
  if(!items?.length)return '<div class="empty">'+esc(emptyText)+'</div>';
  return '<div class="rows">'+items.join('')+'</div>';
}
function row(title,detail,right=''){return '<div class="row"><div><strong>'+esc(title)+'</strong><small>'+esc(detail)+'</small></div><div>'+right+'</div></div>'}

function renderAnalytics(data){
  const e=data.executive||{}, commerce=data.commerce||{}, growth=data.growth||{}, sources=data.sources||{};
  const googleReady=['ga4','search_console','youtube'].some(key=>sources[key]?.live);
  const top=commerce.top_products||[], recs=data.recommendations||[];
  const rel=growth.relationships||{}, prt=growth.prt||{};
  $('#analytics-view').innerHTML=
    (googleReady?'':'<section class="card" style="margin-bottom:12px"><span class="section-label">Google Data</span><h2>Connect GA4 + Search Console + YouTube</h2><p style="color:var(--muted)">One read-only authorization unlocks website traffic, search performance, and YouTube metrics.</p><button id="connect-google" type="button" class="native-action">Connect Google Analytics</button></section>')+
    '<div class="grid metrics">'+
      metric('Revenue',money(e.revenue),num(e.orders)+' orders')+
      metric('AOV',money(e.average_order_value),'Shopify')+
      metric('Traffic',num(e.sessions),num(e.users)+' users')+
      metric('Meta spend',money(e.meta_spend),num(e.meta_clicks)+' clicks')+
      metric('PRT demand',num(e.prt_applications),'applications')+
      metric('Relationships',num(e.relationships),num(rel.overdue_follow_up)+' overdue')+
    '</div>'+
    '<div class="grid two" style="margin-top:12px">'+
      '<section class="card"><span class="section-label">Decision Engine</span><h2>What deserves attention</h2>'+
        rows(recs.map(r=>'<div class="recommendation"><div>'+badge(r.priority||'info')+' <span class="badge">'+esc(r.type||'signal')+'</span></div><h3>'+esc(r.title||'Recommendation')+'</h3><p>'+esc(r.reason||'')+'</p><p><strong>Next:</strong> '+esc(r.action||'')+'</p></div>'),'No active warnings right now.')+
      '</section>'+
      '<section class="card"><span class="section-label">Connector Health</span><h2>First-party sources</h2>'+
        rows(Object.entries(sources).map(([name,value])=>row(name.replaceAll('_',' '),value?.error||'Direct Pitmark connector',badge(value?.live?'live':value?.status||'not configured'))))+
      '</section>'+
    '</div>'+
    '<div class="grid two" style="margin-top:12px">'+
      '<section class="card"><span class="section-label">Commerce</span><h2>Top products</h2>'+
        rows(top.slice(0,10).map(p=>row(p.title||'Product',num(p.quantity)+' units · '+num(p.orders)+' order lines','<strong>'+money(p.revenue)+'</strong>')),'No qualifying product sales in this window.')+
      '</section>'+
      '<section class="card"><span class="section-label">Growth</span><h2>PRT + relationships</h2>'+
        rows([
          row('PRT applications',num(prt.applications_total),badge(num(prt.applications_new)+' new')),
          row('PRT tester activation',num(prt.testers_redeemed)+' redeemed',badge((prt.redemption_rate??0)+'%')),
          row('Warm relationships',num(rel.warm),badge(num(rel.overdue_follow_up)+' overdue')),
          row('Stale open relationships',num(rel.stale_open),'')
        ])+
      '</section>'+
    '</div>';
}

function groupCalendar(items){
  const map=new Map();
  for(const item of items||[]){
    const raw=item.scheduled_for||item.updated_at||item.created_at;if(!raw)continue;
    const d=new Date(raw);if(Number.isNaN(d.getTime()))continue;
    const key=d.toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'});
    if(!map.has(key))map.set(key,[]);map.get(key).push(item);
  }
  return [...map.entries()];
}
function renderSocial(data){
  const s=data.summary||{}, op=data.operator||{}, cal=data.calendar||{}, windows=data.posting_windows||{};
  const groups=groupCalendar(cal.items||[]).slice(0,21);
  $('#social-view').innerHTML=
    '<div class="grid metrics">'+
      metric('Published',num(s.published),'all tracked')+
      metric('Scheduled',num(s.scheduled),'upcoming queue')+
      metric('Pending',num(s.pending),'needs decision')+
      metric('Approved',num(s.approved),'ready to schedule')+
      metric('Review queue',num(s.review_queue),'engagement')+
      metric('Operator',String(op.status||'unknown'),op.summary||'latest run')+
    '</div>'+
    '<div class="grid two" style="margin-top:12px">'+
      '<section class="card"><span class="section-label">Publishing Calendar</span><h2>Current social schedule</h2>'+
        (groups.length?'<div class="calendar">'+groups.map(([day,items])=>'<div class="day"><strong>'+esc(day)+'</strong>'+items.slice(0,6).map(item=>'<div class="event"><b>'+esc(item.platform||'platform')+'</b><span>'+esc(item.status||'')+' · '+esc((item.title||item.body||'').slice(0,70))+'</span></div>').join('')+'</div>').join('')+'</div>':'<div class="empty">No calendar items in this window.</div>')+
      '</section>'+
      '<section class="card"><span class="section-label">Posting Windows</span><h2>Cadence guardrails</h2>'+
        rows(Object.entries(windows).map(([platform,times])=>row(platform,times.join(' · '),badge(num((data.platforms||{})[platform])+' tracked'))))+
      '</section>'+
    '</div>'+
    '<div class="grid two" style="margin-top:12px">'+
      '<section class="card"><span class="section-label">Channel Health</span><h2>Social Operator</h2>'+
        rows(Object.entries(op.channels||{}).map(([name,value])=>row(name,(value?.error||('scanned '+num(value?.scanned))),badge(value?.ok===false?'degraded':'healthy'))),'No channel health run recorded yet.')+
      '</section>'+
      '<section class="card"><span class="section-label">Recommendations</span><h2>What to do next</h2>'+
        rows((data.recommendations||[]).map(r=>'<div class="recommendation">'+badge(r.priority||'info')+'<h3>'+esc(r.title||'Recommendation')+'</h3><p>'+esc(r.detail||'')+'</p></div>'),'No social operations warnings right now.')+
      '</section>'+
    '</div>';
}

function applyDeskIdentity(){
  const title=document.querySelector('.top h1');
  const copy=document.querySelector('.top p');
  if(title) title.textContent=tab==='social'?'Pitmark Social Desk':'Pitmark Analytics';
  if(copy) copy.textContent=tab==='social'
    ? 'Calendar, publishing, channel health, engagement, and social performance without Metricool.'
    : 'Sales, traffic, ads, PRT, outreach, and business performance without Supermetrics.';
  document.title=(tab==='social'?'Pitmark Social Desk':'Pitmark Analytics')+' · Control Center';
}

async function load(force=false){
  $('#status').textContent='Loading Pitmark data…';
  try{
    const base=tab==='analytics'?'/api/control/native-ops/analytics':'/api/control/native-ops/social';
    const data=await request(base+'?days='+days+(force?'&force=true':''));
    if(tab==='analytics')renderAnalytics(data);else renderSocial(data);
    const generated=data.generated_at?new Date(data.generated_at).toLocaleTimeString([],{hour:'numeric',minute:'2-digit'}):'now';
    $('#status').textContent=(data.cached?'Cached · ':'Live · ')+days+'d · '+generated;
  }catch(e){
    $('#status').textContent='Data error';
    const target=tab==='analytics'?$('#analytics-view'):$('#social-view');
    target.innerHTML='<section class="card"><h2>Could not load this desk</h2><p>'+esc(e.message||'Unknown error')+'</p></section>';
  }
}

async function connectGoogle(){
  let popup=null;
  try{
    popup=window.open('about:blank','pitmark-google-intelligence');
    const start=await request('/api/control/intelligence/google/oauth/start',{method:'POST'});
    if(popup)popup.location.href=start.authorization_url;else window.open(start.authorization_url,'_blank','noopener');
    const callback=prompt('After Google redirects to localhost, copy the full URL from the address bar and paste it here.');
    if(!callback)return;
    await request('/api/control/intelligence/google/oauth/complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({callback_url:callback.trim()})});
    await request('/api/control/native-ops/refresh',{method:'POST'});
    toast('Google analytics connected.');
    await load(true);
  }catch(e){
    try{popup?.close();}catch{}
    toast(e.message||'Google connection failed.');
  }
}
document.addEventListener('click',event=>{if(event.target.closest('#connect-google'))connectGoogle();});

$$('[data-tab]').forEach(btn=>btn.addEventListener('click',()=>{
  tab=btn.dataset.tab;
  history.replaceState(null,'','#'+tab);
  $$('[data-tab]').forEach(x=>x.classList.toggle('is-active',x===btn));
  applyDeskIdentity();
  $('#analytics-view').hidden=tab!=='analytics';$('#social-view').hidden=tab!=='social';load(false);
}));
$$('[data-days]').forEach(btn=>btn.addEventListener('click',()=>{
  days=Number(btn.dataset.days)||30;$$('[data-days]').forEach(x=>x.classList.toggle('is-active',x===btn));load(false);
}));
$$('[data-tab]').forEach(btn=>btn.classList.toggle('is-active',btn.dataset.tab===tab));
applyDeskIdentity();
$('#analytics-view').hidden=tab!=='analytics';
$('#social-view').hidden=tab!=='social';

$('#refresh').addEventListener('click',async()=>{
  try{await request('/api/control/native-ops/refresh',{method:'POST'});}catch{}
  await load(true);toast('Pitmark data refreshed.');
});
load(false);
