/**
 * Till lock storage. No imports from ./api, because ./api reads the operator token from here.
 *
 * The operator token lives in sessionStorage, so it survives a refresh and dies with the
 * tab. The cart snapshot lives in localStorage so a sale outlasts a refresh or a crash.
 */

export type TillSurface = 'retail' | 'restaurant';

export type TillOperator = { id: string; name: string; role?: string };

export type TillSnapshot = {
  owner_id: string;
  owner_name: string;
  at: number;
  item_count: number;
  total: number;
  data: unknown;
  started_by?: string | null;
};

type TillStore = { current: TillSnapshot | null; parked: Record<string, TillSnapshot> };

const OPERATOR_KEY = 'ribdigi:pos:operator';
const HELD_TOKEN_KEY = 'ribdigi:pos:operator-held';
const LOCKED_KEY = 'ribdigi:pos:locked';
const WELCOME_KEY = 'ribdigi:pos:welcome';
const VERIFIER_KEY = 'ribdigi:pos:offline-verifier';
const SNAPSHOT_PREFIX = 'ribdigi:pos:till:';
const SNAPSHOT_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const PBKDF2_ROUNDS = 200_000;
const OFFLINE_FAIL_LIMIT = 5;
const OFFLINE_LOCK_MS = 5 * 60 * 1000;

export const POS_LOCKED_EVENT = 'ribdigi:pos-locked';
export const POS_LOCK_NOW_EVENT = 'ribdigi:pos-lock-now';
export const POS_OPERATOR_HEADER = 'X-Pos-Operator';

/** Screens where the cashier at the till acts instead of the signed-in account. */
export function isTillPath(pathname: string): boolean {
  return pathname === '/pos' || pathname === '/restaurant/till' || pathname.startsWith('/restaurant/till/');
}

function session(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

function local(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function getOperatorToken(): string | null {
  return session()?.getItem(OPERATOR_KEY) || null;
}

/** The header value for a request made from a till screen, or null anywhere else. */
export function tillOperatorToken(): string | null {
  if (typeof window === 'undefined' || !isTillPath(window.location.pathname)) return null;
  return getOperatorToken();
}

export function setOperatorToken(token: string): void {
  const store = session();
  store?.setItem(OPERATOR_KEY, token);
  store?.removeItem(LOCKED_KEY);
  store?.removeItem(HELD_TOKEN_KEY);
  lockedNow = false;
}

let lockedNow = false;

/** True while the lock screen is up: till shortcuts and background sync must stand still. */
export function isTillLocked(): boolean {
  return lockedNow;
}

export function setTillLockedFlag(value: boolean): void {
  lockedNow = value;
}

export function wasLeftLocked(): boolean {
  return session()?.getItem(LOCKED_KEY) === '1';
}

/** The server says this till is open, so nothing is waiting behind a lock. */
export function clearLeftLocked(): void {
  const store = session();
  store?.removeItem(LOCKED_KEY);
  store?.removeItem(HELD_TOKEN_KEY);
  lockedNow = false;
}

/** Stop sending the token. It is kept aside only so an offline unlock can pick it back up. */
export function holdOperatorToken(): void {
  const store = session();
  const token = store?.getItem(OPERATOR_KEY);
  if (token) store?.setItem(HELD_TOKEN_KEY, token);
  store?.removeItem(OPERATOR_KEY);
  store?.setItem(LOCKED_KEY, '1');
  lockedNow = true;
}

export function resumeHeldToken(): void {
  const store = session();
  const token = store?.getItem(HELD_TOKEN_KEY);
  if (token) store?.setItem(OPERATOR_KEY, token);
  store?.removeItem(HELD_TOKEN_KEY);
  store?.removeItem(LOCKED_KEY);
  lockedNow = false;
}

export function rememberWelcome(name: string): void {
  session()?.setItem(WELCOME_KEY, name);
}

export function takeWelcome(): string {
  const store = session();
  const name = store?.getItem(WELCOME_KEY) || '';
  store?.removeItem(WELCOME_KEY);
  return name;
}

/** The server answered 423: the till is locked, so stop acting as this cashier. */
export function notePosLockedResponse(): void {
  if (typeof window === 'undefined' || !isTillPath(window.location.pathname)) return;
  holdOperatorToken();
  window.dispatchEvent(new Event(POS_LOCKED_EVENT));
}

// ---------- cart snapshot ----------

function snapshotKey(surface: TillSurface, tenantId: string): string {
  return `${SNAPSHOT_PREFIX}${surface}:${tenantId}`;
}

function fresh(row: TillSnapshot | null | undefined, now: number): TillSnapshot | null {
  if (!row || typeof row !== 'object' || !row.owner_id) return null;
  return now - Number(row.at || 0) > SNAPSHOT_MAX_AGE_MS ? null : row;
}

function readTill(surface: TillSurface, tenantId: string, now = Date.now()): TillStore {
  try {
    const raw = local()?.getItem(snapshotKey(surface, tenantId));
    const parsed = raw ? (JSON.parse(raw) as Partial<TillStore>) : {};
    const parked: Record<string, TillSnapshot> = {};
    for (const [owner, row] of Object.entries(parsed.parked || {})) {
      const kept = fresh(row, now);
      if (kept) parked[owner] = kept;
    }
    return { current: fresh(parsed.current, now), parked };
  } catch {
    return { current: null, parked: {} };
  }
}

function writeTill(surface: TillSurface, tenantId: string, till: TillStore): void {
  try {
    const store = local();
    if (!store) return;
    if (!till.current && Object.keys(till.parked).length === 0) {
      store.removeItem(snapshotKey(surface, tenantId));
      return;
    }
    store.setItem(snapshotKey(surface, tenantId), JSON.stringify(till));
  } catch {
    /* storage full or blocked: the sale still works, it just would not outlast a refresh */
  }
}

export function saveCurrentSale(surface: TillSurface, tenantId: string, snapshot: TillSnapshot | null): void {
  const till = readTill(surface, tenantId);
  till.current = snapshot;
  writeTill(surface, tenantId, till);
}

export function readTillSale(surface: TillSurface, tenantId: string): TillStore {
  return readTill(surface, tenantId);
}

/** Set a sale aside for the cashier who started it, and clear it from the till. */
export function parkForOwner(surface: TillSurface, tenantId: string, snapshot: TillSnapshot): void {
  const till = readTill(surface, tenantId);
  till.parked[snapshot.owner_id] = snapshot;
  till.current = null;
  writeTill(surface, tenantId, till);
}

export function takeParked(surface: TillSurface, tenantId: string, ownerId: string): TillSnapshot | null {
  const till = readTill(surface, tenantId);
  const row = till.parked[ownerId] || null;
  if (row) {
    delete till.parked[ownerId];
    writeTill(surface, tenantId, till);
  }
  return row;
}

// ---------- offline unlock ----------

type OfflineVerifier = {
  operator: TillOperator;
  tenant_id: string;
  salt: string;
  hash: string;
  failed: number;
  locked_until: number;
};

function toHex(bytes: ArrayBuffer | Uint8Array): string {
  return Array.from(new Uint8Array(bytes as ArrayBuffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function fromHex(text: string): Uint8Array {
  const out = new Uint8Array(text.length / 2);
  for (let i = 0; i < out.length; i += 1) out[i] = parseInt(text.slice(i * 2, i * 2 + 2), 16);
  return out;
}

async function derive(passcode: string, salt: Uint8Array): Promise<string> {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(passcode), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', salt: salt as BufferSource, iterations: PBKDF2_ROUNDS, hash: 'SHA-256' },
    key,
    256
  );
  return toHex(bits);
}

function readVerifier(tenantId: string): OfflineVerifier | null {
  try {
    const raw = local()?.getItem(VERIFIER_KEY);
    const row = raw ? (JSON.parse(raw) as OfflineVerifier) : null;
    return row && row.tenant_id === tenantId ? row : null;
  } catch {
    return null;
  }
}

/** Only the last cashier on this till can unlock without a connection. Switching needs the server. */
export async function saveOfflineVerifier(tenantId: string, operator: TillOperator, passcode: string): Promise<void> {
  try {
    if (typeof crypto === 'undefined' || !crypto.subtle) return;
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const row: OfflineVerifier = {
      operator,
      tenant_id: tenantId,
      salt: toHex(salt),
      hash: await derive(passcode, salt),
      failed: 0,
      locked_until: 0,
    };
    local()?.setItem(VERIFIER_KEY, JSON.stringify(row));
  } catch {
    /* offline unlock is a bonus: the till still works online */
  }
}

export function clearOfflineVerifier(): void {
  try {
    local()?.removeItem(VERIFIER_KEY);
  } catch {
    /* ignore */
  }
}

export function offlineVerifierFor(tenantId: string): TillOperator | null {
  return readVerifier(tenantId)?.operator || null;
}

export type OfflineCheck = { ok: boolean; operator?: TillOperator; waitMs?: number; triesLeft?: number };

export async function checkOfflinePasscode(tenantId: string, passcode: string, now = Date.now()): Promise<OfflineCheck> {
  const row = readVerifier(tenantId);
  if (!row) return { ok: false, triesLeft: 0 };
  if (row.locked_until > now) return { ok: false, waitMs: row.locked_until - now };
  const matched = (await derive(passcode, fromHex(row.salt))) === row.hash;
  if (matched) {
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
    local()?.setItem(VERIFIER_KEY, JSON.stringify(row));
  } catch {
    /* ignore */
  }
  if (matched) return { ok: true, operator: row.operator };
  if (row.locked_until > now) return { ok: false, waitMs: OFFLINE_LOCK_MS };
  return { ok: false, triesLeft: OFFLINE_FAIL_LIMIT - row.failed };
}
