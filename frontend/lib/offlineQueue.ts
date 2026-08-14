/**
 * Stage 165 K1 / Stage 168 F1 — IndexedDB offline op queue.
 * Flushes via POST /sync/push. Never stores tokens; SW must not cache /api/v1/*.
 */

const DB_NAME = 'ribdigi-offline-queue';
const DB_VERSION = 1;
const STORE = 'ops';

/** Stage 168 F1 — attestation contract markers (static proof; not Offline Complete). */
export const OFFLINE_QUEUE_CONTRACT = {
  storesTokens: false,
  storesAuthorizationHeader: false,
  flushEndpoint: '/sync/push',
  requiresBoundDevice: true,
  swMustNotCacheApi: true,
  offlineCompleteClaimed: false,
} as const;

export type OfflineQueueOp = {
  id?: number;
  client_op_id: string;
  op_type: string;
  payload: Record<string, unknown>;
  device_id: string;
  created_at: string;
  status: 'pending' | 'flushed' | 'failed';
  last_error?: string;
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
        const store = db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
        store.createIndex('client_op_id', 'client_op_id', { unique: true });
        store.createIndex('status', 'status', { unique: false });
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

export function getBoundOfflineDeviceId(): string {
  if (typeof window === 'undefined') return '';
  return (localStorage.getItem('offline_device_id') || '').trim();
}

export function setBoundOfflineDeviceId(deviceId: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem('offline_device_id', deviceId);
}

/** Stage 367 P0 — chrome event for Shell connectivity badge (not Offline Complete). */
export const OFFLINE_QUEUE_CHANGED_EVENT = 'ribdigi-offline-queue-changed';

let synchronizingDepth = 0;

function emitQueueChanged(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(OFFLINE_QUEUE_CHANGED_EVENT));
}

export function isOfflineQueueSynchronizing(): boolean {
  return synchronizingDepth > 0;
}

export type OfflineQueueSummary = {
  pending: number;
  failed: number;
  synchronizing: boolean;
};

export async function getOfflineQueueSummary(): Promise<OfflineQueueSummary> {
  const rows = await listPendingOfflineOps();
  return {
    pending: rows.filter((r) => r.status === 'pending').length,
    failed: rows.filter((r) => r.status === 'failed').length,
    synchronizing: synchronizingDepth > 0,
  };
}

export async function enqueueOfflineOp(op: {
  client_op_id: string;
  op_type: string;
  payload: Record<string, unknown>;
  device_id: string;
}): Promise<OfflineQueueOp> {
  const db = await openDb();
  const row: OfflineQueueOp = {
    client_op_id: op.client_op_id,
    op_type: op.op_type,
    payload: op.payload,
    device_id: op.device_id,
    created_at: new Date().toISOString(),
    status: 'pending',
  };
  const tx = db.transaction(STORE, 'readwrite');
  tx.objectStore(STORE).add(row);
  await txDone(tx);
  db.close();
  emitQueueChanged();
  return row;
}

export async function listPendingOfflineOps(): Promise<OfflineQueueOp[]> {
  const db = await openDb();
  const tx = db.transaction(STORE, 'readonly');
  const store = tx.objectStore(STORE);
  const req = store.getAll();
  const rows: OfflineQueueOp[] = await new Promise((resolve, reject) => {
    req.onsuccess = () => resolve((req.result || []) as OfflineQueueOp[]);
    req.onerror = () => reject(req.error || new Error('IndexedDB list failed'));
  });
  await txDone(tx);
  db.close();
  return rows.filter((r) => r.status === 'pending' || r.status === 'failed');
}

export async function markOfflineOp(
  clientOpId: string,
  status: 'flushed' | 'failed',
  lastError?: string,
): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(STORE, 'readwrite');
  const store = tx.objectStore(STORE);
  const idx = store.index('client_op_id');
  const getReq = idx.get(clientOpId);
  const row: OfflineQueueOp | undefined = await new Promise((resolve, reject) => {
    getReq.onsuccess = () => resolve(getReq.result as OfflineQueueOp | undefined);
    getReq.onerror = () => reject(getReq.error || new Error('IndexedDB get failed'));
  });
  if (row && row.id != null) {
    row.status = status;
    if (lastError) row.last_error = lastError;
    store.put(row);
  }
  await txDone(tx);
  db.close();
  emitQueueChanged();
}

export async function flushOfflineQueue(apiFn: typeof import('./api').api): Promise<{
  flushed: number;
  failed: number;
  results: unknown[];
}> {
  const deviceId = getBoundOfflineDeviceId();
  if (!deviceId) {
    throw new Error('Bind an offline device in Settings → Offline sync before flushing');
  }
  const pending = await listPendingOfflineOps();
  if (!pending.length) {
    return { flushed: 0, failed: 0, results: [] };
  }
  synchronizingDepth += 1;
  emitQueueChanged();
  try {
    const ops = pending.map((p) => ({
      client_op_id: p.client_op_id,
      op_type: p.op_type,
      payload: p.payload,
    }));
    const res = await apiFn('/sync/push', {
      method: 'POST',
      body: JSON.stringify({ device_id: deviceId, ops }),
    });
    const results = (res.data?.results || []) as Array<{
      client_op_id: string;
      status: string;
      error?: string;
      replayed?: boolean;
    }>;
    let flushed = 0;
    let failed = 0;
    for (const r of results) {
      if (r.status === 'applied' || r.status === 'acked' || r.replayed) {
        await markOfflineOp(r.client_op_id, 'flushed');
        flushed += 1;
      } else if (r.status === 'failed' || r.status === 'conflict') {
        await markOfflineOp(r.client_op_id, 'failed', r.error || r.status);
        failed += 1;
      }
    }
    return { flushed, failed, results };
  } finally {
    synchronizingDepth = Math.max(0, synchronizingDepth - 1);
    emitQueueChanged();
  }
}

export function newClientOpId(prefix = 'op'): string {
  const rand =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  return `${prefix}-${rand}`;
}
