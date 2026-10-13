import { api } from './api';
import { normalizeIndustry } from './industries';
import { getMe } from './meCache';

const POS_INDUSTRIES = new Set(['retail', 'restaurant', 'hotel']);
const PLATFORM_ROLES = new Set([
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
]);

type MeData = {
  role?: string;
  industry?: string | null;
  must_enroll_2fa?: boolean;
  permissions?: Record<string, string[]> | null;
};

export type CashierShift = {
  session_id?: string;
  session_number?: string;
  expected_cash?: number;
  store_id?: string | null;
  [key: string]: unknown;
};

function canRunTill(me: MeData | null | undefined): boolean {
  if (!me || me.must_enroll_2fa) return false;
  const role = String(me.role || '').toLowerCase();
  if (PLATFORM_ROLES.has(role)) return false;
  const industry = normalizeIndustry(me.industry);
  if (!industry || !POS_INDUSTRIES.has(industry)) return false;
  const perms = me.permissions;
  if (perms && typeof perms === 'object') {
    const star = perms['*'] || [];
    const pos = perms.pos || [];
    const allowed = star.includes('*') || star.includes('write') || pos.includes('write') || pos.includes('*');
    if (!allowed) return false;
  }
  return true;
}

function rememberedStoreId(stores: Array<{ id?: string }>): string {
  if (typeof window === 'undefined') return '';
  const tid = localStorage.getItem('tenant') || '';
  const saved = (localStorage.getItem(tid ? `ribdigi.activeStoreId.${tid}` : 'ribdigi.activeStoreId') || '').trim();
  if (saved && stores.some((row) => row.id === saved)) return saved;
  if (stores.length === 1) return String(stores[0]?.id || '').trim();
  return '';
}

/** Open the signed-in person's till. An existing open shift is reused. Opening cash is 0. */
export async function openShiftForSignedInUser(preferredStoreId?: string | null): Promise<CashierShift | null> {
  if (typeof window === 'undefined') return null;
  try {
    const me = await getMe();
    const data = ((me as { data?: MeData }).data || null) as MeData | null;
    if (!canRunTill(data)) return null;
    const current = await api('/pos/sessions/current');
    if (current?.data?.session_id) return current.data as CashierShift;
    let storeId = String(preferredStoreId || '').trim();
    if (!storeId) {
      const stores = await api('/pos/stores');
      const list = Array.isArray(stores?.data) ? (stores.data as Array<{ id?: string }>) : [];
      storeId = rememberedStoreId(list);
    }
    try {
      const opened = await api('/pos/sessions/open', {
        method: 'POST',
        body: JSON.stringify({
          opening_cash: 0,
          store_id: storeId.trim() || null,
        }),
      });
      return (opened?.data || null) as CashierShift | null;
    } catch (err) {
      const status = (err as { status?: number }).status;
      if (status === 409) {
        const again = await api('/pos/sessions/current');
        return (again?.data || null) as CashierShift | null;
      }
      return null;
    }
  } catch {
    return null;
  }
}

/** Count the drawer and close the open shift. Pending offline sales stay on this device. */
export async function countAndCloseOpenShift(
  actualCash: number,
  notes: string | null
): Promise<CashierShift> {
  if (typeof window === 'undefined') {
    throw new Error('Cash can only be counted in the browser.');
  }
  const current = await api('/pos/sessions/current');
  const session = current?.data as CashierShift | null;
  if (!session?.session_id) throw new Error('There is no open shift to count.');
  try {
    const offline = await import('./posOffline');
    const unsynced = (await offline.listQueuedSales()).filter(
      (rec) =>
        rec.kind === 'sale' &&
        ['pending', 'syncing', 'needs_attention'].includes(rec.state) &&
        String(rec.payload?.session_id || '') === String(session.session_id)
    );
    if (unsynced.length) {
      throw new Error(
        `Sync ${unsynced.length} offline sale${unsynced.length === 1 ? '' : 's'} before closing this shift.`
      );
    }
  } catch (err) {
    if (err instanceof Error && err.message.startsWith('Sync ')) throw err;
    throw new Error('Offline sales could not be checked. Stay online and try the count again.');
  }
  const closed = await api(`/pos/sessions/${session.session_id}/close`, {
    method: 'POST',
    body: JSON.stringify({
      actual_cash: actualCash,
      notes: notes && notes.trim() ? notes.trim() : null,
    }),
  });
  return (closed?.data || session) as CashierShift;
}

/** Close the open till when the person signs out. Counted cash matches the drawer. */
export async function closeShiftForSignOut(): Promise<void> {
  if (typeof window === 'undefined') return;
  try {
    const current = await api('/pos/sessions/current');
    const session = current?.data as CashierShift | null;
    if (!session?.session_id) return;
    try {
      const offline = await import('./posOffline');
      const unsynced = (await offline.listQueuedSales()).filter(
        (rec) =>
          rec.kind === 'sale' &&
          ['pending', 'syncing', 'needs_attention'].includes(rec.state) &&
          String(rec.payload?.session_id || '') === String(session.session_id)
      );
      if (unsynced.length) return;
    } catch {
      /* queue unreadable: server totals still authoritative */
    }
    await api(`/pos/sessions/${session.session_id}/close`, {
      method: 'POST',
      body: JSON.stringify({
        actual_cash: Number(session.expected_cash || 0),
        notes: 'Closed when the cashier signed out',
      }),
    });
  } catch {
    /* sign-out still proceeds */
  }
}
