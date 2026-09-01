(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
  }[c]));
  let access = null;
  let roles = null;

  async function api(url, opt={}) {
    const headers = {...(opt.headers || {})};
    if (opt.body != null && !(opt.body instanceof FormData)) headers['Content-Type'] = 'application/json';
    const r = await fetch(url, {credentials:'same-origin', ...opt, headers});
    const t = await r.text();
    let d;
    try { d = JSON.parse(t); } catch { d = t; }
    if (!r.ok) throw new Error((d && d.detail) || t || `HTTP ${r.status}`);
    return d;
  }

  function has(permission) {
    return !!access && (access.role === 'owner' || access.role === 'admin' || (access.permissions || []).includes(permission));
  }

  function toast(title, detail, kind='info') {
    if (window.showToast) return window.showToast(title, detail, kind);
    console[kind === 'error' ? 'error' : 'log'](title, detail);
  }

  function currentDesktopView(name) {
    document.querySelectorAll('[data-view-section]').forEach(x => x.classList.toggle('active', x.dataset.viewSection === name));
    document.querySelectorAll('#nav [data-view]').forEach(x => x.classList.toggle('active', x.dataset.view === name));
  }

  function permissionForView(view) {
    return {
      dashboard:'dashboard',
      autopilot:'autopilot',
      shield:'shield',
      campaigns:'campaigns',
      outreach:'outreach',
      email:'mail',
      blog:'blog',
      directory:'directory',
      analytics:'analytics',
      settings:'settings',
    }[view] || 'dashboard';
  }

  function applyAccessToUI() {
    if (!access) return;
    const username = document.querySelector('.session-box strong');
    if (username) username.textContent = (access.display_name || access.username || '').toUpperCase();

    document.querySelectorAll('#nav [data-view]').forEach(btn => {
      const view = btn.dataset.view;
      btn.hidden = !has(permissionForView(view));
    });

    document.querySelectorAll('[data-mnav]').forEach(btn => {
      const view = btn.dataset.mnav;
      btn.hidden = !has(permissionForView(view === 'home' ? 'dashboard' : view));
    });

    document.querySelectorAll('[data-view-section]').forEach(section => {
      const view = section.dataset.viewSection;
      if (view && !has(permissionForView(view))) section.dataset.pm191Denied = '1';
    });
  }

  /* ---------------- PRT analytics ---------------- */
  function analyticsMarkup(mobile=false) {
    return `<div class="${mobile ? 'pm191-mobile-analytics' : 'view pm191-analytics-view'}" ${mobile ? '' : 'data-view-section="analytics"'}>
      <div class="pm191-section-head">
        <div><span class="pm19-kicker">PITMARK RACING TOOLS</span><h1>PRT Analytics</h1>
        <p>Real installs and usage flowing through Pitmark Cloud.</p></div>
        <button class="pm191-secondary" id="pm191AnalyticsRefresh">Refresh</button>
      </div>
      <div id="pm191AnalyticsBody"><div class="pm191-loading">Loading PRT usage…</div></div>
    </div>`;
  }

  function installAnalytics() {
    if (!has('analytics')) return;
    const nav = $('nav');
    const content = document.querySelector('.content');

    if (nav && content && !nav.querySelector('[data-view="analytics"]')) {
      const btn = document.createElement('button');
      btn.dataset.view = 'analytics';
      btn.innerHTML = '<span class="ico">⌁</span><span>PRT Analytics<small>Installs & Usage</small></span>';
      const settings = nav.querySelector('[data-view="settings"]');
      nav.insertBefore(btn, settings || null);
      btn.addEventListener('click', () => {
        currentDesktopView('analytics');
        loadAnalytics();
      });
    }
    if (content && !document.querySelector('[data-view-section="analytics"]')) {
      const wrap = document.createElement('div');
      wrap.innerHTML = analyticsMarkup(false);
      content.appendChild(wrap.firstElementChild);
    }

    const mobileSettings = document.querySelector('[data-mview="home"]') || document.querySelector('[data-mview="settings"]');
    if (mobileSettings && !mobileSettings.querySelector('[data-pm191-open-analytics]')) {
      const card = document.createElement('section');
      card.className = 'm-card pm191-mobile-launch';
      card.innerHTML = `<strong>PRT Analytics</strong><p>Installs, live sessions and activity.</p><button class="m-orange" data-pm191-open-analytics>Open Analytics</button><div data-pm191-mobile-analytics></div>`;
      mobileSettings.appendChild(card);
      card.querySelector('[data-pm191-open-analytics]').addEventListener('click', async () => {
        const target = card.querySelector('[data-pm191-mobile-analytics]');
        target.innerHTML = analyticsMarkup(true);
        await loadAnalytics(target);
      });
    }
  }

  function metric(label, value, sub='') {
    return `<article class="pm191-metric"><span>${esc(label)}</span><strong>${esc(value)}</strong>${sub ? `<small>${esc(sub)}</small>` : ''}</article>`;
  }

  async function loadAnalytics(scope=document) {
    const target = scope.querySelector?.('#pm191AnalyticsBody') || $('pm191AnalyticsBody');
    if (!target) return;
    target.innerHTML = '<div class="pm191-loading">Loading PRT usage…</div>';
    try {
      const x = await api('/api/prt/analytics/summary');
      target.innerHTML = `
        <div class="pm191-metrics">
          ${metric('Registered installs', x.registered_installs, `${x.registered_devices} devices registered`)}
          ${metric('Live right now', x.active_now, `${x.active_devices_24h} devices active in 24h`)}
          ${metric('Sessions today', x.sessions_today)}
          ${metric('Sessions · 7 days', x.sessions_7d)}
          ${metric('Total tracked sessions', x.total_sessions)}
          ${metric('Download clicks', x.downloads, x.download_tracking_ready ? 'Tracker ready for the public download button' : '')}
        </div>
        <div class="pm191-analytics-grid">
          <section class="pm191-card"><div class="pm191-card-head"><strong>Top tracks · 7 days</strong></div>
            <div class="pm191-ranked">${(x.top_tracks_7d || []).length ? x.top_tracks_7d.map((v,i)=>`<div><b>${i+1}</b><span>${esc(v.name)}</span><strong>${v.sessions}</strong></div>`).join('') : '<p>No tracked sessions yet.</p>'}</div>
          </section>
          <section class="pm191-card"><div class="pm191-card-head"><strong>Top cars · 7 days</strong></div>
            <div class="pm191-ranked">${(x.top_cars_7d || []).length ? x.top_cars_7d.map((v,i)=>`<div><b>${i+1}</b><span>${esc(v.name)}</span><strong>${v.sessions}</strong></div>`).join('') : '<p>No tracked sessions yet.</p>'}</div>
          </section>
        </div>
        <section class="pm191-card"><div class="pm191-card-head"><strong>Recent PRT sessions</strong><small>No personally identifying info is shown here.</small></div>
          <div class="pm191-session-list">${(x.recent_sessions || []).length ? x.recent_sessions.map(v=>`<article class="${v.active?'live':''}">
            <span class="pm191-live-dot"></span><div><strong>${esc(v.track_name || 'iRacing session')}</strong><small>${esc(v.car_name || '')}</small></div>
            <div><b>${v.max_lap ? `Lap ${v.max_lap}` : 'Session'}</b><small>${esc(v.device_id ? `Device …${v.device_id}` : '')}</small></div>
          </article>`).join('') : '<p class="pm191-empty">No PRT live-session history has been recorded yet.</p>'}</div>
        </section>`;
      target.closest('.pm191-analytics-view, .pm191-mobile-analytics')?.querySelector('#pm191AnalyticsRefresh')?.addEventListener('click', () => loadAnalytics(scope));
    } catch (err) {
      target.innerHTML = `<div class="pm191-error">${esc(err.message)}</div>`;
    }
  }

  /* ---------------- Team access ---------------- */
  function installTeamAccess() {
    if (!has('users')) return;
    const settings = document.querySelector('[data-view-section="settings"]') || document.querySelector('[data-mview="settings"]') || document.querySelector('[data-mview="more"]');
    if (!settings || settings.querySelector('#pm191TeamAccess')) return;
    const panel = document.createElement('section');
    panel.className = `${settings.dataset.mview ? 'm-card' : 'panel'} pm191-team-access`;
    panel.id = 'pm191TeamAccess';
    panel.innerHTML = `
      <div class="pm191-section-head compact"><div><span class="pm19-kicker">CONTROL CENTER ACCESS</span><h2>Team Access</h2>
      <p>Create logins without handing somebody full owner access.</p></div><button class="pm191-secondary" id="pm191UsersRefresh">Refresh</button></div>
      <div class="pm191-user-create">
        <input id="pm191UserName" autocomplete="off" placeholder="Username">
        <input id="pm191DisplayName" autocomplete="off" placeholder="Display name">
        <select id="pm191UserRole"><option value="marketing">Marketing</option><option value="support">Support</option><option value="viewer">Viewer</option><option value="admin">Admin</option></select>
        <input id="pm191UserPassword" type="password" autocomplete="new-password" placeholder="Temporary password · 12+ chars">
        <button class="pm191-primary" id="pm191UserCreate">Create account</button>
      </div>
      <div class="pm191-role-help">
        <span><b>Marketing</b> Content, campaigns, outreach, mail, blog & analytics</span>
        <span><b>Support</b> Shield, outreach, mail & analytics</span>
        <span><b>Viewer</b> Dashboard + analytics only</span>
        <span><b>Admin</b> Everything except owner-only protection</span>
      </div>
      <div id="pm191UserList"><div class="pm191-loading">Loading team access…</div></div>`;
    settings.appendChild(panel);
    $('pm191UsersRefresh').addEventListener('click', loadUsers);
    $('pm191UserCreate').addEventListener('click', createUser);
    loadUsers();
  }

  async function loadUsers() {
    const box = $('pm191UserList');
    if (!box) return;
    try {
      const users = await api('/api/control/access/users');
      box.innerHTML = users.map(u => `<article class="pm191-user-row" data-user-id="${u.id}">
        <div class="pm191-user-avatar">${esc((u.display_name || u.username || '?').slice(0,1).toUpperCase())}</div>
        <div class="pm191-user-identity"><strong>${esc(u.display_name || u.username)}</strong><span>@${esc(u.username)}</span></div>
        <select data-role ${u.is_owner?'disabled':''}>
          ${['owner','admin','marketing','support','viewer'].map(r=>`<option value="${r}" ${u.role===r?'selected':''} ${r==='owner'&&!u.is_owner?'disabled':''}>${r}</option>`).join('')}
        </select>
        <label class="pm191-user-active"><input type="checkbox" data-active ${u.active?'checked':''} ${u.is_owner?'disabled':''}> Active</label>
        <div class="pm191-user-actions">
          ${u.is_owner?'<span class="pm191-owner">OWNER</span>':`<button data-save>Save</button><button data-password>Password</button><button class="danger" data-delete>Delete</button>`}
        </div>
      </article>`).join('');

      box.querySelectorAll('[data-save]').forEach(b => b.addEventListener('click', async () => {
        const row=b.closest('.pm191-user-row');
        await api(`/api/control/access/users/${row.dataset.userId}`, {method:'PATCH',body:JSON.stringify({
          role:row.querySelector('[data-role]').value,
          active:row.querySelector('[data-active]').checked
        })});
        toast('Access updated','The user must sign in again for the new permissions.');
        loadUsers();
      }));
      box.querySelectorAll('[data-password]').forEach(b => b.addEventListener('click', async () => {
        const row=b.closest('.pm191-user-row');
        const pw=prompt('Enter a new password (12+ characters).');
        if (!pw) return;
        await api(`/api/control/access/users/${row.dataset.userId}/password`, {method:'POST',body:JSON.stringify({password:pw})});
        toast('Password reset','Existing sessions for that user were invalidated.');
      }));
      box.querySelectorAll('[data-delete]').forEach(b => b.addEventListener('click', async () => {
        const row=b.closest('.pm191-user-row');
        if (!confirm('Delete this Control Center account?')) return;
        await api(`/api/control/access/users/${row.dataset.userId}`, {method:'DELETE'});
        loadUsers();
      }));
    } catch (err) {
      box.innerHTML=`<div class="pm191-error">${esc(err.message)}</div>`;
    }
  }

  async function createUser() {
    const username=$('pm191UserName').value.trim();
    const display_name=$('pm191DisplayName').value.trim();
    const role=$('pm191UserRole').value;
    const password=$('pm191UserPassword').value;
    try {
      await api('/api/control/access/users',{method:'POST',body:JSON.stringify({username,display_name,role,password})});
      $('pm191UserName').value=''; $('pm191DisplayName').value=''; $('pm191UserPassword').value='';
      toast('Account created', `${display_name || username} can now sign into Control Center.`);
      loadUsers();
    } catch(err){ toast('Could not create account',err.message,'error'); }
  }

  /* ---------------- Campaign / Outreach UX ---------------- */
  function decorateRookieCard(card) {
    if (card.dataset.pm191) return;
    card.dataset.pm191='1';
    const controls=card.querySelector('.outreach-fields');
    if (controls && !controls.closest('.pm191-manage')) {
      const details=document.createElement('details');
      details.className='pm191-manage';
      details.innerHTML='<summary><span>Manage racer</span><small>Stage, intake, media & research</small></summary>';
      controls.parentNode.insertBefore(details,controls);
      details.appendChild(controls);
    }
  }

  function decorateOutreachCard(card) {
    if (card.dataset.pm191) return;
    card.dataset.pm191='1';
    const controls=card.querySelector('.outreach-edit');
    if (controls && !controls.closest('.pm191-manage')) {
      const email=controls.querySelector('.ocontact')?.value || '';
      const method=controls.querySelector('.omethod')?.value || '';
      const details=document.createElement('details');
      details.className='pm191-manage';
      details.innerHTML=`<summary><span>Manage relationship</span><small>${esc([method,email].filter(Boolean).join(' · ') || 'Contact details & follow-up')}</small></summary>`;
      controls.parentNode.insertBefore(details,controls);
      details.appendChild(controls);
    }
  }

  function outreachOverview() {
    const output=$('outreachOutput');
    if (!output) return;
    const view=output.closest('[data-view-section="outreach"]');
    if (!view) return;
    let board=view.querySelector('.pm191-outreach-overview');
    if (!board) {
      board=document.createElement('div');
      board.className='pm191-outreach-overview';
      output.parentNode.insertBefore(board,output);
    }
    const cards=[...output.querySelectorAll('.outreach-card')];
    const counts={prospect:0,contacted:0,interested:0,partner:0,supporter:0};
    cards.forEach(card=>{
      const stage=card.querySelector('.ostage')?.value || card.querySelector('.status-pill')?.textContent?.trim().toLowerCase();
      if (stage in counts) counts[stage]++;
    });
    const nextHtml=Object.entries(counts).map(([k,v])=>`<div><strong>${v}</strong><span>${k}</span></div>`).join('');
    if (board.innerHTML !== nextHtml) board.innerHTML=nextHtml;
  }


  function collapseCreateForm(buttonId, label, help) {
    const button=$(buttonId);
    if (!button) return;
    const form=button.closest('.outreach-fields, .outreach-form, .quick-grid, .form-grid, .record-fields') || button.parentElement;
    if (!form || form.closest('.pm191-create-panel')) return;
    const details=document.createElement('details');
    details.className='pm191-create-panel';
    details.innerHTML=`<summary><span>＋ ${esc(label)}</span><small>${esc(help)}</small></summary>`;
    form.parentNode.insertBefore(details,form);
    details.appendChild(form);
  }

  function upgradeOperationalPages() {
    const campaigns=document.querySelector('[data-view-section="campaigns"]');
    if (campaigns) {
      campaigns.classList.add('pm191-campaigns');
      collapseCreateForm('addRookieBtn','Add racer','Start a new Rookie Year profile');
      campaigns.querySelectorAll('.rookie-card').forEach(decorateRookieCard);
    }
    const outreach=document.querySelector('[data-view-section="outreach"]');
    if (outreach) {
      outreach.classList.add('pm191-outreach');
      collapseCreateForm('addOutreachBtn','Add relationship','Track a new league, track, team or partner');
      outreach.querySelectorAll('.outreach-card').forEach(decorateOutreachCard);
      outreachOverview();
    }
  }


  function installMobileCampaignAccess() {
    if (!has('campaigns')) return;
    const more=document.querySelector('[data-mview="more"]');
    if (!more || more.querySelector('[data-pm191-campaign-mobile]')) return;
    const wrap=document.createElement('section');
    wrap.className='m-card pm191-mobile-campaign';
    wrap.dataset.pm191CampaignMobile='1';
    wrap.innerHTML=`<div class="m-card-head"><h2>Rookie Year 2026</h2><button class="m-ghost" id="pm191MobileCampaignRefresh">Refresh</button></div>
      <p>Campaign participants and current stage.</p><div id="pm191MobileCampaignList"><p>Loading campaign…</p></div>`;
    more.prepend(wrap);
    $('pm191MobileCampaignRefresh')?.addEventListener('click',loadMobileCampaign);
    loadMobileCampaign();
  }

  async function loadMobileCampaign() {
    const box=$('pm191MobileCampaignList');
    if (!box) return;
    try {
      const x=await api('/api/control/campaigns/rookie-year');
      const stages=['prospect','interested','intake_sent','submitted','verification','ready_for_review','selected','story_building','racer_review','scheduled','published','alumni'];
      box.innerHTML=(x.participants||[]).length ? x.participants.map(r=>`<article class="pm191-mobile-racer" data-id="${r.id}">
        <div><strong>${esc(r.name)}</strong><span>${esc(r.intake_status)} · ${esc(r.verification_status)}</span></div>
        <select data-stage>${stages.map(v=>`<option value="${v}" ${v===r.stage?'selected':''}>${v.replaceAll('_',' ')}</option>`).join('')}</select>
        <button data-save>Save</button></article>`).join('') : '<p class="pm191-empty">No racers in this campaign yet.</p>';
      box.querySelectorAll('[data-save]').forEach(b=>b.addEventListener('click',async()=>{
        const row=b.closest('.pm191-mobile-racer');
        await api(`/api/control/campaigns/rookie-year/participants/${row.dataset.id}`,{method:'POST',body:JSON.stringify({stage:row.querySelector('[data-stage]').value})});
        toast('Racer updated','Campaign stage saved.');
      }));
    } catch(err) {
      box.innerHTML=`<div class="pm191-error">${esc(err.message)}</div>`;
    }
  }

  /* ---------------- Blog preview ---------------- */
  function sanitizeFragment(html) {
    const doc=new DOMParser().parseFromString(String(html||''),'text/html');
    doc.querySelectorAll('script,iframe,object,embed,form').forEach(x=>x.remove());
    doc.querySelectorAll('*').forEach(el=>[...el.attributes].forEach(a=>{if(a.name.toLowerCase().startsWith('on'))el.removeAttribute(a.name)}));
    return doc.body.innerHTML;
  }

  function upgradeBlogPreviews() {
    document.querySelectorAll('#blogOutput .blog-preview').forEach(box=>{
      if (box.dataset.pm191) return;
      const raw=box.textContent || '';
      if (/<[a-z][\s\S]*>/i.test(raw)) {
        box.innerHTML=sanitizeFragment(raw);
        box.dataset.pm191='1';
      }
    });
  }

  /* ---------------- Context-aware Instagram images ---------------- */
  async function generateContextImage(card, button) {
    const id=Number(card?.dataset.id || 0);
    if (!id) return;
    const old=button.textContent;
    button.disabled=true;
    button.textContent='Generating story image…';
    try {
      const x=await api(`/api/control/social/posts/${id}/context-image`,{method:'POST'});
      toast('Story image ready', 'Generated for this post — no random merchandise.');
      if (window.loadQueue) await window.loadQueue();
      return x;
    } catch(err) {
      toast('Image generation failed',err.message,'error');
      throw err;
    } finally {
      button.disabled=false;
      button.textContent=old;
    }
  }

  function upgradeQueueButtons() {
    document.querySelectorAll('.queue-card').forEach(card=>{
      const text=card.textContent.toLowerCase();
      if (!text.includes('instagram')) return;
      const asset=card.querySelector('[data-action="asset"]');
      if (asset && asset.textContent !== 'Generate Story Image') {
        asset.textContent='Generate Story Image';
      }
    });
  }

  document.addEventListener('click', async e=>{
    const asset=e.target.closest('.queue-card [data-action="asset"]');
    if (asset) {
      e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
      await generateContextImage(asset.closest('.queue-card'),asset).catch(()=>{});
      return;
    }
    const publish=e.target.closest('.queue-card [data-action="publish"]');
    if (publish) {
      const card=publish.closest('.queue-card');
      const isInstagram=card?.textContent.toLowerCase().includes('instagram');
      const image=card?.querySelector('.queue-media-preview img');
      const src=String(image?.getAttribute('src') || '').toLowerCase();
      const intelligence=card?.textContent.toLowerCase().includes('intelligence:');
      const looksLikeProduct=intelligence && (src.includes('cdn.shopify.com') || src.includes('/products/') || src.includes('shopify'));
      const hasStoryImage=!!image && !looksLikeProduct;
      if (isInstagram && !hasStoryImage && !publish.disabled) {
        e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
        try {
          await generateContextImage(card,publish);
          const id=Number(card.dataset.id);
          await api(`/api/control/social/posts/${id}/publish`,{method:'POST'});
          toast('Published ✓','Instagram post published with a story-specific image.');
          if (window.loadQueue) await window.loadQueue();
        } catch {}
      }
    }
  }, true);

  /* ---------------- boot ---------------- */
  async function boot() {
    try {
      access=await api('/api/control/access/me');
      roles=await api('/api/control/access/roles');
    } catch(err) {
      console.warn('Control access profile unavailable',err);
      return;
    }
    applyAccessToUI();
    installAnalytics();
    installTeamAccess();
    installMobileCampaignAccess();
    upgradeOperationalPages();
    upgradeBlogPreviews();
    upgradeQueueButtons();

    // v0.19.4: observe only the workspaces that actually need enhancement.
    // The previous body-wide observer woke up for Mail, queue counters, compose,
    // analytics, navigation and nearly every other UI mutation.
    const observeWorkspace=(selector,enhance)=>{
      const target=document.querySelector(selector);
      if(!target)return;
      let pending=false;
      const observer=new MutationObserver(mutations=>{
        if(!mutations.some(m=>m.addedNodes.length||m.removedNodes.length))return;
        if(pending)return;
        pending=true;
        requestAnimationFrame(()=>{
          pending=false;
          enhance();
        });
      });
      observer.observe(target,{childList:true,subtree:true});
    };

    // Mobile does not use the desktop record-card decorators. Avoid keeping a
    // global enhancement loop alive on the phone entirely.
    const mobile=!!document.querySelector('[data-mview]');
    if(!mobile){
      observeWorkspace('#rookieOutput',upgradeOperationalPages);
      observeWorkspace('#outreachOutput',upgradeOperationalPages);
      observeWorkspace('#blogOutput',upgradeBlogPreviews);
      observeWorkspace('#queueList',upgradeQueueButtons);
    }
  }

  document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,180));
})();