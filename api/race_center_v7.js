(function(){
  'use strict';
  window.RACE_CENTER_V7=true;

  const $=(selector,root=document)=>(root||document).querySelector(selector);
  const $$=(selector,root=document)=>Array.from((root||document).querySelectorAll(selector));
  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const view=String(document.body.dataset.view||'hub');

  let graphCache=null;
  let graphPromise=null;

  async function getJson(url,options={}){
    const response=await fetch(url,{credentials:'same-origin',cache:'no-store',...options});
    if(!response.ok){
      let message='Race Center request failed.';
      try{const body=await response.json();message=body.detail||body.message||message;}catch(_e){}
      throw new Error(message);
    }
    return response.json();
  }

  function graph(){
    if(graphCache)return Promise.resolve(graphCache);
    if(graphPromise)return graphPromise;
    graphPromise=getJson('/api/public/race-center/graph?v=7')
      .then(data=>{graphCache=data;return data;})
      .finally(()=>{graphPromise=null;});
    return graphPromise;
  }

  function normalize(value){
    return String(value||'').toLowerCase().replace(/[^a-z0-9]+/g,'');
  }

  function hrefFor(type,item){
    const key=encodeURIComponent(String(item.key||''));
    if(type==='track')return '/race-center/track/'+key;
    if(type==='team')return '/race-center/team/'+key;
    if(type==='event')return '/race-center/event/'+key;
    if(type==='series')return '/race-center/series/'+key;
    if(type==='driver'){
      const series=(item.series&&item.series[0]&&item.series[0].series_key)||'';
      return '/race-center/driver/'+encodeURIComponent(series)+'/'+encodeURIComponent(String(item.name||''));
    }
    return '/race-center';
  }

  function setActiveNav(){
    const map={tracks:'tracks',trackprofile:'tracks',events:'events',eventprofile:'events',teams:'teams',teamprofile:'teams'};
    const active=map[view];
    if(!active)return;
    $$('.site-header nav a').forEach(a=>{
      const href=String(a.getAttribute('href')||'');
      const match=href==='/race-center/'+active;
      a.classList.toggle('active',match);
      if(match)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');
    });
  }

  function entityRouteKey(kind){
    const marker='/race-center/'+kind+'/';
    const path=decodeURI(location.pathname);
    const index=path.indexOf(marker);
    return index>=0?decodeURIComponent(path.slice(index+marker.length)):'';
  }

  function eventWhen(start){
    if(!start)return 'Date from official schedule';
    const date=new Date(start);
    if(Number.isNaN(date.getTime()))return String(start);
    return new Intl.DateTimeFormat(undefined,{weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(date);
  }

  function eventCountdown(start,state){
    if(state==='live')return 'LIVE NOW';
    if(state==='recent')return 'COMPLETE';
    const date=new Date(start||'');
    if(Number.isNaN(date.getTime()))return 'TIME TBA';
    const diff=date.getTime()-Date.now();
    if(diff<=0)return 'STARTING / STATUS PENDING';
    const minutes=Math.floor(diff/60000);
    const days=Math.floor(minutes/1440);
    const hours=Math.floor((minutes%1440)/60);
    const mins=minutes%60;
    if(days>0)return 'GREEN IN '+days+'D '+hours+'H';
    if(hours>0)return 'GREEN IN '+hours+'H '+mins+'M';
    return 'GREEN IN '+Math.max(1,mins)+'M';
  }

  function eventRows(items,empty){
    const rows=Array.isArray(items)?items:[];
    if(!rows.length)return '<p>'+esc(empty||'Not yet published by the connected source.')+'</p>';
    return '<div class="v7-event-data-list">'+rows.slice(0,40).map((row,index)=>{
      if(row===null||row===undefined)return '';
      if(typeof row!=='object')return '<div><strong>'+esc(String(row))+'</strong></div>';
      const title=row.name||row.driver||row.title||row.label||row.class||row.session||('Entry '+(index+1));
      const detail=[row.number?('#'+row.number):'',row.team,row.position?('P'+row.position):'',row.time,row.status].filter(Boolean).join(' · ');
      return '<div><strong>'+esc(title)+'</strong><span>'+esc(detail)+'</span></div>';
    }).join('')+'</div>';
  }

  function directoryConfig(){
    if(view==='tracks')return {
      type:'track',collection:'tracks',eyebrow:'TRACK DIRECTORY',title:'Every track in the graph',
      intro:'Venues connected to Race Center events and the series that race there.',
      placeholder:'Search track or location…'
    };
    if(view==='teams')return {
      type:'team',collection:'teams',eyebrow:'TEAM DIRECTORY',title:'Teams across racing',
      intro:'Drivers, manufacturers and championships connected in one place.',
      placeholder:'Search team or manufacturer…'
    };
    if(view==='events')return {
      type:'event',collection:'events',eyebrow:'EVENT HUBS',title:'Race day starts here',
      intro:'Upcoming and live events connected to tracks, series, watch information and championship context.',
      placeholder:'Search event, track or series…'
    };
    return null;
  }

  function entityCard(type,item){
    if(type==='track'){
      return '<a class="v7-entity-card" href="'+esc(hrefFor(type,item))+'">'+
        '<span class="v7-card-kicker">TRACK</span>'+
        '<h3>'+esc(item.name||'Track')+'</h3>'+
        '<p>'+esc(item.location||'Location from official event source')+'</p>'+
        '<div class="v7-card-meta"><span>'+Number((item.series||[]).length)+' series</span><span>'+Number((item.events||[]).length)+' events</span></div>'+
        '<strong>Open track →</strong></a>';
    }
    if(type==='team'){
      return '<a class="v7-entity-card" href="'+esc(hrefFor(type,item))+'">'+
        '<span class="v7-card-kicker">TEAM</span>'+
        '<h3>'+esc(item.name||'Team')+'</h3>'+
        '<p>'+esc(item.manufacturer||'Manufacturer varies / not published')+'</p>'+
        '<div class="v7-card-meta"><span>'+Number((item.drivers||[]).length)+' drivers</span><span>'+Number((item.series||[]).length)+' series</span></div>'+
        '<strong>Open team →</strong></a>';
    }
    const state=String(item.state||'schedule').toUpperCase();
    return '<a class="v7-entity-card v7-event-card '+esc(String(item.state||''))+'" href="'+esc(hrefFor(type,item))+'">'+
      '<span class="v7-card-kicker">'+esc(state)+'</span>'+
      '<h3>'+esc(item.name||'Race event')+'</h3>'+
      '<p>'+esc([item.series_name,item.venue,item.location].filter(Boolean).join(' · ')||'Official event details')+'</p>'+
      '<div class="v7-card-meta"><span>'+esc(eventWhen(item.start))+'</span></div>'+
      '<strong>Open event hub →</strong></a>';
  }

  async function renderDirectory(){
    const cfg=directoryConfig();
    const host=$('#v7EntityDirectory');
    if(!cfg||!host)return;
    host.style.display='block';
    $('#v7DirectoryEyebrow').textContent=cfg.eyebrow;
    $('#v7DirectoryTitle').textContent=cfg.title;
    $('#v7DirectoryIntro').textContent=cfg.intro;
    $('#v7DirectorySearch').placeholder=cfg.placeholder;

    const data=await graph();
    const all=Array.isArray(data[cfg.collection])?data[cfg.collection]:[];
    const grid=$('#v7EntityGrid');
    const count=$('#v7DirectoryCount');
    const meta=$('#v7DirectoryMeta');

    const draw=()=>{
      const q=String($('#v7DirectorySearch').value||'').trim().toLowerCase();
      const rows=!q?all:all.filter(item=>JSON.stringify(item).toLowerCase().includes(q));
      count.textContent=rows.length+' '+cfg.collection;
      meta.textContent=cfg.type==='event'?'Each event connects the race to its series, track and watch information.':'Built from source-backed Race Center relationships.';
      grid.innerHTML=rows.length?rows.map(item=>entityCard(cfg.type,item)).join(''):'<div class="loading-card">No matches in the current Race Center graph.</div>';
    };
    $('#v7DirectorySearch').addEventListener('input',draw);
    draw();
  }

  function followButton(type,item){
    if(!['track','team'].includes(type))return '';
    return '<button class="button primary v7-follow-entity" type="button" data-kind="'+esc(type)+'" data-key="'+esc(item.key)+'" data-label="'+esc(item.name)+'">☆ Follow '+esc(type)+'</button>';
  }

  function shareButton(title){
    return '<button class="button v7-share-page" type="button" data-share-title="'+esc(title||'Pitmark Race Center')+'">Share ↗</button>';
  }

  async function shareCurrentPage(title){
    const payload={title:String(title||document.title||'Pitmark Race Center'),url:location.href};
    try{
      if(navigator.share){
        await navigator.share(payload);
        return;
      }
      await navigator.clipboard.writeText(payload.url);
      const notice=document.createElement('div');
      notice.className='v7-copy-toast';
      notice.textContent='Race Center link copied';
      document.body.appendChild(notice);
      setTimeout(()=>notice.remove(),1800);
    }catch(_error){}
  }

  function claimButton(type,item){
    if(!['track','team','series','driver'].includes(type))return '';
    return '<button class="button v7-claim-entity" type="button" data-kind="'+esc(type)+'" data-key="'+esc(item.key)+'" data-label="'+esc(item.name||item.series_name||'Racing entity')+'">Claim this '+esc(type)+'</button>';
  }

  function ownerContentBlock(item){
    const owner=item&&item.owner_content;
    const verification=item&&item.verification;
    if(!owner&&!verification?.claimed)return '';
    const links=[];
    if(owner?.website_url)links.push('<a href="'+esc(owner.website_url)+'" target="_blank" rel="noopener">Official website ↗</a>');
    if(owner?.shop_url)links.push('<a href="'+esc(owner.shop_url)+'" target="_blank" rel="noopener">Shop ↗</a>');
    if(owner?.contact_url)links.push('<a href="'+esc(owner.contact_url)+'" target="_blank" rel="noopener">Contact ↗</a>');
    return '<section class="v7-profile-section v7-owner-content">'+
      '<div class="v7-owner-head"><span class="eyebrow">VERIFIED PROFILE CONTENT</span>'+(verification?.verified?'<span class="v7-verified-badge">✓ VERIFIED OWNER</span>':'')+'</div>'+
      '<h3>From the people behind this '+esc(item.type||'racing profile')+'</h3>'+
      (owner?.bio?'<p>'+esc(owner.bio)+'</p>':'')+
      (owner?.sponsors?.length?'<div class="v7-sponsor-list">'+owner.sponsors.map(x=>'<span>'+esc(x)+'</span>').join('')+'</div>':'')+
      (links.length?'<div class="v7-owner-links">'+links.join('')+'</div>':'')+
    '</section>';
  }

  function editorialBlock(items){
    if(!items||!items.length)return '';
    return '<section class="v7-profile-section"><span class="eyebrow">PITMARK COVERAGE</span><h3>Stories connected to this page</h3><div class="v7-editorial-list">'+items.map(x=>
      '<a href="'+esc(x.url)+'" target="_blank" rel="noopener"><strong>'+esc(x.title)+'</strong><span>'+esc(x.summary||'Open Pitmark coverage')+'</span></a>'
    ).join('')+'</div></section>';
  }

  function trackProfile(item){
    const events=(item.events||[]).slice(0,12);
    const drivers=(item.related_drivers||[]).slice(0,12);
    const facts=[
      ['TYPE',item.track_type],
      ['SURFACE',item.surface],
      ['LENGTH',item.length],
      ['CONFIG',item.configuration]
    ].filter(row=>row[1]);
    const sources=(item.provenance&&item.provenance.source_urls)||item.source_urls||[];
    const socials=(item.social_links||[]).filter(Boolean);
    return '<article class="v7-profile-hero"><div><span class="eyebrow">TRACK</span><h2>'+esc(item.name)+'</h2><p>'+esc(item.location||'Location sourced from connected events')+'</p>'+
      '<div class="v7-profile-actions">'+followButton('track',item)+claimButton('track',item)+
      '<a class="button" href="/api/public/race-center/calendar/track/'+encodeURIComponent(item.key)+'.ics">Calendar ↓</a>'+
      '<a class="button" href="https://www.google.com/maps/search/?api=1&query='+encodeURIComponent([item.name,item.location].filter(Boolean).join(', '))+'" target="_blank" rel="noopener">Map ↗</a>'+
      (item.official_url?'<a class="button" href="'+esc(item.official_url)+'" target="_blank" rel="noopener">Official site ↗</a>':'')+
      shareButton(item.name+' — Pitmark Race Center')+'</div></div>'+
      '<div class="v7-profile-stats"><div><span>SERIES</span><strong>'+Number((item.series||[]).length)+'</strong></div><div><span>EVENTS</span><strong>'+Number(events.length)+'</strong></div></div></article>'+
      (facts.length?'<section class="v7-track-facts">'+facts.map(row=>'<div><span>'+esc(row[0])+'</span><strong>'+esc(row[1])+'</strong></div>').join('')+'</section>':'')+
      '<div class="v7-profile-layout"><section class="v7-profile-section"><span class="eyebrow">UPCOMING / RECENT</span><h3>Events at '+esc(item.name)+'</h3><div class="v7-related-list">'+
      (events.length?events.map(e=>'<a href="/race-center/event/'+encodeURIComponent(e.key)+'"><strong>'+esc(e.name)+'</strong><span>'+esc([e.series_name,eventWhen(e.start)].filter(Boolean).join(' · '))+'</span></a>').join(''):'<p>No connected events are available yet.</p>')+
      '</div></section><section class="v7-profile-section"><span class="eyebrow">SERIES</span><h3>Who races here</h3><div class="v7-chip-list">'+(item.series||[]).map(key=>'<a href="/race-center/series/'+encodeURIComponent(key)+'">'+esc(key)+'</a>').join('')+'</div></section></div>'+
      '<div class="v7-profile-layout"><section class="v7-profile-section"><span class="eyebrow">DRIVERS</span><h3>Related drivers</h3><div class="v7-related-list">'+
      (drivers.length?drivers.map(d=>'<a href="/race-center/driver/'+encodeURIComponent((d.series&&d.series[0]&&d.series[0].series_key)||'')+'/'+encodeURIComponent(d.name||'')+'"><strong>'+esc((d.number?'#'+d.number+' · ':'')+(d.name||'Driver'))+'</strong><span>'+esc(d.team||((d.series||[]).map(x=>x.series_name).filter(Boolean).join(' · ')))+'</span></a>').join(''):'<p>Related drivers will appear as connected results data becomes available.</p>')+
      '</div></section><section class="v7-profile-section"><span class="eyebrow">SOURCES</span><h3>Track information provenance</h3><div class="v7-related-list">'+
      (sources.length?sources.map((url,index)=>'<a href="'+esc(url)+'" target="_blank" rel="noopener"><strong>Source '+(index+1)+'</strong><span>'+esc(url)+'</span></a>').join(''):'<p>This track is currently derived from connected race schedules.</p>')+
      (socials.length?socials.map(url=>'<a href="'+esc(url)+'" target="_blank" rel="noopener"><strong>Official social</strong><span>'+esc(url)+'</span></a>').join(''):'')+
      '</div></section></div>'+
      (item.photo_url?'<section class="v7-profile-section v7-track-media"><span class="eyebrow">TRACK MEDIA</span><img src="'+esc(item.photo_url)+'" alt="'+esc(item.name)+'"><p>'+esc([item.photo_attribution,item.photo_license].filter(Boolean).join(' · '))+'</p></section>':'');
  }

  function teamProfile(item){
    const drivers=item.drivers||[];
    return '<article class="v7-profile-hero"><div><span class="eyebrow">TEAM</span><h2>'+esc(item.name)+'</h2><p>'+esc(item.manufacturer||'Manufacturer not consistently published across connected series')+'</p>'+
      '<div class="v7-profile-actions">'+followButton('team',item)+claimButton('team',item)+shareButton(item.name+' — Pitmark Race Center')+'</div></div>'+
      '<div class="v7-profile-stats"><div><span>DRIVERS</span><strong>'+drivers.length+'</strong></div><div><span>SERIES</span><strong>'+Number((item.series||[]).length)+'</strong></div></div></article>'+
      '<div class="v7-profile-layout"><section class="v7-profile-section"><span class="eyebrow">DRIVER ROSTER</span><h3>Connected drivers</h3><div class="v7-related-list">'+drivers.map(d=>
        '<a href="/race-center/driver/'+encodeURIComponent(d.series_key||'')+'/'+encodeURIComponent(d.name||'')+'"><strong>'+esc((d.number?'#'+d.number+' · ':'')+d.name)+'</strong><span>'+esc(d.series_key||'Race Center driver')+'</span></a>'
      ).join('')+'</div></section><section class="v7-profile-section"><span class="eyebrow">CHAMPIONSHIPS</span><h3>Series</h3><div class="v7-chip-list">'+(item.series||[]).map(key=>'<a href="/race-center/series/'+encodeURIComponent(key)+'">'+esc(key)+'</a>').join('')+'</div></section></div>';
  }

  function eventProfile(item){
    const classes=Array.isArray(item.classes)?item.classes:[];
    const entries=Array.isArray(item.entry_list)&&item.entry_list.length?item.entry_list:(item.related_drivers||[]);
    const sources=(item.source_urls||[]);
    const context=item.championship_context||{};
    const leader=context.leader||null;
    return '<article class="v7-profile-hero v7-event-profile"><div><span class="eyebrow">'+esc(String(item.state||'EVENT').toUpperCase())+'</span><h2>'+esc(item.name)+'</h2><p>'+esc([item.series_name,item.venue,item.location].filter(Boolean).join(' · '))+'</p>'+
      '<div class="v7-event-countdown">'+esc(eventCountdown(item.start,item.state))+'</div>'+
      '<div class="v7-event-time">'+esc(eventWhen(item.start))+'</div><div class="v7-profile-actions">'+
      (item.watch_url?'<a class="button primary" href="'+esc(item.watch_url)+'" target="_blank" rel="noopener">Watch info ↗</a>':'')+
      (item.schedule_url?'<a class="button" href="'+esc(item.schedule_url)+'" target="_blank" rel="noopener">Official schedule ↗</a>':'')+
      (item.event_url?'<a class="button" href="'+esc(item.event_url)+'" target="_blank" rel="noopener">Event source ↗</a>':'')+
      '<a class="button" href="/api/public/race-center/calendar/event/'+encodeURIComponent(item.key)+'.ics">Add to calendar ↓</a>'+
      shareButton(item.name+' — Pitmark Race Center')+
      '</div></div><div class="v7-profile-stats"><div><span>STATUS</span><strong>'+esc(String(item.state||'schedule').toUpperCase())+'</strong></div><div><span>SERIES</span><strong>'+esc(item.series_name||'—')+'</strong></div></div></article>'+
      (classes.length?'<section class="v7-chip-strip"><span class="eyebrow">CLASSES / DIVISIONS</span><div class="v7-chip-list">'+classes.map(x=>'<span>'+esc(typeof x==='object'?(x.name||x.label||JSON.stringify(x)):x)+'</span>').join('')+'</div></section>':'')+
      '<div class="v7-profile-layout"><section class="v7-profile-section"><span class="eyebrow">EVENT HUB</span><h3>Race-day connections</h3><div class="v7-related-list">'+
      '<a href="/race-center/series/'+encodeURIComponent(item.series_key||'')+'"><strong>'+esc(item.series_name||'Series')+'</strong><span>Championship profile + standings</span></a>'+
      (item.track_key?'<a href="/race-center/track/'+encodeURIComponent(item.track_key)+'"><strong>'+esc(item.venue||'Track')+'</strong><span>'+esc(item.location||'Track profile')+'</span></a>':'')+
      '</div></section><section class="v7-profile-section"><span class="eyebrow">CHAMPIONSHIP CONTEXT</span><h3>What this race means</h3>'+
      (leader?'<div class="v7-event-leader"><span>POINTS LEADER</span><strong>'+esc((leader.number?('#'+leader.number+' · '):'')+(leader.name||'Leader'))+'</strong><p>'+esc([leader.team,leader.points!==undefined&&leader.points!==null?(leader.points+' pts'):''].filter(Boolean).join(' · '))+'</p></div>':'<p>Championship context will appear when current standings are available.</p>')+
      '</section></div>'+
      '<div class="v7-profile-layout"><section class="v7-profile-section"><span class="eyebrow">ENTRY LIST</span><h3>Who is in</h3>'+eventRows(entries,'Entry list has not been published by the connected source yet.')+'</section>'+
      '<section class="v7-profile-section"><span class="eyebrow">STARTING LINEUP</span><h3>Grid / lineup</h3>'+eventRows(item.starting_lineup,'Starting lineup has not been published yet.')+'</section></div>'+
      '<div class="v7-profile-layout"><section class="v7-profile-section"><span class="eyebrow">QUALIFYING + HEATS</span><h3>Race program</h3>'+eventRows([...(item.qualifying||[]),...(item.heats||[]),...(item.features||[])],'Session structure has not been published by the connected source yet.')+'</section>'+
      '<section class="v7-profile-section"><span class="eyebrow">RESULTS</span><h3>Official results</h3>'+eventRows(item.results,item.state==='recent'?'Official results are not yet available from the connected source.':'Results appear here after the event when a verified source publishes them.')+'</section></div>'+
      '<section class="v7-profile-section"><span class="eyebrow">SOURCES</span><h3>Event provenance</h3><div class="v7-related-list">'+
      (sources.length?sources.map((url,index)=>'<a href="'+esc(url)+'" target="_blank" rel="noopener"><strong>Source '+(index+1)+'</strong><span>'+esc(url)+'</span></a>').join(''):'<p>This event is derived from the connected series schedule.</p>')+
      '</div></section>';
  }

  async function renderEntityProfile(){
    const mapping={
      trackprofile:['track','track'],
      teamprofile:['team','team'],
      eventprofile:['event','event']
    };
    if(!mapping[view])return;
    const [type,pathKind]=mapping[view];
    const key=entityRouteKey(pathKind);
    const host=$('#v7EntityProfile');
    const content=$('#v7EntityProfileContent');
    host.style.display='block';
    try{
      const item=await getJson('/api/public/race-center/entity/'+type+'/'+encodeURIComponent(key)+'?v=7');
      let html=type==='track'?trackProfile(item):type==='team'?teamProfile(item):eventProfile(item);
      html+=ownerContentBlock(item);
      html+=editorialBlock(item.editorial);
      content.innerHTML=html;
    }catch(error){
      content.innerHTML='<div class="loading-card">'+esc(error.message)+'</div>';
    }
  }

  async function setFollow(button){
    const kind=button.dataset.kind;
    const key=button.dataset.key;
    const label=button.dataset.label;
    button.disabled=true;
    try{
      const result=await getJson('/api/public/race-center/follows',{
        method:'PUT',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({kind,key,label,series_key:''})
      });
      button.textContent='★ Following '+kind;
      button.classList.add('is-following');
      if(typeof state!=='undefined'&&state.account){
        state.account.follows=result.follows||state.account.follows||[];
        if(typeof renderMySeries==='function')renderMySeries();
        enhanceAccountCounts();
        setTimeout(augmentHomeMyRacing,30);
      }
    }catch(error){
      alert(error.message);
    }finally{button.disabled=false;}
  }

  async function claimEntity(button){
    const evidence=prompt('Paste an official website, social account, or other evidence showing you represent this '+button.dataset.kind+'.');
    if(evidence===null)return;
    const note=prompt('Optional note for Pitmark verification:')||'';
    try{
      const result=await getJson('/api/public/race-center/entity-claims',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          entity_type:button.dataset.kind,
          entity_key:button.dataset.key,
          entity_name:button.dataset.label,
          evidence_url:evidence,
          note
        })
      });
      button.textContent='Claim '+String(result.status||'submitted');
      button.disabled=true;
    }catch(error){alert(error.message);}
  }

  function briefCard(label,title,body,href){
    return '<a class="v7-brief-card" href="'+esc(href||'#')+'"><span class="v7-card-kicker">'+esc(label)+'</span><strong>'+esc(title)+'</strong><p>'+esc(body||'')+'</p></a>';
  }

  async function renderRaceDay(){
    const host=$('#v7RaceDay');
    const grid=$('#v7RaceDayGrid');
    if(!host||view!=='hub')return;
    try{
      const data=await getJson('/api/public/race-center/race-day?v=7');
      const rows=[];
      (data.live||[]).slice(0,4).forEach(e=>rows.push(briefCard(e.race_day_reason||'LIVE NOW',e.name,[e.series_name,e.venue,'LIVE NOW'].filter(Boolean).join(' · '),'/race-center/event/'+encodeURIComponent(e.key))));
      (data.upcoming||[]).slice(0,4).forEach(e=>rows.push(briefCard(e.race_day_reason||'UP NEXT',e.name,[eventCountdown(e.start,e.state),e.venue,e.series_name].filter(Boolean).join(' · '),'/race-center/event/'+encodeURIComponent(e.key))));
      (data.movement||[]).slice(0,2).forEach(m=>rows.push(briefCard('POINTS MOVE',m.driver,'P'+String(m.position||'—')+' · '+String(m.series_name||''),'/race-center/driver/'+encodeURIComponent(m.series_key||'')+'/'+encodeURIComponent(m.driver||''))));
      if(rows.length){
        host.style.display='block';
        grid.innerHTML=rows.join('');
      }else{
        host.style.display='block';
        grid.innerHTML='<a class="v7-brief-card" href="/race-center/my-racing"><span class="v7-card-kicker">MY RACING</span><strong>Build your race-day board</strong><p>Follow drivers, series, tracks and teams. Race Center will bring the important stuff here.</p></a>';
      }
    }catch(_error){
      host.style.display='none';
    }
  }

  async function renderMyRacing(){
    if(view!=='myracing')return;
    const host=$('#v7MyRacing');
    const grid=$('#v7MyRacingGrid');
    host.style.display='block';
    try{
      const [data,alertData]=await Promise.all([
        getJson('/api/public/race-center/my-racing?v=7'),
        getJson('/api/public/race-center/alerts?v=7').catch(()=>({alerts:[]}))
      ]);
      const blocks=[];
      const alerts=alertData.alerts||[];
      blocks.push('<section class="v7-brief-section v7-alert-stream"><span class="eyebrow">ATTENTION</span><h3>What needs your eyes</h3><div class="v7-brief-row">'+(
        alerts.length?alerts.slice(0,8).map(a=>briefCard(String(a.type||'UPDATE').replaceAll('_',' '),a.title,a.body,a.url)).join(''):'<p>No urgent updates across your racing right now.</p>'
      )+'</div></section>');
      blocks.push('<section class="v7-brief-section"><span class="eyebrow">RIGHT NOW</span><h3>Live</h3><div class="v7-brief-row">'+((data.live||[]).map(e=>briefCard('LIVE',e.name,e.series_name,'/race-center/event/'+encodeURIComponent(e.key))).join('')||'<p>Nothing you follow is live right now.</p>')+'</div></section>');
      blocks.push('<section class="v7-brief-section"><span class="eyebrow">COMING UP</span><h3>Next races</h3><div class="v7-brief-row">'+((data.upcoming||[]).map(e=>briefCard('NEXT',e.name,eventWhen(e.start),'/race-center/event/'+encodeURIComponent(e.key))).join('')||'<p>Follow series or tracks to build your upcoming-race list.</p>')+'</div></section>');
      blocks.push('<section class="v7-brief-section"><span class="eyebrow">CHAMPIONSHIP MOVEMENT</span><h3>What changed</h3><div class="v7-brief-row">'+((data.movement||[]).map(m=>briefCard('MOVE',m.driver,'P'+String(m.position||'—')+' · '+String(m.series_name||''),'/race-center/driver/'+encodeURIComponent(m.series_key||'')+'/'+encodeURIComponent(m.driver||''))).join('')||'<p>No verified moves among your followed drivers.</p>')+'</div></section>');
      blocks.push('<section class="v7-brief-section"><span class="eyebrow">YOUR GRAPH</span><h3>Following</h3><div class="v7-follow-summary"><div><strong>'+Number(data.counts?.series||0)+'</strong><span>Series</span></div><div><strong>'+Number(data.counts?.drivers||0)+'</strong><span>Drivers</span></div><div><strong>'+Number(data.counts?.tracks||0)+'</strong><span>Tracks</span></div><div><strong>'+Number(data.counts?.teams||0)+'</strong><span>Teams</span></div></div></section>');
      grid.innerHTML=blocks.join('');
    }catch(error){
      grid.innerHTML='<div class="loading-card">'+esc(error.message)+'</div>';
    }
  }

  function compareIdentity(driver){
    const identity=[driver.number?'#'+driver.number:'',driver.team,driver.manufacturer].filter(Boolean);
    return identity.length?identity.join(' · '):'Identity fields not published by the connected source.';
  }

  function compareDriverCard(driver,label){
    const championships=driver.series||[];
    const wins=championships.reduce((total,row)=>total+(Number(row.wins)||0),0);
    const starts=championships.reduce((total,row)=>total+(Number(row.starts)||0),0);
    const best=championships
      .filter(row=>Number.isFinite(Number(row.position)))
      .sort((a,b)=>Number(a.position)-Number(b.position))[0];
    return '<article class="v7-compare-driver">'+
      '<span class="v7-card-kicker">'+esc(label)+'</span>'+
      '<h3>'+esc(driver.name||'Driver')+'</h3>'+
      '<p>'+esc(compareIdentity(driver))+'</p>'+
      '<div class="v7-compare-stat-grid">'+
        '<div><span>Championships</span><strong>'+championships.length+'</strong></div>'+
        '<div><span>Best position</span><strong>'+(best?'P'+esc(best.position):'—')+'</strong></div>'+
        '<div><span>Starts</span><strong>'+starts+'</strong></div>'+
        '<div><span>Wins</span><strong>'+wins+'</strong></div>'+
      '</div>'+
      '<a class="button" href="/race-center/driver/'+encodeURIComponent(championships[0]?.series_key||'')+'/'+encodeURIComponent(driver.name||'')+'">Open profile →</a>'+
    '</article>';
  }

  async function renderCompare(){
    if(view!=='compare')return;
    const host=$('#v7Compare');
    const results=$('#v7CompareResults');
    const left=$('#v7CompareA');
    const right=$('#v7CompareB');
    const go=$('#v7CompareGo');
    if(!host||!results||!left||!right||!go)return;
    host.style.display='block';

    const params=new URLSearchParams(location.search);
    const firstKey=String(params.get('a')||'');
    const secondKey=String(params.get('b')||'');
    let catalog=[];

    const load=async(a,b)=>{
      const data=await getJson('/api/public/race-center/compare?a='+encodeURIComponent(a||'')+'&b='+encodeURIComponent(b||'')+'&v=7');
      catalog=data.drivers||catalog;
      if(!left.dataset.loaded){
        const options=catalog.map(driver=>'<option value="'+esc(driver.key)+'">'+esc((driver.number?'#'+driver.number+' · ':'')+driver.name)+'</option>').join('');
        left.insertAdjacentHTML('beforeend',options);
        right.insertAdjacentHTML('beforeend',options);
        left.dataset.loaded='1';
        right.dataset.loaded='1';
      }
      if(a)left.value=a;
      if(b)right.value=b;
      if(!data.a||!data.b){
        results.innerHTML='<div class="loading-card">Choose two drivers to compare.</div>';
        return;
      }

      const shared=data.shared_series||[];
      results.innerHTML=
        '<div class="v7-compare-pair">'+
          compareDriverCard(data.a,'DRIVER A')+
          '<div class="v7-compare-vs">VS</div>'+
          compareDriverCard(data.b,'DRIVER B')+
        '</div>'+
        '<div class="v7-compare-share"><button class="button v7-share-page" type="button" data-share-title="'+esc(data.a.name+' vs '+data.b.name+' — Pitmark Race Center')+'">Share comparison ↗</button></div>'+
        '<section class="v7-profile-section v7-compare-series"><span class="eyebrow">HEAD TO HEAD</span><h3>Shared championships</h3>'+
          (shared.length
            ?'<div class="v7-compare-table"><div class="v7-compare-row header"><span>Series</span><span>'+esc(data.a.name)+'</span><span>'+esc(data.b.name)+'</span></div>'+
              shared.map(row=>'<div class="v7-compare-row"><strong>'+esc(row.series_name||row.series_key)+'</strong>'+
                '<span>'+esc(['P'+(row.a.position??'—'),(row.a.points??'—')+' pts',row.a.wins!==undefined&&row.a.wins!==null?row.a.wins+' wins':''].filter(Boolean).join(' · '))+'</span>'+
                '<span>'+esc(['P'+(row.b.position??'—'),(row.b.points??'—')+' pts',row.b.wins!==undefined&&row.b.wins!==null?row.b.wins+' wins':''].filter(Boolean).join(' · '))+'</span></div>').join('')+
              '</div>'
            :'<p>These drivers do not currently share a tracked championship. Their individual racing profiles are still shown above.</p>')+
        '</section>';
    };

    try{
      await load(firstKey,secondKey);
      go.addEventListener('click',()=>{
        const a=left.value;
        const b=right.value;
        if(!a||!b||a===b){
          results.innerHTML='<div class="loading-card">Choose two different drivers.</div>';
          return;
        }
        const url=new URL(location.href);
        url.searchParams.set('a',a);
        url.searchParams.set('b',b);
        history.replaceState(null,'',url);
        load(a,b).catch(error=>results.innerHTML='<div class="loading-card">'+esc(error.message)+'</div>');
      });
    }catch(error){
      results.innerHTML='<div class="loading-card">'+esc(error.message)+'</div>';
    }
  }

  async function renderHealth(){
    if(view!=='health')return;
    const host=$('#v7Health');
    const grid=$('#v7HealthGrid');
    host.style.display='block';
    try{
      const data=await getJson('/api/public/race-center/data-health?v=7');
      const cards=[
        ['SERIES',data.series_total,'tracked'],
        ['FRESH',data.fresh_series,'current snapshots'],
        ['STALE',data.stale_series_count,'need refresh'],
        ['UNAVAILABLE',data.unavailable_series_count,'no usable saved snapshot'],
        ['IDENTITY',data.complete_driver_identity,'complete driver rows'],
        ['IDENTITY GAPS',data.incomplete_driver_identity,'rows need enrichment']
      ];
      grid.innerHTML='<div class="v7-health-stats">'+cards.map(x=>'<div><span>'+esc(x[0])+'</span><strong>'+Number(x[1]||0)+'</strong><small>'+esc(x[2])+'</small></div>').join('')+'</div>'+
        '<div class="v7-health-lists"><section><h3>Stale sources</h3>'+((data.stale_series||[]).map(x=>'<a href="/race-center/series/'+encodeURIComponent(x.key)+'">'+esc(x.name)+'</a>').join('')||'<p>None.</p>')+'</section>'+
        '<section><h3>Unavailable sources</h3>'+((data.unavailable_series||[]).map(x=>'<a href="/race-center/series/'+encodeURIComponent(x.key)+'">'+esc(x.name)+'</a>').join('')||'<p>None.</p>')+'</section></div>';
    }catch(error){
      grid.innerHTML='<div class="loading-card">'+esc(error.message)+'</div>';
    }
  }

  async function openAlerts(){
    try{
      const data=await getJson('/api/public/race-center/notifications?v=7');
      const prefs=data.preferences||{};
      const modal=document.createElement('dialog');
      modal.className='v7-alert-dialog';
      modal.innerHTML='<form method="dialog"><div class="dialog-head"><div><span class="eyebrow">MY RACING ALERTS</span><h2>What should Race Center surface?</h2></div><button class="dialog-close" value="cancel">×</button></div>'+
        '<div class="v7-alert-options">'+[
          ['race_day','Race day','Upcoming races for what you follow'],
          ['live_now','Live now','When followed racing goes live'],
          ['results_posted','Results','When verified results arrive'],
          ['standings_move','Standings movement','Meaningful championship moves'],
          ['schedule_change','Schedule changes','Changed dates/times from tracked sources'],
          ['editorial','Pitmark coverage','Stories connected to what you follow']
        ].map(([key,title,desc])=>'<label><input type="checkbox" name="'+key+'" '+(prefs[key]?'checked':'')+'><span><strong>'+title+'</strong><small>'+desc+'</small></span></label>').join('')+
        '</div><div class="dialog-actions"><button class="button" value="cancel">Cancel</button><button class="button primary" id="v7SaveAlerts" type="button">Save alerts</button></div></form>';
      document.body.appendChild(modal);
      modal.showModal();
      modal.addEventListener('close',()=>modal.remove(),{once:true});
      $('#v7SaveAlerts',modal).addEventListener('click',async()=>{
        const values={};
        $$('input[type=checkbox]',modal).forEach(input=>values[input.name]=input.checked);
        await getJson('/api/public/race-center/notifications',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});
        modal.close();
      });
    }catch(error){alert(error.message);}
  }

  let searchTimer=null;
  function wireUniversalSearch(){
    const input=$('#raceSearchInput');
    const host=$('#raceSearchResults');
    if(!input||!host)return;
    input.addEventListener('input',()=>{
      clearTimeout(searchTimer);
      const q=String(input.value||'').trim();
      if(q.length<2)return;
      searchTimer=setTimeout(async()=>{
        try{
          const data=await getJson('/api/public/race-center/search?q='+encodeURIComponent(q)+'&limit=18&v=7');
          if(String(input.value||'').trim()!==q)return;
          const rows=data.results||[];
          host.innerHTML=rows.length?rows.map(item=>'<a class="race-search-result" href="'+esc(hrefFor(item.type,item))+'"><span class="race-search-kind">'+esc(item.type)+'</span><span class="race-search-copy"><strong>'+esc(item.name||item.series_name||'Racing')+'</strong><small>'+esc([item.team,item.manufacturer,item.location,item.group,item.series_name].filter(Boolean).join(' · ')||'Open in Race Center')+'</small></span><b>→</b></a>').join(''):'<div class="race-search-empty"><strong>No match yet.</strong><span>Try a driver, number, team, track, series or event.</span></div>';
          host.hidden=false;
        }catch(_error){}
      },160);
    });
  }

  async function augmentDriverPage(){
    if(view!=='driver')return;
    const content=$('#driverProfileContent');
    if(!content)return;
    const parts=decodeURI(location.pathname).split('/');
    const name=decodeURIComponent(parts.slice(4).join('/'));
    const seriesKey=decodeURIComponent(parts[3]||'');
    try{
      const data=await graph();
      const driver=(data.drivers||[]).find(x=>normalize(x.name)===normalize(name));
      if(!driver)return;
      const entity=await getJson('/api/public/race-center/entity/driver/'+encodeURIComponent(driver.key)+'?v=7').catch(()=>null);
      const add=()=>{
        if($('#v7DriverConnections',content))return;
        const teams=[];
        if(driver.team)teams.push('<a href="/race-center/team/'+encodeURIComponent(String(driver.team).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,''))+'"><strong>'+esc(driver.team)+'</strong><span>Team profile →</span></a>');
        const series=(driver.series||[]).map(x=>'<a href="/race-center/series/'+encodeURIComponent(x.series_key)+'"><strong>'+esc(x.series_name||x.series_key)+'</strong><span>P'+esc(x.position||'—')+' · '+esc(x.points||'—')+' pts'+(x.wins!==undefined&&x.wins!==null?' · '+esc(x.wins)+' wins':'')+(x.starts!==undefined&&x.starts!==null?' · '+esc(x.starts)+' starts':'')+'</span></a>').join('');
        const section=document.createElement('section');
        section.id='v7DriverConnections';
        section.className='v7-driver-connections';
        section.innerHTML='<div class="section-head"><div><span class="eyebrow">CONNECTED RACING</span><h2>Across Race Center</h2></div><div class="v7-profile-actions"><a class="button" href="/race-center/compare?a='+encodeURIComponent(driver.key)+'">Compare driver ↔</a>'+shareButton(driver.name+' — Pitmark Race Center')+'</div></div><div class="v7-profile-layout"><section class="v7-profile-section"><h3>Team</h3><div class="v7-related-list">'+(teams.join('')||'<p>No team relationship is published yet.</p>')+'</div></section><section class="v7-profile-section"><h3>Current championships</h3><div class="v7-related-list">'+series+'</div></section></div>'+ownerContentBlock(entity||{})+editorialBlock(entity?.editorial||[]);
        content.appendChild(section);
      };
      add();
      const observer=new MutationObserver(add);
      observer.observe(content,{childList:true,subtree:false});
      setTimeout(()=>observer.disconnect(),6000);
    }catch(_error){}
  }

  async function augmentSeriesProfile(){
    if(view!=='seriesprofile')return;
    const content=$('#seriesProfileContent');
    if(!content)return;
    const key=entityRouteKey('series');
    if(!key)return;
    try{
      const [archive,entity]=await Promise.all([
        getJson('/api/public/race-center/archive/'+encodeURIComponent(key)+'?limit=12&v=7'),
        getJson('/api/public/race-center/entity/series/'+encodeURIComponent(key)+'?v=7').catch(()=>null)
      ]);
      const add=()=>{
        if($('#v7SeriesArchive',content))return;
        const rows=archive.snapshots||[];
        const section=document.createElement('section');
        section.id='v7SeriesArchive';
        section.className='v7-driver-connections';
        section.innerHTML='<div class="section-head"><div><span class="eyebrow">RESULTS ARCHIVE</span><h2>Championship snapshots</h2></div><p>'+Number(archive.snapshot_count||0)+' saved snapshots for '+esc(String(archive.season||''))+'.</p></div>'+
          '<div class="v7-archive-grid">'+(rows.length?rows.map(row=>{
            const leader=row.leader||{};
            return '<article class="v7-archive-card"><span>'+esc(eventWhen(row.fetched_at))+'</span><strong>'+esc(leader.name||'Snapshot saved')+'</strong><p>'+(leader.position?'P'+esc(leader.position)+' · ':'')+esc(leader.points??'—')+' pts · '+Number(row.field_size||0)+' drivers</p><small>'+esc(row.source_name||'Race Center source')+'</small></article>';
          }).join(''):'<div class="loading-card">No saved archive snapshots yet.</div>')+'</div>';
        if(entity){
          section.innerHTML+=ownerContentBlock(entity)+editorialBlock(entity.editorial||[])+
            '<div class="v7-profile-actions">'+claimButton('series',entity)+
            '<a class="button" href="/api/public/race-center/calendar/series/'+encodeURIComponent(key)+'.ics">Series calendar ↓</a>'+shareButton((entity.name||entity.series_name||'Series')+' — Pitmark Race Center')+'</div>';
        }
        content.appendChild(section);
      };
      add();
      const observer=new MutationObserver(add);
      observer.observe(content,{childList:true,subtree:false});
      setTimeout(()=>observer.disconnect(),6000);
    }catch(_error){}
  }


  function enhanceAccountCounts(){
    try{
      const follows=(typeof state!=='undefined'&&state.account&&state.account.follows)||[];
      const counts={series:0,driver:0,track:0,team:0};
      follows.forEach(item=>{if(counts[item.kind]!==undefined)counts[item.kind]++;});
      const track=$('#accountTrackCount');
      const team=$('#accountTeamCount');
      if(track)track.textContent=String(counts.track);
      if(team)team.textContent=String(counts.team);
    }catch(_error){}
  }

  async function augmentHomeMyRacing(){
    if(view!=='hub')return;
    const strip=$('#mySeriesStrip');
    if(!strip)return;
    try{
      const follows=(typeof state!=='undefined'&&state.account&&state.account.follows)||[];
      const extra=follows.filter(item=>item.kind==='track'||item.kind==='team');
      if(!extra.length)return;
      const data=await graph();
      const trackMap=new Map((data.tracks||[]).map(item=>[String(item.key),item]));
      const teamMap=new Map((data.teams||[]).map(item=>[String(item.key),item]));
      extra.forEach(follow=>{
        const selector='[data-v7-follow-chip="'+CSS.escape(String(follow.kind)+':'+String(follow.key))+'"]';
        if(strip.querySelector(selector))return;
        const item=follow.kind==='track'?trackMap.get(String(follow.key)):teamMap.get(String(follow.key));
        const label=item?.name||follow.label||follow.key;
        const href=follow.kind==='track'?'/race-center/track/'+encodeURIComponent(follow.key):'/race-center/team/'+encodeURIComponent(follow.key);
        const chip=document.createElement('a');
        chip.className='my-series-chip v7-follow-chip';
        chip.dataset.v7FollowChip=String(follow.kind)+':'+String(follow.key);
        chip.href=href;
        chip.innerHTML='<span class="v7-chip-icon">'+(follow.kind==='track'?'⌖':'T')+'</span><span><strong>'+esc(label)+'</strong><small>'+esc(follow.kind==='track'?'Followed track':'Followed team')+'</small></span>';
        strip.appendChild(chip);
      });
      if(extra.length&&typeof refreshMySeriesScrollCue==='function')refreshMySeriesScrollCue();
    }catch(_error){}
  }

  function registerPwa(){
    if('serviceWorker' in navigator){
      navigator.serviceWorker.register('/race-center-sw.js?v=7',{scope:'/race-center/'}).catch(()=>{});
    }
  }

  function init(){
    setActiveNav();
    renderDirectory();
    renderEntityProfile();
    renderRaceDay();
    renderMyRacing();
    renderCompare();
    renderHealth();
    wireUniversalSearch();
    augmentDriverPage();
    augmentSeriesProfile();
    enhanceAccountCounts();
    augmentHomeMyRacing();
    registerPwa();

    document.addEventListener('click',event=>{
      const follow=event.target.closest('.v7-follow-entity');
      if(follow){event.preventDefault();setFollow(follow);return;}
      const claim=event.target.closest('.v7-claim-entity');
      if(claim){event.preventDefault();claimEntity(claim);return;}
      const share=event.target.closest('.v7-share-page');
      if(share){event.preventDefault();shareCurrentPage(share.dataset.shareTitle||document.title);return;}
    });

    const alerts=$('#v7AlertsButton');
    if(alerts)alerts.addEventListener('click',openAlerts);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();