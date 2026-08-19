/**
 * Stage 166 C1 / Stage 167 T1 — IndexedDB offline catalog cache from /sync/pull.
 * Stock figures are non-authoritative; Stage 167 adds client TTL / refresh policy.
 */

import { getBoundOfflineDeviceId } from './offlineQueue';

const DB_NAME = 'ribdigi-offline-catalog';
const DB_VERSION = 1;
const STORE = 'products';
const META = 'meta';

/** Stage 167 T1 — default catalog freshness window (4 hours). */
export const DEFAULT_CATALOG_TTL_MS = 4 * 60 * 60 * 1000;

export type OfflineCatalogProduct = {
  id: string;
  sku: string;
  name: string;
  barcode?: string | null;
  selling_price: number;
  stock_qty: number;
  reserved_qty?: number;
  available_qty?: number;
  stock_authoritative: false;
  as_of: string;
};

export type OfflineCatalogMeta = {
  id: 'catalog';
  as_of: string;
  count: number;
  stock_authoritative: false;
  device_id?: string;
  ttl_ms: number;
  expires_at: string;
};

export type OfflineCatalogFreshness = {
  meta: OfflineCatalogMeta | null;
  expired: boolean;
  ttl_ms: number;
  age_ms: number | null;
  expires_at: string | null;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'id' });
        store.createIndex('sku', 'sku', { unique: false });
        store.createIndex('name', 'name', { unique: false });
        store.createIndex('barcode', 'barcode', { unique: false });
      }
      if (!db.objectStoreNames.contains(META)) {
        db.createObjectStore(META, { keyPath: 'id' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('IndexedDB open failed'));
  });
}

function txDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error || new Error('IndexedDB tx failed'));
    tx.onabort = () => reject(tx.error || new Error('IndexedDB tx aborted'));
  });
}

function computeExpiresAt(asOf: string, ttlMs: number): string {
  const base = Date.parse(asOf);
  const start = Number.isFinite(base) ? base : Date.now();
  return new Date(start + ttlMs).toISOString();
}

export async function cacheCatalogProducts(
  products: Array<Record<string, unknown>>,
  opts?: { as_of?: string; device_id?: string; ttl_ms?: number },
): Promise<OfflineCatalogMeta> {
  const asOf = opts?.as_of || new Date().toISOString();
  const ttlMs = opts?.ttl_ms != null && opts.ttl_ms > 0 ? opts.ttl_ms : DEFAULT_CATALOG_TTL_MS;
  const expiresAt = computeExpiresAt(asOf, ttlMs);
  const db = await openDb();
  const tx = db.transaction([STORE, META], 'readwrite');
  const store = tx.objectStore(STORE);
  const metaStore = tx.objectStore(META);

  // Clear previous snapshot so stale SKUs do not linger.
  store.clear();
  for (const raw of products) {
    const id = String(raw.id || '').trim();
    if (!id) continue;
    const row: OfflineCatalogProduct = {
      id,
      sku: String(raw.sku || ''),
      name: String(raw.name || ''),
      barcode: (raw.barcode as string | null | undefined) ?? null,
      selling_price: Number(raw.selling_price || 0),
      stock_qty: Number(raw.stock_qty || 0),
      reserved_qty: Number(raw.reserved_qty || 0),
      available_qty: Number(
        raw.available_qty != null ? raw.available_qty : Number(raw.stock_qty || 0),
      ),
      stock_authoritative: false,
      as_of: asOf,
    };
    store.put(row);
  }
  const meta: OfflineCatalogMeta = {
    id: 'catalog',
    as_of: asOf,
    count: products.length,
    stock_authoritative: false,
    device_id: opts?.device_id,
    ttl_ms: ttlMs,
    expires_at: expiresAt,
  };
  metaStore.put(meta);
  await txDone(tx);
  db.close();
  return meta;
}

export async function getOfflineCatalogMeta(): Promise<OfflineCatalogMeta | null> {
  const db = await openDb();
  const tx = db.transaction(META, 'readonly');
  const req = tx.objectStore(META).get('catalog');
  const row = await new Promise<OfflineCatalogMeta | null>((resolve, reject) => {
    req.onsuccess = () => resolve((req.result as OfflineCatalogMeta) || null);
    req.onerror = () => reject(req.error || new Error('IndexedDB meta failed'));
  });
  await txDone(tx);
  db.close();
  if (!row) return null;
  // Backfill TTL fields for caches written before Stage 167.
  if (!row.ttl_ms || !row.expires_at) {
    const ttl = DEFAULT_CATALOG_TTL_MS;
    return {
      ...row,
      ttl_ms: ttl,
      expires_at: computeExpiresAt(row.as_of, ttl),
    };
  }
  return row;
}

export function isOfflineCatalogExpired(meta: OfflineCatalogMeta | null, nowMs = Date.now()): boolean {
  if (!meta?.as_of) return true;
  const ttl = meta.ttl_ms > 0 ? meta.ttl_ms : DEFAULT_CATALOG_TTL_MS;
  const expires = meta.expires_at ? Date.parse(meta.expires_at) : Date.parse(meta.as_of) + ttl;
  if (!Number.isFinite(expires)) return true;
  return nowMs >= expires;
}

export async function getOfflineCatalogFreshness(): Promise<OfflineCatalogFreshness> {
  const meta = await getOfflineCatalogMeta();
  if (!meta) {
    return {
      meta: null,
      expired: true,
      ttl_ms: DEFAULT_CATALOG_TTL_MS,
      age_ms: null,
      expires_at: null,
    };
  }
  const asOfMs = Date.parse(meta.as_of);
  const age = Number.isFinite(asOfMs) ? Math.max(0, Date.now() - asOfMs) : null;
  return {
    meta,
    expired: isOfflineCatalogExpired(meta),
    ttl_ms: meta.ttl_ms || DEFAULT_CATALOG_TTL_MS,
    age_ms: age,
    expires_at: meta.expires_at || null,
  };
}

export async function searchOfflineCatalog(query: string): Promise<OfflineCatalogProduct[]> {
  const q = query.trim().toLowerCase();
  const db = await openDb();
  const tx = db.transaction(STORE, 'readonly');
  const req = tx.objectStore(STORE).getAll();
  const all: OfflineCatalogProduct[] = await new Promise((resolve, reject) => {
    req.onsuccess = () => resolve((req.result || []) as OfflineCatalogProduct[]);
    req.onerror = () => reject(req.error || new Error('IndexedDB catalog list failed'));
  });
  await txDone(tx);
  db.close();
  if (!q) return all.slice(0, 50);
  return all
    .filter((p) => {
      const sku = (p.sku || '').toLowerCase();
      const name = (p.name || '').toLowerCase();
      const barcode = (p.barcode || '').toLowerCase();
      return sku.includes(q) || name.includes(q) || barcode === q || barcode.includes(q);
    })
    .slice(0, 50);
}

/** Pull catalog via /sync/pull and cache products; ack the catalog op when present. */
export async function refreshOfflineCatalog(
  apiFn: typeof import('./api').api,
): Promise<OfflineCatalogMeta | null> {
  const deviceId = getBoundOfflineDeviceId();
  if (!deviceId) {
    throw new Error('Bind an offline device in Settings → Offline sync before refreshing catalog');
  }
  const res = await apiFn('/sync/pull', {
    method: 'POST',
    body: JSON.stringify({ device_id: deviceId, include_catalog: true, limit: 50 }),
  });
  const ops = (res.data?.ops || []) as Array<{
    id: string;
    op_type: string;
    payload?: {
      products?: Array<Record<string, unknown>>;
      as_of?: string;
      stock_authoritative?: boolean;
      recommended_ttl_seconds?: number;
    };
    result_payload?: {
      products?: Array<Record<string, unknown>>;
      as_of?: string;
      recommended_ttl_seconds?: number;
    };
  }>;
  const catalogOp = ops.find((o) => o.op_type === 'catalog_products');
  if (!catalogOp) {
    return getOfflineCatalogMeta();
  }
  const payload = catalogOp.result_payload || catalogOp.payload || {};
  const products = payload.products || [];
  const ttlSec = Number(payload.recommended_ttl_seconds || 0);
  const ttlMs = ttlSec > 0 ? ttlSec * 1000 : DEFAULT_CATALOG_TTL_MS;
  const meta = await cacheCatalogProducts(products, {
    as_of: payload.as_of || new Date().toISOString(),
    device_id: deviceId,
    ttl_ms: ttlMs,
  });
  try {
    await apiFn('/sync/ack', {
      method: 'POST',
      body: JSON.stringify({ device_id: deviceId, op_ids: [catalogOp.id] }),
    });
  } catch {
    // Cache still valid even if ack fails (device may lack write briefly).
  }
  return meta;
}
