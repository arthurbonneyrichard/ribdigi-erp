/**
 * Stage 166 C1 — IndexedDB offline catalog cache from /sync/pull.
 * Stock figures are non-authoritative (stale) and must be labeled as such in UI.
 */

import { getBoundOfflineDeviceId } from './offlineQueue';

const DB_NAME = 'ribdigi-offline-catalog';
const DB_VERSION = 1;
const STORE = 'products';
const META = 'meta';

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

export async function cacheCatalogProducts(
  products: Array<Record<string, unknown>>,
  opts?: { as_of?: string; device_id?: string },
): Promise<OfflineCatalogMeta> {
  const asOf = opts?.as_of || new Date().toISOString();
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
  return row;
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
    payload?: { products?: Array<Record<string, unknown>>; as_of?: string; stock_authoritative?: boolean };
    result_payload?: { products?: Array<Record<string, unknown>>; as_of?: string };
  }>;
  const catalogOp = ops.find((o) => o.op_type === 'catalog_products');
  if (!catalogOp) {
    return getOfflineCatalogMeta();
  }
  const payload = catalogOp.result_payload || catalogOp.payload || {};
  const products = payload.products || [];
  const meta = await cacheCatalogProducts(products, {
    as_of: payload.as_of || new Date().toISOString(),
    device_id: deviceId,
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
