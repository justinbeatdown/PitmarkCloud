const CACHE='pitmark-race-center-v7-shell-4';
const SHELL=[
  '/race-center',
  '/race-center/drivers',
  '/race-center/series',
  '/race-center/tracks',
  '/race-center/events',
  '/race-center/teams',
  '/race-center/my-racing',
  '/race-center/standings',
  '/race-center/schedules',
  '/race-center/live',
  '/standings.css',
  '/standings.js',
  '/race-center-v6.js',
  '/race-center-v7.js',
  '/race-center-consumer.js',
  '/prt-logo.png',
  '/race-center-icon-192.png',
  '/race-center-icon-512.png'
];

self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).catch(()=>{}));
  self.skipWaiting();
});

self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE&&key.startsWith('pitmark-race-center-')).map(key=>caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener('fetch',event=>{
  const request=event.request;
  if(request.method!=='GET')return;
  const url=new URL(request.url);
  if(url.origin!==location.origin)return;

  if(url.pathname.startsWith('/api/')){
    event.respondWith(fetch(request));
    return;
  }

  if(url.pathname.startsWith('/race-center')||url.pathname.startsWith('/standings.')||url.pathname.startsWith('/race-center-v')){
    event.respondWith(
      fetch(request).then(response=>{
        const copy=response.clone();
        caches.open(CACHE).then(cache=>cache.put(request,copy)).catch(()=>{});
        return response;
      }).catch(()=>caches.match(request).then(hit=>hit||caches.match('/race-center')))
    );
  }
});

self.addEventListener('push',event=>{
  let data={};
  try{data=event.data?event.data.json():{};}catch(_e){data={title:'Pitmark Race Center',body:event.data?event.data.text():'Race Center update'};}
  const title=data.title||'Pitmark Race Center';
  const options={
    body:data.body||'Something changed in the racing you follow.',
    icon:'/race-center-icon-192.png',
    badge:'/race-center-icon-192.png',
    tag:data.tag||'race-center',
    data:{url:data.url||'/race-center/my-racing'}
  };
  event.waitUntil(self.registration.showNotification(title,options));
});

self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const target=event.notification.data&&event.notification.data.url||'/race-center/my-racing';
  event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>{
    const existing=list.find(client=>client.url.includes('/race-center'));
    if(existing){existing.navigate(target);existing.focus();return;}
    return clients.openWindow(target);
  }));
});
