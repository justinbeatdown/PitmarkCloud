(() => {
  let lastStatus = null;
  let applying = false;

  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));

  async function getMailStatus() {
    const r = await fetch('/api/control/email/status', {credentials:'same-origin'});
    if (!r.ok) throw new Error('mail status unavailable');
    return await r.json();
  }

  function desktopText(x) {
    const shield = x.shield_protection || {};
    const scanned = Number(shield.protected_events || 0);
    const review = Number(shield.review_count || 0);
    return `Communications Protection: Pitmark Mail is connected and Shield-aware. ${scanned} inbound message${scanned===1?'':'s'} scanned · ${review} requiring review.`;
  }

  function mobileCard(x) {
    const shield = x.shield_protection || {};
    const scanned = Number(shield.protected_events || 0);
    const review = Number(shield.review_count || 0);
    return `<div id="mShieldMailStatus" class="m-card">
      <div class="top"><b>Pitmark Mail Protection</b><span class="pill good">ACTIVE</span></div>
      <div class="body">${esc(`${scanned} scanned · ${review} requiring review`)}</div>
    </div>`;
  }

  function render() {
    if (!lastStatus || applying) return;
    applying = true;
    try {
      const connected = Boolean(lastStatus?.shield_protection?.connected);
      const desktop = document.getElementById('shieldMailboxStatus');
      if (desktop) {
        const wanted = connected
          ? desktopText(lastStatus)
          : 'Communications Protection: Pitmark Mail protection is unavailable.';
        if (desktop.textContent !== wanted) desktop.textContent = wanted;
      }

      const mobileList = document.getElementById('mShieldList');
      if (mobileList) {
        const old = document.getElementById('mShieldMailStatus');
        const wanted = connected
          ? mobileCard(lastStatus)
          : '<div id="mShieldMailStatus" class="m-card bad">Pitmark Mail protection unavailable.</div>';
        if (old) old.outerHTML = wanted;
        else mobileList.insertAdjacentHTML('beforebegin', wanted);
      }
    } finally {
      applying = false;
    }
  }

  async function sync() {
    try {
      lastStatus = await getMailStatus();
      render();
    } catch (_) {
      const desktop = document.getElementById('shieldMailboxStatus');
      if (desktop) desktop.textContent = 'Communications Protection: unable to read Pitmark Mail status.';
    }
  }

  // The core Shield renderer runs asynchronously after navigation and used to
  // overwrite the mail-aware message. Re-apply after that renderer mutates it.
  const observer = new MutationObserver(() => {
    const desktop = document.getElementById('shieldMailboxStatus');
    if (desktop && lastStatus && !applying) queueMicrotask(render);
  });

  document.addEventListener('DOMContentLoaded', () => {
    observer.observe(document.documentElement, {subtree:true, childList:true, characterData:true});
    sync();
  });

  document.addEventListener('click', e => {
    if (e.target.closest?.('[data-view="shield"], [data-mnav="shield"], #mShieldRefresh')) {
      [120, 350, 800].forEach(ms => setTimeout(sync, ms));
    }
  }, true);
})();
