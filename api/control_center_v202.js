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
      @media(max-width:980px){html body .m-nav{grid-template-columns:repeat(4,1fr)!important}}
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

  function installMobileRaceControlStyle() {
    if (location.pathname !== '/control/mobile' || document.getElementById('pm2132-race-control-style')) return;
    const style = document.createElement('style');
    style.id = 'pm2132-race-control-style';
    style.textContent = `
      body.pm-mobile-race-control{
        --rc-o:#ff5500;--rc-hot:#ff7633;--rc-bg:#050607;--rc-panel:#0b0e11;--rc-panel2:#101418;
        --rc-line:rgba(255,255,255,.105);--rc-muted:#78818a;
        background:linear-gradient(180deg,#08090b 0,#050607 58%,#030405 100%)!important;
      }
      body.pm-mobile-race-control:before{content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;opacity:.12;background:repeating-linear-gradient(135deg,transparent 0 21px,rgba(255,255,255,.022) 22px,transparent 23px)}
      body.pm-mobile-race-control .m-app{padding-bottom:84px!important}
      body.pm-mobile-race-control .m-head{min-height:54px!important;padding:7px 10px!important;border:0!important;border-bottom:3px solid var(--rc-o)!important;background:#07090b!important;box-shadow:0 10px 30px rgba(0,0,0,.28)!important}
      body.pm-mobile-race-control .m-brand{gap:8px!important}
      body.pm-mobile-race-control .m-brand img{width:34px!important;height:34px!important}
      body.pm-mobile-race-control .m-brand strong{font-size:13px!important;letter-spacing:.06em!important;font-style:italic!important}
      body.pm-mobile-race-control .m-brand span{margin-top:1px!important;color:#8b9298!important;font-size:7px!important;letter-spacing:.15em!important}
      body.pm-mobile-race-control .m-head .m-ghost{min-height:32px!important;padding:5px 8px!important;border-radius:3px!important;font-size:8px!important;background:#101316!important}
      body.pm-mobile-race-control .m-main{max-width:560px!important;padding:10px 10px 22px!important}
      body.pm-mobile-race-control [data-mview="home"]>.m-title{display:none!important}

      body.pm-mobile-race-control .pm-mobile-hero{position:relative!important;margin:2px 0 10px!important;padding:15px 15px 13px!important;min-height:150px!important;border:1px solid rgba(255,85,0,.32)!important;border-left:5px solid var(--rc-o)!important;border-radius:2px!important;background:linear-gradient(105deg,rgba(255,85,0,.13),transparent 38%),linear-gradient(180deg,#11161a,#080b0e)!important;box-shadow:0 16px 40px rgba(0,0,0,.32)!important}
      body.pm-mobile-race-control .pm-mobile-hero:before{content:""!important;position:absolute!important;right:0!important;top:0!important;width:92px!important;height:46px!important;opacity:.12!important;background:conic-gradient(#fff 25%,transparent 0 50%,#fff 0 75%,transparent 0)!important;background-size:14px 14px!important;transform:none!important}
      body.pm-mobile-race-control .pm-mobile-hero:after{content:"87"!important;right:8px!important;bottom:-18px!important;font-size:110px!important;line-height:1!important;font-style:italic!important;color:rgba(255,255,255,.025)!important}
      body.pm-mobile-race-control .pm-mobile-kicker{color:var(--rc-hot)!important;font-size:8px!important;letter-spacing:.19em!important}
      body.pm-mobile-race-control .pm-mobile-live{top:15px!important;right:15px!important;width:8px!important;height:8px!important}
      body.pm-mobile-race-control .pm-mobile-hero h2{max-width:80%!important;margin:7px 0 6px!important;font-size:28px!important;line-height:.96!important;letter-spacing:-.045em!important;text-transform:uppercase!important;font-style:italic!important}
      body.pm-mobile-race-control .pm-mobile-hero p{max-width:82%!important;margin:0!important;font-size:10px!important;line-height:1.45!important;color:#919aa2!important}
      .pm-rc-status{position:relative;z-index:2;display:flex;gap:6px;flex-wrap:wrap;margin-top:12px;padding-top:10px;border-top:1px solid rgba(255,255,255,.08)}
      .pm-rc-status span{display:inline-flex;align-items:center;gap:5px;padding:5px 7px;border:1px solid rgba(255,255,255,.09);background:#090c0e;color:#9199a1;font-size:7px;font-weight:900;letter-spacing:.07em;text-transform:uppercase}
      .pm-rc-status i{width:5px;height:5px;border-radius:50%;background:#4fe082;box-shadow:0 0 8px rgba(79,224,130,.8)}

      body.pm-mobile-race-control .pm-mobile-section-label{margin:13px 0 6px!important;padding-bottom:5px!important;border-bottom:1px solid rgba(255,255,255,.07)!important}
      body.pm-mobile-race-control .pm-mobile-section-label strong{font-size:9px!important;letter-spacing:.16em!important;color:#c5c9cd!important}
      body.pm-mobile-race-control .pm-mobile-section-label span{font-size:7px!important;color:#606970!important}

      body.pm-mobile-race-control .m-stats{display:grid!important;grid-template-columns:1fr 1fr!important;gap:6px!important;margin-bottom:9px!important}
      body.pm-mobile-race-control .m-stats button{position:relative!important;min-height:78px!important;padding:10px 11px!important;border:1px solid var(--rc-line)!important;border-left:3px solid #353b40!important;border-radius:0!important;background:#0b0f12!important;box-shadow:none!important}
      body.pm-mobile-race-control .m-stats button.pm-needs-attention{border-left-color:var(--rc-o)!important;background:linear-gradient(90deg,rgba(255,85,0,.08),#0b0f12 46%)!important}
      body.pm-mobile-race-control .m-stats span{font-size:8px!important;letter-spacing:.12em!important;color:#6f7880!important}
      body.pm-mobile-race-control .m-stats b{margin-top:9px!important;font-size:27px!important;line-height:1!important;font-style:italic!important}

      body.pm-mobile-race-control .pm-mobile-quick{display:grid!important;grid-template-columns:1fr 1fr!important;gap:6px!important;margin-bottom:10px!important}
      body.pm-mobile-race-control .pm-mobile-quick button{min-height:64px!important;padding:10px!important;border:1px solid var(--rc-line)!important;border-radius:0!important;background:#0d1114!important;box-shadow:none!important}
      body.pm-mobile-race-control .pm-mobile-quick button.pm-rc-primary{grid-column:1/-1!important;min-height:58px!important;background:linear-gradient(90deg,#ff5f0b,#dd4200)!important;border-color:#ff6b1b!important}
      body.pm-mobile-race-control .pm-mobile-quick .pm-q-icon{float:left!important;width:28px!important;height:28px!important;margin:0 10px 0 0!important;border-radius:2px!important;background:rgba(255,255,255,.07)!important}
      body.pm-mobile-race-control .pm-mobile-quick strong{display:block!important;padding-top:1px!important;font-size:10px!important;text-transform:uppercase!important;letter-spacing:.035em!important}
      body.pm-mobile-race-control .pm-mobile-quick small{font-size:8px!important;line-height:1.3!important}

      body.pm-mobile-race-control .m-card,body.pm-mobile-race-control .m-row,body.pm-mobile-race-control .m-item{border:1px solid var(--rc-line)!important;border-radius:0!important;background:linear-gradient(145deg,#0d1114,#090c0e)!important;box-shadow:none!important}
      body.pm-mobile-race-control .m-card{padding:12px!important;margin-bottom:7px!important}
      body.pm-mobile-race-control .m-card h2{font-size:12px!important;text-transform:uppercase!important;font-style:italic!important;letter-spacing:.04em!important}
      body.pm-mobile-race-control .m-card p{font-size:10px!important;line-height:1.45!important}
      body.pm-mobile-race-control .m-row{padding:12px!important;margin-bottom:6px!important}
      body.pm-mobile-race-control .m-row b{font-size:10px!important;text-transform:uppercase!important}
      body.pm-mobile-race-control .m-row span{font-size:9px!important}
      body.pm-mobile-race-control input,body.pm-mobile-race-control select,body.pm-mobile-race-control textarea{border-radius:2px!important;background:#06080a!important;border-color:rgba(255,255,255,.13)!important}
      body.pm-mobile-race-control .m-orange,body.pm-mobile-race-control .m-ghost{min-height:42px!important;border-radius:2px!important;font-size:9px!important}
      body.pm-mobile-race-control .m-orange{background:linear-gradient(180deg,#ff6511,#df4500)!important}
      body.pm-mobile-race-control .pm-mobile-workspace-grid{gap:6px!important}
      body.pm-mobile-race-control .pm-mobile-workspace-grid button{min-height:76px!important;padding:11px!important;border-radius:0!important;background:#0c1013!important}

      body.pm-mobile-race-control .m-nav{left:0!important;right:0!important;bottom:0!important;width:100%!important;transform:none!important;padding:5px max(5px,env(safe-area-inset-right)) calc(5px + env(safe-area-inset-bottom))!important;border:0!important;border-top:2px solid var(--rc-o)!important;border-radius:0!important;background:rgba(6,8,10,.98)!important;box-shadow:0 -12px 28px rgba(0,0,0,.42)!important}
      body.pm-mobile-race-control .m-nav button{position:relative!important;min-height:48px!important;border-radius:0!important;color:#68717a!important;font-size:15px!important}
      body.pm-mobile-race-control .m-nav button span{font-size:7px!important;font-weight:900!important;text-transform:uppercase!important;letter-spacing:.07em!important}
      body.pm-mobile-race-control .m-nav button.active{color:#fff!important;background:linear-gradient(180deg,rgba(255,85,0,.12),transparent)!important}
      body.pm-mobile-race-control .m-nav button.active:before{content:"";position:absolute;top:-5px;left:22%;right:22%;height:3px;background:var(--rc-o)}
      body.pm-mobile-race-control .m-nav button.active span{color:#ff7736!important}
      @media(max-width:390px){body.pm-mobile-race-control .pm-mobile-hero h2{font-size:25px!important}}
    `;
    document.head.appendChild(style);
  }

  function remodelMobileHome() {
    if (location.pathname !== '/control/mobile') return;
    document.body.classList.add('pm-mobile-race-control');
    installMobileRaceControlStyle();

    const brand = document.querySelector('.m-brand span');
    if (brand) brand.textContent = 'RACE CONTROL · v0.21.32';

    const home = document.querySelector('[data-mview="home"]');
    const hero = home?.querySelector('.pm-mobile-hero');
    if (hero) {
      const kicker = hero.querySelector('.pm-mobile-kicker');
      const heading = hero.querySelector('h2');
      const copy = hero.querySelector('p');
      if (kicker) kicker.textContent = 'PITMARK // MOBILE RACE CONTROL';
      if (heading) heading.textContent = 'Run the whole operation.';
      if (copy) copy.textContent = 'What needs your decision right now — content, Shield, outreach and PRT — in one pit-wall view.';
      hero.querySelector('.pm-deck-status')?.remove();
      if (!hero.querySelector('.pm-rc-status')) {
        const status = document.createElement('div');
        status.className = 'pm-rc-status';
        status.innerHTML = '<span><i></i>Cloud live</span><span>Autopilot armed</span><span>PRT early access</span>';
        hero.appendChild(status);
      }
    }

    // v2 used an icon span before the word Mail, so the old /^Mail/ check never
    // matched. Remove it by semantic text instead and promote Review to primary.
    document.querySelectorAll('.pm-mobile-quick button').forEach(button => {
      const text = (button.textContent || '').replace(/\s+/g,' ').trim();
      if (/Mail/i.test(text) && /Inbox|replies/i.test(text)) { button.remove(); return; }
      button.classList.toggle('pm-rc-primary', /Review/i.test(text));
    });

    const quick = home?.querySelector('.pm-mobile-quick');
    const stats = home?.querySelector('.m-stats');
    if (hero && stats && quick && !home.dataset.rcOrder) {
      home.dataset.rcOrder = '1';
      const labels = [...home.querySelectorAll('.pm-mobile-section-label')];
      const attentionLabel = labels.find(x => /Needs your attention/i.test(x.textContent || ''));
      const quickLabel = labels.find(x => /Quick actions/i.test(x.textContent || ''));
      hero.after(attentionLabel || stats, stats);
      stats.after(quickLabel || quick, quick);
    }

    const moreTitle = document.querySelector('[data-mview="more"] .m-title h1');
    if (moreTitle) moreTitle.textContent = 'Pitmark Workspaces';
  }

  function boot() {
    installNoMailStyle();
    repairDirectMailRoute();
    addAnalyticsNav();
    cleanMailCopy();
    applyAccessPermissions();
    remodelMobileHome();

    // Older enhancement bundles build pieces asynchronously. Re-apply the small,
    // idempotent mobile transformation after they finish.
    [80,180,320,520,900,1500,3000].forEach(delay => setTimeout(() => {
      installNoMailStyle(); addAnalyticsNav(); cleanMailCopy(); remodelMobileHome();
    }, delay));
    window.addEventListener('pageshow', () => {
      installNoMailStyle(); repairDirectMailRoute(); addAnalyticsNav(); cleanMailCopy(); remodelMobileHome();
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();