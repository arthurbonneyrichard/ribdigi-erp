import { api } from './api';
import { normalizeIndustry } from './industries';
import { getMe } from './meCache';

const POS_INDUSTRIES = new Set(['retail', 'retail_wholesale', 'pharmacy', 'restaurant', 'hotel']);
const CASHIER_SIGN_OUT_ROLES = new Set(['cashier', 'hotel_cashier']);
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

/** Till roles that may be asked to count the drawer on Log out. */
export function isCashierSignOutRole(role?: string | null): boolean {
  return CASHIER_SIGN_OUT_ROLES.has(String(role || '').toLowerCase());
}

/** Count-on-sign-out is cashiers only, and the company can turn it off for them. */
export function shouldPromptDrawerCountOnSignOut(me: {
  role?: string | null;
  count_drawer_on_sign_out?: boolean | null;
} | null | undefined): boolean {
  if (!me || !isCashierSignOutRole(me.role)) return false;
  return me.count_drawer_on_sign_out !== false;
}

/** Why the signed-in person cannot run a till, in words for them; '' when they can. */
export function tillBlockedReason(me: MeData | null | undefined): string {
  if (!me) return 'Your account could not be loaded. Sign out and sign in again.';
  if (me.must_enroll_2fa) return 'Set up two-step sign-in under Security before using the till.';
  const role = String(me.role || '').toLowerCase();
  if (PLATFORM_ROLES.has(role)) {
    return "This is the RIBDIGI platform account, which manages companies and does not sell. To sell, sign in with a shop's company code and a staff or owner email.";
  }
  const industry = normalizeIndustry(me.industry);
  if (!industry || !POS_INDUSTRIES.has(industry)) {
    return `This company is set up as ${industry ? industry.replace(/_/g, ' ') : 'a business without a till'}, so it has no till. Sign in to a shop's company account to sell.`;
  }
  const perms = me.permissions;
  if (perms && typeof perms === 'object') {
    const star = perms['*'] || [];
    // A restaurant rings on its own till, which needs restaurant access (not the retail POS).
    const pos = (industry === 'restaurant' ? perms.restaurant : perms.pos) || [];
    const allowed = star.includes('*') || star.includes('write') || pos.includes('write') || pos.includes('*');
    if (!allowed) return 'Your role cannot sell at the till. Ask the owner to give you till access in User Management.';
  }
  return '';
}

function canRunTill(me: MeData | null | undefined): boolean {
  return !tillBlockedReason(me);
}

/** The reason the last shift-open attempt failed, so the till can say it instead of waiting. */
let lastShiftOpenError = '';
export function shiftOpenError(): string {
  return lastShiftOpenError;
}

async function isRestaurantCompany(): Promise<boolean> {
  try {
    const me = await getMe();
    return normalizeIndustry(((me as { data?: MeData }).data || null)?.industry) === 'restaurant';
  } catch {
    return false;
  }
}

/** A restaurant till shift (restaurant_till_shifts) in the shape the shell already uses. */
function asCashierShift(row: Record<string, unknown> | null | undefined): CashierShift | null {
  if (!row || !row.id) return null;
  return { ...row, session_id: String(row.id), session_number: String(row.shift_number || '') };
}

async function currentRestaurantShift(): Promise<CashierShift | null> {
  const res = await api('/restaurant/till/shift');
  return asCashierShift(res?.data as Record<string, unknown> | null);
}

function rememberedStoreId(stores: Array<{ id?: string }>): string {
  if (typeof window === 'undefined') return '';
  const tid = localStorage.getItem('tenant') || '';
  const saved = (localStorage.getItem(tid ? `ribdigi.activeStoreId.${tid}` : 'ribdigi.activeStoreId') || '').trim();
  if (saved && stores.some((row) => row.id === saved)) return saved;
  if (stores.length === 1) return String(stores[0]?.id || '').trim();
  return '';
}

/** Open the signed-in person's till. An existing open shift is reused. Login and the shell send 0. A hotel shop shift or restaurant till starts only when startShift is true. */
export async function openShiftForSignedInUser(
  preferredStoreId?: string | null,
  openingCash = 0,
  startShift = false
): Promise<CashierShift | null> {
  if (typeof window === 'undefined') return null;
  try {
    const me = await getMe();
    const data = ((me as { data?: MeData }).data || null) as MeData | null;
    lastShiftOpenError = tillBlockedReason(data);
    if (lastShiftOpenError) return null;
    if (normalizeIndustry(data?.industry) === 'restaurant') {
      // Restaurant shifts live on the restaurant till; they never open a retail POS session.
      const open = await currentRestaurantShift();
      if (open || !startShift) return open;
      const opened = await api('/restaurant/till/shift/open', {
        method: 'POST',
        body: JSON.stringify({
          opening_cash: Number(openingCash) > 0 ? Number(openingCash) : 0,
          store_id: String(preferredStoreId || '').trim() || null,
        }),
      });
      return asCashierShift(opened?.data as Record<string, unknown> | null);
    }
    const current = await api('/pos/sessions/current');
    const hotel = normalizeIndustry(data?.industry) === 'hotel';
    if (hotel && !startShift) {
      lastShiftOpenError = '';
      return (current?.data?.session_id ? current.data : null) as CashierShift | null;
    }
    if (current?.data?.session_id) {
      const sess = current.data as CashierShift;
      const want = Number(openingCash);
      const unused =
        !Number(sess.sale_count || 0) &&
        !Number(sess.cash_in || 0) &&
        !Number(sess.cash_out || 0);
      if (want > 0 && unused) return setOpeningCash(want);
      return sess;
    }
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
          // Auto-open and sign-in still send opening_cash: 0
          opening_cash: Number(openingCash) > 0 ? Number(openingCash) : 0,
          store_id: storeId.trim() || null,
        }),
      });
      return (opened?.data || null) as CashierShift | null;
    } catch (err) {
      const status = (err as { status?: number }).status;
      if (status === 409) {
        const again = await api('/pos/sessions/current');
        if (again?.data) {
          const sess = again.data as CashierShift;
          const want = Number(openingCash);
          const unused =
            !Number(sess.sale_count || 0) &&
            !Number(sess.cash_in || 0) &&
            !Number(sess.cash_out || 0);
          if (want > 0 && unused) return setOpeningCash(want);
          return sess;
        }
      }
      lastShiftOpenError =
        (err instanceof Error && err.message) || 'Your shift could not be started. Sign out and sign in again.';
      return null;
    }
  } catch (err) {
    lastShiftOpenError =
      (err instanceof Error && err.message) || 'Your shift could not be started. Sign out and sign in again.';
    return null;
  }
}

/** Set opening float on an unused open shift (no sales or cash movements yet). */
export async function setOpeningCash(amount: number): Promise<CashierShift> {
  if (typeof window === 'undefined') {
    throw new Error('Opening cash can only be set in the browser.');
  }
  const current = await api('/pos/sessions/current');
  const session = current?.data as CashierShift | null;
  if (!session?.session_id) throw new Error('There is no open shift to update.');
  const updated = await api(`/pos/sessions/${session.session_id}/opening-cash`, {
    method: 'PATCH',
    body: JSON.stringify({ opening_cash: amount }),
  });
  return (updated?.data || session) as CashierShift;
}

/** Count the drawer and close the open shift. Pending offline sales stay on this device. */
export async function countAndCloseOpenShift(
  actualCash: number,
  notes: string | null
): Promise<CashierShift> {
  if (typeof window === 'undefined') {
    throw new Error('Cash can only be counted in the browser.');
  }
  if (await isRestaurantCompany()) {
    const open = await currentRestaurantShift();
    if (!open?.session_id) throw new Error('There is no open shift to count.');
    const closed = await api(`/restaurant/till/shift/${open.session_id}/close`, {
      method: 'POST',
      body: JSON.stringify({ counted_cash: actualCash, notes: notes && notes.trim() ? notes.trim() : null }),
    });
    return asCashierShift(closed?.data as Record<string, unknown> | null) || open;
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
      closing_cash: actualCash,
      notes: notes && notes.trim() ? notes.trim() : null,
    }),
  });
  try {
    // A closed shift should not keep this till's offline stock slice away from other tills.
    const offline = await import('./posOffline');
    await offline.releaseOfflineGrantIfIdle(api);
  } catch {
    /* the slice expires on its own */
  }
  return (closed?.data || session) as CashierShift;
}

/** Current open shift, or null. Used by Log out to ask for a cash count. */
export async function peekOpenCashierShift(): Promise<CashierShift | null> {
  if (typeof window === 'undefined') return null;
  try {
    if (await isRestaurantCompany()) return await currentRestaurantShift();
    const current = await api('/pos/sessions/current');
    const session = current?.data as CashierShift | null;
    return session?.session_id ? session : null;
  } catch {
    return null;
  }
}

/** Idle or forced sign-out leaves the shift open so a zero-variance count is not invented. */
export async function closeShiftForSignOut(): Promise<void> {
  return;
}
