(() => {
  const el = id => document.getElementById(id);
  let identities = [];
  let activeThreadId = null;


  function pitmarkConfirm(message, title = 'Confirm Delete') {
    return new Promise(resolve => {
      document.getElementById('pitmarkConfirmOverlay')?.remove();

      const overlay = document.createElement('div');
      overlay.id = 'pitmarkConfirmOverlay';
      overlay.setAttribute('role', 'presentation');
      overlay.style.cssText = [
        'position:fixed','inset:0','z-index:99999','display:flex',
        'align-items:center','justify-content:center','padding:20px',
        'background:rgba(0,0,0,.72)','backdrop-filter:blur(7px)'
      ].join(';');

      const modal = document.createElement('div');
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-modal', 'true');
      modal.setAttribute('aria-labelledby', 'pitmarkConfirmTitle');
      modal.style.cssText = [
        'width:min(430px,100%)','background:#111214','color:#f5f5f5',
        'border:1px solid rgba(255,85,0,.55)','border-radius:18px',
        'box-shadow:0 22px 70px rgba(0,0,0,.55)','overflow:hidden',
        'font-family:inherit'
      ].join(';');

      modal.innerHTML = `
        <div style="height:4px;background:#ff5500"></div>
        <div style="padding:22px 22px 8px">
          <div style="font-size:12px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:#ff5500;margin-bottom:8px">Pitmark Mail</div>
          <h3 id="pitmarkConfirmTitle" style="margin:0 0 10px;font-size:22px;line-height:1.15;color:#fff">${title}</h3>
          <p style="margin:0;color:#b8bbc2;line-height:1.5;font-size:14px">${message}</p>
        </div>
        <div style="display:flex;gap:10px;justify-content:flex-end;padding:18px 22px 22px">
          <button type="button" data-pm-confirm="cancel" style="border:1px solid #353840;background:#1b1d21;color:#e8e8e8;border-radius:10px;padding:10px 16px;font:inherit;font-weight:750;cursor:pointer">Cancel</button>
          <button type="button" data-pm-confirm="delete" style="border:1px solid #ff5500;background:#ff5500;color:#fff;border-radius:10px;padding:10px 16px;font:inherit;font-weight:850;cursor:pointer">Delete</button>
        </div>`;

      overlay.appendChild(modal);
      document.body.appendChild(overlay);

      const finish = value => {
        document.removeEventListener('keydown', onKey);
        overlay.remove();
        resolve(value);
      };
      const onKey = e => {
        if (e.key === 'Escape') finish(false);
        if (e.key === 'Enter') finish(true);
      };

      document.addEventListener('keydown', onKey);
      overlay.addEventListener('click', e => {
        if (e.target === overlay || e.target.closest('[data-pm-confirm="cancel"]')) finish(false);
        if (e.target.closest('[data-pm-confirm="delete"]')) finish(true);
      });

      modal.querySelector('[data-pm-confirm="cancel"]')?.focus();
    });
  }

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
    if (!(await pitmarkConfirm('This draft will be permanently removed from Pitmark Mail.', 'Delete Draft?'))) return;
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
    if (!(await pitmarkConfirm('This entire conversation and its locally stored messages will be permanently removed.', 'Delete Conversation?'))) return;
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