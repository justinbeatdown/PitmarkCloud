const routePath=(location.pathname.replace(/\/+$/,'')||'/').toLowerCase();
const pageView=routePath==='/standings'||routePath.endsWith('/standings')
  ?'standings'
  :routePath.endsWith('/schedules')
    ?'schedules'
    :routePath.endsWith('/live')
      ?'live'
      :routePath.includes('/race-center/driver/')
        ?'driver'
        :routePath.endsWith('/drivers')
          ?'drivers'
          :'hub';
const PREF_KEY='pitmark-race-center-v5';
const CACHE_KEY='pitmark-race-center-v5-feed';
const readPrefs=()=>{
  try{
    const raw=JSON.parse(localStorage.getItem(PREF_KEY)||'{}');
    return {
      favorites:new Set(Array.isArray(raw.favorites)?raw.favorites.map(String):[]),
      drivers:new Set(Array.isArray(raw.drivers)?raw.drivers.map(String):[]),
      lastSeries:String(raw.lastSeries||''),
      favoritesOnly:Boolean(raw.favoritesOnly)
    };
  }catch(_error){
    return {favorites:new Set(),drivers:new Set(),lastSeries:'',favoritesOnly:false};
  }
};
const prefs=readPrefs();
const state={
  payload:null,group:'All',search:'',driverSearch:'',view:pageView,
  favorites:prefs.favorites,drivers:prefs.drivers,lastSeries:prefs.lastSeries,favoritesOnly:prefs.favoritesOnly,
  account:null,socialPosts:[]
};
const readCachedPayload=()=>{
  try{
    const raw=JSON.parse(localStorage.getItem(CACHE_KEY)||'null');
    if(!raw?.payload||!raw?.savedAt)return null;
    if(Date.now()-Number(raw.savedAt)>6*60*60*1000)return null;
    return raw.payload;
  }catch(_error){return null;}
};
const saveCachedPayload=payload=>{
  try{localStorage.setItem(CACHE_KEY,JSON.stringify({savedAt:Date.now(),payload}));}catch(_error){}
};
const savePrefs=()=>{
  try{
    localStorage.setItem(PREF_KEY,JSON.stringify({
      favorites:[...state.favorites],
      drivers:[...state.drivers],
      lastSeries:state.lastSeries,
      favoritesOnly:state.favoritesOnly
    }));
  }catch(_error){}
};

const apiJson=async(url,options={})=>{
  const response=await fetch(url,{
    ...options,
    headers:{'Content-Type':'application/json',Accept:'application/json',...(options.headers||{})},
    credentials:'same-origin'
  });
  let payload={};
  try{payload=await response.json();}catch(_error){}
  if(!response.ok)throw new Error(payload.detail||payload.message||'Request failed');
  return payload;
};

const accountSeriesFollows=()=>new Set((state.account?.follows||[]).filter(x=>x.kind==='series').map(x=>String(x.key)));
const accountDriverFollows=()=>new Set((state.account?.follows||[]).filter(x=>x.kind==='driver').map(x=>String(x.key)));

function mergeAccountFollows(){
  if(!state.account?.authenticated)return;
  accountSeriesFollows().forEach(key=>state.favorites.add(key));
  accountDriverFollows().forEach(key=>state.drivers.add(key));
  savePrefs();
}

function renderAccount(){
  const button=$('#accountButton');
  const loggedOut=$('#accountLoggedOut');
  const loggedIn=$('#accountLoggedIn');
  if(!button||!loggedOut||!loggedIn)return;
  const authed=Boolean(state.account?.authenticated);
  button.textContent=authed
    ?(state.account.display_name||state.account.email||'My Race Center')
    :'My Race Center';
  loggedOut.hidden=authed;
  loggedIn.hidden=!authed;
  if(authed){
    const follows=state.account.follows||[];
    $('#accountWelcome').textContent=`Welcome${state.account.display_name?' back, '+state.account.display_name:''}.`;
    $('#accountIdentity').textContent=state.account.email||'Your racing board is synced.';
    $('#accountSeriesCount').textContent=String(follows.filter(x=>x.kind==='series').length);
    $('#accountDriverCount').textContent=String(follows.filter(x=>x.kind==='driver').length);
    const publicProfile=$('#viewPublicProfile');
    const handle=state.account.profile&&state.account.profile.handle;
    if(publicProfile&&handle)publicProfile.href='/race-center/u/'+encodeURIComponent(handle);
  }
}

async function syncAccount(){
  try{
    state.account=await apiJson('/api/public/race-center/account',{method:'GET'});
    mergeAccountFollows();
  }catch(_error){
    state.account={authenticated:false,follows:[]};
  }
  renderAccount();
  if(state.payload)render();
}

async function cloudFollow(kind,key,label='',seriesKey=''){
  if(!state.account?.authenticated)return;
  const payload=await apiJson('/api/public/race-center/follows',{
    method:'PUT',
    body:JSON.stringify({kind,key,label,series_key:seriesKey})
  });
  state.account.follows=payload.follows||[];
  renderAccount();
}

async function cloudUnfollow(kind,key,label='',seriesKey=''){
  if(!state.account?.authenticated)return;
  const payload=await apiJson('/api/public/race-center/follows',{
    method:'DELETE',
    body:JSON.stringify({kind,key,label,series_key:seriesKey})
  });
  state.account.follows=payload.follows||[];
  renderAccount();
}

function driverFollowKey(series,row){
  return `${String(series?.series_key||'series')}:${String(row?.name||'driver').trim().toLowerCase()}`;
}

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
  $$('[data-race-view]').forEach(link=>{
    const active=link.dataset.raceView===state.view||(state.view==='driver'&&link.dataset.raceView==='drivers');
    link.classList.toggle('active',active);
    if(active)link.setAttribute('aria-current','page');
    else link.removeAttribute('aria-current');
  });

  const config={
    hub:{
      title:'All of racing.<br><em>One home base.</em>',
      intro:'See what is live, what is next, who leads, and where the championships stand — without digging through a dozen different sites.',
      primary:['Open standings','/race-center/standings'],
      secondary:['Find the next race','/race-center/schedules'],
      pageTitle:'Pitmark Race Center — Racing Standings, Schedules + Live'
    },
    drivers:{
      title:'Find a driver.<br><em>Know their racing.</em>',
      intro:'Search the drivers already inside Race Center by name, number, team, manufacturer, or series — then open a source-backed driver profile.',
      primary:['Search drivers','#driversDirectory'],
      secondary:['Open standings','/race-center/standings'],
      pageTitle:'Drivers — Pitmark Race Center'
    },
    driver:{
      title:'Driver profile.<br><em>Source backed.</em>',
      intro:'Official racing data stays source-backed. Claimed drivers can own the personality, photo, links and story around it.',
      primary:['All drivers','/race-center/drivers'],
      secondary:['Standings','/race-center/standings'],
      pageTitle:'Driver Profile — Pitmark Race Center'
    },
    standings:{
      title:'Championships,<br><em>at a glance.</em>',
      intro:'The full Pitmark standings board with current leaders, verified position movement and source-backed championship data.',
      primary:['Browse standings','#standingsBoard'],
      secondary:['Schedules + watch','/race-center/schedules'],
      pageTitle:'Standings — Pitmark Race Center V5'
    },
    schedules:{
      title:'Race calendar,<br><em>without the hunt.</em>',
      intro:'Official schedule and viewing links across the racing world, organized into one searchable board.',
      primary:['Browse schedules','#schedules'],
      secondary:['Live + next','/race-center/live'],
      pageTitle:'Schedules — Pitmark Race Center V5'
    },
    live:{
      title:'What’s racing,<br><em>right now.</em>',
      intro:'Live events and the next races across Pitmark’s tracked series, with direct official watch and schedule links.',
      primary:['Open race weekend','#raceWeekend'],
      secondary:['Full schedules','/race-center/schedules'],
      pageTitle:'Live + Next — Pitmark Race Center V5'
    }
  }[state.view]||{
    title:'All of racing.<br><em>One home base.</em>',
    intro:'Race Center keeps racing information organized in one place.',
    primary:['Race Center','/race-center'],
    secondary:['Standings','/race-center/standings'],
    pageTitle:'Pitmark Race Center'
  };

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

const driverProfileHref=(seriesKey,name)=>'/race-center/driver/'+encodeURIComponent(String(seriesKey||''))+'/'+encodeURIComponent(String(name||''));

function driverDirectoryRows(){
  const rows=[];
  (state.payload?.series||[]).forEach(series=>{
    const seen=new Set();
    const candidates=[...(series.entries||[]),...(series.roster||[])];
    candidates.forEach(row=>{
      const name=String(row?.name||'').trim();
      if(!name)return;
      const localKey=name.toLowerCase();
      if(seen.has(localKey))return;
      seen.add(localKey);
      rows.push({
        key:driverFollowKey(series,row),
        name,
        number:String(row.number||'').trim(),
        team:String(row.team||'').trim(),
        manufacturer:String(row.manufacturer||'').trim(),
        position:row.position,
        points:row.points,
        series_key:String(series.series_key||''),
        series_name:String(series.series_name||''),
        series_short:String(series.short_name||series.series_name||''),
        group:String(series.group||'RACING'),
        photo_url:row.photo_use_allowed===true?String(row.photo_url||''):'',
        photo_source_url:row.photo_use_allowed===true?String(row.photo_source_url||''):'',
      });
    });
  });
  return rows.sort((a,b)=>a.name.localeCompare(b.name)||a.series_short.localeCompare(b.series_short));
}

function driverInitials(name){
  return String(name||'?').split(/\s+/).filter(Boolean).map(x=>x[0]||'').join('').slice(0,2).toUpperCase()||'?';
}

function driverPortrait(driver,large=false){
  if(driver.photo_url){
    return '<img class="driver-photo'+(large?' is-large':'')+'" src="'+esc(driver.photo_url)+'" alt="'+esc(driver.name)+'" loading="lazy" decoding="async">';
  }
  return '<span class="driver-photo driver-photo-fallback'+(large?' is-large':'')+'">'+esc(driverInitials(driver.name))+'</span>';
}

function renderDrivers(){
  const grid=$('#driversGrid');
  if(!grid||!state.payload)return;
  const q=normalizeSearch(state.driverSearch);
  const all=driverDirectoryRows();
  const filtered=q?all.filter(driver=>[
    driver.name,driver.number,driver.team,driver.manufacturer,driver.series_name,driver.series_short,driver.group
  ].filter(Boolean).join(' ').toLowerCase().includes(q)):all;
  const count=$('#driverResultCount');
  if(count)count.textContent=filtered.length+' driver profile'+(filtered.length===1?'':'s');

  grid.innerHTML=filtered.length?filtered.slice(0,600).map(driver=>{
    const followed=state.drivers.has(driver.key);
    return '<article class="driver-directory-card">'+
      '<a class="driver-directory-main" href="'+driverProfileHref(driver.series_key,driver.name)+'">'+
        driverPortrait(driver)+
        '<div><span class="driver-number">'+(driver.number?'#'+esc(driver.number):esc(driver.series_short))+'</span>'+
        '<strong>'+esc(driver.name)+'</strong>'+
        '<small>'+esc([driver.team,driver.manufacturer].filter(Boolean).join(' · ')||driver.series_short)+'</small>'+
        '<em>'+esc(driver.series_short)+(driver.position?' · P'+esc(driver.position):'')+'</em></div>'+
      '</a>'+
      '<button class="driver-directory-follow '+(followed?'is-following':'')+'" type="button" data-driver-follow="'+esc(driver.key)+'" data-driver-label="'+esc(driver.name)+'" data-driver-series="'+esc(driver.series_key)+'" aria-pressed="'+(followed?'true':'false')+'" aria-label="'+(followed?'Unfollow ':'Follow ')+esc(driver.name)+'">'+(followed?'★':'☆')+'</button>'+
    '</article>';
  }).join(''):'<div class="loading-card">No drivers match that search.</div>';
}

function currentDriverRoute(){
  const marker='/race-center/driver/';
  const path=decodeURI(location.pathname);
  const index=path.indexOf(marker);
  if(index<0)return null;
  const rest=path.slice(index+marker.length);
  const slash=rest.indexOf('/');
  if(slash<0)return null;
  return {
    series_key:decodeURIComponent(rest.slice(0,slash)),
    name:decodeURIComponent(rest.slice(slash+1))
  };
}

function driverIdentityKey(value){
  return String(value||'').toLowerCase().replace(/[^a-z0-9]+/g,'').trim();
}

function driverAppearances(name){
  const wanted=driverIdentityKey(name);
  if(!wanted)return [];
  const out=[];
  (state.payload?.series||[]).forEach(series=>{
    const rows=[...(series.entries||[]),...(series.roster||[])];
    const row=rows.find(item=>driverIdentityKey(item?.name)===wanted);
    if(!row)return;
    out.push({series,row});
  });
  return out;
}

function driverStatTile(label,value,detail=''){
  if(value===null||value===undefined||String(value).trim()==='')return '';
  return '<div class="driver-stat-tile"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong>'+(detail?'<small>'+detail+'</small>':'')+'</div>';
}

function driverGapText(value){
  if(!hasValue(value))return '—';
  const numeric=numericValue(value);
  if(numeric===null)return String(value);
  if(numeric===0)return 'Leader';
  return (numeric<0?'−':'')+fmt.format(Math.abs(numeric))+' pts';
}

function driverStandingContext(series,row){
  const entries=series.entries||[];
  const index=entries.findIndex(item=>driverIdentityKey(item?.name)===driverIdentityKey(row?.name));
  if(index<0)return '';
  const slice=entries.slice(Math.max(0,index-1),Math.min(entries.length,index+2));
  return '<div class="driver-neighbor-list">'+slice.map(item=>{
    const active=driverIdentityKey(item.name)===driverIdentityKey(row.name);
    return '<div class="driver-neighbor-row '+(active?'is-driver':'')+'">'+
      '<span>P'+esc(item.position??'—')+'</span>'+
      '<strong>'+esc(item.name||'Unknown')+'</strong>'+
      '<em>'+points(item.points)+' pts</em>'+
    '</div>';
  }).join('')+'</div>';
}

function driverNextRace(series){
  const event=series.current_event||null;
  if(!event)return '';
  const label=series.event_state==='live'?'LIVE NOW':'NEXT RACE';
  const when=eventTime(event);
  return '<section class="driver-detail-card driver-next-card">'+
    '<span class="eyebrow">'+label+'</span>'+
    '<h3>'+esc(event.name||series.series_name||'Race event')+'</h3>'+
    '<p>'+esc([when,event.venue,event.location].filter(Boolean).join(' · ')||'Official event timing is available through the series source.')+'</p>'+
    '<div class="driver-detail-actions">'+
      (series.watch_url?'<a class="button primary" href="'+esc(series.watch_url)+'" target="_blank" rel="noopener">Official watch info ↗</a>':'')+
      '<a class="button" href="/race-center/schedules">Full schedule</a>'+
    '</div>'+
  '</section>';
}

function renderDriverProfile(){
  const host=$('#driverProfileContent');
  if(!host||state.view!=='driver'||!state.payload)return;
  const route=currentDriverRoute();
  if(!route){
    host.innerHTML='<div class="loading-card">Driver profile not found.</div>';
    return;
  }

  const series=(state.payload.series||[]).find(x=>String(x.series_key)===String(route.series_key));
  if(!series){
    host.innerHTML='<div class="loading-card">That series is not currently available.</div>';
    return;
  }

  const rows=[...(series.entries||[]),...(series.roster||[])];
  const row=rows.find(x=>driverIdentityKey(x.name)===driverIdentityKey(route.name));
  if(!row){
    host.innerHTML='<div class="loading-card">That driver is not in the current Race Center data.</div>';
    return;
  }

  const appearances=driverAppearances(row.name||route.name);
  const primary={
    key:driverFollowKey(series,row),
    name:row.name||route.name,
    number:row.number||'',
    team:row.team||'',
    manufacturer:row.manufacturer||'',
    position:row.position,
    points:row.points,
    behind:row.behind,
    wins:row.wins,
    starts:row.starts,
    movement:row.movement,
    points_delta:row.points_delta,
    comparison_ready:row.comparison_ready!==false,
    series_key:series.series_key,
    series_name:series.series_name,
    series_short:series.short_name||series.series_name,
    group:series.group||'RACING',
    photo_url:row.photo_use_allowed===true?String(row.photo_url||''):''
  };

  const followed=state.drivers.has(primary.key);
  const identityLine=[primary.number?'#'+primary.number:'',primary.team,primary.manufacturer].filter(Boolean);
  const stats=[
    driverStatTile('Championship',primary.position?'P'+primary.position:'—',move(primary.movement,primary.comparison_ready)),
    driverStatTile('Points',hasValue(primary.points)?points(primary.points):'—',pointsDelta(primary.points_delta,primary.comparison_ready)),
    driverStatTile('Gap to leader',driverGapText(primary.behind)),
    driverStatTile('Wins',hasValue(primary.wins)?points(primary.wins):null),
    driverStatTile('Starts',hasValue(primary.starts)?points(primary.starts):null),
    driverStatTile('Series tracked',appearances.length||1)
  ].filter(Boolean).join('');

  const appearancesHtml=appearances.map(item=>{
    const itemRow=item.row;
    const itemSeries=item.series;
    return '<a class="driver-series-row" href="'+driverProfileHref(itemSeries.series_key,itemRow.name)+'">'+
      '<div>'+logo(itemSeries)+'<span><strong>'+esc(itemSeries.series_name)+'</strong><small>'+esc(itemSeries.group||'RACING')+' · '+esc(itemSeries.season||'')+'</small></span></div>'+
      '<div class="driver-series-values"><span>'+(itemRow.position?'P'+esc(itemRow.position):'—')+'</span><strong>'+points(itemRow.points)+' pts</strong>'+move(itemRow.movement,itemRow.comparison_ready!==false)+'</div>'+
    '</a>';
  }).join('');

  const sourceLinks=[
    series.official_url?'<a href="'+esc(series.official_url)+'" target="_blank" rel="noopener"><span>Official series standings</span><strong>Open source ↗</strong></a>':'',
    series.metadata_source_url?'<a href="'+esc(series.metadata_source_url)+'" target="_blank" rel="noopener"><span>Driver identity source</span><strong>Open source ↗</strong></a>':'',
    series.provider_url?'<a href="'+esc(series.provider_url)+'" target="_blank" rel="noopener"><span>'+esc(series.source_name||'Standings data source')+'</span><strong>Open source ↗</strong></a>':''
  ].filter(Boolean).join('');

  host.innerHTML=
    '<article class="driver-profile-hero driver-profile-hero-rich">'+
      '<div class="driver-profile-photo">'+driverPortrait(primary,true)+'</div>'+
      '<div class="driver-profile-copy">'+
        '<span class="eyebrow">'+esc(primary.group)+' · '+esc(primary.series_short)+'</span>'+
        '<h2>'+esc(primary.name)+'</h2>'+
        '<p>'+esc(identityLine.join(' · ')||'Source-backed Race Center driver profile')+'</p>'+
        '<div class="driver-profile-actions">'+
          '<button class="button '+(followed?'':'primary')+'" type="button" data-driver-follow="'+esc(primary.key)+'" data-driver-label="'+esc(primary.name)+'" data-driver-series="'+esc(primary.series_key)+'">'+(followed?'★ Following':'☆ Follow driver')+'</button>'+
          '<button class="button" type="button" data-driver-claim="'+esc(primary.key)+'" data-driver-name="'+esc(primary.name)+'" data-driver-series="'+esc(primary.series_key)+'">Claim this profile</button>'+
          '<a class="button" href="'+esc(series.official_url||'/race-center/standings')+'" '+(series.official_url?'target="_blank" rel="noopener"':'')+'>Official standings'+(series.official_url?' ↗':'')+'</a>'+
        '</div>'+
      '</div>'+
      '<div class="driver-profile-stat-grid">'+stats+'</div>'+
    '</article>'+

    '<div class="driver-profile-layout">'+
      '<div class="driver-profile-main">'+
        '<section class="driver-detail-card">'+
          '<div class="driver-detail-head"><div><span class="eyebrow">CHAMPIONSHIP SNAPSHOT</span><h3>'+esc(primary.series_short)+'</h3></div><span class="driver-source-age">Updated '+esc(age(series.fetched_at))+' ago</span></div>'+
          '<div class="driver-snapshot-grid">'+
            '<div><span>Current position</span><strong>'+(primary.position?'P'+esc(primary.position):'—')+'</strong></div>'+
            '<div><span>Points</span><strong>'+points(primary.points)+'</strong></div>'+
            '<div><span>Gap</span><strong>'+esc(driverGapText(primary.behind))+'</strong></div>'+
            '<div><span>Field</span><strong>'+String((series.entries||[]).length||'—')+'</strong></div>'+
          '</div>'+
          driverStandingContext(series,row)+
        '</section>'+
        driverNextRace(series)+
        '<section class="driver-detail-card">'+
          '<span class="eyebrow">RACING ACROSS RACE CENTER</span>'+
          '<h3>'+esc(primary.name)+' in tracked series</h3>'+
          '<p class="driver-detail-intro">Every current championship where Race Center finds this driver by verified name identity.</p>'+
          '<div class="driver-series-list">'+(appearancesHtml||'<div class="loading-card">Only this championship is currently tracked for this driver.</div>')+'</div>'+
        '</section>'+
      '</div>'+
      '<aside class="driver-profile-aside">'+
        '<section class="driver-detail-card">'+
          '<span class="eyebrow">RACING IDENTITY</span>'+
          '<h3>What Race Center knows</h3>'+
          '<dl class="driver-identity-list">'+
            '<div><dt>Car number</dt><dd>'+esc(primary.number||'Not verified')+'</dd></div>'+
            '<div><dt>Team</dt><dd>'+esc(primary.team||'Not verified')+'</dd></div>'+
            '<div><dt>Manufacturer</dt><dd>'+esc(primary.manufacturer||'Not verified')+'</dd></div>'+
            '<div><dt>Series</dt><dd>'+esc(primary.series_name)+'</dd></div>'+
            '<div><dt>Season</dt><dd>'+esc(series.season||'Current')+'</dd></div>'+
          '</dl>'+
        '</section>'+
        '<section class="driver-detail-card">'+
          '<span class="eyebrow">OFFICIAL SOURCES</span>'+
          '<h3>Where this data comes from</h3>'+
          '<div class="driver-source-list">'+(sourceLinks||'<p>No public source links are attached to this snapshot.</p>')+'</div>'+
        '</section>'+
        '<section class="driver-detail-card driver-claim-card">'+
          '<span class="eyebrow">DRIVER OWNERSHIP</span>'+
          '<h3>Is this your profile?</h3>'+
          '<p>Claim it to add your own photo, bio, sponsors, links and posts while Race Center keeps standings and results source-backed.</p>'+
          '<button class="button primary" type="button" data-driver-claim="'+esc(primary.key)+'" data-driver-name="'+esc(primary.name)+'" data-driver-series="'+esc(primary.series_key)+'">Claim this profile</button>'+
        '</section>'+
      '</aside>'+
    '</div>';
}

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
    const controls=$('#mySeriesControls');
    if(controls)controls.hidden=true;
    return;
  }
  hint.textContent=state.account?.authenticated?'Synced to your Race Center account.':'Saved on this device.';
  strip.innerHTML=series.map(item=>{
    const leader=item.entries?.[0];
    const event=item.current_event;
    const meta=event
      ?`${item.event_state==='live'?'LIVE · ':''}${event.name||eventWhen(event)}`
      :leader?`Leader: ${leader.name||'—'}`:'Open championship';
    return `<button class="my-series-chip" type="button" data-key="${esc(item.series_key)}">${logo(item)}<span><strong>${esc(item.short_name||item.series_name)}</strong><small>${esc(meta)}</small></span></button>`;
  }).join('');
  requestAnimationFrame(refreshMySeriesScrollCue);
}

function refreshMySeriesScrollCue(){
  const strip=$('#mySeriesStrip');
  const hint=$('#mySeriesHint');
  if(!strip||!hint)return;
  const scrollable=strip.scrollWidth>strip.clientWidth+4;
  strip.classList.toggle('is-scrollable',scrollable);
  const controls=$('#mySeriesControls');
  if(controls)controls.hidden=!scrollable;
  const prev=$('#mySeriesPrev');
  const next=$('#mySeriesNext');
  const max=Math.max(0,strip.scrollWidth-strip.clientWidth);
  if(prev)prev.disabled=strip.scrollLeft<=2;
  if(next)next.disabled=strip.scrollLeft>=max-2;
  if(!state.favorites.size){
    hint.textContent='Your saved championships live here.';
    return;
  }
  const syncText=state.account?.authenticated?'Synced to your Race Center account.':'Saved on this device.';
  hint.textContent=scrollable?'Drag or scroll to see all · '+syncText:syncText;
}

function bindMySeriesScroller(){
  const strip=$('#mySeriesStrip');
  if(!strip||strip.dataset.dragScrollBound==='1')return;
  strip.dataset.dragScrollBound='1';

  let dragging=false;
  let moved=false;
  let startX=0;
  let startScroll=0;
  let suppressClick=false;

  strip.addEventListener('pointerdown',event=>{
    if(event.pointerType!=='mouse'||event.button!==0)return;
    dragging=true;
    moved=false;
    startX=event.clientX;
    startScroll=strip.scrollLeft;
    strip.classList.add('is-dragging');
    strip.setPointerCapture?.(event.pointerId);
  });

  strip.addEventListener('pointermove',event=>{
    if(!dragging)return;
    const delta=event.clientX-startX;
    if(Math.abs(delta)>4)moved=true;
    if(moved){
      event.preventDefault();
      strip.scrollLeft=startScroll-delta;
    }
  });

  const finishDrag=event=>{
    if(!dragging)return;
    dragging=false;
    strip.classList.remove('is-dragging');
    try{strip.releasePointerCapture?.(event.pointerId);}catch(_error){}
    if(moved){
      suppressClick=true;
      requestAnimationFrame(()=>{suppressClick=false;});
    }
  };
  strip.addEventListener('pointerup',finishDrag);
  strip.addEventListener('pointercancel',finishDrag);

  strip.addEventListener('scroll',refreshMySeriesScrollCue,{passive:true});

  strip.addEventListener('wheel',event=>{
    if(strip.scrollWidth<=strip.clientWidth+4)return;
    const delta=Math.abs(event.deltaX)>Math.abs(event.deltaY)?event.deltaX:event.deltaY;
    if(!delta)return;
    const max=Math.max(0,strip.scrollWidth-strip.clientWidth);
    const canMove=(delta>0&&strip.scrollLeft<max-1)||(delta<0&&strip.scrollLeft>1);
    if(!canMove)return;
    event.preventDefault();
    strip.scrollLeft+=delta;
  },{passive:false});

  strip.addEventListener('click',event=>{
    const chip=event.target.closest('.my-series-chip[data-key]');
    if(!chip)return;
    if(suppressClick||moved){
      event.preventDefault();
      event.stopPropagation();
      moved=false;
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    openSeries(chip.dataset.key);
  });

  const nudge=direction=>strip.scrollBy({left:direction*Math.max(240,Math.floor(strip.clientWidth*.72)),behavior:'smooth'});
  safeBind('#mySeriesPrev','click',()=>nudge(-1));
  safeBind('#mySeriesNext','click',()=>nudge(1));
  window.addEventListener('resize',refreshMySeriesScrollCue,{passive:true});
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
  const pulseFavorites=$('#pulseFavorites');
  const pulseFavoriteText=$('#pulseFavoriteText');
  if(pulseFavorites)pulseFavorites.textContent=String(state.favorites.size);
  if(pulseFavoriteText)pulseFavoriteText.textContent=state.favorites.size
    ?`${state.favorites.size} saved championship${state.favorites.size===1?'':'s'}`
    :'nothing followed yet';
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
  renderDrivers();
  renderDriverProfile();
  bindLogoErrors();
  $('#clearSearch').hidden=!normalizeSearch(state.search);

  if(state.view==='schedules'){
    const count=(state.payload?.events?.catalog||[]).filter(scheduleVisible).length;
    $('#resultCount').textContent=`${count} schedules`;
  }else if(state.view==='drivers'){
    const q=normalizeSearch(state.driverSearch);
    const rows=driverDirectoryRows().filter(driver=>!q||[
      driver.name,driver.number,driver.team,driver.manufacturer,driver.series_name,driver.series_short,driver.group
    ].filter(Boolean).join(' ').toLowerCase().includes(q));
    $('#resultCount').textContent=`${rows.length} drivers`;
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
    {key:'name',label:'Driver',always:true,cell:row=>{
      const followKey=driverFollowKey(series,row);
      const following=state.drivers.has(followKey);
      return `<span class="driver-follow-cell"><button type="button" class="driver-follow ${following?'is-following':''}" data-driver-follow="${esc(followKey)}" data-driver-label="${esc(row.name||'Unknown')}" data-driver-series="${esc(series.series_key||'')}" aria-pressed="${following?'true':'false'}">${following?'★':'☆'}</button><strong>${esc(row.name||'Unknown')}</strong></span>`;
    }},
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
    const response=await fetch('/api/public/standings?v=race-center-v5-20260922',{
      headers:{Accept:'application/json'},
      cache:'no-store',
      signal:controller.signal
    });
    clearTimeout(timeout);
    if(!response.ok)throw new Error('Race Center feed unavailable');
    state.payload=await response.json();
    saveCachedPayload(state.payload);
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
  // Render a recent saved board instantly, then refresh from the durable API.
  const cached=readCachedPayload();
  if(cached){
    state.payload=cached;
    render();
    const status=$('#headerStatus');
    if(status){
      status.className='header-health warn';
      status.innerHTML='<i></i> Refreshing live board';
    }
  }
  load();
  syncAccount();
  bindMySeriesScroller();
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
      const series=(state.payload?.series||[]).find(item=>String(item.series_key)===key);
      if(state.favorites.has(key)){
        state.favorites.delete(key);
        cloudUnfollow('series',key,series?.series_name||'',key).catch(()=>{});
      }else{
        state.favorites.add(key);
        cloudFollow('series',key,series?.series_name||'',key).catch(()=>{});
      }
      savePrefs();
      render();
      return;
    }
    const driverFollow=event.target.closest('[data-driver-follow]');
    if(driverFollow){
      event.preventDefault();
      event.stopPropagation();
      const key=String(driverFollow.dataset.driverFollow||'');
      const label=String(driverFollow.dataset.driverLabel||'');
      const seriesKey=String(driverFollow.dataset.driverSeries||'');
      if(state.drivers.has(key)){
        state.drivers.delete(key);
        cloudUnfollow('driver',key,label,seriesKey).catch(()=>{});
      }else{
        state.drivers.add(key);
        cloudFollow('driver',key,label,seriesKey).catch(()=>{});
      }
      savePrefs();
      if(state.lastSeries)openSeries(state.lastSeries);
      renderAccount();
      return;
    }
    const claim=event.target.closest('[data-driver-claim]');
    if(claim){
      event.preventDefault();
      if(!state.account?.authenticated){
        renderAccount();
        $('#accountMessage').textContent='Sign in or create a Race Center account before claiming a driver profile.';
        $('#accountDialog')?.showModal();
        return;
      }
      $('#driverClaimKey').value=String(claim.dataset.driverClaim||'');
      $('#driverClaimName').value=String(claim.dataset.driverName||'');
      $('#driverClaimSeries').value=String(claim.dataset.driverSeries||'');
      $('#driverClaimTitle').textContent='Claim '+String(claim.dataset.driverName||'driver profile');
      $('#driverClaimMessage').textContent='';
      $('#driverClaimDialog')?.showModal();
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
    if(event.target?.id==='driverSearch'){
      state.driverSearch=event.target.value||'';
      renderDrivers();
    }
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

  safeBind('#accountButton','click',()=>{
    renderAccount();
    $('#accountDialog')?.showModal();
  });
  safeBind('#accountClose','click',()=>$('#accountDialog')?.close());
  safeBind('#logoutButton','click',async()=>{
    try{await apiJson('/api/public/race-center/account/logout',{method:'POST'});}catch(_error){}
    state.account={authenticated:false,follows:[]};
    renderAccount();
  });

  const signupForm=$('#signupForm');
  if(signupForm)signupForm.addEventListener('submit',async event=>{
    event.preventDefault();
    const form=new FormData(signupForm);
    const message=$('#accountMessage');
    if(message)message.textContent='Creating your Race Center…';
    try{
      state.account=await apiJson('/api/public/race-center/account/signup',{
        method:'POST',
        body:JSON.stringify({
          display_name:String(form.get('display_name')||''),
          email:String(form.get('email')||''),
          password:String(form.get('password')||'')
        })
      });
      for(const key of state.favorites){
        const series=(state.payload?.series||[]).find(item=>String(item.series_key)===key);
        await cloudFollow('series',key,series?.series_name||'',key);
      }
      for(const key of state.drivers){
        const [seriesKey]=key.split(':',1);
        await cloudFollow('driver',key,key.split(':').slice(1).join(':')||'Driver',seriesKey||'');
      }
      renderAccount();
      if(message)message.textContent='';
    }catch(error){
      if(message)message.textContent=error.message||'Could not create account.';
    }
  });

  const loginForm=$('#loginForm');
  if(loginForm)loginForm.addEventListener('submit',async event=>{
    event.preventDefault();
    const form=new FormData(loginForm);
    const message=$('#accountMessage');
    if(message)message.textContent='Signing in…';
    try{
      state.account=await apiJson('/api/public/race-center/account/login',{
        method:'POST',
        body:JSON.stringify({
          email:String(form.get('email')||''),
          password:String(form.get('password')||''),
          display_name:''
        })
      });
      mergeAccountFollows();
      renderAccount();
      render();
      if(message)message.textContent='';
    }catch(error){
      if(message)message.textContent=error.message||'Could not sign in.';
    }
  });

  safeBind('#clearSearch','click',()=>{
    const input=$('#searchInput');
    if(input)input.value='';
    state.search='';
    if(state.payload)render();
    if(input)input.focus();
  });

  safeBind('#driverClaimClose','click',()=>$('#driverClaimDialog')?.close());
  const driverClaimForm=$('#driverClaimForm');
  if(driverClaimForm){
    driverClaimForm.addEventListener('submit',async event=>{
      event.preventDefault();
      const message=$('#driverClaimMessage');
      message.textContent='Submitting claim…';
      try{
        const result=await apiJson('/api/public/race-center/driver-claims',{
          method:'POST',
          body:JSON.stringify({
            driver_key:String($('#driverClaimKey').value||''),
            driver_name:String($('#driverClaimName').value||''),
            series_key:String($('#driverClaimSeries').value||''),
            evidence_url:String($('#driverClaimEvidence').value||''),
            note:String($('#driverClaimNote').value||'')
          })
        });
        message.textContent=result.status==='pending'?'Claim submitted for review.':'Claim saved.';
        setTimeout(()=>$('#driverClaimDialog')?.close(),900);
      }catch(error){
        message.textContent=error.message||'Could not submit claim.';
      }
    });
  }

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
