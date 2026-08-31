(() => {
  const el = id => document.getElementById(id);
  let identities = [];
  let activeThreadId = null;

  async function loadIdentities() {
    const to = el('mMailTo');
    if (!to || el('mMailFromIdentity')) return;
    const select = document.createElement('select');
    select.id = 'mMailFromIdentity';
    select.className = 'm-input';
    select.innerHTML = '<option value="">From — loading identities…</option>';
    to.parentNode.insertBefore(select, to);
    try {
      identities = await api('/api/control/email/identities');
      select.innerHTML = '<option value="">From — Auto (receiving address on replies)</option>' + identities.map(x =>
        `<option value="${esc(x.key)}" ${x.default?'selected':''}>From — ${esc(x.label)} · ${esc(x.address)}</option>`
      ).join('');
    } catch (e) {
      select.innerHTML = '<option value="">From — identity load failed</option>';
    }
  }

  function keyFromAddress(value) {
    const raw = String(value || '').toLowerCase();
    const hit = identities.find(x => raw.includes(String(x.address || '').toLowerCase()));
    return hit ? hit.key : '';
  }

  function ensureDraftDelete() {
    if (el('mMailDeleteDraft')) return;
    const cancel = el('mMailCancel');
    if (!cancel) return;
    const b = document.createElement('button');
    b.id = 'mMailDeleteDraft';
    b.className = 'm-ghost';
    b.textContent = 'Delete Draft';
    b.hidden = true;
    cancel.parentNode.insertBefore(b, cancel);
    b.addEventListener('click', deleteDraft, true);
  }

  function syncDraftDelete() {
    ensureDraftDelete();
    const b = el('mMailDeleteDraft');
    if (b) b.hidden = !mMailDraftId;
  }

  function ensureThreadDelete() {
    const box = el('mMailThread');
    if (!box || !activeThreadId || el('mMailDeleteThread')) return;
    const head = box.querySelector('.m-card-head');
    if (!head) return;
    const b = document.createElement('button');
    b.id = 'mMailDeleteThread';
    b.className = 'm-ghost';
    b.textContent = 'Delete';
    b.addEventListener('click', deleteThread, true);
    head.appendChild(b);
  }

  function addIdentity(payload) {
    payload.from_identity = mMailReplyId ? '' : (el('mMailFromIdentity')?.value || '');
    return payload;
  }

  async function sendIdentity(e) {
    e.preventDefault(); e.stopImmediatePropagation();
    const b = el('mMailSend');
    b.disabled = true; b.textContent = 'Sending…';
    try {
      const p = addIdentity(mailPayload());
      const x = await api('/api/control/email/send', {method:'POST', body:JSON.stringify(p)});
      el('mMailMsg').textContent = `Sent ✓ from ${x.from || ''}`;
      mMailFolder = 'sent';
      document.querySelectorAll('[data-mmail-folder]').forEach(y => y.classList.toggle('active', y.dataset.mmailFolder === 'sent'));
      await mailLoad();
      setTimeout(mailClose, 400);
    } catch (err) {
      el('mMailMsg').textContent = err.message;
    } finally {
      b.disabled = false; b.textContent = 'Send';
    }
  }

  async function draftIdentity(e) {
    e.preventDefault(); e.stopImmediatePropagation();
    const b = el('mMailSaveDraft');
    b.disabled = true;
    try {
      const q = addIdentity(mailPayload());
      q.id = mMailDraftId;
      delete q.reply_to_message_id;
      const x = await api('/api/control/email/drafts', {method:'POST', body:JSON.stringify(q)});
      mMailDraftId = x.id;
      syncDraftDelete();
      el('mMailMsg').textContent = `Draft saved ✓ · ${x.from || ''}`;
      mMailFolder = 'drafts';
      document.querySelectorAll('[data-mmail-folder]').forEach(y => y.classList.toggle('active', y.dataset.mmailFolder === 'drafts'));
      await mailLoad();
    } catch (err) {
      el('mMailMsg').textContent = err.message;
    } finally {
      b.disabled = false;
    }
  }

  async function deleteDraft(e) {
    e?.preventDefault(); e?.stopImmediatePropagation();
    if (!mMailDraftId) return;
    if (!confirm('Delete this draft permanently?')) return;
    const b = el('mMailDeleteDraft');
    if (b) { b.disabled = true; b.textContent = 'Deleting…'; }
    try {
      await api(`/api/control/email/drafts/${mMailDraftId}`, {method:'DELETE'});
      mMailDraftId = null;
      mailClose();
      mMailFolder = 'drafts';
      document.querySelectorAll('[data-mmail-folder]').forEach(y => y.classList.toggle('active', y.dataset.mmailFolder === 'drafts'));
      await mailLoad();
    } catch (err) {
      el('mMailMsg').textContent = err.message;
    } finally {
      if (b) { b.disabled = false; b.textContent = 'Delete Draft'; }
      syncDraftDelete();
    }
  }

  async function deleteThread(e) {
    e?.preventDefault(); e?.stopImmediatePropagation();
    if (!activeThreadId) return;
    if (!confirm('Delete this entire conversation permanently?')) return;
    const id = activeThreadId;
    const b = el('mMailDeleteThread');
    if (b) { b.disabled = true; b.textContent = 'Deleting…'; }
    try {
      await api(`/api/control/email/threads/${id}`, {method:'DELETE'});
      activeThreadId = null;
      el('mMailThread').innerHTML = '<div class="m-card">Conversation deleted.</div>';
      await mailLoad();
    } catch (err) {
      if (b) { b.disabled = false; b.textContent = 'Delete'; }
      alert(err.message);
    }
  }

  function context(e) {
    if (e.target.closest('#mMailCompose')) {
      setTimeout(() => {
        const def = identities.find(x => x.default);
        if (el('mMailFromIdentity')) el('mMailFromIdentity').value = def?.key || 'mail';
        syncDraftDelete();
      }, 0);
      return;
    }

    const thread = e.target.closest('[data-mmail-thread]');
    if (thread) {
      activeThreadId = Number(thread.dataset.mmailThread) || null;
      setTimeout(ensureThreadDelete, 50);
    }

    const draft = e.target.closest('[data-mmail-draft]');
    if (draft) {
      try {
        const x = JSON.parse(decodeURIComponent(draft.dataset.mmailDraft));
        setTimeout(() => {
          const key = keyFromAddress(x.from);
          if (key && el('mMailFromIdentity')) el('mMailFromIdentity').value = key;
          syncDraftDelete();
        }, 0);
      } catch {}
    }

    const reply = e.target.closest('[data-mmail-reply]');
    if (reply) {
      try {
        JSON.parse(decodeURIComponent(reply.dataset.mmailReply));
        setTimeout(() => {
          if (el('mMailFromIdentity')) el('mMailFromIdentity').value = '';
          syncDraftDelete();
        }, 0);
      } catch {}
    }
  }

  function boot() {
    loadIdentities();
    ensureDraftDelete();
    document.addEventListener('click', context, true);
    el('mMailSend')?.addEventListener('click', sendIdentity, true);
    el('mMailSaveDraft')?.addEventListener('click', draftIdentity, true);
    const threadBox = el('mMailThread');
    if (threadBox) {
      new MutationObserver(() => ensureThreadDelete()).observe(threadBox, {childList:true, subtree:true});
    }
  }

  document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 0));
})();