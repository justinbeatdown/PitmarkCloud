const CACHE='pitmark-race-center-v7-shell-1';
const SHELL=[
  '/race-center',
  '/race-center-icon.svg',
  '/prt-logo.png'
];

self.addEventListener('install',event=>{
  event.waitUntil(
    caches.open(CACHE).then(cache=>cache.addAll(SHELL)).catch(()=>null)
  );
  self.skipWaiting();
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE&&key.startsWith('pitmark-race-center-')).map(key=>caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener('fetch',event=>{
  const request=event.request;
  if(request.method!=='GET')return;
  const url=new URL(request.url);
  if(url.origin!==location.origin)return;

  // Racing data must stay fresh: never answer API calls from cache.
  if(url.pathname.startsWith('/api/public/race-center/')||url.pathname==='/api/public/standings'){
    event.respondWith(fetch(request));
    return;
  }

  // Navigations are network-first with a Race Center shell fallback.
  if(request.mode==='navigate'){
    event.respondWith(
      fetch(request)
        .then(response=>{
          const copy=response.clone();
          caches.open(CACHE).then(cache=>cache.put(request,copy)).catch(()=>{});
          return response;
        })
        .catch(async()=>{
          const exact=await caches.match(request);
          return exact||caches.match('/race-center');
        })
    );
    return;
  }

  // Static Race Center assets can use stale-while-revalidate.
  if(
    url.pathname.endsWith('.css')||
    url.pathname.endsWith('.js')||
    url.pathname.endsWith('.svg')||
    url.pathname.endsWith('.png')||
    url.pathname.startsWith('/standings-logo/')
  ){
    event.respondWith(
      caches.match(request).then(cached=>{
        const network=fetch(request).then(response=>{
          if(response&&response.ok){
            const copy=response.clone();
            caches.open(CACHE).then(cache=>cache.put(request,copy)).catch(()=>{});
          }
          return response;
        }).catch(()=>cached);
        return cached||network;
      })
    );
  }
});