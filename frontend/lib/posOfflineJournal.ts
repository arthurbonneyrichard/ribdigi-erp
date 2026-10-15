/**
 * Copy of a queued sale that lives on this PC, outside browser site data.
 * The till print agent writes it. IndexedDB is still the working queue.
 * If the agent is not running, the sale stays in the browser only.
 */

import type { QueuedSale } from './posOffline';

const DEFAULT_BASE = 'http://127.0.0.1:8765';
const SECRET_KEYS = new Set([
  'password',
  'admin_password',
  'access_token',
  'refresh_token',
  'authorization',
  'secret',
  'totp_code',
  'token',
  'api_key',
  'auth_token',
  'password_enc',
  'payload_enc',
]);

let baseOverride: string | null | undefined;

export function setOutsideJournalBase(url: string | null): void {
  baseOverride = url;
}

function journalBase(): string | null {
  if (baseOverride !== undefined) return baseOverride;
  if (typeof window === 'undefined') return null;
  return DEFAULT_BASE;
}

function scrub(value: unknown): unknown {
  if (Array.isArray(value)) return value.map((item) => scrub(item));
  if (!value || typeof value !== 'object') return value;
  const out: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (SECRET_KEYS.has(key.toLowerCase())) continue;
    out[key] = scrub(item);
  }
  return out;
}

export async function mirrorSaleToOutsideJournal(rec: QueuedSale): Promise<void> {
  const base = journalBase();
  if (!base || !rec.client_request_id || !rec.tenant_id || !rec.user_id) return;
  const body = scrub({ ...rec, payload_enc: undefined }) as Record<string, unknown>;
  delete body.payload_enc;
  const response = await fetch(new URL('/v1/offline-sales', base), {
    method: 'POST',
    credentials: 'omit',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(2000),
  });
  if (!response.ok) {
    throw new Error('Till journal did not accept the sale');
  }
}

export async function fetchOutsideJournal(tenantId: string, userId: string): Promise<QueuedSale[]> {
  const base = journalBase();
  if (!base || !tenantId || !userId) return [];
  try {
    const url = new URL('/v1/offline-sales', base);
    url.searchParams.set('tenant_id', tenantId);
    url.searchParams.set('user_id', userId);
    const response = await fetch(url, {
      credentials: 'omit',
      signal: AbortSignal.timeout(2000),
    });
    if (!response.ok) return [];
    const body = (await response.json()) as { records?: QueuedSale[] };
    return Array.isArray(body?.records) ? body.records : [];
  } catch {
    return [];
  }
}
