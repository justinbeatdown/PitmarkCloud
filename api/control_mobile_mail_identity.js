(() => {
  const el = id => document.getElementById(id);
  let identities = [];

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

  function context(e) {
    if (e.target.closest('#mMailCompose')) {
      setTimeout(() => {
        const def = identities.find(x => x.default);
        if (el('mMailFromIdentity')) el('mMailFromIdentity').value = def?.key || 'mail';
      }, 0);
      return;
    }
    const draft = e.target.closest('[data-mmail-draft]');
    if (draft) {
      try {
        const x = JSON.parse(decodeURIComponent(draft.dataset.mmailDraft));
        setTimeout(() => {
          const key = keyFromAddress(x.from);
          if (key && el('mMailFromIdentity')) el('mMailFromIdentity').value = key;
        }, 0);
      } catch {}
    }
    const reply = e.target.closest('[data-mmail-reply]');
    if (reply) {
      try {
        const x = JSON.parse(decodeURIComponent(reply.dataset.mmailReply));
        setTimeout(() => {
          if (el('mMailFromIdentity')) el('mMailFromIdentity').value = '';
        }, 0);
      } catch {}
    }
  }

  function boot() {
    loadIdentities();
    document.addEventListener('click', context, true);
    el('mMailSend')?.addEventListener('click', sendIdentity, true);
    el('mMailSaveDraft')?.addEventListener('click', draftIdentity, true);
  }

  document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 0));
})();