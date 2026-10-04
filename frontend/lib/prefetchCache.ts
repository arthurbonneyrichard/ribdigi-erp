/** In-flight + short TTL cache for GET payloads prefetched on nav hover. */

import { api } from './api';

type Body = Awaited<ReturnType<typeof api>>;

const store = new Map<string, { at: number; body: Body }>();
const inflight = new Map<string, Promise<Body>>();

const TTL_MS = 15_000;

export function invalidatePrefetchCache(path?: string) {
  if (path) {
    store.delete(path);
    inflight.delete(path);
    return;
  }
  store.clear();
  inflight.clear();
}

export function peekPrefetch(path: string): Body | null {
  const hit = store.get(path);
  if (!hit) return null;
  if (Date.now() - hit.at > TTL_MS) {
    store.delete(path);
    return null;
  }
  return hit.body;
}

export async function prefetchGet(path: string, options?: { force?: boolean }): Promise<Body> {
  const force = Boolean(options?.force);
  if (!force) {
    const existing = peekPrefetch(path);
    if (existing) return existing;
    const pending = inflight.get(path);
    if (pending) return pending;
  } else {
    store.delete(path);
    inflight.delete(path);
  }

  const run = api(path)
    .then((body) => {
      store.set(path, { at: Date.now(), body });
      return body;
    })
    .finally(() => {
      inflight.delete(path);
    });
  inflight.set(path, run);
  return run;
}

export async function getPrefetched(path: string, options?: { force?: boolean }): Promise<Body> {
  return prefetchGet(path, options);
}
