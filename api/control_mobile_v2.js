(() => {
  'use strict';

  const q = (s, root = document) => root.querySelector(s);
  const qa = (s, root = document) => [...root.querySelectorAll(s)];
  const $ = id => document.getElementById(id);

  function sectionHead(title, detail = '') {
    const el = document.createElement('div');
    el.className = 'pm4-section-head';
    el.innerHTML = `<strong>${title}</strong><span>${detail}</span>`;
    return el;
  }

  function taskShape(button, icon, title, sub, countId) {
    if (!button) return;
    const current = $(countId)?.textContent || '—';
    button.className = 'pm4-task';
    button.innerHTML = `
      <span class="pm4-icon">${icon}</span>
      <span class="pm4-copy"><b>${title}</b><span>${sub}</span></span>
      <b class="pm4-count" id="${countId}">${current}</b>`;
  }

  function syncAttention() {
    ['mPending', 'mShield', 'mOutreach', 'mBlog'].forEach(id => {
      const el = $(id);
      if (!el) return;
      const n = Number(String(el.textContent || '').replace(/[^0-9.-]/g, ''));
      el.closest('.pm4-task')?.classList.toggle('attention', Number.isFinite(n) && n > 0);
    });
  }

  function openView(name) {
    const nav = q(`[data-mnav="${name}"]`);
    if (nav) nav.click();
    else q(`[data-mgo="${name}"]`)?.click();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function cleanDesktopBleed() {
    qa('link[rel="stylesheet"]').forEach(link => {
      const href = link.getAttribute('href') || '';
      if (/control-center-v(?:19|191|195|201|202)\.css/i.test(href)) link.remove();
    });
    document.body.classList.remove('pm-mobile-v2', 'pm-mobile-v3');
    document.body.classList.add('pm-mobile-v4');
  }

  function rebuildHeader() {
    const brandMeta = q('.m-brand span');
    if (brandMeta) brandMeta.textContent = 'MOBILE CONTROL';
    const logout = $('mLogout');
    if (logout) logout.textContent = 'Log out';
  }

  function rebuildHome() {
    const home = q('[data-mview="home"]');
    if (!home || home.dataset.pm4 === '1') return;
    home.dataset.pm4 = '1';

    qa('.pm-mobile-hero,.pm-mobile-section-label,.pm-mobile-quick,.pm-mobile-tools-drawer,.pm4-focus,.pm4-section-head,.pm4-system', home).forEach(x => x.remove());

    const title = q('.m-title', home);
    const h1 = q('h1', title);
    if (h1) h1.textContent = 'Today';

    if (title) {
      title.classList.add('pm4-page-head');
      const live = document.createElement('span');
      live.className = 'pm4-live';
      live.textContent = 'Cloud live';
      title.appendChild(live);
    }

    const stats = q('.m-stats', home);
    if (stats) {
      const pending = $('mPending')?.closest('button');
      const shield = $('mShield')?.closest('button');
      const outreach = $('mOutreach')?.closest('button');
      const blog = $('mBlog')?.closest('button');
      taskShape(pending, '✓', 'Posts to review', 'Approve, schedule or publish', 'mPending');
      taskShape(shield, '⬡', 'Shield review', 'Security decisions that need you', 'mShield');
      taskShape(outreach, '↗', 'Follow-ups', 'Tracks, racers and partners', 'mOutreach');
      taskShape(blog, '▤', 'Draft articles', 'Review and publish Pitmark stories', 'mBlog');
      stats.className = 'pm4-list';

      const focus = document.createElement('section');
      focus.className = 'pm4-focus';
      focus.innerHTML = `
        <div><small>Needs your attention</small><strong>Control queue</strong><span>Start with the things waiting on a decision.</span></div>
        <button type="button" class="pm4-primary">Review now</button>`;
      q('button', focus).onclick = () => openView('autopilot');
      title?.after(focus, sectionHead('Work queue', 'tap to open'));
      focus.nextElementSibling?.after(stats);
    }

    const cards = qa(':scope > .m-card', home);
    const notifications = cards.find(c => /Notifications/i.test(c.textContent));
    const social = cards.find(c => /Social Publishing/i.test(c.textContent));
    const quick = cards.find(c => /Quick Actions/i.test(c.textContent));

    if (notifications) {
      notifications.classList.add('pm4-alerts');
      notifications.querySelector('.m-card-head h2')?.replaceChildren(document.createTextNode('Recent alerts'));
      notifications.before(sectionHead('Recent alerts', 'important events'));
    }

    if (social || quick) {
      const tools = document.createElement('details');
      tools.className = 'pm4-system';
      tools.innerHTML = '<summary>System & automation</summary><div class="pm4-system-body"></div>';
      const body = q('.pm4-system-body', tools);
      [social, quick].filter(Boolean).forEach(card => body.appendChild(card));
      (notifications || stats)?.after(tools);
    }

    const install = $('mInstall');
    if (install) install.textContent = 'Install Pitmark Control';
    syncAttention();
  }

  function rebuildReview() {
    const view = q('[data-mview="autopilot"]');
    if (!view || view.dataset.pm4 === '1') return;
    view.dataset.pm4 = '1';

    const title = q('.m-title', view);
    const h1 = q('h1', title);
    if (h1) h1.textContent = 'Review';

    const composer = qa(':scope > .m-card', view).find(c => /Create Post/i.test(c.textContent));
    const filter = qa(':scope > .m-card', view).find(c => c.querySelector('#mQueueFilter'));
    const queue = $('mQueue');

    if (composer) composer.classList.add('pm4-composer-hidden');
    if (filter && queue) {
      title?.after(filter);
      filter.after(queue);
      queue.after(composer);
    }

    if (title && !q('.pm4-review-tools', view)) {
      const tools = document.createElement('div');
      tools.className = 'pm4-review-tools';
      const refresh = $('mQueueRefresh');
      if (refresh) {
        refresh.textContent = 'Refresh';
        tools.appendChild(refresh);
      }
      const create = document.createElement('button');
      create.type = 'button';
      create.className = 'primary';
      create.textContent = 'New post';
      create.onclick = () => showComposer(true);
      tools.appendChild(create);
      title.after(tools);
    }
  }

  function showComposer(focus = false) {
    const view = q('[data-mview="autopilot"]');
    const composer = qa(':scope > .m-card', view).find(c => /Create Post/i.test(c.textContent));
    if (!composer) return;
    composer.classList.remove('pm4-composer-hidden');
    composer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    if (focus) setTimeout(() => $('mTopic')?.focus(), 260);
  }

  function rebuildMore() {
    const more = q('[data-mview="more"]');
    if (!more || more.dataset.pm4 === '1') return;
    more.dataset.pm4 = '1';
    const h1 = q('.m-title h1', more);
    if (h1) h1.textContent = 'More';

    const rows = qa(':scope > .m-row', more);
    if (rows.length) {
      const list = document.createElement('div');
      list.className = 'pm4-more-list';
      rows.forEach((row, i) => {
        const b = q('b', row)?.textContent || 'Tool';
        const s = q('span', row)?.textContent || '';
        const icons = { Blog: '▤', Outreach: '↗', 'Desktop Control Center': '▣', GitHub: '⌘', Render: '◈', Shopify: '▰' };
        row.innerHTML = `<i>${icons[b] || '•'}</i><span><b>${b}</b><span>${s}</span></span><em>›</em>`;
        list.appendChild(row);
      });
      q('.m-title', more)?.after(list);
    }
    q('.m-big-badge', more)?.closest('.m-card')?.classList.add('hidden');
  }

  function rebuildNav() {
    const nav = q('nav.m-nav');
    if (!nav || nav.dataset.pm4 === '1') return;
    nav.dataset.pm4 = '1';

    const home = q('[data-mnav="home"]', nav);
    const review = q('[data-mnav="autopilot"]', nav);
    const email = q('[data-mnav="email"]', nav);
    const shield = q('[data-mnav="shield"]', nav);
    const more = q('[data-mnav="more"]', nav);

    if (home) home.innerHTML = '⌂<span>Home</span>';
    if (review) {
      review.innerHTML = '✓<span>Review</span>';
      review.addEventListener('click', () => {
        q('.pm4-composer-hidden') || q('[data-mview="autopilot"] .m-card')?.classList.add('pm4-composer-hidden');
      });
    }
    if (shield) shield.innerHTML = '⬡<span>Shield</span>';
    if (more) more.innerHTML = '•••<span>More</span>';

    if (email) {
      email.removeAttribute('data-mnav');
      email.id = 'mNavCreate';
      email.className = 'pm4-create';
      email.innerHTML = '+<span>Create</span>';
      email.onclick = () => {
        review?.click();
        showComposer(true);
      };
    }
  }

  function observeCounts() {
    const observer = new MutationObserver(syncAttention);
    ['mPending', 'mShield', 'mOutreach', 'mBlog'].forEach(id => {
      const el = $(id);
      if (el) observer.observe(el, { childList: true, characterData: true, subtree: true });
    });
  }

  function boot() {
    cleanDesktopBleed();
    rebuildHeader();
    rebuildHome();
    rebuildReview();
    rebuildMore();
    rebuildNav();
    observeCounts();
    syncAttention();

    // Final pass after the older parity scripts finish any async DOM work.
    setTimeout(() => {
      cleanDesktopBleed();
      rebuildHome();
      rebuildReview();
      rebuildMore();
      rebuildNav();
      syncAttention();
    }, 800);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 80), { once: true });
  } else {
    setTimeout(boot, 80);
  }
})();