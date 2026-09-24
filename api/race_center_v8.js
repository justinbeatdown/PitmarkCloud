(function(){
'use strict';
var view=String(document.body.dataset.view||'hub');
var $=function(s,r){return (r||document).querySelector(s);};
var $$=function(s,r){return Array.from((r||document).querySelectorAll(s));};
var esc=function(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};

function json(url){
  return fetch(url,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}}).then(function(r){
    if(!r.ok)throw new Error('Race Center data unavailable');
    return r.json();
  });
}
function graph(){
  if(window.__pitmarkRaceGraphData)return Promise.resolve(window.__pitmarkRaceGraphData);
  if(window.__pitmarkRaceGraphPromise)return window.__pitmarkRaceGraphPromise;
  window.__pitmarkRaceGraphPromise=json('/api/public/race-center/graph?v=v8').then(function(d){window.__pitmarkRaceGraphData=d;return d;}).finally(function(){delete window.__pitmarkRaceGraphPromise;});
  return window.__pitmarkRaceGraphPromise;
}
function stories(){
  if(window.__pitmarkRaceStoriesData)return Promise.resolve(window.__pitmarkRaceStoriesData);
  if(window.__pitmarkRaceStoriesPromise)return window.__pitmarkRaceStoriesPromise;
  window.__pitmarkRaceStoriesPromise=json('/api/public/race-center/stories?limit=18').then(function(d){window.__pitmarkRaceStoriesData=d;return d;}).finally(function(){delete window.__pitmarkRaceStoriesPromise;});
  return window.__pitmarkRaceStoriesPromise;
}
function prefs(){try{return JSON.parse(localStorage.getItem('pitmark-race-center-consumer-v1')||'{}')||{};}catch(_e){return {};}}
function dateLabel(v){var d=new Date(v||'');return Number.isNaN(d.getTime())?'':new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',year:'numeric'}).format(d);}
function eventLabel(v){var d=new Date(v||'');return Number.isNaN(d.getTime())?'':new Intl.DateTimeFormat(undefined,{weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(d);}
function imageUrl(v,w){
  var raw=String(v||'').trim(); if(!raw)return '';
  try{var u=new URL(raw,location.origin);if(u.hostname==='cdn.shopify.com'||(u.hostname.endsWith('pitmarkracing.com')&&u.pathname.indexOf('/cdn/shop/')>=0)){if(!u.searchParams.has('width'))u.searchParams.set('width',String(w||900));return u.toString();}}catch(_e){}
  return raw;
}
function media(url,title,hero){
  var src=imageUrl(url,900);
  if(!src)return '<span class="v8-media v8-media-fallback"><b>RACE</b><i>CENTER</i></span>';
  return '<span class="v8-media"><img src="'+esc(src)+'" alt="'+esc(title||'')+'" width="900" height="506" loading="'+(hero?'eager':'lazy')+'" decoding="async" fetchpriority="'+(hero?'high':'low')+'"><span class="v8-media-shade"></span></span>';
}
function isGrassroots(x){
  if(!x)return false;if(x.grassroots)return true;
  var p=x.provenance||{}, names=Array.isArray(p.source_names)?p.source_names.join(' '):'';
  var h=[x.group,x.series_name,x.name,names].filter(Boolean).join(' ').toLowerCase();
  return /grassroots|local|regional|dirt|sprint|late model|modified|midget|short track|imca|dirtcar|usac/.test(h);
}
function regionTokens(){
  var raw=String(prefs().region||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();if(!raw)return [];
  var a={pa:'pennsylvania',oh:'ohio',wv:'west virginia',ny:'new york',md:'maryland',va:'virginia',nj:'new jersey'},out=[raw];
  raw.split(/\s+/).filter(function(t){return t.length>1;}).forEach(function(t){out.push(t);if(a[t])out.push(a[t]);});
  return Array.from(new Set(out));
}
function regionMatch(x){
  var t=regionTokens();if(!t.length)return false;
  var h=[x&&x.name,x&&x.location,x&&x.venue,x&&x.series_name,x&&x.summary,x&&x.title].filter(Boolean).join(' ').toLowerCase();
  return t.some(function(v){return h.indexOf(v)>=0;});
}
function compact(k,t,m,h){
  return '<a class="v8-compact-row" href="'+esc(h||'#')+'"><span>'+esc(k)+'</span><div><strong>'+esc(t||'Racing')+'</strong><small>'+esc(m||'')+'</small></div><b>→</b></a>';
}
function storyCard(s,i){
  return '<a class="v8-story-card" href="/race-center/story/'+encodeURIComponent(String(s.key||''))+'">'+media(s.image_url,s.title,i===0)+'<span class="v8-story-copy"><span class="eyebrow">RACING CULTURE</span><strong>'+esc(s.title||'Pitmark Racing Culture')+'</strong><p>'+esc(s.summary||'Original Pitmark racing coverage and culture.')+'</p><small>'+esc(dateLabel(s.published_at))+'</small><b>Read in Race Center →</b></span></a>';
}
function ensureHome(){
  if(view!=='hub'||$('#v8Culture'))return;
  var anchor=$('#v7RaceDay')||$('#hubNavigation');if(!anchor)return;
  var w=document.createElement('div');w.className='v8-home-expansion';
  w.innerHTML='<section class="v8-culture content-section" id="v8Culture"><div class="section-head"><div><span class="eyebrow">PITMARK RACING CULTURE</span><h2>Stories inside Race Center</h2></div><a class="section-link" href="https://pitmarkracing.com/blogs/racing-culture">All coverage ↗</a></div><div class="v8-story-grid" id="v8StoryGrid"><div class="loading-card">Loading Pitmark stories…</div></div></section>'+
  '<section class="v8-grassroots content-section" id="v8Grassroots"><div class="section-head"><div><span class="eyebrow">LOCAL + GRASSROOTS</span><h2>More than one little local card</h2></div><a class="section-link" href="/race-center/tracks">Explore tracks →</a></div><div class="v8-grassroots-columns"><div><header><strong>Upcoming</strong><span>Race nights and events</span></header><div id="v8GrassrootsEvents"></div></div><div><header><strong>Tracks</strong><span>Places worth following</span></header><div id="v8GrassrootsTracks"></div></div><div><header><strong>Drivers</strong><span>People in the scene</span></header><div id="v8GrassrootsDrivers"></div></div></div></section>';
  anchor.parentNode.insertBefore(w,anchor);
}
function renderStories(){
  var h=$('#v8StoryGrid');if(!h)return;
  stories().then(function(d){var rows=(d.stories||[]).slice(0,6);h.innerHTML=rows.length?rows.map(storyCard).join(''):'<div class="v8-empty"><strong>Stories are refreshing.</strong><span>Race Center will pull Racing Culture back in automatically.</span></div>';}).catch(function(){h.innerHTML='<div class="v8-empty"><strong>Stories are refreshing.</strong></div>';});
}
function renderGrassroots(){
  var e=$('#v8GrassrootsEvents'),t=$('#v8GrassrootsTracks'),d=$('#v8GrassrootsDrivers');if(!e||!t||!d)return;
  graph().then(function(g){
    var tracks=(g.tracks||[]).filter(isGrassroots), keys=new Set(tracks.map(function(x){return String(x.key||'');}));
    var events=(g.events||[]).filter(function(x){return isGrassroots(x)||keys.has(String(x.track_key||''));}).filter(function(x){var w=new Date(x.start||'');return Number.isNaN(w.getTime())||w.getTime()>=Date.now()-10800000;}).sort(function(a,b){return String(a.start||'').localeCompare(String(b.start||''));});
    var drivers=(g.drivers||[]).filter(isGrassroots);
    var re=events.filter(regionMatch),rt=tracks.filter(regionMatch),rd=drivers.filter(regionMatch);
    events=(re.length?re:events).slice(0,5);tracks=(rt.length?rt:tracks).slice(0,5);drivers=(rd.length?rd:drivers).slice(0,5);
    e.innerHTML=events.length?events.map(function(x){return compact('UPCOMING',x.name||x.series_name,[eventLabel(x.start),x.venue||x.location,x.series_name].filter(Boolean).join(' · '),'/race-center/event/'+encodeURIComponent(String(x.key||'')));}).join(''):'<div class="v8-mini-empty">Upcoming grassroots events are still filling in.</div>';
    t.innerHTML=tracks.length?tracks.map(function(x){return compact('TRACK',x.name,x.location||'Grassroots racing venue','/race-center/track/'+encodeURIComponent(String(x.key||'')));}).join(''):'<div class="v8-mini-empty">Track discovery is still filling in.</div>';
    d.innerHTML=drivers.length?drivers.map(function(x){var s=(x.series&&x.series[0]&&x.series[0].series_key)||(x.grassroots?'grassroots':'');return compact('DRIVER',(x.number?'#'+x.number+' · ':'')+(x.name||'Driver'),[x.team,(x.series&&x.series[0]&&x.series[0].series_name)].filter(Boolean).join(' · '),'/race-center/driver/'+encodeURIComponent(String(s||''))+'/'+encodeURIComponent(String(x.name||'')));}).join(''):'<div class="v8-mini-empty">Grassroots driver profiles are still filling in.</div>';
  }).catch(function(){[e,t,d].forEach(function(h){h.innerHTML='<div class="v8-mini-empty">Race Center data is refreshing.</div>';});});
}
function patchLocal(){
  var h=$('#consumerLocalGrid');if(!h)return;
  Promise.all([graph(),stories().catch(function(){return {stories:[]};})]).then(function(v){
    if(h.querySelectorAll('.consumer-card').length>=5)return;
    var g=v[0]||{},s=v[1]||{},add=[];
    (g.events||[]).filter(isGrassroots).slice(0,2).forEach(function(x){add.push('<a class="consumer-card" href="/race-center/event/'+encodeURIComponent(String(x.key||''))+'"><span class="consumer-media consumer-media-fallback"><b>UP</b><i>NEXT</i></span><span class="consumer-card-copy"><span class="consumer-kicker">GRASSROOTS EVENT</span><strong>'+esc(x.name||x.series_name)+'</strong><p>'+esc([eventLabel(x.start),x.venue||x.location].filter(Boolean).join(' · '))+'</p><b>Open →</b></span></a>');});
    var rs=(s.stories||[]).filter(regionMatch);(rs.length?rs:(s.stories||[])).slice(0,2).forEach(function(x){add.push('<a class="consumer-card has-media" href="/race-center/story/'+encodeURIComponent(String(x.key||''))+'">'+media(x.image_url,x.title,false)+'<span class="consumer-card-copy"><span class="consumer-kicker">RACING CULTURE</span><strong>'+esc(x.title)+'</strong><p>'+esc(x.summary||'Pitmark Racing Culture')+'</p><b>Read →</b></span></a>');});
    if(add.length)h.insertAdjacentHTML('beforeend',add.join(''));
  }).catch(function(){});
}
function youtube(url){
  try{var u=new URL(String(url||''),location.origin),id='';if(u.hostname.indexOf('youtu.be')>=0)id=u.pathname.split('/').filter(Boolean)[0]||'';if(u.hostname.indexOf('youtube.com')>=0||u.hostname.indexOf('youtube-nocookie.com')>=0){id=u.searchParams.get('v')||'';var p=u.pathname.split('/').filter(Boolean),i=p.indexOf('live');if(!id&&i>=0)id=p[i+1]||'';i=p.indexOf('embed');if(!id&&i>=0)id=p[i+1]||'';}return id?'https://www.youtube-nocookie.com/embed/'+encodeURIComponent(id):'';}catch(_e){return '';}
}
function stage(x,live){
  if(!x)return '<div class="v8-live-stage-empty"><span class="eyebrow">LIVE + NEXT</span><strong>No tracked event is live right now.</strong><p>Upcoming racing stays visible instead of leaving dead space.</p></div>';
  var watch=x.watch_url||x.broadcast_url||x.event_url||'',embed=live?youtube(watch):'',m=embed?'<div class="v8-live-video"><iframe src="'+esc(embed)+'" title="'+esc(x.name||'Live race')+'" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe></div>':'<div class="v8-live-placeholder"><span>'+(live?'LIVE EVENT':'UP NEXT')+'</span><strong>'+esc(x.name||x.series_name||'Race event')+'</strong><p>'+esc([eventLabel(x.start),x.venue||x.location,x.series_name].filter(Boolean).join(' · '))+'</p>'+(watch?'<a class="button primary" href="'+esc(watch)+'" target="_blank" rel="noopener">Open official stream ↗</a>':'')+'</div>';
  return '<div class="v8-live-stage-shell">'+m+'<aside><span class="eyebrow">'+(live?'LIVE NOW':'NEXT BROADCAST')+'</span><h2>'+esc(x.name||x.series_name||'Race event')+'</h2><p>'+esc([x.series_name,x.venue||x.location,eventLabel(x.start)].filter(Boolean).join(' · '))+'</p><a class="button" href="/race-center/event/'+encodeURIComponent(String(x.key||''))+'">Open event hub</a></aside></div>';
}
function renderLive(){
  if(view!=='live')return;var main=$('main');if(!main||$('#v8LiveStage'))return;
  var s=document.createElement('section');s.className='v8-live-stage content-section';s.id='v8LiveStage';s.innerHTML='<div class="loading-card">Building the live stage…</div>';main.insertBefore(s,main.firstElementChild);
  graph().then(function(g){var ev=(g.events||[]).slice(),live=ev.find(function(x){return String(x.state||'').toLowerCase()==='live';}),next=ev.filter(function(x){var w=new Date(x.start||'');return !Number.isNaN(w.getTime())&&w.getTime()>=Date.now()-7200000;}).sort(function(a,b){return new Date(a.start||0)-new Date(b.start||0);})[0];s.innerHTML=stage(live||next,Boolean(live));}).catch(function(){s.innerHTML=stage(null,false);});
}
function storyPage(){
  if(view!=='story')return;var main=$('main'),key=decodeURIComponent(location.pathname.split('/').filter(Boolean).pop()||'');if(!main)return;
  var p=document.createElement('section');p.className='v8-story-page content-section';p.id='v8StoryPage';p.innerHTML='<div class="loading-card">Loading Pitmark Racing Culture…</div>';main.appendChild(p);
  json('/api/public/race-center/story/'+encodeURIComponent(key)).then(function(x){document.title=(x.title||'Racing Culture')+' — Pitmark Race Center';p.innerHTML='<a class="v8-back-link" href="/race-center">← Back to Race Center</a><article class="v8-native-story"><header><span class="eyebrow">PITMARK RACING CULTURE</span><h1>'+esc(x.title||'Pitmark Racing Culture')+'</h1><div><span>'+esc(dateLabel(x.published_at))+'</span><span>'+esc(x.author||'Pitmark Racing Co.')+'</span></div></header>'+(x.image_url?media(x.image_url,x.title,true):'')+'<div class="v8-native-story-body">'+String(x.content_html||'<p>'+esc(x.summary||'')+'</p>')+'</div><footer><a class="button" href="'+esc(x.url||x.source_url||'#')+'" target="_blank" rel="noopener">Original article ↗</a><a class="button primary" href="/race-center">Keep exploring</a></footer></article>';}).catch(function(){p.innerHTML='<div class="v8-empty"><strong>This story could not be loaded.</strong><a class="button" href="/race-center">Back to Race Center</a></div>';});
}
function images(){
  $$('img').forEach(function(img,i){if(img.dataset.v8img)return;img.dataset.v8img='1';img.decoding='async';if(i<4&&img.getBoundingClientRect().top<innerHeight*1.5){img.loading='eager';try{img.fetchPriority='high';}catch(_e){}}else img.loading='lazy';img.addEventListener('error',function(){img.classList.add('v8-image-failed');});});
}
function init(){
  document.body.classList.add('race-center-v8');ensureHome();
  if(view==='hub'){renderStories();renderGrassroots();setTimeout(patchLocal,800);}
  renderLive();storyPage();setTimeout(images,250);setTimeout(images,1400);
  new MutationObserver(images).observe(document.body,{childList:true,subtree:true});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();