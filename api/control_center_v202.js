(() => {
  'use strict';

  // v0.21.6 — Control Center is not an email client.
  // Gmail remains server-side for Shield and automation. The two legacy
  // mail-client bootstrap reads are short-circuited so opening Control Center
  // does not initialize identities/preferences for a UI that is no longer used.
  const nativeFetch = window.fetch.bind(window);
  window.fetch = function pitmarkControlFetch(input, init) {
    try {
      const raw = typeof input === 'string' ? input : input?.url || '';
      const url = new URL(raw, location.origin);
      if (url.origin === location.origin) {
        if (url.pathname === '/api/control/email/identities') {
          return Promise.resolve(new Response(JSON.stringify([]), {
            status: 200,
            headers: {'Content-Type':'application/json'}
          }));
        }
        if (url.pathname === '/api/control/email/preferences') {
          return Promise.resolve(new Response(JSON.stringify({}), {
            status: 200,
            headers: {'Content-Type':'application/json'}
          }));
        }
      }
    } catch (_) {}
    return nativeFetch(input, init);
  };

  const MAIL_HIDE_SELECTORS = [
    '[data-view="email"]',
    '[data-view-section="email"]',
    '[data-mview="email"]',
    '[data-mnav="email"]',
    '[data-mgo="email"]',
    '[data-pm19-go="email"]',
    '[data-go="email"]',
    '#pm19ComposeOverlay',
    '#pm204BulkBar'
  ];

  function installNoMailStyle() {
    if (document.getElementById('pm216-no-mail-style')) return;
    const style = document.createElement('style');
    style.id = 'pm216-no-mail-style';
    style.textContent = `
      html body .shell>.sidebar>.nav>button[data-view="email"],
      html body .shell>.sidebar>.nav>button[data-view="email"]:not([hidden]),
      html body .content>[data-view-section="email"],
      html body [data-pm19-go="email"],
      html body [data-go="email"],
      html body #pm19ComposeOverlay,
      html body #pm204BulkBar,
      html body [data-mview="email"],
      html body .m-nav>button[data-mnav="email"],
      html body [data-mgo="email"] {
        display:none !important;
        visibility:hidden !important;
        pointer-events:none !important;
      }
      @media (max-width:980px) {
        html body .m-nav { grid-template-columns:repeat(4,1fr) !important; }
      }
    `;
    document.head.appendChild(style);
  }

  function activate(view) {
    if (view === 'email') view = 'dashboard';
    if (typeof window.setView === 'function') {
      window.setView(view);
      return;
    }
    document.querySelectorAll('[data-view-section]').forEach(section => {
      section.classList.toggle('active', section.dataset.viewSection === view);
    });
    document.querySelectorAll('#nav [data-view]').forEach(button => {
      button.classList.toggle('active', button.dataset.view === view);
    });
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

    const directory = nav.querySelector('[data-view="directory"]');
    nav.insertBefore(button, directory || null);
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

  // v0.21.31 — the dedicated mobile surface should look and behave like a
  // pocket command app, not a compressed desktop dashboard.
  function installMobileCommandDeck() {
    if (location.pathname !== '/control/mobile') return;
    document.body.classList.add('pm-mobile-command-deck');

    if (!document.getElementById('pm2131-mobile-command-deck-style')) {
      const style = document.createElement('style');
      style.id = 'pm2131-mobile-command-deck-style';
      style.textContent = `
        body.pm-mobile-command-deck{
          --deck-orange:#ff5500;
          --deck-orange-hot:#ff7430;
          --deck-bg:#050607;
          --deck-panel:#0d1013;
          --deck-panel-2:#12161a;
          --deck-line:rgba(255,255,255,.085);
          --deck-muted:#7f8992;
          background:
            radial-gradient(circle at 82% -6%,rgba(255,85,0,.17),transparent 29%),
            linear-gradient(180deg,#07090a,#040506 72%);
        }
        body.pm-mobile-command-deck:before{
          content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;opacity:.16;
          background-image:linear-gradient(120deg,transparent 0 48%,rgba(255,255,255,.025) 49%,transparent 50%);
          background-size:28px 28px;
        }
        body.pm-mobile-command-deck .m-app{padding-bottom:102px}
        body.pm-mobile-command-deck .m-head{
          min-height:56px;padding:8px 11px;border-bottom:1px solid var(--deck-line);
          background:rgba(5,6,7,.94);backdrop-filter:blur(22px) saturate(1.25);
        }
        body.pm-mobile-command-deck .m-brand{gap:9px}
        body.pm-mobile-command-deck .m-brand img{width:36px;height:36px;filter:drop-shadow(0 5px 12px rgba(0,0,0,.5))}
        body.pm-mobile-command-deck .m-brand strong{font-size:14px;letter-spacing:.045em;font-style:italic}
        body.pm-mobile-command-deck .m-brand span{margin-top:2px;color:#8b929a;font-size:7px;letter-spacing:.15em}
        body.pm-mobile-command-deck .m-head .m-ghost{min-height:34px;padding:6px 9px;font-size:8px;border-radius:8px}
        body.pm-mobile-command-deck .m-main{max-width:560px;padding:11px 10px 24px}
        body.pm-mobile-command-deck [data-mview="home"]>.m-title{display:none}
        body.pm-mobile-command-deck .pm-mobile-hero{
          margin:2px 0 10px;padding:22px 17px 16px;border:1px solid rgba(255,85,0,.24);
          border-left:4px solid var(--deck-orange);border-radius:13px;
          background:linear-gradient(128deg,rgba(255,85,0,.17),rgba(255,85,0,.025) 46%,transparent 47%),linear-gradient(180deg,#15191d,#0a0d10);
          box-shadow:0 20px 48px rgba(0,0,0,.34);
        }
        body.pm-mobile-command-deck .pm-mobile-hero:before{
          content:"";position:absolute;right:13px;top:13px;width:68px;height:28px;opacity:.12;
          background:conic-gradient(#fff 25%,transparent 0 50%,#fff 0 75%,transparent 0);background-size:12px 12px;
          transform:skewX(-10deg);pointer-events:none;
        }
        body.pm-mobile-command-deck .pm-mobile-hero:after{right:-18px;bottom:-45px;font-size:165px;color:rgba(255,255,255,.018)}
        body.pm-mobile-command-deck .pm-mobile-kicker{font-size:8px;letter-spacing:.18em;color:#ff7b3b}
        body.pm-mobile-command-deck .pm-mobile-live{top:17px;right:17px;width:8px;height:8px}
        body.pm-mobile-command-deck .pm-mobile-hero h2{max-width:92%;margin:8px 0 7px;font-size:29px;line-height:.98;letter-spacing:-.047em;text-transform:uppercase;font-style:italic}
        body.pm-mobile-command-deck .pm-mobile-hero p{max-width:92%;font-size:11px;line-height:1.5;color:#9aa2aa}
        .pm-deck-status{position:relative;z-index:2;display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:16px;padding-top:12px;border-top:1px solid rgba(255,255,255,.08)}
        .pm-deck-status span{display:flex;align-items:center;justify-content:center;gap:5px;min-height:29px;border:1px solid rgba(255,255,255,.075);border-radius:7px;background:rgba(0,0,0,.17);color:#929aa2;font-size:7px;font-weight:900;letter-spacing:.07em;text-transform:uppercase}
        .pm-deck-status i{width:6px;height:6px;border-radius:50%;background:#48dd83;box-shadow:0 0 9px rgba(72,221,131,.65)}
        body.pm-mobile-command-deck .pm-mobile-section-label{margin:15px 2px 7px}
        body.pm-mobile-command-deck .pm-mobile-section-label strong{font-size:9px;color:#c2c7cc;letter-spacing:.13em}
        body.pm-mobile-command-deck .pm-mobile-section-label span{font-size:7px;color:#626b73}
        body.pm-mobile-command-deck .pm-mobile-quick{grid-template-columns:1fr 1fr;gap:7px;margin-bottom:10px}
        body.pm-mobile-command-deck .pm-mobile-quick button{min-height:86px;padding:12px;border-radius:11px;border-color:var(--deck-line);background:linear-gradient(145deg,#12161a,#0a0d10)}
        body.pm-mobile-command-deck .pm-mobile-quick button:first-child{grid-column:1/-1;min-height:74px;background:linear-gradient(135deg,#ff6414,#d94400);border-color:#ff7024}
        body.pm-mobile-command-deck .pm-mobile-quick .pm-q-icon{width:29px;height:29px;margin-bottom:8px;border-radius:7px;font-size:13px}
        body.pm-mobile-command-deck .pm-mobile-quick strong{font-size:11px;text-transform:uppercase;letter-spacing:.025em}
        body.pm-mobile-command-deck .pm-mobile-quick small{font-size:8px;line-height:1.3}
        body.pm-mobile-command-deck .m-stats{grid-template-columns:1fr 1fr;gap:7px;margin-bottom:10px}
        body.pm-mobile-command-deck .m-stats button{position:relative;overflow:hidden;min-height:88px;padding:12px;border-radius:11px;background:linear-gradient(145deg,#12161a,#090c0f);border-color:var(--deck-line)}
        body.pm-mobile-command-deck .m-stats button:after{content:"";position:absolute;left:0;right:0;top:0;height:2px;background:linear-gradient(90deg,var(--deck-orange),transparent 72%);opacity:.7}
        body.pm-mobile-command-deck .m-stats span{font-size:8px;letter-spacing:.11em}
        body.pm-mobile-command-deck .m-stats b{margin-top:13px;font-size:30px;font-style:italic}
        body.pm-mobile-command-deck .m-card,body.pm-mobile-command-deck .m-row,body.pm-mobile-command-deck .m-item{border-radius:11px;border-color:var(--deck-line);background:linear-gradient(145deg,#101418,#090c0f)}
        body.pm-mobile-command-deck .m-card{padding:13px;margin-bottom:8px}
        body.pm-mobile-command-deck .m-card h2{font-size:13px;text-transform:uppercase;font-style:italic;letter-spacing:.025em}
        body.pm-mobile-command-deck .m-card p{font-size:10.5px;line-height:1.45}
        body.pm-mobile-command-deck .m-card-head>span{font-size:8px;color:#78818a;text-transform:uppercase}
        body.pm-mobile-command-deck .m-row{padding:13px;margin-bottom:7px}
        body.pm-mobile-command-deck .m-row b{font-size:11px;text-transform:uppercase}
        body.pm-mobile-command-deck .m-row span{font-size:9px;line-height:1.35}
        body.pm-mobile-command-deck input,body.pm-mobile-command-deck select,body.pm-mobile-command-deck textarea{border-radius:9px;background:#07090b;border-color:rgba(255,255,255,.12)}
        body.pm-mobile-command-deck .m-orange,body.pm-mobile-command-deck .m-ghost{min-height:43px;border-radius:9px;font-size:9px}
        body.pm-mobile-command-deck .m-orange{background:linear-gradient(180deg,#ff6818,#e44800)}
        body.pm-mobile-command-deck .pm-mobile-workspace-grid{gap:7px}
        body.pm-mobile-command-deck .pm-mobile-workspace-grid button{min-height:86px;padding:13px;border-radius:11px;background:linear-gradient(145deg,#11151a,#090c0f)}
        body.pm-mobile-command-deck .pm-mobile-workspace-grid strong{font-size:11px;text-transform:uppercase}
        body.pm-mobile-command-deck .m-nav{left:8px;right:8px;bottom:8px;padding:6px 7px calc(6px + env(safe-area-inset-bottom));border-radius:14px;background:rgba(9,11,13,.96);border:1px solid rgba(255,255,255,.11);box-shadow:0 15px 45px rgba(0,0,0,.55)}
        body.pm-mobile-command-deck .m-nav button{position:relative;min-height:49px;border-radius:9px;font-size:16px}
        body.pm-mobile-command-deck .m-nav button span{font-size:7px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}
        body.pm-mobile-command-deck .m-nav button.active{color:#fff;background:rgba(255,85,0,.12)}
        body.pm-mobile-command-deck .m-nav button.active:before{content:"";position:absolute;left:28%;right:28%;top:2px;height:2px;border-radius:2px;background:var(--deck-orange)}
        body.pm-mobile-command-deck .m-nav button.active span{color:#ff7a39}
        body.pm-mobile-command-deck .pm-mobile-tools-drawer{border-radius:11px;background:#090c0f}
        @media(max-width:390px){
          body.pm-mobile-command-deck .pm-mobile-hero h2{font-size:26px}
          body.pm-mobile-command-deck .pm-mobile-quick{grid-template-columns:1fr 1fr}
          body.pm-mobile-command-deck .pm-mobile-quick button:first-child{grid-column:1/-1}
        }
      `;
      document.head.appendChild(style);
    }

    const brand = document.querySelector('.m-brand span');
    if (brand) brand.textContent = 'MOBILE OPERATIONS · v0.21.31';

    const hero = document.querySelector('[data-mview="home"] .pm-mobile-hero');
    if (hero) {
      const kicker = hero.querySelector('.pm-mobile-kicker');
      const heading = hero.querySelector('h2');
      const copy = hero.querySelector('p');
      if (kicker) kicker.textContent = 'PITMARK MOBILE OPERATIONS';
      if (heading) heading.textContent = 'Command Pitmark from your pocket.';
      if (copy) copy.textContent = 'Approvals, publishing, Shield, outreach and PRT activity — without dragging the desktop dashboard onto your phone.';
      if (!hero.querySelector('.pm-deck-status')) {
        const status = document.createElement('div');
        status.className = 'pm-deck-status';
        status.innerHTML = '<span><i></i>Cloud live</span><span>Autopilot</span><span>PRT early access</span>';
        hero.appendChild(status);
      }
    }

    // The previous mobile-v2 quick deck still offered Mail even though Mail was
    // removed from Control Center. Remove that stale tile and make Review the
    // primary mobile action.
    document.querySelectorAll('.pm-mobile-quick button').forEach(button => {
      if (/^Mail\b/i.test((button.textContent || '').trim())) button.remove();
    });

    const moreTitle = document.querySelector('[data-mview="more"] .m-title h1');
    if (moreTitle) moreTitle.textContent = 'Pitmark Workspaces';
  }

  function boot() {
    installNoMailStyle();
    repairDirectMailRoute();
    addAnalyticsNav();
    cleanMailCopy();
    applyAccessPermissions();
    installMobileCommandDeck();

    // Legacy bundles finish asynchronously. Re-apply only harmless,
    // idempotent presentation work — no MutationObserver and no DOM churn loop.
    [80, 160, 450, 1200, 3000].forEach(delay => {
      setTimeout(() => {
        installNoMailStyle();
        addAnalyticsNav();
        cleanMailCopy();
        installMobileCommandDeck();
      }, delay);
    });

    window.addEventListener('pageshow', () => {
      installNoMailStyle();
      repairDirectMailRoute();
      addAnalyticsNav();
      cleanMailCopy();
      installMobileCommandDeck();
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
