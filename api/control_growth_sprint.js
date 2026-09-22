(() => {
  const API = '/api/control/ops/growth-goal';
  const PLATFORM_ICONS = {facebook:'f',instagram:'◎',tiktok:'♪',youtube:'▶',x:'X',discord:'◈'};
  let loading = false;

  function esc(v='') { return String(v).replace(/[&<>\"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
  function fmt(v) { return v == null ? 'Set baseline' : Number(v).toLocaleString(); }
  async function api(method='GET', body) {
    const res = await fetch(API, {method, credentials:'same-origin', headers:{'Content-Type':'application/json'}, body:body ? JSON.stringify(body) : undefined});
    if (!res.ok) throw new Error((await res.text()) || ('HTTP '+res.status));
    return res.json();
  }
  function shouldMount() {
    const app=document.getElementById('pitmark-control');
    const domain=app?.dataset?.activeDomain || '';
    return domain === 'hq' || domain === 'content' || domain === 'insights';
  }
  function cardMarkup(p) {
    const pct=p.progress_pct == null ? 0 : Math.max(0,Math.min(100,p.progress_pct));
    const pace = p.current == null ? 'Baseline needed' : (p.status === 'on pace' ? 'On pace' : 'Behind pace');
    const delta = p.pace_delta == null ? '' : `${p.pace_delta >= 0 ? '+' : ''}${p.pace_delta} vs pace`;
    return `<article class="pm-growth-platform ${p.status === 'behind pace' ? 'is-behind' : ''}" data-platform="${esc(p.id)}">
      <div class="pm-growth-platform-head"><span class="pm-growth-icon">${PLATFORM_ICONS[p.id]||'•'}</span><div><strong>${esc(p.label)}</strong><small>${esc(p.source)}</small></div><button type="button" data-growth-update="${esc(p.id)}">Update</button></div>
      <div class="pm-growth-number"><strong>${fmt(p.current)}</strong><span>/ 1,000</span></div>
      <div class="pm-growth-bar"><i style="width:${pct}%"></i></div>
      <div class="pm-growth-meta"><span>${p.gap == null ? '—' : p.gap.toLocaleString()} to go</span><span>${p.required_daily == null ? '—' : p.required_daily + '/day'} needed</span></div>
      <div class="pm-growth-pace"><b>${pace}</b><span>${delta}</span></div>
    </article>`;
  }
  function render(data) {
    const root=document.getElementById('view-root'); if(!root || !shouldMount()) return;
    let el=document.getElementById('pm-growth-sprint');
    if(!el){ el=document.createElement('section'); el.id='pm-growth-sprint'; el.className='pm-growth-sprint'; root.prepend(el); }
    el.innerHTML=`<div class="pm-growth-head"><div><span class="pm-growth-kicker">30-DAY SOCIAL SPRINT</span><h2>1K Everywhere</h2><p>Get every active Pitmark community platform to 1,000 by <strong>Oct. 22, 2026</strong>. <b>${data.days_remaining}</b> days remain.</p></div><div class="pm-growth-target"><span>Target</span><strong>1,000</strong><small>each platform</small></div></div>
      <div class="pm-growth-platforms">${(data.platforms||[]).map(cardMarkup).join('')}</div>
      <div class="pm-growth-rules"><div><strong>Daily engine</strong><span>2 short videos + 1 community post</span></div><div><strong>Weekly crossover</strong><span>4 collaborations + 3 driver/track features</span></div><div><strong>Rule</strong><span>Every growth post must give people a reason to follow, not just a reason to like it.</span></div></div>
      <div class="pm-growth-note">Weakest platform gets the extra push. We optimize for follows, shares, saves and repeat viewing — not raw post volume.</div>`;
    el.querySelectorAll('[data-growth-update]').forEach(btn => btn.addEventListener('click', async () => {
      const id=btn.dataset.growthUpdate; const p=(data.platforms||[]).find(x=>x.id===id);
      const raw=window.prompt(`Current ${p?.label||id} followers/members?`, p?.current ?? '');
      if(raw===null) return; const n=Number(raw.replace(/,/g,'')); if(!Number.isFinite(n)||n<0){window.alert('Enter a valid number.');return;}
      btn.disabled=true;
      try { render(await api('PATCH',{counts:{[id]:Math.round(n)}})); } catch(e){ window.alert('Could not update growth count: '+e.message); } finally { btn.disabled=false; }
    }));
  }
  async function load(){ if(loading || !shouldMount()) return; loading=true; try{render(await api());}catch(e){console.warn('[growth-sprint]',e);}finally{loading=false;} }
  function sync(){ const existing=document.getElementById('pm-growth-sprint'); if(!shouldMount()){existing?.remove(); return;} load(); }
  document.addEventListener('DOMContentLoaded',()=>{sync(); const app=document.getElementById('pitmark-control'); if(app) new MutationObserver(sync).observe(app,{attributes:true,attributeFilter:['data-active-domain']}); const root=document.getElementById('view-root'); if(root) new MutationObserver(()=>{ if(shouldMount()&&!document.getElementById('pm-growth-sprint')) sync(); }).observe(root,{childList:true}); setInterval(load,60000);});
})();
