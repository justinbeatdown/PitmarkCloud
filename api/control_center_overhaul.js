(() => {
  const get = id => document.getElementById(id);

  async function json(url) {
    const r = await fetch(url, {credentials:'same-origin'});
    const t = await r.text();
    let d;
    try { d = JSON.parse(t); } catch { d = t; }
    if (!r.ok) throw Error((d && d.detail) || t || 'Request failed');
    return d;
  }

  function dueNow(value) {
    if (!value) return false;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return true;
    return parsed.getTime() <= Date.now();
  }

  function actionableOutreach(rows) {
    const closed = new Set([
      'closed','declined','inactive','archived','published','alumni',
      'active_partner','partnered','complete','completed'
    ]);
    return (rows || []).filter(row => {
      const stage = String(row.stage || '').trim().toLowerCase();
      return !closed.has(stage) && dueNow(row.next_follow_up);
    });
  }

  async function syncOutreachCards() {
    const desktop = get('statOutreach');
    const mobile = get('mOutreach');
    if (!desktop && !mobile) return;
    try {
      const rows = await json('/api/control/outreach');
      const actionable = actionableOutreach(rows);
      const total = rows.length;
      if (desktop) {
        desktop.textContent = String(actionable.length);
        const card = desktop.closest('.stat-card');
        card?.classList.toggle('attention', actionable.length > 0);
        card?.setAttribute('title', `${total} total outreach contact${total === 1 ? '' : 's'} · ${actionable.length} follow-up${actionable.length === 1 ? '' : 's'} due`);
        const label = card?.querySelector('span');
        if (label) label.textContent = 'Outreach Follow-ups';
      }
      if (mobile) {
        mobile.textContent = String(actionable.length);
        const card = mobile.closest('.m-stat, .m-card, button, article, div');
        card?.classList.toggle('attention', actionable.length > 0);
      }
    } catch (err) {
      console.warn('Outreach attention sync failed:', err);
    }
  }

  function simplifyDesktopDashboard() {
    const dashboard = document.querySelector('[data-view-section="dashboard"]');
    if (!dashboard) return;
    dashboard.classList.add('pm-dashboard-clean');

    const quickPanel = [...dashboard.querySelectorAll('.panel')].find(panel =>
      panel.querySelector('h2')?.textContent.trim().toLowerCase() === 'quick actions'
    );
    if (quickPanel) quickPanel.classList.add('pm-redundant-dashboard');

    const count = get('notificationCount');
    const notifications = dashboard.querySelector('.notification-center');
    const applyNotificationState = () => {
      const n = parseInt(String(count?.textContent || '0'), 10) || 0;
      notifications?.classList.toggle('pm-clear', n === 0);
    };
    applyNotificationState();
    if (count) new MutationObserver(applyNotificationState).observe(count, {childList:true, characterData:true, subtree:true});

    const title = dashboard.querySelector('.view-heading p');
    if (title) title.textContent = 'What needs you now — everything else stays out of the way.';
  }

  function hookRefreshes() {
    ['refreshDashboardBtn','mRefresh','mHomeRefresh'].forEach(id => {
      get(id)?.addEventListener('click', () => setTimeout(syncOutreachCards, 250));
    });
    document.addEventListener('click', e => {
      if (e.target.closest?.('[data-view="dashboard"], [data-mnav="home"], [data-mgo="home"]')) {
        setTimeout(syncOutreachCards, 200);
      }
    }, true);
  }

  document.addEventListener('DOMContentLoaded', () => {
    simplifyDesktopDashboard();
    hookRefreshes();
    setTimeout(syncOutreachCards, 250);
    setTimeout(syncOutreachCards, 1200);
  });
})();