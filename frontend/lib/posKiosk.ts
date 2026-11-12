/**
 * Kiosk mode for a till: full screen, no menu, no way to other screens.
 *
 * The device remembers it is a kiosk (localStorage), so a refresh or restart comes back
 * locked to the till. Closing it needs the eight-digit close code. The server checks the
 * code; offline, a PBKDF2 check saved when kiosk mode started is used, so the code itself
 * never sits in the browser.
 */

export const KIOSK_EVENT = 'ribdigi:pos-kiosk';

const KIOSK_KEY = 'ribdigi:pos:kiosk';
const KIOSK_VERIFIER_KEY = 'ribdigi:pos:kiosk-verifier';
const OFFLINE_FAIL_LIMIT = 5;
const OFFLINE_LOCK_MS = 5 * 60 * 1000;

export type KioskState = { home: string; tenant: string; since: number };

type KioskVerifier = { salt: string; hash: string; rounds: number; length: number; failed: number; locked_until: number };

function local(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

function tenantNow(): string {
  return local()?.getItem('tenant') || '';
}

export function kioskHomeFor(pathname: string): string | null {
  if (pathname === '/pos') return '/pos';
  if (pathname === '/restaurant/till' || pathname.startsWith('/restaurant/till/')) return '/restaurant/till';
  return null;
}

export function readKiosk(): KioskState | null {
  try {
    const raw = local()?.getItem(KIOSK_KEY);
    const row = raw ? (JSON.parse(raw) as KioskState) : null;
    if (!row || !kioskHomeFor(row.home)) return null;
    // A kiosk belongs to the company it was started for.
    return row.tenant && row.tenant !== tenantNow() ? null : row;
  } catch {
    return null;
  }
}

function announce(): void {
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') window.dispatchEvent(new Event(KIOSK_EVENT));
}

export function startKiosk(home: string): KioskState {
  const row: KioskState = { home, tenant: tenantNow(), since: Date.now() };
  try {
    local()?.setItem(KIOSK_KEY, JSON.stringify(row));
  } catch {
    /* without storage the kiosk lasts until refresh */
  }
  announce();
  return row;
}

export function endKiosk(): void {
  try {
    local()?.removeItem(KIOSK_KEY);
  } catch {
    /* ignore */
  }
  announce();
}

export function saveKioskVerifier(data: { salt: string; hash: string; rounds: number; length: number }): void {
  try {
    const row: KioskVerifier = { ...data, failed: 0, locked_until: 0 };
    local()?.setItem(KIOSK_VERIFIER_KEY, JSON.stringify(row));
  } catch {
    /* offline close is a bonus */
  }
}

export function kioskCodeLength(): number {
  try {
    const raw = local()?.getItem(KIOSK_VERIFIER_KEY);
    const n = raw ? Number((JSON.parse(raw) as KioskVerifier).length) : 0;
    return n >= 4 && n <= 16 ? n : 8;
  } catch {
    return 8;
  }
}

function toHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function fromHex(text: string): Uint8Array {
  const out = new Uint8Array(text.length / 2);
  for (let i = 0; i < out.length; i += 1) out[i] = parseInt(text.slice(i * 2, i * 2 + 2), 16);
  return out;
}

export type KioskOfflineCheck = { ok: boolean; waitMs?: number; known: boolean };

export async function checkKioskCodeOffline(code: string, now = Date.now()): Promise<KioskOfflineCheck> {
  let row: KioskVerifier | null = null;
  try {
    const raw = local()?.getItem(KIOSK_VERIFIER_KEY);
    row = raw ? (JSON.parse(raw) as KioskVerifier) : null;
  } catch {
    row = null;
  }
  if (!row || typeof crypto === 'undefined' || !crypto.subtle) return { ok: false, known: false };
  if (row.locked_until > now) return { ok: false, known: true, waitMs: row.locked_until - now };
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(code), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', salt: fromHex(row.salt) as BufferSource, iterations: row.rounds, hash: 'SHA-256' },
    key,
    256
  );
  const ok = toHex(bits) === row.hash;
  if (ok) {
    row.failed = 0;
    row.locked_until = 0;
  } else {
    row.failed += 1;
    if (row.failed >= OFFLINE_FAIL_LIMIT) {
      row.failed = 0;
      row.locked_until = now + OFFLINE_LOCK_MS;
    }
  }
  try {
    local()?.setItem(KIOSK_VERIFIER_KEY, JSON.stringify(row));
  } catch {
    /* ignore */
  }
  return { ok, known: true };
}

export function enterFullScreen(): void {
  try {
    const el = document.documentElement as HTMLElement & { webkitRequestFullscreen?: () => void };
    if (document.fullscreenElement) return;
    if (el.requestFullscreen) void el.requestFullscreen().catch(() => undefined);
    else el.webkitRequestFullscreen?.();
  } catch {
    /* some browsers refuse; the kiosk still hides the menu */
  }
}

export function leaveFullScreen(): void {
  try {
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
  } catch {
    /* ignore */
  }
}
