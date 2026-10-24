/** Tenant-scoped in-flight + short TTL cache for GET payloads (nav hover / first paint). */

import { api, tenantHeaderValue } from './api';

type Body = Awaited<ReturnType<typeof api>>;

const store = new Map<string, { at: number; body: Body; tenant: string }>();
const inflight = new Map<string, Promise<Body>>();

/** Long enough to cover hover → click and tab switches; writes still force-refresh. */
const TTL_MS = 45_000;

export function createPaintGet() {
  let firstPaint = true;
  return {
    get(path: string) {
      return getPrefetched(path, { force: !firstPaint });
    },
    done() {
      firstPaint = false;
    },
  };
}

function activeTenant(): string {
  if (typeof window === 'undefined') return '';
  return tenantHeaderValue(localStorage.getItem('tenant')) || '';
}

function sessionScopePart(key: string): string {
  if (typeof window === 'undefined') return '';
  try {
    return sessionStorage.getItem(key) || '';
  } catch {
    return '';
  }
}

function cacheKey(path: string, tenant = activeTenant()): string {
  const user = sessionScopePart('ribdigi:uid');
  const store = sessionScopePart('ribdigi:store');
  return `${tenant || '_'}::${user || '_'}::${store || '_'}::${path}`;
}

export function invalidatePrefetchCache(path?: string) {
  if (path) {
    Array.from(store.keys()).forEach((key) => {
      if (key.endsWith(`::${path}`) || key === cacheKey(path)) store.delete(key);
    });
    Array.from(inflight.keys()).forEach((key) => {
      if (key.endsWith(`::${path}`) || key === cacheKey(path)) inflight.delete(key);
    });
    return;
  }
  store.clear();
  inflight.clear();
}

export function peekPrefetch(path: string): Body | null {
  const tenant = activeTenant();
  const key = cacheKey(path, tenant);
  const hit = store.get(key);
  if (!hit) return null;
  if (hit.tenant !== tenant) {
    store.delete(key);
    return null;
  }
  if (Date.now() - hit.at > TTL_MS) {
    store.delete(key);
    return null;
  }
  return hit.body;
}

export async function prefetchGet(path: string, options?: { force?: boolean }): Promise<Body> {
  const force = Boolean(options?.force);
  const tenant = activeTenant();
  const key = cacheKey(path, tenant);
  if (!force) {
    const existing = peekPrefetch(path);
    if (existing) return existing;
    const pending = inflight.get(key);
    if (pending) return pending;
  } else {
    store.delete(key);
    inflight.delete(key);
  }

  const run = api(path)
    .then((body) => {
      if (activeTenant() !== tenant) return body;
      store.set(key, { at: Date.now(), body, tenant });
      return body;
    })
    .finally(() => {
      inflight.delete(key);
    });
  inflight.set(key, run);
  return run;
}

export async function getPrefetched(path: string, options?: { force?: boolean }): Promise<Body> {
  return prefetchGet(path, options);
}
