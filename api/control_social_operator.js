(() => {
  const API = '/api/control/social/operator';
  const esc = (v='') => String(v).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const fmt = iso => {
    if (!iso) return 'Never';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
  };
  let status = null;

  function mount() {
    const dash = document.querySelector('[data-view-section="dashboard"]');
    const auto = document.querySelector('[data-view-section="autopilot"]');
    if (!dash || !auto || document.getElementById('socialOperatorPanel')) return false;

    const dashCard = document.createElement('div');
    dashCard.className = 'social-operator-dash-card';
    dashCard.id = 'socialOperatorDashCard';
    dashCard.innerHTML = `
      <div><div class="so-kicker">Social Operator</div><h3 id="soDashTitle">Checking operator…</h3><p id="soDashCopy">Loading Pitmark's autonomous social operations.</p></div>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><span class="so-live-badge" id="soDashBadge">Checking</span><button class="btn secondary compact" id="soDashOpen">Open Operator</button></div>`;
    const commandBrief = dash.querySelector('.command-brief');
    (commandBrief?.parentNode || dash).insertBefore(dashCard, commandBrief || null);

    const panel = document.createElement('section');
    panel.className = 'panel social-operator-panel';
    panel.id = 'socialOperatorPanel';
    panel.innerHTML = `
      <div class="panel-head queue-head"><div class="panel-icon">◎</div><div><div class="so-kicker">Pitmark Social Operator</div><h2>Social Operations</h2><div class="meta"><span>Facebook</span><span>Instagram</span><span>X</span><span>Growth + Engagement</span></div></div><div class="queue-tools"><span class="so-run-state" id="soLastRun">Loading…</span><button class="btn secondary" id="soRefresh">Refresh</button></div></div>
      <div class="so-hero">
        <div class="so-status-card">
          <div class="so-status-line"><div><div class="so-status-title" id="soStatusTitle">Checking status…</div><div class="so-status-sub" id="soStatusSub">Connecting to the live operator.</div></div><span class="so-live-badge" id="soBadge">Checking</span></div>
          <div class="so-metrics"><div class="so-metric"><span>Scanned</span><strong id="soScanned">—</strong></div><div class="so-metric"><span>Needs Review</span><strong id="soReview">—</strong></div><div class="so-metric"><span>Replies Sent</span><strong id="soReplied">—</strong></div><div class="so-metric"><span>Posts Planned</span><strong id="soPlanned">—</strong></div></div>
          <div class="so-actions"><button class="btn" id="soRunNow">Run Operator Now</button><button class="btn secondary so-btn-danger" id="soPause">Pause Operator</button><button class="btn secondary so-btn-green" id="soResume" hidden>Resume Operator</button><span class="so-inline-alert" id="soActionMsg"></span></div>
          <div class="so-note" id="soReplyNote">Auto-reply status loading…</div>
        </div>
        <div class="so-guard-card"><h3>Guardrails</h3><ul class="so-guard-list" id="soGuardrails"><li>Loading live operator rules…</li></ul></div>
      </div>
      <div class="so-review-head"><div><h3>Engagement Review Queue</h3><div class="so-status-sub">Questions, support-sensitive comments, and X mentions stop here for a human call.</div></div><span class="status-pill" id="soReviewCount">0 waiting</span></div>
      <div class="so-review-list" id="soReviewList"><div class="so-empty">Loading engagement queue…</div></div>`;
    const overview = auto.querySelector('.autopilot-overview');
    (overview?.parentNode || auto).insertBefore(panel, overview || auto.children[1] || null);

    document.getElementById('soDashOpen')?.addEventListener('click', () => {
      document.querySelector('[data-view="autopilot"]')?.click();
      setTimeout(() => document.getElementById('socialOperatorPanel')?.scrollIntoView({behavior:'smooth',block:'start'}), 80);
    });
    document.getElementById('soRefresh')?.addEventListener('click', load);
    document.getElementById('soRunNow')?.addEventListener('click', runNow);
    document.getElementById('soPause')?.addEventListener('click', () => setPaused(true));
    document.getElementById('soResume')?.addEventListener('click', () => setPaused(false));
    document.getElementById('soReviewList')?.addEventListener('click', handleReviewAction);
    return true;
  }

  async function request(path, options={}) {
    const res = await fetch(API + path, {credentials:'same-origin', ...options, headers:{'Content-Type':'application/json', ...(options.headers || {})}});
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try { const j = await res.json(); msg = j.detail || j.error || msg; } catch (_) {}
      throw new Error(msg);
    }
    return res.json();
  }

  function render(s) {
    status = s;
    const run = s.latest_run || {};
    const paused = !!s.paused;
    const enabled = !!s.enabled;
    const operational = enabled && !paused;
    const badgeText = !enabled ? 'Disabled' : paused ? 'Paused' : 'Running';
    const title = !enabled ? 'Operator disabled' : paused ? 'Operator paused' : 'Operator is running';
    const sub = !enabled ? 'The operator is disabled by configuration.' : paused ? 'Background social operations are paused. Manual runs are still available.' : 'Pitmark is actively watching engagement and filling safe posting gaps.';

    ['soBadge','soDashBadge'].forEach(id => {
      const el = document.getElementById(id); if (!el) return;
      el.textContent = badgeText; el.classList.toggle('paused', !operational); el.classList.toggle('offline', !enabled);
    });
    const dt = document.getElementById('soDashTitle'); if (dt) dt.textContent = title;
    const dc = document.getElementById('soDashCopy'); if (dc) dc.textContent = paused ? 'Autonomous runs are paused until you resume them.' : `Last run: ${fmt(run.created_at)} · ${run.review ?? 0} item${run.review===1?'':'s'} flagged for review.`;
    document.getElementById('soStatusTitle').textContent = title;
    document.getElementById('soStatusSub').textContent = sub;
    document.getElementById('soLastRun').textContent = `Last run: ${fmt(run.created_at)}`;
    document.getElementById('soScanned').textContent = run.scanned ?? 0;
    document.getElementById('soReview').textContent = run.review ?? 0;
    document.getElementById('soReplied').textContent = run.replied ?? 0;
    document.getElementById('soPlanned').textContent = run.posts_planned ?? 0;
    document.getElementById('soPause').hidden = paused || !enabled;
    document.getElementById('soResume').hidden = !paused || !enabled;
    const autoReply = s.auto_reply_enabled ? 'ON' : 'OFF';
    document.getElementById('soReplyNote').innerHTML = `Autonomous comment replies: <strong>${autoReply}</strong>${s.auto_reply_enabled ? ' · safe replies may publish automatically.' : ' · review and ingestion remain active, but Pitmark will not auto-reply.'}`;
    document.getElementById('soGuardrails').innerHTML = (s.guardrails || []).map(x => `<li>${esc(x)}</li>`).join('') || '<li>No guardrails reported.</li>';
    renderQueue(s.review_queue || []);
  }

  function renderQueue(items) {
    const box = document.getElementById('soReviewList');
    document.getElementById('soReviewCount').textContent = `${items.length} waiting`;
    if (!items.length) { box.innerHTML = '<div class="so-empty">Nothing needs you right now. That is exactly what we want.</div>'; return; }
    box.innerHTML = items.map(item => `
      <div class="so-review-item" data-so-id="${item.id}">
        <div class="so-review-top"><div><span class="so-platform">${esc(item.platform)}</span> <strong>${esc(item.author_name || 'Unknown user')}</strong></div><span class="so-review-meta">${fmt(item.created_at)}</span></div>
        <p>${esc(item.body || '(No text)')}</p>
        <div class="so-actions">${item.platform !== 'x' ? `<button class="btn secondary compact" data-so-action="reply">Reply</button>` : ''}<button class="btn secondary compact" data-so-action="dismiss">Dismiss</button></div>
      </div>`).join('');
  }

  async function load() {
    if (!mount()) return;
    try { render(await request('/status')); }
    catch (e) {
      document.getElementById('soStatusTitle').textContent = 'Operator status unavailable';
      document.getElementById('soStatusSub').textContent = e.message;
      document.getElementById('soDashTitle').textContent = 'Social Operator needs attention';
      document.getElementById('soDashCopy').textContent = e.message;
    }
  }

  async function runNow() {
    const btn = document.getElementById('soRunNow'), msg = document.getElementById('soActionMsg');
    btn.disabled = true; btn.textContent = 'Running…'; msg.textContent = '';
    try { const r = await request('/run', {method:'POST'}); msg.textContent = r.ok ? `Done — ${r.scanned||0} scanned, ${r.posts_planned||0} post${r.posts_planned===1?'':'s'} planned.` : (r.error || 'Run failed.'); await load(); }
    catch (e) { msg.textContent = e.message; }
    finally { btn.disabled = false; btn.textContent = 'Run Operator Now'; }
  }

  async function setPaused(paused) {
    const msg = document.getElementById('soActionMsg'); msg.textContent = paused ? 'Pausing…' : 'Resuming…';
    try { await request(paused ? '/pause' : '/resume', {method:'POST'}); msg.textContent = paused ? 'Operator paused.' : 'Operator resumed.'; await load(); }
    catch (e) { msg.textContent = e.message; }
  }

  async function handleReviewAction(ev) {
    const btn = ev.target.closest('[data-so-action]'); if (!btn) return;
    const item = btn.closest('[data-so-id]'); const id = item?.dataset.soId; if (!id) return;
    const action = btn.dataset.soAction;
    try {
      btn.disabled = true;
      if (action === 'dismiss') await request(`/engagement/${id}/dismiss`, {method:'POST'});
      if (action === 'reply') {
        const message = window.prompt('Reply as Pitmark:');
        if (!message?.trim()) { btn.disabled = false; return; }
        await request(`/engagement/${id}/reply`, {method:'POST', body:JSON.stringify({message:message.trim()})});
      }
      await load();
    } catch (e) { window.alert(`Social Operator: ${e.message}`); btn.disabled = false; }
  }

  document.addEventListener('DOMContentLoaded', () => { mount(); load(); setInterval(load, 60000); });
})();