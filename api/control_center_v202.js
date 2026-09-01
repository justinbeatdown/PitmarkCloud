(() => {
  'use strict';

  const ITEMS = [
    ['dashboard', '◉', 'Dashboard', 'Overview & Status'],
    ['autopilot', '➤', 'Autopilot', 'Posts & Queue'],
    ['email', '✉', 'Mail', 'Inbox & Compose'],
    ['shield', '⬡', 'Shield', 'Ecosystem Security'],
    ['campaigns', '🏁', 'Campaigns', 'Rookie Year'],
    ['outreach', '🤝', 'Outreach', 'Tracks & Partners'],
    ['blog', '▤', 'Blog', 'Track Spotlight'],
    ['analytics', '⌁', 'PRT Analytics', 'Installs & Usage'],
    ['directory', '⌘', 'Directory', 'Pitmark Links'],
    ['settings', '⚙', 'Settings', 'Accounts & Security'],
  ];

  let access = null;

  function permitted(view) {
    if (!access) return true;
    if (access.role === 'owner' || access.role === 'admin') return true;
    const permission = view === 'email' ? 'mail' : view;
    return (access.permissions || []).includes(permission);
  }

  function buttonMarkup(icon, label, help) {
    return `<span class="ico">${icon}</span><span>${label}<small>${help}</small></span>`;
  }

  function activate(view) {
    if (typeof window.setView === 'function') window.setView(view);
    else {
      document.querySelectorAll('[data-view-section]').forEach(section => {
        section.classList.toggle('active', section.dataset.viewSection === view);
      });
      document.querySelectorAll('#nav [data-view]').forEach(button => {
        button.classList.toggle('active', button.dataset.view === view);
      });
      location.hash = `#${view}`;
    }
    if (view === 'email') {
      setTimeout(() => document.querySelector('[data-pm19-folder="inbox"]')?.click(), 20);
    }
  }

  function ensureSidebar() {
    if (innerWidth <= 980) return;
    const shell = document.querySelector('.shell');
    const main = shell?.querySelector(':scope > .main');
    if (!shell || !main) return;

    let sidebar = shell.querySelector(':scope > .sidebar');
    if (!sidebar) {
      sidebar = document.createElement('aside');
      sidebar.className = 'sidebar';
      shell.insertBefore(sidebar, main);
    }
    sidebar.classList.add('pm19-sidebar', 'pm202-sidebar');

    let brand = sidebar.querySelector(':scope > .brand');
    if (!brand) {
      brand = document.createElement('a');
      brand.className = 'brand brand-art brand-home';
      brand.href = '#dashboard';
      brand.id = 'brandDashboardLink';
      brand.dataset.nav = 'dashboard';
      brand.setAttribute('aria-label', 'Go to Pitmark dashboard');
      brand.innerHTML = '<img src="/control-logo-wide.png" alt="Pitmark Racing Co.">';
      sidebar.prepend(brand);
    }

    let nav = sidebar.querySelector(':scope > .nav');
    if (!nav) {
      nav = document.createElement('nav');
      nav.className = 'nav';
      nav.id = 'nav';
      brand.after(nav);
    }
    if (!nav.id) nav.id = 'nav';

    if (!nav.querySelector('.pm19-nav-label')) {
      const heading = document.createElement('div');
      heading.className = 'pm19-nav-label';
      heading.textContent = 'WORKSPACES';
      nav.prepend(heading);
    }

    ITEMS.forEach(([view, icon, label, help]) => {
      let button = nav.querySelector(`[data-view="${view}"]`);
      if (!button) {
        button = document.createElement('button');
        button.dataset.view = view;
        button.innerHTML = buttonMarkup(icon, label, help);
      }

      button.hidden = !permitted(view);
      if (!button.dataset.pm202Bound) {
        button.dataset.pm202Bound = '1';
        button.addEventListener('click', () => activate(view));
      }

      // ITEMS is the authoritative desktop sidebar order. appendChild also
      // moves an existing node, repairing buttons injected by older bundles.
      // Settings is intentionally the final workspace item.
      nav.appendChild(button);
    });

    let footer = sidebar.querySelector(':scope > .side-bottom');
    if (!footer) {
      footer = document.createElement('div');
      footer.className = 'side-bottom';
      footer.innerHTML = '<img class="badge-logo" src="/control-logo-badge.png" alt="Pitmark Racing Co. badge"><div class="motto">LEAVE YOUR MARK</div><div>PITMARK RACING CO.</div><div>BUILT BY RACERS, FOR RACERS.</div>';
      sidebar.appendChild(footer);
    }

    if (!brand.dataset.pm202Bound) {
      brand.dataset.pm202Bound = '1';
      brand.addEventListener('click', event => {
        event.preventDefault();
        activate('dashboard');
      });
    }
  }

  async function loadAccess() {
    try {
      const response = await fetch('/api/control/access/me', {credentials:'same-origin'});
      if (response.ok) access = await response.json();
    } catch (error) {
      console.warn('Sidebar access profile unavailable; preserving existing navigation.', error);
    }
    ensureSidebar();
  }

  function boot() {
    ensureSidebar();
    loadAccess();
    [80, 260, 700, 1600, 3200].forEach(delay => setTimeout(ensureSidebar, delay));
    window.addEventListener('pageshow', ensureSidebar);
    window.addEventListener('resize', ensureSidebar);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
