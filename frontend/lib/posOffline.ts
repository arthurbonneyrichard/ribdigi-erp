/**
 * POS offline foundation — IndexedDB queue + 7-day auth envelope.
 * PostgreSQL remains authoritative; offline stock is cached (non-authoritative).
 */

const DB_NAME = 'ribdigi-pos-offline';
const DB_VERSION = 1;
const OFFLINE_DAYS = 7;

export type QueueState =
  | 'pending'
  | 'syncing'
  | 'synced'
  | 'conflict'
  | 'failed_retryable'
  | 'failed_permanent';

export type OfflineAuthEnvelope = {
  tenant_id: string;
  store_id: string | null;
  user_id: string;
  device_id: string;
  permissions: string[];
  issued_at: string;
  last_online_at: string;
  offline_valid_until: string;
  catalog_version: string;
  application_version: string;
};

export type QueuedSale = {
  id: string;
  client_request_id: string;
  local_receipt_number: string;
  tenant_id: string;
  store_id: string | null;
  device_id: string;
  payload: Record<string, unknown>;
  state: QueueState;
  retry_count: number;
  last_attempt_at: string | null;
  next_retry_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  created_at: string;
  server_sale_id: string | null;
  server_reference: string | null;
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
      if (!db.objectStoreNames.contains('catalog')) {
        db.createObjectStore('catalog', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('sync_queue')) {
        const q = db.createObjectStore('sync_queue', { keyPath: 'id' });
        q.createIndex('state', 'state', { unique: false });
        q.createIndex('client_request_id', 'client_request_id', { unique: true });
      }
      if (!db.objectStoreNames.contains('device_state')) {
        db.createObjectStore('device_state', { keyPath: 'key' });
      }
      if (!db.objectStoreNames.contains('sync_log')) {
        db.createObjectStore('sync_log', { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('IndexedDB open failed'));
  });
}

async function idbGet<T>(store: string, key: IDBValidKey): Promise<T | undefined> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readonly');
    const req = tx.objectStore(store).get(key);
    req.onsuccess = () => resolve(req.result as T | undefined);
    req.onerror = () => reject(req.error);
  });
}

async function idbPut(store: string, value: unknown): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite');
    tx.objectStore(store).put(value);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function idbGetAll<T>(store: string): Promise<T[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readonly');
    const req = tx.objectStore(store).getAll();
    req.onsuccess = () => resolve((req.result || []) as T[]);
    req.onerror = () => reject(req.error);
  });
}

export function getOrCreateDeviceId(): string {
  if (typeof localStorage === 'undefined') return 'device-unknown';
  const key = 'pos_device_id';
  let id = localStorage.getItem(key);
  if (!id || id.length < 8) {
    id = `dev-${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`;
    localStorage.setItem(key, id);
  }
  return id;
}

export function newClientRequestId(): string {
  return `cr-${crypto.randomUUID().replace(/-/g, '')}`;
}

export function buildLocalReceiptNumber(storeCode: string, deviceId: string): string {
  const day = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  const seq = String(Date.now() % 1000000).padStart(6, '0');
  const store = (storeCode || 'STORE').replace(/[^A-Za-z0-9]/g, '').slice(0, 12) || 'STORE';
  const dev = (deviceId || 'POS').replace(/[^A-Za-z0-9]/g, '').slice(-6) || 'POS';
  return `OFF-${store}-${dev}-${day}-${seq}`;
}

export async function saveOfflineAuthEnvelope(partial: {
  tenant_id: string;
  store_id: string | null;
  user_id: string;
  permissions?: string[];
  catalog_version?: string;
}): Promise<OfflineAuthEnvelope> {
  const now = new Date();
  const until = new Date(now.getTime() + OFFLINE_DAYS * 24 * 60 * 60 * 1000);
  const envelope: OfflineAuthEnvelope = {
    tenant_id: partial.tenant_id,
    store_id: partial.store_id,
    user_id: partial.user_id,
    device_id: getOrCreateDeviceId(),
    permissions: partial.permissions || ['pos:write'],
    issued_at: now.toISOString(),
    last_online_at: now.toISOString(),
    offline_valid_until: until.toISOString(),
    catalog_version: partial.catalog_version || now.toISOString(),
    application_version: 'web-mvp',
  };
  await idbPut('device_state', { key: 'offline_auth', value: envelope });
  return envelope;
}

export async function getOfflineAuthEnvelope(): Promise<OfflineAuthEnvelope | null> {
  const row = await idbGet<{ key: string; value: OfflineAuthEnvelope }>('device_state', 'offline_auth');
  return row?.value || null;
}

export function isOfflineAuthValid(envelope: OfflineAuthEnvelope | null): boolean {
  if (!envelope?.offline_valid_until) return false;
  return new Date(envelope.offline_valid_until).getTime() > Date.now();
}

export async function touchLastOnline(): Promise<void> {
  const env = await getOfflineAuthEnvelope();
  if (!env) return;
  env.last_online_at = new Date().toISOString();
  await idbPut('device_state', { key: 'offline_auth', value: env });
}

export async function cacheCatalogProducts(
  products: Array<Record<string, unknown>>,
  meta?: { cached_at?: string }
): Promise<void> {
  const cached_at = meta?.cached_at || new Date().toISOString();
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction('catalog', 'readwrite');
    const store = tx.objectStore('catalog');
    store.clear();
    for (const p of products) {
      store.put({ ...p, id: String(p.id), _cached_at: cached_at });
    }
    store.put({ id: '__meta__', cached_at, count: products.length });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getCachedCatalogMeta(): Promise<{ cached_at: string; count: number } | null> {
  const meta = await idbGet<{ id: string; cached_at: string; count: number }>('catalog', '__meta__');
  if (!meta?.cached_at) return null;
  return { cached_at: meta.cached_at, count: meta.count || 0 };
}

export async function getCachedProducts(): Promise<Array<Record<string, unknown>>> {
  const all = await idbGetAll<Record<string, unknown>>('catalog');
  return all.filter((r) => r.id !== '__meta__');
}

export async function enqueueOfflineSale(input: {
  tenant_id: string;
  store_id: string | null;
  store_code: string;
  payload: Record<string, unknown>;
}): Promise<QueuedSale> {
  const envelope = await getOfflineAuthEnvelope();
  if (!isOfflineAuthValid(envelope)) {
    throw new Error('Offline authorization expired — reconnect to continue selling');
  }
  const client_request_id = newClientRequestId();
  const device_id = getOrCreateDeviceId();
  const sale: QueuedSale = {
    id: crypto.randomUUID(),
    client_request_id,
    local_receipt_number: buildLocalReceiptNumber(input.store_code, device_id),
    tenant_id: input.tenant_id,
    store_id: input.store_id,
    device_id,
    payload: { ...input.payload, client_request_id },
    state: 'pending',
    retry_count: 0,
    last_attempt_at: null,
    next_retry_at: null,
    last_error_code: null,
    last_error_message: null,
    created_at: new Date().toISOString(),
    server_sale_id: null,
    server_reference: null,
  };
  await idbPut('sync_queue', sale);
  return sale;
}

export async function listQueuedSales(): Promise<QueuedSale[]> {
  return idbGetAll<QueuedSale>('sync_queue');
}

export async function countPendingSales(): Promise<number> {
  const all = await listQueuedSales();
  return all.filter((s) => s.state === 'pending' || s.state === 'failed_retryable' || s.state === 'syncing')
    .length;
}

export async function pendingSalesValue(): Promise<number> {
  const all = await listQueuedSales();
  return all
    .filter((s) => s.state === 'pending' || s.state === 'failed_retryable' || s.state === 'syncing')
    .reduce((sum, s) => sum + Number((s.payload as any)?.total || 0), 0);
}

export async function assertSafeLocalReset(): Promise<void> {
  const pending = await countPendingSales();
  if (pending > 0) {
    const value = await pendingSalesValue();
    throw new Error(
      `CRITICAL: ${pending} transaction(s) have not synchronized (pending value ≈ ${value.toFixed(2)}). Local data cannot be reset until sync or authorized recovery.`
    );
  }
}

export async function clearSyncedQueue(): Promise<void> {
  const all = await listQueuedSales();
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction('sync_queue', 'readwrite');
    const store = tx.objectStore('sync_queue');
    for (const s of all) {
      if (s.state === 'synced') store.delete(s.id);
    }
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export type RecoveryPackage = {
  version: 1;
  kind: 'ribdigi-pos-recovery';
  exported_at: string;
  device_id: string;
  envelope: OfflineAuthEnvelope | null;
  catalog_meta: { cached_at: string; count: number } | null;
  pending: QueuedSale[];
  /** Never includes JWT / passwords / refresh tokens. */
  secrets_included: false;
};

export async function buildRecoveryPackage(): Promise<RecoveryPackage> {
  const pending = (await listQueuedSales()).filter(
    (s) => s.state === 'pending' || s.state === 'failed_retryable' || s.state === 'syncing' || s.state === 'conflict'
  );
  return {
    version: 1,
    kind: 'ribdigi-pos-recovery',
    exported_at: new Date().toISOString(),
    device_id: getOrCreateDeviceId(),
    envelope: await getOfflineAuthEnvelope(),
    catalog_meta: await getCachedCatalogMeta(),
    pending,
    secrets_included: false,
  };
}

export async function downloadRecoveryPackage(): Promise<RecoveryPackage> {
  const pkg = await buildRecoveryPackage();
  const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const day = new Date().toISOString().slice(0, 10);
  a.href = url;
  a.download = `ribdigi-pos-recovery-${pkg.device_id}-${day}.json`;
  a.click();
  URL.revokeObjectURL(url);
  return pkg;
}

export async function importRecoveryPackage(
  raw: unknown
): Promise<{ imported: number; skipped: number }> {
  if (!raw || typeof raw !== 'object') {
    throw new Error('Invalid recovery package');
  }
  const pkg = raw as RecoveryPackage;
  if (pkg.kind !== 'ribdigi-pos-recovery' || pkg.version !== 1) {
    throw new Error('Unsupported recovery package version');
  }
  if (!Array.isArray(pkg.pending)) {
    throw new Error('Recovery package missing pending queue');
  }
  const existing = await listQueuedSales();
  const byCrid = new Set(existing.map((s) => s.client_request_id));
  let imported = 0;
  let skipped = 0;
  for (const sale of pkg.pending) {
    if (!sale?.client_request_id || !sale.payload) {
      skipped += 1;
      continue;
    }
    if (byCrid.has(sale.client_request_id)) {
      skipped += 1;
      continue;
    }
    const row: QueuedSale = {
      ...sale,
      id: sale.id || crypto.randomUUID(),
      state:
        sale.state === 'synced'
          ? 'pending'
          : sale.state === 'syncing'
            ? 'pending'
            : sale.state || 'pending',
      retry_count: Number(sale.retry_count) || 0,
      device_id: sale.device_id || getOrCreateDeviceId(),
    };
    await idbPut('sync_queue', row);
    byCrid.add(row.client_request_id);
    imported += 1;
  }
  if (pkg.envelope && isOfflineAuthValid(pkg.envelope)) {
    const current = await getOfflineAuthEnvelope();
    if (!current || !isOfflineAuthValid(current)) {
      await idbPut('device_state', { key: 'offline_auth', value: pkg.envelope });
    }
  }
  return { imported, skipped };
}

type ApiFn = (path: string, opts?: RequestInit) => Promise<any>;

export async function flushOfflineQueue(api: ApiFn): Promise<{ synced: number; failed: number }> {
  const all = await listQueuedSales();
  const pending = all.filter(
    (s) => s.state === 'pending' || s.state === 'failed_retryable'
  );
  let synced = 0;
  let failed = 0;
  for (const sale of pending) {
    sale.state = 'syncing';
    sale.last_attempt_at = new Date().toISOString();
    sale.retry_count += 1;
    await idbPut('sync_queue', sale);
    try {
      const r = await api('/pos/sales', {
        method: 'POST',
        body: JSON.stringify(sale.payload),
      });
      sale.state = 'synced';
      sale.server_sale_id = r.data?.id || null;
      sale.server_reference = r.data?.reference || null;
      sale.last_error_code = null;
      sale.last_error_message = null;
      synced += 1;
    } catch (err: any) {
      const status = err?.status;
      const permanent = status === 400 || status === 404 || status === 422;
      sale.state = permanent ? 'failed_permanent' : 'failed_retryable';
      sale.last_error_code = String(status || 'SYNC_ERROR');
      sale.last_error_message = err?.message || 'Sync failed';
      sale.next_retry_at = permanent
        ? null
        : new Date(Date.now() + Math.min(3600000, 2000 * 2 ** Math.min(sale.retry_count, 8))).toISOString();
      failed += 1;
    }
    await idbPut('sync_queue', sale);
  }
  await touchLastOnline();
  return { synced, failed };
}

export function formatCacheAge(iso: string | null | undefined): string {
  if (!iso) return 'unknown';
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return 'unknown';
  const days = Math.floor(ms / 86400000);
  if (days >= 1) return `${days} day${days === 1 ? '' : 's'} ago`;
  const hours = Math.floor(ms / 3600000);
  if (hours >= 1) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const mins = Math.max(1, Math.floor(ms / 60000));
  return `${mins} min ago`;
}
