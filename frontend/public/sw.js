/* Ribdigi POS offline shell cache — application security only; not OS lockdown. */
const CACHE = 'ribdigi-pos-shell-v5';
const ASSETS = ['/', '/pos', '/manifest.webmanifest', '/icon.png', '/brand/logo-full.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS).catch(() => undefined))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/guides/')) return;
  event.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).catch(() => caches.match('/')))
  );
});
