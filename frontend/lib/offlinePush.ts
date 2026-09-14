/**
 * Offline Web Push for remote wipe (PARTIAL — not Offline Complete).
 *
 * Registers PushManager subscription against POST /offline/devices/{id}/push-subscription.
 * Service worker handles `push` events with type remote_wipe and notifies clients.
 * Does **not** claim Offline Complete or push-delivery Complete.
 */

import { api } from './api';
import { getBoundOfflineDeviceId } from './offlineQueue';

export const OFFLINE_PUSH_CONTRACT = {
  vapidEndpoint: '/offline/push/vapid-public-key',
  subscriptionEndpoint: '/offline/devices/{id}/push-subscription',
  pushDeliveryPartial: true,
  pushDeliveryCompleteClaimed: false,
  offlineCompleteClaimed: false,
} as const;

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
}

export type VapidPublicPayload = {
  configured?: boolean;
  enabled?: boolean;
  public_key?: string | null;
};

export async function fetchVapidPublicKey(): Promise<VapidPublicPayload | null> {
  try {
    const res = await api<{ data?: VapidPublicPayload }>(OFFLINE_PUSH_CONTRACT.vapidEndpoint);
    return (res as { data?: VapidPublicPayload })?.data || (res as VapidPublicPayload);
  } catch {
    return null;
  }
}

/**
 * Best-effort: subscribe this browser to Web Push for the bound offline device.
 * No-ops when Push API / VAPID unavailable — wipe poll remains the fallback.
 */
export async function registerOfflinePushSubscription(
  deviceId?: string | null,
): Promise<{ registered: boolean; reason?: string }> {
  if (typeof window === 'undefined') {
    return { registered: false, reason: 'ssr' };
  }
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    return { registered: false, reason: 'push_unsupported' };
  }
  const id = (deviceId || getBoundOfflineDeviceId() || '').trim();
  if (!id) {
    return { registered: false, reason: 'no_device' };
  }
  const vapid = await fetchVapidPublicKey();
  if (!vapid?.enabled || !vapid.public_key) {
    return { registered: false, reason: 'vapid_unconfigured' };
  }
  try {
    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapid.public_key),
      });
    }
    const json = sub.toJSON();
    const endpoint = json.endpoint || '';
    const keys = json.keys || {};
    await api(`/offline/devices/${id}/push-subscription`, {
      method: 'PUT',
      body: JSON.stringify({
        endpoint,
        keys: {
          p256dh: keys.p256dh,
          auth: keys.auth,
        },
      }),
    });
    return { registered: true };
  } catch {
    return { registered: false, reason: 'subscribe_failed' };
  }
}

/** Listen for SW postMessage remote_wipe and run IndexedDB clear + ack. */
export function listenForRemoteWipePushMessages(): () => void {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
    return () => undefined;
  }
  const handler = (event: MessageEvent) => {
    const data = event.data;
    if (!data || data.type !== 'ribdigi-remote-wipe') return;
    void import('./offlineRemoteWipe')
      .then(({ processPendingRemoteWipeIfNeeded }) =>
        processPendingRemoteWipeIfNeeded(
          data.device_id
            ? { id: String(data.device_id), wipe_pending: true }
            : undefined,
        ),
      )
      .catch(() => {
        /* best-effort */
      });
  };
  navigator.serviceWorker.addEventListener('message', handler);
  return () => navigator.serviceWorker.removeEventListener('message', handler);
}
