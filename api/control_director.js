(() => {
  'use strict';
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function call(url, options={}) {
    const headers={...(options.headers||{})};
    let body=options.body;
    if(body && typeof body !== 'string'){headers['Content-Type']='application/json';body=JSON.stringify(body);}
    const r=await fetch(url,{credentials:'same-origin',...options,headers,body});
    const text=await r.text();
    let data={};
    try{data=text?JSON.parse(text):{};}catch{data={detail:text};}
    if(!r.ok) throw new Error(data.detail||'Pitmark Director request failed.');
    return data;
  }
  function render(result){
    const target=document.getElementById('pitmark-director-result');
    if(!target) return;
    const actions=(result.top_actions||[]).map(x =>
      '<article class="pmd-card"><div class="pmd-rank">'+esc(x.rank||'•')+'</div><div><strong>'+esc(x.title||'Action')+'</strong><p>'+esc(x.why||'')+'</p><small>'+esc(x.area||'Pitmark')+' · '+esc(typeof x.execution==='object' ? (x.execution?.status||'prepared') : (x.execution||'review'))+'</small><b>'+esc(x.next_step||'')+'</b></div></article>'
    ).join('');
    const owner=(result.owner_needed||[]).map(x =>
      '<article class="pmd-owner"><strong>'+esc(x.title||'Owner action')+'</strong><p>'+esc(x.reason||'')+'</p><span>'+esc(x.urgency||'later')+'</span></article>'
    ).join('');
    const executed=(result.execution_result?.actions||[]).map(x => {
      if(x.type==='social_drafts_saved') return '<article class="pmd-owner"><strong>Saved '+esc(x.count||0)+' social draft'+(Number(x.count||0)===1?'':'s')+'</strong><p>Added to Content approvals. Nothing was published automatically.</p><span>COMPLETED</span></article>';
      if(x.type==='social_draft_titles_repaired') return '<article class="pmd-owner"><strong>Repaired '+esc(x.count||0)+' social draft title'+(Number(x.count||0)===1?'':'s')+'</strong><p>Replaced internal Director task labels with human-facing content titles.</p><span>COMPLETED</span></article>';
      return '<article class="pmd-owner"><strong>'+esc(x.type||'Execution')+'</strong><p>'+esc(x.error||'')+'</p><span>'+esc(x.status||'')+'</span></article>';
    }).join('');
    const stateLabel = typeof result.state === 'string'
      ? result.state
      : (result.state?.scope ? 'Operating review' : 'Working');
    target.innerHTML =
      '<div class="pmd-state">'+esc(String(stateLabel).toUpperCase())+'</div>'+
      '<h2>'+esc(result.headline||'Pitmark Director')+'</h2>'+
      '<p class="pmd-summary">'+esc(result.executive_summary||'')+'</p>'+
      (actions?'<h3>Priority stack</h3><div class="pmd-stack">'+actions+'</div>':'')+
      (executed?'<h3>Astra completed</h3><div class="pmd-stack">'+executed+'</div>':'')+
      (owner?'<h3>You are needed</h3><div class="pmd-stack">'+owner+'</div>':'<div class="pmd-clear">Nothing currently requires you.</div>');
  }
  function open(){
    document.getElementById('pitmark-director-layer')?.removeAttribute('hidden');
    setTimeout(()=>document.getElementById('pitmark-director-request')?.focus(),30);
  }
  function close(){
    document.getElementById('pitmark-director-layer')?.setAttribute('hidden','');
  }
  async function run(){
    const button=document.getElementById('pitmark-director-run');
    const input=document.getElementById('pitmark-director-request');
    const result=document.getElementById('pitmark-director-result');
    if(button){button.disabled=true;button.textContent='Astra is reviewing Pitmark…';}
    if(result) result.innerHTML='<div class="pmd-loading">Reading the Master Checklist, command brief and autonomy rules…</div>';
    try{
      const data=await call('/api/control/director/run',{method:'POST',body:{request:input?.value?.trim()||'',mode:'operator'}});
      render(data);
    }catch(e){
      if(result) result.innerHTML='<div class="pmd-error">'+esc(e.message)+'</div>';
    }finally{
      if(button){button.disabled=false;button.textContent='Run Director';}
    }
  }
  function install(){
    if(document.getElementById('pitmark-director-open')) return;
    const top=document.querySelector('.pm-top-actions');
    if(top){
      const b=document.createElement('button');
      b.id='pitmark-director-open'; b.type='button'; b.className='pm-button pm-button-ghost pmd-open';
      b.innerHTML='<span class="pmd-spark">✦</span><span class="pm-hide-small">Astra Director</span>';
      b.addEventListener('click',open); top.prepend(b);
    }
    const layer=document.createElement('div');
    layer.id='pitmark-director-layer'; layer.className='pmd-layer'; layer.hidden=true;
    layer.innerHTML='<button class="pmd-scrim" type="button" aria-label="Close"></button><section class="pmd-panel" role="dialog" aria-modal="true" aria-label="Pitmark Astra Director"><header><div><span>PITMARK EXECUTIVE AI</span><h1>Astra Director</h1><p>Reads the live operating picture. Escalates only what actually needs you.</p></div><button class="pmd-close" type="button">×</button></header><div class="pmd-controls"><textarea id="pitmark-director-request" placeholder="Optional: tell Astra what you want Pitmark to accomplish. Leave blank for a full operating review."></textarea><button id="pitmark-director-run" type="button">Run Director</button><small>On-demand only · no background Astra spend</small></div><div id="pitmark-director-result" class="pmd-result"><div class="pmd-empty">Run Director to review Pitmark’s live state.</div></div></section>';
    document.body.appendChild(layer);
    layer.querySelector('.pmd-scrim')?.addEventListener('click',close);
    layer.querySelector('.pmd-close')?.addEventListener('click',close);
    layer.querySelector('#pitmark-director-run')?.addEventListener('click',run);
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!layer.hidden)close();});
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',install); else install();
})();