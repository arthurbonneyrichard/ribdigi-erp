/* Ribdigi POS offline shell cache — application security only; not OS lockdown.
 * Never touches IndexedDB: queued sales survive every service-worker update. */
const VERSION = 'v9';
const SHELL = `ribdigi-pos-shell-${VERSION}`;
const STATIC = `ribdigi-pos-static-${VERSION}`;
const KEEP = new Set([SHELL, STATIC]);
const ASSETS = ['/', '/pos', '/manifest.webmanifest', '/icon.png', '/brand/logo-full.png'];
const MAX_STATIC_ENTRIES = 400;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL).then((cache) => cache.addAll(ASSETS).catch(() => undefined))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => !KEEP.has(key)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

async function trim(cacheName, max) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  for (let i = 0; i < keys.length - max; i += 1) await cache.delete(keys[i]);
}

function isRsc(req, url) {
  return url.searchParams.has('_rsc') || req.headers.get('RSC') === '1' || req.headers.get('Next-Router-Prefetch') === '1';
}

async function networkFirstPage(req, url) {
  const cache = await caches.open(SHELL);
  try {
    const res = await fetch(req);
    if (res.ok && res.type === 'basic') await cache.put(url.pathname, res.clone());
    return res;
  } catch {
    return (
      (await cache.match(url.pathname)) ||
      (url.pathname.startsWith('/pos') ? await cache.match('/pos') : undefined) ||
      (await cache.match('/')) ||
      Response.error()
    );
  }
}

/** Page-data requests must fall back to the same cached response, never to HTML. */
async function networkFirstExact(req) {
  const cache = await caches.open(SHELL);
  try {
    const res = await fetch(req);
    if (res.ok && res.type === 'basic') await cache.put(req, res.clone());
    return res;
  } catch {
    return (await cache.match(req)) || Response.error();
  }
}

function hardReload(req) {
  return req.cache === 'reload' || req.cache === 'no-cache' || req.cache === 'no-store';
}

/** Dev page chunks reuse a stable URL. Cache-first would keep an old dashboard. */
function isHashedNextChunk(pathname) {
  if (pathname.includes('hot-update')) return false;
  return /\/_next\/static\/.+\.[a-f0-9]{8,}\.(js|css)$/i.test(pathname);
}

async function cacheFirstStatic(req) {
  const cache = await caches.open(STATIC);
  if (!hardReload(req)) {
    const hit = await cache.match(req);
    if (hit) return hit;
  }
  try {
    const res = await fetch(req);
    if (res.ok && res.type === 'basic') {
      await cache.put(req, res.clone());
      void trim(STATIC, MAX_STATIC_ENTRIES);
    }
    return res;
  } catch (err) {
    const hit = await cache.match(req);
    if (hit) return hit;
    throw err;
  }
}

async function shellAsset(req) {
  const cache = await caches.open(SHELL);
  try {
    const res = await fetch(req);
    if (res.ok && res.type === 'basic') await cache.put(req, res.clone());
    return res;
  } catch {
    return (await cache.match(req)) || Response.error();
  }
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/guides/')) return;
  if (isRsc(req, url)) {
    event.respondWith(networkFirstExact(req));
    return;
  }
  if (req.mode === 'navigate') {
    event.respondWith(networkFirstPage(req, url));
    return;
  }
  if (url.pathname.startsWith('/_next/static/')) {
    event.respondWith(isHashedNextChunk(url.pathname) ? cacheFirstStatic(req) : networkFirstExact(req));
    return;
  }
  if (ASSETS.includes(url.pathname)) {
    event.respondWith(shellAsset(req));
  }
});
