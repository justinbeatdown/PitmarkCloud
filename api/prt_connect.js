'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  const state = (id, text, kind = '') => {
    const el = $(id);
    if (!el) return;
    el.textContent = text;
    el.className = 'status' + (kind ? ' ' + kind : '');
  };
  const request = async (url, method, payload) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(url, {
        method,
        credentials: 'same-origin',
        cache: 'no-store',
        signal: controller.signal,
        headers: payload === undefined ? {'Accept':'application/json'} :
          {'Accept':'application/json','Content-Type':'application/json'},
        body: payload === undefined ? undefined : JSON.stringify(payload)
      });
      const json = await response.json().catch(() => ({}));
      if (!response.ok) {
        const info = typeof json.detail === 'string' ? json.detail :
          Array.isArray(json.detail) ? 'Please check your pairing code.' : 'The request failed.';
        const err = new Error(info);
        err.httpStatus = response.status;
        throw err;
      }
      return json;
    } finally {
      clearTimeout(timeout);
    }
  };
  const explain = (err) => {
    if (err && err.httpStatus === 404) return 'Code expired or already used. Return to PRT and start a new connection, then try its new code.';
    if (err && err.httpStatus === 401) return 'Your Race Center session expired. Sign in again and retry.';
    if (err && err.httpStatus === 403) return 'Approval was blocked by a security check. Reload this Race Center page and try again.';
    if (err && err.name === 'AbortError') return 'The request timed out. Please retry.';
    return err && err.message ? err.message : 'Connection failed. Please retry.';
  };
  const approval = $('approve');
  if (approval) approval.addEventListener('click', async () => {
    const codeField = $('code');
    const code = String(codeField ? codeField.value : '').replace(/[^a-z0-9]/gi, '').toUpperCase();
    if (code.length !== 8) {
      state('feedback','Enter the 8-character pairing code currently shown in PRT.','error');
      if (codeField) codeField.focus();
      return;
    }
    approval.disabled = true;
    state('feedback','Approving this computer…','busy');
    try {
      const result = await request('/api/public/race-center/prt/link/approve', 'POST', {
        code, consent_private_history: Boolean($('consent') && $('consent').checked)
      });
      if (!result.ok) throw new Error('Approval did not finish. Please retry.');
      state('feedback','Computer approved! Return to PRT and wait for it to confirm your Race Center connection.','ok');
      approval.textContent = 'Computer approved';
    } catch (error) {
      state('feedback',explain(error),'error');
      approval.disabled = false;
    }
  });
  const unlink = $('unlink');
  if (unlink) unlink.addEventListener('click', async () => {
    if (!window.confirm('Disconnect all PRT computers from your Race Center account?')) return;
    unlink.disabled = true;
    state('historyStatus','Disconnecting PRT devices…','busy');
    try {
      await request('/api/public/race-center/prt/unlink','POST');
      state('historyStatus','All PRT computers disconnected. Your imported history is still saved.','ok');
    } catch (error) {
      state('historyStatus',explain(error),'error');
    } finally { unlink.disabled = false; }
  });
  const erase = $('erase');
  if (erase) erase.addEventListener('click', async () => {
    if (!window.confirm('Permanently delete all PRT-imported racing history? This cannot be undone.')) return;
    erase.disabled = true;
    state('historyStatus','Deleting imported racing history…','busy');
    try {
      await request('/api/public/race-center/prt/my-sessions','DELETE');
      state('historyStatus','Imported racing history deleted. Connected devices stay connected.','ok');
    } catch (error) {
      state('historyStatus',explain(error),'error');
    } finally { erase.disabled = false; }
  });
})();
