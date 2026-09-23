(function(){
  const WORLD_VIEWS=new Set(['tracks','trackprofile','teams','teamprofile','events','event','results','myracing','health']);
  const view=String(document.body.dataset.view||'hub');
  const escW=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const worldState={data:null,schedules:new Map(),loading:false,error:''};

  function fmtDate(value,options={}){
    if(!value)return 'TBD';
    const date=new Date(value);
    if(Number.isNaN(date.getTime()))return String(value);
    return new Intl.DateTimeFormat(undefined,{
      month:'short',day:'numeric',year:options.year?'numeric':undefined,
      hour:options.time===false?undefined:'numeric',
      minute:options.time===false?undefined:'2-digit'
    }).format(date);
  }

  function relative(value){
    if(!value)return '';
    const date=new Date(value);
    if(Number.isNaN(date.getTime()))return '';
    const diff=date.getTime()-Date.now();
    const abs=Math.abs(diff);
    const future=diff>=0;
    if(abs<60*60*1000)return (future?'in ':'')+Math.max(1,Math.round(abs/60000))+'m'+(future?'':' ago');
    if(abs<48*60*60*1000)return (future?'in ':'')+Math.round(abs/3600000)+'h'+(future?'':' ago');
    return (future?'in ':'')+Math.round(abs/86400000)+'d'+(future?'':' ago');
  }

  function isFollowed(kind,key){
    return Boolean(state?.account?.authenticated&&(state.account.follows||[]).some(x=>x.kind===kind&&String(x.key)===String(key)));
  }

  function followButton(kind,key,label,seriesKey=''){
    const on=isFollowed(kind,key);
    return '<button class="world-follow '+(on?'is-following':'')+'" type="button" data-world-follow-kind="'+escW(kind)+'" data-world-follow-key="'+escW(key)+'" data-world-follow-label="'+escW(label)+'" data-world-follow-series="'+escW(seriesKey)+'">'+(on?'★ Following':'☆ Follow')+'</button>';
  }

  function claimButton(type,key,name){
    return '<button class="world-claim" type="button" data-world-claim-type="'+escW(type)+'" data-world-claim-key="'+escW(key)+'" data-world-claim-name="'+escW(name)+'">Claim this '+escW(type)+'</button>';
  }

  function seriesName(key){
    const item=(worldState.data?.series||[]).find(x=>String(x.key)===String(key));
    return item?.name||key||'Racing series';
  }

  function entityHero(kicker,title,body,actions=''){
    return '<section class="world-hero">'+
      '<div><span class="eyebrow">'+escW(kicker)+'</span><h1>'+escW(title)+'</h1><p>'+escW(body||'')+'</p></div>'+
      (actions?'<div class="world-hero-actions">'+actions+'</div>':'')+
    '</section>';
  }

  function directoryHead(kicker,title,body,count,placeholder){
    return '<div class="world-directory-head">'+
      '<div><span class="eyebrow">'+escW(kicker)+'</span><h2>'+escW(title)+'</h2><p>'+escW(body)+'</p></div>'+
      '<label class="world-search"><span>⌕</span><input type="search" data-world-search placeholder="'+escW(placeholder)+'"></label>'+
      '<strong class="world-count">'+escW(count)+'</strong>'+
    '</div>';
  }

  function sourceBadge(text){
    return '<span class="world-source-badge">SOURCE-BACKED · '+escW(text)+'</span>';
  }

  function renderTracks(query=''){
    const host=document.querySelector('#worldPageContent');
    if(!host)return;
    const q=String(query||'').toLowerCase().trim();
    const rows=(worldState.data?.tracks||[]).filter(item=>!q||[item.name,item.location,...(item.series||[]).map(seriesName)].filter(Boolean).join(' ').toLowerCase().includes(q));
    host.innerHTML=entityHero(
      'TRACKS',
      'Where racing lives.',
      'Track profiles connect venues to the series and events Race Center already knows.',
      '<a class="button" href="/race-center/events">Open Race Day →</a>'
    )+
    directoryHead('TRACK DIRECTORY','Tracks in Race Center','Built from source-backed schedule venue data and expanded as Race Center learns more events.',rows.length+' tracks','Search track, location, series…')+
    '<div class="world-card-grid">'+(rows.length?rows.map(track=>{
      const next=(track.events||[]).filter(e=>e.start&&new Date(e.start)>=new Date()).sort((a,b)=>String(a.start).localeCompare(String(b.start)))[0];
      const href='/race-center/track/'+encodeURIComponent(track.key)+(track.series?.[0]?'?series_key='+encodeURIComponent(track.series[0]):'');
      return '<article class="world-card"><a class="world-card-main" href="'+href+'">'+
        '<span class="world-card-icon">⌖</span><div><span class="eyebrow">'+escW(track.location||'TRACK')+'</span><h3>'+escW(track.name)+'</h3>'+
        '<p>'+escW((track.series||[]).map(seriesName).slice(0,3).join(' · ')||'Race Center venue')+'</p>'+
        '<small>'+(next?'Next: '+escW(next.name)+' · '+escW(fmtDate(next.start,{time:false})):'Open track profile')+'</small></div><b>→</b></a>'+
        '<div class="world-card-actions">'+followButton('track',track.key,track.name,track.series?.[0]||'')+'</div></article>';
    }).join(''):'<div class="world-empty">Track index is still building from schedule venue data. Open a series/event and Race Center will keep expanding it.</div>')+'</div>';
  }

  async function renderTrackProfile(){
    const host=document.querySelector('#worldPageContent');
    if(!host)return;
    const marker='/race-center/track/';
    const key=decodeURIComponent(location.pathname.slice(location.pathname.indexOf(marker)+marker.length));
    const params=new URLSearchParams(location.search);
    const hint=params.get('series_key')||'';
    host.innerHTML='<div class="loading-card">Connecting track schedule data…</div>';
    try{
      const track=await apiJson('/api/public/race-center/track/'+encodeURIComponent(key)+(hint?'?series_key='+encodeURIComponent(hint):''),{method:'GET'});
      const upcoming=track.upcoming||[];
      const recent=track.recent||[];
      host.innerHTML=entityHero(
        track.location||'TRACK PROFILE',
        track.name,
        (track.series||[]).length+' visiting series currently connected in Race Center.',
        followButton('track',track.key,track.name,hint)+claimButton('track',track.key,track.name)
      )+
      '<div class="world-stat-row"><div><span>Series</span><strong>'+String((track.series||[]).length)+'</strong></div><div><span>Upcoming</span><strong>'+String(upcoming.length)+'</strong></div><div><span>Recent</span><strong>'+String(recent.length)+'</strong></div></div>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">UPCOMING</span><h2>Next races here</h2></div><div class="world-list">'+(upcoming.length?upcoming.map(e=>eventRow(e)).join(''):'<div class="world-empty">No upcoming sourced event is cached for this track yet.</div>')+'</div></section>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">CONNECTED SERIES</span><h2>Who races here</h2></div><div class="world-chip-grid">'+(track.series||[]).map(key=>'<a href="/race-center/series/'+encodeURIComponent(key)+'">'+escW(seriesName(key))+' →</a>').join('')+'</div></section>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">RECENT</span><h2>Recent schedule history</h2></div><div class="world-list">'+(recent.length?recent.map(e=>eventRow(e)).join(''):'<div class="world-empty">No completed event history cached yet.</div>')+'</div></section>';
    }catch(error){
      host.innerHTML=entityHero('TRACK PROFILE','Track data unavailable','Race Center could not resolve this track from a source-backed schedule right now.')+'<div class="world-empty">'+escW(error.message||'Track unavailable')+'</div>';
    }
  }

  function renderTeams(query=''){
    const host=document.querySelector('#worldPageContent');
    if(!host)return;
    const q=String(query||'').toLowerCase().trim();
    const rows=(worldState.data?.teams||[]).filter(item=>!q||[item.name,...(item.manufacturers||[]),...(item.drivers||[]).map(x=>x.name),...(item.series||[]).map(seriesName)].filter(Boolean).join(' ').toLowerCase().includes(q));
    host.innerHTML=entityHero('TEAMS','Who races together.','Team pages are built from current source-backed driver/team relationships in the standings graph.')+
      directoryHead('TEAM DIRECTORY','Racing teams','Drivers, manufacturers and championships connected through current Race Center data.',rows.length+' teams','Search team, driver, manufacturer…')+
      '<div class="world-card-grid">'+(rows.length?rows.map(team=>
        '<article class="world-card"><a class="world-card-main" href="/race-center/team/'+encodeURIComponent(team.key)+'">'+
        '<span class="world-card-icon">T</span><div><span class="eyebrow">'+escW((team.manufacturers||[]).join(' · ')||'TEAM')+'</span><h3>'+escW(team.name)+'</h3>'+
        '<p>'+escW((team.drivers||[]).slice(0,4).map(x=>x.name).join(' · '))+'</p><small>'+String((team.series||[]).length)+' series · '+String((team.drivers||[]).length)+' driver records</small></div><b>→</b></a>'+
        '<div class="world-card-actions">'+followButton('team',team.key,team.name)+'</div></article>'
      ).join(''):'<div class="world-empty">No team relationships are available in the current standings payload.</div>')+'</div>';
  }

  async function renderTeamProfile(){
    const host=document.querySelector('#worldPageContent');
    if(!host)return;
    const marker='/race-center/team/';
    const key=decodeURIComponent(location.pathname.slice(location.pathname.indexOf(marker)+marker.length));
    host.innerHTML='<div class="loading-card">Building team profile…</div>';
    try{
      const team=await apiJson('/api/public/race-center/team/'+encodeURIComponent(key),{method:'GET'});
      host.innerHTML=entityHero(
        (team.manufacturers||[]).join(' · ')||'TEAM PROFILE',
        team.name,
        'Current source-backed driver relationships across '+String((team.series||[]).length)+' championship'+((team.series||[]).length===1?'':'s')+'.',
        followButton('team',team.key,team.name)+claimButton('team',team.key,team.name)
      )+
      '<div class="world-stat-row"><div><span>Drivers</span><strong>'+String((team.drivers||[]).length)+'</strong></div><div><span>Series</span><strong>'+String((team.series||[]).length)+'</strong></div><div><span>Manufacturers</span><strong>'+String((team.manufacturers||[]).length)+'</strong></div></div>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">DRIVERS</span><h2>Current Race Center roster</h2></div><div class="world-list">'+(team.drivers||[]).map(driver=>
        '<a class="world-list-row" href="/race-center/driver/'+encodeURIComponent(driver.series_key)+'/'+encodeURIComponent(driver.name)+'"><span>'+(driver.number?'#'+escW(driver.number):'—')+'</span><strong>'+escW(driver.name)+'</strong><em>'+escW(seriesName(driver.series_key))+(driver.position?' · P'+escW(driver.position):'')+'</em><b>→</b></a>'
      ).join('')+'</div></section>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">CHAMPIONSHIPS</span><h2>Series connections</h2></div><div class="world-chip-grid">'+(team.series||[]).map(key=>'<a href="/race-center/series/'+encodeURIComponent(key)+'">'+escW(seriesName(key))+' →</a>').join('')+'</div></section>';
    }catch(error){
      host.innerHTML='<div class="world-empty">'+escW(error.message||'Team unavailable')+'</div>';
    }
  }

  function eventRow(event){
    const key=event.key||'';
    const seriesKey=event.series_key||'';
    const href=key&&seriesKey?'/race-center/event/'+encodeURIComponent(seriesKey)+'/'+encodeURIComponent(key):'/race-center/schedules';
    const state=String(event.state||'').toLowerCase();
    return '<a class="world-list-row world-event-row" href="'+href+'"><span class="world-event-state '+escW(state)+'">'+escW(state==='live'?'LIVE':state==='in'?'LIVE':state==='post'?'RESULT':'NEXT')+'</span>'+
      '<strong>'+escW(event.name||'Race event')+'</strong><em>'+escW([event.series_name||seriesName(seriesKey),event.venue,fmtDate(event.start)].filter(Boolean).join(' · '))+'</em><b>→</b></a>';
  }

  async function loadSchedule(seriesKey){
    if(worldState.schedules.has(seriesKey))return worldState.schedules.get(seriesKey);
    try{
      const payload=await apiJson('/api/public/race-center/schedule/'+encodeURIComponent(seriesKey),{method:'GET'});
      const events=payload.events||[];
      worldState.schedules.set(seriesKey,events);
      return events;
    }catch(_error){
      worldState.schedules.set(seriesKey,[]);
      return [];
    }
  }

  async function renderEvents(){
    const host=document.querySelector('#worldPageContent');
    if(!host)return;
    const current=worldState.data?.events||[];
    const followed=(state?.account?.follows||[]).filter(x=>x.kind==='series').map(x=>String(x.key));
    const priority=[...new Set([...followed,...current.map(x=>x.series_key)])].slice(0,8);
    host.innerHTML=entityHero('RACE DAY','Everything for the event.','Race Center Event Hubs connect the race, venue, series, watch link, standings context and source trail.')+
      '<section class="world-block race-day-block"><div class="world-block-head"><span class="eyebrow">RIGHT NOW + NEXT</span><h2>Race Day board</h2></div><div class="world-list" id="worldEventList">'+(current.length?current.map(eventRow).join(''):'<div class="world-empty">No live/current event summaries are available yet.</div>')+'</div></section>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">MY SCHEDULES</span><h2>Upcoming from your racing</h2><p>Race Center is loading full source-backed schedules for the series most relevant to you.</p></div><div class="world-list" id="worldUpcomingList"><div class="loading-card">Loading event schedules…</div></div></section>';
    const results=(await Promise.all(priority.map(loadSchedule))).flat().filter(x=>!x.completed&&x.start).sort((a,b)=>String(a.start).localeCompare(String(b.start))).slice(0,30);
    const list=document.querySelector('#worldUpcomingList');
    if(list)list.innerHTML=results.length?results.map(eventRow).join(''):'<div class="world-empty">Follow series to build a personalized Race Day schedule.</div>';
  }

  async function renderEventProfile(){
    const host=document.querySelector('#worldPageContent');
    if(!host)return;
    const marker='/race-center/event/';
    const rest=location.pathname.slice(location.pathname.indexOf(marker)+marker.length).split('/');
    const seriesKey=decodeURIComponent(rest.shift()||'');
    const key=decodeURIComponent(rest.join('/')||'');
    host.innerHTML='<div class="loading-card">Building Event Hub…</div>';
    try{
      const event=await apiJson('/api/public/race-center/event/'+encodeURIComponent(seriesKey)+'/'+encodeURIComponent(key),{method:'GET'});
      const series=(worldState.data?.series||[]).find(x=>x.key===seriesKey)||{};
      const leader=series.leader;
      const trackLink=event.track_key?'/race-center/track/'+encodeURIComponent(event.track_key)+'?series_key='+encodeURIComponent(seriesKey):'';
      const raceState=event.completed?'Completed':event.state==='in'?'LIVE':event.start?relative(event.start):'Scheduled';
      host.innerHTML=entityHero(
        event.state==='in'?'LIVE NOW':'EVENT HUB',
        event.name||seriesName(seriesKey),
        [event.venue,event.location,fmtDate(event.start)].filter(Boolean).join(' · '),
        (event.watch_url?'<a class="button primary" href="'+escW(event.watch_url)+'" target="_blank" rel="noopener">Watch info ↗</a>':'')+
        '<a class="button" href="/race-center/series/'+encodeURIComponent(seriesKey)+'">Series profile →</a>'
      )+
      '<div class="world-stat-row"><div><span>Status</span><strong>'+escW(raceState)+'</strong></div><div><span>Series</span><strong>'+escW(series.short_name||series.name||seriesName(seriesKey))+'</strong></div><div><span>Leader</span><strong>'+escW(leader?.name||'—')+'</strong></div><div><span>Field</span><strong>'+escW(series.field||'—')+'</strong></div></div>'+
      '<div class="world-two-col"><section class="world-block"><div class="world-block-head"><span class="eyebrow">RACE DAY</span><h2>Event information</h2></div><dl class="world-detail-list">'+
        '<div><dt>Start</dt><dd>'+escW(fmtDate(event.start))+'</dd></div><div><dt>Venue</dt><dd>'+(trackLink?'<a href="'+trackLink+'">'+escW(event.track_name||event.venue)+' →</a>':escW(event.venue||'Not published'))+'</dd></div><div><dt>Location</dt><dd>'+escW(event.location||'Not published')+'</dd></div><div><dt>Broadcast</dt><dd>'+escW(event.watch_name||event.broadcast||'See official source')+'</dd></div></dl></section>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">CHAMPIONSHIP CONTEXT</span><h2>What this race sits inside</h2></div>'+
        (leader?'<a class="world-leader-card" href="/race-center/driver/'+encodeURIComponent(seriesKey)+'/'+encodeURIComponent(leader.name)+'"><span>CHAMPIONSHIP LEADER</span><strong>'+escW(leader.name)+'</strong><small>'+escW(leader.points??'—')+' pts</small></a>':'<div class="world-empty">No current standings are available for this championship.</div>')+
        '<a class="button" href="/race-center/series/'+encodeURIComponent(seriesKey)+'">Open full championship →</a></section></div>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">OFFICIAL SOURCES</span><h2>Source trail</h2></div><div class="world-source-list">'+
        (event.source_url?'<a href="'+escW(event.source_url)+'" target="_blank" rel="noopener">Official event/schedule source ↗</a>':'')+
        (event.watch_url?'<a href="'+escW(event.watch_url)+'" target="_blank" rel="noopener">Official viewing information ↗</a>':'')+
        (event.schedule_url?'<a href="'+escW(event.schedule_url)+'" target="_blank" rel="noopener">Full official schedule ↗</a>':'')+
      '</div></section>';
    }catch(error){
      host.innerHTML='<div class="world-empty">'+escW(error.message||'Event unavailable')+'</div>';
    }
  }

  function renderResults(){
    const host=document.querySelector('#worldPageContent');
    if(!host)return;
    const history=worldState.data?.history||{};
    const rows=Object.entries(history).flatMap(([seriesKey,items])=>(items||[]).map(item=>({seriesKey,...item}))).sort((a,b)=>String(b.fetched_at||'').localeCompare(String(a.fetched_at||'')));
    const recentEvents=(worldState.data?.events||[]).filter(x=>x.completed||x.state==='recent'||x.state==='post');
    host.innerHTML=entityHero('RESULTS + HISTORY','A durable racing archive.','Race Center keeps championship snapshots and completed schedule context so the racing story does not disappear when a page updates.')+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">RECENT EVENTS</span><h2>Completed race activity</h2></div><div class="world-list">'+(recentEvents.length?recentEvents.map(eventRow).join(''):'<div class="world-empty">Completed event results will appear as source-backed result feeds are connected. Race Center will not invent unofficial finishing orders.</div>')+'</div></section>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">CHAMPIONSHIP ARCHIVE</span><h2>Saved standings snapshots</h2><p>These are durable source-backed championship states — useful for showing how the points picture changed over time.</p></div><div class="world-list">'+(rows.length?rows.slice(0,60).map(row=>
        '<a class="world-list-row" href="/race-center/series/'+encodeURIComponent(row.seriesKey)+'"><span>'+escW(fmtDate(row.fetched_at,{time:false}))+'</span><strong>'+escW(seriesName(row.seriesKey))+'</strong><em>'+(row.leader?'Leader: '+escW(row.leader.name)+' · '+escW(row.leader.points??'—')+' pts':escW(row.field)+' drivers')+'</em><b>→</b></a>'
      ).join(''):'<div class="world-empty">No standings history is available yet.</div>')+'</div></section>';
  }

  function renderMyRacing(){
    const host=document.querySelector('#worldPageContent');
    if(!host)return;
    if(!state?.account?.authenticated){
      host.innerHTML=entityHero('MY RACING','Your personal race briefing.','Sign in to turn follows into a daily racing briefing.')+'<button class="button primary" type="button" data-open-race-account>Sign in to My Race Center</button>';
      return;
    }
    const briefing=worldState.data?.briefing||{};
    const items=briefing.items||[];
    host.innerHTML=entityHero(
      'MY RACING',
      'What matters to you.',
      'A briefing built from your actual Race Center follows — not an algorithmic social timeline.',
      '<button class="button" type="button" data-world-alerts>Alert settings</button>'
    )+
      '<div class="world-stat-row"><div><span>Series</span><strong>'+String(briefing.series_followed||0)+'</strong></div><div><span>Drivers</span><strong>'+String(briefing.drivers_followed||0)+'</strong></div><div><span>Tracks</span><strong>'+String(briefing.tracks_followed||0)+'</strong></div><div><span>Teams</span><strong>'+String(briefing.teams_followed||0)+'</strong></div></div>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">TODAY + NEXT</span><h2>Your racing briefing</h2></div><div class="briefing-list">'+(items.length?items.map((item,index)=>
        '<a class="briefing-item priority-'+escW(item.priority||0)+'" href="'+escW(item.href||'/race-center')+'"><span>'+String(index+1).padStart(2,'0')+'</span><div><strong>'+escW(item.title)+'</strong><small>'+escW(item.meta||item.kind||'Race Center')+'</small></div><b>→</b></a>'
      ).join(''):'<div class="world-empty">Follow drivers, series, tracks and teams to build your briefing.</div>')+'</div></section>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">DISCOVER</span><h2>Add more to My Racing</h2></div><div class="world-chip-grid"><a href="/race-center/drivers">Drivers →</a><a href="/race-center/series">Series →</a><a href="/race-center/tracks">Tracks →</a><a href="/race-center/teams">Teams →</a></div></section>';
  }

  function healthMetric(label,value,total,detail){
    const numeric=Number(value||0), max=Number(total||0);
    const pct=max?Math.max(0,Math.min(100,Math.round(numeric/max*100))):0;
    return '<article class="health-metric"><div><span>'+escW(label)+'</span><strong>'+escW(value)+' / '+escW(total)+'</strong></div><div class="health-bar"><i style="width:'+pct+'%"></i></div><p>'+escW(detail||pct+'% coverage')+'</p></article>';
  }

  function renderHealth(){
    const host=document.querySelector('#worldPageContent');
    if(!host)return;
    const h=worldState.data?.health||{};
    host.innerHTML=entityHero('DATA HEALTH','Trust the racing data.','Race Center exposes its own coverage instead of pretending every upstream source is perfect.',sourceBadge(String(h.status||'unknown').toUpperCase()))+
      '<div class="world-health-grid">'+
      healthMetric('Standings freshness',h.standings_fresh,h.series_total,'Series currently carrying fresh standings status.')+
      healthMetric('Schedule coverage',h.schedule_coverage,h.series_total,'Tracked series connected to an official schedule source.')+
      healthMetric('Source coverage',h.source_coverage,h.series_total,'Series with a standings or schedule source attached.')+
      healthMetric('Complete driver identity',h.complete_driver_identity,h.drivers_total,'Driver rows with number, team and manufacturer.')+
      healthMetric('Driver photo coverage',h.driver_photo_coverage,h.drivers_total,'Reusable or claimed profile photos currently available.')+
      '</div>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">SYSTEM</span><h2>Race Center graph</h2></div><div class="world-stat-row"><div><span>Series</span><strong>'+escW(worldState.data?.counts?.series||0)+'</strong></div><div><span>Drivers</span><strong>'+escW(worldState.data?.counts?.drivers||0)+'</strong></div><div><span>Teams</span><strong>'+escW(worldState.data?.counts?.teams||0)+'</strong></div><div><span>Tracks</span><strong>'+escW(worldState.data?.counts?.tracks||0)+'</strong></div><div><span>Current events</span><strong>'+escW(worldState.data?.counts?.current_events||0)+'</strong></div></div></section>'+
      '<section class="world-block"><div class="world-block-head"><span class="eyebrow">TRUST RULES</span><h2>What Race Center will not fake</h2></div><div class="health-rules"><p>Official racing facts stay source-backed.</p><p>Unknown results remain unknown instead of being inferred.</p><p>Claimed profiles can own presentation, bio, sponsors and links — not official standings/results.</p><p>Photo reuse requires a permitted source or owner upload.</p></div></section>';
  }

  function ensureClaimDialog(){
    let dialog=document.querySelector('#worldClaimDialog');
    if(dialog)return dialog;
    dialog=document.createElement('dialog');
    dialog.id='worldClaimDialog';
    dialog.className='account-dialog world-claim-dialog';
    dialog.innerHTML='<form method="dialog" class="world-claim-shell" id="worldClaimForm"><button class="dialog-close" value="cancel" aria-label="Close">×</button><span class="eyebrow">ENTITY OWNERSHIP</span><h2 id="worldClaimTitle">Claim this profile</h2><p>Race Center keeps official racing facts source-backed. Verified owners can control the human side: imagery, bio, links, sponsors and updates.</p><input type="hidden" name="entity_type"><input type="hidden" name="entity_key"><label>Proof / official link<input name="evidence_url" type="url" placeholder="Official site, verified social, team page…"></label><label>Note<textarea name="note" maxlength="1200" placeholder="Tell Pitmark how you are connected to this profile."></textarea></label><div class="world-claim-actions"><button class="button" value="cancel">Cancel</button><button class="button primary" type="submit" value="">Submit claim</button></div><p id="worldClaimMessage"></p></form>';
    document.body.appendChild(dialog);
    dialog.querySelector('#worldClaimForm').addEventListener('submit',async event=>{
      event.preventDefault();
      if(!state?.account?.authenticated){dialog.close();document.querySelector('#accountDialog')?.showModal();return;}
      const form=new FormData(event.currentTarget);
      const message=dialog.querySelector('#worldClaimMessage');
      message.textContent='Submitting…';
      try{
        await apiJson('/api/public/race-center/entity-claim',{method:'POST',body:JSON.stringify({
          entity_type:form.get('entity_type'),
          entity_key:form.get('entity_key'),
          entity_name:dialog.dataset.entityName||'',
          evidence_url:form.get('evidence_url')||'',
          note:form.get('note')||''
        })});
        message.textContent='Claim submitted for verification.';
      }catch(error){message.textContent=error.message||'Claim failed.';}
    });
    return dialog;
  }

  async function openAlerts(){
    if(!state?.account?.authenticated){document.querySelector('#accountDialog')?.showModal();return;}
    let dialog=document.querySelector('#worldAlertDialog');
    if(!dialog){
      dialog=document.createElement('dialog');
      dialog.id='worldAlertDialog';
      dialog.className='account-dialog';
      dialog.innerHTML='<form class="world-alert-shell" id="worldAlertForm"><button class="dialog-close" type="button" data-alert-close aria-label="Close">×</button><span class="eyebrow">MY RACING ALERTS</span><h2>Tell Race Center what matters.</h2><p>These preferences power the Race Center alert center and are ready for push delivery as the PWA notification channel rolls out.</p><div class="alert-toggle-list"></div><button class="button primary" type="submit">Save alerts</button><p id="worldAlertMessage"></p></form>';
      document.body.appendChild(dialog);
      dialog.querySelector('[data-alert-close]').addEventListener('click',()=>dialog.close());
      dialog.querySelector('#worldAlertForm').addEventListener('submit',async event=>{
        event.preventDefault();
        const data=Object.fromEntries(new FormData(event.currentTarget).entries());
        const body={race_start:Boolean(data.race_start),results:Boolean(data.results),standings:Boolean(data.standings),schedule_changes:Boolean(data.schedule_changes),editorial:Boolean(data.editorial)};
        const msg=dialog.querySelector('#worldAlertMessage');
        msg.textContent='Saving…';
        try{await apiJson('/api/public/race-center/alerts',{method:'PUT',body:JSON.stringify(body)});msg.textContent='Alert preferences saved.';}catch(error){msg.textContent=error.message||'Could not save alerts.';}
      });
    }
    try{
      const payload=await apiJson('/api/public/race-center/alerts',{method:'GET'});
      const prefs=payload.preferences||{};
      const labels={race_start:'Race start / live alerts',results:'Results posted',standings:'Championship changes',schedule_changes:'Schedule changes',editorial:'Pitmark coverage tied to my racing'};
      dialog.querySelector('.alert-toggle-list').innerHTML=Object.entries(labels).map(([key,label])=>'<label><input type="checkbox" name="'+key+'" '+(prefs[key]?'checked':'')+'><span><strong>'+escW(label)+'</strong><small>Based on entities in My Racing.</small></span></label>').join('');
      dialog.showModal();
    }catch(_error){document.querySelector('#accountDialog')?.showModal();}
  }

  function renderCurrentView(){
    document.querySelectorAll('[data-world-view]').forEach(link=>{
      const active=link.dataset.worldView===view||
        (view==='trackprofile'&&link.dataset.worldView==='tracks')||
        (view==='teamprofile'&&link.dataset.worldView==='teams')||
        (view==='event'&&link.dataset.worldView==='events');
      link.classList.toggle('active',active);
    });
    if(view==='tracks')renderTracks();
    else if(view==='trackprofile')renderTrackProfile();
    else if(view==='teams')renderTeams();
    else if(view==='teamprofile')renderTeamProfile();
    else if(view==='events')renderEvents();
    else if(view==='event')renderEventProfile();
    else if(view==='results')renderResults();
    else if(view==='myracing')renderMyRacing();
    else if(view==='health')renderHealth();
  }

  async function loadWorld(){
    if(worldState.loading)return;
    worldState.loading=true;
    try{
      worldState.data=await apiJson('/api/public/race-center/world?v=world-v1',{method:'GET',cache:'no-store'});
      window.RaceCenterWorld=worldState.data;
      renderCurrentView();
    }catch(error){
      worldState.error=error.message||'Race Center World failed to load';
      const host=document.querySelector('#worldPageContent');
      if(host&&WORLD_VIEWS.has(view))host.innerHTML='<div class="world-empty">'+escW(worldState.error)+'</div>';
    }finally{worldState.loading=false;}
  }

  document.addEventListener('input',event=>{
    if(!event.target.matches('[data-world-search]'))return;
    if(view==='tracks')renderTracks(event.target.value);
    if(view==='teams')renderTeams(event.target.value);
    const replacement=document.querySelector('[data-world-search]');
    if(replacement){replacement.value=event.target.value;replacement.focus();replacement.setSelectionRange(replacement.value.length,replacement.value.length);}
  });

  document.addEventListener('click',async event=>{
    const follow=event.target.closest('[data-world-follow-kind]');
    if(follow){
      event.preventDefault();
      const kind=follow.dataset.worldFollowKind;
      const key=follow.dataset.worldFollowKey;
      const label=follow.dataset.worldFollowLabel||'';
      const seriesKey=follow.dataset.worldFollowSeries||'';
      if(!state?.account?.authenticated){document.querySelector('#accountDialog')?.showModal();return;}
      follow.disabled=true;
      try{
        if(isFollowed(kind,key))await cloudUnfollow(kind,key,label,seriesKey);
        else await cloudFollow(kind,key,label,seriesKey);
        await loadWorld();
        renderCurrentView();
      }finally{follow.disabled=false;}
      return;
    }
    const claim=event.target.closest('[data-world-claim-type]');
    if(claim){
      event.preventDefault();
      if(!state?.account?.authenticated){document.querySelector('#accountDialog')?.showModal();return;}
      const dialog=ensureClaimDialog();
      dialog.dataset.entityName=claim.dataset.worldClaimName||'';
      dialog.querySelector('[name="entity_type"]').value=claim.dataset.worldClaimType||'';
      dialog.querySelector('[name="entity_key"]').value=claim.dataset.worldClaimKey||'';
      dialog.querySelector('#worldClaimTitle').textContent='Claim '+(claim.dataset.worldClaimName||'this profile');
      dialog.querySelector('#worldClaimMessage').textContent='';
      dialog.showModal();
      return;
    }
    if(event.target.closest('[data-world-alerts]')){event.preventDefault();openAlerts();return;}
    if(event.target.closest('[data-open-race-account]')){event.preventDefault();document.querySelector('#accountDialog')?.showModal();}
  });

  if('serviceWorker' in navigator){
    window.addEventListener('load',()=>navigator.serviceWorker.register('/race-center-sw.js').catch(()=>{}),{once:true});
  }

  if(WORLD_VIEWS.has(view))loadWorld();
  else loadWorld();
})();