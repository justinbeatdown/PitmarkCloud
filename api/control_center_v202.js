(() => {
  'use strict';

  // v0.21.5 — safe Control Center mail removal.
  // Mail UI remains dormant in the DOM so legacy bundles can initialize safely.
  // Google Workspace / Gmail remains available server-side for Shield and automation.

  const MAIL_HIDE_SELECTORS = [
    '[data-view="email"]',
    '[data-view-section="email"]',
    '[data-mview="email"]',
    '[data-mnav="email"]',
    '[data-mgo="email"]',
    '[data-pm19-go="email"]',
    '#pm19ComposeOverlay',
    '#pm204BulkBar'
  ];

  function installNoMailStyle() {
    if (document.getElementById('pm215-no-mail-style')) return;
    const style = document.createElement('style');
    style.id = 'pm215-no-mail-style';
    style.textContent = `
      ${MAIL_HIDE_SELECTORS.join(',\n      ')} { display:none !important; }
      @media (max-width:980px) {
        .m-nav { grid-template-columns:repeat(4,1fr) !important; }
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
    button.innerHTML = '<span class="ico">⌁</span><span>PRT Analytics<small>Installs & Usage</small></span>';
    button.addEventListener('click', () => activate('analytics'));

    const directory = nav.querySelector('[data-view="directory"]');
    nav.insertBefore(button, directory || null);
  }

  async function applyAccessPermissions() {
    try {
      const response = await fetch('/api/control/access/me', {credentials:'same-origin'});
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

    // Legacy bundles finish their own boot asynchronously. Re-apply only harmless,
    // idempotent presentation work; never observe or delete live DOM nodes.
    [120, 450, 1200, 3000].forEach(delay => {
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
