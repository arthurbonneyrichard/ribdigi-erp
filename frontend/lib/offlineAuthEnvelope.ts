/**
 * §13–14 — 7-day offline authorization envelope (IndexedDB).
 * Stores permissions snapshot + validity window only — never passwords/tokens.
 */

import { getBoundOfflineDeviceId } from './offlineQueue';
import { getSelectedStoreId } from './storeContext';

const DB_NAME = 'ribdigi-offline-auth';
const DB_VERSION = 1;
const STORE = 'envelope';

export const OFFLINE_AUTH_VALIDITY_DAYS = 7;
export const OFFLINE_AUTH_CHANGED_EVENT = 'ribdigi-offline-auth-changed';

/** Stage 2026-08-23 — attestation contract markers (not Offline Complete). */
export const OFFLINE_AUTH_CONTRACT = {
  storesTokens: false,
  storesPasswords: false,
  storesRefreshTokens: false,
  defaultValidityDays: OFFLINE_AUTH_VALIDITY_DAYS,
  offlineCompleteClaimed: false,
} as const;

export type OfflineAuthEnvelope = {
  tenant_id: string;
  company_id: string | null;
  store_id: string | null;
  user_id: string | null;
  device_id: string;
  permissions: Record<string, string[]>;
  issued_at: string;
  last_online_at: string;
  offline_valid_until: string;
  catalog_version?: string | null;
  app_version?: string | null;
  validity_days?: number;
};

export type OfflineAuthStatus = {
  envelope: OfflineAuthEnvelope | null;
  expired: boolean;
  canQueueOfflineSales: boolean;
  expiresAt: string | null;
  daysRemaining: number | null;
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
        db.createObjectStore(STORE, { keyPath: 'device_id' });
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

function emitAuthChanged(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(OFFLINE_AUTH_CHANGED_EVENT));
}

export function parseEnvelope(raw: unknown): OfflineAuthEnvelope | null {
  if (!raw || typeof raw !== 'object') return null;
  const e = raw as Record<string, unknown>;
  const deviceId = String(e.device_id || '').trim();
  const tenantId = String(e.tenant_id || '').trim();
  const until = String(e.offline_valid_until || '').trim();
  if (!deviceId || !tenantId || !until) return null;
  const perms = e.permissions;
  return {
    tenant_id: tenantId,
    company_id: e.company_id != null ? String(e.company_id) : null,
    store_id: e.store_id != null ? String(e.store_id) : null,
    user_id: e.user_id != null ? String(e.user_id) : null,
    device_id: deviceId,
    permissions: typeof perms === 'object' && perms ? (perms as Record<string, string[]>) : {},
    issued_at: String(e.issued_at || ''),
    last_online_at: String(e.last_online_at || ''),
    offline_valid_until: until,
    catalog_version: e.catalog_version != null ? String(e.catalog_version) : null,
    app_version: e.app_version != null ? String(e.app_version) : null,
    validity_days:
      typeof e.validity_days === 'number' ? e.validity_days : OFFLINE_AUTH_VALIDITY_DAYS,
  };
}

export function isEnvelopeExpired(
  envelope: OfflineAuthEnvelope | null,
  nowMs = Date.now(),
): boolean {
  if (!envelope?.offline_valid_until) return true;
  const until = Date.parse(envelope.offline_valid_until);
  if (!Number.isFinite(until)) return true;
  return until <= nowMs;
}

export async function getStoredOfflineAuthEnvelope(
  deviceId?: string,
): Promise<OfflineAuthEnvelope | null> {
  const id = (deviceId || getBoundOfflineDeviceId()).trim();
  if (!id) return null;
  const db = await openDb();
  const tx = db.transaction(STORE, 'readonly');
  const req = tx.objectStore(STORE).get(id);
  const row = await new Promise<OfflineAuthEnvelope | undefined>((resolve, reject) => {
    req.onsuccess = () => resolve(req.result as OfflineAuthEnvelope | undefined);
    req.onerror = () => reject(req.error || new Error('IndexedDB get failed'));
  });
  await txDone(tx);
  db.close();
  return row || null;
}

export async function storeOfflineAuthEnvelope(envelope: OfflineAuthEnvelope): Promise<void> {
  const parsed = parseEnvelope(envelope);
  if (!parsed) throw new Error('Invalid offline auth envelope');
  const db = await openDb();
  const tx = db.transaction(STORE, 'readwrite');
  tx.objectStore(STORE).put(parsed);
  await txDone(tx);
  db.close();
  emitAuthChanged();
}

export async function clearOfflineAuthEnvelope(deviceId?: string): Promise<void> {
  const id = (deviceId || getBoundOfflineDeviceId()).trim();
  if (!id) return;
  const db = await openDb();
  const tx = db.transaction(STORE, 'readwrite');
  tx.objectStore(STORE).delete(id);
  await txDone(tx);
  db.close();
  emitAuthChanged();
}

export async function getOfflineAuthStatus(
  deviceId?: string,
): Promise<OfflineAuthStatus> {
  const envelope = await getStoredOfflineAuthEnvelope(deviceId);
  const expired = isEnvelopeExpired(envelope);
  let daysRemaining: number | null = null;
  if (envelope?.offline_valid_until) {
    const until = Date.parse(envelope.offline_valid_until);
    if (Number.isFinite(until)) {
      daysRemaining = Math.max(0, Math.ceil((until - Date.now()) / 86400000));
    }
  }
  return {
    envelope,
    expired,
    canQueueOfflineSales: Boolean(envelope) && !expired,
    expiresAt: envelope?.offline_valid_until || null,
    daysRemaining,
  };
}

export type OfflineBindContext = {
  tenant_id: string;
  company_id?: string | null;
  user_id?: string | null;
  store_id?: string | null;
  catalog_version?: string | null;
};

export const APP_VERSION = '1.0.0-mvp';

export function buildBindPayload(ctx: OfflineBindContext): Record<string, unknown> {
  return {
    store_id: ctx.store_id || getSelectedStoreId() || null,
    catalog_version: ctx.catalog_version || null,
    app_version: APP_VERSION,
  };
}

/** Online bind/refresh — calls POST /offline/devices/{id}/bind and persists envelope. */
export async function refreshOfflineAuthEnvelope(
  apiFn: typeof import('./api').api,
  ctx: OfflineBindContext,
): Promise<OfflineAuthEnvelope> {
  const deviceId = getBoundOfflineDeviceId();
  if (!deviceId) {
    throw new Error('Bind an offline device in Settings → Offline sync before refreshing auth');
  }
  const res = await apiFn(`/offline/devices/${deviceId}/bind`, {
    method: 'POST',
    body: JSON.stringify(buildBindPayload(ctx)),
  });
  const envelope = parseEnvelope(res.data?.auth_envelope);
  if (!envelope) {
    throw new Error('Server did not return an offline auth envelope');
  }
  await storeOfflineAuthEnvelope(envelope);
  return envelope;
}

/** Attach envelope metadata to sync payloads (push/pull/ack). */
export async function withOfflineAuthPayload<T extends Record<string, unknown>>(
  body: T,
): Promise<T & { auth_envelope?: OfflineAuthEnvelope; store_id?: string | null; app_version: string }> {
  const envelope = await getStoredOfflineAuthEnvelope();
  const storeId = envelope?.store_id || getSelectedStoreId() || null;
  return {
    ...body,
    ...(envelope ? { auth_envelope: envelope } : {}),
    store_id: storeId,
    app_version: APP_VERSION,
  };
}

export function offlineAuthBlockedMessage(status: OfflineAuthStatus): string {
  if (!status.envelope) {
    return 'Offline auth envelope missing — go online and bind device (Settings → Offline sync)';
  }
  if (status.expired) {
    return (
      'Offline authorization expired — reconnect online to renew. ' +
      'Pending queue is preserved; new offline sales are blocked.'
    );
  }
  return '';
}
