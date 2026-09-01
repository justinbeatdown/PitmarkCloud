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
  const bulkMailSelection = new Set();
  let bulkMailObserver = null;

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


  function installBulkMailStyles() {
    if (document.getElementById('pm204-bulk-mail-style')) return;
    const style = document.createElement('style');
    style.id = 'pm204-bulk-mail-style';
    style.textContent = `
      .pm204-bulkbar{display:flex;align-items:center;gap:8px;padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.07);background:#0c1015;min-height:38px}
      .pm204-bulkbar[hidden]{display:none!important}
      .pm204-bulkbar button{border:1px solid rgba(255,255,255,.12);background:#151a21;color:#eef2f7;border-radius:8px;padding:7px 10px;font:inherit;font-size:12px;cursor:pointer}
      .pm204-bulkbar button:hover{border-color:rgba(255,85,0,.55)}
      .pm204-bulkbar .pm204-delete{background:#35140d;border-color:#7a2a18;color:#ffb39c}
      .pm204-bulkbar .pm204-delete:disabled{opacity:.45;cursor:default}
      .pm204-bulk-count{margin-left:auto;color:#9ca8b7;font-size:11px}
      .pm19-mail-row{position:relative}
      .pm204-selectbox{position:absolute;left:8px;top:50%;transform:translateY(-50%);width:17px;height:17px;border:1px solid #566171;border-radius:5px;background:#0d1117;display:grid;place-items:center;z-index:4;cursor:pointer;box-sizing:border-box}
      .pm204-selectbox::after{content:'✓';font-size:12px;font-weight:900;color:white;opacity:0}
      .pm19-mail-row.pm204-checked .pm204-selectbox{background:#ff5500;border-color:#ff5500}
      .pm19-mail-row.pm204-checked .pm204-selectbox::after{opacity:1}
      .pm19-mail-row[data-pm19-thread]{padding-left:36px!important}
      .pm19-mail-row.pm204-checked{box-shadow:inset 3px 0 #ff5500;background:rgba(255,85,0,.08)}
      @media(max-width:980px){
        .pm204-bulkbar{position:sticky;top:0;z-index:6}
        .pm204-bulkbar button{min-height:36px}
        .pm204-selectbox{left:10px}
        .pm19-mail-row[data-pm19-thread]{padding-left:40px!important}
      }`;
    document.head.appendChild(style);
  }

  function bulkMailRows() {
    return [...document.querySelectorAll('#pm19MailList [data-pm19-thread]')];
  }

  function updateBulkMailUI() {
    const bar = document.getElementById('pm204BulkBar');
    if (!bar) return;
    const rows = bulkMailRows();
    const visibleIds = rows.map(row => Number(row.dataset.pm19Thread)).filter(Number.isFinite);
    for (const id of [...bulkMailSelection]) {
      if (!visibleIds.includes(id)) bulkMailSelection.delete(id);
    }
    rows.forEach(row => {
      const id = Number(row.dataset.pm19Thread);
      row.classList.toggle('pm204-checked', bulkMailSelection.has(id));
    });
    const count = bulkMailSelection.size;
    const label = bar.querySelector('.pm204-bulk-count');
    const del = bar.querySelector('.pm204-delete');
    const all = bar.querySelector('.pm204-select-all');
    if (label) label.textContent = count ? `${count} selected` : 'Select messages';
    if (del) {
      del.disabled = count === 0;
      del.textContent = count ? `Delete (${count})` : 'Delete';
    }
    if (all) {
      const allSelected = visibleIds.length > 0 && visibleIds.every(id => bulkMailSelection.has(id));
      all.textContent = allSelected ? 'Clear all' : 'Select all';
    }
  }

  async function bulkDeleteMail() {
    const ids = [...bulkMailSelection];
    if (!ids.length) return;
    if (!confirm(`Delete ${ids.length} selected conversation${ids.length === 1 ? '' : 's'}?`)) return;
    const button = document.querySelector('#pm204BulkBar .pm204-delete');
    if (button) {
      button.disabled = true;
      button.textContent = 'Deleting…';
    }
    try {
      const response = await fetch('/api/control/email/threads/bulk-delete', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({thread_ids: ids}),
      });
      const text = await response.text();
      let data = {};
      try { data = JSON.parse(text); } catch {}
      if (!response.ok) throw new Error(data.detail || text || `HTTP ${response.status}`);
      bulkMailSelection.clear();
      document.getElementById('pm19MailRefresh')?.click();
    } catch (error) {
      alert(`Bulk delete failed: ${error.message}`);
      updateBulkMailUI();
    }
  }

  function installBulkMailControls() {
    installBulkMailStyles();
    const list = document.getElementById('pm19MailList');
    const search = document.querySelector('.pm19-mail-searchbar');
    if (!list || !search) return;

    let bar = document.getElementById('pm204BulkBar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'pm204BulkBar';
      bar.className = 'pm204-bulkbar';
      bar.innerHTML = `
        <button type="button" class="pm204-select-all">Select all</button>
        <button type="button" class="pm204-delete" disabled>Delete</button>
        <span class="pm204-bulk-count">Select messages</span>`;
      search.after(bar);
      bar.querySelector('.pm204-select-all')?.addEventListener('click', () => {
        const ids = bulkMailRows().map(row => Number(row.dataset.pm19Thread)).filter(Number.isFinite);
        const allSelected = ids.length > 0 && ids.every(id => bulkMailSelection.has(id));
        if (allSelected) ids.forEach(id => bulkMailSelection.delete(id));
        else ids.forEach(id => bulkMailSelection.add(id));
        updateBulkMailUI();
      });
      bar.querySelector('.pm204-delete')?.addEventListener('click', bulkDeleteMail);
    }

    const decorate = () => {
      bulkMailRows().forEach(row => {
        if (row.querySelector('.pm204-selectbox')) return;
        const box = document.createElement('span');
        box.className = 'pm204-selectbox';
        box.setAttribute('role', 'checkbox');
        box.setAttribute('aria-label', 'Select conversation');
        box.addEventListener('click', event => {
          event.preventDefault();
          event.stopPropagation();
          const id = Number(row.dataset.pm19Thread);
          if (!Number.isFinite(id)) return;
          if (bulkMailSelection.has(id)) bulkMailSelection.delete(id);
          else bulkMailSelection.add(id);
          updateBulkMailUI();
        });
        row.prepend(box);
      });
      updateBulkMailUI();
    };

    decorate();
    if (bulkMailObserver) bulkMailObserver.disconnect();
    bulkMailObserver = new MutationObserver(decorate);
    bulkMailObserver.observe(list, {childList:true, subtree:true});
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
    installBulkMailControls();
    loadAccess();
    [80, 260, 700, 1600, 3200].forEach(delay => setTimeout(() => { ensureSidebar(); installBulkMailControls(); }, delay));
    window.addEventListener('pageshow', () => { ensureSidebar(); installBulkMailControls(); });
    window.addEventListener('resize', ensureSidebar);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
