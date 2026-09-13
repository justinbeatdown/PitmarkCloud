(() => {
  const allowedSources = new Set(['facebook','tiktok','instagram','x','discord','league','creator']);
  const allowedAssets = new Set(['race','feedback','invite']);
  const url = new URL(location.href);
  const campaign = url.searchParams.get('utm_campaign') === 'prt_raceproof_202609' ? 'prt_raceproof_202609' : '';
  const sourceRaw = url.searchParams.get('utm_source') || '';
  const assetRaw = url.searchParams.get('utm_content') || '';
  const source = campaign && allowedSources.has(sourceRaw) ? sourceRaw : '';
  const asset = campaign && allowedAssets.has(assetRaw) ? assetRaw : '';

  const attribution = () => ({
    campaign: source && asset ? campaign : '',
    source: source || 'website',
    asset: source && asset ? asset : ''
  });

  const appendAttribution = link => {
    if (!campaign || !source || !asset) return;
    let target;
    try { target = new URL(link.href, location.href); } catch (_) { return; }
    if (target.origin !== location.origin) return;
    if (!['/prt','/prt/apply','/prt/support','/prt/proof/rob','/prt/apply/google'].includes(target.pathname)) return;
    target.searchParams.set('utm_campaign', campaign);
    target.searchParams.set('utm_source', source);
    target.searchParams.set('utm_content', asset);
    target.searchParams.set('utm_medium', ['league','creator'].includes(source) ? 'referral' : 'organic_social');
    link.href = target.href;
  };

  document.querySelectorAll('a[href]').forEach(appendAttribution);

  const record = (stage, placement) => {
    const payload = {...attribution(), stage, placement: placement || ''};
    try {
      fetch('/api/prt/funnel', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        credentials: 'same-origin',
        keepalive: true,
        body: JSON.stringify(payload)
      }).catch(() => {});
    } catch (_) {}
  };

  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0) return;
    const link = event.target.closest?.('a[data-prt-funnel-link]');
    if (!link) return;
    record('cta_click', link.dataset.prtFunnelLink || 'link');
  });

  // Tester proof cleanup: the testimonial card itself is the proof, so the extra
  // orange kicker is redundant. Use TimmyNeutron020's supplied logo without a
  // Pitmark-orange avatar treatment or circular crop.
  document.querySelector('.tester-proof-kicker')?.remove();
  const testimonialAvatar = document.querySelector('.tester-proof-avatar');
  if (testimonialAvatar) {
    testimonialAvatar.src = '/prt-timmy-logo.jpg?v=1';
    Object.assign(testimonialAvatar.style, {
      display: 'block', width: '64px', height: '64px', borderRadius: '8px',
      objectFit: 'contain', background: '#080808', padding: '4px',
      border: '1px solid #2f3434', boxSizing: 'border-box'
    });
  }
})();