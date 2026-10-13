/**
 * POS offline queue on IndexedDB. PostgreSQL remains authoritative.
 *
 * Authorization: the server issues a device-bound grant (POST /pos/offline/authorize)
 * with an expiry and a per-device stock allocation. The grant only gates *new*
 * offline sales. Syncing queued sales needs an online sign-in, never a fresh grant,
 * and expiry / logout / revalidation / restore never delete queued records.
 *
 * Local data (grant, catalogue, customers, queued payloads, session snapshot) is
 * AES-GCM encrypted with a non-extractable device key. Tokens and passwords are
 * never written here.
 */

import {
  decryptJson,
  decryptWithPassphrase,
  encryptJson,
  encryptWithPassphrase,
  webCryptoAvailable,
  type PassphraseCiphertext,
} from './deviceCrypto';

const DB_NAME = 'ribdigi-pos-offline';
const DB_VERSION = 3;
export const DEFAULT_OFFLINE_AUTH_HOURS = 168;
export const MAX_SYNC_RETRIES = 8;
export const SYNCED_RETENTION_DAYS = 30;
const MAX_BACKOFF_MS = 60 * 60 * 1000;
const MAX_SNAPSHOTS = 10;

export type QueueState = 'pending' | 'syncing' | 'synced' | 'needs_attention' | 'dismissed';
export type RecordKind = 'sale' | 'quote';

export type OfflineAllocation = {
  product_id: string;
  allocated_qty: number;
  sold_qty: number;
};

export type OfflineAuthEnvelope = {
  grant_id: string | null;
  tenant_id: string;
  store_id: string | null;
  user_id: string;
  device_id: string;
  permissions: string[];
  industry?: string | null;
  can_override_allocation?: boolean;
  issued_at: string;
  last_online_at: string;
  offline_valid_until: string;
  offline_auth_hours: number;
  revoked_at?: string | null;
  allocations?: OfflineAllocation[];
  allocations_refreshed_at?: string;
  catalog_version: string;
  application_version: string;
  scope: string;
};

export type QueuedSale = {
  id: string;
  kind: RecordKind;
  scope: string;
  client_request_id: string;
  local_receipt_number: string;
  tenant_id: string;
  store_id: string | null;
  user_id: string;
  device_id: string;
  grant_id: string | null;
  payload: Record<string, unknown>;
  payload_enc?: string;
  state: QueueState;
  retry_count: number;
  last_attempt_at: string | null;
  next_retry_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  created_at: string;
  synced_at?: string | null;
  server_sale_id: string | null;
  server_reference: string | null;
  sync_event_id?: string | null;
  resolution_event_id?: string | null;
  resolution?: string | null;
  allowed_resolutions?: string[];
  conflict?: Record<string, unknown> | null;
};

export type ApiFn = (path: string, opts?: RequestInit) => Promise<unknown>;

let deviceIdMem = '';
let activeScopeMem = '';
let catalogMem: { scope: string; products: Array<Record<string, unknown>>; customers: Array<Record<string, unknown>> } | null =
  null;

export function partitionScope(tenantId: string, userId: string, storeId: string | null): string {
  return `${tenantId || '_'}::${userId || '_'}::${storeId || '_'}`;
}

export function setActiveOfflineScope(scope: string) {
  activeScopeMem = scope;
}

export function hoursUntilValid(hours: number | null | undefined): number {
  const n = Number(hours);
  if (!Number.isFinite(n)) return DEFAULT_OFFLINE_AUTH_HOURS;
  return Math.min(168, Math.max(1, Math.round(n)));
}

/** Gate for *new* offline sales only. Never used to decide whether queued sales may sync. */
export function isOfflineAuthValid(envelope: OfflineAuthEnvelope | null, now = Date.now()): boolean {
  if (!envelope?.offline_valid_until || !envelope.user_id || !envelope.tenant_id) return false;
  if (envelope.revoked_at) return false;
  return new Date(envelope.offline_valid_until).getTime() > now;
}

/** Older builds used conflict, failed_retryable, failed_permanent, and expired. Expired sales were never invalid — they go back to pending. */
export function normalizeLegacyState(state: string | null | undefined): QueueState {
  switch (state) {
    case 'pending':
    case 'syncing':
    case 'synced':
    case 'needs_attention':
    case 'dismissed':
      return state;
    case 'conflict':
    case 'failed_permanent':
      return 'needs_attention';
    case 'expired':
    case 'failed_retryable':
    default:
      return 'pending';
  }
}

export function isUnsynced(state: QueueState): boolean {
  return state === 'pending' || state === 'syncing' || state === 'needs_attention';
}

export function backoffMs(retryCount: number): number {
  return Math.min(MAX_BACKOFF_MS, 2000 * 2 ** Math.min(Math.max(0, retryCount), 11));
}

// ── IndexedDB ──────────────────────────────────────────────────────────────

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (event) => {
      // Upgrades only add stores/indexes. The sync_queue store is never cleared or recreated.
      const db = req.result;
      const oldVersion = event.oldVersion || 0;
      if (!db.objectStoreNames.contains('catalog')) {
        db.createObjectStore('catalog', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('sync_queue')) {
        const q = db.createObjectStore('sync_queue', { keyPath: 'id' });
        q.createIndex('state', 'state', { unique: false });
      }
      if (!db.objectStoreNames.contains('device_state')) {
        db.createObjectStore('device_state', { keyPath: 'key' });
      }
      if (!db.objectStoreNames.contains('sync_log')) {
        db.createObjectStore('sync_log', { keyPath: 'id', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains('queue_snapshots')) {
        db.createObjectStore('queue_snapshots', { keyPath: 'id' });
      }
      const tx = req.transaction;
      if (tx && oldVersion < 3) {
        const q = tx.objectStore('sync_queue');
        if (!q.indexNames.contains('client_request_id')) {
          q.createIndex('client_request_id', 'client_request_id', { unique: false });
        }
        if (!q.indexNames.contains('scope')) {
          q.createIndex('scope', 'scope', { unique: false });
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
    tx.oncomplete = () => {
      db.close();
      resolve(req.result as T | undefined);
    };
    tx.onerror = () => {
      db.close();
      reject(req.error || tx.error);
    };
  });
}

async function idbPut(store: string, value: unknown): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite');
    tx.objectStore(store).put(value);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

async function idbDelete(store: string, key: IDBValidKey): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite');
    tx.objectStore(store).delete(key);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

async function idbGetAll<T>(store: string): Promise<T[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readonly');
    const req = tx.objectStore(store).getAll();
    tx.oncomplete = () => {
      db.close();
      resolve((req.result || []) as T[]);
    };
    tx.onerror = () => {
      db.close();
      reject(req.error || tx.error);
    };
  });
}

function requireCrypto() {
  if (!webCryptoAvailable()) {
    throw new Error('This browser cannot encrypt offline data. Use a current browser over HTTPS to sell offline.');
  }
}

async function putSecret(key: string, value: unknown, extra?: Record<string, unknown>): Promise<void> {
  requireCrypto();
  await idbPut('device_state', { key, enc: await encryptJson(value), ...(extra || {}) });
}

async function getSecret<T>(key: string): Promise<T | null> {
  const row = await idbGet<{ key: string; enc?: string; value?: T }>('device_state', key);
  if (!row) return null;
  if (row.enc) {
    try {
      return await decryptJson<T>(row.enc);
    } catch {
      return null;
    }
  }
  return null;
}

async function getPlain<T>(key: string): Promise<T | null> {
  const row = await idbGet<{ key: string; value?: T }>('device_state', key);
  return (row?.value as T) ?? null;
}

async function putPlain(key: string, value: unknown): Promise<void> {
  await idbPut('device_state', { key, value });
}

// ── Device identity / receipts ─────────────────────────────────────────────

export function getOrCreateDeviceId(): string {
  if (deviceIdMem && deviceIdMem.length >= 8) return deviceIdMem;
  if (typeof localStorage !== 'undefined') {
    const legacy = (localStorage.getItem('pos_device_id') || '').trim();
    if (legacy.length >= 8) {
      deviceIdMem = legacy;
      localStorage.removeItem('pos_device_id');
      void putPlain('device_id', deviceIdMem).catch(() => undefined);
      return deviceIdMem;
    }
  }
  deviceIdMem = `dev-${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`;
  void putPlain('device_id', deviceIdMem).catch(() => undefined);
  return deviceIdMem;
}

export async function hydrateDeviceId(): Promise<string> {
  const stored = await getPlain<string>('device_id').catch(() => null);
  if (stored && stored.length >= 8) {
    deviceIdMem = stored;
    return deviceIdMem;
  }
  return getOrCreateDeviceId();
}

export function newClientRequestId(): string {
  return `cr-${crypto.randomUUID().replace(/-/g, '')}`;
}

export function buildLocalReceiptNumber(storeCode: string, deviceId: string, seq?: number): string {
  const day = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  const n = seq ?? Date.now() % 1000000;
  const store = (storeCode || 'STORE').replace(/[^A-Za-z0-9]/g, '').slice(0, 12) || 'STORE';
  const dev = (deviceId || 'POS').replace(/[^A-Za-z0-9]/g, '').slice(-6) || 'POS';
  return `OFF-${store}-${dev}-${day}-${String(n).padStart(4, '0')}`;
}

async function nextLocalReceiptNumber(storeCode: string, deviceId: string): Promise<string> {
  const day = new Date().toISOString().slice(0, 10);
  const key = `receipt_seq:${day}`;
  const current = Number(await getPlain<number>(key).catch(() => 0)) || 0;
  const next = current + 1;
  await putPlain(key, next);
  return buildLocalReceiptNumber(storeCode, deviceId, next);
}

// ── Grant envelope ─────────────────────────────────────────────────────────

type ServerGrant = {
  grant_id: string;
  tenant_id: string;
  user_id: string;
  device_id: string;
  store_id: string | null;
  industry?: string | null;
  allowed_actions?: string[];
  can_override_allocation?: boolean;
  issued_at: string;
  valid_until: string;
  revoked_at?: string | null;
  offline_auth_hours?: number;
  allocations?: OfflineAllocation[];
};

export function envelopeFromGrant(grant: ServerGrant): OfflineAuthEnvelope {
  const now = new Date().toISOString();
  return {
    grant_id: grant.grant_id,
    tenant_id: grant.tenant_id,
    store_id: grant.store_id,
    user_id: grant.user_id,
    device_id: grant.device_id,
    permissions: grant.allowed_actions || ['pos_sale'],
    industry: grant.industry || null,
    can_override_allocation: Boolean(grant.can_override_allocation),
    issued_at: grant.issued_at,
    last_online_at: now,
    offline_valid_until: grant.valid_until,
    offline_auth_hours: hoursUntilValid(grant.offline_auth_hours),
    revoked_at: grant.revoked_at || null,
    allocations: (grant.allocations || []).map((a) => ({
      product_id: String(a.product_id),
      allocated_qty: Number(a.allocated_qty) || 0,
      sold_qty: Number(a.sold_qty) || 0,
    })),
    allocations_refreshed_at: now,
    catalog_version: now,
    application_version: 'web',
    scope: partitionScope(grant.tenant_id, grant.user_id, grant.store_id),
  };
}

export async function saveOfflineGrant(envelope: OfflineAuthEnvelope): Promise<void> {
  setActiveOfflineScope(envelope.scope);
  await putSecret('offline_auth', envelope);
}

export async function getOfflineAuthEnvelope(): Promise<OfflineAuthEnvelope | null> {
  const env = await getSecret<OfflineAuthEnvelope>('offline_auth');
  if (env?.scope) activeScopeMem = env.scope;
  return env;
}

export async function clearOfflineAuthEnvelope(): Promise<void> {
  await idbDelete('device_state', 'offline_auth');
}

/** Records that the device reached the server. Never extends the grant. */
export async function touchLastOnline(): Promise<void> {
  await putPlain('last_online_at', new Date().toISOString()).catch(() => undefined);
}

export async function getLastSyncAt(): Promise<string | null> {
  return getPlain<string>('last_sync_at').catch(() => null);
}

async function setLastSyncAt(iso: string): Promise<void> {
  await putPlain('last_sync_at', iso);
}

// ── Encrypted catalogue / customers / session snapshot ─────────────────────

function catalogKey(scope: string) {
  return `${scope}::__catalog__`;
}

export async function cacheOfflineCatalog(input: {
  scope: string;
  products: Array<Record<string, unknown>>;
  customers: Array<Record<string, unknown>>;
  generated_at?: string;
}): Promise<void> {
  requireCrypto();
  const cached_at = input.generated_at || new Date().toISOString();
  const enc = await encryptJson({ products: input.products, customers: input.customers });
  await idbPut('catalog', {
    id: catalogKey(input.scope),
    _scope: input.scope,
    enc,
    cached_at,
    count: input.products.length,
    customer_count: input.customers.length,
  });
  catalogMem = { scope: input.scope, products: input.products, customers: input.customers };
}

async function loadCatalog(): Promise<typeof catalogMem> {
  const env = await getOfflineAuthEnvelope();
  const scope = env?.scope || activeScopeMem;
  if (!scope) return null;
  if (catalogMem && catalogMem.scope === scope) return catalogMem;
  const row = await idbGet<{ id: string; enc?: string }>('catalog', catalogKey(scope));
  if (!row?.enc) return null;
  try {
    const data = await decryptJson<{ products: Array<Record<string, unknown>>; customers: Array<Record<string, unknown>> }>(
      row.enc
    );
    catalogMem = { scope, products: data.products || [], customers: data.customers || [] };
    return catalogMem;
  } catch {
    return null;
  }
}

export async function getCachedCatalogMeta(): Promise<{ cached_at: string; count: number } | null> {
  const env = await getOfflineAuthEnvelope();
  const scope = env?.scope || activeScopeMem;
  if (!scope) return null;
  const meta = await idbGet<{ id: string; cached_at: string; count: number }>('catalog', catalogKey(scope));
  if (!meta?.cached_at) return null;
  return { cached_at: meta.cached_at, count: meta.count || 0 };
}

export async function getCachedProducts(): Promise<Array<Record<string, unknown>>> {
  return (await loadCatalog())?.products || [];
}

export async function getCachedCustomers(): Promise<Array<Record<string, unknown>>> {
  return (await loadCatalog())?.customers || [];
}

export function searchCachedProducts(
  products: Array<Record<string, unknown>>,
  query: string,
  opts?: { barcode?: boolean }
): Array<Record<string, unknown>> {
  const q = query.trim().toLowerCase();
  if (!q) return products.slice(0, 48);
  if (opts?.barcode) {
    const exact = products.filter(
      (p) => String(p.barcode || '').toLowerCase() === q || String(p.sku || '').toLowerCase() === q
    );
    if (exact.length) return exact;
  }
  return products
    .filter(
      (p) =>
        String(p.name || '').toLowerCase().includes(q) ||
        String(p.sku || '').toLowerCase().includes(q) ||
        String(p.barcode || '').toLowerCase().includes(q)
    )
    .slice(0, 48);
}

export async function cacheSnapshot(key: 'session' | 'me' | 'stores', value: unknown): Promise<void> {
  if (!webCryptoAvailable()) return;
  await putSecret(`snapshot:${key}`, value);
}

export async function getSnapshot<T>(key: 'session' | 'me' | 'stores'): Promise<T | null> {
  return getSecret<T>(`snapshot:${key}`);
}

// ── Queue persistence ──────────────────────────────────────────────────────

async function persistRecord(rec: QueuedSale): Promise<void> {
  requireCrypto();
  const { payload, ...rest } = rec;
  const payload_enc = await encryptJson(payload);
  await idbPut('sync_queue', { ...rest, payload: { offline_encrypted: true }, payload_enc });
}

async function revealRecord(raw: QueuedSale): Promise<QueuedSale> {
  let rec: QueuedSale = {
    ...raw,
    kind: raw.kind || 'sale',
    grant_id: raw.grant_id ?? null,
    state: normalizeLegacyState(raw.state as string),
  };
  if (raw.payload_enc) {
    try {
      rec = { ...rec, payload: await decryptJson<Record<string, unknown>>(raw.payload_enc) };
    } catch {
      rec = { ...rec, payload: { offline_encrypted: true, undecryptable: true } };
    }
  }
  return rec;
}

export async function listQueuedSales(): Promise<QueuedSale[]> {
  const rows = await idbGetAll<QueuedSale>('sync_queue');
  const out: QueuedSale[] = [];
  for (const row of rows) out.push(await revealRecord(row));
  out.sort((a, b) => a.created_at.localeCompare(b.created_at));
  return out;
}

/** Older builds stored `expired` for sales they refused to sync. Put them back in the queue. */
export async function migrateLegacyQueueStates(): Promise<number> {
  const rows = await idbGetAll<QueuedSale>('sync_queue');
  let changed = 0;
  for (const row of rows) {
    const next = normalizeLegacyState(row.state as string);
    const stuckSyncing = row.state === 'syncing';
    if (next !== row.state || stuckSyncing || !row.kind) {
      const rec = await revealRecord(row);
      rec.state = stuckSyncing ? 'pending' : next;
      if ((row.state as string) === 'expired') {
        rec.last_error_code = null;
        rec.last_error_message = null;
        rec.next_retry_at = null;
      }
      await persistRecord(rec);
      changed += 1;
    }
  }
  return changed;
}

function recordQty(rec: QueuedSale): Record<string, number> {
  const out: Record<string, number> = {};
  if (rec.kind !== 'sale') return out;
  const items = (rec.payload?.items as Array<{ product_id?: string; quantity?: number }>) || [];
  for (const item of items) {
    const pid = String(item.product_id || '');
    if (!pid) continue;
    out[pid] = (out[pid] || 0) + (Number(item.quantity) || 0);
  }
  return out;
}

export async function countPendingSales(): Promise<number> {
  const all = await listQueuedSales();
  return all.filter((s) => isUnsynced(s.state)).length;
}

export async function pendingSalesValue(): Promise<number> {
  const all = await listQueuedSales();
  return all
    .filter((s) => s.kind === 'sale' && isUnsynced(s.state))
    .reduce((sum, s) => sum + Number((s.payload as { total?: number })?.total || 0), 0);
}

export type QueueSummary = {
  pending: number;
  syncing: number;
  needs_attention: number;
  synced: number;
  dismissed: number;
  other_users_pending: number;
  pending_value: number;
};

export async function queueSummary(userId?: string): Promise<QueueSummary> {
  const all = await listQueuedSales();
  const s: QueueSummary = {
    pending: 0,
    syncing: 0,
    needs_attention: 0,
    synced: 0,
    dismissed: 0,
    other_users_pending: 0,
    pending_value: 0,
  };
  for (const r of all) {
    s[r.state] += 1;
    if (isUnsynced(r.state)) {
      if (userId && r.user_id && r.user_id !== userId) s.other_users_pending += 1;
      if (r.kind === 'sale') s.pending_value += Number((r.payload as { total?: number })?.total || 0);
    }
  }
  s.pending_value = Math.round(s.pending_value * 100) / 100;
  return s;
}

export async function unsyncedQtyByProduct(tenantId: string): Promise<Record<string, number>> {
  const out: Record<string, number> = {};
  for (const rec of await listQueuedSales()) {
    if (rec.tenant_id !== tenantId || !isUnsynced(rec.state)) continue;
    for (const [pid, qty] of Object.entries(recordQty(rec))) out[pid] = (out[pid] || 0) + qty;
  }
  return out;
}

/** Remaining offline allocation for a product on this device's current grant. */
export function allocationRemaining(
  envelope: OfflineAuthEnvelope | null,
  records: QueuedSale[],
  productId: string
): number {
  if (!envelope?.grant_id) return 0;
  const alloc = (envelope.allocations || []).find((a) => a.product_id === productId);
  if (!alloc) return 0;
  const refreshed = envelope.allocations_refreshed_at || envelope.issued_at;
  let used = Number(alloc.sold_qty) || 0;
  for (const rec of records) {
    if (rec.grant_id !== envelope.grant_id || rec.state === 'dismissed') continue;
    const counted =
      isUnsynced(rec.state) || (rec.state === 'synced' && (rec.synced_at || '') > (refreshed || ''));
    if (!counted) continue;
    used += recordQty(rec)[productId] || 0;
  }
  return Math.max(0, Math.round(((Number(alloc.allocated_qty) || 0) - used) * 1000) / 1000);
}

export async function allocationRemainingFor(productIds: string[]): Promise<Record<string, number>> {
  const env = await getOfflineAuthEnvelope();
  const records = await listQueuedSales();
  const out: Record<string, number> = {};
  for (const pid of productIds) out[pid] = allocationRemaining(env, records, pid);
  return out;
}

function assertWritableGrant(envelope: OfflineAuthEnvelope | null, tenantId: string, userId: string) {
  if (!envelope?.grant_id) {
    throw new Error('This device has no offline access yet. Revalidate offline access while online.');
  }
  if (!isOfflineAuthValid(envelope)) {
    throw new Error(
      'Offline access on this device has expired. New offline sales are blocked; queued sales are kept and will sync once you are online and signed in.'
    );
  }
  if (envelope.tenant_id !== tenantId || (userId && envelope.user_id !== userId)) {
    throw new Error('Offline access on this device belongs to another account. Sign in online to continue.');
  }
}

export async function enqueueOfflineSale(input: {
  tenant_id: string;
  store_id: string | null;
  store_code: string;
  user_id?: string;
  payload: Record<string, unknown>;
  allocation_override?: boolean;
}): Promise<QueuedSale> {
  requireCrypto();
  const envelope = await getOfflineAuthEnvelope();
  const user_id = input.user_id || envelope?.user_id || '';
  assertWritableGrant(envelope, input.tenant_id, user_id);
  const env = envelope as OfflineAuthEnvelope;
  if (!env.permissions.includes('pos_sale')) {
    throw new Error('Your offline access does not include POS sales.');
  }
  const draft: QueuedSale = {
    id: crypto.randomUUID(),
    kind: 'sale',
    scope: partitionScope(input.tenant_id, user_id, input.store_id),
    client_request_id: newClientRequestId(),
    local_receipt_number: '',
    tenant_id: input.tenant_id,
    store_id: input.store_id,
    user_id,
    device_id: getOrCreateDeviceId(),
    grant_id: env.grant_id,
    payload: input.payload,
    state: 'pending',
    retry_count: 0,
    last_attempt_at: null,
    next_retry_at: null,
    last_error_code: null,
    last_error_message: null,
    created_at: new Date().toISOString(),
    synced_at: null,
    server_sale_id: null,
    server_reference: null,
    sync_event_id: null,
    resolution_event_id: null,
    conflict: null,
  };
  const records = await listQueuedSales();
  const over: string[] = [];
  for (const [pid, qty] of Object.entries(recordQty(draft))) {
    if (qty > allocationRemaining(env, records, pid) + 1e-9) over.push(pid);
  }
  const override = Boolean(input.allocation_override);
  if (over.length && !(override && env.can_override_allocation)) {
    throw new Error(
      override
        ? 'Only a manager can sell beyond this device’s offline stock allocation.'
        : 'This sale is more than this device’s offline stock allocation. Reduce the quantity or ask a manager to override.'
    );
  }
  draft.local_receipt_number = await nextLocalReceiptNumber(input.store_code, draft.device_id);
  draft.payload = {
    ...input.payload,
    client_request_id: draft.client_request_id,
    offline_sync: true,
    offline_created_at: draft.created_at,
    device_id: draft.device_id,
    offline_grant_id: env.grant_id,
    local_receipt_number: draft.local_receipt_number,
    allocation_override: Boolean(over.length && override),
  };
  await persistRecord(draft);
  return draft;
}

export async function enqueueOfflineQuote(input: {
  tenant_id: string;
  store_id: string | null;
  store_code: string;
  user_id?: string;
  payload: Record<string, unknown>;
}): Promise<QueuedSale> {
  requireCrypto();
  const envelope = await getOfflineAuthEnvelope();
  const user_id = input.user_id || envelope?.user_id || '';
  assertWritableGrant(envelope, input.tenant_id, user_id);
  const env = envelope as OfflineAuthEnvelope;
  if (!env.permissions.includes('quote_capture')) {
    throw new Error('Your offline access does not include quotes.');
  }
  const created_at = new Date().toISOString();
  const client_request_id = newClientRequestId();
  const rec: QueuedSale = {
    id: crypto.randomUUID(),
    kind: 'quote',
    scope: partitionScope(input.tenant_id, user_id, input.store_id),
    client_request_id,
    local_receipt_number: (await nextLocalReceiptNumber(input.store_code, getOrCreateDeviceId())).replace(
      /^OFF-/,
      'OFQ-'
    ),
    tenant_id: input.tenant_id,
    store_id: input.store_id,
    user_id,
    device_id: getOrCreateDeviceId(),
    grant_id: env.grant_id,
    payload: { ...input.payload, client_request_id },
    state: 'pending',
    retry_count: 0,
    last_attempt_at: null,
    next_retry_at: null,
    last_error_code: null,
    last_error_message: null,
    created_at,
    synced_at: null,
    server_sale_id: null,
    server_reference: null,
  };
  await persistRecord(rec);
  return rec;
}

// ── Sync ───────────────────────────────────────────────────────────────────

type ApiError = { status?: number; message?: string; detail?: unknown };

function errorDetail(err: ApiError): Record<string, unknown> {
  const detail = err?.detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) return detail as Record<string, unknown>;
  return { message: typeof detail === 'string' ? detail : err?.message || 'Sync failed' };
}

function requestBody(rec: QueuedSale): Record<string, unknown> {
  if (rec.kind === 'quote') {
    const quote: Record<string, unknown> = { ...rec.payload, client_request_id: rec.client_request_id };
    delete quote.total;
    return quote;
  }
  const body: Record<string, unknown> = {
    ...rec.payload,
    offline_sync: true,
    offline_created_at: rec.created_at,
    device_id: rec.device_id,
    client_request_id: rec.client_request_id,
    local_receipt_number: rec.local_receipt_number,
  };
  if (rec.grant_id) body.offline_grant_id = rec.grant_id;
  else delete body.offline_grant_id;
  if (rec.resolution_event_id) body.resolution_event_id = rec.resolution_event_id;
  delete body.total;
  return body;
}

export type FlushResult = {
  synced: number;
  needsAttention: number;
  retrying: number;
  authRequired: boolean;
  otherUsers: number;
};

/**
 * Send queued records for the signed-in user. Does not depend on the offline grant:
 * an online-authenticated user can always sync what was recorded on this device.
 */
let flushDepth = 0;

export async function flushOfflineQueue(
  api: ApiFn,
  ctx: { tenant_id: string; user_id: string; force?: boolean }
): Promise<FlushResult> {
  if (
    flushDepth === 0 &&
    typeof navigator !== 'undefined' &&
    typeof navigator.locks?.request === 'function'
  ) {
    return navigator.locks.request('ribdigi-offline-flush', () => {
      flushDepth += 1;
      return flushOfflineQueue(api, ctx).finally(() => {
        flushDepth -= 1;
      });
    });
  }
  const result: FlushResult = { synced: 0, needsAttention: 0, retrying: 0, authRequired: false, otherUsers: 0 };
  if (!ctx.tenant_id || !ctx.user_id) return result;
  await migrateLegacyQueueStates();
  const now = Date.now();
  const all = await listQueuedSales();
  for (const rec of all) {
    if (!isUnsynced(rec.state)) continue;
    if (rec.tenant_id !== ctx.tenant_id || (rec.user_id && rec.user_id !== ctx.user_id)) {
      result.otherUsers += 1;
      continue;
    }
    if (rec.state === 'needs_attention' && !ctx.force) continue;
    if (!ctx.force && rec.next_retry_at && new Date(rec.next_retry_at).getTime() > now) {
      result.retrying += 1;
      continue;
    }
    rec.state = 'syncing';
    rec.last_attempt_at = new Date().toISOString();
    rec.retry_count += 1;
    await persistRecord(rec);
    try {
      const path = rec.kind === 'quote' ? '/sales/quotations' : '/pos/sales';
      const r = (await api(path, { method: 'POST', body: JSON.stringify(requestBody(rec)) })) as {
        data?: { id?: string; reference?: string; quotation_number?: string };
      };
      rec.state = 'synced';
      rec.synced_at = new Date().toISOString();
      rec.server_sale_id = r?.data?.id || null;
      rec.server_reference = r?.data?.reference || r?.data?.quotation_number || null;
      rec.last_error_code = null;
      rec.last_error_message = null;
      rec.next_retry_at = null;
      rec.conflict = null;
      result.synced += 1;
    } catch (err: unknown) {
      const e = err as ApiError;
      const status = Number(e?.status) || 0;
      const detail = errorDetail(e);
      const code = String(detail.code || (status ? `HTTP_${status}` : 'NETWORK'));
      if (status === 401) {
        rec.state = 'pending';
        rec.retry_count = Math.max(0, rec.retry_count - 1);
        rec.last_error_code = 'SIGN_IN_REQUIRED';
        rec.last_error_message = 'Sign in again to sync. The sale is kept on this device.';
        await persistRecord(rec);
        result.authRequired = true;
        break;
      }
      if (!status || status >= 500 || status === 429 || status === 408) {
        rec.state = rec.retry_count >= MAX_SYNC_RETRIES ? 'needs_attention' : 'pending';
        rec.next_retry_at = new Date(Date.now() + backoffMs(rec.retry_count)).toISOString();
        rec.last_error_code = code;
        rec.last_error_message =
          rec.state === 'needs_attention'
            ? `Still failing after ${rec.retry_count} attempts. The sale is kept; retry when the server is reachable.`
            : String(detail.message || e?.message || 'Server not reachable — will retry');
        if (rec.state === 'needs_attention') result.needsAttention += 1;
        else result.retrying += 1;
      } else {
        rec.state = 'needs_attention';
        rec.last_error_code = code;
        rec.last_error_message = String(detail.message || e?.message || 'Needs review — the sale was kept');
        rec.sync_event_id = (detail.sync_event_id as string) || rec.sync_event_id || null;
        rec.conflict = detail;
        rec.next_retry_at = null;
        result.needsAttention += 1;
      }
    }
    await persistRecord(rec);
  }
  if (result.synced > 0) await setLastSyncAt(new Date().toISOString());
  await touchLastOnline();
  await pruneSyncedRecords(SYNCED_RETENTION_DAYS);
  return result;
}

type StatusEvent = {
  id: string;
  client_request_id: string | null;
  resolution: string | null;
  resolution_note?: string | null;
  allowed_resolutions?: string[];
  sale_id?: string | null;
};

/** Pull grant/allocation state and manager resolutions for records needing attention. */
export async function refreshOfflineStatus(
  api: ApiFn,
  ctx: { tenant_id: string; user_id: string }
): Promise<{ grant_active: boolean; other_devices_pending: number; provisional: boolean } | null> {
  const records = (await listQueuedSales()).filter(
    (r) => r.tenant_id === ctx.tenant_id && r.user_id === ctx.user_id && r.state === 'needs_attention'
  );
  const r = (await api('/pos/offline/status', {
    method: 'POST',
    body: JSON.stringify({
      device_id: getOrCreateDeviceId(),
      client_request_ids: records.map((x) => x.client_request_id).slice(0, 500),
    }),
  })) as {
    data?: {
      grant?: ServerGrant | null;
      grant_active?: boolean;
      other_devices_pending?: number;
      provisional?: boolean;
      device_blocked?: boolean;
      events?: StatusEvent[];
    };
  };
  const data = r?.data || {};
  const env = await getOfflineAuthEnvelope();
  if (env && data.grant && data.grant.grant_id === env.grant_id) {
    env.revoked_at = data.grant.revoked_at || null;
    env.offline_valid_until = data.grant.valid_until;
    env.allocations = (data.grant.allocations || []).map((a) => ({
      product_id: String(a.product_id),
      allocated_qty: Number(a.allocated_qty) || 0,
      sold_qty: Number(a.sold_qty) || 0,
    }));
    env.allocations_refreshed_at = new Date().toISOString();
    env.last_online_at = env.allocations_refreshed_at;
    await saveOfflineGrant(env);
  } else if (env && data.grant && data.grant.grant_id !== env.grant_id) {
    env.revoked_at = env.revoked_at || new Date().toISOString();
    await saveOfflineGrant(env);
  }
  const byCrid = new Map<string, StatusEvent[]>();
  for (const ev of data.events || []) {
    if (!ev.client_request_id) continue;
    const list = byCrid.get(ev.client_request_id) || [];
    list.push(ev);
    byCrid.set(ev.client_request_id, list);
  }
  for (const rec of records) {
    const events = byCrid.get(rec.client_request_id) || [];
    const dismissed = events.find((e) => e.resolution === 'dismiss');
    const approved = events.find((e) => e.resolution && e.resolution.startsWith('approve_'));
    const open = events.find((e) => !e.resolution);
    if (dismissed) {
      rec.state = 'dismissed';
      rec.resolution = 'dismiss';
      rec.last_error_message = `Dismissed by a manager: ${dismissed.resolution_note || 'no note'}. Kept on record, not posted.`;
    } else if (approved) {
      rec.state = 'pending';
      rec.resolution = approved.resolution;
      rec.resolution_event_id = approved.id;
      rec.next_retry_at = null;
      rec.last_error_message = `Approved by a manager (${approved.resolution}). Syncing…`;
    } else if (open) {
      rec.sync_event_id = open.id;
      rec.allowed_resolutions = open.allowed_resolutions || [];
    } else {
      continue;
    }
    await persistRecord(rec);
  }
  return {
    grant_active: Boolean(data.grant_active),
    other_devices_pending: Number(data.other_devices_pending) || 0,
    provisional: Boolean(data.provisional),
  };
}

/** Online-only: revalidate user/tenant/permissions/device and refresh the encrypted catalogue. */
export async function revalidateOfflineAccess(
  api: ApiFn,
  ctx: { tenant_id: string; user_id: string; store_id: string | null; label?: string }
): Promise<{ envelope: OfflineAuthEnvelope; products: number; customers: number }> {
  requireCrypto();
  const device_id = await hydrateDeviceId();
  const pending_items = await unsyncedQtyByProduct(ctx.tenant_id);
  const summary = await queueSummary(ctx.user_id);
  const auth = (await api('/pos/offline/authorize', {
    method: 'POST',
    body: JSON.stringify({
      device_id,
      store_id: ctx.store_id,
      pending_items,
      label: ctx.label || null,
      app_version: 'web',
      pending_queue_count: summary.pending + summary.syncing + summary.needs_attention,
    }),
  })) as { data: ServerGrant };
  const envelope = envelopeFromGrant(auth.data);
  if (envelope.tenant_id !== ctx.tenant_id || envelope.user_id !== ctx.user_id) {
    throw new Error('Offline access was issued for a different account');
  }
  const params = new URLSearchParams();
  if (ctx.store_id) params.set('store_id', ctx.store_id);
  const cat = (await api(`/pos/offline/catalog?${params.toString()}`)) as {
    data: { products: Array<Record<string, unknown>>; customers: Array<Record<string, unknown>>; generated_at?: string };
  };
  await saveOfflineGrant(envelope);
  await cacheOfflineCatalog({
    scope: envelope.scope,
    products: cat.data.products || [],
    customers: cat.data.customers || [],
    generated_at: cat.data.generated_at,
  });
  await touchLastOnline();
  return { envelope, products: (cat.data.products || []).length, customers: (cat.data.customers || []).length };
}

export async function resolveRecordOnServer(
  api: ApiFn,
  rec: QueuedSale,
  action: string,
  note: string
): Promise<void> {
  if (!rec.sync_event_id) throw new Error('This record has no server conflict to resolve yet. Sync it first.');
  await api(`/pos/offline/conflicts/${rec.sync_event_id}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ action, note }),
  });
  const fresh = (await listQueuedSales()).find((r) => r.id === rec.id);
  if (!fresh) return;
  if (action === 'dismiss') {
    fresh.state = 'dismissed';
    fresh.resolution = 'dismiss';
    fresh.last_error_message = `Dismissed: ${note}. Kept on record, not posted.`;
  } else {
    fresh.state = 'pending';
    fresh.resolution = action;
    fresh.resolution_event_id = rec.sync_event_id;
    fresh.next_retry_at = null;
  }
  await persistRecord(fresh);
}

export async function retryRecord(id: string): Promise<void> {
  const rec = (await listQueuedSales()).find((r) => r.id === id);
  if (!rec || rec.state === 'synced' || rec.state === 'dismissed') return;
  rec.state = 'pending';
  rec.next_retry_at = null;
  await persistRecord(rec);
}

/** After a server restore, re-send synced records; idempotent keys prevent duplicates. */
export async function resendSyncedAfterRestore(tenantId: string): Promise<number> {
  let n = 0;
  for (const rec of await listQueuedSales()) {
    if (rec.tenant_id !== tenantId || rec.state !== 'synced') continue;
    rec.state = 'pending';
    rec.next_retry_at = null;
    rec.last_error_message = 'Re-sending after a server restore (no duplicates: same request id).';
    await persistRecord(rec);
    n += 1;
  }
  return n;
}

export async function pruneSyncedRecords(days: number): Promise<number> {
  const cutoff = Date.now() - days * 86400000;
  let n = 0;
  for (const row of await idbGetAll<QueuedSale>('sync_queue')) {
    if (row.state !== 'synced' || !row.synced_at) continue;
    if (new Date(row.synced_at).getTime() < cutoff) {
      await idbDelete('sync_queue', row.id);
      n += 1;
    }
  }
  return n;
}

// ── Safety copies / recovery file ──────────────────────────────────────────

export async function snapshotQueue(reason: string): Promise<string> {
  requireCrypto();
  const rows = await idbGetAll<QueuedSale>('sync_queue');
  const id = `${new Date().toISOString()}-${Math.random().toString(36).slice(2, 8)}`;
  await idbPut('queue_snapshots', {
    id,
    reason,
    created_at: new Date().toISOString(),
    count: rows.length,
    enc: await encryptJson(rows),
  });
  const snaps = (await idbGetAll<{ id: string }>('queue_snapshots')).sort((a, b) => a.id.localeCompare(b.id));
  for (const old of snaps.slice(0, Math.max(0, snaps.length - MAX_SNAPSHOTS))) {
    await idbDelete('queue_snapshots', old.id);
  }
  return id;
}

export async function listQueueSnapshots(): Promise<Array<{ id: string; reason: string; created_at: string; count: number }>> {
  const snaps = await idbGetAll<{ id: string; reason: string; created_at: string; count: number }>('queue_snapshots');
  return snaps
    .map(({ id, reason, created_at, count }) => ({ id, reason, created_at, count }))
    .sort((a, b) => b.id.localeCompare(a.id));
}

async function mergeRecords(rows: QueuedSale[]): Promise<{ imported: number; skipped: number }> {
  const existing = new Set((await idbGetAll<QueuedSale>('sync_queue')).map((r) => r.client_request_id));
  let imported = 0;
  let skipped = 0;
  for (const raw of rows) {
    if (!raw?.client_request_id || existing.has(raw.client_request_id)) {
      skipped += 1;
      continue;
    }
    const rec = raw.payload_enc ? await revealRecord(raw) : { ...raw };
    if (!rec.payload || (rec.payload as { undecryptable?: boolean }).undecryptable) {
      skipped += 1;
      continue;
    }
    const state = normalizeLegacyState(rec.state as string);
    await persistRecord({
      ...rec,
      id: rec.id || crypto.randomUUID(),
      kind: rec.kind || 'sale',
      grant_id: rec.grant_id ?? (rec.payload?.offline_grant_id as string) ?? null,
      scope: rec.scope || partitionScope(rec.tenant_id, rec.user_id, rec.store_id),
      state: state === 'syncing' ? 'pending' : state,
      retry_count: Number(rec.retry_count) || 0,
      device_id: rec.device_id || getOrCreateDeviceId(),
    });
    existing.add(rec.client_request_id);
    imported += 1;
  }
  return { imported, skipped };
}

export async function restoreQueueSnapshot(id: string): Promise<{ imported: number; skipped: number }> {
  const snap = await idbGet<{ id: string; enc: string }>('queue_snapshots', id);
  if (!snap?.enc) throw new Error('Safety copy not found');
  const rows = await decryptJson<QueuedSale[]>(snap.enc);
  return mergeRecords(rows);
}

export type RecoveryPackageV2 = {
  version: 2;
  kind: 'ribdigi-pos-recovery';
  exported_at: string;
  device_id: string;
  record_count: number;
  /** Never includes tokens, passwords, or the device key. Payload is passphrase-encrypted. */
  secrets_included: false;
  encrypted: PassphraseCiphertext;
};

type LegacyRecoveryPackage = {
  version: 1;
  kind: 'ribdigi-pos-recovery';
  pending: QueuedSale[];
  envelope?: OfflineAuthEnvelope | null;
};

export async function buildRecoveryPackage(passphrase: string): Promise<RecoveryPackageV2> {
  const records = await listQueuedSales();
  return {
    version: 2,
    kind: 'ribdigi-pos-recovery',
    exported_at: new Date().toISOString(),
    device_id: getOrCreateDeviceId(),
    record_count: records.length,
    secrets_included: false,
    encrypted: await encryptWithPassphrase({ records }, passphrase),
  };
}

export async function downloadRecoveryPackage(passphrase: string): Promise<RecoveryPackageV2> {
  const pkg = await buildRecoveryPackage(passphrase);
  const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const day = new Date().toISOString().slice(0, 10);
  a.href = url;
  a.download = `ribdigi-pos-backup-${pkg.device_id}-${day}.json`;
  a.click();
  URL.revokeObjectURL(url);
  return pkg;
}

/**
 * Merge records from a backup file. Takes a safety copy first and never overwrites
 * or removes records already on this device. This is not the sync path.
 */
export async function importRecoveryPackage(
  raw: unknown,
  opts: { tenant_id: string; passphrase?: string }
): Promise<{ imported: number; skipped: number; safety_copy_id: string }> {
  if (!raw || typeof raw !== 'object') throw new Error('Invalid backup file');
  const pkg = raw as RecoveryPackageV2 | LegacyRecoveryPackage;
  if (pkg.kind !== 'ribdigi-pos-recovery') throw new Error('This is not a Ribdigi POS backup file');
  let rows: QueuedSale[];
  if (pkg.version === 2) {
    if (!opts.passphrase) throw new Error('Enter the backup passphrase');
    rows = (await decryptWithPassphrase<{ records: QueuedSale[] }>(pkg.encrypted, opts.passphrase)).records || [];
  } else if (pkg.version === 1 && Array.isArray(pkg.pending)) {
    rows = pkg.pending;
  } else {
    throw new Error('Unsupported backup version');
  }
  const foreign = rows.find((r) => r?.tenant_id && r.tenant_id !== opts.tenant_id);
  if (foreign) throw new Error('This backup belongs to another workspace');
  const safety_copy_id = await snapshotQueue('before-restore');
  const merged = await mergeRecords(rows);
  return { ...merged, safety_copy_id };
}

// ── Sign-out ───────────────────────────────────────────────────────────────

/** Sign-out removes the grant and cached catalogue/customers. Queued records always stay. */
export async function clearOfflineOnLogout(): Promise<void> {
  catalogMem = null;
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(['catalog', 'device_state'], 'readwrite');
    tx.objectStore('catalog').clear();
    const state = tx.objectStore('device_state');
    state.delete('offline_auth');
    state.delete('snapshot:session');
    state.delete('snapshot:me');
    state.delete('snapshot:stores');
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

/** Return the device's stock slice to the store when nothing is waiting to sync. */
export async function releaseOfflineGrantIfIdle(api: ApiFn): Promise<boolean> {
  const unsynced = (await listQueuedSales()).filter((r) => isUnsynced(r.state)).length;
  if (unsynced > 0) return false;
  const env = await getOfflineAuthEnvelope();
  if (!env?.grant_id) return false;
  await api('/pos/offline/release', {
    method: 'POST',
    body: JSON.stringify({ device_id: getOrCreateDeviceId(), client_request_ids: [] }),
  });
  return true;
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

export function formatTimeLeft(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return 'not set';
  const ms = new Date(iso).getTime() - now;
  if (!Number.isFinite(ms)) return 'unknown';
  if (ms <= 0) return 'expired';
  const hours = Math.floor(ms / 3600000);
  if (hours >= 24) return `${Math.floor(hours / 24)}d ${hours % 24}h left`;
  if (hours >= 1) return `${hours}h left`;
  return `${Math.max(1, Math.floor(ms / 60000))} min left`;
}
