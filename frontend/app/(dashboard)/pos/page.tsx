'use client';

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, apiFetch, isAbortError } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { getPrefetched } from '../../../lib/prefetchCache';
import { pageLoadStarted } from '../../../lib/navTiming';
import { useStoreContext } from '../../../lib/storeContext';
import { isHotelIndustry, tenantIsMultiStore } from '../../../lib/tenantNav';
import { normalizeIndustry } from '../../../lib/industries';
import { formatDate, formatWhen, plainLabel } from '../../../lib/format';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';
import { openShiftForSignedInUser } from '../../../lib/cashierShift';
import { setPosDrawerBridge } from '../../../lib/posDrawerBridge';
import { openReceiptPrintWindow } from '../../../lib/posReceiptPrint';
import { consumeWedgeKey, looksLikeBarcode, type WedgeBuffer } from '../../../lib/posWedgeScan';
import {
  allocationRemainingFor,
  cacheSnapshot,
  countPendingSales,
  enqueueOfflineQuote,
  enqueueOfflineSale,
  formatCacheAge,
  getCachedCatalogMeta,
  getCachedCustomers,
  getCachedProducts,
  getOrCreateDeviceId,
  getOfflineAuthEnvelope,
  getSnapshot,
  hydrateDeviceId,
  isOfflineAuthValid,
  listQueuedSales,
  migrateLegacyQueueStates,
  newClientRequestId,
  revalidateOfflineAccess,
  searchCachedProducts,
  touchLastOnline,
  type QueuedSale,
} from '../../../lib/posOffline';
import PosOfflinePanel, { type OfflineStatus } from '../../../components/PosOfflinePanel';

const OFFLINE_TENDERS = new Set(['cash', 'mobile_money', 'card', 'bank_transfer', 'credit']);

function hasPerm(
  me: { permissions?: Record<string, string[]> | null } | null | undefined,
  module: string,
  action: string
) {
  const perms = me?.permissions;
  if (!perms || typeof perms !== 'object') return false;
  const star = perms['*'] || [];
  if (star.includes('*') || star.includes(action)) return true;
  const mod = perms[module] || [];
  return mod.includes(action) || mod.includes('*');
}

function escapeHtml(value: unknown) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) =>
    ch === '&' ? '&amp;' : ch === '<' ? '&lt;' : ch === '>' ? '&gt;' : ch === '"' ? '&quot;' : '&#39;'
  );
}

function printProvisionalReceipt(rec: QueuedSale, lines: Array<{ name: string; quantity: number; unit: number }>, storeName: string) {
  const payload = rec.payload as Record<string, unknown>;
  const payments = Array.isArray(payload.payments)
    ? (payload.payments as Array<{ payment_method: string; amount: number }>)
    : [{ payment_method: String(payload.payment_method || 'cash'), amount: Number(payload.total || 0) }];
  const rows = lines
    .map(
      (l) =>
        `<tr><td>${escapeHtml(l.name)}</td><td style="text-align:right">${l.quantity}</td><td style="text-align:right">${(l.unit * l.quantity).toFixed(2)}</td></tr>`
    )
    .join('');
  const tenders = payments
    .map((p) => `<div>${escapeHtml(posPayLabel(p.payment_method))}: ${Number(p.amount || 0).toFixed(2)}</div>`)
    .join('');
  return openReceiptPrintWindow(
    `<!doctype html><html><head><title>${escapeHtml(rec.local_receipt_number)}</title>` +
      '<style>@page{margin:0;size:80mm auto}html,body{margin:0;padding:0;width:100%}body{display:flex;justify-content:center}' +
      '.slip{width:72mm;max-width:80mm;margin:2mm auto;font-family:\'Courier New\',ui-monospace,monospace;font-weight:700;font-size:13px;line-height:1.15}' +
      'h3,p,.mid{text-align:center;margin:0}p{font-size:10px;margin:2mm 0}' +
      'table{width:100%;border-collapse:collapse}td{font-size:13px;font-weight:700;padding:1px 0;vertical-align:top}' +
      'td:nth-child(2),td:last-child{text-align:right;white-space:nowrap;padding-left:2mm}</style></head><body><div class="slip">' +
      `<h3>${escapeHtml(storeName)}</h3>` +
      '<p><strong>Receipt copy — not the final receipt yet</strong><br/>The final receipt number is issued when this sale is sent.</p>' +
      `<div class="mid">No: ${escapeHtml(rec.local_receipt_number)}</div><div class="mid">${escapeHtml(formatWhen(rec.created_at) || '')}</div>` +
      `<table>${rows}</table><hr/><div class="mid"><strong>Total ${Number(payload.total || 0).toFixed(2)}</strong></div><div class="mid">${tenders}</div>` +
      '</div></body></html>',
    ''
  );
}

function posPayLabel(method?: string | null) {
  const key = String(method || 'cash');
  if (key === 'mobile_money') return 'Mobile Money (MoMo)';
  if (key === 'gift_card') return 'Gift card';
  if (key === 'loyalty') return 'Loyalty points';
  return key.split('_').join(' ');
}

type TaxComponent = {
  code?: string;
  name?: string;
  rate: number;
  basis?: string;
};

type Product = {
  id: string;
  product_id?: string;
  variant_id?: string | null;
  name: string;
  sku: string;
  barcode?: string | null;
  selling_price: number;
  cost_price?: number | null;
  stock_qty: number;
  is_low_stock?: boolean;
  is_out_of_stock?: boolean;
  kind?: string;
  has_image?: boolean;
  rx_only?: boolean;
  nearest_expiry_date?: string | null;
  tax_rate_pct?: number;
  tax_pricing_mode?: string;
  tax_reverse_charge?: boolean;
  tax_components?: TaxComponent[] | null;
  batch_tracked?: boolean;
  saleable_lots?: Array<{ expiry_date?: string | null; quantity?: number }>;
  offline_block_reason?: string | null;
};

function offlineDispenseBlock(product: Product): string | null {
  if (product.offline_block_reason) return product.offline_block_reason;
  if (product.rx_only) return `${product.name} needs a prescription check and cannot be sold offline`;
  if (product.batch_tracked) {
    const today = new Date().toISOString().slice(0, 10);
    const qty = (product.saleable_lots || [])
      .filter((lot) => !lot.expiry_date || lot.expiry_date >= today)
      .reduce((sum, lot) => sum + (Number(lot.quantity) || 0), 0);
    if (qty <= 0) return `${product.name} has no unexpired, released batch on this device`;
  }
  return null;
}

function canWriteCredit(me: { permissions?: Record<string, string[]> | null } | null | undefined) {
  const perms = me?.permissions;
  if (!perms || typeof perms !== 'object') return false;
  const star = perms['*'] || [];
  if (star.includes('*') || star.includes('write')) return true;
  const credit = perms.credit || [];
  return credit.includes('write') || credit.includes('*') || credit.includes('approve');
}

type CartItem = Product & {
  quantity: number;
};

type OpenPrescription = {
  id: string;
  rx_number: string;
  status: string;
  customer_id?: string | null;
  customer_name?: string | null;
};

type Customer = {
  id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
  status?: string | null;
  profile_type?: string | null;
  credit_limit?: number;
  balance?: number;
  customer_group_id?: string | null;
  customer_group?: { id: string; name: string; discount_percent: number } | null;
};

type Store = {
  id: string;
  name: string;
  code: string;
  address?: string | null;
  phone?: string | null;
};

type Session = {
  session_id: string;
  session_number: string;
  status: string;
  opening_cash: number;
  expected_cash: number;
  cash_sales: number;
  cash_in?: number;
  cash_out?: number;
  card_sales: number;
  other_sales: number;
  total_sales: number;
  sale_count: number;
  actual_cash?: number | null;
  variance?: number | null;
  store_id?: string | null;
  store_name?: string | null;
  store_address?: string | null;
  cashier_id?: string | null;
  cashier_name?: string | null;
  opened_at?: string | null;
};

function money(n: number) {
  return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
}

/** Turn movement API failures into a till-friendly sentence. */
function plainCashMoveError(err: unknown): string {
  const raw = err instanceof Error ? err.message.trim() : '';
  if (!raw) return 'Could not record the cash movement. Try again.';
  let text = raw.replace(/^(amount|reason|movement_type):\s*/i, '').trim();
  const lower = text.toLowerCase();
  if (
    lower.includes('greater than 0') ||
    lower.includes('must be positive') ||
    lower.includes('positive cash')
  ) {
    return 'Enter an amount greater than zero.';
  }
  if (
    lower.includes('narrative') ||
    lower.includes('reason is required') ||
    lower.includes('cash movement reason')
  ) {
    return 'Enter a short reason (at least 3 characters).';
  }
  if (lower.includes('not your pos session') || lower.includes('do not have permission')) {
    return 'You do not have permission to change this drawer.';
  }
  if (lower.includes('session is not open')) {
    return 'This shift is not open.';
  }
  if (lower.includes('email, role, phone')) {
    return 'Check the amount and the reason, then try again.';
  }
  if (!/[.!?]$/.test(text)) text = `${text}.`;
  return text;
}

/** Mirror backend `compute_tax_amounts` for cart preview (cashiers lack tax:read). */
function computeLineTaxAmounts(
  amount: number,
  ratePct: number,
  pricingMode = 'exclusive',
  reverseCharge = false,
  components?: TaxComponent[] | null
): { net: number; tax: number; gross: number } {
  const base = Number(amount) || 0;
  const mode = (pricingMode || 'exclusive').toLowerCase();
  const comps = Array.isArray(components) && components.length ? components : null;
  let rate = Number(ratePct) || 0;
  if (comps) {
    const netSum = comps
      .filter((c) => (c.basis || 'net') === 'net')
      .reduce((s, c) => s + (Number(c.rate) || 0), 0);
    rate = netSum > 0 ? netSum : comps.reduce((s, c) => s + (Number(c.rate) || 0), 0);
  }
  if (base <= 0) return { net: Math.round(base * 100) / 100, tax: 0, gross: Math.round(base * 100) / 100 };

  let net: number;
  let tax: number;
  let gross: number;
  if (comps) {
    if (mode === 'inclusive') {
      if (rate <= 0) {
        net = Math.round(base * 100) / 100;
        return { net, tax: 0, gross: net };
      }
      gross = Math.round(base * 100) / 100;
      tax = Math.round((gross * rate) / (100 + rate) * 100) / 100;
      net = Math.round((gross - tax) * 100) / 100;
    } else {
      net = Math.round(base * 100) / 100;
      let running = net;
      tax = 0;
      for (const c of comps) {
        const part =
          (c.basis || 'net') === 'compound'
            ? Math.round((running * (Number(c.rate) || 0)) / 100 * 100) / 100
            : Math.round((net * (Number(c.rate) || 0)) / 100 * 100) / 100;
        running += part;
        tax += part;
      }
      tax = Math.round(tax * 100) / 100;
      gross = Math.round((net + tax) * 100) / 100;
    }
  } else if (rate <= 0) {
    net = Math.round(base * 100) / 100;
    tax = 0;
    gross = net;
  } else if (mode === 'inclusive') {
    gross = Math.round(base * 100) / 100;
    tax = Math.round((gross * rate) / (100 + rate) * 100) / 100;
    net = Math.round((gross - tax) * 100) / 100;
  } else {
    net = Math.round(base * 100) / 100;
    tax = Math.round((net * rate) / 100 * 100) / 100;
    gross = Math.round((net + tax) * 100) / 100;
  }
  if (reverseCharge) gross = net;
  return { net, tax, gross };
}

const ProductThumb = memo(function ProductThumb({
  productId,
  hasImage,
  name,
}: {
  productId: string;
  hasImage?: boolean;
  name: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [visible, setVisible] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    if (typeof IntersectionObserver === 'undefined') {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          io.disconnect();
        }
      },
      { rootMargin: '120px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    let alive = true;
    let objectUrl: string | null = null;
    async function load() {
      if (!visible || !hasImage || !productId) {
        setSrc(null);
        return;
      }
      try {
        const res = await apiFetch(`/products/${productId}/image`);
        if (!res.ok) throw new Error('no image');
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (alive) setSrc(objectUrl);
      } catch {
        if (alive) setSrc(null);
      }
    }
    load();
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [productId, hasImage, visible]);

  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img className="tpos-thumb-img" src={src} alt={name} draggable={false} loading="lazy" />
    );
  }

  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || '')
    .join('');

  return (
    <div className="tpos-thumb-fallback" aria-hidden ref={rootRef}>
      <span>{initials || '?'}</span>
    </div>
  );
});

export default function Page() {
  useCompanyFormat();
  const [q, setQ] = useState('');
  const [rows, setRows] = useState<Product[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [shifts, setShifts] = useState<any[]>([]);
  const [shiftManageFilter, setShiftManageFilter] = useState<'all' | 'open' | 'closed'>('all');
  const [receiptPaper, setReceiptPaper] = useState('80mm');
  const [posSalePrefix, setPosSalePrefix] = useState('');
  const [posSaleNext, setPosSaleNext] = useState('');
  const [posSessionPrefix, setPosSessionPrefix] = useState('');
  const [posSessionNext, setPosSessionNext] = useState('');
  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState('');
  const { storeId: ctxStoreId, setStoreId: setCtxStoreId } = useStoreContext();
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [canCreditSale, setCanCreditSale] = useState(false);
  const [splitTender, setSplitTender] = useState(false);
  const [cashTender, setCashTender] = useState('');
  const [cardTender, setCardTender] = useState('');
  const [splitOtherMethod, setSplitOtherMethod] = useState<'card' | 'mobile_money' | 'bank_transfer'>('card');
  const [amountPaidNow, setAmountPaidNow] = useState('');
  const [depositMethod, setDepositMethod] = useState('cash');
  const [receiptTo, setReceiptTo] = useState('');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [creditOverrideReason, setCreditOverrideReason] = useState('');
  const [canOpenDrawer, setCanOpenDrawer] = useState(false);
  const [cashMoveAmount, setCashMoveAmount] = useState('');
  const [cashMoveReason, setCashMoveReason] = useState('');
  const [cashMoveBusy, setCashMoveBusy] = useState<null | 'cash_in' | 'cash_out'>(null);
  const [cashMoveError, setCashMoveError] = useState('');
  const [cartDiscount, setCartDiscount] = useState('');
  const [cartDiscountType, setCartDiscountType] = useState<'fixed' | 'percent'>('fixed');
  const [couponCode, setCouponCode] = useState('');
  const [isPharmacy, setIsPharmacy] = useState(false);
  const [tradeBanner, setTradeBanner] = useState('');
  const [rxList, setRxList] = useState<OpenPrescription[]>([]);
  const [prescriptionId, setPrescriptionId] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [lastSale, setLastSale] = useState<{
    id: string;
    reference: string;
    payment_status?: string;
    paid_amount?: number;
    balance_due?: number;
    invoice_number?: string | null;
    offline?: QueuedSale;
  } | null>(null);
  const [reprintTarget, setReprintTarget] = useState<
    | { offline: true; rec: QueuedSale; lines: Array<{ name: string; quantity: number; unit: number }>; store: string }
    | { offline: false; id: string }
    | null
  >(null);
  const [payAsReprint, setPayAsReprint] = useState(false);
  const [showReceiptEmailSms, setShowReceiptEmailSms] = useState(false);
  const printedPayIds = useRef<Set<string>>(new Set());
  const wedgeLookupRef = useRef<(query: string) => void>(() => undefined);
  const wedgeState = useRef<WedgeBuffer>({ buf: '', last: 0 });
  const [busy, setBusy] = useState(false);
  const [cashierName, setCashierName] = useState('');
  const [hideStorePicker, setHideStorePicker] = useState(false);
  const [receiptBusy, setReceiptBusy] = useState('');
  const [shiftReport, setShiftReport] = useState<any>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [shiftBusy, setShiftBusy] = useState(false);
  const [online, setOnline] = useState(
    typeof navigator === 'undefined' ? true : navigator.onLine
  );
  const [pendingOffline, setPendingOffline] = useState(0);
  const [catalogCachedAt, setCatalogCachedAt] = useState<string | null>(null);
  const [meId, setMeId] = useState('');
  const [tenantId, setTenantId] = useState('');
  const [industryCode, setIndustryCode] = useState('');
  const [canApproveOffline, setCanApproveOffline] = useState(false);
  const [canWriteQuotes, setCanWriteQuotes] = useState(false);
  const [offlineStatus, setOfflineStatus] = useState<OfflineStatus | null>(null);
  const [offlineRefresh, setOfflineRefresh] = useState(0);
  const [allocationOverride, setAllocationOverride] = useState(false);
  const [bootedOffline, setBootedOffline] = useState(false);
  const bumpOffline = useCallback(() => setOfflineRefresh((n) => n + 1), []);
  const handleOfflineStatus = useCallback((s: OfflineStatus) => {
    setOfflineStatus(s);
    setPendingOffline(s.summary.pending + s.summary.syncing + s.summary.needs_attention);
  }, []);
  const offlineValid = isOfflineAuthValid(offlineStatus?.envelope || null);
  const offlinePerms = offlineStatus?.envelope?.permissions || [];
  const checkoutReqRef = useRef<string | null>(null);
  const cashMoveLock = useRef(false);
  const browseGen = useRef(0);
  const skipEmptyBrowse = useRef(false);
  const prevQ = useRef(q);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [bootLoading, setBootLoading] = useState(true);

  const groupDiscountPct = useMemo(() => {
    const match = customers.find((c) => c.id === customerId);
    return Math.max(0, Math.min(100, Number(match?.customer_group?.discount_percent || 0)));
  }, [customers, customerId]);

  function groupUnitPrice(listPrice: number) {
    return Math.round(Number(listPrice) * (1 - groupDiscountPct / 100) * 100) / 100;
  }

  const cartTotals = useMemo(() => {
    let subtotal = 0;
    let tax = 0;
    for (const c of cart) {
      const unit = groupUnitPrice(Number(c.selling_price));
      const taxable = Math.max(0, Math.round(unit * c.quantity * 100) / 100);
      const amounts = computeLineTaxAmounts(
        taxable,
        Number(c.tax_rate_pct) || 0,
        c.tax_pricing_mode || 'exclusive',
        Boolean(c.tax_reverse_charge),
        c.tax_components
      );
      subtotal += amounts.net;
      if (!c.tax_reverse_charge) tax += amounts.tax;
    }
    subtotal = Math.round(subtotal * 100) / 100;
    tax = Math.round(tax * 100) / 100;
    const maxDiscount = Math.round((subtotal + tax) * 100) / 100;
    const discount =
      cartDiscountType === 'percent'
        ? Math.round((maxDiscount * Math.max(0, Math.min(100, Number(cartDiscount) || 0))) / 100 * 100) / 100
        : Math.max(0, Number(cartDiscount) || 0);
    const due = Math.max(0, Math.round((subtotal + tax - discount) * 100) / 100);
    return { subtotal, tax, maxDiscount, discount, due };
  }, [cart, cartDiscount, cartDiscountType, groupDiscountPct]);
  const cartDiscountAmount = cartTotals.discount;
  const cartTotal = cartTotals.due;
  const cartCount = useMemo(() => cart.reduce((sum, c) => sum + c.quantity, 0), [cart]);
  const selectedCustomer = useMemo(
    () => customers.find((c) => c.id === customerId) || null,
    [customers, customerId],
  );
  const creditPaidNow = Math.max(0, Math.round((Number(amountPaidNow) || 0) * 100) / 100);
  const creditRemaining =
    paymentMethod === 'credit' && !splitTender
      ? Math.max(0, Math.round((cartTotal - creditPaidNow) * 100) / 100)
      : 0;
  const cashTenderAmount = Math.round((Number(cashTender) || 0) * 100) / 100;
  const otherTenderAmount = Math.round((Number(cardTender) || 0) * 100) / 100;
  const splitPaid = Math.round((cashTenderAmount + otherTenderAmount) * 100) / 100;
  const splitBalanced = Math.abs(splitPaid - cartTotal) <= 0.01;
  const splitOtherLabel =
    splitOtherMethod === 'mobile_money'
      ? 'Mobile Money'
      : splitOtherMethod === 'bank_transfer'
        ? 'Bank transfer'
        : 'Card';
  const splitError = !splitTender
    ? ''
    : cashTenderAmount <= 0 || otherTenderAmount <= 0
      ? `Enter a cash amount and a ${splitOtherLabel} amount.`
      : !splitBalanced
        ? `Cash and ${splitOtherLabel} must add up to the amount due.`
        : '';

  useEffect(() => {
    if (!splitTender) return;
    const cash = Math.round((Number(cashTender) || 0) * 100) / 100;
    const nextOther = Math.max(0, Math.round((cartTotal - cash) * 100) / 100);
    setCardTender((prev) => {
      const current = Math.round((Number(prev) || 0) * 100) / 100;
      if (Math.abs(current - nextOther) <= 0.001) return prev;
      return nextOther === 0 ? '0' : String(nextOther);
    });
    // Rebalance the other tender when the sale total changes. Typing either
    // amount already fills the remainder in the change handlers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cartTotal, splitTender]);

  useEffect(() => {
    if (!canCreditSale && paymentMethod === 'credit') setPaymentMethod('cash');
  }, [canCreditSale, paymentMethod]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      consumeWedgeKey(event, wedgeState.current, (query) => {
        wedgeLookupRef.current(query);
      });
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, []);

  useEffect(() => {
    let cancelled = false;
    api('/pos/settings')
      .then((r) => {
        if (!cancelled) setShowReceiptEmailSms(r.data?.show_receipt_email_sms === true);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  async function loadShiftHistory() {
    try {
      const list = await api('/pos/sessions');
      if (Array.isArray(list.data)) setShifts(list.data);
    } catch {
      /* recent shifts stay hidden if history cannot load */
    }
  }

  async function refreshSession() {
    const r = await api('/pos/sessions/current');
    setSession(r.data || null);
    await loadShiftHistory();
  }

  const managedShifts = shifts.filter((row) => {
    if (shiftManageFilter === 'all') return true;
    return String(row.status || '') === shiftManageFilter;
  });

  async function savePosNumbering() {
    const body: Record<string, unknown> = {};
    const pack = (prefix: string, next: string) => {
      const p = prefix.trim();
      const n = next.trim();
      if (!p && !n) return undefined;
      const out: { prefix?: string; next_number?: number } = {};
      if (p) out.prefix = p;
      if (n) out.next_number = Number(n);
      return out;
    };
    const sale = pack(posSalePrefix, posSaleNext);
    const sess = pack(posSessionPrefix, posSessionNext);
    if (sale) body.pos_sale_numbering = sale;
    if (sess) body.pos_session_numbering = sess;
    await api('/pos/settings', { method: 'PATCH', body: JSON.stringify(body) });
  }

  const browse = useCallback(async (query = '', opts?: { signal?: AbortSignal; barcode?: boolean }) => {
    const posStore = (session?.store_id || storeId).trim();
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    if (posStore) params.set('store_id', posStore);
    const gen = ++browseGen.current;
    setCatalogLoading(true);
    const fromCache = async (barcode?: boolean) => {
      const cached = (await getCachedProducts()) as unknown as Product[];
      const hits = searchCachedProducts(cached as unknown as Array<Record<string, unknown>>, query, {
        barcode,
      }) as unknown as Product[];
      const remaining = await allocationRemainingFor(hits.map((p) => p.product_id || p.id));
      const list = hits.map((p) => {
        const left = remaining[p.product_id || p.id] ?? 0;
        return { ...p, stock_qty: left, is_out_of_stock: left <= 0 };
      });
      if (gen === browseGen.current) setRows(list);
      const meta = await getCachedCatalogMeta();
      setCatalogCachedAt(meta?.cached_at || null);
      return list;
    };
    try {
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        return await fromCache(opts?.barcode);
      }
      const r = await api('/pos/products/search?' + params.toString(), {
        signal: opts?.signal,
      });
      const list = (r.data || []) as Product[];
      if (gen !== browseGen.current) return list;
      setRows(list);
      await touchLastOnline();
      return list;
    } catch (err) {
      if (isAbortError(err)) return [];
      if (!navigator.onLine || (err as { status?: number })?.status === undefined) {
        return fromCache(opts?.barcode);
      }
      throw err;
    } finally {
      if (gen === browseGen.current) setCatalogLoading(false);
    }
  }, [session?.store_id, storeId]);

  async function refreshPendingCount() {
    try {
      setPendingOffline(await countPendingSales());
    } catch {
      setPendingOffline(0);
    }
  }

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    (async () => {
      await hydrateDeviceId().catch(() => null);
      await migrateLegacyQueueStates().catch(() => 0);
      await refreshPendingCount();
      bumpOffline();
    })();
    getCachedCatalogMeta()
      .then((m) => setCatalogCachedAt(m?.cached_at || null))
      .catch(() => null);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [bumpOffline]);

  useEffect(() => {
    if (online && session && offlineStatus?.summary.synced) {
      refreshSession().catch(() => undefined);
    }
    // refresh shift totals after background sync
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online, offlineStatus?.summary.synced]);

  useEffect(() => {
    let cancelled = false;
    async function beat(sellingOnline: boolean) {
      try {
        const pending = await countPendingSales();
        await api('/pos/devices/heartbeat', {
          method: 'POST',
          body: JSON.stringify({
            device_id: getOrCreateDeviceId(),
            store_id: storeId.trim() || session?.store_id || null,
            app_version: 'web-mvp',
            pending_queue_count: pending,
            selling_online: sellingOnline,
          }),
        });
      } catch {
        /* heartbeat best-effort; a missed beat still ages into offline on the server */
      }
    }
    beat(online);
    if (!online) {
      return () => {
        cancelled = true;
      };
    }
    const t = window.setInterval(() => {
      if (!cancelled && navigator.onLine) beat(true);
    }, 60000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, [online, storeId, session?.store_id]);

  async function refreshOfflineAccess(storeForGrant: string | null) {
    if (!tenantId || !meId || !navigator.onLine) return;
    try {
      await revalidateOfflineAccess(api, {
        tenant_id: tenantId,
        user_id: meId,
        store_id: storeForGrant,
        label: stores.find((s) => s.id === storeForGrant)?.name,
      });
      const meta = await getCachedCatalogMeta();
      setCatalogCachedAt(meta?.cached_at || null);
    } catch {
      /* the panel shows offline access as not set up / expired */
    } finally {
      bumpOffline();
    }
  }

  useEffect(() => {
    const ac = new AbortController();
    const done = pageLoadStarted('pos');
    let cancelled = false;
    (async () => {
      try {
        let sess: any;
        let storeRes: any;
        let meRes: any;
        try {
          if (!navigator.onLine) throw new Error('offline');
          [sess, storeRes, meRes] = await Promise.all([
            getPrefetched('/pos/sessions/current'),
            getPrefetched('/pos/stores'),
            getMe(),
          ]);
          void cacheSnapshot('session', sess.data || null).catch(() => undefined);
          void cacheSnapshot('stores', storeRes.data || []).catch(() => undefined);
          void cacheSnapshot('me', meRes.data || null).catch(() => undefined);
          setBootedOffline(false);
        } catch (bootErr) {
          if (navigator.onLine && (bootErr as { status?: number })?.status !== undefined) throw bootErr;
          const [sSnap, stSnap, meSnap, env] = await Promise.all([
            getSnapshot<Session | null>('session').catch(() => null),
            getSnapshot<Store[]>('stores').catch(() => null),
            getSnapshot<any>('me').catch(() => null),
            getOfflineAuthEnvelope().catch(() => null),
          ]);
          if (!meSnap || !env || env.user_id !== String(meSnap.id || '')) {
            throw new Error(
              'This device has not been prepared for offline selling. Sign in online once so this device can sell offline.'
            );
          }
          sess = { data: sSnap };
          storeRes = { data: stSnap || [] };
          meRes = { data: meSnap };
          setBootedOffline(true);
        }
        if (cancelled) return;
        setMeId(String(meRes.data?.id || ''));
        setTenantId(String(meRes.data?.tenant_id || ''));
        setIndustryCode(normalizeIndustry(meRes.data?.industry) || '');
        setCanApproveOffline(hasPerm(meRes.data, 'pos', 'approve'));
        setCanOpenDrawer(hasPerm(meRes.data, 'pos', 'write'));
        setCanWriteQuotes(hasPerm(meRes.data, 'sales', 'write'));
        const list: Store[] = storeRes.data || [];
        setStores(list);
        let chosen = '';
        if (ctxStoreId && list.some((s) => s.id === ctxStoreId)) {
          chosen = ctxStoreId;
          setStoreId(ctxStoreId);
        } else if (list.length === 1) {
          chosen = list[0].id;
          setStoreId(list[0].id);
          setCtxStoreId(list[0].id);
        }
        const tillIndustry = ['retail', 'retail_wholesale', 'pharmacy', 'restaurant', 'hotel'].includes(
          normalizeIndustry(meRes.data?.industry) || ''
        );
        if (!sess.data && navigator.onLine && tillIndustry && !cancelled) {
          const opened = await openShiftForSignedInUser(chosen || null);
          if (cancelled) return;
          if (opened?.session_id) sess = { data: opened as Session };
          else setError('Your shift could not be started. Sign out and sign in again.');
        }
        if (cancelled) return;
        setSession(sess.data || null);
        void loadShiftHistory();
        setCashierName(meRes.data?.full_name || meRes.data?.email || '');
        setCanCreditSale(canWriteCredit(meRes.data));
        setHideStorePicker(
          isHotelIndustry(meRes.data?.industry) ||
            list.length <= 1 ||
            !tenantIsMultiStore(meRes.data)
        );
        const industry = normalizeIndustry(meRes.data?.industry);
        const pharmacy = industry === 'pharmacy';
        setIsPharmacy(pharmacy);
        setTradeBanner(
          industry === 'retail_wholesale'
            ? 'Retail counter. Wholesale quotes and orders stay on Sales.'
            : industry === 'wholesale'
              ? 'Wholesale counter. Sales from this register use the wholesale channel.'
              : ''
        );
        if (pharmacy && navigator.onLine) {
          const rx = await api('/pharmacy/prescriptions').catch(() => ({ data: [] }));
          const open = (Array.isArray(rx.data) ? rx.data : []).filter((row: OpenPrescription) =>
            ['approved', 'partially_dispensed'].includes(row.status)
          );
          setRxList(open);
        }
      } catch (err: any) {
        if (!cancelled && !isAbortError(err)) setError(err.message);
      } finally {
        if (!cancelled) setBootLoading(false);
        done();
      }
    })();
    return () => {
      cancelled = true;
      ac.abort();
    };
    // setCtxStoreId intentionally omitted: stable setter (see storeContext noops);
    // including an unstable fallback previously caused a mount request storm.
  }, [ctxStoreId, setCtxStoreId]);

  useEffect(() => {
    const sessionId = String(session?.session_id || '').trim();
    const shiftOpen = String(session?.status || '').toLowerCase() === 'open';
    if (canOpenDrawer && shiftOpen && sessionId) {
      setPosDrawerBridge({ sessionId });
    } else {
      setPosDrawerBridge(null);
    }
    return () => setPosDrawerBridge(null);
  }, [canOpenDrawer, session]);

  useEffect(() => {
    if (!session) {
      setRows([]);
      return;
    }
    const ac = new AbortController();
    browse('', { signal: ac.signal }).catch((err) => {
      if (!isAbortError(err)) setError(err.message);
    });
    return () => ac.abort();
  }, [session?.session_id, session?.store_id, browse]);

  useEffect(() => {
    if (!session) return;
    const query = q.trim();
    const prev = prevQ.current.trim();
    prevQ.current = q;
    if (!query) {
      if (skipEmptyBrowse.current) {
        skipEmptyBrowse.current = false;
        return;
      }
      if (!prev) return;
    }
    if (looksLikeBarcode(query)) return;
    const ac = new AbortController();
    const timer = window.setTimeout(() => {
      browse(query, { signal: ac.signal }).catch((err) => {
        if (!isAbortError(err)) setError(err.message);
      });
    }, query ? 220 : 0);
    return () => {
      window.clearTimeout(timer);
      ac.abort();
    };
  }, [q, session?.session_id, browse]);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    const t = window.setTimeout(() => {
      const cachedCustomers = () =>
        getCachedCustomers()
          .then((rows) => {
            if (!cancelled) setCustomers(rows as unknown as Customer[]);
          })
          .catch(() => {
            if (!cancelled) setCustomers([]);
          });
      if (!navigator.onLine) {
        void cachedCustomers();
        return;
      }
      api('/customers')
        .then((r) => {
          if (!cancelled) setCustomers(r.data || []);
        })
        .catch(() => {
          void cachedCustomers();
        });
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [session?.session_id, online]);

  useEffect(() => {
    if (!online || bootedOffline) return;
    void cacheSnapshot('session', session).catch(() => undefined);
  }, [online, bootedOffline, session]);

  useEffect(() => {
    if (!online || !session || !tenantId || !meId) return;
    let cancelled = false;
    (async () => {
      const env = await getOfflineAuthEnvelope().catch(() => null);
      const stale =
        !env?.grant_id ||
        !isOfflineAuthValid(env) ||
        env.user_id !== meId ||
        env.tenant_id !== tenantId ||
        (env.store_id || null) !== (session.store_id || null) ||
        Date.now() - new Date(env.allocations_refreshed_at || env.issued_at).getTime() > 6 * 3600000;
      if (!cancelled && stale) await refreshOfflineAccess(session.store_id || null);
    })();
    return () => {
      cancelled = true;
    };
    // refreshOfflineAccess reads current state; re-run only on identity/store changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online, session?.session_id, session?.store_id, tenantId, meId]);

  function selectCustomer(id: string) {
    setCustomerId(id);
    if (!id) {
      setCustomerName('');
      return;
    }
    const match = customers.find((c) => c.id === id);
    if (match) setCustomerName(match.name);
  }

  function clearCustomer() {
    setCustomerId('');
    setCustomerName('');
  }

  async function recordCashMove(kind: 'cash_in' | 'cash_out') {
    if (!session || cashMoveLock.current) return;
    setError('');
    setCashMoveError('');
    setMessage('');
    const amt = Math.round(Number(cashMoveAmount) * 100) / 100;
    const reason = cashMoveReason.trim();
    if (!cashMoveAmount.trim() || !Number.isFinite(amt) || amt <= 0) {
      const msg = 'Enter an amount greater than zero.';
      setCashMoveError(msg);
      setError(msg);
      return;
    }
    if (reason.length < 3) {
      const msg = 'Enter a short reason (at least 3 characters).';
      setCashMoveError(msg);
      setError(msg);
      return;
    }
    cashMoveLock.current = true;
    setCashMoveBusy(kind);
    try {
      const r = await api(`/pos/sessions/${session.session_id}/movements`, {
        method: 'POST',
        body: JSON.stringify({
          movement_type: kind,
          amount: amt,
          reason,
        }),
      });
      if (r.data?.session) setSession(r.data.session);
      setCashMoveAmount('');
      setCashMoveReason('');
      setMessage(r.message || (kind === 'cash_in' ? 'Cash in recorded.' : 'Cash out recorded.'));
    } catch (err: unknown) {
      const msg = plainCashMoveError(err);
      setCashMoveError(msg);
      setError(msg);
    } finally {
      cashMoveLock.current = false;
      setCashMoveBusy(null);
    }
  }

  async function loadShiftReport() {
    if (!session) return;
    if (shiftReport) {
      setShiftReport(null);
      return;
    }
    setError('');
    setReportBusy(true);
    try {
      const r = await api(`/pos/sessions/${session.session_id}/report`);
      setShiftReport(r.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setReportBusy(false);
    }
  }

  async function applyScannedBarcode(raw: string) {
    setError('');
    const query = raw.trim();
    if (!query) return;
    try {
      // USB/Bluetooth wedge scanners type digits then Enter — accept as barcode.
      if (looksLikeBarcode(query) && !navigator.onLine) {
        const hits = await browse(query, { barcode: true });
        const exact = hits.filter(
          (p) => String(p.barcode || '').toLowerCase() === query.toLowerCase() || p.sku.toLowerCase() === query.toLowerCase()
        );
        if (exact.length === 1) {
          addToCart(exact[0]);
          setMessage('');
          skipEmptyBrowse.current = true;
          setQ('');
          return;
        }
        if (hits.length === 0) setError(`No product for ${query} in the saved catalog`);
        return;
      }
      if (looksLikeBarcode(query)) {
        const params = new URLSearchParams();
        params.set('barcode', query);
        const posStore = (session?.store_id || storeId).trim();
        if (posStore) params.set('store_id', posStore);
        const exact = await api('/pos/products/search?' + params.toString());
        const hits: Product[] = exact.data || [];
        if (hits.length === 1) {
          addToCart(hits[0]);
          setMessage('');
          skipEmptyBrowse.current = true;
          setQ('');
          return;
        }
        if (hits.length === 0) {
          // Fall back to SKU / name search for the same token.
          const soft = await browse(query);
          if (soft.length === 1) {
            addToCart(soft[0]);
            setMessage('');
            skipEmptyBrowse.current = true;
            setQ('');
            return;
          }
          if (soft.length === 0) {
            setError(`No product for barcode ${query}`);
            return;
          }
          return;
        }
        setRows(hits);
        setMessage('');
        return;
      }
      await browse(query);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function search(e?: React.FormEvent) {
    e?.preventDefault();
    await applyScannedBarcode(q);
  }

  wedgeLookupRef.current = (query: string) => {
    void applyScannedBarcode(query);
  };

  function addToCart(product: Product) {
    if (!session) {
      setError('Open a POS shift before selling');
      return;
    }
    if (!navigator.onLine) {
      const blocked = offlineDispenseBlock(product);
      if (blocked) {
        setError(blocked);
        return;
      }
    }
    const avail = lineLimit(product);
    if (avail <= 0 || (product.is_out_of_stock && avail !== Infinity)) {
      setError(
        navigator.onLine
          ? `${product.name} is out of stock at this store`
          : `${product.name} has no offline stock allocated to this device`
      );
      return;
    }
    const pid = product.product_id || product.id;
    const existing = cart.find((p) => p.id === product.id);
    if (existing && existing.quantity >= avail) {
      setError(`Only ${avail} of ${product.name} in stock at this store`);
      return;
    }
    setError('');
    setPayAsReprint(false);
    setCart((prev) => {
      const row = prev.find((p) => p.id === product.id);
      if (row) {
        if (row.quantity + 1 > avail) return prev;
        return prev.map((p) => (p.id === product.id ? { ...p, quantity: p.quantity + 1 } : p));
      }
      return [
        ...prev,
        {
          ...product,
          id: product.id,
          product_id: pid,
          variant_id: product.variant_id || null,
          quantity: 1,
        },
      ];
    });
  }

  function lineLimit(product: Product) {
    if (!navigator.onLine && allocationOverride && offlineStatus?.envelope?.can_override_allocation) return Infinity;
    return Math.max(0, Number(product.stock_qty) || 0);
  }

  function bumpQty(id: string, delta: number) {
    const line = cart.find((p) => p.id === id);
    if (!line) return;
    if (delta > 0 && line.quantity + delta > lineLimit(line)) {
      setError(`Only ${Number(line.stock_qty)} of ${line.name} in stock at this store`);
      return;
    }
    setCart((prev) =>
      prev
        .map((p) => (p.id === id ? { ...p, quantity: p.quantity + delta } : p))
        .filter((p) => p.quantity > 0)
    );
  }

  function setLineQty(id: string, raw: number) {
    if (!Number.isFinite(raw)) return;
    const line = cart.find((p) => p.id === id);
    if (!line) return;
    const quantity = Math.floor(raw);
    if (quantity > lineLimit(line)) {
      setError(`Only ${Number(line.stock_qty)} of ${line.name} in stock at this store`);
      return;
    }
    if (quantity === line.quantity) return;
    setCart((prev) =>
      prev
        .map((p) => (p.id === id ? { ...p, quantity } : p))
        .filter((p) => p.quantity > 0)
    );
  }

  function removeLine(id: string) {
    setCart((prev) => prev.filter((p) => p.id !== id));
  }

  function clearCart() {
    setCart([]);
    setCartDiscount('');
    setCouponCode('');
    setCashTender('');
    setCardTender('');
    setAmountPaidNow('');
  }

  function scalePayments(
    payments: { payment_method: string; amount: number }[],
    target: number
  ) {
    const sum = payments.reduce((s, p) => s + p.amount, 0);
    if (sum <= 0 || payments.length === 0) return payments;
    const scaled = payments.map((p) => ({
      ...p,
      amount: Math.round((p.amount / sum) * target * 100) / 100,
    }));
    const paid = scaled.reduce((s, p) => s + p.amount, 0);
    const last = scaled[scaled.length - 1];
    last.amount = Math.round((last.amount + (target - paid)) * 100) / 100;
    return scaled.filter((p) => p.amount > 0);
  }

  function enableSplit(next: boolean) {
    setSplitTender(next);
    if (next) {
      const half = Math.round((cartTotal / 2) * 100) / 100;
      setCashTender(String(half || ''));
      setCardTender(String(Math.max(0, Math.round((cartTotal - half) * 100) / 100) || ''));
    }
  }

  async function printReceiptAfterPay(
    saleId: string,
    jobs: Array<{ id?: string; purpose?: string; status?: string }>,
    offline?: { rec: QueuedSale; lines: Array<{ name: string; quantity: number; unit: number }>; store: string }
  ) {
    if (!saleId || printedPayIds.current.has(saleId)) return;
    printedPayIds.current.add(saleId);
    if (offline) {
      printProvisionalReceipt(offline.rec, offline.lines, offline.store);
      return;
    }
    const receiptJobs = (jobs || []).filter((job) => job.purpose === 'customer_receipt');
    if (!receiptJobs.length) return;
    if (receiptJobs.some((job) => job.status === 'printed')) return;
    const browserJob = receiptJobs.find((job) => job.status === 'browser_pending' && job.id);
    if (!browserJob?.id) return;
    try {
      const detail = await api(`/printers/jobs/${browserJob.id}`);
      const payload = detail.data?.payload || {};
      const opened = openReceiptPrintWindow(payload.html, payload.text || '');
      if (!opened) return;
      await api(`/printers/jobs/${browserJob.id}/browser-ack`, {
        method: 'POST',
        body: JSON.stringify({ status: 'printed' }),
      });
    } catch {
      return;
    }
  }

  async function checkout() {
    if (busy) return;
    setError('');
    setMessage('');
    setLastSale(null);
    if (!session) {
      setError('Open a POS shift before selling');
      return;
    }
    if (!cart.length) {
      setError('Cart is empty');
      return;
    }
    const selectedName = (selectedCustomer?.name || '').trim();
    const name = selectedName || customerName.trim();
    if (!splitTender && paymentMethod === 'credit' && !canCreditSale) {
      setError('Credit sales require credit permission');
      return;
    }
    if (!splitTender && paymentMethod === 'credit' && !customerId) {
      setError('Select a customer for credit sales');
      return;
    }
    if (!splitTender && paymentMethod === 'credit') {
      const paidNow = Math.round((Number(amountPaidNow) || 0) * 100) / 100;
      if (paidNow < 0) {
        setError('Amount paid cannot be negative');
        return;
      }
      if (paidNow - cartTotal > 0.01) {
        setError('Amount paid cannot exceed sale total');
        return;
      }
    }
    if (cartDiscountAmount > cartTotals.maxDiscount + 1e-9) {
      setError('Cart discount exceeds sale total');
      return;
    }
    if (isPharmacy && cart.some((c) => c.rx_only) && !prescriptionId.trim()) {
      setError('Select an approved prescription before selling Rx-only products');
      return;
    }
    const items = cart.map((c) => ({
      product_id: c.product_id || c.id,
      variant_id: c.variant_id || null,
      quantity: c.quantity,
      discount: 0,
      discount_type: 'fixed',
      discount_percent: 0,
    }));
    const body: Record<string, unknown> = {
      // trim so Complete sale (UuidIdValue session_id / party_id) does not 422
      session_id: String(session.session_id).trim(),
      discount_amount: cartDiscountType === 'percent' ? 0 : cartDiscountAmount,
      discount_type: cartDiscountType,
      discount_percent: cartDiscountType === 'percent' ? Math.max(0, Math.min(100, Number(cartDiscount) || 0)) : 0,
      coupon_code: couponCode.trim() || null,
      prescription_id: prescriptionId.trim() || null,
      status: 'completed',
      party_id: customerId.trim() || null,
      customer_name: name.trim() || null,
      items,
    };
    let payments: { payment_method: string; amount: number }[] | null = null;
    if (splitTender) {
      if (splitError) {
        setError(splitError);
        return;
      }
      payments = [
        { payment_method: 'cash', amount: cashTenderAmount },
        { payment_method: splitOtherMethod, amount: otherTenderAmount },
      ];
      body.payments = payments;
      body.payment_method = 'split';
    } else if (paymentMethod === 'credit') {
      const paidNow = Math.round((Number(amountPaidNow) || 0) * 100) / 100;
      const remaining = Math.max(0, Math.round((cartTotal - paidNow) * 100) / 100);
      if (paidNow > 0 && remaining > 0) {
        payments = [
          { payment_method: depositMethod, amount: paidNow },
          { payment_method: 'credit', amount: remaining },
        ];
        body.payments = payments;
        body.payment_method = 'split';
      } else if (paidNow > 0 && remaining <= 0) {
        body.payment_method = depositMethod;
      } else {
        body.payment_method = 'credit';
      }
    } else {
      body.payment_method = paymentMethod;
    }
    if (paymentMethod === 'loyalty' && !customerId) {
      setError('Select a customer before paying with loyalty points');
      return;
    }
    setBusy(true);
    try {
      const clientRequestId = checkoutReqRef.current || newClientRequestId();
      checkoutReqRef.current = clientRequestId;
      body.client_request_id = clientRequestId;

      // Offline tenders are recorded only; nothing is charged through a provider until the sale syncs.
      if (!navigator.onLine) {
        const methods = (payments || [{ payment_method: String(body.payment_method), amount: cartTotal }]).map(
          (p) => p.payment_method
        );
        if (body.payment_method && body.payment_method !== 'split') methods.push(String(body.payment_method));
        const blockedTender = methods.find((m) => !OFFLINE_TENDERS.has(m));
        if (blockedTender) {
          throw new Error(
            `${posPayLabel(blockedTender)} needs a live check and cannot be taken offline. Use cash, Mobile Money, card, bank transfer or credit.`
          );
        }
        if (couponCode.trim()) {
          throw new Error('Coupons need a live check. Remove the coupon or wait until you are online.');
        }
        const env = await getOfflineAuthEnvelope();
        if (!isOfflineAuthValid(env)) {
          throw new Error(
            'Offline selling on this device has expired, so new offline sales are blocked. Saved sales stay on this device and will send when you are back online.'
          );
        }
        const blocked = cart.map((c) => offlineDispenseBlock(c)).find(Boolean);
        if (blocked) throw new Error(blocked);
        const creditPart = (payments || [])
          .filter((p) => p.payment_method === 'credit')
          .reduce((s, p) => s + p.amount, 0) || (body.payment_method === 'credit' ? cartTotal : 0);
        if (creditPart > 0) {
          if (!env?.permissions.includes('credit_sale')) {
            throw new Error('Your offline access does not include credit sales.');
          }
          const limit = Number(selectedCustomer?.credit_limit || 0);
          if (limit > 0) {
            const queuedCredit = (await listQueuedSales())
              .filter(
                (rec) =>
                  rec.kind === 'sale' &&
                  ['pending', 'syncing', 'needs_attention'].includes(rec.state) &&
                  rec.payload?.party_id === customerId
              )
              .reduce((s, rec) => {
                const lines = Array.isArray(rec.payload?.payments)
                  ? (rec.payload.payments as Array<{ payment_method: string; amount: number }>)
                  : [];
                const credit = lines.filter((l) => l.payment_method === 'credit').reduce((a, l) => a + l.amount, 0);
                return s + (credit || (rec.payload?.payment_method === 'credit' ? Number(rec.payload?.total || 0) : 0));
              }, 0);
            const projected = Number(selectedCustomer?.balance || 0) + queuedCredit + creditPart;
            if (projected > limit + 0.009) {
              throw new Error(
                `This would take ${selectedCustomer?.name || 'the customer'} over their credit limit (${money(limit)}, projected ${money(projected)} including queued sales). Over-limit credit needs a manager online.`
              );
            }
          }
        }
        body.items = cart.map((c) => ({
          product_id: c.product_id || c.id,
          variant_id: c.variant_id || null,
          quantity: c.quantity,
          unit_price: groupUnitPrice(Number(c.selling_price)),
          discount: 0,
          discount_type: 'fixed',
          discount_percent: 0,
        }));
        const store = stores.find((s) => s.id === (session.store_id || storeId));
        const receiptLines = cart.map((c) => ({
          name: c.name,
          quantity: c.quantity,
          unit: groupUnitPrice(Number(c.selling_price)),
        }));
        const queued = await enqueueOfflineSale({
          tenant_id: tenantId,
          store_id: session.store_id || storeId || null,
          store_code: store?.code || 'STORE',
          user_id: meId,
          payload: { ...body, total: cartTotal },
          allocation_override: allocationOverride,
        });
        clearCart();
        clearCustomer();
        setCreditOverrideReason('');
        setSplitTender(false);
        setAllocationOverride(false);
        setLastSale({ id: queued.id, reference: queued.local_receipt_number, offline: queued });
        setReprintTarget({
          offline: true,
          rec: queued,
          lines: receiptLines,
          store: store?.name || session.store_name || '',
        });
        setPayAsReprint(true);
        void printReceiptAfterPay(queued.id, [], {
          rec: queued,
          lines: receiptLines,
          store: store?.name || session.store_name || '',
        });
        setMessage(
          `Saved on this device as ${queued.local_receipt_number}. This is not the final receipt. It will send when you are back online.`
        );
        checkoutReqRef.current = null;
        await refreshPendingCount();
        bumpOffline();
        await browse(q);
        return;
      }
      body.device_id = getOrCreateDeviceId();

      let r;
      try {
        r = await api('/pos/sales', {
          method: 'POST',
          body: JSON.stringify(body),
        });
      } catch (err: any) {
        const detail = err?.detail;
        if (
          splitTender &&
          payments &&
          detail &&
          typeof detail === 'object' &&
          detail.code === 'PAYMENT_TOTAL_MISMATCH' &&
          typeof detail.sale_total === 'number'
        ) {
          body.payments = scalePayments(payments, detail.sale_total);
          const scaled = body.payments as Array<{ payment_method: string; amount: number }>;
          setCashTender(String(scaled.find((p) => p.payment_method === 'cash')?.amount ?? ''));
          setCardTender(String(scaled.find((p) => p.payment_method !== 'cash')?.amount ?? ''));
          r = await api('/pos/sales', {
            method: 'POST',
            body: JSON.stringify(body),
          });
        } else if (
          err?.status === 409 &&
          detail &&
          typeof detail === 'object' &&
          detail.code === 'CREDIT_LIMIT_EXCEEDED'
        ) {
          const over = detail.over_by != null ? ` (over by ${detail.over_by})` : '';
          const ok = window.confirm(
            `Credit limit exceeded${over}. Complete sale with manager override?\n` +
              `Limit ${detail.credit_limit} · balance ${detail.current_balance}`,
          );
          if (!ok) throw err;
          const reason = creditOverrideReason.trim();
          if (!reason) {
            setError('Enter a credit override reason before completing an over-limit credit sale');
            return;
          }
          body.override_credit_limit = true;
          body.override_reason = reason;
          r = await api('/pos/sales', {
            method: 'POST',
            body: JSON.stringify(body),
          });
          setCreditOverrideReason('');
        } else {
          throw err;
        }
      }
      if (!r?.data?.id || !r?.data?.reference) {
        throw new Error(r?.message || 'Sale failed');
      }
      clearCart();
      clearCustomer();
      setSplitTender(false);
      setAmountPaidNow('');
      setDepositMethod('cash');
      setLastSale({
        id: r.data.id,
        reference: r.data.reference,
        payment_status: r.data.payment_status,
        paid_amount: r.data.paid_amount,
        balance_due: r.data.balance_due,
        invoice_number: r.data.invoice_number,
      });
      setReprintTarget({ offline: false, id: r.data.id });
      setPayAsReprint(true);
      const jobs = Array.isArray(r.data.print_jobs) ? r.data.print_jobs : [];
      void printReceiptAfterPay(r.data.id, jobs);
      await refreshSession();
      await browse(q);
      const statusLabel = String(r.data.payment_status || '').replace(/_/g, ' ');
      const bal = Number(r.data.balance_due || 0);
      const extra =
        r.data?.credit_limit_overridden
          ? ' (credit override)'
          : statusLabel
            ? ` · ${statusLabel}${bal > 0 ? ` · balance ${money(bal)}` : ''}`
            : '';
      setMessage(`Sale ${r.data.reference} saved${extra}`);
      checkoutReqRef.current = null;
      bumpOffline();
    } catch (err: any) {
      setMessage('');
      setLastSale(null);
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveQuoteOffline() {
    setError('');
    setMessage('');
    if (!session || !cart.length) {
      setError('Add items before saving a quote');
      return;
    }
    if (!customerId) {
      setError('Select a customer for the quote');
      return;
    }
    try {
      const store = stores.find((s) => s.id === (session.store_id || storeId));
      const quoteBody = {
        customer_id: customerId,
        sales_channel: industryCode === 'retail' ? 'retail' : 'wholesale',
        notes: 'Captured on POS while offline',
        items: cart.map((c) => ({
          product_id: c.product_id || c.id,
          variant_id: c.variant_id || null,
          quantity: c.quantity,
        })),
        total: cartTotal,
      };
      if (navigator.onLine) {
        const r = await api('/sales/quotations', {
          method: 'POST',
          body: JSON.stringify({ ...quoteBody, total: undefined, notes: null, client_request_id: newClientRequestId() }),
        });
        setMessage(`Quote ${r.data?.number || r.data?.reference || ''} saved`);
      } else {
        const rec = await enqueueOfflineQuote({
          tenant_id: tenantId,
          store_id: session.store_id || storeId || null,
          store_code: store?.code || 'STORE',
          user_id: meId,
          payload: quoteBody,
        });
        setMessage(`Quote saved offline as ${rec.local_receipt_number}. Prices are confirmed by the server when it syncs.`);
        bumpOffline();
      }
      clearCart();
    } catch (err: any) {
      setError(err.message || 'Could not save the quote');
    }
  }

  async function reprintLastReceipt() {
    if (!reprintTarget || receiptBusy) return;
    setError('');
    setReceiptBusy('reprint');
    try {
      if (reprintTarget.offline) {
        printProvisionalReceipt(reprintTarget.rec, reprintTarget.lines, reprintTarget.store);
        return;
      }
      let printed = false;
      try {
        const queued = await api('/printers/reprint', {
          method: 'POST',
          body: JSON.stringify({ source_type: 'pos_sale', source_id: reprintTarget.id }),
        });
        const jobs = Array.isArray(queued.data) ? queued.data : [];
        if (
          jobs.some(
            (job: { purpose?: string; status?: string }) =>
              job.purpose === 'customer_receipt' && job.status === 'printed'
          )
        ) {
          printed = true;
        }
        const browser = printed
          ? undefined
          : jobs.find(
              (job: { id?: string; purpose?: string; status?: string }) =>
                job.purpose === 'customer_receipt' && job.status === 'browser_pending' && job.id
            );
        if (browser?.id) {
          const detail = await api(`/printers/jobs/${browser.id}`);
          const payload = detail.data?.payload || {};
          printed = openReceiptPrintWindow(payload.html, payload.text || '');
          if (printed) {
            await api(`/printers/jobs/${browser.id}/browser-ack`, {
              method: 'POST',
              body: JSON.stringify({ status: 'printed' }),
            });
          }
        }
      } catch {
        printed = false;
      }
      if (!printed) {
        const receipt = await api(`/pos/sales/${reprintTarget.id}/receipt`);
        const opened = openReceiptPrintWindow(receipt.data?.html, receipt.data?.text || '');
        if (!opened) setError('Reprint could not open the print dialog.');
      }
    } catch (err: any) {
      setError(err?.message || 'Reprint could not open the print dialog.');
    } finally {
      setReceiptBusy('');
    }
  }

  async function sendLastReceipt(channel: 'email' | 'sms') {
    if (!lastSale) return;
    setError('');
    setReceiptBusy(channel);
    try {
      const params = new URLSearchParams({ channel });
      if (receiptTo.trim()) params.set('to', receiptTo.trim());
      await api(`/pos/sales/${lastSale.id}/receipt/send?${params.toString()}`, {
        method: 'POST',
        body: '{}',
      });
      setMessage(
        channel === 'email'
          ? `Receipt emailed${receiptTo.trim() ? ` to ${receiptTo.trim()}` : ''}`
          : `Receipt SMS sent${receiptTo.trim() ? ` to ${receiptTo.trim()}` : ''}`,
      );
    } catch (err: any) {
      setError(err.message);
    } finally {
      setReceiptBusy('');
    }
  }

  return (
    <>
      <div className="tpos">
        <header className="tpos-top">
          <div className="tpos-top-copy">
            <h1>Point of Sale</h1>
            {tradeBanner ? <p className="muted">{tradeBanner}</p> : null}
            {cashierName || !online ? (
            <p className="muted">
              {cashierName}
              {!online
                ? `${cashierName ? ' · ' : ''}Offline. Prices and stock are from the last time this device was online.`
                : ''}
              {!online && catalogCachedAt ? ` · Saved ${formatCacheAge(catalogCachedAt)}` : ''}
            </p>
            ) : null}
            {meId && tenantId ? (
              <PosOfflinePanel
                api={api as unknown as (path: string, opts?: RequestInit) => Promise<unknown>}
                online={online}
                tenantId={tenantId}
                userId={meId}
                storeId={session?.store_id || storeId.trim() || null}
                storeLabel={stores.find((s) => s.id === (session?.store_id || storeId))?.name}
                canApprove={canApproveOffline}
                refreshToken={offlineRefresh}
                onStatus={handleOfflineStatus}
                onMessage={setMessage}
                onError={setError}
              />
            ) : null}
          </div>
          <div className="tpos-shift">
            {!session ? (
              <>
                {stores.length > 0 && !hideStorePicker && (
                  <select
                    className="tpos-input"
                    value={storeId}
                    onChange={(e) => {
                      const id = e.target.value;
                      setStoreId(id);
                      setCtxStoreId(id);
                      if (!id) return;
                      setShiftBusy(true);
                      setError('');
                      void openShiftForSignedInUser(id).then((opened) => {
                        if (opened?.session_id) {
                          setSession(opened as Session);
                          void loadShiftHistory();
                        } else {
                          setError('Your shift could not be started. Sign out and sign in again.');
                        }
                        setShiftBusy(false);
                      });
                    }}
                    aria-label="POS store"
                  >
                    <option value="">Select store</option>
                    {stores.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                )}
                <span className="muted">
                  {shiftBusy || hideStorePicker || stores.length <= 1
                    ? 'Starting your shift…'
                    : 'Choose a store to start your shift.'}
                </span>
              </>
            ) : (
              <>
                <div className="tpos-shift-meta">
                  <strong>{session.session_number}</strong>
                  <span>
                    {session.opened_at ? `${formatWhen(session.opened_at)} · ` : ''}
                    {session.store_name ? `${session.store_name} · ` : ''}
                    {session.sale_count} sales · {money(Number(session.total_sales || 0))}
                  </span>
                </div>
                <button
                  type="button"
                  className="tpos-btn"
                  onClick={loadShiftReport}
                  disabled={reportBusy}
                  aria-label={shiftReport ? 'Hide POS shift report' : 'Load POS shift report'}
                >
                  {reportBusy ? 'Loading…' : shiftReport ? 'Hide report' : 'Shift report'}
                </button>
                <section className="tpos-cash" aria-label="Shift drawer cash">
                  <p className="tpos-cash-balance">
                    <span>Cash in the drawer</span>
                    <strong>{money(Number(session.expected_cash || 0))}</strong>
                    <span>
                      In {money(Number(session.cash_in || 0))} · Out {money(Number(session.cash_out || 0))}
                    </span>
                  </p>
                  <label className="tpos-cash-field">
                    Amount
                    <input
                      className="tpos-input"
                      value={cashMoveAmount}
                      onChange={(e) => setCashMoveAmount(e.target.value)}
                      inputMode="decimal"
                      placeholder="0.00"
                      autoComplete="off"
                      aria-label="Amount"
                    />
                  </label>
                  <label className="tpos-cash-field">
                    Reason
                    <input
                      className="tpos-input"
                      value={cashMoveReason}
                      onChange={(e) => setCashMoveReason(e.target.value)}
                      placeholder="Short note"
                      maxLength={200}
                      autoComplete="off"
                      aria-label="Reason"
                    />
                  </label>
                  <div className="tpos-cash-actions">
                    <button
                      type="button"
                      className="tpos-btn tpos-btn-primary"
                      disabled={!!cashMoveBusy}
                      aria-label="Cash in"
                      onClick={() => recordCashMove('cash_in')}
                    >
                      {cashMoveBusy === 'cash_in' ? 'Saving…' : 'Cash in'}
                    </button>
                    <button
                      type="button"
                      className="tpos-btn"
                      disabled={!!cashMoveBusy}
                      aria-label="Cash out"
                      onClick={() => recordCashMove('cash_out')}
                    >
                      {cashMoveBusy === 'cash_out' ? 'Saving…' : 'Cash out'}
                    </button>
                  </div>
                  {cashMoveError ? (
                    <p className="tpos-cash-error" role="alert">
                      {cashMoveError}
                    </p>
                  ) : null}
                </section>
              </>
            )}
            <details className="tpos-more">
              <summary>Receipt numbers</summary>
              <div className="tpos-more-body">
                <label className="muted">
                  Receipt paper
                  <select
                    value={receiptPaper}
                    onChange={(e) => setReceiptPaper(e.target.value)}
                    aria-label="POS receipt paper"
                  >
                    <option value="58mm">58mm</option>
                    <option value="80mm">80mm</option>
                  </select>
                </label>
                <input value={posSalePrefix} onChange={(e) => setPosSalePrefix(e.target.value)} aria-label="POS sale number prefix" placeholder="Sale prefix" />
                <input value={posSaleNext} onChange={(e) => setPosSaleNext(e.target.value)} aria-label="POS sale next number" placeholder="Next sale number" />
                <input value={posSessionPrefix} onChange={(e) => setPosSessionPrefix(e.target.value)} aria-label="POS session number prefix" placeholder="Shift prefix" />
                <input value={posSessionNext} onChange={(e) => setPosSessionNext(e.target.value)} aria-label="POS session next number" placeholder="Next shift number" />
                <button type="button" className="tpos-btn" onClick={() => savePosNumbering().catch((err) => setError(err.message || 'Could not save numbering'))}>
                  Save numbering
                </button>
                <label className="muted">
                  Recent shifts
                  <select
                    value={shiftManageFilter}
                    onChange={(e) => setShiftManageFilter(e.target.value as 'all' | 'open' | 'closed')}
                    aria-label="POS shift status filter"
                  >
                    <option value="all">All</option>
                    <option value="open">Open</option>
                    <option value="closed">Closed</option>
                  </select>
                </label>
                {managedShifts.length === 0 ? <p>No shifts yet.</p> : null}
                {managedShifts.slice(0, 8).map((row) => (
                  <p key={row.session_id || row.id} className="muted">
                    {row.session_number} · {plainLabel(row.status) || 'Open'}
                    {row.opened_at ? ` · ${formatWhen(row.opened_at)}` : ''}
                    {row.closed_at ? ` – ${formatWhen(row.closed_at)}` : ''}
                  </p>
                ))}
              </div>
            </details>
          </div>
        </header>

        {shiftReport && session && (
          <section className="tpos-report" aria-label="Shift report">
            <div className="tpos-report-head">
              <h2>Shift report</h2>
              <button type="button" className="tpos-btn" onClick={() => setShiftReport(null)} aria-label="Close POS shift report">
                Close
              </button>
            </div>
            <div className="tpos-report-kpis">
              <div>
                <span>Opening</span>
                <strong>{money(Number(shiftReport.session?.opening_cash || 0))}</strong>
              </div>
              <div>
                <span>Cash sales</span>
                <strong>{money(Number(shiftReport.payment_breakdown?.cash || 0))}</strong>
              </div>
              <div>
                <span>Card sales</span>
                <strong>{money(Number(shiftReport.payment_breakdown?.card || 0))}</strong>
              </div>
              <div>
                <span>Other</span>
                <strong>{money(Number(shiftReport.payment_breakdown?.other || 0))}</strong>
              </div>
              <div>
                <span>Discounts</span>
                <strong>{money(Number(shiftReport.summary?.discounts || 0))}</strong>
              </div>
              <div>
                <span>Returns</span>
                <strong>{money(Number(shiftReport.summary?.return_total || 0))}</strong>
              </div>
              <div>
                <span>Cash in</span>
                <strong>{money(Number(shiftReport.session?.cash_in || shiftReport.payment_breakdown?.cash_in || 0))}</strong>
              </div>
              <div>
                <span>Cash out</span>
                <strong>{money(Number(shiftReport.session?.cash_out || shiftReport.payment_breakdown?.cash_out || 0))}</strong>
              </div>
              <div>
                <span>Expected drawer</span>
                <strong>{money(Number(shiftReport.session?.expected_cash || 0))}</strong>
              </div>
              <div>
                <span>Net sales</span>
                <strong>{money(Number(shiftReport.summary?.net_sales ?? shiftReport.payment_breakdown?.total ?? 0))}</strong>
              </div>
            </div>
            <p className="muted" style={{ margin: '8px 0' }}>
              {shiftReport.session?.opened_at
                ? `Opened ${formatWhen(shiftReport.session.opened_at)} · `
                : ''}
              {shiftReport.session?.cashier_name
                ? `Cashier ${shiftReport.session.cashier_name} · `
                : ''}
              {shiftReport.summary?.sale_count ?? 0} sales · Tax{' '}
              {money(Number(shiftReport.summary?.tax || 0))} · After returns{' '}
              {money(Number(shiftReport.summary?.net_after_returns ?? 0))}
            </p>
            {(shiftReport.cash_movements || []).length > 0 ? (
              <div className="tpos-report-table-wrap">
                <table className="tpos-report-table">
                  <thead>
                    <tr>
                      <th>Cash movement</th>
                      <th>Amount</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(shiftReport.cash_movements || []).map((mv: any) => (
                      <tr key={mv.id}>
                        <td>{mv.movement_type === 'cash_in' ? 'In' : 'Out'}</td>
                        <td>{money(Number(mv.amount || 0))}</td>
                        <td>{mv.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            <div className="tpos-report-table-wrap">
              <table className="tpos-report-table">
                <thead>
                  <tr>
                    <th>Sale</th>
                    <th>Time</th>
                    <th>Customer</th>
                    <th>Pay</th>
                    <th>Discount</th>
                    <th>Tax</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {(shiftReport.sales || []).length === 0 && (
                    <tr>
                      <td colSpan={7} className="muted">
                        No sales in this shift yet.
                      </td>
                    </tr>
                  )}
                  {(shiftReport.sales || []).map((sale: any) => (
                    <tr key={sale.id}>
                      <td>{sale.reference}</td>
                      <td>{sale.created_at ? formatWhen(sale.created_at) || '—' : '—'}</td>
                      <td>{sale.customer_name || 'Walk-in'}</td>
                      <td>
                        {sale.payment_method === 'split' && sale.payments?.length
                          ? sale.payments
                              .map(
                                (p: any) =>
                                  `${posPayLabel(p.payment_method)} ${money(
                                    Number(p.amount || 0)
                                  )}`
                              )
                              .join(' + ')
                          : posPayLabel(sale.payment_method)}
                        {sale.payment_status && sale.payment_status !== 'paid'
                          ? ` · ${plainLabel(sale.payment_status)}`
                          : ''}
                      </td>
                      <td>{money(Number(sale.discounts || sale.discount_amount || 0))}</td>
                      <td>{money(Number(sale.tax || 0))}</td>
                      <td>{money(Number(sale.total || 0))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {(shiftReport.returns || []).length > 0 && (
              <div className="tpos-report-table-wrap" style={{ marginTop: 12 }}>
                <h3 style={{ margin: '0 0 8px' }}>Returns</h3>
                <table className="tpos-report-table">
                  <thead>
                    <tr>
                      <th>Return</th>
                      <th>Reason</th>
                      <th>Status</th>
                      <th>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shiftReport.returns.map((ret: any) => (
                      <tr key={ret.id}>
                        <td>{ret.return_number}</td>
                        <td>{plainLabel(ret.reason) || '—'}</td>
                        <td>{plainLabel(ret.status) || '—'}</td>
                        <td>{money(Number(ret.total_amount || 0))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        <div className="tpos-body">
          <section className="tpos-catalog" aria-label="Product catalog">
            <form className="tpos-search" onSubmit={search}>
              <input
                className="tpos-search-input"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Scan a barcode or search by name"
                disabled={!session}
                autoComplete="off"
                autoFocus
                inputMode="text"
                aria-label="Barcode scan or product search"
              />
              <button type="submit" className="tpos-btn tpos-btn-primary" disabled={!session} aria-label="POS scan or search products">
                Scan / Search
              </button>
              <button
                type="button"
                className="tpos-btn"
                disabled={!session}
                onClick={() => {
                  setQ('');
                  browse('').catch((err) => setError(err.message));
                }}
                aria-label="Browse all POS products"
              >
                All
              </button>
            </form>

            {!session && (
              <div className="tpos-empty">
                <p>{error || 'Starting your shift…'}</p>
              </div>
            )}

            {session && catalogLoading && rows.length === 0 && (
              <div className="tpos-skeleton-grid" aria-busy="true" aria-label="Loading products">
                {Array.from({ length: 8 }, (_, i) => (
                  <div key={i} className="tpos-skeleton-tile" />
                ))}
              </div>
            )}

            {session && !catalogLoading && rows.length === 0 && (
              <div className="tpos-empty">
                <p>No products match this search.</p>
              </div>
            )}

            <div className="tpos-grid">
              {rows.map((r) => {
                const out = Number(r.stock_qty) <= 0 || Boolean(r.is_out_of_stock);
                const low = Boolean(r.is_low_stock) && !out;
                const inCart = cart.find((c) => c.id === r.id)?.quantity || 0;
                return (
                  <button
                    key={r.id}
                    type="button"
                    className={`tpos-tile${out ? ' out' : ''}`}
                    onClick={() => addToCart(r)}
                    disabled={!session || out}
                    aria-label={`Add ${r.name}`}
                  >
                    <div className="tpos-thumb">
                      <ProductThumb
                        productId={r.product_id || r.id}
                        hasImage={r.has_image}
                        name={r.name}
                      />
                      {inCart > 0 && <span className="tpos-badge">{inCart}</span>}
                      {out && <span className="tpos-oos">Out</span>}
                      {low && !out && <span className="tpos-oos">Low</span>}
                      {r.kind === 'variant' ? <span className="tpos-oos">Variant</span> : null}
                    </div>
                    <div className="tpos-tile-body">
                      <strong title={r.name}>{r.name}</strong>
                      <span className="tpos-sku" title={r.sku || undefined}>
                        {r.sku}
                      </span>
                      <div className="tpos-tile-foot">
                        <span className="tpos-price-selling">
                          <span className="tpos-price-value">{money(Number(r.selling_price))}</span>
                        </span>
                        <span
                          className="tpos-stock"
                          title={
                            online
                              ? `${r.stock_qty} in stock`
                              : `Saved on this device: ${r.stock_qty}`
                          }
                        >
                          {`${r.stock_qty} left`}
                          {r.nearest_expiry_date
                            ? ` · Expires ${formatDate(r.nearest_expiry_date) || r.nearest_expiry_date}`
                            : ''}
                          {r.rx_only ? ' · Prescription' : ''}
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <aside className="tpos-cart" aria-label="Cart">
            <div className="tpos-cart-head">
              <h2>Cart</h2>
              <span className="tpos-items-badge">Items {cartCount}</span>
            </div>
            <label className="tpos-field tpos-customer">
              <span>Customer</span>
              <select
                value={customerId}
                onChange={(e) => selectCustomer(e.target.value)}
                aria-label="POS customer"
              >
                <option value="">Walk-in</option>
                {customers
                  .filter((c) => c.status !== 'inactive')
                  .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.customer_group
                      ? ` [${c.customer_group.name}${
                          c.customer_group.discount_percent
                            ? ` −${c.customer_group.discount_percent}%`
                            : ''
                        }]`
                      : ''}
                  </option>
                ))}
              </select>
            </label>
              {isPharmacy ? (
                <label className="tpos-field tpos-customer">
                  <span>Prescription (required for Rx-only)</span>
                  <select
                    value={prescriptionId}
                    onChange={(e) => {
                      const id = e.target.value;
                      setPrescriptionId(id);
                      const rx = rxList.find((r) => r.id === id);
                      if (rx?.customer_id) selectCustomer(rx.customer_id);
                    }}
                    aria-label="POS prescription"
                  >
                    <option value="">None</option>
                    {rxList.map((rx) => (
                      <option key={rx.id} value={rx.id}>
                        {rx.rx_number} · {rx.status}
                        {rx.customer_name ? ` · ${rx.customer_name}` : ''}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              {selectedCustomer ? (
                <p className="tpos-split-hint" aria-label="POS customer credit snapshot">
                  Outstanding {money(Number(selectedCustomer.balance || 0))}
                  {Number(selectedCustomer.credit_limit || 0) > 0
                    ? ` · limit ${money(Number(selectedCustomer.credit_limit))}`
                    : ' · no credit limit'}
                </p>
              ) : null}

            <div className="tpos-cart-list">
              {cart.length === 0 ? (
                <div className="tpos-cart-empty">
                  <strong>No products selected</strong>
                </div>
              ) : (
                <div className="tpos-order-head" aria-hidden>
                  <span>Product</span>
                  <span>Qty</span>
                  <span>Price</span>
                  <span />
                </div>
              )}
              {cart.map((c) => {
                const unit = groupUnitPrice(Number(c.selling_price));
                const taxable = Math.max(0, Math.round(unit * c.quantity * 100) / 100);
                const lineAmounts = computeLineTaxAmounts(
                  taxable,
                  Number(c.tax_rate_pct) || 0,
                  c.tax_pricing_mode || 'exclusive',
                  Boolean(c.tax_reverse_charge),
                  c.tax_components
                );
                const stockOut = Number(c.stock_qty) <= 0 || c.is_out_of_stock;
                return (
                  <div key={c.id} className="tpos-cart-row">
                    <div className="tpos-cart-product">
                      <strong className="tpos-cart-name" title={c.name}>
                        <span className="tpos-cart-name-text">{c.name}</span>
                        {c.rx_only ? <span className="tpos-cart-flag">Prescription</span> : null}
                        {stockOut ? (
                          <span className="tpos-cart-flag tpos-cart-flag-out">Out</span>
                        ) : c.is_low_stock ? (
                          <span className="tpos-cart-flag tpos-cart-flag-low">Low</span>
                        ) : null}
                      </strong>
                      <span className="tpos-cart-unit">{money(unit)} each</span>
                    </div>
                    <div className="tpos-qty">
                      <button
                        type="button"
                        aria-label={`Decrease quantity of ${c.name}`}
                        onClick={() => bumpQty(c.id, -1)}
                      >
                        −
                      </button>
                      <input
                        type="number"
                        min={1}
                        max={Math.max(0, Number(c.stock_qty) || 0)}
                        step={1}
                        value={c.quantity}
                        onChange={(e) => {
                          if (e.target.value === '') return;
                          const n = Number(e.target.value);
                          if (!Number.isFinite(n)) return;
                          setLineQty(c.id, n);
                        }}
                        inputMode="numeric"
                        aria-label={`Quantity for ${c.name}`}
                      />
                      <button
                        type="button"
                        aria-label={`Increase quantity of ${c.name}`}
                        onClick={() => bumpQty(c.id, 1)}
                      >
                        +
                      </button>
                    </div>
                    <div className="tpos-line">{money(lineAmounts.gross)}</div>
                    <button
                      type="button"
                      className="tpos-cart-remove"
                      onClick={() => removeLine(c.id)}
                      aria-label={`Remove ${c.name}`}
                    >
                      ×
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="tpos-cart-dock">
              <div className="tpos-cart-lines">
                <label className="tpos-field">
                  <span>Customer name</span>
                  <input
                    className="tpos-input"
                    aria-label="POS customer name"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    placeholder="Walk-in if none selected"
                    maxLength={180}
                    autoComplete="off"
                  />
                </label>
                <label className="tpos-split-toggle">
                  <input
                    type="checkbox"
                    aria-label="POS split tender"
                    checked={splitTender}
                    onChange={(e) => enableSplit(e.target.checked)}
                  />
                  <span>Split payment</span>
                </label>
                {splitTender ? (
                  <div className="tpos-split-panel">
                    <p className="tpos-split-due">
                      <span>Amount due</span>
                      <strong>{money(cartTotal)}</strong>
                    </p>
                    <p className="tpos-split-hint">
                      Cash plus one other tender. Editing either amount fills the rest. Mobile Money is
                      recorded only and does not charge a phone.
                    </p>
                    <div className="tpos-split-fields">
                      <label className="tpos-field">
                        <span>Cash amount</span>
                        <input
                          className="tpos-input tpos-cash-tender"
                          type="number"
                          min={0}
                          step="0.01"
                          value={cashTender}
                          onChange={(e) => {
                            const raw = e.target.value;
                            const cash = Number(raw);
                            setCashTender(raw);
                            if (!Number.isFinite(cash)) return;
                            setCardTender(
                              String(Math.max(0, Math.round((cartTotal - cash) * 100) / 100))
                            );
                          }}
                          inputMode="decimal"
                          aria-label="POS cash tender"
                        />
                      </label>
                      <label className="tpos-field">
                        <span>Other tender</span>
                        <select
                          value={splitOtherMethod}
                          onChange={(e) =>
                            setSplitOtherMethod(e.target.value as 'card' | 'mobile_money' | 'bank_transfer')
                          }
                          aria-label="POS split second method"
                        >
                          <option value="card">Card</option>
                          <option value="mobile_money">Mobile Money (MoMo)</option>
                          <option value="bank_transfer">Bank transfer</option>
                        </select>
                      </label>
                      <label className="tpos-field tpos-split-other-amount">
                        <span>{splitOtherLabel} amount</span>
                        <input
                          className="tpos-input tpos-card-tender"
                          type="number"
                          min={0}
                          step="0.01"
                          value={cardTender}
                          onChange={(e) => {
                            const raw = e.target.value;
                            const other = Number(raw);
                            setCardTender(raw);
                            if (!Number.isFinite(other)) return;
                            setCashTender(
                              String(Math.max(0, Math.round((cartTotal - other) * 100) / 100))
                            );
                          }}
                          inputMode="decimal"
                          aria-label="POS card tender"
                        />
                      </label>
                    </div>
                    {splitError ? (
                      <p className="tpos-split-error" role="alert">
                        {splitError}
                      </p>
                    ) : (
                      <p className="tpos-split-hint">
                        Cash {money(cashTenderAmount)} + {splitOtherLabel} {money(otherTenderAmount)} ={' '}
                        {money(splitPaid)}
                      </p>
                    )}
                  </div>
                ) : (
                  <label className="tpos-pay-select">
                    <span>Payment</span>
                    <select
                      value={paymentMethod}
                      onChange={(e) => setPaymentMethod(e.target.value)}
                      aria-label="POS payment method"
                    >
                      <option value="cash">Cash</option>
                      <option value="card">Card</option>
                      <option value="mobile_money">Mobile Money (MoMo)</option>
                      <option value="bank_transfer">Bank transfer</option>
                      {online ? <option value="wallet">Wallet</option> : null}
                      {online ? <option value="gift_card">Gift card</option> : null}
                      {online ? <option value="loyalty">Loyalty points</option> : null}
                      {canCreditSale && (online || offlinePerms.includes('credit_sale')) ? (
                        <option value="credit">Credit</option>
                      ) : null}
                    </select>
                  </label>
                )}
                {!splitTender && paymentMethod === 'mobile_money' ? (
                  <p className="tpos-split-hint">
                    Mobile Money is recorded only. It does not charge a phone.
                  </p>
                ) : null}
                {!online ? (
                  <p className="tpos-split-hint">
                    Offline payments are recorded only. Card, Mobile Money and bank transfers must already be
                    confirmed on the terminal or phone.
                  </p>
                ) : null}
                {!online && offlineStatus?.envelope?.can_override_allocation ? (
                  <label className="tpos-split-toggle">
                    <input
                      type="checkbox"
                      aria-label="Manager override of offline stock allocation"
                      checked={allocationOverride}
                      onChange={(e) => setAllocationOverride(e.target.checked)}
                    />
                    <span>Manager: allow selling beyond this device’s allocation (reviewed at sync)</span>
                  </label>
                ) : null}
                {!splitTender && paymentMethod === 'credit' ? (
                  <>
                    <label className="tpos-field">
                      <span>Amount paid now</span>
                      <input
                        className="tpos-input"
                        type="number"
                        min={0}
                        step="0.01"
                        value={amountPaidNow}
                        onChange={(e) => setAmountPaidNow(e.target.value)}
                        placeholder="0.00"
                        inputMode="decimal"
                        aria-label="POS amount paid now"
                      />
                    </label>
                    {creditPaidNow > 0 ? (
                      <label className="tpos-field">
                        <span>How this amount was paid</span>
                        <select
                          value={depositMethod}
                          onChange={(e) => setDepositMethod(e.target.value)}
                          aria-label="POS deposit method"
                        >
                          <option value="cash">Cash</option>
                          <option value="card">Card</option>
                          {online ? <option value="wallet">Digital wallet</option> : null}
                          <option value="mobile_money">Mobile Money (MoMo)</option>
                          <option value="bank_transfer">Bank transfer</option>
                        </select>
                      </label>
                    ) : null}
                  </>
                ) : null}
                {paymentMethod === 'credit' && !splitTender ? (
                  <label className="tpos-field">
                    <span>Reason for selling over the limit</span>
                    <input
                      className="tpos-input"
                      value={creditOverrideReason}
                      onChange={(e) => setCreditOverrideReason(e.target.value)}
                      placeholder="Needed only if over the credit limit"
                      maxLength={500}
                      autoComplete="off"
                      aria-label="Credit override reason"
                    />
                  </label>
                ) : null}
                <div className="tpos-foot-discounts">
                  <label className="tpos-field tpos-field-compact">
                    <span>Cart discount</span>
                    <span className="tpos-inline-controls">
                      <select
                        value={cartDiscountType}
                        onChange={(e) => {
                          setCartDiscountType(e.target.value === 'percent' ? 'percent' : 'fixed');
                          setCartDiscount('');
                        }}
                        aria-label="POS cart discount type"
                      >
                        <option value="fixed">Amount</option>
                        <option value="percent">Percent</option>
                      </select>
                      <input
                        className="tpos-input"
                        type="number"
                        min={0}
                        step="0.01"
                        value={cartDiscount}
                        onChange={(e) => setCartDiscount(e.target.value)}
                        placeholder={cartDiscountType === 'percent' ? '0' : '0.00'}
                        inputMode="decimal"
                        aria-label="POS cart discount"
                      />
                    </span>
                  </label>
                  <label className="tpos-field tpos-field-compact">
                    <span>Coupon</span>
                    <input
                      className="tpos-input"
                      value={couponCode}
                      onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                      placeholder="CODE"
                      aria-label="POS coupon code"
                    />
                  </label>
                </div>
              </div>
              <div className="tpos-total" aria-label="POS cart totals">
                <span>
                  Subtotal {money(cartTotals.subtotal)}
                  {cartTotals.tax > 0 ? ` · Tax ${money(cartTotals.tax)}` : ''}
                  {cartDiscountAmount > 0 ? ` · Discount −${money(cartDiscountAmount)}` : ''}
                  {paymentMethod === 'credit' && !splitTender
                    ? ` · On account ${money(creditRemaining)}`
                    : ''}
                </span>
                <strong>{money(cartTotal)}</strong>
              </div>
              <div className="tpos-cart-actions">
                <div className="tpos-pay-row">
                <button
                  type="button"
                  className="tpos-btn tpos-btn-pay"
                  onClick={payAsReprint ? reprintLastReceipt : checkout}
                  disabled={payAsReprint ? !!receiptBusy : !cart.length || !session || busy}
                  aria-label={payAsReprint ? 'Reprint last receipt' : 'Charge'}
                >
                  {payAsReprint
                    ? receiptBusy === 'reprint'
                      ? 'Reprint…'
                      : 'Reprint'
                    : busy
                      ? 'Paying…'
                      : `Pay ${money(cartTotal)}`}
                </button>
                <button
                  type="button"
                  className="tpos-btn tpos-btn-clear btn-danger"
                  onClick={clearCart}
                  disabled={!cart.length}
                  aria-label="Clear POS cart"
                >
                  Clear
                </button>
                </div>
                <button
                  type="button"
                  className="sr-only"
                  onClick={checkout}
                  disabled={!cart.length || !session || busy}
                  aria-label="Charge complete sale"
                >
                  Charge complete sale
                </button>
                {(industryCode === 'wholesale' || industryCode === 'retail_wholesale') &&
                (online ? canWriteQuotes : offlineValid && offlinePerms.includes('quote_capture')) ? (
                  <button
                    type="button"
                    className="tpos-btn"
                    onClick={saveQuoteOffline}
                    disabled={!cart.length || !session || busy || !customerId}
                    aria-label="Save as quote"
                    title={customerId ? '' : 'Select a customer first'}
                  >
                    {online ? 'Save as quote' : 'Save quote offline'}
                  </button>
                ) : null}
              </div>
              {error ? (
                <p className="tpos-banner tpos-banner-err" role="alert">
                  {error}
                </p>
              ) : null}
              {message ? (
                <div className="tpos-banner tpos-banner-ok tpos-success-bar">
                  <span>{message}</span>
                  {lastSale ? (
                    <div className="tpos-success-actions">
                      {showReceiptEmailSms && !lastSale.offline ? (
                      <>
                      <input
                        type="text"
                        value={receiptTo}
                        onChange={(e) => setReceiptTo(e.target.value)}
                        placeholder="Email or phone"
                        aria-label="POS receipt override to"
                        disabled={!!receiptBusy}
                      />
                      <button
                        type="button"
                        className="tpos-btn"
                        onClick={() => sendLastReceipt('email')}
                        disabled={!!receiptBusy}
                        aria-label="Email last receipt"
                      >
                        {receiptBusy === 'email' ? 'Sending…' : 'Email'}
                      </button>
                      <button
                        type="button"
                        className="tpos-btn"
                        onClick={() => sendLastReceipt('sms')}
                        disabled={!!receiptBusy}
                        aria-label="SMS last receipt"
                      >
                        {receiptBusy === 'sms' ? 'Sending…' : 'SMS'}
                      </button>
                      </>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </aside>
        </div>
      </div>
    </>
  );
}
