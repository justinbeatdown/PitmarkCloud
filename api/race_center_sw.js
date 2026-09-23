const CACHE='pitmark-race-center-v1';
const SHELL=[
  '/race-center',
  '/standings.css',
  '/standings.js',
  '/race-center-v6.js',
  '/race-center-world.js',
  '/prt-logo.png'
];

self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).catch(()=>{}));
  self.skipWaiting();
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener('fetch',event=>{
  const req=event.request;
  if(req.method!=='GET')return;
  const url=new URL(req.url);
  if(url.origin!==self.location.origin)return;
  if(url.pathname.startsWith('/api/public/race-center/account')||
     url.pathname.includes('/profile-photo/')||
     url.pathname.startsWith('/api/public/race-center/alerts')){
    return;
  }

  if(url.pathname.startsWith('/api/public/standings')||
     url.pathname.startsWith('/api/public/race-center/world')){
    event.respondWith(
      fetch(req).then(response=>{
        const copy=response.clone();
        caches.open(CACHE).then(cache=>cache.put(req,copy)).catch(()=>{});
        return response;
      }).catch(()=>caches.match(req))
    );
    return;
  }

  if(url.pathname.startsWith('/race-center')||
     url.pathname==='/standings.css'||
     url.pathname==='/standings.js'||
     url.pathname==='/race-center-v6.js'||
     url.pathname==='/race-center-world.js'||
     url.pathname==='/prt-logo.png'){
    event.respondWith(
      caches.match(req).then(cached=>cached||fetch(req).then(response=>{
        const copy=response.clone();
        caches.open(CACHE).then(cache=>cache.put(req,copy)).catch(()=>{});
        return response;
      }))
    );
  }
});