const state={payload:null,group:'All',search:''};
const $=s=>document.querySelector(s);
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const n=value=>Number(value||0).toLocaleString();
const points=value=>value===null||value===undefined||value===''?'—':(typeof value==='number'?value.toLocaleString():esc(value));
const age=iso=>{
  if(!iso)return '—';
  const then=new Date(iso).getTime(),now=Date.now(),mins=Math.max(0,Math.round((now-then)/60000));
  if(mins<2)return 'just now';if(mins<60)return mins+'m ago';const hrs=Math.round(mins/60);if(hrs<48)return hrs+'h ago';return Math.round(hrs/24)+'d ago';
};
const move=value=>{
  if(value===null||value===undefined||Number(value)===0)return '<span class="move flat">—</span>';
  const v=Number(value);return v>0?`<span class="move up">▲${Math.abs(v)}</span>`:`<span class="move down">▼${Math.abs(v)}</span>`;
};
const statusBadge=series=>{
  const status=String(series.status||'unavailable').toLowerCase();
  const label=status==='live'?'Live':status==='stale'?'Cached':'Unavailable';
  return `<span class="status ${esc(status)}">${label}</span>`;
};
const seriesVisible=series=>{
  const groupOk=state.group==='All'||series.group===state.group;
  const q=state.search.trim().toLowerCase();
  if(!q)return groupOk;
  const hay=[
    series.series_name,series.short_name,series.group,
    ...(series.entries||[]).slice(0,20).map(x=>x.name)
  ].join(' ').toLowerCase();
  return groupOk&&hay.includes(q);
};
function miniRows(series){
  const rows=(series.entries||[]).slice(0,5);
  if(!rows.length)return '<div class="empty-card">Standings source is temporarily unavailable.</div>';
  return `<div class="mini-table">${rows.map(row=>`<div class="mini-row">
    <span class="pos">${esc(row.position??'—')}</span>
    <span class="driver"><strong>${esc(row.name||'Unknown')}</strong><small>${esc(row.team||row.manufacturer||'')}</small></span>
    ${move(row.movement)}
    <span class="pts">${points(row.points)}</span>
  </div>`).join('')}</div>`;
}
function card(series){
  const leader=(series.entries||[])[0];
  return `<article class="series-card" data-key="${esc(series.series_key)}">
    <header><div><span class="eyebrow">${esc(series.group||'RACING')}</span><h4>${esc(series.short_name||series.series_name)}</h4></div>${statusBadge(series)}</header>
    <div class="card-leader"><span>Championship leader</span><strong>${esc(leader?.name||'—')}</strong><small>${leader?points(leader.points)+' pts':'No data yet'}</small></div>
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
    return `<article class="leader-card" data-key="${esc(series.series_key)}"><span class="series">${esc(series.short_name||series.series_name)}</span><div><strong>${esc(leader.name||'—')}</strong><div class="points">${points(leader.points)} pts</div><small>${esc(leader.team||leader.manufacturer||series.group||'')}</small></div></article>`;
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
  $('#seriesCount').textContent=n(s.series_total||p.series?.length);
  $('#liveCount').textContent=n(s.live);
  $('#seasonValue').textContent=p.season||'—';
  $('#updatedValue').textContent=age(s.last_snapshot_at||p.generated_at);
}
function render(){
  renderSummary();renderFilters();renderLeaders();renderGroups();
}
function openSeries(key){
  const series=(state.payload?.series||[]).find(s=>String(s.series_key)===String(key));
  if(!series)return;
  const rows=series.entries||[];
  const body=rows.length?`<div class="table-wrap"><table><thead><tr><th>Pos</th><th>Move</th><th>Driver</th><th>Team / Mfr</th><th>Points</th><th>Behind</th><th>Wins</th></tr></thead><tbody>${rows.map(row=>`<tr>
    <td><strong>${esc(row.position??'—')}</strong></td><td>${move(row.movement)}</td><td><strong>${esc(row.name||'Unknown')}</strong></td>
    <td>${esc(row.team||row.manufacturer||'—')}</td><td><strong>${points(row.points)}</strong></td><td>${points(row.behind)}</td><td>${points(row.wins)}</td>
  </tr>`).join('')}</tbody></table></div>`:'<div class="loading-card">No current standings are available from this source yet.</div>';
  $('#dialogContent').innerHTML=`<div class="dialog-title"><span class="eyebrow">${esc(series.group||'RACING')} · ${esc(series.season||'')}</span><h2>${esc(series.series_name||'Standings')}</h2><p>${esc(series.source_name||'Series standings')} · updated ${esc(age(series.fetched_at))}</p></div>${body}${series.official_url?`<a class="official-link" href="${esc(series.official_url)}" target="_blank" rel="noopener">Open official series standings ↗</a>`:''}`;
  $('#standingsDialog').showModal();
}
async function load(){
  try{
    const bootstrap=document.getElementById('pitmark-standings-bootstrap');
    if(bootstrap?.textContent?.trim()){
      state.payload=JSON.parse(bootstrap.textContent);
      render();
      return;
    }
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
$('#searchInput').addEventListener('input',event=>{state.search=event.target.value;renderLeaders();renderGroups();});
$('#dialogClose').addEventListener('click',()=>$('#standingsDialog').close());
$('#standingsDialog').addEventListener('click',event=>{if(event.target===$('#standingsDialog'))$('#standingsDialog').close();});
$('#jumpLive').addEventListener('click',()=>$('#standingsStart').scrollIntoView({behavior:'smooth'}));
load();
