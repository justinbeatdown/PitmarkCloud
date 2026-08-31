(() => {
  const q = (s, p=document) => p.querySelector(s);
  const qa = (s, p=document) => [...p.querySelectorAll(s)];
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
  let desktopThread = null;
  let mobileThread = null;
  let decorating = false;
  let scheduled = null;

  async function getJson(url) {
    const r = await fetch(url, {credentials:'same-origin'});
    const t = await r.text();
    let d;
    try { d = JSON.parse(t); } catch { d = t; }
    if (!r.ok) throw Error((d && d.detail) || t || 'Request failed');
    return d;
  }

  function shieldTone(s) {
    const c = String(s?.classification || '').toLowerCase();
    if (c === 'legit' || c === 'system') return 'good';
    if (c === 'spam') return 'bad';
    if (c === 'review') return 'warn';
    if (c === 'unverified') return 'neutral';
    return 'neutral';
  }

  function shieldLabel(s) {
    if (!s) return 'Shield scanning';
    const pct = Math.round(Number(s.confidence || 0) * 100);
    return `${String(s.classification || 'Review')} · ${pct}%`;
  }

  function shieldBadge(s) {
    const icon = shieldTone(s) === 'good' ? '✓' : shieldTone(s) === 'bad' ? '!' : shieldTone(s) === 'warn' ? '!' : '◌';
    return `<span class="pm-shield-badge ${shieldTone(s)}"><span class="pm-shield-icon">${icon}</span><span>Shield ${esc(shieldLabel(s))}</span></span>`;
  }

  function shieldDetail(s) {
    if (!s) return '';
    const reasons = (s.reasons || []).map(x => esc(String(x).replaceAll('-', ' '))).join(' · ');
    const pct = Math.round(Number(s.confidence || 0) * 100);
    const action = esc(String(s.action || s.action_taken || 'none').replaceAll('-', ' '));
    return `<div class="pm-shield-detail ${shieldTone(s)}">
      <div class="pm-shield-detail-head"><strong>Pitmark Shield</strong><span>${esc(s.classification || 'Review')} · ${pct}% confidence</span></div>
      <div class="pm-shield-detail-copy">${reasons || 'No additional risk indicators.'}</div>
      <div class="pm-shield-action">Action: ${action}</div>
    </div>`;
  }

  async function decorateDesktopList() {
    const list = q('#mailList');
    if (!list) return;
    const active = q('[data-mail-folder].active')?.dataset.mailFolder || 'inbox';
    const shell = q('.mail-shell');
    if (active !== 'inbox') {
      shell?.classList.remove('pm-thread-open');
      return;
    }
    const rows = await getJson('/api/control/email/threads?folder=inbox');
    const map = new Map(rows.map(x => [String(x.thread_id), x]));
    qa('[data-mail-thread]', list).forEach(el => {
      const item = map.get(String(el.dataset.mailThread));
      if (!item) return;
      el.querySelector('.pm-shield-badge')?.remove();
      el.insertAdjacentHTML('beforeend', shieldBadge(item.shield));
    });
  }

  async function decorateMobileList() {
    const list = q('#mMailList');
    if (!list) return;
    const active = q('[data-mmail-folder].active')?.dataset.mmailFolder || 'inbox';
    if (active !== 'inbox') return;
    const rows = await getJson('/api/control/email/threads?folder=inbox');
    const map = new Map(rows.map(x => [String(x.thread_id), x]));
    qa('[data-mmail-thread]', list).forEach(el => {
      const item = map.get(String(el.dataset.mmailThread));
      if (!item) return;
      el.querySelector('.pm-shield-badge')?.remove();
      el.insertAdjacentHTML('beforeend', shieldBadge(item.shield));
    });
  }

  async function decorateDesktopThread() {
    if (!desktopThread) return;
    const box = q('#mailThread');
    if (!box) return;
    const data = await getJson(`/api/control/email/threads/${desktopThread}`);
    const articles = qa('.mail-thread-message', box);
    (data.messages || []).forEach((m, i) => {
      if (m.direction !== 'inbound' || !m.shield || !articles[i]) return;
      articles[i].querySelector('.pm-shield-detail')?.remove();
      const body = q('.mail-body', articles[i]);
      if (body) body.insertAdjacentHTML('beforebegin', shieldDetail(m.shield));
    });
  }

  async function decorateMobileThread() {
    if (!mobileThread) return;
    const box = q('#mMailThread');
    if (!box) return;
    const data = await getJson(`/api/control/email/threads/${mobileThread}`);
    const articles = qa('.m-item', box);
    (data.messages || []).forEach((m, i) => {
      if (m.direction !== 'inbound' || !m.shield || !articles[i]) return;
      articles[i].querySelector('.pm-shield-detail')?.remove();
      const body = q('.body', articles[i]);
      if (body) body.insertAdjacentHTML('beforebegin', shieldDetail(m.shield));
    });
  }

  async function decorateStatus() {
    const d = q('#mailStatusDetail');
    const m = q('#mMailStatusDetail');
    if (!d && !m) return;
    const x = await getJson('/api/control/email/status');
    const s = x.shield_protection || {};
    const counts = s.classification_counts || {};
    const text = s.connected
      ? `Shield active · ${Number(s.protected_events || 0)} scanned · ${Number(counts.review || 0)} review · ${Number(counts.unverified || 0)} unverified`
      : 'Shield unavailable';
    if (d) {
      const existing = q('.pm-shield-status', d);
      if (existing) existing.textContent = `🛡 ${text}`;
      else d.insertAdjacentHTML('beforeend', `<span class="status-pill status-approved pm-shield-status">🛡 ${esc(text)}</span>`);
    }
    if (m) {
      const parent = m.parentElement || document;
      const existing = q('.pm-shield-status', parent);
      if (existing) existing.textContent = `🛡 ${text}`;
      else m.insertAdjacentHTML('afterend', `<div class="pm-shield-status mobile">🛡 ${esc(text)}</div>`);
    }
  }

  async function decorate() {
    if (decorating) return;
    decorating = true;
    try {
      await Promise.allSettled([
        decorateDesktopList(),
        decorateMobileList(),
        decorateDesktopThread(),
        decorateMobileThread(),
        decorateStatus()
      ]);
    } finally {
      decorating = false;
    }
  }

  function schedule() {
    clearTimeout(scheduled);
    scheduled = setTimeout(decorate, 80);
  }

  document.addEventListener('click', e => {
    const dt = e.target.closest?.('[data-mail-thread]');
    if (dt) {
      desktopThread = Number(dt.dataset.mailThread) || null;
      q('.mail-shell')?.classList.add('pm-thread-open');
      schedule();
    }
    const mt = e.target.closest?.('[data-mmail-thread]');
    if (mt) {
      mobileThread = Number(mt.dataset.mmailThread) || null;
      schedule();
    }
    const df = e.target.closest?.('[data-mail-folder]');
    if (df && df.dataset.mailFolder !== 'inbox') {
      desktopThread = null;
      q('.mail-shell')?.classList.remove('pm-thread-open');
    }
    if (df && df.dataset.mailFolder === 'inbox') {
      desktopThread = null;
      q('.mail-shell')?.classList.remove('pm-thread-open');
    }
    schedule();
  }, true);

  document.addEventListener('DOMContentLoaded', () => {
    const observer = new MutationObserver(schedule);
    ['mailList','mailThread','mailStatusDetail','mMailList','mMailThread','mMailStatusDetail'].forEach(id => {
      const el = document.getElementById(id);
      if (el) observer.observe(el, {childList:true, subtree:true});
    });
    schedule();
  });
})();