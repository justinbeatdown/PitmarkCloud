/* Native Control Center workspaces. Data loads on demand, never all on the home page. */
const esc = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
const fmt = value => value===null||value===undefined?'—':Number(value).toLocaleString();
const when = value => {if(!value)return 'Date unavailable';const d=new Date(value);return Number.isFinite(d.valueOf())?d.toLocaleString([],{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):String(value).slice(0,30)};
const short = (s,n=210) => String(s||'').replace(/\s+/g,' ').slice(0,n);
const heading=(title,subtitle,actions='')=>'<header class="page-head"><div><div class="eyebrow">PITMARK / OPERATIONS</div><h1>'+esc(title)+'</h1><p>'+esc(subtitle)+'</p></div><div class="page-actions">'+actions+'</div></header>';
const button=(label,action,cls='btn outline',other='')=>'<button type="button" class="'+esc(cls)+'" data-action="'+esc(action)+'" '+other+'>'+esc(label)+'</button>';
const pane=(label,title,contents)=>'<section class="panel"><header class="panel-head"><div class="kicker">'+esc(label)+'</div><h2>'+esc(title)+'</h2></header><div class="panel-body">'+contents+'</div></section>';
const note=(title,detail='')=>'<div class="empty"><b>'+esc(title)+'</b><p>'+esc(detail)+'</p></div>';
const errorBox=(err)=>'<div class="error-banner"><strong>Unable to load this workspace</strong><p>'+esc(err?.message||err||'Connection unavailable')+'. The rest of Control Center remains usable.</p></div>';
const field=(name,label,value='',type='text',extra='')=>'<div class="field"><label for="'+esc(name)+'">'+esc(label)+'</label><input class="field-input" id="'+esc(name)+'" name="'+esc(name)+'" type="'+esc(type)+'" value="'+esc(value||'')+'" '+extra+'></div>';
const tag=(v)=>'<span class="inline-status">'+esc(String(v||'unknown').replaceAll('_',' '))+'</span>';
const row=(name,meta,body,controls='',classes='')=>'<article class="workspace-row '+esc(classes)+'"><div class="meta">'+meta+'</div><h3>'+esc(name||'Untitled')+'</h3>'+(body?'<p>'+esc(short(body,430))+'</p>':'')+(controls?'<div class="actions">'+controls+'</div>':'')+'</article>';
const ttl=new Map(),inflight=new Map(),currentRecords={},sections={inbox:'action',mail:'inbox',content:'pending',relationships:'all',prt:'applications',work:'now',racing:'results',store:'overview',growth:'30',systems:'health'};
const selections={mail:null,contact:null,post:null,work:null};
const pagination={content:0,relationships:0,mail:0};
let active=0;
let busyMutation=false;
let searchValue='';
async function request(url,options={},timeout=8500){
 const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),timeout);
 try{
  const response=await fetch(url,{credentials:'same-origin',cache:'no-store',signal:ctrl.signal, ...options});
  if(response.status===401||response.status===403){location.assign('/control');throw Error('Please sign in again.');}
  const raw=await response.text();let data;try{data=raw?JSON.parse(raw):null}catch{data=raw}
  if(!response.ok)throw Error(String(data?.detail||data?.error||('Server returned '+response.status)).slice(0,280));
  return data;
 }catch(e){if(e?.name==='AbortError')throw Error('This source is taking too long. It may be disconnected; retry this section when ready.');throw e;}
 finally{clearTimeout(timer);}
}
async function read(url,ttlMs=12000,timeout=8500){
 const cached=ttl.get(url),now=Date.now();
 if(cached&&now-cached.at<ttlMs)return cached.value;
 if(inflight.has(url))return inflight.get(url);
 const pending=request(url,{},timeout).then(data=>{ttl.set(url,{value:data,at:Date.now()});return data;}).finally(()=>inflight.delete(url));
 inflight.set(url,pending);return pending;
}
const invalidate=(prefix='')=>{for(const k of ttl.keys())if(!prefix||k.includes(prefix))ttl.delete(k);};
const write=(url,method,body)=>request(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)},15000);
const urlSearch=(resource,opts={})=>{const u=new URL('/api/control/hq/v2/records/'+resource,location.origin);for(const [k,v]of Object.entries(opts))if(v!==undefined&&v!==null&&v!=='')u.searchParams.set(k,v);return u.pathname+u.search;};
function renderTabs(view,choices){return '<div class="workspace-tabs" role="tablist" aria-label="'+esc(view)+' views">'+choices.map(([value,label])=>button(label,'tab:'+view+':'+value,'workspace-tab'+(sections[view]===value?' active':''),'role="tab" aria-selected="'+String(sections[view]===value)+'"')).join('')+'</div>';}
const pageNav=(key,data)=>'<div class="workspace-controls"><span class="inline-status">'+fmt(data.total)+' total · showing '+(data.items?.length?fmt((data.offset||0)+1):'0')+'–'+fmt((data.offset||0)+(data.items?.length||0))+'</span>'+button('← Previous','page:'+key+':prev','btn mini',pagination[key]===0?'disabled':'')+button('Next →','page:'+key+':next','btn mini',!data.has_more?'disabled':'')+'</div>';
const refresh=()=>button('↻ Refresh','refresh','btn outline');
async function mountInbox(root,ctx){
 const list=Array.isArray(ctx.core?.actions)?ctx.core.actions:[];
 const html=heading('Decision inbox','Review what requires your judgment without leaving this interface.',refresh())+
 (ctx.core?.status!=='live'?errorBox('Owner activity source is unavailable.'):pane('ACTION REQUIRED','Your operating queue',list.length?list.map(a=>{
   let dest=a.kind==='publishing'||a.kind==='approval'?'#content':a.kind==='relationship'?'#relationships':a.kind==='system'?'#systems':'#work';
   const id=a.kind==='publishing'?'post:'+String(a.id||'').split(':').pop():a.kind==='relationship'?'contact:'+String(a.id||'').split(':').pop():'';
   return row(a.title,'<span>'+esc(a.kind)+'</span> · '+esc(when(a.at)),a.detail,button('Review here','navigate:'+dest+(id?':'+id:''),'btn mini accent'));
 }).join(''):note('You are caught up','No actionable records are currently returned by Pitmark Cloud.')));
 root.innerHTML=html;
}
async function mountMail(root,ctx){
 const folder=sections.mail;
 const data=await read('/api/control/email/threads?folder='+encodeURIComponent(folder)+'&limit=90',15000,10000);
 if(!Array.isArray(data))throw Error('Mail returned an unsupported response.');
 const itemList=data.slice(pagination.mail,pagination.mail+35);
 const controls=renderTabs('mail',[['inbox','Inbox'],['sent','Sent'],['drafts','Drafts']])+button('Compose','mail-compose','btn accent');
 let list=itemList.map(m=>{
   const t=m.thread||{};const id=m.thread_id||t.id;
   const title=t.subject||m.subject||'(No subject)';
   const who=String(m.from||t.participants?.[0]||'Unknown sender');
   return row(title,esc(who)+' · '+esc(when(m.created_at||t.last_message_at))+(t.unread_count?' · Unread':''),short(m.text||'Open the conversation'),button('Read','mail-open:'+id,'btn mini'),Number(t.unread_count)>0?'mail-unread':'');
 }).join('');
 const left=pane('GOOGLE WORKSPACE',folder==='inbox'?'Mail inbox':folder==='sent'?'Sent mail':'Saved drafts',
  controls+'<div class="workspace-controls">'+button('Earlier','page:mail:prev','btn mini',pagination.mail===0?'disabled':'')+button('Later','page:mail:next','btn mini',pagination.mail+35>=data.length?'disabled':'')+
  '<span class="small-note">'+fmt(data.length)+' conversations returned</span></div>'+(list||note('Nothing in this folder','Mail is read from the synchronized Cloud mailbox.')));
 const selected=selections.mail;
 let right='';
 if(selected?.type==='compose')right=mailCompose(selected);
 else if(selected?.thread)right=mailThread(selected.thread);
 else right=pane('CONVERSATIONS','Read & reply',note('Choose a conversation','Open a message on the left to read, reply, or save a draft.'));
 root.innerHTML=heading('Mail & features','A real inbox inside Pitmark HQ. Read replies, keep feature interviews moving, and respond when ready.',refresh())+'<div class="workspace-pair">'+left+right+'</div>';
}
function mailThread(data){
 const messages=data.messages||[],t=data.thread||{};
 const last=[...messages].reverse().find(m=>m.direction==='inbound')||messages[messages.length-1]||{};
 const raw=String(last.from||'');
 const replies=messages.map(m=>row(m.from||'Pitmark',esc(m.direction||'message')+' · '+esc(when(m.created_at)),short(m.text||'HTML-only message — use the Gmail view for formatting.',2500))).join('');
 return pane('THREAD / '+esc(when(t.last_message_at)),t.subject||'Conversation','<div style="max-height:440px;overflow:auto">'+(replies||note('No messages','This conversation has no saved messages.'))+'</div>'+
 '<div class="workspace-controls">'+button('Reply','mail-reply','btn accent')+button('New message','mail-compose','btn outline')+'</div>');
}
function mailCompose(o={}){
 const s=o.subject||'',to=o.to||'',id=o.reply_id||'',body=o.body||'';
 return pane('NEW MESSAGE',id?'Reply to conversation':'Compose email',
 '<form class="workspace-form" id="mail-form">'+field('mail-to','To',to,'email','required')+field('mail-subject','Subject',s,'text','required')+
 '<div class="field"><label for="mail-body">Message</label><textarea class="field-area" id="mail-body" required>'+esc(body)+'</textarea></div>'+
 '<div class="actions"><button class="btn accent" type="submit">Send email</button>'+button('Save draft','mail-draft','btn outline')+button('Cancel','mail-cancel','btn outline')+'</div>'+
 '<p class="workspace-note">Messages send only when you explicitly press Send and confirm. Saving a draft does not send it.</p></form>');
}
async function mountContent(root,ctx){
 const tab=sections.content;
 const opts={limit:35,offset:pagination.content,status:tab==='editorial'?'draft':tab};
 const resource=tab==='editorial'?'editorial':'posts';
 const data=await read(urlSearch(resource,opts),14000,8500);
 currentRecords.content=data.items||[];
 let rows=(data.items||[]).map(p=>{
  if(tab==='editorial'){
   return row(p.title,esc(p.content_type||'Article')+' · '+esc(when(p.updated_at))+' · '+esc(p.status),'Editorial draft',
     button('Approve draft','article-approve:'+p.id,'btn mini accent')+button('Archive','article-archive:'+p.id,'btn mini'));
  }
  const blocked=['failed','error','needs_review','blocked','publish_failed'].includes(p.status);
  let controls=button('Edit / preview','post-edit:'+p.id,'btn mini');
  if(p.status==='pending')controls+=button('Approve','post-approve:'+p.id,'btn mini accent')+button('Reject','post-reject:'+p.id,'btn mini');
  if(blocked)controls+=button('Inspect failure','post-edit:'+p.id,'btn mini');
  return row(p.title||short(p.body,78),esc(p.platform)+' · '+esc(p.status)+' · '+esc(when(p.scheduled_for||p.updated_at)),
  short(p.body,300)+(blocked?' · Verify provider delivery before retrying.':''),controls,blocked?'mail-unread':'');
 }).join('');
 let selected=selections.post;
 let editor=selected?postEditor(selected):'';
 const body=renderTabs('content',[['pending','Approvals'],['approved','Approved'],['scheduled','Scheduled'],['attention','Failed / review'],['published','Published'],['editorial','Editorial']])+
 '<div class="workspace-controls">'+button('New social post','post-new','btn accent')+'</div>'+
 (rows||note('No records on this tab','This is a live, paginated view. Try another status.'))+pageNav('content',data);
 const metric=ctx.core?.metrics||{};
 root.innerHTML=heading('Content studio','Approvals, scheduling, problems, and articles — managed without opening Classic.',refresh())+
 '<div class="metrics">'+[
 ['Pending approvals',metric.pending_posts],['Scheduled posts',metric.scheduled_posts],
 ['Needs investigation',metric.failed_posts],['Published articles',metric.published_articles]
 ].map(([n,v])=>'<div class="metric"><small>'+esc(n)+'</small><strong>'+fmt(v)+'</strong></div>').join('')+'</div>'+
 (editor?'<div class="workspace-pair">'+pane('EDITORIAL & PUBLISHING',tab==='editorial'?'Article drafts':'Social pipeline',body)+editor+'</div>':pane('EDITORIAL & PUBLISHING',tab==='editorial'?'Article drafts':'Social pipeline',body))+
 '<p class="workspace-note">“Approved” means approved in Pitmark Cloud, not necessarily published by the destination platform. Failed/ambiguous posts are never automatically retried here.</p>';
}
function postEditor(p){
 const draft=p.id===null,valid=!['published','archived','rejected'].includes(p.status||'pending');
 let more='';
 if(p.media_url){
  try{const u=new URL(p.media_url,location.origin);if(['https:','http:'].includes(u.protocol))more='<a class="btn outline mini" href="'+esc(u.href)+'" target="_blank" rel="noopener noreferrer">View attached media ↗</a>';}catch{}
 }
 return pane('EDIT / PREVIEW',draft?'Create social post':'Post #'+p.id,
 '<form id="post-form" class="workspace-form"><div class="field"><label for="post-platform">Platform</label><select id="post-platform" class="field-input" '+(!draft?'disabled':'')+'>'+
 ['facebook','instagram','tiktok','x'].map(v=>'<option value="'+v+'"'+(p.platform===v?' selected':'')+'>'+v.toUpperCase()+'</option>').join('')+'</select></div>'+
 field('post-title','Title',p.title||'')+
 '<div class="field"><label for="post-body">Post copy</label><textarea class="field-area" id="post-body" style="min-height:170px">'+esc(p.body||'')+'</textarea></div>'+
 '<div class="actions">'+(valid?'<button type="submit" class="btn accent">'+(draft?'Save to approval queue':'Save changes')+'</button>':'')+more+
 button('Close editor','post-close','btn mini')+'</div></form>');
}
async function mountRelationships(root,ctx){
 const data=await read(urlSearch('relationships',{limit:35,offset:pagination.relationships,q:searchValue}),12000,8500);
 currentRecords.relationships=data.items||[];
 const selected=selections.contact;
 const right=selected?contactEditor(selected):null;
 const left=pane('PITMARK NETWORK','Partners & contacts',
 '<form id="relationship-search" class="workspace-controls">'+
 '<input name="q" id="relationship-query" value="'+esc(searchValue)+'" placeholder="Search name or organization" aria-label="Search relationships">'+
 '<button type="submit" class="btn mini">Search</button>'+button('New contact','contact-new','btn accent')+'</form>'+
 (data.items||[]).map(p=>{
  const date=p.next_follow_up?when(p.next_follow_up):'None scheduled';
  const desc=[p.name,p.email].filter(Boolean).join(' · ');
  return row(p.organization||p.name,esc(p.contact_type)+' · '+esc(p.stage)+' · Follow-up '+esc(date),desc,button('Open / edit','contact-edit:'+p.id,'btn mini'));
 }).join('')+pageNav('relationships',data));
 root.innerHTML=heading('Relationships','Keep the entire motorsports network moving from one workspace.',refresh())+
 '<div class="workspace-pair">'+left+(right||pane('RELATIONSHIP DETAILS','Select a contact',note('Choose a relationship','Update a stage, notes, follow-up date, or add a new contact here.')))+'</div>';
}
function contactEditor(p){
 const fresh=p.id===null;
 return pane('RELATIONSHIP',fresh?'New contact':(p.organization||p.name||'Contact'),
 '<form class="workspace-form" id="contact-form">'+field('contact-name','Contact name',p.name||'','text','required')+
 field('contact-org','Organization',p.organization||'')+field('contact-email','Email',p.email||'','email')+
 field('contact-type','Type',p.contact_type||'track')+field('contact-stage','Stage',p.stage||'prospect')+
 field('contact-follow','Next follow-up',p.next_follow_up?String(p.next_follow_up).slice(0,10):'','date')+
 '<div class="field"><label for="contact-notes">Notes</label><textarea id="contact-notes" class="field-area">'+esc(p.notes||'')+'</textarea></div>'+
 '<div class="actions"><button class="btn accent" type="submit">'+(fresh?'Create contact':'Save relationship')+'</button>'+button('Close','contact-close','btn outline')+'</div></form>');
}
async function mountPRT(root,ctx){
 const tab=sections.prt,urls={applications:'/api/control/ops/testers?limit=100',feedback:'/api/control/ops/feedback?limit=100',testers:'/api/control/ops/testers?limit=100',founders:'/api/control/ops/founders-race'};
 const d=await read(urls[tab],18000,11000);
 let listing='';
 if(tab==='applications'){
  const a=(d.applications||[]).filter(x=>['new','hold','pending','reviewing'].includes(String(x.status||'new').toLowerCase()));
  listing=a.map(p=>row(p.full_name||p.name||p.email,esc(p.role||'Driver')+' · '+esc(p.status)+' · '+esc(when(p.created_at||p.submitted_at)),[p.email,p.iracing_name,p.discord_username].filter(Boolean).join(' · '),
   button('Hold','prt-app:'+p.id+':hold','btn mini')+button('Decline','prt-app:'+p.id+':declined','btn mini')+
   button('Accept + onboard','prt-app:'+p.id+':accepted','btn mini accent'))).join('')||note('No new applications','The PRT intake queue has no new or held applications.');
 }else if(tab==='feedback'){
  listing=(d.items||[]).filter(p=>String(p.status||'open')!=='resolved').map(p=>row(p.title||p.summary||'Feedback',esc(p.kind||p.type||'Report')+' · '+esc(p.severity||'normal')+' · '+esc(p.status||'open'),p.description||p.notes||p.body||'',
  button('Reviewing','prt-feedback:'+p.id+':reviewing','btn mini')+button('Resolve','prt-feedback:'+p.id+':resolved','btn mini accent'))).join('')||note('No open feedback','No active product feedback was returned.');
 }else if(tab==='testers'){
  listing=(d.invites||[]).slice(0,90).map(p=>row(p.applicant_name||p.tester_name||p.email,esc(p.status)+' · '+esc(p.tester_status||'unknown'),p.iracing_name||p.discord||p.discord_username||'', '')).join('')||note('No testers','No tester invitations returned.');
 }else{
  listing=(d.leaderboard||[]).slice(0,50).map(p=>row('#'+(p.position||'?')+' '+(p.tester_name||p.name||'Racer'),esc(p.qualified||0)+' qualified · '+esc(p.pending||0)+' pending',p.milestone_status||p.referral_code||'', '')).join('')||note('No race records','No founder-race results returned.');
 }
 root.innerHTML=heading('PRT operations','Tester applications, onboarding, bug reports and race activity are now managed here.',refresh())+
 renderTabs('prt',[['applications','Applications'],['feedback','Feedback'],['testers','Testers'],['founders',"Founder’s Race"]])+
 pane('PITMARK RACING TOOLS',tab==='applications'?'Applicant review':tab==='feedback'?'Feedback queue':tab==='testers'?'Tester roster':"Founder's Race",listing)+
 '<p class="workspace-note">Accepting an applicant creates an Early Access invite and sends their onboarding email. Confirm before accepting.</p>';
}
async function mountWork(root,ctx){
 const tab=sections.work;
 const d=await read('/api/control/work?view='+encodeURIComponent(tab),14000,8500);
 const items=d.items||[],selected=selections.work;currentRecords.work=items;
 let editor=selected?pane('MASTER CHECKLIST',selected.task||'Task','<form class="workspace-form" id="work-form">'+
 '<div class="meta">'+esc(selected.area||'')+' · Priority '+esc(selected.priority||'—')+'</div>'+
 '<div class="field"><label for="work-status">Status</label><select id="work-status" class="field-input">'+['Active','Waiting','Monitoring','Blocked','Done'].map(s=>'<option'+(String(selected.status||'').toLowerCase()===s.toLowerCase()?' selected':'')+'>'+s+'</option>').join('')+'</select></div>'+
 '<div class="field"><label for="work-notes">Notes</label><textarea id="work-notes" class="field-area">'+esc(selected.notes||'')+'</textarea></div>'+
 '<div class="actions"><button type="submit" class="btn accent">Save to Master Checklist</button>'+button('Close','work-close','btn mini')+'</div></form>'):null;
 root.innerHTML=heading('Work & priorities','The real Master Checklist, not a second disconnected to-do list.',refresh())+
 '<div class="workspace-toolbar">'+renderTabs('work',[['now','Needs attention'],['active','Active'],['blocked','Blocked'],['waiting','Waiting'],['monitoring','Monitoring'],['today','All open']])+
 '<span class="inline-status">'+esc(d.stale?'Cached (source unavailable)':'Google Sheets synced')+'</span></div>'+
 '<div class="'+(editor?'workspace-pair':'')+'">'+pane('MASTER CHECKLIST',fmt(items.length)+' items shown',
 items.length?items.map(x=>row(x.task||'Task',esc(x.priority||'—')+' · '+esc(x.area||'General')+' · '+esc(x.status||x.bucket),x.next_action||x.notes||'',button('Open / update','work-edit:'+x.row_number,'btn mini'))).join(''):note('Nothing in this work view','No matching tasks were returned.'))+
 (editor||'')+'</div>';
}
async function mountRacing(root){
 const tab=sections.racing;let listing='',subtitle='';
 if(tab==='results'){
  const d=await read('/api/control/results-sweep/status',20000,12000);
  const recent=(d.recent||[]).filter(x=>x.status!=='superseded').slice(0,65);
  listing=recent.map(x=>row(x.title||x.event_name||x.race_name||'Race result',
   esc(x.series||x.status||'Result')+' · '+esc(when(x.created_at||x.updated_at)),
   [x.winner?('Winner: '+x.winner):'',x.notes||x.source_name||''].filter(Boolean).join(' · '),
   x.article_url?'<a href="'+esc(verifiedUrl(x.article_url))+'" target="_blank" rel="noopener noreferrer" class="btn mini">Article ↗</a>':'' )).join('');
  subtitle='Results recorded by the Pitmark coverage system.';
 }else{
  const d=await read('/api/control/standings',45000,14000);
  const list=d.series||[];listing=list.slice(0,60).map(x=>row(x.short_name||x.name||'Racing series',
   esc(x.season||'')+' · '+esc(x.status||x.source_status||'Standings'),(x.entries||[]).slice(0,3).map(v=>v.driver_name||v.name||'').join(' · '),
   '')).join('');subtitle='Series standings from their existing saved source snapshots.';
 }
 root.innerHTML=heading('Race Center & results','Keep your racing coverage and standings in one operator view.',refresh())+
 renderTabs('racing',[['results','Results desk'],['standings','Standings']])+pane('RACING INTELLIGENCE',subtitle,listing||note('No records returned','The source has no records for the selected view.'))+
 '<p class="workspace-note">Coverage and standings are source-backed; items marked incomplete require editorial verification.</p>';
}
function verifiedUrl(raw){try{const u=new URL(raw);return u.protocol==='https:'?u.href:'#';}catch{return '#'}}
async function mountStore(root,ctx){
 const d=await read('/api/control/store/overview',20000,12000);
 const commerce=d.commerce||{},orders=commerce.orders||{},products=commerce.products||{},collections=commerce.collections||{};
 const listings=(products.items||[]).slice(0,35).map(x=>row(x.title||'Product',esc(x.status||'Active')+' · '+esc(x.price||'Price unavailable'),
  x.handle||'', x.handle?'<a href="https://pitmarkracing.com/products/'+encodeURIComponent(x.handle)+'" target="_blank" rel="noopener noreferrer" class="btn mini">View storefront ↗</a>':'')).join('');
 const orderCount=orders.count??orders.total??null;
 root.innerHTML=heading('Store & commerce','One place to inspect your storefront, product catalog and orders.',refresh())+
 '<div class="metrics"><div class="metric"><small>Orders in snapshot</small><strong>'+fmt(orderCount)+'</strong></div>'+
 '<div class="metric"><small>Products</small><strong>'+fmt(products.count)+'</strong></div>'+
 '<div class="metric"><small>Collections</small><strong>'+fmt(collections.count)+'</strong></div>'+
 '<div class="metric"><small>Shopify connection</small><strong style="font-size:19px">'+esc(commerce.connection?.authenticated?'Connected':'Unavailable')+'</strong></div></div>'+
 pane('MERCHANDISE','Current product catalog',listings||note('Products unavailable','Shopify did not return product records for this view.'))+
 '<p class="workspace-note">Commerce totals use Shopify provider responses. Empty or unavailable data is never presented as verified revenue.</p>';
}
async function mountGrowth(root,ctx){
 const d=await read('/api/control/intelligence/overview?days=30',95000,15500),c=d.commerce||{},g=d.growth||{},prt=g.prt||{},sources=d.sources||{};
 const money=c.status==='live'?new Intl.NumberFormat('en-US',{style:'currency',currency:c.currency||'USD'}).format(Number(c.revenue||0)):'—';
 root.innerHTML=heading('Growth & revenue','Actual performance and source confidence, not vanity metrics.',refresh())+
 '<div class="metrics">'+[['Shopify revenue',money],['Orders',c.status==='live'?fmt(c.orders):'—'],['PRT applicants',fmt(prt.applications_total)],['Activated testers',fmt(prt.testers_redeemed)]].map(x=>'<div class="metric"><small>'+esc(x[0])+'</small><strong>'+esc(x[1])+'</strong></div>').join('')+'</div>'+
 '<div class="workspace-pair">'+pane('REPORTING','Connected measurement',Object.entries(sources).map(([name,v])=>row(name.toUpperCase(),esc(v.status||'unavailable'),v.error||v.note||'', '')).join('')||note('Sources unavailable','No provider data returned.'))+
 pane('RECOMMENDATIONS','Where to focus',(d.recommendations||[]).map(x=>row(x.title,esc(x.priority||'recommendation'),x.reason||'', '')).join('')||note('No recommendations','The operating intelligence system returned no new actions.'))+'</div>'+
 '<p class="workspace-note">Window: last 30 days. Generated '+esc(when(d.generated_at))+'. Dashboards never substitute zero for disconnected providers.</p>';
}
async function mountSystems(root,ctx){
 let notifications=null,error=null;
 try{notifications=await read('/api/control/notifications',12000,9000);}catch(e){error=e;}
 const alive=ctx.core?.status==='live';
 const rows=(notifications?.items||[]).filter(x=>x.status==='unread').slice(0,35).map(x=>row(x.title||'Operational signal',esc(x.priority||'info')+' · '+esc(x.module||'Pitmark'),x.detail||x.reason||'', '')).join('');
 root.innerHTML=heading('Systems','Source health, operational notifications and real failure states.',refresh())+
 '<div class="workspace-pair">'+pane('RUNTIME','Cloud health',row('Pitmark Cloud',esc(alive?'Operations connected':'Operational status unavailable'),alive?'Owner HQ read source responded.':'The owner HQ data source could not respond.', ''))+
 pane('NOTIFICATIONS','Needs investigation',rows||note('No unread notifications',error?'Notifications unavailable: '+error.message:'Nothing currently unread.'))+'</div><p class="workspace-note">Security systems continue behind the scenes. This view does not expose Shield or other sensitive security-event details.</p>';
}
export const WORKSPACE_VIEWS=new Set(['inbox','mail','content','relationships','prt','work','racing','store','growth','systems']);
export async function mountWorkspace(view,root,ctx={},force=false){
 const sequence=++active;if(force)invalidate();root.innerHTML=heading(view==='mail'?'Mail & features':view.replaceAll('-',' '),'Loading the source for this workspace…')+'<div class="loading-note">Loading '+esc(view)+' without blocking other sections</div>';
 try{
  const fn={inbox:mountInbox,mail:mountMail,content:mountContent,relationships:mountRelationships,prt:mountPRT,work:mountWork,racing:mountRacing,store:mountStore,growth:mountGrowth,systems:mountSystems}[view];
  if(!fn)return;
  // Build into a detached node: a late request must never repaint a newly selected tab.
  const holder=document.createElement('div');
  await fn(holder,ctx);
  if(sequence!==active||!root.isConnected||location.hash.slice(1)!==view)return;
  root.innerHTML=holder.innerHTML;
  root.onclick=(event)=>{const b=event.target.closest('[data-action]');if(b)handleAction(b.dataset.action,root,ctx);};
  root.onsubmit=(event)=>{event.preventDefault();handleSubmit(event.target,root,ctx);};
 }catch(e){
  if(sequence!==active||!root.isConnected)return;
  root.innerHTML=heading(view.toUpperCase(),'The rest of Control Center remains available.')+errorBox(e)+button('Try again','refresh','btn accent');
  root.onclick=(e)=>{if(e.target.closest('[data-action="refresh"]'))mountWorkspace(view,root,ctx,true)};
 }
}
async function handleAction(action,root,ctx){
 if(busyMutation)return;
 const args=action.split(':'),type=args[0],view=location.hash.slice(1);
 if(type==='refresh')return mountWorkspace(view,root,ctx,true);
 if(type==='tab'){sections[args[1]]=args[2];pagination[args[1]]=0;if(args[1]==='content')selections.post=null;if(args[1]==='mail')selections.mail=null;return mountWorkspace(args[1],root,ctx);}
 if(type==='navigate'){const target=args[1]||'#inbox';const id=args[2]||'';if(id.startsWith('post')){sections.content='attention';selections.post=null;}if(id.startsWith('contact')){sections.relationships='all';selections.contact=null;}location.hash=target;return;}
 if(type==='page'){const key=args[1];const prev=args[2]==='prev';pagination[key]=Math.max(0,pagination[key]+(prev?-35:35));return mountWorkspace(view,root,ctx);}
 if(type==='mail-compose'){selections.mail={type:'compose'};return mountWorkspace('mail',root,ctx);}
 if(type==='mail-cancel'){selections.mail=null;return mountWorkspace('mail',root,ctx);}
 if(type==='mail-reply'){
   const all=selections.mail?.thread?.messages||[],incoming=[...all].reverse().find(m=>m.direction==='inbound');
   const t=selections.mail?.thread?.thread||{};
   if(!incoming)return alert('No inbound message is available for a reply.');
   selections.mail={type:'compose',to:incoming.from,subject:/^re:/i.test(t.subject||'')?t.subject:'Re: '+(t.subject||''),reply_id:incoming.id};
   return mountWorkspace('mail',root,ctx);
 }
 if(type==='mail-open'){
   try{const d=await request('/api/control/email/threads/'+encodeURIComponent(args[1]));selections.mail={thread:d};invalidate('/api/control/email/threads?');return mountWorkspace('mail',root,ctx);}
   catch(e){return alert(e.message);}
 }
 if(type==='mail-draft')return sendOrDraft(false,root,ctx);
 if(type==='post-close'){selections.post=null;return mountWorkspace(view,root,ctx);}
 if(type==='post-new'){selections.post={id:null,platform:'facebook',title:'',body:'',status:'pending'};return mountWorkspace('content',root,ctx);}
 if(type==='post-edit'){
   selections.post=(currentRecords.content||[]).find(p=>String(p.id)===args[1])||null;
   if(!selections.post)return alert('This post is not in the current page. Search or switch to the matching status.');
   return mountWorkspace('content',root,ctx);
 }
 if(type==='contact-new'){selections.contact={id:null,stage:'prospect',contact_type:'track'};return mountWorkspace('relationships',root,ctx);}
 if(type==='contact-close'){selections.contact=null;return mountWorkspace('relationships',root,ctx);}
 if(type==='contact-edit'){
   selections.contact=(currentRecords.relationships||[]).find(p=>String(p.id)===args[1])||null;return mountWorkspace('relationships',root,ctx);
 }
 if(type==='work-close'){selections.work=null;return mountWorkspace('work',root,ctx);}
 if(type==='work-edit'){
   selections.work=(currentRecords.work||[]).find(p=>String(p.row_number)===args[1])||null;return mountWorkspace('work',root,ctx);
 }
 const changes={
  'post-approve':['/api/control/autopilot/posts/'+args[1]+'/decision','POST',{action:'approve'},'Approve this post?'],
  'post-reject':['/api/control/autopilot/posts/'+args[1]+'/decision','POST',{action:'reject'},'Reject this post?'],
  'article-approve':['/api/control/blog/drafts/'+args[1]+'/decision','POST',{action:'approve'},'Approve this article draft? This does not publish to Shopify.'],
  'article-archive':['/api/control/blog/drafts/'+args[1]+'/decision','POST',{action:'archive'},'Archive this article draft?'],
 };
 if(type==='prt-app'){const s=args[2];changes[type]=['/api/control/ops/testers/'+args[1]+'/status','PATCH',{status:s},s==='accepted'?'Accept this person, create their invite, and send the onboarding email?':'Change applicant status to '+s+'?'];}
 if(type==='prt-feedback'){changes[type]=['/api/control/ops/feedback/'+args[1]+'/status','PATCH',{status:args[2]},'Change feedback status to '+args[2]+'?'];}
 const task=changes[type];
 if(task){if(!confirm(task[3]))return;busyMutation=true;try{await write(task[0],task[1],task[2]);invalidate();if(type.startsWith('post')&&typeof ctx.refreshCore==='function')ctx.refreshCore();mountWorkspace(view,root,ctx,true);}catch(e){alert(e.message)}finally{busyMutation=false;}return;}
}
async function handleSubmit(form,root,ctx){
 if(busyMutation)return;
 const id=form.id;
 if(id==='mail-form')return sendOrDraft(true,root,ctx);
 if(id==='relationship-search'){
  searchValue=String(document.getElementById('relationship-query')?.value||'').trim();pagination.relationships=0;return mountWorkspace('relationships',root,ctx,true);
 }
 if(id==='contact-form'){
  const p=selections.contact;const payload={
   name:document.getElementById('contact-name').value.trim(),
   organization:document.getElementById('contact-org').value.trim(),
   email:document.getElementById('contact-email').value.trim(),
   contact_type:document.getElementById('contact-type').value.trim(),
   stage:document.getElementById('contact-stage').value.trim(),
   next_follow_up:document.getElementById('contact-follow').value||'',
   notes:document.getElementById('contact-notes').value
  };
  if(!payload.name)return alert('Contact name required.');
  busyMutation=true;try{await write(p.id===null?'/api/control/outreach':'/api/control/outreach/'+p.id,p.id===null?'POST':'PATCH',payload);selections.contact=null;invalidate();mountWorkspace('relationships',root,ctx,true);if(ctx.refreshCore)ctx.refreshCore();}catch(e){alert(e.message)}finally{busyMutation=false;}return;
 }
 if(id==='post-form'){
  const p=selections.post;const payload={title:document.getElementById('post-title').value,body:document.getElementById('post-body').value};
  if(!payload.body.trim())return alert('Post copy is required.');
  if(p.id===null){payload.platform=document.getElementById('post-platform').value;payload.content_type='community';payload.source='manual';payload.risk='medium';}
  busyMutation=true;try{await write(p.id===null?'/api/control/autopilot/posts':'/api/control/autopilot/posts/'+p.id,p.id===null?'POST':'PATCH',payload);selections.post=null;invalidate();sections.content='pending';mountWorkspace('content',root,ctx,true);if(ctx.refreshCore)ctx.refreshCore();}catch(e){alert(e.message)}finally{busyMutation=false;}return;
 }
 if(id==='work-form'){
  const p=selections.work;busyMutation=true;
  try{await write('/api/control/work/'+p.row_number,'PATCH',{status:document.getElementById('work-status').value,notes:document.getElementById('work-notes').value});selections.work=null;invalidate();mountWorkspace('work',root,ctx,true);if(ctx.refreshCore)ctx.refreshCore();}catch(e){alert(e.message)}finally{busyMutation=false;}
 }
}
async function sendOrDraft(send,root,ctx){
 const selected=selections.mail||{},to=document.getElementById('mail-to')?.value.trim()||'',subject=document.getElementById('mail-subject')?.value.trim()||'',text=document.getElementById('mail-body')?.value||'';
 if(!to||!subject||!text.trim()||! /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to))return alert('A valid recipient, subject, and message are required.');
 if(send&&!confirm('Send this email to '+to+' now?'))return;
 busyMutation=true;
 try{await write(send?'/api/control/email/send':'/api/control/email/drafts','POST',{
  to:[to],cc:[],bcc:[],from_identity:'',subject,text,html:'',...(send&&selected.reply_id?{reply_to_message_id:selected.reply_id}:{})
 });selections.mail=null;invalidate();mountWorkspace('mail',root,ctx,true);alert(send?'Email sent.':'Draft saved.');}
 catch(e){alert(e.message)}finally{busyMutation=false;}
}
