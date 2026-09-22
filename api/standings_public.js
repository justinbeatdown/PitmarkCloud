const routePath=(location.pathname.replace(/\/+$/,'')||'/').toLowerCase();
const pageView=routePath==='/standings'||routePath.endsWith('/standings')
  ?'standings'
  :routePath.endsWith('/schedules')
    ?'schedules'
    :routePath.endsWith('/live')
      ?'live'
      :'hub';
const PREF_KEY='pitmark-race-center-v4';
const readPrefs=()=>{
  try{
    const raw=JSON.parse(localStorage.getItem(PREF_KEY)||'{}');
    return {
      favorites:new Set(Array.isArray(raw.favorites)?raw.favorites.map(String):[]),
      lastSeries:String(raw.lastSeries||''),
      favoritesOnly:Boolean(raw.favoritesOnly)
    };
  }catch(_error){
    return {favorites:new Set(),lastSeries:'',favoritesOnly:false};
  }
};
const prefs=readPrefs();
const state={
  payload:null,group:'All',search:'',view:pageView,
  favorites:prefs.favorites,lastSeries:prefs.lastSeries,favoritesOnly:prefs.favoritesOnly
};
const savePrefs=()=>{
  try{
    localStorage.setItem(PREF_KEY,JSON.stringify({
      favorites:[...state.favorites],
      lastSeries:state.lastSeries,
      favoritesOnly:state.favoritesOnly
    }));
  }catch(_error){}
};
const $=selector=>document.querySelector(selector);
const $$=selector=>[...document.querySelectorAll(selector)];
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const fmt=new Intl.NumberFormat();
const n=value=>fmt.format(Number(value||0));
const hasValue=value=>value!==null&&value!==undefined&&String(value).trim()!=='';
const points=value=>!hasValue(value)?'—':(typeof value==='number'?fmt.format(value):esc(value));
const normalizeSearch=value=>String(value??'').trim().toLowerCase();
const numericValue=value=>{
  if(!hasValue(value))return null;
  const cleaned=String(value).replace(/,/g,'').replace(/[^0-9.+-]/g,'').trim();
  if(!cleaned)return null;
  const result=Number(cleaned);
  return Number.isFinite(result)?result:null;
};

function configurePage(){
  document.body.dataset.view=state.view;
  $('[data-race-view]').forEach(link=>{
    const active=link.dataset.raceView===state.view;
    link.classList.toggle('active',active);
    if(active)link.setAttribute('aria-current','page');
    else link.removeAttribute('aria-current');
  });

  const config={
    hub:{
      title:'Race day,<br><em>weaponized.</em>',
      intro:'Live motorsports intelligence for what is happening now, what is next, who moved, and the championships you actually follow.',
      primary:['Open standings','/race-center/standings'],
      secondary:['Find the next race','/race-center/schedules'],
      pageTitle:'Pitmark Race Center V4 — Racing Hub'
    },
    standings:{
      title:'Championships,<br><em>at a glance.</em>',
      intro:'The full Pitmark standings board with current leaders, verified position movement and source-backed championship data.',
      primary:['Browse standings','#standingsBoard'],
      secondary:['Schedules + watch','/race-center/schedules'],
      pageTitle:'Standings — Pitmark Race Center V4'
    },
    schedules:{
      title:'Race calendar,<br><em>without the hunt.</em>',
      intro:'Official schedule and viewing links across the racing world, organized into one searchable board.',
      primary:['Browse schedules','#schedules'],
      secondary:['Live + next','/race-center/live'],
      pageTitle:'Schedules — Pitmark Race Center V4'
    },
    live:{
      title:'What’s racing,<br><em>right now.</em>',
      intro:'Live events and the next races across Pitmark’s tracked series, with direct official watch and schedule links.',
      primary:['Open race weekend','#raceWeekend'],
      secondary:['Full schedules','/race-center/schedules'],
      pageTitle:'Live + Next — Pitmark Race Center V4'
    }
  }[state.view];

  $('#heroTitle').innerHTML=config.title;
  $('#heroIntro').textContent=config.intro;
  $('#heroActions').innerHTML=`<a class="button primary" href="${config.primary[1]}">${config.primary[0]}</a><a class="button secondary" href="${config.secondary[1]}">${config.secondary[0]}</a>`;
  document.title=config.pageTitle;

  const search=$('#searchInput');
  if(search){
    search.placeholder=state.view==='schedules'||state.view==='live'
      ?'Search series, event, broadcast…'
      :'Search series, driver, team…';
  }
}

const seriesMarkText=series=>{
  const key=String(series?.series_key||'');
  const special={
    'f1':'FORMULA 1','motogp':'MotoGP','moto2':'Moto2','moto3':'Moto3','worldsbk':'WorldSBK',
    'nhra-top-fuel':'NHRA','nhra-funny-car':'NHRA','nhra-pro-stock':'NHRA','nhra-pro-stock-motorcycle':'NHRA',
    'imsa-weathertech':'IMSA','imsa-michelin-pilot':'IMSA','imsa-vp-racing':'IMSA',
    'wec':'FIA WEC','formula-e':'FORMULA E','indycar':'INDYCAR',
    'world-of-outlaws-sprint':'WORLD OF OUTLAWS','world-of-outlaws-late-models':'WORLD OF OUTLAWS',
    'lucas-oil-late-models':'LOLMDS','cars-tour-lmsc':'zMAX CARS TOUR','asa-stars':'ASA STARS',
    'smart-modified':'SMART MODIFIED','high-limit-sprint':'HIGH LIMIT','arca-menards':'ARCA'
  };
  return special[key]||String(series?.short_name||series?.series_name||'RACING').toUpperCase();
};

const logoToneClass=key=>{
  const light=new Set([
    'formula-e','arca-menards','arca-east','arca-west',
    'nhra-top-fuel','nhra-funny-car','nhra-pro-stock','nhra-pro-stock-motorcycle',
    'imsa-weathertech','imsa-michelin-pilot','imsa-vp-racing',
    'imsa-porsche-carrera-cup','imsa-mustang-challenge',
    'imsa-lamborghini-super-trofeo','imsa-mx5-cup',
    'motogp','moto2','moto3','btcc'
  ]);
  return light.has(String(key||''))?'logo-light':'logo-dark';
};

const logo=series=>{
  const key=String(series?.series_key||'');
  const mark=seriesMarkText(series);
  const direct=String(series?.series_logo_direct||'').trim();
  const proxy=String(series?.series_logo||'').trim();
  const primary=direct||proxy;
  const fallback=direct&&proxy?proxy:'';
  return primary
    ?`<img class="series-logo ${logoToneClass(key)}" src="${esc(primary)}" data-direct="${esc(fallback)}" data-fallback="${esc(mark)}" loading="lazy" decoding="async" alt="${esc(series?.series_name||'Series')} logo">`
    :`<span class="series-wordmark" title="${esc(series?.series_name||'Series')}">${esc(mark)}</span>`;
};

const identityText=row=>{
  const values=[row?.team,row?.manufacturer].filter(Boolean).map(String);
  return [...new Set(values)].join(' · ');
};

const age=iso=>{
  if(!iso)return '—';
  const then=new Date(iso).getTime();
  if(!Number.isFinite(then))return '—';
  const mins=Math.max(0,Math.round((Date.now()-then)/60000));
  if(mins<2)return 'now';
  if(mins<60)return `${mins}m`;
  const hrs=Math.round(mins/60);
  if(hrs<48)return `${hrs}h`;
  return `${Math.round(hrs/24)}d`;
};

const move=(value,ready=true)=>{
  if(!ready)return '<span class="move flat" title="No prior trustworthy comparison yet">↔0</span>';
  const v=Number(value||0);
  if(!Number.isFinite(v)||v===0)return '<span class="move flat" title="No championship position change">↔0</span>';
  return v>0
    ?`<span class="move up" title="Up ${Math.abs(v)} championship position${Math.abs(v)===1?'':'s'}">▲${Math.abs(v)}</span>`
    :`<span class="move down" title="Down ${Math.abs(v)} championship position${Math.abs(v)===1?'':'s'}">▼${Math.abs(v)}</span>`;
};

const pointsDelta=(value,ready=true)=>{
  if(!ready)return '<small class="points-delta flat" title="No prior trustworthy comparison yet">Δ 0</small>';
  const v=Number(value||0);
  if(!Number.isFinite(v)||v===0)return '<small class="points-delta flat">Δ 0</small>';
  const display=fmt.format(Math.abs(v));
  return v>0
    ?`<small class="points-delta up" title="Points gained since the prior trustworthy snapshot">▲ +${display}</small>`
    :`<small class="points-delta down" title="Points lost or corrected since the prior trustworthy snapshot">▼ −${display}</small>`;
};

const eventTime=event=>{
  if(!event?.start)return '';
  const d=new Date(event.start);
  if(Number.isNaN(d.getTime()))return '';
  if(event.date_only)return d.toLocaleDateString(undefined,{month:'short',day:'numeric',timeZone:'UTC'});
  return d.toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
};

const seriesVisible=series=>{
  const groupOk=state.group==='All'||series.group===state.group;
  if(!groupOk)return false;
  if(state.favoritesOnly&&!state.favorites.has(String(series.series_key)))return false;
  const q=normalizeSearch(state.search);
  if(!q)return true;
  const hay=[
    series.series_name,series.short_name,series.group,
    ...(series.entries||[]).flatMap(row=>[row.name,row.number,row.team,row.manufacturer])
  ].filter(Boolean).join(' ').toLowerCase();
  return hay.includes(q);
};

const visibleSeries=()=> (state.payload?.series||[]).filter(seriesVisible);
const visibleSeriesKeys=()=>new Set(visibleSeries().map(series=>String(series.series_key)));

const scheduleVisible=item=>{
  if(state.group!=='All'&&item.group!==state.group)return false;
  const q=normalizeSearch(state.search);
  if(!q)return true;
  const match=(state.payload?.series||[]).find(series=>String(series.series_key)===String(item.series_key));
  if(match&&seriesVisible(match))return true;
  return [item.series_name,item.group,item.watch_name,item.event?.name].filter(Boolean).join(' ').toLowerCase().includes(q);
};

const statusBadge=series=>{
  const eventState=String(series.event_state||'').toLowerCase();
  if(eventState==='live')return '<span class="status live">LIVE NOW</span>';
  if(eventState==='next'&&series.current_event?.start)return `<span class="status next">NEXT ${esc(eventTime(series.current_event))}</span>`;
  if(series.stale)return '<span class="status cached">CACHED</span>';
  return '';
};

function miniRows(series){
  const rows=(series.entries||[]).slice(0,5);
  if(!rows.length)return '<div class="empty-card">No verified standings available.</div>';
  return `<div class="mini-table">${rows.map(row=>`<div class="mini-row">
    <span class="pos">${esc(row.position??'—')}</span>
    <span class="car-number">${row.number?esc('#'+row.number):''}</span>
    <span class="driver"><strong>${esc(row.name||'Unknown')}</strong><small>${esc(identityText(row))}</small></span>
    ${move(row.movement,row.comparison_ready!==false)}
    <span class="pts"><strong>${points(row.points)}</strong>${pointsDelta(row.points_delta,row.comparison_ready!==false)}</span>
  </div>`).join('')}</div>`;
}

function card(series){
  const leader=(series.entries||[])[0];
  const count=(series.entries||[]).length;
  const rosterCount=Math.max(count,(series.roster||[]).length);
  const key=String(series.series_key||'');
  const favorite=state.favorites.has(key);
  return `<article class="series-card" data-key="${esc(series.series_key)}" role="button" tabindex="0" aria-label="Open ${esc(series.series_name)} standings">
    <header>
      <button class="favorite-star ${favorite?'is-favorite':''}" type="button" data-favorite-key="${esc(key)}" aria-label="${favorite?'Remove':'Add'} ${esc(series.series_name)} ${favorite?'from':'to'} My Series" aria-pressed="${favorite?'true':'false'}">${favorite?'★':'☆'}</button>
      <div class="card-brand">${logo(series)}<div><span class="eyebrow">${esc(series.group||'RACING')}</span><h4>${esc(series.short_name||series.series_name)}</h4></div></div>
      ${statusBadge(series)}
    </header>
    <div class="card-leader">
      <span>Championship leader</span>
      <strong>${leader?.number?esc('#'+leader.number+' · '):''}${esc(leader?.name||'—')}</strong>
      <small>${leader?points(leader.points)+' pts'+(identityText(leader)?' · '+esc(identityText(leader)):''):'No data yet'}</small>
    </div>
    ${miniRows(series)}
    <footer><span>${rosterCount?rosterCount+' drivers':'No verified rows'}</span><strong>View full field ›</strong></footer>
  </article>`;
}

function allGroups(){
  const groups=[
    ...(state.payload?.series||[]).map(item=>item.group||'Other'),
    ...(state.payload?.events?.catalog||[]).map(item=>item.group||'Other')
  ];
  return ['All',...[...new Set(groups)]];
}

function renderFilters(){
  const series=state.payload?.series||[];
  const catalog=state.payload?.events?.catalog||[];
  $('#filters').innerHTML=allGroups().map(group=>{
    const count=group==='All'
      ?new Set([...series.map(x=>x.series_key),...catalog.map(x=>x.series_key)]).size
      :new Set([
        ...series.filter(x=>(x.group||'Other')===group).map(x=>x.series_key),
        ...catalog.filter(x=>(x.group||'Other')===group).map(x=>x.series_key)
      ]).size;
    return `<button class="filter ${state.group===group?'active':''}" type="button" data-group="${esc(group)}">${esc(group)}<span>${count}</span></button>`;
  }).join('');
}

function renderSummary(){
  const payload=state.payload||{};
  const summary=payload.summary||{};
  const total=Number(summary.series_total||payload.series?.length||0);
  const fresh=Number(summary.live||0);
  const stale=Number(summary.stale||0);
  const unavailable=Number(summary.unavailable||0);
  $('#seriesCount').textContent=n(summary.schedule_series_total||total);
  $('#liveCount').textContent=n(summary.events_live||0);
  const available=Math.max(0,total-unavailable);
  $('#feedHealth').textContent=total?`${available}/${total}`:'—';
  $('#seasonValue').textContent=`Season ${payload.season||'—'}`;
  $('#updatedValue').textContent=age(summary.last_snapshot_at||payload.generated_at);

  const status=$('#headerStatus');
  if(unavailable>0){
    status.className='header-health bad';
    status.innerHTML=`<i></i> ${unavailable} feed${unavailable===1?'':'s'} unavailable`;
  }else if(stale>0){
    status.className='header-health warn';
    status.innerHTML=`<i></i> ${fresh} fresh · ${stale} cached`;
  }else{
    status.className='header-health good';
    status.innerHTML='<i></i> Data online';
  }
}


function allMovement(){
  const movers=[];
  (state.payload?.series||[]).forEach(series=>{
    (series.entries||[]).forEach(row=>{
      if(row.comparison_ready===false)return;
      const movement=Number(row.movement||0);
      const delta=Number(row.points_delta||0);
      if(!movement&&!delta)return;
      movers.push({series,row,movement,delta,score:Math.abs(movement)*100000+Math.abs(delta)});
    });
  });
  return movers.sort((a,b)=>b.score-a.score);
}

function nextEventAcrossBoard(){
  const next=state.payload?.events?.next||[];
  return next
    .filter(item=>item?.event?.start)
    .map(item=>({...item,_time:new Date(item.event.start).getTime()}))
    .filter(item=>Number.isFinite(item._time))
    .sort((a,b)=>a._time-b._time)[0]||null;
}

function countdownText(timestamp){
  if(!Number.isFinite(timestamp))return '—';
  const diff=timestamp-Date.now();
  if(diff<=0)return 'NOW';
  const mins=Math.floor(diff/60000);
  const days=Math.floor(mins/1440);
  const hours=Math.floor((mins%1440)/60);
  const rem=mins%60;
  if(days>0)return `${days}d ${hours}h`;
  if(hours>0)return `${hours}h ${rem}m`;
  return `${Math.max(1,rem)}m`;
}

function renderMySeries(){
  const shell=$('#mySeriesShell');
  const strip=$('#mySeriesStrip');
  const hint=$('#mySeriesHint');
  if(!shell||!strip||!hint)return;
  const series=(state.payload?.series||[]).filter(item=>state.favorites.has(String(item.series_key)));
  $('#pulseFavorites').textContent=String(series.length);
  $('#pulseFavoriteText').textContent=series.length
    ?`${series.length} saved championship${series.length===1?'':'s'}`
    :'Star a series to build your board';
  if(!series.length){
    strip.innerHTML='<button class="my-series-chip" id="emptyFavoriteCta" type="button"><span class="series-wordmark">START</span><span><strong>Build My Series</strong><small>Star the championships you care about.</small></span></button>';
    hint.textContent='Your saved championships live here.';
    return;
  }
  hint.textContent='Saved locally on this device.';
  strip.innerHTML=series.map(item=>{
    const leader=item.entries?.[0];
    const event=item.current_event;
    const meta=event
      ?`${item.event_state==='live'?'LIVE · ':''}${event.name||eventWhen(event)}`
      :leader?`Leader: ${leader.name||'—'}`:'Open championship';
    return `<button class="my-series-chip" type="button" data-key="${esc(item.series_key)}">${logo(item)}<span><strong>${esc(item.short_name||item.series_name)}</strong><small>${esc(meta)}</small></span></button>`;
  }).join('');
}

function renderPulse(){
  if(!state.payload)return;
  const events=state.payload.events||{};
  const live=events.live||[];
  const next=nextEventAcrossBoard();
  const movers=allMovement();
  $('#pulseLive').textContent=String(live.length);
  $('#pulseLiveText').textContent=live.length
    ?`${live.slice(0,2).map(item=>item.series_name).filter(Boolean).join(' · ')}${live.length>2?' +'+(live.length-2):''}`
    :'No tracked series are live right now';
  $('#pulseMoves').textContent=String(movers.length);
  $('#pulseCountdown').textContent=next?countdownText(next._time):'—';
  $('#pulseNextText').textContent=next
    ?`${next.series_name||'Series'} · ${next.event?.name||'next event'}`
    :'No upcoming start time available';
  renderMySeries();
  const favoriteButton=$('#favoritesFilter');
  if(favoriteButton){
    favoriteButton.setAttribute('aria-pressed',state.favoritesOnly?'true':'false');
    favoriteButton.textContent=state.favoritesOnly?'★ My Series':'☆ My Series';
  }
}

function renderLeaders(){
  const leaders=visibleSeries().filter(series=>series.entries?.length).slice(0,state.view==='hub'?4:8);
  $('#leaderStrip').innerHTML=leaders.length?leaders.map(series=>{
    const leader=series.entries[0];
    return `<article class="leader-card" data-key="${esc(series.series_key)}" role="button" tabindex="0">
      <div class="leader-brand">${logo(series)}<span class="series">${esc(series.short_name||series.series_name)}</span></div>
      <div>
        <strong>${leader.number?esc('#'+leader.number+' · '):''}${esc(leader.name||'—')}</strong>
        <div class="points">${points(leader.points)} pts</div>
        <small>${esc(identityText(leader)||series.group||'')}</small>
      </div>
    </article>`;
  }).join(''):'<div class="loading-card">No championship leaders match this view.</div>';
}

function renderMovers(){
  const movers=allMovement().filter(item=>visibleSeriesKeys().has(String(item.series.series_key)));
  const top=movers.slice(0,state.view==='hub'?4:8);
  $('#moversStrip').innerHTML=top.length?top.map(item=>`<article class="mover-card" data-key="${esc(item.series.series_key)}" role="button" tabindex="0">
    <span class="mover-rank">${esc(item.row.position??'—')}</span>
    <div><strong>${esc(item.row.name||'Unknown')}</strong><small>${esc(item.series.short_name||item.series.series_name)}</small></div>
    <div class="mover-change">${move(item.movement,true)}${pointsDelta(item.delta,true)}</div>
  </article>`).join(''):'<div class="loading-card">No verified championship movement since the previous trustworthy snapshot.</div>';
}

function renderGroups(){
  const visible=visibleSeries();
  const groups=[...new Set(visible.map(series=>series.group||'Other'))];
  $('#seriesGroups').innerHTML=groups.length?groups.map(group=>{
    const items=visible.filter(series=>(series.group||'Other')===group);
    return `<section class="group">
      <div class="group-head"><h3>${esc(group)}</h3><span>${items.length} championship${items.length===1?'':'s'}</span></div>
      <div class="series-grid">${items.map(card).join('')}</div>
    </section>`;
  }).join(''):'<div class="loading-card">Nothing matched that search.</div>';

  const fresh=visible.filter(item=>!item.stale&&item.status!=='unavailable').length;
  const cached=visible.filter(item=>item.stale).length;
  $('#statusText').textContent=`${visible.length} championship${visible.length===1?'':'s'} shown · ${fresh} fresh${cached?' · '+cached+' cached':''}`;
  $('#resultCount').textContent=state.group==='All'
    ?`${visible.length} championships`
    :`${state.group} · ${visible.length}`;
}

function bindLogoErrors(){
  $$('.series-logo').forEach(img=>{
    if(img.dataset.logoBound)return;
    img.dataset.logoBound='1';
    img.addEventListener('error',()=>{
      const fallback=img.dataset.direct||'';
      if(fallback&&!img.dataset.directTried){
        img.dataset.directTried='1';
        img.src=fallback;
        return;
      }
      const span=document.createElement('span');
      span.className='series-wordmark event-wordmark';
      span.title=img.alt||'Series';
      span.textContent=img.dataset.fallback||'RACING';
      img.replaceWith(span);
    });
  });
}

function eventLogo(item){
  const matching=(state.payload?.series||[]).find(series=>String(series.series_key)===String(item?.series_key));
  if(matching)return logo(matching);
  const direct=String(item?.logo_url||'').trim();
  const mark=seriesMarkText({series_key:item?.series_key,series_name:item?.series_name,short_name:item?.series_name});
  if(direct){
    return `<img class="series-logo event-series-logo ${logoToneClass(item?.series_key)}" src="${esc(direct)}" data-fallback="${esc(mark)}" loading="lazy" decoding="async" alt="${esc(item?.series_name||'Series')} logo">`;
  }
  return `<span class="series-wordmark event-wordmark" title="${esc(item?.series_name||'Series')}">${esc(mark)}</span>`;
}

function eventWhen(event){return event?.start?eventTime(event):'See official schedule';}

function eventCard(item){
  const event=item?.event||{};
  const live=item?.state==='live';
  const hasStandings=(state.payload?.series||[]).some(series=>String(series.series_key)===String(item.series_key));
  return `<article class="event-card ${live?'is-live':''}" ${hasStandings?`data-key="${esc(item.series_key)}" role="button" tabindex="0"`:''}>
    <div class="event-brand">${eventLogo(item)}<div><span class="eyebrow">${live?'LIVE NOW':'NEXT UP'}</span><h3>${esc(item.series_name||'Series')}</h3></div></div>
    <strong>${esc(event.name||'Official schedule')}</strong>
    <p>${esc(eventWhen(event))}${item.watch_name?' · '+esc(item.watch_name):''}</p>
    <div class="event-actions">
      ${item.watch_url?`<a href="${esc(item.watch_url)}" target="_blank" rel="noopener">Watch info ↗</a>`:''}
      ${item.schedule_url?`<a href="${esc(item.schedule_url)}" target="_blank" rel="noopener">Schedule ↗</a>`:''}
    </div>
  </article>`;
}

function renderEvents(){
  const events=state.payload?.events||{};
  const keys=visibleSeriesKeys();
  const filterItem=item=>{
    if(state.group!=='All'&&item.group!==state.group)return false;
    if(!normalizeSearch(state.search))return true;
    return keys.has(String(item.series_key))||scheduleVisible(item);
  };
  const live=(events.live||[]).filter(filterItem);
  const next=(events.next||[]).filter(filterItem);
  $('#eventStatusText').textContent=live.length
    ?`${live.length} event${live.length===1?'':'s'} live right now`
    :next.length?'Nothing live in this view — here’s what’s next.':'No upcoming events match this view.';
  $('#liveNow').innerHTML=live.length?`<div class="live-grid">${live.map(eventCard).join('')}</div>`:'';
  const nextLimit=state.view==='hub'?4:12;
  $('#nextEvents').innerHTML=next.length?next.slice(0,nextLimit).map(eventCard).join(''):'<div class="loading-card">No upcoming events match this view.</div>';
}

function renderScheduleCatalog(){
  const catalog=(state.payload?.events?.catalog||[]).filter(scheduleVisible);
  $('#scheduleCatalog').innerHTML=catalog.length?catalog.map(item=>{
    const hasStandings=(state.payload?.series||[]).some(series=>String(series.series_key)===String(item.series_key));
    return `<article class="schedule-card" ${hasStandings?`data-key="${esc(item.series_key)}" role="button" tabindex="0"`:''}>
      <div class="event-brand">${eventLogo(item)}<div><span class="eyebrow">${esc(item.group||'RACING')}</span><h3>${esc(item.series_name||'Series')}</h3></div></div>
      <p>${item.state==='live'?'LIVE NOW':item.state==='next'&&item.event?.start?'Next: '+esc(eventTime(item.event)):'Official 2026 schedule'}</p>
      <div class="event-actions">
        ${item.schedule_url?`<a href="${esc(item.schedule_url)}" target="_blank" rel="noopener">Schedule ↗</a>`:''}
        ${item.watch_url?`<a href="${esc(item.watch_url)}" target="_blank" rel="noopener">${esc(item.watch_name||'Where to watch')} ↗</a>`:''}
      </div>
    </article>`;
  }).join(''):'<div class="loading-card">No schedules match this view.</div>';
  $('#scheduleStatusText').textContent=`${catalog.length} series schedule${catalog.length===1?'':'s'} in this view · official links when available`;
}

function render(){
  renderSummary();
  renderPulse();
  renderFilters();
  renderEvents();
  renderLeaders();
  renderMovers();
  renderGroups();
  renderScheduleCatalog();
  bindLogoErrors();
  $('#clearSearch').hidden=!normalizeSearch(state.search);

  if(state.view==='schedules'){
    const count=(state.payload?.events?.catalog||[]).filter(scheduleVisible).length;
    $('#resultCount').textContent=`${count} schedules`;
  }else if(state.view==='live'){
    const events=state.payload?.events||{};
    const matches=[...(events.live||[]),...(events.next||[])].filter(item=>{
      if(state.group!=='All'&&item.group!==state.group)return false;
      return !normalizeSearch(state.search)||scheduleVisible(item);
    });
    $('#resultCount').textContent=`${matches.length} live / upcoming`;
  }
}

function openSeries(key){
  state.lastSeries=String(key||'');
  savePrefs();
  const series=(state.payload?.series||[]).find(item=>String(item.series_key)===String(key));
  if(!series)return;
  const rows=(series.entries||[]).map(row=>({...row}));
  const roster=(series.roster||[]).map(row=>({...row}));
  const rosterCount=Math.max(rows.length,roster.length);
  const rosterOnly=roster.filter(row=>row.in_standings===false);
  const leaderPoints=rows.length?numericValue(rows[0]?.points):null;

  rows.forEach(row=>{
    if(!hasValue(row.behind)&&leaderPoints!==null){
      const rowPoints=numericValue(row.points);
      if(rowPoints!==null)row._derivedBehind=Math.max(0,leaderPoints-rowPoints);
    }
  });

  const any=field=>rows.some(row=>hasValue(row[field]));
  const anyBehind=rows.some(row=>hasValue(row.behind)||row._derivedBehind!==undefined);
  const columns=[
    {key:'position',label:'Pos',always:true,cell:row=>`<strong>${esc(row.position??'—')}</strong>`},
    {key:'number',label:'#',show:any('number'),cell:row=>`<strong>${esc(row.number||'—')}</strong>`},
    {key:'movement',label:'Move',always:true,cell:row=>move(row.movement,row.comparison_ready!==false)},
    {key:'name',label:'Driver',always:true,cell:row=>`<strong>${esc(row.name||'Unknown')}</strong>`},
    {key:'team',label:'Team',show:any('team'),cell:row=>esc(row.team||'—')},
    {key:'manufacturer',label:'Manufacturer',show:any('manufacturer'),cell:row=>esc(row.manufacturer||'—')},
    {key:'points',label:'Points',always:true,cell:row=>`<strong>${points(row.points)}</strong>${pointsDelta(row.points_delta,row.comparison_ready!==false)}`},
    {key:'behind',label:'Behind',show:anyBehind,cell:row=>{
      if(hasValue(row.behind))return points(row.behind);
      if(row._derivedBehind!==undefined)return row._derivedBehind===0?'LEADER':points(row._derivedBehind);
      return '—';
    }},
    {key:'wins',label:'Wins',show:any('wins'),cell:row=>points(row.wins)},
    {key:'starts',label:'Starts',show:any('starts'),cell:row=>points(row.starts)}
  ].filter(column=>column.always||column.show);

  const body=rows.length
    ?`<div class="table-wrap adaptive-table cols-${columns.length}"><table>
      <thead><tr>${columns.map(column=>`<th data-col="${esc(column.key)}">${esc(column.label)}</th>`).join('')}</tr></thead>
      <tbody>${rows.map(row=>`<tr>${columns.map(column=>`<td data-col="${esc(column.key)}">${column.cell(row)}</td>`).join('')}</tr>`).join('')}</tbody>
    </table></div>`
    :'<div class="loading-card">No verified current standings are available from this source.</div>';

  const rosterSupplement=rosterOnly.length
    ?`<section class="roster-supplement">
      <div class="roster-head"><div><span class="eyebrow">SEASON ROSTER</span><h3>Additional full-time competitors</h3></div><small>${rosterOnly.length} not exposed in the source's points table</small></div>
      <div class="roster-grid">${rosterOnly.map(row=>`<div class="roster-person">
        <strong>${row.number?esc('#'+row.number+' · '):''}${esc(row.name||'Unknown')}</strong>
        <small>${esc([row.team,row.manufacturer].filter(Boolean).join(' · ')||'Full-time series competitor')}</small>
      </div>`).join('')}</div>
    </section>`
    :'';

  const leader=rows[0];
  const summary=`<div class="dialog-summary">
    <div><span>Leader</span><strong>${esc(leader?.name||'—')}</strong></div>
    <div><span>Roster</span><strong>${rosterCount?rosterCount+' drivers':'—'}</strong></div>
    <div><span>Data</span><strong>${series.stale?'Cached snapshot':'Current snapshot'}</strong></div>
    <div><span>Updated</span><strong>${esc(age(series.fetched_at))} ago</strong></div>
  </div>`;

  const identitySource=series.metadata_source_url?`<a class="official-link identity-source" href="${esc(series.metadata_source_url)}" target="_blank" rel="noopener">Identity source ↗</a>`:'';
  const logoSource=series.series_logo_source_url?`<a class="official-link identity-source" href="${esc(series.series_logo_source_url)}" target="_blank" rel="noopener">Logo source ↗</a>`:'';
  const scheduleLink=series.schedule_url?`<a class="official-link" href="${esc(series.schedule_url)}" target="_blank" rel="noopener">Official schedule ↗</a>`:'';
  const watchLink=series.watch_url?`<a class="official-link" href="${esc(series.watch_url)}" target="_blank" rel="noopener">${esc(series.watch_name||'Where to watch')} ↗</a>`:'';
  const eventLine=series.current_event?`<div class="dialog-event ${series.event_state==='live'?'is-live':''}">
    <span class="eyebrow">${series.event_state==='live'?'LIVE NOW':'NEXT / RECENT'}</span>
    <strong>${esc(series.current_event.name||'Event')}</strong>
    <small>${series.current_event.start?esc(eventTime(series.current_event)):''}</small>
  </div>`:'';

  $('#dialogContent').innerHTML=`<div class="dialog-title">
    <div class="dialog-brand">${logo(series)}<div>
      <span class="eyebrow">${esc(series.group||'RACING')} · ${esc(series.season||'')}</span>
      <h2 id="dialogSeriesTitle">${esc(series.series_name||'Standings')}</h2>
      <p>${esc(series.source_name||'Series standings')} · updated ${esc(age(series.fetched_at))} ago</p>
    </div></div>
  </div>
  ${eventLine}${summary}${body}${rosterSupplement}
  <div class="source-links">
    ${scheduleLink}${watchLink}
    ${series.official_url?`<a class="official-link" href="${esc(series.official_url)}" target="_blank" rel="noopener">Official standings ↗</a>`:''}
    ${identitySource}${logoSource}
  </div>`;

  bindLogoErrors();
  const dialog=$('#standingsDialog');
  document.body.classList.add('dialog-open');
  dialog.showModal();
  $('#dialogClose').focus({preventScroll:true});
}

function setLoadError(message){
  $('#headerStatus').className='header-health bad';
  $('#headerStatus').innerHTML='<i></i> Feed unavailable';
  $('#leaderStrip').innerHTML=`<div class="loading-card">${esc(message)}</div>`;
  $('#moversStrip').innerHTML='<div class="loading-card">Movement history unavailable.</div>';
  $('#seriesGroups').innerHTML='<div class="loading-card">Standings temporarily unavailable.</div>';
  $('#scheduleCatalog').innerHTML='<div class="loading-card">Schedules temporarily unavailable.</div>';
  $('#nextEvents').innerHTML='<div class="loading-card">Events temporarily unavailable.</div>';
  $('#statusText').textContent=message;
}

async function load(){
  try{
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),10000);
    const response=await fetch('/api/public/standings?v=race-center-v4-20260922',{
      headers:{Accept:'application/json'},
      cache:'no-store',
      signal:controller.signal
    });
    clearTimeout(timeout);
    if(!response.ok)throw new Error('Race Center feed unavailable');
    state.payload=await response.json();
    render();
  }catch(error){
    setLoadError(error?.name==='AbortError'?'Race Center timed out. Refresh to retry.':(error.message||'Unable to load Race Center.'));
  }
}

let searchTimer=null;
const applySearch=value=>{
  state.search=String(value??'');
  clearTimeout(searchTimer);
  searchTimer=setTimeout(()=>{
    renderEvents();
    renderLeaders();
    renderMovers();
    renderGroups();
    renderScheduleCatalog();
    bindLogoErrors();
    $('#clearSearch').hidden=!normalizeSearch(state.search);
  },70);
};

function safeBind(selector,eventName,handler){
  const el=$(selector);
  if(el)el.addEventListener(eventName,handler);
}

function bootRaceCenter(){
  // Kick off the data request first. UI wiring must never be allowed to block it.
  load();
  setInterval(()=>{if(state.payload)renderPulse();},30000);

  try{configurePage();}catch(error){
    console.error('Race Center page configuration failed',error);
  }

  document.addEventListener('click',event=>{
    const favorite=event.target.closest('[data-favorite-key]');
    if(favorite){
      event.preventDefault();
      event.stopPropagation();
      const key=String(favorite.dataset.favoriteKey||'');
      if(state.favorites.has(key))state.favorites.delete(key);else state.favorites.add(key);
      savePrefs();
      render();
      return;
    }
    const filter=event.target.closest('[data-group]');
    if(filter){
      state.group=filter.dataset.group;
      render();
      return;
    }
    if(event.target.closest('a,button,input'))return;
    const card=event.target.closest('[data-key]');
    if(card)openSeries(card.dataset.key);
  });

  document.addEventListener('keydown',event=>{
    if(event.key==='/'&&!event.ctrlKey&&!event.metaKey&&!event.altKey&&document.activeElement?.tagName!=='INPUT'){
      event.preventDefault();
      const input=$('#searchInput');
      input?.focus();
      return;
    }
    if(event.key!=='Enter'&&event.key!==' ')return;
    const card=event.target.closest('[data-key]');
    if(!card||event.target.closest('a,button,input'))return;
    event.preventDefault();
    openSeries(card.dataset.key);
  });

  document.addEventListener('input',event=>{
    if(event.target?.id==='searchInput')applySearch(event.target.value);
  });
  document.addEventListener('search',event=>{
    if(event.target?.id==='searchInput')applySearch(event.target.value);
  });

  safeBind('#favoritesFilter','click',()=>{
    state.favoritesOnly=!state.favoritesOnly;
    savePrefs();
    render();
  });
  safeBind('#focusFavorites','click',()=>{
    state.favoritesOnly=true;
    savePrefs();
    render();
    $('#standingsStart')?.scrollIntoView({behavior:'smooth',block:'start'});
  });
  const focusSearch=()=>{
    const input=$('#searchInput');
    input?.focus({preventScroll:false});
    input?.scrollIntoView({behavior:'smooth',block:'center'});
  };
  safeBind('#jumpSearch','click',focusSearch);
  safeBind('#mobileSearch','click',focusSearch);
  safeBind('#mobileFavorites','click',()=>{
    state.favoritesOnly=true;
    savePrefs();
    render();
    $('#standingsStart')?.scrollIntoView({behavior:'smooth',block:'start'});
  });

  safeBind('#clearSearch','click',()=>{
    const input=$('#searchInput');
    if(input)input.value='';
    state.search='';
    if(state.payload)render();
    if(input)input.focus();
  });

  safeBind('#dialogClose','click',()=>{
    const dialog=$('#standingsDialog');
    if(dialog?.open)dialog.close();
  });

  const dialog=$('#standingsDialog');
  if(dialog){
    dialog.addEventListener('click',event=>{
      if(event.target===dialog&&dialog.open)dialog.close();
    });
    dialog.addEventListener('close',()=>document.body.classList.remove('dialog-open'));
  }

  document.addEventListener('click',event=>{
    const emptyCta=event.target.closest('#emptyFavoriteCta');
    if(emptyCta){
      state.favoritesOnly=false;
      savePrefs();
      render();
      $('#standingsStart')?.scrollIntoView({behavior:'smooth',block:'start'});
    }
  });

  const backToTop=$('#backToTop');
  if(backToTop){
    window.addEventListener('scroll',()=>{
      backToTop.hidden=window.scrollY<900;
    },{passive:true});
    backToTop.addEventListener('click',()=>window.scrollTo({top:0,behavior:'smooth'}));
  }
}

if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',bootRaceCenter,{once:true});
}else{
  bootRaceCenter();
}
