/** API reachability for POS. Do not treat navigator.onLine as proof the server is up. */

export type LinkPhase = 'online' | 'offline' | 'api_down' | 'syncing' | 'sync_failed';

export type LinkSnapshot = {
  phase: LinkPhase;
  pending: number;
  lastSyncAt: string | null;
  syncError: string;
};

export type OfflineGrantShape = {
  grant_id?: string | null;
  user_id?: string | null;
  tenant_id?: string | null;
  revoked_at?: string | null;
  offline_valid_until?: string | null;
};

export const UNPREPARED_OFFLINE =
  'Connect to the internet and sign in to prepare this device for offline POS.';

export const EXPIRED_OFFLINE =
  'Online sign-in is required before this device can sell offline again. Saved sales stay on this device.';

export const PREPARED_OFFLINE =
  'This device is prepared for offline POS. Sign-in needs a connection, so open Point of Sale to keep selling. Saved sales stay on this device.';

/** Why Offline Complete is still missing. Do not shorten this into a completion claim. */
export const OFFLINE_COMPLETE_MISSING =
  'Offline Complete remains missing because the browser device id is not strong device binding, a private window with no till-agent journal on this PC cannot recover those sales, saved sales upload only while the Point of Sale page is open and signed in, and a live site has not been tested.';

const listeners = new Set<(snap: LinkSnapshot) => void>();
let navigatorOnline = typeof navigator === 'undefined' ? true : navigator.onLine;
let apiReachable: boolean | null = null;
let syncing = false;
let syncFailed = false;
let syncError = '';
let pending = 0;
let lastSyncAt: string | null = null;
let watchTimer = 0;
let watchers = 0;

export function classifyLink(input: {
  navigatorOnline: boolean;
  apiReachable: boolean | null;
  syncing: boolean;
  syncFailed: boolean;
}): LinkPhase {
  if (input.syncing && input.navigatorOnline && input.apiReachable !== false) return 'syncing';
  if (!input.navigatorOnline) return 'offline';
  if (input.apiReachable === false) return 'api_down';
  if (input.syncFailed) return 'sync_failed';
  return 'online';
}

export function currentPhase(): LinkPhase {
  return classifyLink({ navigatorOnline, apiReachable, syncing, syncFailed });
}

export function getLinkSnapshot(): LinkSnapshot {
  return { phase: currentPhase(), pending, lastSyncAt, syncError };
}

export function linkStatusText(snap: LinkSnapshot = getLinkSnapshot()): { label: string; detail: string } {
  const waiting =
    snap.pending > 0
      ? `${snap.pending} saved sale${snap.pending === 1 ? '' : 's'} waiting`
      : '';
  if (snap.phase === 'syncing') {
    return { label: 'Syncing', detail: waiting || 'Sending saved sales' };
  }
  if (snap.phase === 'sync_failed') {
    return {
      label: 'Sync failed',
      detail: snap.syncError || 'Saved sales stay on this device and will be sent automatically.',
    };
  }
  if (snap.phase === 'api_down') {
    return {
      label: 'Offline',
      detail: waiting || 'The server did not respond. A prepared Point of Sale can keep selling.',
    };
  }
  if (snap.phase === 'offline') {
    return { label: 'Offline', detail: waiting || 'No internet connection.' };
  }
  if (waiting) {
    return { label: 'Online', detail: `${waiting}. They will be sent automatically.` };
  }
  const sent = snap.lastSyncAt ? 'Saved sales are up to date.' : 'Server reachable.';
  return { label: 'Online', detail: sent };
}

export function explainOfflineAccess(
  envelope: OfflineGrantShape | null | undefined,
  now = Date.now()
): { prepared: boolean; message: string } {
  if (!envelope?.grant_id || !envelope.user_id || !envelope.tenant_id) {
    return { prepared: false, message: UNPREPARED_OFFLINE };
  }
  const until = envelope.offline_valid_until ? new Date(envelope.offline_valid_until).getTime() : 0;
  if (envelope.revoked_at || !Number.isFinite(until) || until <= now) {
    return { prepared: false, message: EXPIRED_OFFLINE };
  }
  return { prepared: true, message: PREPARED_OFFLINE };
}

export const CATALOG_NOT_SAVED = 'The product list was not saved on this device.';

export const PREPARING_OFFLINE = 'Preparing this device for offline selling.';

/** Shown after grant, catalog, and IndexedDB all succeed. */
export const OFFLINE_READY = 'Offline ready';

const REVOKED_PANEL =
  'Not prepared. Offline selling was turned off on this device. Sign in online. Saved sales stay on this device.';

/**
 * Till status for offline selling.
 * The exact unprepared sentence is used only when this device still has no grant.
 */
export function offlineSellingStatus(input: {
  grantId?: string | null;
  catalogSaved?: boolean;
  valid?: boolean;
  revoked?: boolean;
  online?: boolean;
  preparing?: boolean;
  failure?: string | null;
}): string {
  const hasGrant = Boolean(input.grantId);
  if (hasGrant && input.catalogSaved && input.valid) return OFFLINE_READY;
  if (input.preparing) return PREPARING_OFFLINE;
  if (hasGrant && input.valid === false) {
    return input.revoked ? REVOKED_PANEL : `Not prepared. ${EXPIRED_OFFLINE}`;
  }
  if (!hasGrant) {
    const failure = String(input.failure || '').trim();
    if (input.online && !failure) return PREPARING_OFFLINE;
    if (!failure) return UNPREPARED_OFFLINE;
    return failure.includes(UNPREPARED_OFFLINE) ? failure : `${failure} ${UNPREPARED_OFFLINE}`;
  }
  const failure = String(input.failure || '').trim();
  if (failure && !failure.includes(UNPREPARED_OFFLINE)) return failure;
  return CATALOG_NOT_SAVED;
}

/** Plain prepare failure. The unprepared sentence is appended only when no grant was saved. */
export function describePrepareFailure(err: unknown, hasGrant: boolean): string {
  const raw = (err instanceof Error ? err.message : String(err || '')).trim();
  const reason =
    raw.split(UNPREPARED_OFFLINE).join('').replace(/\s+/g, ' ').trim() ||
    (hasGrant ? CATALOG_NOT_SAVED : 'Offline selling could not be prepared.');
  if (hasGrant || reason.includes(UNPREPARED_OFFLINE)) return reason;
  return `${reason} ${UNPREPARED_OFFLINE}`;
}

function emit() {
  const snap = getLinkSnapshot();
  listeners.forEach((fn) => fn(snap));
}

export function subscribeLink(fn: (snap: LinkSnapshot) => void): () => void {
  listeners.add(fn);
  fn(getLinkSnapshot());
  return () => listeners.delete(fn);
}

export function noteQueue(nextPending: number, nextLastSyncAt: string | null) {
  pending = nextPending;
  lastSyncAt = nextLastSyncAt;
  emit();
}

export function noteSyncStart() {
  syncing = true;
  syncFailed = false;
  syncError = '';
  emit();
}

export function noteSyncEnd(error?: string) {
  syncing = false;
  syncFailed = Boolean(error);
  syncError = error || '';
  emit();
}

export async function probeApi(timeoutMs = 4000): Promise<'online' | 'offline' | 'api_down'> {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return 'offline';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch('/api/v1/health', {
      method: 'GET',
      cache: 'no-store',
      signal: controller.signal,
    });
    return res.ok ? 'online' : 'api_down';
  } catch {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) return 'offline';
    return 'api_down';
  } finally {
    clearTimeout(timer);
  }
}

export async function refreshLink(): Promise<LinkPhase> {
  navigatorOnline = typeof navigator === 'undefined' ? true : navigator.onLine;
  if (!navigatorOnline) {
    apiReachable = null;
    emit();
    return currentPhase();
  }
  const probed = await probeApi();
  apiReachable = probed === 'online';
  if (apiReachable) syncFailed = syncFailed && !syncing;
  emit();
  return currentPhase();
}

export function startLinkWatch(intervalMs = 20000): () => void {
  watchers += 1;
  if (!watchTimer && typeof window !== 'undefined') {
    void refreshLink();
    watchTimer = window.setInterval(() => {
      void refreshLink();
    }, intervalMs);
  }
  return () => {
    watchers = Math.max(0, watchers - 1);
    if (watchers === 0 && watchTimer) {
      window.clearInterval(watchTimer);
      watchTimer = 0;
    }
  };
}
