(() => {
  function trackDownload(event) {
    if (event.defaultPrevented || (event.type === 'click' && event.button !== 0) ||
        (event.type === 'auxclick' && event.button !== 1)) return;
    const link = event.target.closest?.('a[data-prt-download]');
    if (!link) return;
    const target = new URL(link.href, location.href);
    if (target.origin !== location.origin || target.pathname !== '/downloads/PRT-Setup-Latest.exe') return;

    // Count download clicks, not completed transfers or unique installs. Only
    // the button's source and displayed version are sent; never identity data.
    const version = (document.getElementById('prtBuildVersion')?.textContent || '')
      .trim().replace(/^v/i, '');
    try {
      fetch('/api/prt/analytics/download', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'same-origin',
        keepalive: true,
        body: JSON.stringify({source: link.dataset.prtDownload || 'website', version})
      }).catch(() => {});
    } catch (_) {
      // Analytics must never delay or block the browser's normal download.
    }
  }
  document.addEventListener('click', trackDownload);
  document.addEventListener('auxclick', trackDownload);
})();
