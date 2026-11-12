/**
 * Restaurant till sales kept on this device while the internet is down.
 *
 * Each paid sale gets its own key (offline_ref). When the connection returns the
 * till sends the queue to POST /restaurant/till/offline/sync; the server books each
 * key once, at today's menu prices, so a retry never charges the books twice.
 * A sale the server refuses stays on the device with its reason until a manager
 * deals with it. Nothing here touches the retail till's offline store.
 */

export type OfflineMethod = 'cash' | 'card' | 'mobile_money';

/** Wallet needs a live balance, so it is not offered offline. */
export const OFFLINE_METHODS: OfflineMethod[] = ['cash', 'card', 'mobile_money'];

export type OfflineLine = {
  product_id: string;
  quantity: number;
  modifier_ids: string[];
  note?: string;
  /** Shown on the device only; the server books its own menu price. */
  name: string;
  amount: number;
};

export type OfflineSale = {
  offline_ref: string;
  created_at: string;
  service_mode: 'takeaway' | 'dine_in' | 'delivery';
  payment_method: OfflineMethod;
  store_id: string | null;
  table_id: string | null;
  shift_id: string | null;
  customer_name: string | null;
  delivery_address: string | null;
  charged_total: number;
  lines: OfflineLine[];
  /** Set when the server refused it. */
  refused_reason?: string;
};

export type SyncResult = {
  offline_ref: string;
  status: 'booked' | 'already_booked' | 'refused' | 'duplicate_in_batch' | string;
  order_number?: string;
  reason?: string;
  difference?: number;
  no_shift?: boolean;
};

const QUEUE_PREFIX = 'ribdigi.restaurant.offline.queue.v1:';
const CACHE_PREFIX = 'ribdigi.restaurant.till.cache.v1:';

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function storage(): Store | null {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null;
  } catch {
    return null;
  }
}

function tenantKey(): string {
  const s = storage();
  return (s?.getItem('tenant') || '_').trim() || '_';
}

/** A failure with no HTTP status means the server was not reached. */
export function isLinkDown(err: unknown): boolean {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return true;
  const status = (err as { status?: number } | null)?.status;
  return status === undefined || status === null || status === 0;
}

export function newOfflineRef(now = Date.now(), rand?: string): string {
  const tail =
    rand ||
    (typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID().replace(/-/g, '').slice(0, 16)
      : Math.random().toString(36).slice(2, 14));
  return `rt-${now.toString(36)}-${tail}`.slice(0, 64);
}

/** Short number the cashier can read out, e.g. OFF-4F2A. */
export function offlineLabel(ref: string): string {
  return `OFF-${ref.replace(/[^A-Za-z0-9]/g, '').slice(-4).toUpperCase()}`;
}

export function readQueue(store: Store | null = storage(), tenant = tenantKey()): OfflineSale[] {
  if (!store) return [];
  try {
    const rows = JSON.parse(store.getItem(QUEUE_PREFIX + tenant) || '[]');
    return Array.isArray(rows) ? (rows as OfflineSale[]) : [];
  } catch {
    return [];
  }
}

export function writeQueue(rows: OfflineSale[], store: Store | null = storage(), tenant = tenantKey()): void {
  if (!store) return;
  if (!rows.length) store.removeItem(QUEUE_PREFIX + tenant);
  else store.setItem(QUEUE_PREFIX + tenant, JSON.stringify(rows));
}

export function enqueueSale(sale: OfflineSale, store: Store | null = storage(), tenant = tenantKey()): OfflineSale[] {
  const rows = readQueue(store, tenant).filter((row) => row.offline_ref !== sale.offline_ref);
  rows.push(sale);
  writeQueue(rows, store, tenant);
  return rows;
}

/** Sales still waiting to be sent (refused ones are kept apart for a manager). */
export function pendingSales(rows: OfflineSale[]): OfflineSale[] {
  return rows.filter((row) => !row.refused_reason);
}

/** The body the server takes: device-only fields (names, amounts) stay on the device. */
export function syncBody(rows: OfflineSale[], deviceId?: string | null) {
  return {
    ...(deviceId ? { device_id: deviceId } : {}),
    sales: rows.map((row) => ({
      offline_ref: row.offline_ref,
      created_at: row.created_at,
      service_mode: row.service_mode,
      payment_method: row.payment_method,
      store_id: row.store_id,
      table_id: row.table_id,
      shift_id: row.shift_id,
      customer_name: row.customer_name,
      delivery_address: row.delivery_address,
      charged_total: row.charged_total,
      lines: row.lines.map((line) => ({
        product_id: line.product_id,
        quantity: line.quantity,
        modifier_ids: line.modifier_ids,
        ...(line.note ? { note: line.note } : {}),
      })),
    })),
  };
}

/** Drop what the server booked; keep refusals with their reason. */
export function applySyncResults(rows: OfflineSale[], results: SyncResult[]): OfflineSale[] {
  const byRef = new Map(results.map((row) => [row.offline_ref, row]));
  const out: OfflineSale[] = [];
  for (const row of rows) {
    const result = byRef.get(row.offline_ref);
    if (!result) {
      out.push(row);
      continue;
    }
    if (result.status === 'booked' || result.status === 'already_booked' || result.status === 'duplicate_in_batch') {
      continue;
    }
    out.push({ ...row, refused_reason: result.reason || 'Refused by the server' });
  }
  return out;
}

export type TillCache = {
  saved_at: string;
  menu: unknown[];
  sold_out: string[];
  groups: unknown[];
  tables: unknown[];
  stores: unknown[];
  shift: unknown;
  prices?: PriceSheet | null;
};

export type PriceSheet = {
  service_percent: number;
  service_tax_percent: number;
  items: Record<string, { price: number; added_tax_percent: number }>;
};

function round2(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

/**
 * Total an offline bill the way the server does: dishes, the tax each dish adds,
 * the service charge, and the tax on the service charge.
 */
export function offlineBill(
  lines: { product_id: string; amount: number }[],
  sheet: PriceSheet | null | undefined,
): { subtotal: number; tax: number; service: number; total: number } {
  const subtotal = round2(lines.reduce((sum, line) => sum + Number(line.amount || 0), 0));
  let tax = 0;
  for (const line of lines) {
    const pct = Number(sheet?.items?.[line.product_id]?.added_tax_percent || 0);
    tax = round2(tax + round2((Number(line.amount || 0) * pct) / 100));
  }
  const service = round2((subtotal * Number(sheet?.service_percent || 0)) / 100);
  if (service > 0) tax = round2(tax + round2((service * Number(sheet?.service_tax_percent || 0)) / 100));
  return { subtotal, tax, service, total: round2(subtotal + service + tax) };
}

export function saveTillCache(data: Omit<TillCache, 'saved_at'>, store: Store | null = storage(), tenant = tenantKey()) {
  if (!store) return;
  try {
    store.setItem(CACHE_PREFIX + tenant, JSON.stringify({ ...data, saved_at: new Date().toISOString() }));
  } catch {
    /* storage full: the till still works online */
  }
}

export function readTillCache(store: Store | null = storage(), tenant = tenantKey()): TillCache | null {
  if (!store) return null;
  try {
    const raw = store.getItem(CACHE_PREFIX + tenant);
    return raw ? (JSON.parse(raw) as TillCache) : null;
  } catch {
    return null;
  }
}

/** A stable id for this till, so the server records which device rang an offline sale. */
export function tillDeviceId(store: Store | null = storage()): string | null {
  if (!store) return null;
  const key = 'ribdigi.restaurant.device.v1';
  let id = store.getItem(key);
  if (!id || !/^[A-Za-z0-9_-]{4,64}$/.test(id)) {
    id = `rtd-${newOfflineRef().slice(3, 40)}`.replace(/[^A-Za-z0-9_-]/g, '');
    store.setItem(key, id);
  }
  return id;
}
