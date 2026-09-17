// Retirement worker for the pre-HQ mobile Control Center PWA.
// Keep this endpoint alive long enough for installed clients to update, purge the
// obsolete cache, escape the old /control/ scope, and unregister permanently.
const RECOVERY_URL = '/control-reset?source=retired-worker';

self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter(key => key.startsWith('pitmark-mobile-') || key.startsWith('pitmark-control-'))
        .map(key => caches.delete(key))
    );

    await self.clients.claim();
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    await Promise.all(windows.map(async client => {
      try {
        const url = new URL(client.url);
        if (url.pathname.startsWith('/control/')) {
          await client.navigate(RECOVERY_URL);
        }
      } catch (_) {
        // A failed client navigation must not prevent worker retirement.
      }
    }));

    await self.registration.unregister();
  })());
});
