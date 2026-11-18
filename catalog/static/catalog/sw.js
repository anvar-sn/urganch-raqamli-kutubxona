// Self-clearing Service Worker for UrDU Academic Lyceum Digital Library
const CACHE_NAME = 'uzedu-library-v10';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .then(() => self.registration.unregister())
      .then(() => self.clients.matchAll())
      .then((clients) => {
        clients.forEach((client) => {
          if (client.url && 'navigate' in client) {
            client.navigate(client.url).catch(() => {});
          }
        });
      })
  );
});

self.addEventListener('fetch', (event) => {
  // Always pass through directly to network without offline.html interception
  return;
});
