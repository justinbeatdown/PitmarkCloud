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
  const raw=String(value||'unknown');
  const lower=raw.toLowerCase();
  const good=['live','ok','healthy','published','connected'].includes(lower);
  const bad=lower==='error'||lower==='failed'||lower.includes('fatal')||lower.includes('degraded');
  return '<span class="badge '+(good?'good':bad?'bad':'warn')+'">'+esc(raw.replaceAll('_',' '))+'</span>';
}
function metric(label,value,small=''){return '<div class="card metric"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong><small>'+esc(small)+'</small></div>'}
function rows(items,emptyText='Nothing to show.'){
  if(!items?.length)return '<div class="empty">'+esc(emptyText)+'</div>';
  return '<div class="rows">'+items.join('')+'</div>';
}
function row(title,detail,right=''){return '<div class="row"><div><strong>'+esc(title)+'</strong><small>'+detail+'</small></div><div>'+right+'</div></div>'}
function clip(value,length=92){
  const text=String(value||'').replace(/\s+/g,' ').trim();
  return text.length>length?text.slice(0,length-1)+'…':text;
}
function safeUrl(value){
  try{
    const u=new URL(String(value||''),location.origin);
    return ['http:','https:'].includes(u.protocol)?u.href:'';
  }catch{return ''}
}
function inlineLink(label,url){
  const safe=safeUrl(url);
  return safe?'<a class="inline-link" href="'+esc(safe)+'" target="_blank" rel="noopener noreferrer">'+esc(label)+'</a>':'';
}
function sourceActions(value){
  const actions=(value?.setup_urls||[]).map(item=>inlineLink(item?.label||'Open setup',item?.url)).filter(Boolean);
  return actions.length?'<div class="source-actions">'+actions.join('')+'</div>':'';
}
function sourceHealthRow(name,value){
  const status=value?.live?'live':value?.status||'not_configured';
  const detail=esc(value?.error||value?.note||'Direct Pitmark connector')+sourceActions(value);
  return row(name.replaceAll('_',' '),detail,badge(status));
}
function pct(value){
  const n=Number(value||0);
  return (n<=1?n*100:n).toLocaleString(undefined,{maximumFractionDigits:1})+'%';
}
function dateTime(value){
  if(!value)return 'Unknown time';
  const d=new Date(value);
  return Number.isNaN(d.getTime())?'Unknown time':d.toLocaleString([],{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
}

function renderAnalytics(data){
  const e=data.executive||{}, commerce=data.commerce||{}, growth=data.growth||{}, sources=data.sources||{};
  const social=data.social||{}, meta=social.meta||{}, google=social.google||{};
  const facebook=meta.facebook||{}, instagram=meta.instagram||{}, ga4=google.ga4||{}, search=google.search_console||{};
  const fbPage=facebook.page||{}, igProfile=instagram.profile||{};
  const googleReady=['ga4','search_console'].some(key=>sources[key]?.live);
  const googleConnected=['ga4','search_console'].some(key=>!['not_configured','auth_required'].includes(String(sources[key]?.status||'')));
  const googleNeedsApi=['ga4','search_console'].some(key=>String(sources[key]?.status||'')==='api_disabled');
  const top=commerce.top_products||[], recentOrders=commerce.recent_orders||[], recs=data.recommendations||[];
  const rel=growth.relationships||{}, prt=growth.prt||{};
  const fbTop=(facebook.top_posts||[]).map(p=>({
    platform:'Facebook',
    text:p.message||'Facebook post',
    engagement:Number(p.engagement_actions||0),
    url:p.permalink_url,
    timestamp:p.created_time
  }));
  const igTop=(instagram.top_posts||[]).map(p=>({
    platform:'Instagram',
    text:p.caption||'Instagram post',
    engagement:Number(p.engagement_actions||0),
    url:p.permalink,
    timestamp:p.timestamp
  }));
  const topSocial=[...fbTop,...igTop].sort((a,b)=>b.engagement-a.engagement).slice(0,8);
  const setupLinks=['ga4','search_console'].flatMap(key=>(sources[key]?.setup_urls||[])).filter((item,index,array)=>array.findIndex(x=>x?.url===item?.url)===index);
  const googleBanner=googleReady?'':googleNeedsApi
    ? '<section class="card setup-card"><span class="section-label">Google Data</span><h2>Google is connected — turn on the data pipes</h2><p>Your authorization is good. The Google Cloud project still has the reporting APIs disabled. Enable them once and Pitmark will start reading GA4 + Search Console automatically.</p><div class="setup-actions">'+setupLinks.map(item=>inlineLink(item?.label||'Enable API',item?.url)).join('')+'</div></section>'
    : googleConnected
      ? '<section class="card setup-card"><span class="section-label">Google Data</span><h2>Google connected · source setup needs attention</h2><p>The account is authorized, but a GA4 property or Search Console property still needs to be visible to Pitmark. Connector Health below shows exactly which source needs attention.</p></section>'
      : '<section class="card setup-card"><span class="section-label">Google Data</span><h2>Connect GA4 + Search Console</h2><p>One read-only authorization unlocks website traffic and Google search performance. YouTube stays separate so it cannot block this setup.</p><button id="connect-google" type="button" class="native-action">Connect Google Analytics</button></section>';

  $('#analytics-view').innerHTML=
    googleBanner+
    '<div class="grid metrics">'+
      metric('Revenue',money(e.revenue),num(e.orders)+' orders')+
      metric('AOV',money(e.average_order_value),'Shopify')+
      metric('Traffic',num(e.sessions),num(e.users)+' users')+
      metric('Meta spend',money(e.meta_spend),num(e.meta_clicks)+' clicks')+
      metric('PRT demand',num(e.prt_applications),'applications')+
      metric('Relationships',num(e.relationships),num(rel.overdue_follow_up)+' overdue')+
    '</div>'+
    '<div class="grid two section-gap">'+
      '<section class="card"><span class="section-label">Decision Engine</span><h2>What deserves attention</h2>'+
        rows(recs.map(r=>'<div class="recommendation"><div>'+badge(r.priority||'info')+' <span class="badge">'+esc(r.type||'signal')+'</span></div><h3>'+esc(r.title||'Recommendation')+'</h3><p>'+esc(r.reason||'')+'</p><p><strong>Next:</strong> '+esc(r.action||'')+'</p></div>'),'No active warnings right now.')+
      '</section>'+
      '<section class="card"><span class="section-label">Connector Health</span><h2>First-party sources</h2>'+
        rows(Object.entries(sources).map(([name,value])=>sourceHealthRow(name,value)))+
      '</section>'+
    '</div>'+
    '<div class="grid two section-gap">'+
      '<section class="card"><span class="section-label">Social Performance</span><h2>Facebook + Instagram</h2>'+
        '<div class="mini-metrics">'+
          '<div><span>Facebook followers</span><strong>'+num(fbPage.followers_count??fbPage.fan_count)+'</strong></div>'+
          '<div><span>FB engagement</span><strong>'+num(facebook.engagement_actions)+'</strong></div>'+
          '<div><span>Instagram followers</span><strong>'+num(igProfile.followers_count)+'</strong></div>'+
          '<div><span>IG engagement</span><strong>'+num(instagram.engagement_actions)+'</strong></div>'+
        '</div>'+
        '<span class="section-label sub-label">Top social posts</span>'+
        rows(topSocial.map(p=>row(
          p.platform+' · '+clip(p.text,82),
          esc(dateTime(p.timestamp))+(p.url?' · '+inlineLink('Open post',p.url):''),
          badge(num(p.engagement)+' actions')
        )),'Social post performance will appear as connector permissions allow.')+
      '</section>'+
      '<section class="card"><span class="section-label">Acquisition</span><h2>Website + Google Search</h2>'+
        '<span class="section-label sub-label">Top pages</span>'+
        rows((ga4.top_pages||[]).slice(0,6).map(p=>row(
          clip(p.path||'Page',78),
          esc(num(p.sessions)+' sessions'),
          badge(num(p.page_views)+' views')
        )),'GA4 top pages will appear once the Analytics APIs are enabled.')+
        '<span class="section-label sub-label">Top searches</span>'+
        rows((search.top_queries||[]).slice(0,6).map(q=>row(
          clip(q.query||'Search query',78),
          esc(num(q.clicks)+' clicks · '+num(q.impressions)+' impressions · '+pct(q.ctr)),
          badge('pos '+Number(q.position||0).toFixed(1))
        )),'Search Console queries will appear once that API is enabled.')+
      '</section>'+
    '</div>'+
    '<div class="grid two section-gap">'+
      '<section class="card"><span class="section-label">Commerce</span><h2>Top products</h2>'+
        rows(top.slice(0,10).map(p=>row(
          esc(p.title||'Product'),
          esc(num(p.quantity)+' units · '+num(p.orders)+' order lines'),
          '<strong>'+money(p.revenue)+'</strong>'
        )),'No qualifying product sales in this window.')+
      '</section>'+
      '<section class="card"><span class="section-label">Recent Orders</span><h2>Latest Shopify conversions</h2>'+
        rows(recentOrders.slice(0,8).map(order=>row(
          esc(order.name||'Order'),
          esc(dateTime(order.created_at)+' · '+String(order.financial_status||'').replaceAll('_',' ').toLowerCase()),
          '<strong>'+money(order.amount)+'</strong>'
        )),'No qualifying orders in this reporting window.')+
      '</section>'+
    '</div>'+
    '<div class="grid two section-gap">'+
      '<section class="card"><span class="section-label">Growth</span><h2>PRT + relationships</h2>'+
        rows([
          row('PRT applications',esc(num(prt.applications_total)),badge(num(prt.applications_new)+' new')),
          row('PRT tester activation',esc(num(prt.testers_redeemed)+' redeemed'),badge((prt.redemption_rate??0)+'%')),
          row('Warm relationships',esc(num(rel.warm)),badge(num(rel.overdue_follow_up)+' overdue')),
          row('Stale open relationships',esc(num(rel.stale_open)),'')
        ])+
      '</section>'+
      '<section class="card"><span class="section-label">Replacement Coverage</span><h2>Metricool + Supermetrics exit readiness</h2>'+
        '<div class="readiness"><strong>'+num(e.live_sources)+' / '+num(e.source_count)+'</strong><span>sources live now</span></div>'+
        rows([
          row('Commerce + revenue','Shopify is the source of truth.',badge(sources.shopify?.live?'ready':sources.shopify?.status)),
          row('Social publishing','Pitmark scheduler + Social Desk own the workflow.',badge('ready')),
          row('Social reporting','Meta reads are first-party; TikTok/YouTube remain staged.',badge(sources.meta?.status||'checking')),
          row('Web + SEO','GA4 + Search Console feed the acquisition view.',badge(googleReady?'ready':'setup')),
          row('PRT + outreach','Native Pitmark data is already unified here.',badge('ready'))
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
  const failures=(cal.failures||[]).slice(0,8);
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
        (failures.length?'<div style="margin-top:14px"><span class="section-label">Publishing issues</span>'+rows(failures.map(item=>row(item.platform||'platform',(item.title||item.body||'').slice(0,85),badge(item.status||'failed'))))+'</div>':'')+
      '</section>'+
      '<section class="card"><span class="section-label">Posting Windows</span><h2>Cadence guardrails</h2>'+
        rows(Object.entries(windows).map(([platform,times])=>row(platform,times.join(' · '),badge(num((data.platforms||{})[platform])+' tracked'))))+
      '</section>'+
    '</div>'+
    '<div class="grid two" style="margin-top:12px">'+
      '<section class="card"><span class="section-label">Channel Health</span><h2>Social Operator</h2>'+
        rows(Object.entries(op.channels||{}).map(([name,value])=>{
          const status=value?.status==='limited'?'limited':(value?.ok===false?'degraded':'healthy');
          const detail=value?.note||value?.error||('scanned '+num(value?.scanned));
          return row(name,detail,badge(status));
        }),'No channel health run recorded yet.')+
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

function closeGoogleConnectPanel(){
  document.getElementById('google-connect-panel')?.remove();
}
function showGoogleConnectPanel(){
  closeGoogleConnectPanel();
  const panel=document.createElement('div');
  panel.id='google-connect-panel';
  panel.className='native-modal-backdrop';
  panel.innerHTML='<div class="native-modal"><span class="section-label">Google Analytics</span><h2>Finish the connection</h2><p>Google will end on a localhost page that says it cannot connect. That is expected. Copy the <strong>entire URL</strong> from that page\'s address bar, come back here, and paste it below.</p><label for="google-callback-url">Google callback URL</label><textarea id="google-callback-url" placeholder="http://127.0.0.1:8765/?state=...&code=..."></textarea><div class="native-modal-actions"><button type="button" id="google-cancel">Cancel</button><button type="button" class="native-action" id="google-complete">Complete connection</button></div><small id="google-connect-status"></small></div>';
  document.body.appendChild(panel);
  document.getElementById('google-cancel')?.addEventListener('click',closeGoogleConnectPanel);
  document.getElementById('google-complete')?.addEventListener('click',completeGoogleConnect);
}
async function completeGoogleConnect(){
  const input=document.getElementById('google-callback-url');
  const status=document.getElementById('google-connect-status');
  const callback=input?.value?.trim()||'';
  if(!callback){if(status)status.textContent='Paste the full localhost URL first.';return;}
  if(!/^https?:\/\/127\.0\.0\.1:8765\/\?/i.test(callback)){
    if(status)status.textContent='That does not look like the Google callback URL from 127.0.0.1:8765.';
    return;
  }
  if(status)status.textContent='Connecting Google Analytics…';
  try{
    await request('/api/control/intelligence/google/oauth/complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({callback_url:callback})});
    await request('/api/control/native-ops/refresh',{method:'POST'});
    closeGoogleConnectPanel();
    toast('GA4 + Search Console connected.');
    await load(true);
  }catch(e){
    if(status)status.textContent=e.message||'Google connection failed.';
  }
}
async function connectGoogle(){
  let popup=null;
  try{
    const start=await request('/api/control/intelligence/google/oauth/start',{method:'POST'});
    showGoogleConnectPanel();
    popup=window.open(start.authorization_url,'pitmark-google-intelligence');
    if(!popup) window.open(start.authorization_url,'_blank','noopener');
  }catch(e){
    try{popup?.close();}catch{}
    closeGoogleConnectPanel();
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
