(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const qs = (s, r=document) => r.querySelector(s);
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  let socialStatus = null;
  let socialStatusAt = 0;
  let queueSyncPending = false;

  function toast(title, message, kind='success') {
    if (typeof window.showToast === 'function') {
      window.showToast(title, message, kind);
      return;
    }
    console[kind === 'error' ? 'error' : 'log'](title, message);
  }

  async function request(url, opt={}) {
    const headers = {...(opt.headers || {})};
    if (opt.body != null && !(opt.body instanceof FormData) && !headers['Content-Type'])
      headers['Content-Type'] = 'application/json';

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60000);
    try {
      const response = await fetch(url, {
        credentials:'same-origin',
        ...opt,
        headers,
        signal: controller.signal
      });
      const text = await response.text();
      let data;
      try { data = JSON.parse(text); } catch { data = text; }
      if (response.status === 401) {
        location.href = location.pathname.includes('/mobile') ? '/control/mobile' : '/control';
        throw new Error('Session expired.');
      }
      if (!response.ok)
        throw new Error((data && data.detail) || text || `HTTP ${response.status}`);
      return data;
    } catch (err) {
      if (err?.name === 'AbortError')
        throw new Error('Pitmark Cloud took too long to respond. Try again.');
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  async function getSocialStatus(force=false) {
    const now = Date.now();
    if (!force && socialStatus && now - socialStatusAt < 30000)
      return socialStatus;
    try {
      socialStatus = await request('/api/control/social/status');
      socialStatusAt = now;
    } catch (err) {
      console.warn('Social status refresh failed', err);
      socialStatus = socialStatus || {};
    }
    return socialStatus;
  }

  function setBusy(button, label) {
    if (!button) return () => {};
    const original = button.textContent;
    button.dataset.pm194Busy = '1';
    button.disabled = true;
    button.textContent = label;
    button.classList.add('pm194-busy');
    return (next=original) => {
      button.dataset.pm194Busy = '';
      button.disabled = false;
      button.textContent = next;
      button.classList.remove('pm194-busy');
    };
  }

  function statusLine(card, text, kind='working') {
    if (!card) return;
    let line = qs('.pm194-action-status', card);
    if (!line) {
      line = document.createElement('div');
      line.className = 'pm194-action-status';
      const actions = qs('.queue-actions,.m-actions', card);
      (actions?.parentNode || card).insertBefore(line, actions || null);
    }
    line.className = `pm194-action-status ${kind}`;
    line.textContent = text;
  }

  function refreshDesktopSoon() {
    if (queueSyncPending) return;
    queueSyncPending = true;
    setTimeout(() => {
      queueSyncPending = false;
      try { window.loadQueue?.(); } catch {}
      // Status/brief is deliberately background work now.
      setTimeout(() => { try { window.loadStatus?.(); } catch {} }, 120);
    }, 50);
  }

  function refreshMobileSoon() {
    if (queueSyncPending) return;
    queueSyncPending = true;
    setTimeout(() => {
      queueSyncPending = false;
      try { window.queue?.(); } catch {}
      setTimeout(() => { try { window.home?.(); } catch {} }, 180);
    }, 50);
  }

  function cleanSocialCopy(value) {
    let text = String(value || '');
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '$1 $2');
    text = text.replace(/\*\*([^*\n]+)\*\*/g, '$1');
    text = text.replace(/__([^_\n]+)__/g, '$1');
    text = text.replace(/(^|\s)\*([^*\n]+)\*(?=\s|$)/g, '$1$2');
    text = text.replace(/(^|\s)_([^_\n]+)_(?=\s|$)/g, '$1$2');
    return text.trim();
  }

  async function normalizeQueuedPost(id, card) {
    const bodyNode = card?.querySelector('.queue-body,.body');
    const raw = String(bodyNode?.textContent || '').trim();
    if (!raw) return;
    const cleaned = cleanSocialCopy(raw);
    if (!cleaned || cleaned === raw) return;
    await request(`/api/control/autopilot/posts/${id}`, {
      method:'PATCH',
      body:JSON.stringify({body:cleaned})
    });
    if (bodyNode) bodyNode.textContent = cleaned;
  }

  async function handleDesktopAction(button, card, action) {
    if (button.dataset.pm194Busy) return;
    if (action === 'asset') return; // story-image handler remains owned by v191

    const id = card?.dataset.id;
    if (!id) return;

    const label = action === 'publish' ? 'Publishing…'
      : action === 'schedule' ? 'Scheduling…'
      : action === 'approve' ? 'Approving…'
      : action === 'reject' ? 'Rejecting…'
      : action === 'archive' ? 'Archiving…'
      : 'Working…';
    const restore = setBusy(button, label);
    statusLine(card, label.replace('…','') + ' — Pitmark is working.', 'working');

    try {
      if (action === 'publish') {
        await normalizeQueuedPost(id, card);
        const result = await request(`/api/control/social/posts/${id}/publish`, {method:'POST'});
        const platform = String(result?.post?.platform || card.textContent || 'social').toLowerCase();
        statusLine(card, 'Published ✓', 'success');
        toast('Published ✓', `${platform.includes('x') ? 'X' : platform.includes('facebook') ? 'Facebook' : platform.includes('instagram') ? 'Instagram' : 'Social'} post is live.`);
      } else {
        const payload = {action};
        if (action === 'schedule') {
          const input = qs('.schedule-input', card);
          if (!input?.value) {
            input?.focus();
            statusLine(card, 'Choose a schedule time first.', 'error');
            restore();
            return;
          }
          payload.scheduled_for = input.value;
        }
        await request(`/api/control/autopilot/posts/${id}/decision`, {
          method:'POST',
          body:JSON.stringify(payload)
        });
        statusLine(card, `${action.charAt(0).toUpperCase()+action.slice(1)} complete ✓`, 'success');
      }

      restore(action === 'publish' ? 'Published ✓' : 'Done ✓');
      refreshDesktopSoon();
    } catch (err) {
      restore();
      statusLine(card, err.message, 'error');
      toast('Action failed', err.message, 'error');
    }
  }

  async function handleMobileAction(button, card, action) {
    if (button.dataset.pm194Busy) return;
    if (action === 'asset') return;

    const id = card?.dataset.id;
    if (!id) return;

    const label = action === 'publish' ? 'Publishing…'
      : action === 'schedule' ? 'Scheduling…'
      : action === 'approve' ? 'Approving…'
      : action === 'reject' ? 'Rejecting…'
      : action === 'archive' ? 'Archiving…'
      : 'Working…';
    const restore = setBusy(button, label);
    statusLine(card, label.replace('…','') + ' — keep this screen open.', 'working');

    try {
      if (action === 'publish') {
        await normalizeQueuedPost(id, card);
        await request(`/api/control/social/posts/${id}/publish`, {method:'POST'});
        statusLine(card, 'Published ✓', 'success');
        restore('Published ✓');
      } else {
        const payload = {action};
        if (action === 'schedule') {
          const input = qs('.schedule', card);
          if (!input?.value) {
            input?.focus();
            statusLine(card, 'Choose a schedule time first.', 'error');
            restore();
            return;
          }
          payload.scheduled_for = input.value;
        }
        await request(`/api/control/autopilot/posts/${id}/decision`, {
          method:'POST',
          body:JSON.stringify(payload)
        });
        statusLine(card, `${action.charAt(0).toUpperCase()+action.slice(1)} complete ✓`, 'success');
        restore('Done ✓');
      }
      refreshMobileSoon();
    } catch (err) {
      restore();
      statusLine(card, err.message, 'error');
      alert(err.message);
    }
  }

  async function syncMobilePublishButtons() {
    const queue = $('mQueue');
    if (!queue) return;
    const status = await getSocialStatus();
    queue.querySelectorAll('.m-item').forEach(card => {
      const title = String(qs('.top b', card)?.textContent || '').toLowerCase();
      const platform = title.includes('instagram') ? 'instagram'
        : title.includes('facebook') ? 'facebook'
        : /(^|\W)x(\W|$)/.test(title) ? 'x'
        : '';
      if (!platform) return;

      const pill = String(qs('.pill', card)?.textContent || '').trim().toLowerCase();
      const configured = Boolean(status?.[platform]?.configured);
      const publish = qs('[data-pa="publish"]', card);
      if (!publish || publish.dataset.pm194Busy) return;

      const allowed = configured && ['approved','scheduled'].includes(pill);
      publish.disabled = !allowed;
      if (platform === 'x' && allowed)
        publish.title = 'Publish this post to X';
    });
  }

  function observeMobileQueue() {
    const queue = $('mQueue');
    if (!queue || queue.dataset.pm194Observed) return;
    queue.dataset.pm194Observed = '1';
    let pending = false;
    new MutationObserver(mutations => {
      if (!mutations.some(m => m.addedNodes.length || m.removedNodes.length)) return;
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => {
        pending = false;
        syncMobilePublishButtons();
      });
    }).observe(queue, {childList:true,subtree:true});
    syncMobilePublishButtons();
  }

  // Queue actions are handled in capture phase so the UI can provide immediate
  // feedback and avoid the legacy "publish -> reload queue -> reload dashboard
  // -> rebuild command brief" serial wait.
  document.addEventListener('click', e => {
    const desktopButton = e.target.closest?.('.queue-card [data-action]');
    if (desktopButton) {
      const action = desktopButton.dataset.action;
      if (['publish','approve','reject','archive','schedule'].includes(action)) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        handleDesktopAction(desktopButton, desktopButton.closest('.queue-card'), action);
        return;
      }
    }

    const mobileButton = e.target.closest?.('#mQueue [data-pa]');
    if (mobileButton) {
      const action = mobileButton.dataset.pa;
      if (['publish','approve','reject','archive','schedule'].includes(action)) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        handleMobileAction(mobileButton, mobileButton.closest('.m-item'), action);
      }
    }
  }, true);

  function installStyles() {
    if ($('pm194Styles')) return;
    const style = document.createElement('style');
    style.id = 'pm194Styles';
    style.textContent = `
      .pm194-action-status{margin:8px 0 6px;padding:7px 9px;border-radius:8px;font-size:10px;font-weight:750;background:rgba(255,255,255,.04);color:#9aa2ab}
      .pm194-action-status.working{border:1px solid rgba(255,85,0,.22);color:#ff8a4d}
      .pm194-action-status.success{border:1px solid rgba(72,221,131,.18);color:#55dc89}
      .pm194-action-status.error{border:1px solid rgba(255,95,95,.24);color:#ff8181}
      .pm194-busy{cursor:wait!important;opacity:.82!important}
    `;
    document.head.appendChild(style);
  }

  function boot() {
    installStyles();
    observeMobileQueue();
    setTimeout(observeMobileQueue, 500);
    setTimeout(syncMobilePublishButtons, 900);
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 120), {once:true});
  else
    setTimeout(boot, 120);
})();