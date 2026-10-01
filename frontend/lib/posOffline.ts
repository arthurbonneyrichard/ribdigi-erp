/**
 * POS offline queue on IndexedDB. PostgreSQL remains authoritative.
 * Default authorization window is 168 hours (7 days, refresh-token aligned) from
 * GET /pos/offline-policy — not a client hardcode.
 */

import { decryptJson, encryptJson, webCryptoAvailable } from './deviceCrypto';

const DB_NAME = 'ribdigi-pos-offline';
const DB_VERSION = 2;
export const DEFAULT_OFFLINE_AUTH_HOURS = 168;
export const MAX_SYNC_RETRIES = 8;

export type QueueState =
  | 'pending'
  | 'syncing'
  | 'synced'
  | 'conflict'
  | 'failed_retryable'
  | 'failed_permanent'
  | 'expired';

export type OfflineAuthEnvelope = {
  tenant_id: string;
  store_id: string | null;
  user_id: string;
  device_id: string;
  permissions: string[];
  issued_at: string;
  last_online_at: string;
  offline_valid_until: string;
  offline_auth_hours: number;
  catalog_version: string;
  application_version: string;
  scope: string;
};

export type QueuedSale = {
  id: string;
  scope: string;
  client_request_id: string;
  local_receipt_number: string;
  tenant_id: string;
  store_id: string | null;
  user_id: string;
  device_id: string;
  payload: Record<string, unknown>;
  payload_enc?: string;
  state: QueueState;
  retry_count: number;
  last_attempt_at: string | null;
  next_retry_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  created_at: string;
  server_sale_id: string | null;
  server_reference: string | null;
  conflict?: Record<string, unknown> | null;
};

let deviceIdMem = '';
let activeScopeMem = '';

export function partitionScope(tenantId: string, userId: string, storeId: string | null): string {
  return `${tenantId || '_'}::${userId || '_'}::${storeId || '_'}`;
}

export function setActiveOfflineScope(scope: string) {
  activeScopeMem = scope;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (event) => {
      const db = req.result;
      const oldVersion = event.oldVersion || 0;
      if (oldVersion < 1) {
        if (!db.objectStoreNames.contains('catalog')) {
          db.createObjectStore('catalog', { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('sync_queue')) {
          const q = db.createObjectStore('sync_queue', { keyPath: 'id' });
          q.createIndex('state', 'state', { unique: false });
          q.createIndex('client_request_id', 'client_request_id', { unique: false });
        }
        if (!db.objectStoreNames.contains('device_state')) {
          db.createObjectStore('device_state', { keyPath: 'key' });
        }
        if (!db.objectStoreNames.contains('sync_log')) {
          db.createObjectStore('sync_log', { keyPath: 'id', autoIncrement: true });
        }
      }
      if (oldVersion < 2 && db.objectStoreNames.contains('sync_queue')) {
        const tx = req.transaction;
        if (tx) {
          const q = tx.objectStore('sync_queue');
          if (q.indexNames.contains('client_request_id')) {
            try {
              q.deleteIndex('client_request_id');
            } catch {
              /* ignore */
            }
          }
          if (!q.indexNames.contains('client_request_id')) {
            q.createIndex('client_request_id', 'client_request_id', { unique: false });
          }
          if (!q.indexNames.contains('scope')) {
            q.createIndex('scope', 'scope', { unique: false });
          }
        }
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

async function persistPayload(sale: QueuedSale): Promise<QueuedSale> {
  if (!webCryptoAvailable()) return sale;
  const { payload, ...rest } = sale;
  const payload_enc = await encryptJson(payload);
  return { ...rest, payload: { offline_encrypted: true }, payload_enc };
}

async function revealPayload(sale: QueuedSale): Promise<QueuedSale> {
  if (sale.payload_enc) {
    try {
      const payload = await decryptJson<Record<string, unknown>>(sale.payload_enc);
      return { ...sale, payload };
    } catch {
      return sale;
    }
  }
  return sale;
}

export function getOrCreateDeviceId(): string {
  if (deviceIdMem && deviceIdMem.length >= 8) return deviceIdMem;
  if (typeof localStorage !== 'undefined') {
    const legacy = (localStorage.getItem('pos_device_id') || '').trim();
    if (legacy.length >= 8) {
      deviceIdMem = legacy;
      localStorage.removeItem('pos_device_id');
      void idbPut('device_state', { key: 'device_id', value: deviceIdMem });
      return deviceIdMem;
    }
  }
  deviceIdMem = `dev-${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`;
  void idbPut('device_state', { key: 'device_id', value: deviceIdMem }).catch(() => undefined);
  return deviceIdMem;
}

export async function hydrateDeviceId(): Promise<string> {
  const row = await idbGet<{ key: string; value: string }>('device_state', 'device_id');
  if (row?.value && row.value.length >= 8) {
    deviceIdMem = row.value;
    return deviceIdMem;
  }
  return getOrCreateDeviceId();
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

export function hoursUntilValid(hours: number | null | undefined): number {
  const n = Number(hours);
  if (!Number.isFinite(n)) return DEFAULT_OFFLINE_AUTH_HOURS;
  return Math.min(168, Math.max(1, Math.round(n)));
}

export async function saveOfflineAuthEnvelope(partial: {
  tenant_id: string;
  store_id: string | null;
  user_id: string;
  permissions?: string[];
  catalog_version?: string;
  offline_auth_hours?: number;
}): Promise<OfflineAuthEnvelope> {
  if (!partial.user_id || !partial.tenant_id) {
    throw new Error('Offline authorization requires a prior online sign-in on this device');
  }
  const now = new Date();
  const hours = hoursUntilValid(partial.offline_auth_hours);
  const until = new Date(now.getTime() + hours * 60 * 60 * 1000);
  const scope = partitionScope(partial.tenant_id, partial.user_id, partial.store_id);
  const envelope: OfflineAuthEnvelope = {
    tenant_id: partial.tenant_id,
    store_id: partial.store_id,
    user_id: partial.user_id,
    device_id: getOrCreateDeviceId(),
    permissions: partial.permissions || ['pos:write'],
    issued_at: now.toISOString(),
    last_online_at: now.toISOString(),
    offline_valid_until: until.toISOString(),
    offline_auth_hours: hours,
    catalog_version: partial.catalog_version || now.toISOString(),
    application_version: 'web-mvp',
    scope,
  };
  setActiveOfflineScope(scope);
  const stored = webCryptoAvailable()
    ? { key: 'offline_auth', value: envelope, enc: await encryptJson(envelope) }
    : { key: 'offline_auth', value: envelope };
  await idbPut('device_state', stored);
  return envelope;
}

export async function getOfflineAuthEnvelope(): Promise<OfflineAuthEnvelope | null> {
  const row = await idbGet<{ key: string; value?: OfflineAuthEnvelope; enc?: string }>(
    'device_state',
    'offline_auth'
  );
  if (!row) return null;
  if (row.enc) {
    try {
      return await decryptJson<OfflineAuthEnvelope>(row.enc);
    } catch {
      return row.value || null;
    }
  }
  return row.value || null;
}

export function isOfflineAuthValid(
  envelope: OfflineAuthEnvelope | null,
  now = Date.now()
): boolean {
  if (!envelope?.offline_valid_until || !envelope.user_id || !envelope.tenant_id) return false;
  return new Date(envelope.offline_valid_until).getTime() > now;
}

export async function touchLastOnline(): Promise<void> {
  const env = await getOfflineAuthEnvelope();
  if (!env) return;
  env.last_online_at = new Date().toISOString();
  await saveOfflineAuthEnvelope({
    tenant_id: env.tenant_id,
    store_id: env.store_id,
    user_id: env.user_id,
    permissions: env.permissions,
    catalog_version: env.catalog_version,
    offline_auth_hours: env.offline_auth_hours,
  });
}

function catalogMetaId(scope: string) {
  return `${scope}::__meta__`;
}

export async function cacheCatalogProducts(
  products: Array<Record<string, unknown>>,
  meta?: { cached_at?: string; scope?: string }
): Promise<void> {
  const env = await getOfflineAuthEnvelope();
  const scope = meta?.scope || env?.scope || activeScopeMem || partitionScope('', '', null);
  const cached_at = meta?.cached_at || new Date().toISOString();
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction('catalog', 'readwrite');
    const store = tx.objectStore('catalog');
    const prefix = `${scope}::`;
    const req = store.openCursor();
    req.onsuccess = () => {
      const cursor = req.result;
      if (cursor) {
        if (String(cursor.key).startsWith(prefix)) cursor.delete();
        cursor.continue();
      }
    };
    for (const p of products) {
      store.put({ ...p, id: `${scope}::${String(p.id)}`, _scope: scope, _cached_at: cached_at });
    }
    store.put({ id: catalogMetaId(scope), cached_at, count: products.length, _scope: scope });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getCachedCatalogMeta(): Promise<{ cached_at: string; count: number } | null> {
  const env = await getOfflineAuthEnvelope();
  const scope = env?.scope || activeScopeMem;
  if (!scope) return null;
  const meta = await idbGet<{ id: string; cached_at: string; count: number }>('catalog', catalogMetaId(scope));
  if (!meta?.cached_at) return null;
  return { cached_at: meta.cached_at, count: meta.count || 0 };
}

export async function getCachedProducts(): Promise<Array<Record<string, unknown>>> {
  const env = await getOfflineAuthEnvelope();
  const scope = env?.scope || activeScopeMem;
  if (!scope) return [];
  const all = await idbGetAll<Record<string, unknown>>('catalog');
  const prefix = `${scope}::`;
  return all.filter((r) => String(r.id).startsWith(prefix) && !String(r.id).endsWith('::__meta__'));
}

export async function enqueueOfflineSale(input: {
  tenant_id: string;
  store_id: string | null;
  store_code: string;
  user_id?: string;
  payload: Record<string, unknown>;
}): Promise<QueuedSale> {
  const envelope = await getOfflineAuthEnvelope();
  if (!isOfflineAuthValid(envelope)) {
    throw new Error('Offline authorization expired — reconnect to continue selling');
  }
  if (envelope && envelope.tenant_id !== input.tenant_id) {
    throw new Error('Offline queue is bound to another workspace — sign in online to continue');
  }
  const client_request_id = newClientRequestId();
  const device_id = getOrCreateDeviceId();
  const user_id = input.user_id || envelope?.user_id || '';
  const scope = partitionScope(input.tenant_id, user_id, input.store_id);
  const created_at = new Date().toISOString();
  const payload = {
    ...input.payload,
    client_request_id,
    offline_sync: true,
    offline_created_at: created_at,
    device_id,
  };
  const sale: QueuedSale = {
    id: crypto.randomUUID(),
    scope,
    client_request_id,
    local_receipt_number: buildLocalReceiptNumber(input.store_code, device_id),
    tenant_id: input.tenant_id,
    store_id: input.store_id,
    user_id,
    device_id,
    payload,
    state: 'pending',
    retry_count: 0,
    last_attempt_at: null,
    next_retry_at: null,
    last_error_code: null,
    last_error_message: null,
    created_at,
    server_sale_id: null,
    server_reference: null,
    conflict: null,
  };
  await idbPut('sync_queue', await persistPayload(sale));
  return sale;
}

export async function listQueuedSales(): Promise<QueuedSale[]> {
  const rows = await idbGetAll<QueuedSale>('sync_queue');
  const out: QueuedSale[] = [];
  for (const row of rows) out.push(await revealPayload(row));
  return out;
}

export async function countPendingSales(): Promise<number> {
  const all = await listQueuedSales();
  const env = await getOfflineAuthEnvelope();
  const scope = env?.scope || activeScopeMem;
  return all.filter(
    (s) =>
      (!scope || s.scope === scope || !s.scope) &&
      (s.state === 'pending' || s.state === 'failed_retryable' || s.state === 'syncing' || s.state === 'conflict')
  ).length;
}

export async function pendingSalesValue(): Promise<number> {
  const all = await listQueuedSales();
  return all
    .filter((s) => s.state === 'pending' || s.state === 'failed_retryable' || s.state === 'syncing' || s.state === 'conflict')
    .reduce((sum, s) => sum + Number((s.payload as { total?: number })?.total || 0), 0);
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

export async function clearOfflineOnLogout(): Promise<void> {
  const pending = await countPendingSales();
  if (pending > 0) {
    await lockExpiredOffline('logout');
    return;
  }
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(['catalog', 'device_state', 'sync_queue'], 'readwrite');
    tx.objectStore('catalog').clear();
    tx.objectStore('device_state').delete('offline_auth');
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function lockExpiredOffline(reason: string): Promise<void> {
  const env = await getOfflineAuthEnvelope();
  if (!env) return;
  env.offline_valid_until = new Date(0).toISOString();
  await idbPut('device_state', { key: 'offline_auth', value: env, lock_reason: reason });
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
    (s) =>
      s.state === 'pending' ||
      s.state === 'failed_retryable' ||
      s.state === 'syncing' ||
      s.state === 'conflict' ||
      s.state === 'expired'
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
  const current = await getOfflineAuthEnvelope();
  if (pkg.envelope && current && pkg.envelope.tenant_id !== current.tenant_id) {
    throw new Error('Recovery package belongs to another workspace');
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
      scope: sale.scope || partitionScope(sale.tenant_id, sale.user_id, sale.store_id),
      state:
        sale.state === 'synced'
          ? 'pending'
          : sale.state === 'syncing'
            ? 'pending'
            : sale.state || 'pending',
      retry_count: Number(sale.retry_count) || 0,
      device_id: sale.device_id || getOrCreateDeviceId(),
    };
    await idbPut('sync_queue', await persistPayload(row));
    byCrid.add(row.client_request_id);
    imported += 1;
  }
  if (pkg.envelope && isOfflineAuthValid(pkg.envelope) && (!current || !isOfflineAuthValid(current))) {
    await idbPut('device_state', { key: 'offline_auth', value: pkg.envelope });
  }
  return { imported, skipped };
}

type ApiFn = (path: string, opts?: RequestInit) => Promise<unknown>;

function conflictDetail(err: { detail?: unknown; message?: string; status?: number }) {
  const detail = err?.detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    return detail as Record<string, unknown>;
  }
  return { message: err?.message || 'Sync conflict', status: err?.status };
}

export async function flushOfflineQueue(
  api: ApiFn
): Promise<{ synced: number; failed: number; conflicts: number; expired: number }> {
  const envelope = await getOfflineAuthEnvelope();
  if (!isOfflineAuthValid(envelope)) {
    const all = await listQueuedSales();
    for (const sale of all) {
      if (sale.state === 'pending' || sale.state === 'failed_retryable' || sale.state === 'syncing') {
        sale.state = 'expired';
        sale.last_error_code = 'OFFLINE_AUTH_EXPIRED';
        sale.last_error_message = 'Offline authorization expired — reconnect to revalidate before restore';
        await idbPut('sync_queue', await persistPayload(sale));
      }
    }
    await lockExpiredOffline('expired');
    return { synced: 0, failed: 0, conflicts: all.filter((s) => s.state === 'conflict').length, expired: 1 };
  }

  const all = await listQueuedSales();
  const pending = all.filter((s) => s.state === 'pending' || s.state === 'failed_retryable');
  let synced = 0;
  let failed = 0;
  let conflicts = 0;
  let expired = 0;
  for (const sale of pending) {
    if (sale.retry_count >= MAX_SYNC_RETRIES) {
      sale.state = 'failed_permanent';
      sale.last_error_code = 'MAX_RETRIES';
      sale.last_error_message = `Stopped after ${MAX_SYNC_RETRIES} attempts — sale was not dropped; export a recovery package`;
      failed += 1;
      await idbPut('sync_queue', await persistPayload(sale));
      continue;
    }
    sale.state = 'syncing';
    sale.last_attempt_at = new Date().toISOString();
    sale.retry_count += 1;
    await idbPut('sync_queue', await persistPayload(sale));
    try {
      const r = (await api('/pos/sales', {
        method: 'POST',
        body: JSON.stringify({
          ...sale.payload,
          offline_sync: true,
          offline_created_at: sale.created_at,
          device_id: sale.device_id,
          client_request_id: sale.client_request_id,
        }),
      })) as { data?: { id?: string; reference?: string } };
      sale.state = 'synced';
      sale.server_sale_id = r.data?.id || null;
      sale.server_reference = r.data?.reference || null;
      sale.last_error_code = null;
      sale.last_error_message = null;
      sale.conflict = null;
      synced += 1;
    } catch (err: unknown) {
      const error = err as { status?: number; message?: string; detail?: unknown };
      const status = error?.status;
      const code =
        error?.detail && typeof error.detail === 'object' && !Array.isArray(error.detail)
          ? String((error.detail as { code?: string }).code || status || 'SYNC_ERROR')
          : String(status || 'SYNC_ERROR');
      if (code === 'OFFLINE_AUTH_EXPIRED' || status === 401) {
        sale.state = 'expired';
        sale.last_error_code = 'OFFLINE_AUTH_EXPIRED';
        sale.last_error_message = error?.message || 'Offline authorization expired';
        expired += 1;
      } else if (status === 409 || code === 'PRICE_CONFLICT' || code === 'STOCK_CONFLICT') {
        sale.state = 'conflict';
        sale.conflict = conflictDetail(error);
        sale.last_error_code = code;
        sale.last_error_message =
          (error.detail && typeof error.detail === 'object' && !Array.isArray(error.detail)
            ? String((error.detail as { message?: string }).message || '')
            : '') || error.message || 'Sync conflict — sale was not dropped';
        conflicts += 1;
      } else {
        const permanent = status === 400 || status === 404 || status === 422;
        sale.state = permanent ? 'failed_permanent' : 'failed_retryable';
        sale.last_error_code = code;
        sale.last_error_message = error?.message || 'Sync failed';
        sale.next_retry_at = permanent
          ? null
          : new Date(Date.now() + Math.min(3600000, 2000 * 2 ** Math.min(sale.retry_count, 8))).toISOString();
        failed += 1;
      }
    }
    await idbPut('sync_queue', await persistPayload(sale));
  }
  await touchLastOnline();
  return { synced, failed, conflicts, expired };
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
