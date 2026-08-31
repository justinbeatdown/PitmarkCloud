(() => {
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

  async function sync() {
    try {
      const x = await getMailStatus();
      const connected = Boolean(x?.shield_protection?.connected);

      const desktop = document.getElementById('shieldMailboxStatus');
      if (desktop) {
        desktop.textContent = connected
          ? desktopText(x)
          : 'Communications Protection: Pitmark Mail protection is unavailable.';
      }

      const mobileList = document.getElementById('mShieldList');
      if (mobileList) {
        document.getElementById('mShieldMailStatus')?.remove();
        mobileList.insertAdjacentHTML(
          'beforebegin',
          connected
            ? mobileCard(x)
            : '<div id="mShieldMailStatus" class="m-card bad">Pitmark Mail protection unavailable.</div>'
        );
      }
    } catch (_) {
      const desktop = document.getElementById('shieldMailboxStatus');
      if (desktop) desktop.textContent = 'Communications Protection: unable to read Pitmark Mail status.';
    }
  }

  document.addEventListener('click', e => {
    if (e.target.closest?.('[data-view="shield"], [data-mnav="shield"], #mShieldRefresh')) {
      setTimeout(sync, 120);
    }
  }, true);

  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(sync, 180);
  });
})();
