/**
 * Monotonic offline receipt numbers per bound device (IndexedDB).
 * Format: OFF-{deviceShort}-{seq} — no secrets; survives page reload.
 */

const DB_NAME = 'ribdigi-offline-receipt-seq';
const DB_VERSION = 1;
const STORE = 'counters';

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
        db.createObjectStore(STORE);
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

function deviceShort(deviceId: string): string {
  const cleaned = (deviceId || '').replace(/-/g, '').toLowerCase();
  return (cleaned.slice(0, 8) || 'device').slice(0, 12);
}

/** Allocate next receipt number for a device-bound offline sale. */
export async function nextOfflineReceiptNumber(deviceId: string): Promise<string> {
  const key = (deviceId || '').trim();
  if (!key) {
    throw new Error('Device id required for offline receipt numbering');
  }
  const db = await openDb();
  const tx = db.transaction(STORE, 'readwrite');
  const store = tx.objectStore(STORE);
  const getReq = store.get(key);
  const prev: number = await new Promise((resolve, reject) => {
    getReq.onsuccess = () => resolve(Number(getReq.result || 0));
    getReq.onerror = () => reject(getReq.error || new Error('IndexedDB get failed'));
  });
  const next = prev + 1;
  store.put(next, key);
  await txDone(tx);
  db.close();
  return `OFF-${deviceShort(key)}-${String(next).padStart(6, '0')}`;
}

export function formatOfflineReceiptLabel(receiptNumber: string | undefined | null): string {
  if (!receiptNumber) return '';
  return String(receiptNumber);
}
