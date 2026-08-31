(() => {
  const byId = id => document.getElementById(id);
  const parseList = v => String(v || '').split(',').map(x => x.trim()).filter(Boolean);
  let identities = [];
  let activeDraftId = null;
  let activeReplyId = null;
  let activeThreadId = null;

  async function call(url, opt = {}) {
    const r = await fetch(url, {
      credentials: 'same-origin',
      ...opt,
      headers: {'Content-Type': 'application/json', ...(opt.headers || {})}
    });
    const t = await r.text();
    let d;
    try { d = JSON.parse(t); } catch { d = t; }
    if (!r.ok) throw Error((d && d.detail) || t || 'Request failed');
    return d;
  }

  function identityKeyFromAddress(value) {
    const raw = String(value || '').toLowerCase();
    const match = identities.find(x => raw.includes(String(x.address || '').toLowerCase()));
    return match ? match.key : '';
  }

  function ensureSelector() {
    const to = byId('mailTo');
    if (!to || byId('mailFromIdentity')) return;
    const select = document.createElement('select');
    select.className = 'input wide';
    select.id = 'mailFromIdentity';
    select.setAttribute('aria-label', 'From identity');
    select.innerHTML = '<option value="">From — loading identities…</option>';
    to.parentNode.insertBefore(select, to);
  }

  function ensureDeleteDraftButton() {
    if (byId('mailDeleteDraftBtn')) return;
    const cancel = byId('mailCancelBtn');
    if (!cancel) return;
    const b = document.createElement('button');
    b.className = 'btn ghost';
    b.id = 'mailDeleteDraftBtn';
    b.textContent = 'Delete Draft';
    b.hidden = true;
    cancel.parentNode.insertBefore(b, cancel);
    b.addEventListener('click', deleteDraft, true);
  }

  function ensureDeleteThreadButton() {
    const box = byId('mailThread');
    if (!box || !activeThreadId || byId('mailDeleteThreadBtn')) return;
    const header = box.querySelector('.record-row');
    if (!header) return;
    const b = document.createElement('button');
    b.className = 'btn ghost mini';
    b.id = 'mailDeleteThreadBtn';
    b.textContent = 'Delete Conversation';
    b.style.marginLeft = 'auto';
    b.addEventListener('click', deleteThread, true);
    header.appendChild(b);
  }

  async function loadIdentities() {
    ensureSelector();
    const select = byId('mailFromIdentity');
    if (!select) return;
    try {
      identities = await call('/api/control/email/identities');
      select.innerHTML = '<option value="">From — Auto (receiving address on replies)</option>' + identities.map(x =>
        `<option value="${x.key}" ${x.default ? 'selected' : ''}>From — ${x.label} · ${x.address}</option>`
      ).join('');
    } catch (e) {
      select.innerHTML = '<option value="">From — identity load failed</option>';
    }
  }

  function composePayload() {
    return {
      to: parseList(byId('mailTo')?.value),
      cc: parseList(byId('mailCc')?.value),
      bcc: parseList(byId('mailBcc')?.value),
      from_identity: activeReplyId ? '' : (byId('mailFromIdentity')?.value || ''),
      subject: String(byId('mailSubject')?.value || '').trim(),
      text: byId('mailBody')?.value || '',
      reply_to_message_id: activeReplyId
    };
  }

  async function send(e) {
    e.preventDefault(); e.stopImmediatePropagation();
    const b = byId('mailSendBtn'), m = byId('mailComposeMessage');
    b.disabled = true; b.textContent = 'Sending…';
    try {
      const x = await call('/api/control/email/send', {method:'POST', body:JSON.stringify(composePayload())});
      m.textContent = `Sent ✓ from ${x.from || ''}`;
      setTimeout(() => {
        byId('mailComposePanel').hidden = true;
        const sent = document.querySelector('[data-mail-folder="sent"]');
        if (sent) sent.click();
      }, 450);
    } catch (err) {
      m.textContent = err.message;
    } finally {
      b.disabled = false; b.textContent = 'Send';
    }
  }

  async function draft(e) {
    e.preventDefault(); e.stopImmediatePropagation();
    const b = byId('mailDraftBtn'), m = byId('mailComposeMessage');
    b.disabled = true;
    try {
      const p = composePayload();
      p.id = activeDraftId;
      delete p.reply_to_message_id;
      const x = await call('/api/control/email/drafts', {method:'POST', body:JSON.stringify(p)});
      activeDraftId = x.id;
      syncDeleteDraftButton();
      m.textContent = `Draft saved ✓ · ${x.from || ''}`;
      const drafts = document.querySelector('[data-mail-folder="drafts"]');
      if (drafts) drafts.click();
    } catch (err) {
      m.textContent = err.message;
    } finally {
      b.disabled = false;
    }
  }

  function syncDeleteDraftButton() {
    ensureDeleteDraftButton();
    const b = byId('mailDeleteDraftBtn');
    if (b) b.hidden = !activeDraftId;
  }

  async function deleteDraft(e) {
    e?.preventDefault(); e?.stopImmediatePropagation();
    if (!activeDraftId) return;
    if (!confirm('Delete this draft permanently?')) return;
    const b = byId('mailDeleteDraftBtn');
    if (b) { b.disabled = true; b.textContent = 'Deleting…'; }
    try {
      await call(`/api/control/email/drafts/${activeDraftId}`, {method:'DELETE'});
      activeDraftId = null;
      byId('mailComposePanel').hidden = true;
      const drafts = document.querySelector('[data-mail-folder="drafts"]');
      if (drafts) drafts.click();
    } catch (err) {
      byId('mailComposeMessage').textContent = err.message;
    } finally {
      if (b) { b.disabled = false; b.textContent = 'Delete Draft'; }
      syncDeleteDraftButton();
    }
  }

  async function deleteThread(e) {
    e?.preventDefault(); e?.stopImmediatePropagation();
    if (!activeThreadId) return;
    if (!confirm('Delete this entire conversation permanently?')) return;
    const id = activeThreadId;
    const b = byId('mailDeleteThreadBtn');
    if (b) { b.disabled = true; b.textContent = 'Deleting…'; }
    try {
      await call(`/api/control/email/threads/${id}`, {method:'DELETE'});
      activeThreadId = null;
      const box = byId('mailThread');
      if (box) box.innerHTML = '<div class="mail-empty">Conversation deleted.</div>';
      byId('mailRefreshBtn')?.click();
    } catch (err) {
      if (b) { b.disabled = false; b.textContent = 'Delete Conversation'; }
      alert(err.message);
    }
  }

  function captureContext(e) {
    const compose = e.target.closest('#mailComposeBtn');
    if (compose) {
      activeDraftId = null; activeReplyId = null;
      setTimeout(() => {
        const def = identities.find(x => x.default);
        if (byId('mailFromIdentity')) byId('mailFromIdentity').value = def?.key || 'mail';
        syncDeleteDraftButton();
      }, 0);
      return;
    }

    const thread = e.target.closest('[data-mail-thread]');
    if (thread) {
      activeThreadId = Number(thread.dataset.mailThread) || null;
      setTimeout(ensureDeleteThreadButton, 50);
    }

    const draft = e.target.closest('[data-mail-draft]');
    if (draft) {
      try {
        const x = JSON.parse(decodeURIComponent(draft.dataset.mailDraft));
        activeDraftId = x.id || null;
        activeReplyId = null;
        setTimeout(() => {
          const key = identityKeyFromAddress(x.from);
          if (key && byId('mailFromIdentity')) byId('mailFromIdentity').value = key;
          syncDeleteDraftButton();
        }, 0);
      } catch {}
      return;
    }

    const reply = e.target.closest('[data-mail-reply]');
    if (reply) {
      try {
        const x = JSON.parse(decodeURIComponent(reply.dataset.mailReply));
        activeReplyId = x.reply_to_message_id || null;
        activeDraftId = null;
        setTimeout(() => {
          if (byId('mailFromIdentity')) byId('mailFromIdentity').value = '';
          syncDeleteDraftButton();
        }, 0);
      } catch {}
    }
  }

  function boot() {
    ensureSelector();
    ensureDeleteDraftButton();
    loadIdentities();
    document.addEventListener('click', captureContext, true);
    byId('mailSendBtn')?.addEventListener('click', send, true);
    byId('mailDraftBtn')?.addEventListener('click', draft, true);
    const threadBox = byId('mailThread');
    if (threadBox) {
      new MutationObserver(() => ensureDeleteThreadButton()).observe(threadBox, {childList:true, subtree:true});
    }
  }

  document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 0));
})();