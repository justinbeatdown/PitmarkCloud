(function(){
  'use strict';

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

  function claimButton(type,item){
    if(!['track','team','series','driver'].includes(type))return '';
    return '<button class="button v7-claim-entity" type="button" data-kind="'+esc(type)+'" data-key="'+esc(item.key)+'" data-label="'+esc(item.name||item.series_name||'Racing entity')+'">Claim this '+esc(type)+'</button>';
  }

  function editorialBlock(items){
    if(!items||!items.length)return '';
    return '<section class="v7-profile-section"><span class="eyebrow">PITMARK COVERAGE</span><h3>Stories connected to this page</h3><div class="v7-editorial-list">'+items.map(x=>
      '<a href="'+esc(x.url)+'" target="_blank" rel="noopener"><strong>'+esc(x.title)+'</strong><span>'+esc(x.summary||'Open Pitmark coverage')+'</span></a>'
    ).join('')+'</div></section>';
  }

  function trackProfile(item){
    const events=(item.events||[]).slice(0,12);
    return '<article class="v7-profile-hero"><div><span class="eyebrow">TRACK</span><h2>'+esc(item.name)+'</h2><p>'+esc(item.location||'Location sourced from connected events')+'</p>'+
      '<div class="v7-profile-actions">'+followButton('track',item)+claimButton('track',item)+'</div></div>'+
      '<div class="v7-profile-stats"><div><span>SERIES</span><strong>'+Number((item.series||[]).length)+'</strong></div><div><span>EVENTS</span><strong>'+Number(events.length)+'</strong></div></div></article>'+
      '<div class="v7-profile-layout"><section class="v7-profile-section"><span class="eyebrow">UPCOMING / RECENT</span><h3>Events at '+esc(item.name)+'</h3><div class="v7-related-list">'+
      (events.length?events.map(e=>'<a href="/race-center/event/'+encodeURIComponent(e.key)+'"><strong>'+esc(e.name)+'</strong><span>'+esc([e.series_name,eventWhen(e.start)].filter(Boolean).join(' · '))+'</span></a>').join(''):'<p>No connected events are available yet.</p>')+
      '</div></section><section class="v7-profile-section"><span class="eyebrow">SERIES</span><h3>Who races here</h3><div class="v7-chip-list">'+(item.series||[]).map(key=>'<a href="/race-center/series/'+encodeURIComponent(key)+'">'+esc(key)+'</a>').join('')+'</div></section></div>';
  }

  function teamProfile(item){
    const drivers=item.drivers||[];
    return '<article class="v7-profile-hero"><div><span class="eyebrow">TEAM</span><h2>'+esc(item.name)+'</h2><p>'+esc(item.manufacturer||'Manufacturer not consistently published across connected series')+'</p>'+
      '<div class="v7-profile-actions">'+followButton('team',item)+claimButton('team',item)+'</div></div>'+
      '<div class="v7-profile-stats"><div><span>DRIVERS</span><strong>'+drivers.length+'</strong></div><div><span>SERIES</span><strong>'+Number((item.series||[]).length)+'</strong></div></div></article>'+
      '<div class="v7-profile-layout"><section class="v7-profile-section"><span class="eyebrow">DRIVER ROSTER</span><h3>Connected drivers</h3><div class="v7-related-list">'+drivers.map(d=>
        '<a href="/race-center/driver/'+encodeURIComponent(d.series_key||'')+'/'+encodeURIComponent(d.name||'')+'"><strong>'+esc((d.number?'#'+d.number+' · ':'')+d.name)+'</strong><span>'+esc(d.series_key||'Race Center driver')+'</span></a>'
      ).join('')+'</div></section><section class="v7-profile-section"><span class="eyebrow">CHAMPIONSHIPS</span><h3>Series</h3><div class="v7-chip-list">'+(item.series||[]).map(key=>'<a href="/race-center/series/'+encodeURIComponent(key)+'">'+esc(key)+'</a>').join('')+'</div></section></div>';
  }

  function eventProfile(item){
    return '<article class="v7-profile-hero v7-event-profile"><div><span class="eyebrow">'+esc(String(item.state||'EVENT').toUpperCase())+'</span><h2>'+esc(item.name)+'</h2><p>'+esc([item.series_name,item.venue,item.location].filter(Boolean).join(' · '))+'</p>'+
      '<div class="v7-event-time">'+esc(eventWhen(item.start))+'</div><div class="v7-profile-actions">'+
      (item.watch_url?'<a class="button primary" href="'+esc(item.watch_url)+'" target="_blank" rel="noopener">Watch info ↗</a>':'')+
      (item.schedule_url?'<a class="button" href="'+esc(item.schedule_url)+'" target="_blank" rel="noopener">Official schedule ↗</a>':'')+
      '</div></div><div class="v7-profile-stats"><div><span>STATUS</span><strong>'+esc(String(item.state||'schedule').toUpperCase())+'</strong></div><div><span>SERIES</span><strong>'+esc(item.series_name||'—')+'</strong></div></div></article>'+
      '<div class="v7-profile-layout"><section class="v7-profile-section"><span class="eyebrow">EVENT HUB</span><h3>Race-day connections</h3><div class="v7-related-list">'+
      '<a href="/race-center/series/'+encodeURIComponent(item.series_key||'')+'"><strong>'+esc(item.series_name||'Series')+'</strong><span>Championship profile + standings</span></a>'+
      (item.track_key?'<a href="/race-center/track/'+encodeURIComponent(item.track_key)+'"><strong>'+esc(item.venue||'Track')+'</strong><span>'+esc(item.location||'Track profile')+'</span></a>':'')+
      '</div></section><section class="v7-profile-section"><span class="eyebrow">RESULTS</span><h3>Event results</h3><p>'+(
        item.state==='recent'?'Race Center will attach official results here when the connected source exposes them.':'Results appear here after the event when a verified source is available.'
      )+'</p></section></div>';
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
      (data.live||[]).slice(0,3).forEach(e=>rows.push(briefCard('LIVE NOW',e.name,e.series_name,'/race-center/event/'+encodeURIComponent(e.key))));
      (data.upcoming||[]).slice(0,3).forEach(e=>rows.push(briefCard('UP NEXT',e.name,eventWhen(e.start),'/race-center/event/'+encodeURIComponent(e.key))));
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
      const data=await getJson('/api/public/race-center/my-racing?v=7');
      const blocks=[];
      blocks.push('<section class="v7-brief-section"><span class="eyebrow">RIGHT NOW</span><h3>Live</h3><div class="v7-brief-row">'+((data.live||[]).map(e=>briefCard('LIVE',e.name,e.series_name,'/race-center/event/'+encodeURIComponent(e.key))).join('')||'<p>Nothing you follow is live right now.</p>')+'</div></section>');
      blocks.push('<section class="v7-brief-section"><span class="eyebrow">COMING UP</span><h3>Next races</h3><div class="v7-brief-row">'+((data.upcoming||[]).map(e=>briefCard('NEXT',e.name,eventWhen(e.start),'/race-center/event/'+encodeURIComponent(e.key))).join('')||'<p>Follow series or tracks to build your upcoming-race list.</p>')+'</div></section>');
      blocks.push('<section class="v7-brief-section"><span class="eyebrow">CHAMPIONSHIP MOVEMENT</span><h3>What changed</h3><div class="v7-brief-row">'+((data.movement||[]).map(m=>briefCard('MOVE',m.driver,'P'+String(m.position||'—')+' · '+String(m.series_name||''),'/race-center/driver/'+encodeURIComponent(m.series_key||'')+'/'+encodeURIComponent(m.driver||''))).join('')||'<p>No verified moves among your followed drivers.</p>')+'</div></section>');
      blocks.push('<section class="v7-brief-section"><span class="eyebrow">YOUR GRAPH</span><h3>Following</h3><div class="v7-follow-summary"><div><strong>'+Number(data.counts?.series||0)+'</strong><span>Series</span></div><div><strong>'+Number(data.counts?.drivers||0)+'</strong><span>Drivers</span></div><div><strong>'+Number(data.counts?.tracks||0)+'</strong><span>Tracks</span></div><div><strong>'+Number(data.counts?.teams||0)+'</strong><span>Teams</span></div></div></section>');
      grid.innerHTML=blocks.join('');
    }catch(error){
      grid.innerHTML='<div class="loading-card">'+esc(error.message)+'</div>';
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
      const add=()=>{
        if($('#v7DriverConnections',content))return;
        const teams=[];
        if(driver.team)teams.push('<a href="/race-center/team/'+encodeURIComponent(String(driver.team).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,''))+'"><strong>'+esc(driver.team)+'</strong><span>Team profile →</span></a>');
        const series=(driver.series||[]).map(x=>'<a href="/race-center/series/'+encodeURIComponent(x.series_key)+'"><strong>'+esc(x.series_name||x.series_key)+'</strong><span>P'+esc(x.position||'—')+' · '+esc(x.points||'—')+' pts</span></a>').join('');
        const section=document.createElement('section');
        section.id='v7DriverConnections';
        section.className='v7-driver-connections';
        section.innerHTML='<div class="section-head"><div><span class="eyebrow">CONNECTED RACING</span><h2>Across Race Center</h2></div><p>Team and championship relationships tied to this driver.</p></div><div class="v7-profile-layout"><section class="v7-profile-section"><h3>Team</h3><div class="v7-related-list">'+(teams.join('')||'<p>No team relationship is published yet.</p>')+'</div></section><section class="v7-profile-section"><h3>Current championships</h3><div class="v7-related-list">'+series+'</div></section></div>';
        content.appendChild(section);
      };
      add();
      const observer=new MutationObserver(add);
      observer.observe(content,{childList:true,subtree:false});
      setTimeout(()=>observer.disconnect(),6000);
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
    renderHealth();
    wireUniversalSearch();
    augmentDriverPage();
    registerPwa();

    document.addEventListener('click',event=>{
      const follow=event.target.closest('.v7-follow-entity');
      if(follow){event.preventDefault();setFollow(follow);return;}
      const claim=event.target.closest('.v7-claim-entity');
      if(claim){event.preventDefault();claimEntity(claim);return;}
    });

    const alerts=$('#v7AlertsButton');
    if(alerts)alerts.addEventListener('click',openAlerts);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();