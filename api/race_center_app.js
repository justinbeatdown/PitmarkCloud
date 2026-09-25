(() => {
  'use strict';

  const routes = [
    ['Home','⌂','/race-center','hub'],
    ['Community','●','/race-center/community','community'],
    ['Live','◉','/race-center/live','live'],
    ['Drivers','⚑','/race-center/drivers','drivers'],
    ['My Racing','★','/race-center/my-racing','my-racing']
  ];

  function currentView(){
    const view = (document.body && document.body.dataset.view) || '';
    if (view === 'myracing') return 'my-racing';
    if (view === 'driverprofile') return 'drivers';
    return view || 'hub';
  }

  function buildMobileNav(){
    if (document.querySelector('.rc-mobile-nav')) return;
    const nav = document.createElement('nav');
    nav.className = 'rc-mobile-nav';
    nav.setAttribute('aria-label','Race Center mobile navigation');
    const view = currentView();
    nav.innerHTML = routes.map(([label,icon,url,key]) =>
      '<a href="'+url+'"'+(view===key?' aria-current="page"':'')+'><span aria-hidden="true">'+icon+'</span><span>'+label+'</span></a>'
    ).join('');
    document.body.appendChild(nav);
  }

  let deferredPrompt = null;

  function isStandalone(){
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  }

  function buildInstallBanner(){
    if (isStandalone() || document.querySelector('.rc-install-banner')) return;
    const banner = document.createElement('div');
    banner.className = 'rc-install-banner';
    banner.innerHTML = '<div><strong>Install Race Center</strong><span>Put racing on your home screen and open it like an app.</span></div><button class="rc-install-action" type="button">Install</button><button class="rc-install-close" type="button" aria-label="Dismiss install prompt">×</button>';
    document.body.appendChild(banner);

    banner.querySelector('.rc-install-close').addEventListener('click', () => {
      banner.classList.remove('is-visible');
      try { localStorage.setItem('rc-install-dismissed-at', String(Date.now())); } catch(_e){}
    });

    banner.querySelector('.rc-install-action').addEventListener('click', async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        try { await deferredPrompt.userChoice; } catch(_e){}
        deferredPrompt = null;
        banner.classList.remove('is-visible');
        return;
      }
      if (/iphone|ipad|ipod/i.test(navigator.userAgent)) {
        alert('On iPhone/iPad: tap Share, then Add to Home Screen.');
      }
    });

    const dismissed = Number(localStorage.getItem('rc-install-dismissed-at') || 0);
    if (!dismissed || Date.now() - dismissed > 7*24*60*60*1000) {
      if (/iphone|ipad|ipod/i.test(navigator.userAgent)) banner.classList.add('is-visible');
    }
  }

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredPrompt = event;
    const banner = document.querySelector('.rc-install-banner');
    if (banner && !isStandalone()) banner.classList.add('is-visible');
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    const banner = document.querySelector('.rc-install-banner');
    if (banner) banner.classList.remove('is-visible');
  });

  async function registerServiceWorker(){
    if (!('serviceWorker' in navigator)) return;
    try {
      await navigator.serviceWorker.register('/race-center-sw.js', {scope:'/race-center'});
    } catch (error) {
      console.warn('Race Center service worker registration failed', error);
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    buildMobileNav();
    buildInstallBanner();
    registerServiceWorker();
  });
})();