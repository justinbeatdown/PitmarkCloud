(function(){
  const $7=(selector,root=document)=>(root||document).querySelector(selector);
  const $$7=(selector,root=document)=>[...(root||document).querySelectorAll(selector)];
  const e7=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const RC7={platform:null,briefing:null,loading:false};

  const currentView=()=>String(document.body.dataset.view||'hub');
  const followRows=()=>Array.isArray(state?.account?.follows)?state.account.follows:[];
  const followed=(kind,key)=>followRows().some(row=>String(row.kind)===String(kind)&&String(row.key)===String(key));

  function eventHref(event){
    return '/race-center/event/'+encodeURIComponent(String(event?.key||'').replaceAll(':','~'));
  }
  function routeEventKey(){
    const marker='/race-center/event/';
    const path=decodeURIComponent(location.pathname);
    const index=path.indexOf(marker);
    return index>=0?path.slice(index+marker.length).replaceAll('~',':'):'';
  }
  function routeKey(prefix){
    const marker='/race-center/'+prefix+'/';
    const path=decodeURIComponent(location.pathname);
    const index=path.indexOf(marker);
    return index>=0?path.slice(index+marker.length):'';
  }
  function dt(value){
    if(!value)return null;
    const parsed=new Date(value);
    return Number.isNaN(parsed.getTime())?null:parsed;
  }
  function formatDate(value,dateOnly=false){
    const parsed=dt(value);
    if(!parsed)return 'Date TBD';
    const options=dateOnly
      ?{weekday:'short',month:'short',day:'numeric',year:'numeric'}
      :{weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'};
    return new Intl.DateTimeFormat(undefined,options).format(parsed);
  }
  function countdown(value){
    const parsed=dt(value);
    if(!parsed)return 'TBD';
    const ms=parsed.getTime()-Date.now();
    if(ms<=0)return 'Now';
    const hours=Math.floor(ms/3600000);
    if(hours<1)return Math.max(1,Math.ceil(ms/60000))+'m';
    if(hours<48)return hours+'h';
    return Math.floor(hours/24)+'d '+(hours%24)+'h';
  }
  function stateLabel(event){
    if(event?.state==='in')return 'LIVE';
    if(event?.completed||event?.state==='post')return 'Completed';
    return event?.date_only?'Scheduled':'Starts '+countdown(event?.start);
  }
  function currentSeries(seriesKey){
    return (state?.payload?.series||[]).find(row=>String(row.series_key)===String(seriesKey))||null;
  }
  function seriesLogo(seriesKey,name){
    return '<img class="v7-series-mark" src="/standings-logo/'+encodeURIComponent(seriesKey)+'" alt="'+e7(name||'Series')+' logo" loading="lazy">';
  }
  function followButton(kind,key,label,seriesKey=''){
    const active=followed(kind,key);
    return '<button class="v7-follow '+(active?'is-following':'')+'" type="button" data-v7-follow-kind="'+e7(kind)+'" data-v7-follow-key="'+e7(key)+'" data-v7-follow-label="'+e7(label||key)+'" data-v7-follow-series="'+e7(seriesKey)+'">'+(active?'★ Following':'☆ Follow')+'</button>';
  }
  function claimButton(type,key,name){
    return '<button class="button v7-claim-button" type="button" data-v7-claim-type="'+e7(type)+'" data-v7-claim-key="'+e7(key)+'" data-v7-claim-name="'+e7(name)+'">Claim / verify</button>';
  }
  function eventCard(event,compact=false){
    const track=event.track_key
      ?'<a class="v7-inline-link" href="/race-center/track/'+encodeURIComponent(event.track_key)+'">'+e7(event.venue||'Track')+'</a>'
      :e7(event.venue||event.location||'Venue not supplied');
    return '<article class="v7-event-card '+(event.state==='in'?'is-live':'')+'">'+
      '<a class="v7-event-main" href="'+eventHref(event)+'">'+
        '<span class="v7-event-state">'+e7(stateLabel(event))+'</span>'+
        '<div><span class="eyebrow">'+e7(event.group||'RACING')+'</span><strong>'+e7(event.name||'Race event')+'</strong>'+
        '<small>'+e7(event.series_name||'Series')+' · '+e7(formatDate(event.start,event.date_only))+'</small>'+
        (!compact?'<em>'+track+(event.location?' · '+e7(event.location):'')+'</em>':'')+
        '</div><b>→</b>'+
      '</a>'+
      '<div class="v7-event-actions">'+
        followButton('event',event.key,event.name,event.series_key)+
        (event.watch_url?'<a class="v7-mini-action" href="'+e7(event.watch_url)+'" target="_blank" rel="noopener">Watch ↗</a>':'')+
      '</div>'+
    '</article>';
  }

  function trackCard(track){
    const next=track.next_event;
    return '<article class="v7-entity-card">'+
      '<a class="v7-entity-main" href="/race-center/track/'+encodeURIComponent(track.key)+'">'+
        '<span class="v7-entity-icon">⌖</span><div><span class="eyebrow">TRACK</span><strong>'+e7(track.name)+'</strong>'+
        '<small>'+e7(track.location||'Location from event source')+'</small>'+
        '<em>'+e7(next?'Next: '+next.name+' · '+formatDate(next.start,next.date_only):track.event_count+' indexed events')+'</em></div><b>→</b>'+
      '</a>'+
      '<div class="v7-entity-actions">'+followButton('track',track.key,track.name)+'</div>'+
    '</article>';
  }

  function teamCard(team){
    const manufacturers=(team.manufacturers||[]).join(' / ');
    const lead=(team.drivers||[])[0];
    return '<article class="v7-entity-card">'+
      '<a class="v7-entity-main" href="/race-center/team/'+encodeURIComponent(team.key)+'">'+
        '<span class="v7-entity-icon">T</span><div><span class="eyebrow">TEAM</span><strong>'+e7(team.name)+'</strong>'+
        '<small>'+e7(manufacturers||team.series_count+' series')+'</small>'+
        '<em>'+e7(lead?lead.name+' · '+lead.series_name+' · P'+(lead.position||'—'):team.driver_count+' tracked drivers')+'</em></div><b>→</b>'+
      '</a>'+
      '<div class="v7-entity-actions">'+followButton('team',team.key,team.name)+'</div>'+
    '</article>';
  }

  function renderBriefing(){
    const host=$7('#briefingGrid');
    const status=$7('#briefingStatus');
    if(!host||!RC7.briefing)return;
    const alerts=RC7.briefing.alerts||[];
    const raceDay=RC7.briefing.race_day||[];

    if(!state?.account?.authenticated){
      status.textContent='Sign in and follow racing to turn this into your personal race briefing.';
      const featured=raceDay.slice(0,3);
      host.innerHTML=featured.length
        ?featured.map(event=>'<a class="v7-brief-card" href="'+eventHref(event)+'"><span>'+e7(event.race_day_state==='live'?'LIVE':'RACE DAY')+'</span><strong>'+e7(event.name)+'</strong><small>'+e7(event.series_name)+' · '+e7(formatDate(event.start,event.date_only))+'</small></a>').join('')
        :'<a class="v7-brief-card" href="/race-center/events"><span>RACE DAY</span><strong>Build your racing briefing</strong><small>Follow series, drivers, teams and tracks to see what matters to you.</small></a>';
      return;
    }

    status.textContent=alerts.length
      ?alerts.length+' current update'+(alerts.length===1?'':'s')+' from your followed racing.'
      :'Your follows are synced. New race-day and championship updates will appear here.';

    const cards=alerts.slice(0,6).map(item=>
      '<a class="v7-brief-card '+e7(item.kind||'')+'" href="'+e7(item.href||'/race-center')+'"><span>'+e7((item.kind||'UPDATE').toUpperCase())+'</span><strong>'+e7(item.title||'Racing update')+'</strong><small>'+e7(item.detail||'Open Race Center')+'</small></a>'
    );

    const staff=state.account?.profile?.staff;
    if(staff&&RC7.platform?.health){
      const health=RC7.platform.health;
      cards.push(
        '<article class="v7-brief-card data-health"><span>DATA HEALTH · STAFF</span><strong>'+e7(health.standings.fresh)+'/'+e7(health.standings.total)+' standings feeds fresh</strong><small>'+e7(health.identity.coverage_pct)+'% complete driver identity · '+e7(health.schedules.events_indexed)+' events · '+e7(health.schedules.tracks_indexed)+' tracks indexed</small></article>'
      );
    }
    host.innerHTML=cards.length?cards.join(''):'<div class="loading-card">Nothing urgent in your racing right now.</div>';
  }

  function renderTracks(){
    const host=$7('#tracksGrid');
    if(!host||!RC7.platform)return;
    const q=String($7('#trackSearch')?.value||'').trim().toLowerCase();
    const tracks=(RC7.platform.tracks||[]).filter(track=>
      !q||[track.name,track.location,...(track.series_names||[])].filter(Boolean).join(' ').toLowerCase().includes(q)
    );
    const count=$7('#trackResultCount');
    if(count)count.textContent=tracks.length+' track'+(tracks.length===1?'':'s')+' indexed';
    host.innerHTML=tracks.length?tracks.map(trackCard).join(''):'<div class="loading-card">No indexed tracks match that search yet.</div>';
  }

  function renderTrackProfile(){
    const host=$7('#trackProfileContent');
    if(!host||!RC7.platform||currentView()!=='trackprofile')return;
    const key=routeKey('track');
    const track=(RC7.platform.tracks||[]).find(row=>row.key===key);
    if(!track){host.innerHTML='<div class="loading-card">This track is not in the current Race Center event graph yet.</div>';return;}
    const events=(track.events||[]).slice().sort((a,b)=>String(a.start||'').localeCompare(String(b.start||'')));
    const series=(track.series_keys||[]).map(seriesKey=>{
      const item=currentSeries(seriesKey);
      return '<a class="v7-related-chip" href="/race-center/series/'+encodeURIComponent(seriesKey)+'">'+seriesLogo(seriesKey,item?.series_name||seriesKey)+'<span>'+e7(item?.series_name||seriesKey)+'</span></a>';
    }).join('');
    host.innerHTML=
      '<article class="v7-profile-hero"><div class="v7-profile-icon">⌖</div><div class="v7-profile-copy"><span class="eyebrow">TRACK</span><h2>'+e7(track.name)+'</h2><p>'+e7(track.location||'Location supplied by official event feeds when available.')+'</p><div class="v7-profile-actions">'+followButton('track',track.key,track.name)+claimButton('track',track.key,track.name)+'</div></div><div class="v7-profile-stats"><div><span>Series</span><strong>'+e7(track.series_keys.length)+'</strong></div><div><span>Indexed events</span><strong>'+e7(track.event_count)+'</strong></div><div><span>Upcoming</span><strong>'+e7(track.upcoming_count)+'</strong></div></div></article>'+
      '<div class="v7-profile-layout"><div class="v7-profile-main">'+
        '<section class="v7-panel"><span class="eyebrow">UPCOMING / RECENT</span><h3>Events at '+e7(track.name)+'</h3><div class="v7-event-list">'+(events.length?events.map(event=>eventCard(event,true)).join(''):'<div class="loading-card">No dated events are indexed yet.</div>')+'</div></section>'+
      '</div><aside class="v7-profile-aside"><section class="v7-panel"><span class="eyebrow">CONNECTED SERIES</span><h3>Who races here</h3><div class="v7-related-list">'+(series||'<p>No series connections yet.</p>')+'</div></section>'+
      '<section class="v7-panel"><span class="eyebrow">PITMARK COVERAGE</span><h3>Add context around the racing</h3><p>Track submissions, releases and Pitmark coverage can connect back to this profile without altering official event facts.</p><a class="button" href="/submit-racing-news">Submit track news</a></section></aside></div>';
  }

  function renderTeams(){
    const host=$7('#teamsGrid');
    if(!host||!RC7.platform)return;
    const q=String($7('#teamSearch')?.value||'').trim().toLowerCase();
    const teams=(RC7.platform.teams||[]).filter(team=>
      !q||[team.name,...(team.manufacturers||[]),...(team.series||[]).map(x=>x.name),...(team.drivers||[]).map(x=>x.name)].filter(Boolean).join(' ').toLowerCase().includes(q)
    );
    const count=$7('#teamResultCount');
    if(count)count.textContent=teams.length+' team'+(teams.length===1?'':'s')+' indexed';
    host.innerHTML=teams.length?teams.map(teamCard).join(''):'<div class="loading-card">No teams match that search yet.</div>';
  }

  function renderTeamProfile(){
    const host=$7('#teamProfileContent');
    if(!host||!RC7.platform||currentView()!=='teamprofile')return;
    const key=routeKey('team');
    const team=(RC7.platform.teams||[]).find(row=>row.key===key);
    if(!team){host.innerHTML='<div class="loading-card">This team is not in the current Race Center identity graph yet.</div>';return;}
    const drivers=(team.drivers||[]).map(driver=>
      '<a class="v7-driver-row" href="/race-center/driver/'+encodeURIComponent(driver.series_key)+'/'+encodeURIComponent(driver.name||'')+'">'+
        '<span>'+(driver.number?'#'+e7(driver.number):'—')+'</span><strong>'+e7(driver.name||'Driver')+'</strong><small>'+e7(driver.series_name||'Series')+'</small><em>P'+e7(driver.position||'—')+' · '+e7(driver.points||'—')+' pts</em></a>'
    ).join('');
    const series=(team.series||[]).map(item=>'<a class="v7-related-chip" href="/race-center/series/'+encodeURIComponent(item.key)+'">'+seriesLogo(item.key,item.name)+'<span>'+e7(item.name)+'</span></a>').join('');
    host.innerHTML=
      '<article class="v7-profile-hero"><div class="v7-profile-icon">T</div><div class="v7-profile-copy"><span class="eyebrow">TEAM</span><h2>'+e7(team.name)+'</h2><p>'+e7((team.manufacturers||[]).join(' · ')||'Manufacturer not published across current verified identities.')+'</p><div class="v7-profile-actions">'+followButton('team',team.key,team.name)+claimButton('team',team.key,team.name)+'</div></div><div class="v7-profile-stats"><div><span>Drivers</span><strong>'+e7(team.driver_count)+'</strong></div><div><span>Series</span><strong>'+e7(team.series_count)+'</strong></div><div><span>Manufacturers</span><strong>'+e7((team.manufacturers||[]).length)+'</strong></div></div></article>'+
      '<div class="v7-profile-layout"><div class="v7-profile-main"><section class="v7-panel"><span class="eyebrow">ROSTER</span><h3>Current Race Center drivers</h3><div class="v7-driver-list">'+(drivers||'<div class="loading-card">No connected drivers yet.</div>')+'</div></section></div>'+
      '<aside class="v7-profile-aside"><section class="v7-panel"><span class="eyebrow">SERIES</span><h3>Where they race</h3><div class="v7-related-list">'+(series||'<p>No series connections yet.</p>')+'</div></section>'+
      '<section class="v7-panel"><span class="eyebrow">OWNER-CONTROLLED CONTENT</span><h3>Claim the team page</h3><p>Verified teams can own biography, links, sponsors and announcements around source-backed results and standings.</p>'+claimButton('team',team.key,team.name)+'</section></aside></div>';
  }

  function renderEvents(){
    const host=$7('#eventsGrid');
    const hero=$7('#raceDayHero');
    if(!host||!RC7.platform)return;
    const q=String($7('#eventSearch')?.value||'').trim().toLowerCase();
    const events=(RC7.platform.events||[]).filter(event=>
      !q||[event.name,event.series_name,event.group,event.venue,event.location,event.broadcast].filter(Boolean).join(' ').toLowerCase().includes(q)
    );
    const count=$7('#eventResultCount');
    if(count)count.textContent=events.length+' event'+(events.length===1?'':'s')+' indexed';

    const raceDay=RC7.platform.race_day||[];
    if(hero){
      hero.innerHTML=raceDay.length
        ?'<div class="v7-race-day-heading"><span class="eyebrow">RACE DAY MODE</span><h3>'+e7(raceDay[0].race_day_state==='live'?'Racing is live.':'The next green flags.')+'</h3></div><div class="v7-race-day-strip">'+raceDay.slice(0,5).map(event=>eventCard(event,true)).join('')+'</div>'
        :'<div class="v7-race-day-heading"><span class="eyebrow">RACE DAY MODE</span><h3>No indexed green flag in the next 36 hours.</h3><p>Race Center will automatically elevate followed racing here as event feeds update.</p></div>';
    }
    host.innerHTML=events.length?events.slice(0,120).map(event=>eventCard(event)).join(''):'<div class="loading-card">No events match that search.</div>';
  }

  function renderEventProfile(){
    const host=$7('#eventProfileContent');
    if(!host||!RC7.platform||currentView()!=='eventprofile')return;
    const key=routeEventKey();
    const event=(RC7.platform.events||[]).find(row=>row.key===key);
    if(!event){host.innerHTML='<div class="loading-card">This event is not in the current source-backed event index.</div>';return;}
    const series=currentSeries(event.series_key);
    const top=(series?.entries||[]).slice(0,5).map(row=>
      '<a class="v7-driver-row" href="/race-center/driver/'+encodeURIComponent(event.series_key)+'/'+encodeURIComponent(row.name||'')+'"><span>P'+e7(row.position||'—')+'</span><strong>'+e7(row.name||'Driver')+'</strong><small>'+(row.number?'#'+e7(row.number):e7(row.team||''))+'</small><em>'+e7(row.points||'—')+' pts</em></a>'
    ).join('');
    const trackLink=event.track_key?'<a href="/race-center/track/'+encodeURIComponent(event.track_key)+'">'+e7(event.venue||'Track')+'</a>':e7(event.venue||'Venue not supplied');
    const resultPanel=event.completed
      ?'<section class="v7-panel"><span class="eyebrow">RESULTS</span><h3>Official event result</h3><p>Race Center does not manufacture finishing orders. Use the linked source until a structured result feed is attached to this event.</p>'+(event.source_url?'<a class="button" href="'+e7(event.source_url)+'" target="_blank" rel="noopener">Open official/source result ↗</a>':'')+'</section>'
      :'<section class="v7-panel"><span class="eyebrow">RACE STATUS</span><h3>'+e7(stateLabel(event))+'</h3><p>'+e7(formatDate(event.start,event.date_only))+(event.broadcast?' · '+e7(event.broadcast):'')+'</p></section>';
    host.innerHTML=
      '<article class="v7-event-hero '+(event.state==='in'?'is-live':'')+'"><div>'+seriesLogo(event.series_key,event.series_name)+'</div><div><span class="eyebrow">'+e7(event.state==='in'?'LIVE EVENT':'EVENT HUB')+'</span><h2>'+e7(event.name)+'</h2><p>'+e7(event.series_name)+' · '+e7(formatDate(event.start,event.date_only))+'</p><div class="v7-profile-actions">'+followButton('event',event.key,event.name,event.series_key)+claimButton('event',event.key,event.name)+(event.watch_url?'<a class="button primary" href="'+e7(event.watch_url)+'" target="_blank" rel="noopener">Watch info ↗</a>':'')+'</div></div><div class="v7-event-countdown"><span>'+e7(event.completed?'COMPLETED':event.state==='in'?'LIVE NOW':'GREEN FLAG')+'</span><strong>'+e7(event.completed?'—':event.state==='in'?'LIVE':countdown(event.start))+'</strong><small>'+trackLink+'</small></div></article>'+
      '<div class="v7-profile-layout"><div class="v7-profile-main">'+resultPanel+
        '<section class="v7-panel"><span class="eyebrow">CHAMPIONSHIP CONTEXT</span><h3>'+e7(event.series_name)+'</h3><div class="v7-driver-list">'+(top||'<div class="loading-card">Current standings are not available for this series.</div>')+'</div><a class="button" href="/race-center/series/'+encodeURIComponent(event.series_key)+'">Open series profile</a></section>'+
      '</div><aside class="v7-profile-aside"><section class="v7-panel"><span class="eyebrow">EVENT DETAILS</span><h3>What Race Center knows</h3><dl class="v7-fact-list"><div><dt>Venue</dt><dd>'+trackLink+'</dd></div><div><dt>Location</dt><dd>'+e7(event.location||'Not published')+'</dd></div><div><dt>Broadcast</dt><dd>'+e7(event.broadcast||event.watch_name||'See official source')+'</dd></div><div><dt>Status</dt><dd>'+e7(stateLabel(event))+'</dd></div></dl></section>'+
      '<section class="v7-panel"><span class="eyebrow">OFFICIAL / SOURCE LINKS</span><div class="v7-source-list">'+
        (event.source_url?'<a href="'+e7(event.source_url)+'" target="_blank" rel="noopener">Event source ↗</a>':'')+
        (event.schedule_url?'<a href="'+e7(event.schedule_url)+'" target="_blank" rel="noopener">Series schedule ↗</a>':'')+
        (event.watch_url?'<a href="'+e7(event.watch_url)+'" target="_blank" rel="noopener">Watch information ↗</a>':'')+
      '</div></section></aside></div>';
  }

  function renderArchive(){
    const host=$7('#archiveGrid');
    if(!host||!RC7.platform)return;
    const archive=RC7.platform.archive||[];
    host.innerHTML=archive.length?archive.slice(0,150).map(event=>eventCard(event)).join(''):'<div class="loading-card">No completed events are indexed in the current source-backed archive yet.</div>';
  }

  function augmentMyRacing(){
    const strip=$7('#mySeriesStrip');
    if(!strip||!RC7.platform||!state?.account?.authenticated)return;
    $$7('[data-v7-extra-follow]',strip).forEach(node=>node.remove());
    const follows=followRows().filter(row=>['track','team','event'].includes(String(row.kind)));
    follows.forEach(follow=>{
      let href='/race-center';
      let meta=String(follow.kind||'').toUpperCase();
      if(follow.kind==='track')href='/race-center/track/'+encodeURIComponent(follow.key);
      if(follow.kind==='team')href='/race-center/team/'+encodeURIComponent(follow.key);
      if(follow.kind==='event')href='/race-center/event/'+encodeURIComponent(String(follow.key).replaceAll(':','~'));
      const a=document.createElement('a');
      a.className='my-series-chip v7-extra-racing-chip';
      a.dataset.v7ExtraFollow='1';
      a.href=href;
      a.innerHTML='<span class="v7-chip-kind">'+e7(meta)+'</span><span><strong>'+e7(follow.label||follow.key)+'</strong><small>Saved to My Racing</small></span>';
      strip.appendChild(a);
    });
  }

  function renderAll(){
    renderBriefing();
    renderTracks();
    renderTrackProfile();
    renderTeams();
    renderTeamProfile();
    renderEvents();
    renderEventProfile();
    renderArchive();
    augmentMyRacing();
  }

  async function loadPlatform(){
    if(RC7.loading)return;
    RC7.loading=true;
    try{
      const [platform,briefing]=await Promise.all([
        apiJson('/api/public/race-center/platform',{method:'GET',cache:'no-store'}),
        apiJson('/api/public/race-center/briefing',{method:'GET',cache:'no-store'})
      ]);
      RC7.platform=platform;
      RC7.briefing=briefing;
      window.RaceCenterV7Platform=platform;
      window.RaceCenterV7Briefing=briefing;
      renderAll();
    }catch(error){
      ['#tracksGrid','#teamsGrid','#eventsGrid','#archiveGrid'].forEach(selector=>{
        const node=$7(selector);
        if(node)node.innerHTML='<div class="loading-card">Race Center platform data is temporarily unavailable. '+e7(error.message||'Try again shortly.')+'</div>';
      });
    }finally{
      RC7.loading=false;
    }
  }

  async function toggleFollow(button){
    const kind=String(button.dataset.v7FollowKind||'');
    const key=String(button.dataset.v7FollowKey||'');
    const label=String(button.dataset.v7FollowLabel||key);
    const seriesKey=String(button.dataset.v7FollowSeries||'');
    if(!kind||!key)return;
    if(!state?.account?.authenticated){
      $7('#accountDialog')?.showModal();
      return;
    }
    button.disabled=true;
    try{
      if(followed(kind,key))await cloudUnfollow(kind,key,label,seriesKey);
      else await cloudFollow(kind,key,label,seriesKey);
      RC7.briefing=await apiJson('/api/public/race-center/briefing',{method:'GET',cache:'no-store'});
      renderAll();
    }catch(error){
      alert(error.message||'Could not update My Racing.');
    }finally{
      button.disabled=false;
    }
  }

  function openClaim(button){
    if(!state?.account?.authenticated){
      $7('#accountDialog')?.showModal();
      return;
    }
    $7('#entityClaimType').value=button.dataset.v7ClaimType||'';
    $7('#entityClaimKey').value=button.dataset.v7ClaimKey||'';
    $7('#entityClaimName').value=button.dataset.v7ClaimName||'';
    $7('#entityClaimTitle').textContent='Claim '+(button.dataset.v7ClaimName||'this racing page');
    $7('#entityClaimMessage').textContent='';
    $7('#entityClaimDialog')?.showModal();
  }

  async function submitClaim(event){
    event.preventDefault();
    const message=$7('#entityClaimMessage');
    message.textContent='Submitting verification claim…';
    try{
      const payload=await apiJson('/api/public/race-center/entity-claims',{
        method:'POST',
        body:JSON.stringify({
          entity_type:$7('#entityClaimType').value,
          entity_key:$7('#entityClaimKey').value,
          entity_name:$7('#entityClaimName').value,
          evidence_url:$7('#entityClaimEvidence').value,
          note:$7('#entityClaimNote').value
        })
      });
      message.textContent='Claim submitted · '+String(payload.status||'pending')+'.';
      setTimeout(()=>$7('#entityClaimDialog')?.close(),900);
    }catch(error){
      message.textContent=error.message||'Could not submit claim.';
    }
  }

  function wire(){
    ['#trackSearch','#teamSearch','#eventSearch'].forEach(selector=>{
      const input=$7(selector);
      if(!input||input.dataset.v7Wired)return;
      input.dataset.v7Wired='1';
      input.addEventListener('input',renderAll);
    });
    document.addEventListener('click',event=>{
      const follow=event.target.closest('[data-v7-follow-kind]');
      if(follow){event.preventDefault();toggleFollow(follow);return;}
      const claim=event.target.closest('[data-v7-claim-type]');
      if(claim){event.preventDefault();openClaim(claim);return;}
    });
    const form=$7('#entityClaimForm');
    if(form&&!form.dataset.v7Wired){form.dataset.v7Wired='1';form.addEventListener('submit',submitClaim);}
    const close=$7('#entityClaimClose');
    if(close&&!close.dataset.v7Wired){close.dataset.v7Wired='1';close.addEventListener('click',()=>$7('#entityClaimDialog')?.close());}
  }

  function registerPwa(){
    if('serviceWorker' in navigator){
      navigator.serviceWorker.register('/race-center-sw.js?v=7',{scope:'/race-center'}).catch(()=>{});
    }
  }

  function init(){
    wire();
    registerPwa();
    try{
      if(typeof render==='function'){
        const previousRender=render;
        render=function(){
          previousRender();
          requestAnimationFrame(()=>{
            if(RC7.platform)renderAll();
          });
        };
      }
      if(typeof renderAccount==='function'){
        const previousAccount=renderAccount;
        renderAccount=function(){
          previousAccount();
          requestAnimationFrame(()=>{
            if(RC7.platform)renderAll();
          });
        };
      }
    }catch(_error){}
    loadPlatform();
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();