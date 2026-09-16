(() => {
  const API = '/api/control/social/operator';
  const esc = (v='') => String(v).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const label = (v='') => String(v || '').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());

  function previewAssetUrl(url='') {
    const raw = String(url || '').trim();
    const marker = '/social-assets/';
    const index = raw.indexOf(marker);
    return index >= 0 ? raw.slice(index) : raw;
  }

  function mount() {
    const panel = document.getElementById('socialOperatorPanel');
    if (!panel) return false;
    if (document.getElementById('soDailyCampaign')) return true;
    const review = panel.querySelector('.so-review-head');
    const section = document.createElement('section');
    section.id = 'soDailyCampaign';
    section.className = 'so-daily-campaign';
    section.innerHTML = `
      <div class="so-daily-head">
        <div>
          <div class="so-kicker">Today's Campaign</div>
          <h3 id="soDailyTitle">Building today's Pitmark package…</h3>
          <div class="so-daily-meta"><span id="soDailyTopic">Checking topic</span><span id="soDailyDay">—</span></div>
        </div>
        <div class="so-daily-head-actions">
          <span class="so-live-badge" id="soDailyBadge">Checking</span>
          <button class="btn secondary" id="soDailyRun">Build / Refresh Package</button>
        </div>
      </div>
      <p class="so-daily-summary" id="soDailySummary">Social Operations is checking the strongest verified Pitmark story for today.</p>
      <div class="so-daily-progress">
        <div class="so-daily-progress-card"><span>Platform Copy</span><strong id="soDailyCopy">0/5</strong><small>Facebook · Instagram · X · Discord · TikTok/Reels</small></div>
        <div class="so-daily-progress-card"><span>Instagram Slides</span><strong id="soDailyInstagram">0/6</strong><small>1080×1350 carousel assets</small></div>
        <div class="so-daily-progress-card"><span>Vertical Assets</span><strong id="soDailyVertical">0/4</strong><small>1080×1920 TikTok/Reels assets</small></div>
        <div class="so-daily-progress-card"><span>TikTok / Reels</span><strong id="soDailyTikTok">Building</strong><small>Ready-to-post package; no fake auto-publish</small></div>
      </div>
      <div class="so-daily-queue" id="soDailyQueue"></div>
      <div class="so-daily-assets" id="soDailyAssets"></div>
      <div class="so-inline-alert" id="soDailyMessage"></div>`;
    panel.insertBefore(section, review || null);
    document.getElementById('soDailyRun')?.addEventListener('click', runNow);
    return true;
  }

  async function request(path, options={}) {
    const res = await fetch(API + path, {
      credentials:'same-origin',
      ...options,
      headers:{'Content-Type':'application/json', ...(options.headers || {})},
    });
    if (!res.ok) {
      let message = `${res.status} ${res.statusText}`;
      try { const body = await res.json(); message = body.detail || body.error || message; } catch (_) {}
      throw new Error(message);
    }
    return res.json();
  }

  function renderAssets(campaign) {
    const box = document.getElementById('soDailyAssets');
    if (!box) return;
    const assets = campaign?.assets || [];
    const instagram = assets.filter(x => x.platform === 'instagram' && x.status === 'ready' && x.url).sort((a,b) => a.slot-b.slot);
    const vertical = assets.filter(x => x.platform === 'tiktok_reels' && x.status === 'ready' && x.url).sort((a,b) => a.slot-b.slot);
    const cards = [
      ...instagram.map(x => ({...x, kind:`IG ${x.slot}`})),
      ...vertical.map(x => ({...x, kind:`9:16 ${x.slot}`})),
    ];
    if (!cards.length) {
      box.innerHTML = '<div class="so-daily-empty">Visual assets are being built in small batches so Social Operations does not hammer the server or image API.</div>';
      return;
    }
    box.innerHTML = cards.map(item => {
      const previewUrl = previewAssetUrl(item.url);
      return `
      <a class="so-daily-asset" href="${esc(previewUrl)}" target="_blank" rel="noopener noreferrer" title="Open ${esc(item.kind)} asset">
        <img src="${esc(previewAssetUrl(item.url))}" alt="${esc(item.kind)} campaign asset" loading="lazy" />
        <span>${esc(item.kind)}</span>
      </a>`;
    }).join('');
  }

  function renderQueue(campaign) {
    const box = document.getElementById('soDailyQueue');
    if (!box) return;
    const queue = campaign?.queue || {};
    const platforms = ['facebook','instagram','x','discord'];
    box.innerHTML = platforms.map(platform => {
      const item = queue[platform] || {};
      let state = item.status || 'building';
      if (platform === 'instagram' && campaign?.progress?.complete) state = 'carousel ready';
      if (platform === 'discord' && item.status === 'pending') state = 'copy ready';
      return `<div class="so-daily-queue-item"><span>${esc(label(platform))}</span><strong>${esc(label(state))}</strong></div>`;
    }).join('');
  }

  function render(payload) {
    const campaign = payload?.campaign || payload?.daily_campaign || null;
    const badge = document.getElementById('soDailyBadge');
    const title = document.getElementById('soDailyTitle');
    const summary = document.getElementById('soDailySummary');
    if (!campaign) {
      badge.textContent = payload?.enabled === false ? 'Disabled' : 'Not built';
      title.textContent = payload?.enabled === false ? 'Daily Campaign is disabled' : 'No campaign exists for today yet';
      summary.textContent = payload?.enabled === false ? 'Social Operations will not create the daily package until this feature is enabled.' : 'Run the package once or let the background worker create it automatically.';
      return;
    }
    const progress = campaign.progress || campaign.package?.progress || {};
    const complete = !!progress.complete;
    badge.textContent = complete ? 'Ready' : 'Building';
    badge.classList.toggle('degraded', !complete);
    title.textContent = campaign.title || 'Pitmark Daily Campaign';
    summary.textContent = campaign.summary || 'Today’s Pitmark campaign package.';
    document.getElementById('soDailyTopic').textContent = label(campaign.topic_type || 'campaign');
    document.getElementById('soDailyDay').textContent = campaign.day_key || 'Today';
    document.getElementById('soDailyCopy').textContent = `${progress.copy_ready || 0}/${progress.copy_total || 5}`;
    document.getElementById('soDailyInstagram').textContent = `${progress.ig_assets_ready || 0}/${progress.ig_assets_total || 6}`;
    document.getElementById('soDailyVertical').textContent = `${progress.vertical_assets_ready || 0}/${progress.vertical_assets_total || 4}`;
    document.getElementById('soDailyTikTok').textContent = complete ? 'Ready to post' : 'Building';
    renderQueue(campaign);
    renderAssets(campaign);
  }

  async function load() {
    if (!mount()) return;
    try { render(await request('/daily-campaign/status')); }
    catch (error) {
      const message = document.getElementById('soDailyMessage');
      if (message) message.textContent = `Daily Campaign: ${error.message}`;
    }
  }

  async function runNow() {
    const button = document.getElementById('soDailyRun');
    const message = document.getElementById('soDailyMessage');
    if (!button) return;
    button.disabled = true;
    button.textContent = 'Building…';
    if (message) message.textContent = 'Advancing today’s package…';
    try {
      const result = await request('/daily-campaign/run', {method:'POST'});
      render(result);
      const p = result?.campaign?.progress || result?.progress || {};
      if (message) message.textContent = p.complete
        ? 'Today’s full package is ready.'
        : `Package advanced — copy ${p.copy_ready || 0}/${p.copy_total || 5}, Instagram ${p.ig_assets_ready || 0}/${p.ig_assets_total || 6}, vertical ${p.vertical_assets_ready || 0}/${p.vertical_assets_total || 4}.`;
    } catch (error) {
      if (message) message.textContent = error.message;
    } finally {
      button.disabled = false;
      button.textContent = 'Build / Refresh Package';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const tryMount = () => { if (mount()) load(); else setTimeout(tryMount, 150); };
    tryMount();
    setInterval(load, 60000);
  });
})();