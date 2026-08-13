/* Stage 163 P1 — static-asset service worker. Never cache /api/v1/* or auth tokens. */
const CACHE_NAME = 'ribdigi-static-v163';
const PRECACHE = ['/', '/manifest.webmanifest'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

function isApiOrAuth(url) {
  const path = url.pathname || '';
  if (path.startsWith('/api/') || path.includes('/api/v1/')) return true;
  if (path.includes('token') || path.includes('auth')) return true;
  return false;
}

function isStaticAsset(url) {
  if (url.origin !== self.location.origin) return false;
  if (isApiOrAuth(url)) return false;
  return (
    url.pathname.startsWith('/_next/static/') ||
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.jpg') ||
    url.pathname.endsWith('.jpeg') ||
    url.pathname.endsWith('.svg') ||
    url.pathname.endsWith('.webp') ||
    url.pathname.endsWith('.ico') ||
    url.pathname.endsWith('.woff') ||
    url.pathname.endsWith('.woff2') ||
    url.pathname === '/manifest.webmanifest'
  );
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (isApiOrAuth(url)) {
    // Network-only for API and auth — never put responses (or tokens) in Cache Storage.
    return;
  }
  if (!isStaticAsset(url) && req.mode === 'navigate') {
    // Navigations: network-first; fallback to precached shell only.
    event.respondWith(
      fetch(req).catch(() => caches.match('/') || Response.error())
    );
    return;
  }
  if (!isStaticAsset(url)) return;
  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(req);
      if (cached) return cached;
      const res = await fetch(req);
      if (res && res.ok) {
        cache.put(req, res.clone());
      }
      return res;
    })
  );
});
