/* Ribdigi POS offline shell cache — application security only; not OS lockdown. */
const CACHE = 'ribdigi-pos-shell-v1';
const ASSETS = ['/', '/pos', '/manifest.webmanifest', '/icon.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS).catch(() => undefined))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.pathname.startsWith('/api/')) return;
  event.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).catch(() => caches.match('/')))
  );
});
