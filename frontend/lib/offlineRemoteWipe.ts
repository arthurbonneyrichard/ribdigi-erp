/**
 * Offline remote IndexedDB wipe (PARTIAL — push delivery PARTIAL).
 *
 * Admin queues wipe via POST /offline/devices/{id}/wipe. When this browser's
 * bound device reports wipe_pending (online poll **or** Web Push), clear local
 * offline IndexedDB stores and POST wipe/ack.
 *
 * Does **not** claim Offline Complete, push-delivery Complete, or 7-day VERIFIED.
 */

import { api } from './api';
import { getBoundOfflineDeviceId, setBoundOfflineDeviceId } from './offlineQueue';

export const OFFLINE_REMOTE_WIPE_CONTRACT = {
  requestEndpoint: '/offline/devices/{id}/wipe',
  ackEndpoint: '/offline/devices/{id}/wipe/ack',
  clearsIndexedDb: true,
  /** Web Push path exists but is not product-Complete. */
  pushDeliveryPartial: true,
  pushDeliveryCompleteClaimed: false,
  /** @deprecated use pushDeliveryCompleteClaimed — kept false for honesty tests */
  pushDelivery: false,
  /**
   * Poll-path contracts (wipe → GET wipe_pending → clear IndexedDB → ack) are
   * engineering-ready without FCM. This is NOT Offline Complete / 7-day VERIFIED.
   */
  wipePollPathEngineeringReady: true,
  offlineCompleteClaimed: false,
  sevenDayVerifiedClaimed: false,
} as const;

/** Known offline IndexedDB database names used by the SPA. */
export const OFFLINE_INDEXED_DB_NAMES = [
  'ribdigi-offline-queue',
  'ribdigi-offline-catalog',
  'ribdigi-offline-auth',
  'ribdigi-offline-receipt-seq',
] as const;

function deleteDatabase(name: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      resolve();
      return;
    }
    const req = indexedDB.deleteDatabase(name);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error || new Error(`Failed to delete ${name}`));
    req.onblocked = () => resolve();
  });
}

/** Clear all known offline IndexedDB databases (local only). */
export async function clearOfflineIndexedDatabases(): Promise<string[]> {
  const cleared: string[] = [];
  for (const name of OFFLINE_INDEXED_DB_NAMES) {
    await deleteDatabase(name);
    cleared.push(name);
  }
  if (typeof window !== 'undefined') {
    localStorage.removeItem('offline_device_id');
  }
  setBoundOfflineDeviceId('');
  return cleared;
}

export type WipeDevicePayload = {
  wipe_pending?: boolean;
  wipe_status?: string | null;
  id?: string;
};

/**
 * If the bound device has wipe_pending, clear local stores and ack.
 * Safe no-op when no bound device or wipe not pending.
 */
export async function processPendingRemoteWipeIfNeeded(
  device?: WipeDevicePayload | null,
): Promise<{ wiped: boolean; deviceId: string | null }> {
  const boundId = getBoundOfflineDeviceId();
  let payload = device;
  const deviceId = (payload?.id || boundId || '').trim();
  if (!deviceId) {
    return { wiped: false, deviceId: null };
  }
  if (!payload || payload.wipe_pending === undefined) {
    try {
      const res = await api<{ data?: WipeDevicePayload }>(`/offline/devices/${deviceId}`);
      payload = (res as { data?: WipeDevicePayload })?.data || (res as WipeDevicePayload);
    } catch {
      // Push may pass wipe_pending=true before GET works; honor explicit flag.
      if (!payload?.wipe_pending) {
        return { wiped: false, deviceId };
      }
    }
  }
  if (!payload?.wipe_pending) {
    return { wiped: false, deviceId };
  }
  await clearOfflineIndexedDatabases();
  await api(`/offline/devices/${deviceId}/wipe/ack`, { method: 'POST' });
  return { wiped: true, deviceId };
}
