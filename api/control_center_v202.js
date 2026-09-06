(() => {
  'use strict';

  // Control Center is not an email client. Gmail remains server-side for Shield
  // and automation, so legacy mail bootstrap reads are short-circuited.
  const nativeFetch = window.fetch.bind(window);
  window.fetch = function pitmarkControlFetch(input, init) {
    try {
      const raw = typeof input === 'string' ? input : input?.url || '';
      const url = new URL(raw, location.origin);
      if (url.origin === location.origin) {
        if (url.pathname === '/api/control/email/identities') {
          return Promise.resolve(new Response(JSON.stringify([]), {status:200,headers:{'Content-Type':'application/json'}}));
        }
        if (url.pathname === '/api/control/email/preferences') {
          return Promise.resolve(new Response(JSON.stringify({}), {status:200,headers:{'Content-Type':'application/json'}}));
        }
      }
    } catch (_) {}
    return nativeFetch(input, init);
  };

  function installNoMailStyle() {
    if (document.getElementById('pm216-no-mail-style')) return;
    const style = document.createElement('style');
    style.id = 'pm216-no-mail-style';
    style.textContent = `
      html body .shell>.sidebar>.nav>button[data-view="email"],
      html body .content>[data-view-section="email"],
      html body [data-pm19-go="email"],html body [data-go="email"],
      html body #pm19ComposeOverlay,html body #pm204BulkBar,
      html body [data-mview="email"],html body .m-nav>button[data-mnav="email"],
      html body [data-mgo="email"]{display:none!important;visibility:hidden!important;pointer-events:none!important}
    `;
    document.head.appendChild(style);
  }

  function activate(view) {
    if (view === 'email') view = 'dashboard';
    if (typeof window.setView === 'function') { window.setView(view); return; }
    document.querySelectorAll('[data-view-section]').forEach(s => s.classList.toggle('active', s.dataset.viewSection === view));
    document.querySelectorAll('#nav [data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === view));
    location.hash = `#${view}`;
  }

  function repairDirectMailRoute() {
    if (String(location.hash || '').toLowerCase() !== '#email') return;
    history.replaceState(null, '', `${location.pathname}${location.search}#dashboard`);
    activate('dashboard');
  }

  function addAnalyticsNav() {
    if (innerWidth <= 980) return;
    const nav = document.getElementById('nav');
    if (!nav || nav.querySelector('[data-view="analytics"]')) return;
    const button = document.createElement('button');
    button.dataset.view = 'analytics';
    button.innerHTML = '<span class="ico">⌁</span><span>PRT<small>Access & Analytics</small></span>';
    button.addEventListener('click', () => activate('analytics'));
    nav.insertBefore(button, nav.querySelector('[data-view="directory"]') || null);
  }

  async function applyAccessPermissions() {
    try {
      const response = await nativeFetch('/api/control/access/me', {credentials:'same-origin'});
      if (!response.ok) return;
      const access = await response.json();
      if (access.role === 'owner' || access.role === 'admin') return;
      document.querySelectorAll('#nav [data-view]').forEach(button => {
        const view = button.dataset.view;
        if (!view || view === 'dashboard' || view === 'email') return;
        button.hidden = !(access.permissions || []).includes(view);
      });
    } catch (error) {
      console.warn('Control Center access profile unavailable; keeping current navigation.', error);
    }
  }

  function cleanMailCopy() {
    const heroCopy = document.querySelector('.pm19-command-hero p');
    if (heroCopy && /\bmail\b/i.test(heroCopy.textContent || '')) {
      heroCopy.textContent = 'Publishing, security, partnerships and content — each tool gets a focused workspace without turning Control Center into an inbox.';
    }
    const shieldQuick = document.querySelector('[data-go="shield"] span');
    if (shieldQuick && /messages needing a human call/i.test(shieldQuick.textContent || '')) {
      shieldQuick.textContent = 'Inspect communications that need a security decision';
    }
  }

  function installMobileV3Style() {
    if (location.pathname !== '/control/mobile' || document.getElementById('pm2135-mobile-v3-style')) return;
    const style = document.createElement('style');
    style.id = 'pm2135-mobile-v3-style';
    style.textContent = `
      body.pm-mobile-v3{
        --v3-orange:#ff5500;--v3-orange2:#ff7430;--v3-bg:#080a0c;--v3-surface:#111419;
        --v3-surface2:#171b20;--v3-line:rgba(255,255,255,.085);--v3-text:#f5f6f7;
        --v3-muted:#858d96;--v3-green:#4bdb82;--v3-red:#ff6b66;
        background:#080a0c!important;color:var(--v3-text)!important;
      }
      body.pm-mobile-v3 .m-app{min-height:100dvh!important;padding-bottom:86px!important}
      body.pm-mobile-v3 .m-head{
        position:sticky!important;top:0!important;z-index:40!important;min-height:58px!important;padding:8px 14px!important;
        border:0!important;border-bottom:1px solid var(--v3-line)!important;background:rgba(8,10,12,.96)!important;
        backdrop-filter:blur(18px)!important;box-shadow:none!important;
      }
      body.pm-mobile-v3 .m-brand{gap:9px!important}
      body.pm-mobile-v3 .m-brand img{width:36px!important;height:36px!important}
      body.pm-mobile-v3 .m-brand strong{font-size:14px!important;font-style:normal!important;letter-spacing:.025em!important}
      body.pm-mobile-v3 .m-brand span{margin-top:2px!important;color:#6f7780!important;font-size:7px!important;letter-spacing:.12em!important}
      body.pm-mobile-v3 .m-head .m-ghost{min-height:34px!important;padding:6px 10px!important;border:1px solid var(--v3-line)!important;border-radius:10px!important;background:#111419!important;color:#aeb4ba!important;font-size:8px!important}
      body.pm-mobile-v3 .m-main{width:100%!important;max-width:600px!important;margin:0 auto!important;padding:17px 14px 28px!important}
      body.pm-mobile-v3 .m-view{animation:pmv3in .14s ease!important}
      @keyframes pmv3in{from{opacity:.5;transform:translateY(4px)}to{opacity:1;transform:none}}

      .pmv3-pagehead{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:2px 1px 18px}
      .pmv3-pagehead small{display:block;margin-bottom:4px;color:#747d86;font-size:8px;font-weight:900;letter-spacing:.14em;text-transform:uppercase}
      .pmv3-pagehead h1{margin:0!important;font-size:30px!important;line-height:1!important;letter-spacing:-.035em!important;text-transform:none!important;font-style:normal!important}
      .pmv3-live{display:inline-flex;align-items:center;gap:6px;padding:6px 8px;border-radius:999px;background:rgba(75,219,130,.08);color:#66e295;font-size:8px;font-weight:900}
      .pmv3-live:before{content:"";width:6px;height:6px;border-radius:50%;background:var(--v3-green);box-shadow:0 0 8px rgba(75,219,130,.6)}

      .pmv3-focus{display:grid;grid-template-columns:1fr auto;gap:16px;align-items:center;margin-bottom:18px;padding:18px;border:1px solid rgba(255,85,0,.22);border-radius:18px;background:linear-gradient(145deg,rgba(255,85,0,.10),#14171b 45%,#101318);box-shadow:0 14px 35px rgba(0,0,0,.22)}
      .pmv3-focus small{display:block;color:#ff8146;font-size:8px;font-weight:900;letter-spacing:.13em;text-transform:uppercase}
      .pmv3-focus strong{display:block;margin:5px 0 1px;font-size:35px;line-height:1;font-weight:850;letter-spacing:-.04em}
      .pmv3-focus span{display:block;color:#9aa1a8;font-size:10px;line-height:1.35}
      .pmv3-primary{min-width:98px;min-height:48px;padding:10px 13px;border:0;border-radius:13px;background:var(--v3-orange);color:white;font-size:9px;font-weight:900;text-transform:uppercase;box-shadow:0 9px 24px rgba(255,85,0,.20)}

      .pmv3-section-head{display:flex;align-items:center;justify-content:space-between;margin:18px 2px 8px}
      .pmv3-section-head strong{font-size:10px;letter-spacing:.04em}
      .pmv3-section-head span{color:#69717a;font-size:8px}
      .pmv3-task-list{overflow:hidden;border:1px solid var(--v3-line);border-radius:16px;background:var(--v3-surface)}
      .pmv3-task{display:grid;grid-template-columns:42px 1fr auto;gap:10px;align-items:center;width:100%;min-height:68px;padding:10px 13px;border:0;border-bottom:1px solid rgba(255,255,255,.055);background:transparent;color:white;text-align:left}
      .pmv3-task:last-child{border-bottom:0}
      .pmv3-task:active{background:rgba(255,255,255,.035)}
      .pmv3-icon{display:grid;place-items:center;width:38px;height:38px;border-radius:12px;background:#1a1e23;color:#cbd0d4;font-size:16px}
      .pmv3-task.attention .pmv3-icon{background:rgba(255,85,0,.13);color:#ff8146}
      .pmv3-task-copy b{display:block;font-size:12px;font-weight:750}
      .pmv3-task-copy span{display:block;margin-top:3px;color:#777f88;font-size:9px;line-height:1.3}
      .pmv3-count{min-width:32px;text-align:right;font-size:22px;font-weight:850;letter-spacing:-.04em}
      .pmv3-task.attention .pmv3-count{color:#ff7430}

      .pmv3-alerts{margin-top:8px;border:1px solid var(--v3-line);border-radius:16px;background:var(--v3-surface);overflow:hidden}
      .pmv3-alerts-head{display:flex;align-items:center;justify-content:space-between;padding:13px 14px 8px}
      .pmv3-alerts-head b{font-size:11px}.pmv3-alerts-head span{color:#777f88;font-size:8px}
      body.pm-mobile-v3 #mNotifications{padding:0 7px 7px}
      body.pm-mobile-v3 #mNotifications .m-row{margin:0!important;padding:11px 8px!important;border:0!important;border-top:1px solid rgba(255,255,255,.055)!important;border-radius:0!important;background:transparent!important}
      body.pm-mobile-v3 #mNotifications .m-row b{font-size:10px!important;text-transform:none!important}
      body.pm-mobile-v3 #mNotifications .m-row span{font-size:8px!important}
      body.pm-mobile-v3 #mNotifications>p{margin:0;padding:13px;color:#7e8790;font-size:10px}

      .pmv3-system{margin-top:10px;border:1px solid var(--v3-line);border-radius:14px;background:#0d1013;overflow:hidden}
      .pmv3-system>summary{list-style:none;padding:13px 14px;color:#9ba2a9;font-size:9px;font-weight:800;cursor:pointer}
      .pmv3-system>summary::-webkit-details-marker{display:none}.pmv3-system>summary:after{content:"›";float:right;color:#666f77;font-size:17px;line-height:10px;transition:.15s}.pmv3-system[open]>summary:after{transform:rotate(90deg)}
      .pmv3-system-body{padding:0 12px 12px}.pmv3-system-body p{margin:8px 0;color:#7f8790;font-size:9px;line-height:1.4}
      .pmv3-system-status{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}.pmv3-system-status span{padding:5px 7px;border-radius:8px;background:#15191e;color:#879099;font-size:8px}
      .pmv3-system-actions{display:grid;grid-template-columns:1fr 1fr;gap:7px}
      .pmv3-system-actions button{min-height:40px;border:1px solid var(--v3-line);border-radius:10px;background:#171b20;color:#d7dade;font-size:8px;font-weight:900;text-transform:uppercase}

      body.pm-mobile-v3 .m-title{margin:2px 1px 14px!important}
      body.pm-mobile-v3 .m-title h1{font-size:25px!important;line-height:1!important;letter-spacing:-.025em!important;text-transform:none!important;font-style:normal!important}
      body.pm-mobile-v3 .m-card,body.pm-mobile-v3 .m-row,body.pm-mobile-v3 .m-item{border:1px solid var(--v3-line)!important;border-radius:15px!important;background:var(--v3-surface)!important;box-shadow:none!important}
      body.pm-mobile-v3 .m-card{padding:14px!important;margin-bottom:9px!important}
      body.pm-mobile-v3 .m-card h2{font-size:14px!important;font-style:normal!important;text-transform:none!important}
      body.pm-mobile-v3 .m-row{padding:13px!important;margin-bottom:7px!important}
      body.pm-mobile-v3 .m-row b{font-size:11px!important;text-transform:none!important}
      body.pm-mobile-v3 .m-row span{font-size:9px!important}
      body.pm-mobile-v3 .m-item{padding:13px!important;margin-bottom:8px!important}
      body.pm-mobile-v3 label{margin-top:11px!important;color:#7d858d!important;font-size:8px!important;letter-spacing:.07em!important}
      body.pm-mobile-v3 input,body.pm-mobile-v3 select,body.pm-mobile-v3 textarea{min-height:46px!important;margin-top:6px!important;padding:11px 12px!important;border:1px solid rgba(255,255,255,.11)!important;border-radius:11px!important;background:#090b0d!important;color:#f5f6f7!important}
      body.pm-mobile-v3 textarea{min-height:112px!important}
      body.pm-mobile-v3 .m-orange,body.pm-mobile-v3 .m-ghost{min-height:42px!important;padding:9px 11px!important;border-radius:10px!important;font-size:9px!important}
      body.pm-mobile-v3 .m-orange{background:var(--v3-orange)!important;border-color:#ff6c1e!important}
      body.pm-mobile-v3 .m-ghost{background:#171b20!important;border-color:var(--v3-line)!important}

      .pmv3-review-toolbar{display:flex;gap:8px;margin:-3px 0 11px}.pmv3-review-toolbar button{flex:1;min-height:44px;border:1px solid var(--v3-line);border-radius:12px;background:#15191e;color:#cdd1d5;font-size:9px;font-weight:900}.pmv3-review-toolbar button.primary{background:var(--v3-orange);border-color:#ff6b1d;color:#fff}
      body.pm-mobile-v3 .pmv3-composer-collapsed{display:none!important}
      body.pm-mobile-v3 #mQueueFilter{margin-top:0!important}
      body.pm-mobile-v3 #mQueue .m-actions{display:grid!important;grid-template-columns:1fr 1fr!important;gap:7px!important}
      body.pm-mobile-v3 #mQueue .m-actions button{min-height:40px!important}
      body.pm-mobile-v3 #mQueue .m-actions .schedule{grid-column:1/-1!important;width:100%!important;margin:0!important}

      .pmv3-more-list{overflow:hidden;margin-bottom:12px;border:1px solid var(--v3-line);border-radius:16px;background:var(--v3-surface)}
      .pmv3-more-list button,.pmv3-more-list a{display:grid;grid-template-columns:38px 1fr auto;gap:10px;align-items:center;width:100%;min-height:62px;padding:10px 13px;border:0;border-bottom:1px solid rgba(255,255,255,.055);background:transparent;color:#fff;text-align:left;text-decoration:none}
      .pmv3-more-list>*:last-child{border-bottom:0}.pmv3-more-list i{display:grid;place-items:center;width:34px;height:34px;border-radius:10px;background:#1a1e23;font-style:normal}.pmv3-more-list b{display:block;font-size:11px}.pmv3-more-list span{display:block;margin-top:2px;color:#777f88;font-size:8px}.pmv3-more-list em{color:#626a72;font-style:normal;font-size:16px}

      body.pm-mobile-v3 .m-nav{position:fixed!important;left:0!important;right:0!important;bottom:0!important;z-index:60!important;display:grid!important;grid-template-columns:repeat(5,1fr)!important;width:100%!important;transform:none!important;padding:6px 7px calc(6px + env(safe-area-inset-bottom))!important;border:0!important;border-top:1px solid var(--v3-line)!important;border-radius:0!important;background:rgba(10,12,14,.97)!important;box-shadow:0 -12px 35px rgba(0,0,0,.34)!important;backdrop-filter:blur(20px)!important}
      body.pm-mobile-v3 .m-nav button{position:relative!important;min-height:50px!important;padding:4px 2px!important;border:0!important;border-radius:11px!important;background:transparent!important;color:#68717a!important;font-size:16px!important}
      body.pm-mobile-v3 .m-nav button span{display:block!important;margin-top:2px!important;font-size:7px!important;font-weight:800!important;text-transform:none!important;letter-spacing:0!important}
      body.pm-mobile-v3 .m-nav button.active{background:rgba(255,85,0,.09)!important;color:#ff7430!important}
      body.pm-mobile-v3 .m-nav .pmv3-create-nav{align-self:center;justify-self:center;width:48px;height:48px;min-height:48px!important;border-radius:16px!important;background:var(--v3-orange)!important;color:#fff!important;font-size:27px!important;line-height:1!important;box-shadow:0 8px 24px rgba(255,85,0,.25)!important}
      body.pm-mobile-v3 .m-nav .pmv3-create-nav span{display:none!important}

      .pmv3-sheet-backdrop{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.58);backdrop-filter:blur(3px);opacity:0;pointer-events:none;transition:.16s}
      .pmv3-sheet-backdrop.open{opacity:1;pointer-events:auto}
      .pmv3-sheet{position:absolute;left:10px;right:10px;bottom:calc(10px + env(safe-area-inset-bottom));padding:8px;border:1px solid var(--v3-line);border-radius:22px;background:#15191e;box-shadow:0 24px 65px rgba(0,0,0,.55);transform:translateY(18px);transition:.16s}
      .pmv3-sheet-backdrop.open .pmv3-sheet{transform:none}
      .pmv3-sheet-grip{width:36px;height:4px;margin:4px auto 10px;border-radius:4px;background:#41484f}
      .pmv3-sheet h2{margin:4px 7px 12px;font-size:18px}.pmv3-sheet button{display:grid;grid-template-columns:42px 1fr auto;gap:10px;align-items:center;width:100%;min-height:64px;padding:8px 10px;border:0;border-top:1px solid rgba(255,255,255,.055);background:transparent;color:#fff;text-align:left}.pmv3-sheet button:first-of-type{border-top:0}.pmv3-sheet button i{display:grid;place-items:center;width:38px;height:38px;border-radius:12px;background:#20252b;font-style:normal}.pmv3-sheet button b{display:block;font-size:12px}.pmv3-sheet button span{display:block;margin-top:2px;color:#7f8790;font-size:9px}.pmv3-sheet button em{font-style:normal;color:#626a72;font-size:17px}

      @media(max-width:370px){.pmv3-focus{grid-template-columns:1fr}.pmv3-primary{width:100%}.pmv3-pagehead h1{font-size:27px!important}}
    `;
    document.head.appendChild(style);
  }

  function mobileGo(name) {
    if (name === 'email') name = 'home';
    if (typeof window.view === 'function') window.view(name);
    else {
      document.querySelectorAll('[data-mview]').forEach(x => x.classList.toggle('active', x.dataset.mview === name));
    }
    document.querySelectorAll('.m-nav [data-pmv3nav]').forEach(b => b.classList.toggle('active', b.dataset.pmv3nav === name));
    window.scrollTo({top:0, behavior:'smooth'});
  }

  function updateMobileAttention() {
    const ids = ['mPending','mShield','mOutreach','mBlog'];
    let total = 0;
    ids.forEach(id => {
      const el = document.getElementById(id);
      const n = Number(String(el?.textContent || '').replace(/[^0-9.-]/g,''));
      if (Number.isFinite(n) && n > 0) total += n;
      el?.closest('.pmv3-task')?.classList.toggle('attention', Number.isFinite(n) && n > 0);
    });
    const totalEl = document.getElementById('pmv3Total');
    const copy = document.getElementById('pmv3TotalCopy');
    const button = document.getElementById('pmv3ReviewNow');
    if (totalEl) totalEl.textContent = total;
    if (copy) copy.textContent = total ? 'items waiting for a decision' : 'Nothing urgent needs you right now';
    if (button) button.textContent = total ? 'Review now' : 'Open review';
  }

  function rebuildHome() {
    const home = document.querySelector('[data-mview="home"]');
    if (!home || home.dataset.pmv3 === '1') return;
    home.dataset.pmv3 = '1';
    home.innerHTML = `
      <div class="pmv3-pagehead"><div><small>Pitmark Control</small><h1>Today</h1></div><span class="pmv3-live">Cloud live</span></div>
      <section class="pmv3-focus">
        <div><small>Needs your attention</small><strong id="pmv3Total">—</strong><span id="pmv3TotalCopy">Checking Pitmark…</span></div>
        <button class="pmv3-primary" id="pmv3ReviewNow">Review now</button>
      </section>
      <div class="pmv3-section-head"><strong>Work queue</strong><span>tap to open</span></div>
      <div class="pmv3-task-list">
        <button class="pmv3-task" data-pmv3go="autopilot"><span class="pmv3-icon">✓</span><span class="pmv3-task-copy"><b>Posts to review</b><span>Approve, schedule or publish</span></span><b class="pmv3-count" id="mPending">—</b></button>
        <button class="pmv3-task" data-pmv3go="shield"><span class="pmv3-icon">⬡</span><span class="pmv3-task-copy"><b>Shield review</b><span>Security decisions that need a human</span></span><b class="pmv3-count" id="mShield">—</b></button>
        <button class="pmv3-task" data-pmv3go="outreach"><span class="pmv3-icon">🤝</span><span class="pmv3-task-copy"><b>Outreach</b><span>Tracks, racers and partner follow-ups</span></span><b class="pmv3-count" id="mOutreach">—</b></button>
        <button class="pmv3-task" data-pmv3go="blog"><span class="pmv3-icon">▤</span><span class="pmv3-task-copy"><b>Draft articles</b><span>Review and publish Pitmark stories</span></span><b class="pmv3-count" id="mBlog">—</b></button>
      </div>
      <div class="pmv3-section-head"><strong>Recent alerts</strong><span id="mNotificationCount">—</span></div>
      <section class="pmv3-alerts"><div id="mNotifications"><p>Checking Pitmark…</p></div></section>
      <details class="pmv3-system"><summary>System & automation</summary><div class="pmv3-system-body">
        <div class="pmv3-system-status"><span id="mSocialStatus">Checking publishing…</span><span id="mAssetStatus">Checking assets…</span></div>
        <p id="mIntelSummary">Checking Autopilot…</p>
        <div class="pmv3-system-actions"><button id="mRunIntel">Run Intelligence</button><button id="mSyncAssets">Sync Assets</button></div>
      </div></details>
      <button id="mInstall" class="m-install hidden">Install Pitmark Mobile</button>`;

    home.querySelectorAll('[data-pmv3go]').forEach(b => b.addEventListener('click', () => mobileGo(b.dataset.pmv3go)));
    document.getElementById('pmv3ReviewNow')?.addEventListener('click', () => mobileGo('autopilot'));
    document.getElementById('mRunIntel')?.addEventListener('click', () => { if (typeof window.intel === 'function') window.intel(); });
    document.getElementById('mSyncAssets')?.addEventListener('click', () => { if (typeof window.syncAssets === 'function') window.syncAssets(); });

    const observer = new MutationObserver(updateMobileAttention);
    ['mPending','mShield','mOutreach','mBlog'].forEach(id => {
      const el = document.getElementById(id); if (el) observer.observe(el,{childList:true,characterData:true,subtree:true});
    });
    updateMobileAttention();
    if (typeof window.home === 'function') setTimeout(() => window.home(), 0);
  }

  function rebuildNav() {
    const nav = document.querySelector('.m-nav');
    if (!nav || nav.dataset.pmv3 === '1') return;
    nav.dataset.pmv3 = '1';
    nav.innerHTML = `
      <button class="active" data-pmv3nav="home">⌂<span>Home</span></button>
      <button data-pmv3nav="autopilot">✓<span>Review</span></button>
      <button class="pmv3-create-nav" id="pmv3CreateNav">＋<span>Create</span></button>
      <button data-pmv3nav="shield">⬡<span>Shield</span></button>
      <button data-pmv3nav="more">•••<span>More</span></button>`;
    nav.querySelectorAll('[data-pmv3nav]').forEach(b => b.addEventListener('click', () => mobileGo(b.dataset.pmv3nav)));
    document.getElementById('pmv3CreateNav')?.addEventListener('click', openCreateSheet);
  }

  function installCreateSheet() {
    if (document.getElementById('pmv3Sheet')) return;
    const wrap = document.createElement('div');
    wrap.className = 'pmv3-sheet-backdrop';
    wrap.id = 'pmv3Sheet';
    wrap.innerHTML = `<div class="pmv3-sheet" role="dialog" aria-modal="true" aria-label="Create">
      <div class="pmv3-sheet-grip"></div><h2>Create</h2>
      <button data-pmv3create="post"><i>＋</i><span><b>Social post</b><span>Generate or write a post</span></span><em>›</em></button>
      <button data-pmv3create="blog"><i>▤</i><span><b>Blog article</b><span>Draft a Pitmark story</span></span><em>›</em></button>
      <button data-pmv3create="outreach"><i>🤝</i><span><b>Outreach</b><span>Open relationship pipeline</span></span><em>›</em></button>
    </div>`;
    wrap.addEventListener('click', e => { if (e.target === wrap) closeCreateSheet(); });
    wrap.querySelectorAll('[data-pmv3create]').forEach(b => b.addEventListener('click', () => {
      const action = b.dataset.pmv3create;
      closeCreateSheet();
      if (action === 'post') { mobileGo('autopilot'); setComposer(true); }
      if (action === 'blog') mobileGo('blog');
      if (action === 'outreach') mobileGo('outreach');
    }));
    document.body.appendChild(wrap);
  }
  function openCreateSheet(){document.getElementById('pmv3Sheet')?.classList.add('open')}
  function closeCreateSheet(){document.getElementById('pmv3Sheet')?.classList.remove('open')}

  function setComposer(open) {
    const autopilot = document.querySelector('[data-mview="autopilot"]');
    const composer = autopilot?.querySelector('[data-pmv3-composer]');
    if (!composer) return;
    composer.classList.toggle('pmv3-composer-collapsed', !open);
    const toggle = document.getElementById('pmv3ComposerToggle');
    if (toggle) toggle.textContent = open ? 'Hide creator' : 'New post';
    if (open) composer.scrollIntoView({behavior:'smooth',block:'start'});
  }

  function simplifyAutopilot() {
    const view = document.querySelector('[data-mview="autopilot"]');
    if (!view || view.dataset.pmv3 === '1') return;
    view.dataset.pmv3 = '1';
    const title = view.querySelector('.m-title');
    const h1 = title?.querySelector('h1');
    if (h1) h1.textContent = 'Review';
    const refresh = document.getElementById('mQueueRefresh');
    if (refresh) refresh.textContent = 'Refresh';

    const cards = [...view.querySelectorAll(':scope > .m-card')];
    const composer = cards[0];
    const filter = cards.find(c => c.querySelector('#mQueueFilter'));
    const queue = document.getElementById('mQueue');
    if (!composer || !filter || !queue || !title) return;

    composer.dataset.pmv3Composer = '1';
    composer.classList.add('pmv3-composer-collapsed');
    const toolbar = document.createElement('div');
    toolbar.className = 'pmv3-review-toolbar';
    toolbar.innerHTML = '<button id="pmv3ComposerToggle">New post</button><button class="primary" id="pmv3RefreshReview">Refresh queue</button>';
    title.after(toolbar, filter, queue, composer);
    document.getElementById('pmv3ComposerToggle')?.addEventListener('click', () => setComposer(composer.classList.contains('pmv3-composer-collapsed')));
    document.getElementById('pmv3RefreshReview')?.addEventListener('click', () => { if (typeof window.queue === 'function') window.queue(); });
  }

  function simplifyMore() {
    const more = document.querySelector('[data-mview="more"]');
    if (!more || more.dataset.pmv3 === '1') return;
    more.dataset.pmv3 = '1';
    more.innerHTML = `
      <div class="m-title"><h1>More</h1></div>
      <div class="pmv3-section-head"><strong>Pitmark workspaces</strong><span>all tools</span></div>
      <div class="pmv3-more-list">
        <button data-pmv3go="blog"><i>▤</i><span><b>Blog</b><span>Articles and publishing</span></span><em>›</em></button>
        <button data-pmv3go="outreach"><i>🤝</i><span><b>Outreach</b><span>Tracks, racers and partners</span></span><em>›</em></button>
        <button data-pmv3go="autopilot"><i>✓</i><span><b>Autopilot</b><span>Content review and publishing</span></span><em>›</em></button>
        <button data-pmv3go="shield"><i>⬡</i><span><b>Shield</b><span>Security review</span></span><em>›</em></button>
      </div>
      <div class="pmv3-section-head"><strong>Admin</strong><span>external tools</span></div>
      <div class="pmv3-more-list">
        <a href="/control"><i>⌘</i><span><b>Desktop Control Center</b><span>Full operations dashboard</span></span><em>›</em></a>
        <a href="https://admin.shopify.com" target="_blank" rel="noopener"><i>◫</i><span><b>Shopify</b><span>Store administration</span></span><em>↗</em></a>
        <a href="https://dashboard.render.com" target="_blank" rel="noopener"><i>☁</i><span><b>Render</b><span>Cloud deployments and logs</span></span><em>↗</em></a>
      </div>`;
    more.querySelectorAll('[data-pmv3go]').forEach(b => b.addEventListener('click', () => mobileGo(b.dataset.pmv3go)));
  }

  function polishViews() {
    const shieldTitle = document.querySelector('[data-mview="shield"] .m-title h1');
    if (shieldTitle) shieldTitle.textContent = 'Shield Review';
    const outreachTitle = document.querySelector('[data-mview="outreach"] .m-title h1');
    if (outreachTitle) outreachTitle.textContent = 'Outreach';
    const blogTitle = document.querySelector('[data-mview="blog"] .m-title h1');
    if (blogTitle) blogTitle.textContent = 'Blog';
  }

  function rebuildMobileApp() {
    if (location.pathname !== '/control/mobile') return;
    document.body.classList.remove('pm-mobile-race-control','pm-mobile-command-deck');
    document.body.classList.add('pm-mobile-v3');
    installMobileV3Style();
    const brand = document.querySelector('.m-brand span');
    if (brand) brand.textContent = 'MOBILE · v0.21.35';
    rebuildHome();
    simplifyAutopilot();
    simplifyMore();
    polishViews();
    rebuildNav();
    installCreateSheet();
    updateMobileAttention();
  }

  function boot() {
    installNoMailStyle();
    repairDirectMailRoute();
    addAnalyticsNav();
    cleanMailCopy();
    applyAccessPermissions();
    rebuildMobileApp();

    // Keep the dedicated mobile shell authoritative while async data and the PWA
    // finish booting. These calls are idempotent and no longer compete with desktop bundles.
    [100,300,700,1400,3000].forEach(delay => setTimeout(() => {
      installNoMailStyle(); addAnalyticsNav(); cleanMailCopy(); rebuildMobileApp();
    }, delay));
    window.addEventListener('pageshow', () => {
      installNoMailStyle(); repairDirectMailRoute(); addAnalyticsNav(); cleanMailCopy(); rebuildMobileApp();
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();