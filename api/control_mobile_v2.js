(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const q = (s, root=document) => root.querySelector(s);
  const qa = (s, root=document) => [...root.querySelectorAll(s)];

  function openView(name) {
    if (typeof window.view === 'function') {
      window.view(name);
      window.scrollTo({top:0, behavior:'smooth'});
      return;
    }
    const nav = q(`[data-mnav="${name}"]`) || q(`[data-mgo="${name}"]`);
    nav?.click();
  }

  function actionButton(icon, title, sub, view) {
    const b = document.createElement('button');
    b.type = 'button';
    b.innerHTML = `<span class="pm-q-icon">${icon}</span><strong>${title}</strong><small>${sub}</small>`;
    b.addEventListener('click', () => openView(view));
    return b;
  }

  function sectionLabel(title, detail='') {
    const el = document.createElement('div');
    el.className = 'pm-mobile-section-label';
    el.innerHTML = `<strong>${title}</strong><span>${detail}</span>`;
    return el;
  }

  function buildHome() {
    const home = q('[data-mview="home"]');
    if (!home || home.dataset.mobileV2) return;
    home.dataset.mobileV2 = '1';

    const title = q('.m-title', home);
    if (title) {
      title.querySelector('h1').textContent = 'Command Center';
      title.querySelector('span')?.remove();
    }

    const hero = document.createElement('section');
    hero.className = 'pm-mobile-hero';
    hero.innerHTML = `
      <span class="pm-mobile-kicker">PITMARK OPERATIONS</span>
      <span class="pm-mobile-live" aria-hidden="true"></span>
      <h2>Everything that needs you. Nothing that doesn’t.</h2>
      <p>Approve content, answer mail, check PRT activity and handle follow-ups without digging through the whole system.</p>`;
    title?.after(hero);

    const quick = document.createElement('div');
    quick.className = 'pm-mobile-quick';
    quick.append(
      actionButton('✉', 'Mail', 'Inbox & replies', 'email'),
      actionButton('✓', 'Review', 'Posts waiting', 'autopilot'),
      actionButton('🤝', 'Outreach', 'Relationships', 'outreach'),
      actionButton('⬡', 'Shield', 'Security review', 'shield'),
      actionButton('▤', 'Blog', 'Draft & publish', 'blog')
    );
    hero.after(sectionLabel('Quick actions', 'tap once'), quick);

    const stats = q('.m-stats', home);
    if (stats) {
      stats.before(sectionLabel('Needs your attention', 'live status'));
      const labels = [
        ['mPending','Posts'],
        ['mShield','Shield review'],
        ['mOutreach','Follow-ups'],
        ['mBlog','Draft articles']
      ];
      labels.forEach(([id, text]) => {
        const value = $(id);
        const button = value?.closest('button');
        const label = button?.querySelector('span');
        if (label) label.textContent = text;
      });
    }

    const cards = qa(':scope > .m-card', home);
    const notifications = cards.find(c => /Notifications/i.test(c.textContent));
    if (notifications) notifications.before(sectionLabel('Inbox for Pitmark', 'important events'));

    const more = q('[data-mview="more"]');
    const social = cards.find(c => /Social Publishing/i.test(c.textContent));
    const actions = cards.find(c => /Quick Actions/i.test(c.textContent));
    const drawer = document.createElement('details');
    drawer.className = 'pm-mobile-tools-drawer';
    drawer.innerHTML = '<summary>Cloud utilities & manual tools</summary>';

    [social, actions].filter(Boolean).forEach(card => drawer.appendChild(card));
    if (more && drawer.children.length > 1) {
      const mt = q('.m-title', more);
      mt?.after(drawer);
    }

    syncAttention();
  }

  function buildMore() {
    const more = q('[data-mview="more"]');
    if (!more || more.dataset.mobileV2) return;
    more.dataset.mobileV2 = '1';

    const title = q('.m-title h1', more);
    if (title) title.textContent = 'Workspaces';

    const grid = document.createElement('div');
    grid.className = 'pm-mobile-workspace-grid';

    const items = [
      ['Campaigns','Rookie Year & racers','more'],
      ['Outreach','Tracks & partners','outreach'],
      ['Blog','Articles & publishing','blog'],
      ['Shield','Security & review','shield'],
      ['Autopilot','Content queue','autopilot'],
      ['Mail','Inbox & compose','email']
    ];

    items.forEach(([name, sub, view]) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.innerHTML = `<strong>${name}</strong><span>${sub}</span>`;
      if (name === 'Campaigns') {
        b.addEventListener('click', () => {
          q('.pm191-mobile-campaign', more)?.scrollIntoView({behavior:'smooth', block:'start'});
        });
      } else {
        b.addEventListener('click', () => openView(view));
      }
      grid.appendChild(b);
    });

    q('.m-title', more)?.after(grid);
  }

  function modernizeMail() {
    const mail = q('[data-mview="email"]');
    if (!mail || mail.dataset.mobileV2) return;
    mail.dataset.mobileV2 = '1';

    const title = q('.m-title h1', mail);
    if (title) title.textContent = 'Pitmark Mail';

    const compose = $('mMailCompose');
    if (compose) compose.textContent = '+ Compose';
  }

  function syncAttention() {
    ['mPending','mShield','mOutreach','mBlog'].forEach(id => {
      const value = $(id);
      const n = Number(String(value?.textContent || '').replace(/[^0-9.-]/g,''));
      value?.closest('button')?.classList.toggle('pm-needs-attention', Number.isFinite(n) && n > 0);
    });
  }

  function updateBrand() {
    const brand = q('.m-brand span');
    if (brand) brand.textContent = 'CONTROL CENTER · MOBILE';
  }

  function boot() {
    document.body.classList.add('pm-mobile-v2');
    updateBrand();
    buildHome();
    buildMore();
    modernizeMail();
    syncAttention();

    // Existing Control Center scripts populate data asynchronously. This updates
    // only attention classes/text and never rewrites whole page sections.
    let passes = 0;
    const timer = setInterval(() => {
      syncAttention();
      buildMore();
      if (++passes >= 12) clearInterval(timer);
    }, 1000);
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 260), {once:true});
  else
    setTimeout(boot, 260);
})();