(() => {
  // Only this published campaign's public labels are accepted. Do not collect
  // arbitrary URL parameters, referrers, personal data, or browser identifiers.
  const params = new URL(location.href).searchParams;
  const sources = ['facebook', 'tiktok', 'instagram', 'x', 'discord', 'league', 'creator'];
  const assets = ['race', 'feedback', 'invite'];
  const campaign = params.get('utm_campaign') === 'prt_raceproof_202609' &&
    sources.includes(params.get('utm_source')) && assets.includes(params.get('utm_content'))
    ? {name: 'prt_raceproof_202609', source: params.get('utm_source'), asset: params.get('utm_content')}
    : null;

  if (campaign) {
    document.querySelectorAll('a[href]').forEach(link => {
      let target;
      try { target = new URL(link.href, location.href); } catch (_) { return; }
      // Keep attribution on the site's setup path. Installer, checkout,
      // Discord, email, and external URLs retain their original behavior.
      if (target.origin !== location.origin || !['/prt', '/prt/support', '/prt/apply'].includes(target.pathname)) return;
      target.searchParams.set('utm_campaign', campaign.name);
      target.searchParams.set('utm_source', campaign.source);
      target.searchParams.set('utm_content', campaign.asset);
      target.searchParams.set('utm_medium', ['league', 'creator'].includes(campaign.source) ? 'referral' : 'organic_social');
      link.href = target.href;
    });
  }

  function trackDownload(event) {
    if (event.defaultPrevented || (event.type === 'click' && event.button !== 0) ||
        (event.type === 'auxclick' && event.button !== 1)) return;
    const link = event.target.closest?.('a[data-prt-download]');
    if (!link) return;
    const target = new URL(link.href, location.href);
    if (target.origin !== location.origin || target.pathname !== '/downloads/PRT-Setup-Latest.exe') return;

    // Count download clicks, not completed transfers or unique installs. Only
    // public campaign/button labels and displayed version are sent.
    const placement = link.dataset.prtDownload || 'website';
    const source = campaign ? [placement, campaign.source, campaign.asset, campaign.name].join('|') : placement;
    const version = (document.getElementById('prtBuildVersion')?.textContent || '')
      .trim().replace(/^v/i, '');
    try {
      fetch('/api/prt/analytics/download', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'same-origin',
        keepalive: true,
        body: JSON.stringify({source, version})
      }).catch(() => {});
    } catch (_) {
      // Analytics must never delay or block the browser's normal download.
    }
  }
  document.addEventListener('click', trackDownload);
  document.addEventListener('auxclick', trackDownload);
})();
