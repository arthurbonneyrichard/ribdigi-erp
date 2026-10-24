import assert from 'node:assert/strict';
import test from 'node:test';
import { createPaintGet, invalidatePrefetchCache, peekPrefetch, prefetchGet } from './prefetchCache';

function installLocalStorage(tenant: string | null) {
  const store: Record<string, string> = {};
  if (tenant) store.tenant = tenant;
  const ls = {
    getItem(key: string) {
      return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null;
    },
    setItem(key: string, value: string) {
      store[key] = String(value);
    },
    removeItem(key: string) {
      delete store[key];
    },
    clear() {
      for (const key of Object.keys(store)) delete store[key];
    },
  };
  (globalThis as { localStorage?: typeof ls }).localStorage = ls;
  (globalThis as { window?: { localStorage: typeof ls } }).window = { localStorage: ls };
}

test('prefetch cache is tenant-scoped and does not leak across tenants', async () => {
  const tenantA = '11111111-1111-4111-8111-111111111111';
  const tenantB = '22222222-2222-4222-8222-222222222222';
  const calls: string[] = [];
  const origFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    calls.push(url);
    return {
      ok: true,
      status: 200,
      headers: { get: () => null },
      json: async () => ({ data: { url, n: calls.length } }),
    } as unknown as Response;
  }) as typeof fetch;

  try {
    installLocalStorage(tenantA);
    invalidatePrefetchCache();
    const a1 = await prefetchGet('/products');
    const a2 = peekPrefetch('/products');
    assert.equal(a1.data.n, 1);
    assert.equal(a2?.data.n, 1);
    assert.equal(calls.length, 1);

    installLocalStorage(tenantB);
    assert.equal(peekPrefetch('/products'), null);
    const b1 = await prefetchGet('/products');
    assert.equal(b1.data.n, 2);
    assert.equal(calls.length, 2);
    assert.equal(peekPrefetch('/products')?.data.n, 2);

    installLocalStorage(tenantA);
    assert.equal(peekPrefetch('/products')?.data.n, 1);
  } finally {
    globalThis.fetch = origFetch;
    invalidatePrefetchCache();
  }
});

test('prefetch cache dedupes in-flight GETs for the same tenant path', async () => {
  const tenantA = '11111111-1111-4111-8111-111111111111';
  let inflight = 0;
  let started = 0;
  const origFetch = globalThis.fetch;
  globalThis.fetch = (async () => {
    started += 1;
    await new Promise((r) => setTimeout(r, 20));
    inflight += 1;
    return {
      ok: true,
      status: 200,
      headers: { get: () => null },
      json: async () => ({ data: { started } }),
    } as unknown as Response;
  }) as typeof fetch;

  try {
    installLocalStorage(tenantA);
    invalidatePrefetchCache();
    const [x, y] = await Promise.all([prefetchGet('/pos/stores'), prefetchGet('/pos/stores')]);
    assert.equal(x.data.started, 1);
    assert.equal(y.data.started, 1);
    assert.equal(started, 1);
    assert.equal(inflight, 1);
  } finally {
    globalThis.fetch = origFetch;
    invalidatePrefetchCache();
  }
});

test('paint getter reuses the first GET then forces after done()', async () => {
  const tenantA = '11111111-1111-4111-8111-111111111111';
  let started = 0;
  const origFetch = globalThis.fetch;
  globalThis.fetch = (async () => {
    started += 1;
    return {
      ok: true,
      status: 200,
      headers: { get: () => null },
      json: async () => ({ data: { started } }),
    } as unknown as Response;
  }) as typeof fetch;

  try {
    installLocalStorage(tenantA);
    invalidatePrefetchCache();
    const paint = createPaintGet();
    const first = await paint.get('/sales/invoices');
    assert.equal(first.data.started, 1);
    assert.equal(started, 1);
    paint.done();
    const second = await paint.get('/sales/invoices');
    assert.equal(second.data.started, 2);
    assert.equal(started, 2);
  } finally {
    globalThis.fetch = origFetch;
    invalidatePrefetchCache();
  }
});
