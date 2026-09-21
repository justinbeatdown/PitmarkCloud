const state={payload:null,group:'All',search:''};
const $=s=>document.querySelector(s);
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const n=value=>Number(value||0).toLocaleString();
const points=value=>value===null||value===undefined||value===''?'—':(typeof value==='number'?value.toLocaleString():esc(value));
const seriesMarkText=series=>{
  const key=String(series?.series_key||'');
  const special={
    'f1':'FORMULA 1','motogp':'MotoGP','moto2':'Moto2','moto3':'Moto3','worldsbk':'WorldSBK',
    'nhra-top-fuel':'NHRA','nhra-funny-car':'NHRA','nhra-pro-stock':'NHRA','nhra-pro-stock-motorcycle':'NHRA',
    'imsa-weathertech':'IMSA','imsa-michelin-pilot':'IMSA','imsa-vp-racing':'IMSA',
    'wec':'FIA WEC','formula-e':'FORMULA E','indycar':'INDYCAR',
    'world-of-outlaws-sprint':'WORLD OF OUTLAWS','world-of-outlaws-late-models':'WORLD OF OUTLAWS',
    'lucas-oil-late-models':'LOLMDS','cars-tour-lmsc':'CARS TOUR','asa-stars':'ASA STARS',
    'smart-modified':'SMART','high-limit-sprint':'HIGH LIMIT'
  };
  return special[key]||String(series?.short_name||series?.series_name||'RACING').toUpperCase();
};
const logo=series=>series?.series_logo
  ?`<img class="series-logo" src="${esc(series.series_logo)}" data-direct="${esc(series.series_logo_direct||'')}" alt="${esc(series.series_name||'Series')} official logo">`
  :`<span class="series-wordmark" title="${esc(series?.series_name||'Series')}">${esc(seriesMarkText(series))}</span>`;
const identityText=row=>{const values=[row?.team,row?.manufacturer].filter(Boolean).map(String);return [...new Set(values)].join(' · ');};
const age=iso=>{
  if(!iso)return '—';
  const then=new Date(iso).getTime(),now=Date.now(),mins=Math.max(0,Math.round((now-then)/60000));
  if(mins<2)return 'just now';if(mins<60)return mins+'m ago';const hrs=Math.round(mins/60);if(hrs<48)return hrs+'h ago';return Math.round(hrs/24)+'d ago';
};
const move=(value,ready=true)=>{
  if(!ready)return '<span class="move base" title="Baseline captured; movement appears after the next standings change">BASE</span>';
  if(value===null||value===undefined||Number(value)===0)return '<span class="move flat" title="No championship position change">—</span>';
  const v=Number(value);
  return v>0
    ?`<span class="move up" title="Up ${Math.abs(v)} championship position${Math.abs(v)===1?'':'s'}">▲${Math.abs(v)}</span>`
    :`<span class="move down" title="Down ${Math.abs(v)} championship position${Math.abs(v)===1?'':'s'}">▼${Math.abs(v)}</span>`;
};
const pointsDelta=(value,ready=true)=>{
  if(!ready)return '<small class="points-delta base" title="Baseline captured">Δ BASE</small>';
  if(value===null||value===undefined||Number(value)===0)return '<small class="points-delta flat">Δ 0</small>';
  const v=Number(value);
  const display=Math.abs(v).toLocaleString();
  return v>0
    ?`<small class="points-delta up">+${display}</small>`
    :`<small class="points-delta down">−${display}</small>`;
};
const eventTime=event=>{
  const iso=event?.start;
  if(!iso)return '';
  const d=new Date(iso);
  if(Number.isNaN(d.getTime()))return '';
  if(event?.date_only)return d.toLocaleDateString(undefined,{month:'short',day:'numeric',timeZone:'UTC'});
  return d.toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
};
const statusBadge=series=>{
  const state=String(series.event_state||'').toLowerCase();
  const event=series.current_event||{};
  if(state==='live')return '<span class="status live">LIVE NOW</span>';
  if(state==='next'&&event.start)return `<span class="status next">NEXT ${esc(eventTime(event))}</span>`;
  return '';
};
const normalizeSearch=value=>String(value??'').trim().toLowerCase();
const seriesVisible=series=>{
  const groupOk=state.group==='All'||series.group===state.group;
  const q=normalizeSearch(state.search);
  if(!q)return groupOk;
  const hay=[
    series.series_name,series.short_name,series.group,
    ...(series.entries||[]).flatMap(x=>[x.name,x.number,x.team,x.manufacturer])
  ].filter(Boolean).join(' ').toLowerCase();
  return groupOk&&hay.includes(q);
};
function miniRows(series){
  const rows=(series.entries||[]).slice(0,5);
  if(!rows.length)return '<div class="empty-card">Standings source is temporarily unavailable.</div>';
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
  return `<article class="series-card" data-key="${esc(series.series_key)}">
    <header><div class="card-brand">${logo(series)}<div><span class="eyebrow">${esc(series.group||'RACING')}</span><h4>${esc(series.short_name||series.series_name)}</h4></div></div>${statusBadge(series)}</header>
    <div class="card-leader"><span>Championship leader</span><strong>${leader?.number?esc('#'+leader.number+' · '):''}${esc(leader?.name||'—')}</strong><small>${leader?points(leader.points)+' pts'+(leader.points_delta?(' ('+(Number(leader.points_delta)>0?'+':'')+esc(leader.points_delta)+')'):'')+(identityText(leader)?' · '+esc(identityText(leader)):''):'No data yet'}</small></div>
    ${miniRows(series)}
    <footer><span>${esc(series.series_name||'Series')}</span><strong>Full standings ›</strong></footer>
  </article>`;
}
function renderFilters(){
  const groups=['All',...[...new Set((state.payload?.series||[]).map(s=>s.group||'Other'))]];
  $('#filters').innerHTML=groups.map(group=>`<button class="filter ${state.group===group?'active':''}" data-group="${esc(group)}">${esc(group)}</button>`).join('');
}
function renderLeaders(){
  const leaders=(state.payload?.series||[]).filter(s=>s.entries?.length&&seriesVisible(s)).slice(0,8);
  $('#leaderStrip').innerHTML=leaders.length?leaders.map(series=>{
    const leader=series.entries[0];
    return `<article class="leader-card" data-key="${esc(series.series_key)}"><div class="leader-brand">${logo(series)}<span class="series">${esc(series.short_name||series.series_name)}</span></div><div><strong>${leader.number?esc('#'+leader.number+' · '):''}${esc(leader.name||'—')}</strong><div class="points">${points(leader.points)} pts</div><small>${esc(identityText(leader)||series.group||'')}</small></div></article>`;
  }).join(''):'<div class="loading-card">No standings match this filter.</div>';
}
function renderGroups(){
  const visible=(state.payload?.series||[]).filter(seriesVisible);
  const groups=[...new Set(visible.map(s=>s.group||'Other'))];
  $('#seriesGroups').innerHTML=groups.length?groups.map(group=>{
    const items=visible.filter(s=>(s.group||'Other')===group);
    return `<section class="group"><div class="group-head"><h3>${esc(group)}</h3><span>${items.length} tracked</span></div><div class="series-grid">${items.map(card).join('')}</div></section>`;
  }).join(''):'<div class="loading-card">Nothing matched that search.</div>';
  $('#statusText').textContent=`${visible.length} championships shown · Pitmark snapshots update automatically`;
}
function renderSummary(){
  const p=state.payload||{},s=p.summary||{};
  $('#seriesCount').textContent=n(s.schedule_series_total||s.series_total||p.series?.length);
  $('#liveCount').textContent=n(s.events_live||0);
  $('#seasonValue').textContent=p.season||'—';
  $('#updatedValue').textContent=age(s.last_snapshot_at||p.generated_at);
}
function bindLogoErrors(){
  document.querySelectorAll('.series-logo').forEach(img=>{
    if(img.dataset.logoBound)return;
    img.dataset.logoBound='1';
    img.addEventListener('error',()=>{
      const direct=img.dataset.direct||'';
      if(direct&&img.src!==direct&&!img.dataset.directTried){
        img.dataset.directTried='1';
        img.src=direct;
        return;
      }
      img.hidden=true;
    });
  });
}
function eventLogo(item){
  const matching=(state.payload?.series||[]).find(series=>String(series.series_key)===String(item?.series_key));
  if(matching&&matching.series_logo)return logo(matching);
  const direct=String(item?.logo_url||'').trim();
  if(direct)return `<img class="series-logo event-series-logo" src="${esc(direct)}" alt="${esc(item?.series_name||'Series')} official logo">`;
  const special={
    'f1':'FORMULA 1','motogp':'MotoGP','moto2':'Moto2','moto3':'Moto3','worldsbk':'WorldSBK',
    'nhra-top-fuel':'NHRA','nhra-funny-car':'NHRA','nhra-pro-stock':'NHRA','nhra-pro-stock-motorcycle':'NHRA',
    'imsa-weathertech':'IMSA WEATHERTECH','imsa-michelin-pilot':'IMSA MICHELIN PILOT','imsa-vp-racing':'IMSA VP RACING',
    'imsa-porsche-carrera-cup':'PORSCHE CARRERA CUP','imsa-mustang-challenge':'MUSTANG CHALLENGE',
    'imsa-lamborghini-super-trofeo':'LAMBORGHINI SUPER TROFEO','imsa-mx5-cup':'MAZDA MX-5 CUP',
    'gtwc-america':'GT WORLD CHALLENGE','trans-am':'TRANS AM','dtm':'DTM','btcc':'BTCC',
    'nascar-whelen-modified':'NASCAR WHELEN MODIFIED','arca-east':'ARCA EAST','arca-west':'ARCA WEST'
  };
  const mark=special[String(item?.series_key||'')]||String(item?.series_name||'RACING').toUpperCase();
  return `<span class="series-wordmark event-wordmark" title="${esc(item?.series_name||'Series')}">${esc(mark)}</span>`;
}
function eventWhen(event){return event?.start?eventTime(event):'See official schedule';}

function eventCard(item,compact=false){
  const event=item?.event||{};
  const live=item?.state==='live';
  return `<article class="event-card ${live?'is-live':''}">
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
  const live=events.live||[];
  const next=events.next||[];
  $('#eventStatusText').textContent=live.length?`${live.length} event${live.length===1?'':'s'} live right now`:'Nothing live right now — here’s what’s next.';
  $('#liveNow').innerHTML=live.length?`<div class="live-grid">${live.map(item=>eventCard(item)).join('')}</div>`:'';
  $('#nextEvents').innerHTML=next.length?next.slice(0,8).map(item=>eventCard(item,true)).join(''):'<div class="loading-card">Open a series schedule below for the latest event dates.</div>';
}
function renderScheduleCatalog(){
  const catalog=state.payload?.events?.catalog||[];
  $('#scheduleCatalog').innerHTML=catalog.map(item=>`<article class="schedule-card">
    <div class="event-brand">${eventLogo(item)}<div><span class="eyebrow">${esc(item.group||'RACING')}</span><h3>${esc(item.series_name||'Series')}</h3></div></div>
    <p>${item.state==='live'?'LIVE NOW':item.state==='next'&&item.event?.start?'Next: '+esc(eventTime(item.event)):'Official 2026 schedule'}</p>
    <div class="event-actions">
      ${item.schedule_url?`<a href="${esc(item.schedule_url)}" target="_blank" rel="noopener">Schedule ↗</a>`:''}
      ${item.watch_url?`<a href="${esc(item.watch_url)}" target="_blank" rel="noopener">${esc(item.watch_name||'Where to watch')} ↗</a>`:''}
    </div>
  </article>`).join('');
}
function render(){
  renderSummary();renderFilters();renderEvents();renderScheduleCatalog();renderLeaders();renderGroups();bindLogoErrors();
}
function openSeries(key){
  const series=(state.payload?.series||[]).find(s=>String(s.series_key)===String(key));
  if(!series)return;
  const rows=series.entries||[];
  const body=rows.length?`<div class="table-wrap"><table><thead><tr><th>Pos</th><th>#</th><th>Move</th><th>Driver</th><th>Team</th><th>Manufacturer</th><th>Points</th><th>Behind</th><th>Wins</th></tr></thead><tbody>${rows.map(row=>`<tr>
    <td><strong>${esc(row.position??'—')}</strong></td><td><strong>${esc(row.number||'—')}</strong></td><td>${move(row.movement,row.comparison_ready!==false)}</td><td><strong>${esc(row.name||'Unknown')}</strong></td>
    <td>${esc(row.team||'—')}</td><td>${esc(row.manufacturer||'—')}</td><td><strong>${points(row.points)}</strong>${pointsDelta(row.points_delta,row.comparison_ready!==false)}</td><td>${points(row.behind)}</td><td>${points(row.wins)}</td>
  </tr>`).join('')}</tbody></table></div>`:'<div class="loading-card">No current standings are available from this source yet.</div>';
  const identitySource=series.metadata_source_url?`<a class="official-link identity-source" href="${esc(series.metadata_source_url)}" target="_blank" rel="noopener">Driver identity data: official series source ↗</a>`:'';
  const logoSource=series.series_logo_source_url?`<a class="official-link identity-source" href="${esc(series.series_logo_source_url)}" target="_blank" rel="noopener">Logo source: official series page ↗</a>`:'';
  const scheduleLink=series.schedule_url?`<a class="official-link" href="${esc(series.schedule_url)}" target="_blank" rel="noopener">Official schedule ↗</a>`:'';
  const watchLink=series.watch_url?`<a class="official-link" href="${esc(series.watch_url)}" target="_blank" rel="noopener">${esc(series.watch_name||'Where to watch')} ↗</a>`:'';
  const eventLine=series.current_event?`<div class="dialog-event ${series.event_state==='live'?'is-live':''}"><span class="eyebrow">${series.event_state==='live'?'LIVE NOW':'NEXT / RECENT'}</span><strong>${esc(series.current_event.name||'Event')}</strong><small>${series.current_event.start?esc(eventTime(series.current_event)):''}</small></div>`:'';
  $('#dialogContent').innerHTML=`<div class="dialog-title"><div class="dialog-brand">${logo(series)}<div><span class="eyebrow">${esc(series.group||'RACING')} · ${esc(series.season||'')}</span><h2>${esc(series.series_name||'Standings')}</h2><p>${esc(series.source_name||'Series standings')} · updated ${esc(age(series.fetched_at))}</p></div></div></div>${eventLine}${body}<div class="source-links">${scheduleLink}${watchLink}${series.official_url?`<a class="official-link" href="${esc(series.official_url)}" target="_blank" rel="noopener">Open official series standings ↗</a>`:''}${identitySource}${logoSource}</div>`;
  bindLogoErrors();
  $('#standingsDialog').showModal();
}
async function load(){
  try{
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),8000);
    const response=await fetch('/api/public/standings',{headers:{Accept:'application/json'},signal:controller.signal});
    clearTimeout(timeout);
    if(!response.ok)throw new Error('Standings feed unavailable');
    state.payload=await response.json();
    render();
  }catch(error){
    $('#leaderStrip').innerHTML='<div class="loading-card">Pitmark could not load the standings feed right now. Try again shortly.</div>';
    $('#seriesGroups').innerHTML='<div class="loading-card">Standings temporarily unavailable.</div>';
    $('#statusText').textContent=error?.name==='AbortError'?'Standings feed timed out. Refresh the page to retry.':(error.message||'Unable to load standings');
  }
}
document.addEventListener('click',event=>{
  const filter=event.target.closest('[data-group]');
  if(filter){state.group=filter.dataset.group;render();return;}
  const card=event.target.closest('[data-key]');
  if(card){openSeries(card.dataset.key);return;}
});
const applySearch=value=>{
  state.search=String(value??'');
  renderLeaders();
  renderGroups();
  bindLogoErrors();
};
document.addEventListener('input',event=>{
  if(event.target?.id==='searchInput')applySearch(event.target.value);
});
document.addEventListener('search',event=>{
  if(event.target?.id==='searchInput')applySearch(event.target.value);
});
$('#dialogClose').addEventListener('click',()=>$('#standingsDialog').close());
$('#standingsDialog').addEventListener('click',event=>{if(event.target===$('#standingsDialog'))$('#standingsDialog').close();});
$('#jumpLive').addEventListener('click',()=>$('#standingsStart').scrollIntoView({behavior:'smooth'}));
load();