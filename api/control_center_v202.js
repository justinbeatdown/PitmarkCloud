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

  function boot() {
    installNoMailStyle();
    repairDirectMailRoute();
    addAnalyticsNav();
    cleanMailCopy();
    applyAccessPermissions();

    // Legacy bundles finish asynchronously. Re-apply only harmless,
    // idempotent presentation work — no MutationObserver and no DOM churn loop.
    [80, 160, 450, 1200, 3000].forEach(delay => {
      setTimeout(() => {
        installNoMailStyle();
        addAnalyticsNav();
        cleanMailCopy();
      }, delay);
    });

    window.addEventListener('pageshow', () => {
      installNoMailStyle();
      repairDirectMailRoute();
      addAnalyticsNav();
      cleanMailCopy();
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
