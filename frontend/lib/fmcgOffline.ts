/**
 * FMCG field work kept on this device while the internet is down.
 *
 * Shelf audits, competitor prices, complaints and proof of delivery are saved in IndexedDB (not
 * localStorage, so photos and signatures fit) with a reference this device makes up. When the
 * connection returns they go to POST /fmcg/offline/sync, which saves each reference once, so a retry
 * never doubles anything. One the server refuses stays here with its reason until its owner fixes it
 * (send again) or discards it.
 *
 * Be honest about the limit: items live only in this browser on this device. Clearing site data,
 * private browsing or switching browser loses anything not yet sent. Nothing is queued when
 * IndexedDB is unavailable; the caller is told so and must keep the screen open.
 */

import { apiFetch } from './api';

export type OfflineKind = 'shelf_audit' | 'competitor_price' | 'complaint' | 'pod';

export type QueuedAction = {
  ref: string;
  tenant: string;
  kind: OfflineKind;
  captured_at: string;
  payload: Record<string, any>;
  /** What the person typed, shown in the list (never sent). */
  label: string;
  /** Set when the server refused it. */
  error?: string;
};

const DB = 'ribdigi.fmcg.offline';
const STORE = 'queue';
const LIMIT_BYTES = 40 * 1024 * 1024;

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') return reject(new Error('This browser cannot save work offline.'));
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'ref' });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(new Error('This browser cannot save work offline.'));
  });
}

function tx<T>(mode: IDBTransactionMode, run: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return open().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const t = db.transaction(STORE, mode);
        const r = run(t.objectStore(STORE));
        t.oncomplete = () => { db.close(); resolve(r.result); };
        t.onerror = () => { db.close(); reject(t.error || new Error('Could not save on this device.')); };
        t.onabort = () => { db.close(); reject(t.error || new Error('Could not save on this device.')); };
      }),
  );
}

export function newRef(): string {
  const c: Crypto | undefined = typeof crypto !== 'undefined' ? crypto : undefined;
  const id = c && 'randomUUID' in c ? c.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
  return `dev-${id}`;
}

export async function listQueue(tenant: string): Promise<QueuedAction[]> {
  try {
    const all = (await tx<QueuedAction[]>('readonly', (s) => s.getAll() as IDBRequest<QueuedAction[]>)) || [];
    return all.filter((a) => a.tenant === tenant).sort((a, b) => a.captured_at.localeCompare(b.captured_at));
  } catch {
    return [];
  }
}

export async function enqueue(tenant: string, kind: OfflineKind, payload: Record<string, any>, label: string): Promise<QueuedAction> {
  const size = JSON.stringify(payload).length;
  const used = (await listQueue(tenant)).reduce((n, a) => n + JSON.stringify(a.payload).length, 0);
  if (used + size > LIMIT_BYTES) throw new Error('This device is holding too much unsent work. Connect and send it first.');
  const action: QueuedAction = { ref: newRef(), tenant, kind, captured_at: new Date().toISOString(), payload, label };
  await tx('readwrite', (s) => s.put(action));
  return action;
}

export async function discard(ref: string): Promise<void> {
  await tx('readwrite', (s) => s.delete(ref));
}

async function mark(action: QueuedAction, error?: string): Promise<void> {
  await tx('readwrite', (s) => s.put({ ...action, error }));
}

export type SyncSummary = { saved: number; duplicates: number; failed: number; left: number };

/** Send the queue, 25 at a time, oldest first. Safe to call often; concurrent calls share one run. */
let running: Promise<SyncSummary> | null = null;
export function syncQueue(tenant: string): Promise<SyncSummary> {
  if (running) return running;
  running = (async () => {
    const summary: SyncSummary = { saved: 0, duplicates: 0, failed: 0, left: 0 };
    const queue = (await listQueue(tenant)).filter((a) => !a.error || a.error === 'retry');
    for (let i = 0; i < queue.length; i += 25) {
      const chunk = queue.slice(i, i + 25);
      let res: Response;
      try {
        res = await apiFetch('/fmcg/offline/sync', {
          method: 'POST',
          body: JSON.stringify({ actions: chunk.map((a) => ({ ref: a.ref, kind: a.kind, captured_at: a.captured_at, payload: a.payload })) }),
        });
      } catch {
        break; // still offline: keep everything
      }
      if (!res.ok) break; // signed out or server trouble: keep everything and try later
      const body = await res.json();
      for (const r of (body?.data?.results || []) as { ref: string; status: string; message?: string }[]) {
        const item = chunk.find((a) => a.ref === r.ref);
        if (!item) continue;
        if (r.status === 'ok' || r.status === 'duplicate') {
          await discard(r.ref);
          if (r.status === 'ok') summary.saved += 1; else summary.duplicates += 1;
        } else {
          await mark(item, r.message || 'The server did not accept it');
          summary.failed += 1;
        }
      }
    }
    summary.left = (await listQueue(tenant)).filter((a) => !a.error).length;
    return summary;
  })().finally(() => { running = null; });
  return running;
}

/** Put a refused item back in line to be sent again. */
export async function retry(action: QueuedAction): Promise<void> {
  await mark(action, undefined);
}

/** True when the failure looks like the network, not the server saying no. */
export function looksOffline(err: unknown): boolean {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return true;
  const msg = String((err as { message?: string } | null)?.message || err || '');
  return /failed to fetch|networkerror|network request failed|load failed|offline|internet/i.test(msg);
}
