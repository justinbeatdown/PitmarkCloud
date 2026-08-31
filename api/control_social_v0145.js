(() => {
  const $p = id => document.getElementById(id);
  const clean = value => {
    const raw = String(value ?? '').trim();
    return /^(justin|admin)[.!]?$/i.test(raw) ? '' : raw;
  };
  let live = {facebook:false, instagram:false};

  window.composePost = async function(){
    try{
      const p=$p('platform').value,g=$p('goal').value,t=clean($p('topic').value);
      if (!t && /^(justin|admin)[.!]?$/i.test(String($p('topic').value||'').trim())) $p('topic').value='';
      const x=await apiCall('/api/control/autopilot/composer/generate',{method:'POST',body:JSON.stringify({platform:p,goal:g,prompt:t||'Generate a useful Pitmark post',topic:t||null})});
      generated=x.body;
      $p('draft').textContent=x.body+(x.visual_suggestion?'\n\nVISUAL: '+x.visual_suggestion:'');
      $p('draft').classList.add('show');
    }catch(e){$p('draft').textContent='ERROR: '+e.message;$p('draft').classList.add('show')}
  };

  window.loadSocialPublishStatus = async function(){
    try{
      const x=await apiCall('/api/control/social/status');
      live.facebook=Boolean(x?.facebook?.configured);
      live.instagram=Boolean(x?.instagram?.configured);
      if (typeof socialPublishStatus === 'object') {
        socialPublishStatus.facebook = live.facebook;
        socialPublishStatus.instagram = live.instagram;
      }
      return x;
    }catch(e){live={facebook:false,instagram:false};return {}}
  };

  window.loadConnections = async function(){
    let base={}; let social={};
    try{base=await apiCall('/api/control/settings/connections')}catch(e){}
    try{social=await window.loadSocialPublishStatus()}catch(e){}
    for(const name of ['facebook','instagram','tiktok','x']){
      const el=$p('conn-'+name); if(!el) continue;
      let connected=Boolean(base?.[name]?.connected), ready=Boolean(base?.[name]?.ready);
      if(name==='facebook'){connected=Boolean(social?.facebook?.configured);ready=connected||ready}
      if(name==='instagram'){connected=Boolean(social?.instagram?.configured);ready=connected||ready}
      el.textContent=connected?'Connected':(ready?'Ready to authorize':'Setup required');
      el.className=connected?'connected':(ready?'ready':'');
    }
  };

  window.queueCard = function(p){
    const esc2 = typeof esc === 'function' ? esc : (x=>String(x??''));
    const when=p.scheduled_for?`<span>Scheduled: ${esc2(p.scheduled_for)}</span>`:'';
    const canApprove=p.status==='pending';
    const canSchedule=['pending','approved'].includes(p.status);
    const platform=String(p.platform||'').toLowerCase();
    const supported=['facebook','instagram'].includes(platform);
    const connected=Boolean(live[platform]);
    const canPublish=supported&&connected&&['approved','scheduled'].includes(p.status);
    const media=p.media_url?'<span>Media ready ✓</span>':(platform==='instagram'?'<span>Media: Auto-select from Pitmark pool</span>':'');
    return `<article class="queue-card" data-id="${p.id}"><div class="queue-card-top"><div><span class="status-pill status-${esc2(p.status)}">${esc2(p.status)}</span><strong>#${p.id} · ${esc2(p.platform)}</strong><span>${esc2(p.content_type)} · ${esc2(p.source)}</span>${when}${media}</div><span>${esc2((p.created_at||'').replace('T',' ').slice(0,16))}</span></div><div class="queue-body">${esc2(p.body)}</div><div class="queue-actions">${canApprove?'<button class="btn mini" data-action="approve">Approve</button>':''}<button class="btn secondary mini" data-action="reject">Reject</button>${canSchedule?'<input class="input schedule-input" type="datetime-local"><button class="btn secondary mini" data-action="schedule">Schedule</button>':''}<button class="btn ghost mini" data-action="archive">Archive</button>${platform==='instagram'?'<button class="btn ghost mini" data-action="asset">Pick Image</button>':''}<button class="btn ghost mini" data-action="publish" ${canPublish?'':'disabled'}>Publish</button></div></article>`;
  };

  window.loadQueue = async function(){
    try{
      await window.loadSocialPublishStatus();
      const filter=$p('queueFilter').value;
      const posts=await apiCall('/api/control/autopilot/posts'+(filter?'?status='+encodeURIComponent(filter):''));
      $p('queueList').innerHTML=posts.length?posts.map(window.queueCard).join(''):'<div class="empty-state">No posts in this queue yet.</div>';
    }catch(e){$p('queueList').innerHTML='<div class="error-box">'+String(e.message)+'</div>'}
  };

  window.queueAction = async function(card,action){
    const id=card.dataset.id;
    if(action==='asset'){
      try{const x=await apiCall(`/api/control/social/posts/${id}/assign-asset`,{method:'POST'});showToast('Image Selected ✓',x?.asset?.title||'Pitmark image assigned.');await window.loadQueue()}catch(e){showToast('Image Selection Failed',e.message,'error')}
      return;
    }
    if(action==='publish'){
      try{const x=await apiCall(`/api/control/social/posts/${id}/publish`,{method:'POST'});const p=String(x?.post?.platform||'social');showToast('Published ✓',p.charAt(0).toUpperCase()+p.slice(1)+' post is live.');await window.loadQueue();if(typeof loadStatus==='function')await loadStatus()}catch(e){showToast('Publish Failed',e.message,'error')}
      return;
    }
    const payload={action};
    if(action==='schedule'){const input=card.querySelector('.schedule-input');if(!input.value){input.focus();return}payload.scheduled_for=input.value}
    try{await apiCall(`/api/control/autopilot/posts/${id}/decision`,{method:'POST',body:JSON.stringify(payload)});await window.loadQueue();if(typeof loadStatus==='function')await loadStatus()}catch(e){showToast('Action Failed',e.message,'error')}
  };
  });
})();
