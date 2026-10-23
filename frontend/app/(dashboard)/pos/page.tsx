'use client';

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, apiFetch, isAbortError } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { getPrefetched } from '../../../lib/prefetchCache';
import { pageLoadStarted } from '../../../lib/navTiming';
import { useStoreContext } from '../../../lib/storeContext';
import { isHotelIndustry, tenantIsMultiStore } from '../../../lib/tenantNav';
import { normalizeIndustry } from '../../../lib/industries';
import { currencySign, formatDate, formatWhen, plainLabel } from '../../../lib/format';
import { AmountField } from '../../../components/AmountField';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';
import { countAndCloseOpenShift, openShiftForSignedInUser, shiftOpenError, tillBlockedReason } from '../../../lib/cashierShift';
import { POS_RETURN_PANEL_EVENT, POS_SHIFT_PANEL_EVENT, setPosDrawerBridge } from '../../../lib/posDrawerBridge';
import { TillReturnPanel } from './TillReturnPanel';
import { setPosOfflinePanelProps } from '../../../lib/posOfflineSlot';
import {
  CATALOG_NOT_SAVED,
  describePrepareFailure,
  explainOfflineAccess,
  refreshLink,
  startLinkWatch,
  subscribeLink,
  UNPREPARED_OFFLINE,
} from '../../../lib/connectivity';
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
import { type OfflineStatus } from '../../../components/PosOfflinePanel';
import './pos-modern.css';

/** Ways to pay that have their own button on the till. */
const MAIN_PAY_METHODS = new Set(['cash', 'card', 'mobile_money', 'bank_transfer']);
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

function printProvisionalReceipt(
  rec: QueuedSale,
  lines: Array<{ name: string; quantity: number; unit: number }>,
  storeName: string,
  paper: string = '80mm'
) {
  const payload = rec.payload as Record<string, unknown>;
  const payments = Array.isArray(payload.payments)
    ? (payload.payments as Array<{ payment_method: string; amount: number }>)
    : [{ payment_method: String(payload.payment_method || 'cash'), amount: Number(payload.total || 0) }];
  const narrow = paper === '58mm';
  const page = narrow ? '58mm' : '80mm';
  const slip = narrow ? '48mm' : '72mm';
  const font = narrow ? '12px' : '13px';
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
      `<style>@page{margin:0;size:${page} auto}html,body{margin:0;padding:0;width:${page};max-width:${page}}` +
      `.slip{width:${slip};max-width:${page};margin:0 auto;font-family:'Courier New',ui-monospace,monospace;font-weight:700;font-size:${font};line-height:1.15}` +
      'h3,p,.mid{text-align:center;margin:0;overflow-wrap:anywhere}p{font-size:10px;margin:1mm 0}' +
      `table{width:100%;border-collapse:collapse;table-layout:fixed}td{font-size:${font};font-weight:700;padding:1px 0;vertical-align:top;overflow-wrap:anywhere}` +
      'td:nth-child(2),td:last-child{text-align:right;padding-left:1mm}</style></head><body><div class="slip">' +
      `<h3>${escapeHtml(storeName)}</h3>` +
      '<p><strong>Offline sale — pending synchronization.</strong><br/>This is not the final receipt. The receipt number is issued when the sale is sent.</p>' +
      `<div class="mid">Receipt no. ${escapeHtml(rec.local_receipt_number)}</div><div class="mid">${escapeHtml(formatWhen(rec.created_at) || '')}</div>` +
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
  category?: string | null;
  category_id?: string | null;
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
  const body = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
  return `${currencySign()} ${body}`;
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

  // Letters and digits only, so "T-shirt (cotton)" shows "TC", not "T(".
  const initials = name
    .split(/[^A-Za-z0-9]+/)
    .filter(Boolean)
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
  const [categoryFilter, setCategoryFilter] = useState('');
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
  const [giftCardCode, setGiftCardCode] = useState('');
  const [canCreditSale, setCanCreditSale] = useState(false);
  const [splitTender, setSplitTender] = useState(false);
  const [cashTender, setCashTender] = useState('');
  // Change handed back on the last cash sale, shown after Pay.
  const [lastChange, setLastChange] = useState<number | null>(null);
  // On short screens the keypad hides until needed so the cart lines stay visible.
  const [keypadOpen, setKeypadOpen] = useState(true);
  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerHeight < 860) setKeypadOpen(false);
  }, []);
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
  const [countedCash, setCountedCash] = useState('');
  const [countNotes, setCountNotes] = useState('');
  const [countBusy, setCountBusy] = useState(false);
  const [countError, setCountError] = useState('');
  const [shiftClosedNote, setShiftClosedNote] = useState('');
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
    lines?: Array<{ name: string; quantity: number; unit: number; line: number }>;
    total?: number;
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
  // What the product list last asked for: '' means the full list for this store.
  const [lastBrowseQuery, setLastBrowseQuery] = useState('');
  // The shift header and report open over the till from the top bar's Shift button.
  const [shiftPanelOpen, setShiftPanelOpen] = useState(false);
  const [returnPanelOpen, setReturnPanelOpen] = useState(false);
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
  const [preparingOffline, setPreparingOffline] = useState(false);
  const [prepareFailure, setPrepareFailure] = useState('');
  const prepareNotice = useRef('');
  const bumpOffline = useCallback(() => setOfflineRefresh((n) => n + 1), []);
  const handleOfflineStatus = useCallback((s: OfflineStatus) => {
    setOfflineStatus(s);
    setPendingOffline(s.summary.pending + s.summary.syncing + s.summary.needs_attention);
  }, []);
  const offlineValid = isOfflineAuthValid(offlineStatus?.envelope || null);
  const offlinePerms = offlineStatus?.envelope?.permissions || [];
  const checkoutReqRef = useRef<string | null>(null);
  const checkoutAttemptRef = useRef<string | null>(null);
  const cashMoveLock = useRef(false);
  const countLock = useRef(false);
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
  const catalogCategories = useMemo(() => {
    const names = new Set<string>();
    for (const row of rows) {
      const label = String(row.category || '').trim();
      if (label) names.add(label);
    }
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [rows]);
  const visibleRows = useMemo(() => {
    if (!categoryFilter) return rows;
    return rows.filter((row) => String(row.category || '').trim() === categoryFilter);
  }, [rows, categoryFilter]);

  function receiptPreviewFromCart() {
    return {
      lines: cart.map((c) => {
        const unit = groupUnitPrice(Number(c.selling_price));
        return {
          name: c.name,
          quantity: c.quantity,
          unit,
          line: Math.round(unit * c.quantity * 100) / 100,
        };
      }),
      total: cartTotal,
    };
  }
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
  const payingCash = !splitTender && paymentMethod === 'cash';
  const cashChangeDue =
    payingCash && cashTenderAmount > cartTotal ? Math.round((cashTenderAmount - cartTotal) * 100) / 100 : 0;
  const cashShort = payingCash && cashTenderAmount > 0 && cashTenderAmount < cartTotal - 0.004;
  // Exact amount plus the next round notes above the total, e.g. 50, 100, 200.
  const quickCash = (() => {
    if (cartTotal <= 0) return [] as number[];
    const out = [Math.round(cartTotal * 100) / 100];
    for (const step of [5, 10, 20, 50, 100, 200]) {
      const v = Math.ceil(cartTotal / step) * step;
      if (v > cartTotal + 0.004 && !out.includes(v)) out.push(v);
    }
    return out.slice(0, 4);
  })();
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

  // Shortcuts for a busy till: F2 or / to search, F9 to pay, Enter or F9 for the next sale.
  const shortcutRef = useRef({ pay: () => {}, next: () => {}, done: false, blocked: false });
  shortcutRef.current = {
    pay: () => void checkout(),
    next: startNextSale,
    done: payAsReprint,
    blocked: shiftPanelOpen || returnPanelOpen,
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const keys = shortcutRef.current;
      if (keys.blocked) return;
      const el = e.target as HTMLElement | null;
      const typing =
        !!el && (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.isContentEditable);
      if (e.key === 'F2' || (e.key === '/' && !typing)) {
        e.preventDefault();
        document.querySelector<HTMLInputElement>('.tpos-search-input')?.focus();
      } else if (e.key === 'F9') {
        e.preventDefault();
        if (keys.done) keys.next();
        else keys.pay();
      } else if (e.key === 'Enter' && keys.done && !typing) {
        e.preventDefault();
        keys.next();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
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
    setLastBrowseQuery(query);
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
    const kick = () => {
      void refreshLink();
    };
    const unsub = subscribeLink((snap) => {
      setOnline(snap.phase === 'online' || snap.phase === 'syncing' || snap.phase === 'sync_failed');
    });
    const stopWatch = startLinkWatch();
    window.addEventListener('online', kick);
    window.addEventListener('offline', kick);
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
      unsub();
      stopWatch();
      window.removeEventListener('online', kick);
      window.removeEventListener('offline', kick);
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
            device_id: await hydrateDeviceId(),
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
    if (!tenantId || !meId) return;
    setPreparingOffline(true);
    setPrepareFailure('');
    try {
      await revalidateOfflineAccess(api, {
        tenant_id: tenantId,
        user_id: meId,
        store_id: storeForGrant,
        label: stores.find((s) => s.id === storeForGrant)?.name,
      });
      const [meta, env] = await Promise.all([
        getCachedCatalogMeta(),
        getOfflineAuthEnvelope().catch(() => null),
      ]);
      if (!env?.grant_id || !meta?.cached_at) {
        throw new Error(env?.grant_id ? CATALOG_NOT_SAVED : 'Offline access was not saved on this device.');
      }
      setCatalogCachedAt(meta.cached_at);
      const previous = prepareNotice.current;
      prepareNotice.current = '';
      setPrepareFailure('');
      setError((prev) => (prev === UNPREPARED_OFFLINE || prev === previous ? '' : prev));
    } catch (err) {
      const env = await getOfflineAuthEnvelope().catch(() => null);
      const text = describePrepareFailure(err, Boolean(env?.grant_id));
      const previous = prepareNotice.current;
      prepareNotice.current = text;
      setPrepareFailure(text);
      setError((prev) => (prev === '' || prev === UNPREPARED_OFFLINE || prev === previous ? text : prev));
    } finally {
      setPreparingOffline(false);
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
          const httpStatus = (bootErr as { status?: number })?.status;
          const browserOnline = typeof navigator === 'undefined' ? true : navigator.onLine;
          if (browserOnline && httpStatus !== undefined) throw bootErr;
          if (browserOnline && (bootErr as Error)?.message !== 'offline') {
            throw new Error(
              (bootErr as Error)?.message || 'Point of Sale could not reach the server to prepare this device.'
            );
          }
          const [sSnap, stSnap, meSnap, env] = await Promise.all([
            getSnapshot<Session | null>('session').catch(() => null),
            getSnapshot<Store[]>('stores').catch(() => null),
            getSnapshot<any>('me').catch(() => null),
            getOfflineAuthEnvelope().catch(() => null),
          ]);
          const decision = explainOfflineAccess(env);
          if (!decision.prepared || !meSnap || env?.user_id !== String(meSnap.id || '')) {
            throw new Error(
              decision.prepared
                ? 'Online sign-in is required. Saved sales stay on this device.'
                : decision.message
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
        if (!sess.data && navigator.onLine && !tillIndustry) {
          // Say why instead of 'Wait for your shift to open' that never ends.
          setError(tillBlockedReason(meRes.data) || 'This company has no till.');
        }
        if (!sess.data && navigator.onLine && tillIndustry && !cancelled) {
          const opened = await openShiftForSignedInUser(chosen || null);
          if (cancelled) return;
          if (opened?.session_id) sess = { data: opened as Session };
          else if (list.length > 1 && !chosen) setError('Choose the store you are selling from to start your shift.');
          else setError(shiftOpenError() || 'Your shift could not be started. Sign out and sign in again.');
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
    const open = () => setShiftPanelOpen(true);
    const openReturn = () => setReturnPanelOpen(true);
    window.addEventListener(POS_SHIFT_PANEL_EVENT, open);
    window.addEventListener(POS_RETURN_PANEL_EVENT, openReturn);
    return () => {
      window.removeEventListener(POS_SHIFT_PANEL_EVENT, open);
      window.removeEventListener(POS_RETURN_PANEL_EVENT, openReturn);
    };
  }, []);

  // Opening the panel shows the report straight away, so the cash count is one step.
  useEffect(() => {
    if (shiftPanelOpen && session && !shiftReport && !reportBusy) void loadShiftReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shiftPanelOpen, session?.session_id]);

  useEffect(() => {
    if (!shiftPanelOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setShiftPanelOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [shiftPanelOpen]);

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
    if (!online || meId || bootLoading) return;
    let cancelled = false;
    (async () => {
      try {
        const meRes = await getMe();
        if (cancelled) return;
        const id = String(meRes.data?.id || '');
        const tid = String(meRes.data?.tenant_id || '');
        if (!id || !tid) return;
        setMeId(id);
        setTenantId(tid);
        setIndustryCode(normalizeIndustry(meRes.data?.industry) || '');
        setCanApproveOffline(hasPerm(meRes.data, 'pos', 'approve'));
        setCanOpenDrawer(hasPerm(meRes.data, 'pos', 'write'));
        setCanWriteQuotes(hasPerm(meRes.data, 'sales', 'write'));
        setCashierName(meRes.data?.full_name || meRes.data?.email || '');
        setCanCreditSale(canWriteCredit(meRes.data));
        setError('');
        const [sess, storeRes] = await Promise.all([
          getPrefetched('/pos/sessions/current').catch(() => null),
          getPrefetched('/pos/stores').catch(() => null),
        ]);
        if (cancelled) return;
        const list = (storeRes?.data || []) as Store[];
        if (list.length) setStores(list);
        if (sess?.data) {
          setSession(sess.data);
          setBootedOffline(false);
        }
      } catch {
        /* still unreachable; the unprepared sentence stays only when there is no grant */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [online, meId, bootLoading]);

  useEffect(() => {
    if (!online || !tenantId || !meId) return;
    let cancelled = false;
    (async () => {
      const storeForGrant = session?.store_id || storeId.trim() || null;
      const [env, meta] = await Promise.all([
        getOfflineAuthEnvelope().catch(() => null),
        getCachedCatalogMeta().catch(() => null),
      ]);
      const storeMismatch = Boolean(storeForGrant) && (env?.store_id || null) !== storeForGrant;
      const stale =
        !env?.grant_id ||
        !meta?.cached_at ||
        !isOfflineAuthValid(env) ||
        env.user_id !== meId ||
        env.tenant_id !== tenantId ||
        storeMismatch ||
        Date.now() - new Date(env.allocations_refreshed_at || env.issued_at).getTime() > 6 * 3600000;
      if (!cancelled && stale) await refreshOfflineAccess(storeForGrant);
    })();
    return () => {
      cancelled = true;
    };
    // refreshOfflineAccess reads current state; re-run only on identity/store changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online, session?.session_id, session?.store_id, storeId, tenantId, meId]);

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
      // Keep an open report in step with the drawer so the count is checked against the right amount.
      if (shiftReport) {
        const fresh = await api(`/pos/sessions/${session.session_id}/report`).catch(() => null);
        if (fresh?.data) setShiftReport(fresh.data);
      }
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

  async function recordCashCount() {
    if (!session || countLock.current) return;
    setCountError('');
    setError('');
    const raw = countedCash.trim();
    const actual = Math.round(Number(raw) * 100) / 100;
    if (!raw || !Number.isFinite(actual) || actual < 0) {
      setCountError('Enter the counted cash. Use 0 if the drawer is empty.');
      return;
    }
    const expected = Number(session.expected_cash || 0);
    const variance = Math.round((actual - expected) * 100) / 100;
    const note = countNotes.trim();
    if (Math.abs(variance) >= 0.01 && note.length < 3) {
      setCountError('Explain the difference between counted cash and the expected drawer.');
      return;
    }
    countLock.current = true;
    setCountBusy(true);
    try {
      const closed = await countAndCloseOpenShift(actual, note || null);
      const recorded = Number(closed.variance ?? variance);
      const label = closed.session_number || session.session_number;
      setSession(null);
      setShiftReport(null);
      setCountedCash('');
      setCountNotes('');
      setShiftClosedNote(
        Math.abs(recorded) < 0.01
          ? `Shift ${label} closed. Counted cash matched the drawer.`
          : `Shift ${label} closed. Counted cash was ${money(Math.abs(recorded))} ${recorded < 0 ? 'short' : 'over'}.`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'The cash count could not be saved.';
      setCountError(msg);
      setError(msg);
    } finally {
      countLock.current = false;
      setCountBusy(false);
    }
  }

  async function startNewShift() {
    setShiftBusy(true);
    setError('');
    setShiftClosedNote('');
    try {
      const opened = await openShiftForSignedInUser(storeId.trim() || null);
      if (opened?.session_id) {
        setSession(opened as Session);
        void loadShiftHistory();
      } else {
        setError('Your shift could not be started. Sign out and sign in again.');
      }
    } finally {
      setShiftBusy(false);
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
            // Put the product grid back; it only held this one search result.
            void browse('').catch(() => {});
            return;
          }
          // No match: the empty product list already says so and offers Show all products.
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
    // A search covers every category, so results are not hidden by the category tabs.
    if (q.trim()) setCategoryFilter('');
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
    setMessage('');
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

  function applyKeypad(key: string) {
    const append = (current: string) => {
      const raw = String(current || '');
      if (key === 'C') return '';
      if (key === '⌫') return raw.slice(0, -1);
      if (key === '.' && raw.includes('.')) return raw;
      if (key === '00') return raw ? `${raw}00` : '0';
      if (raw === '0' && key !== '.') return key;
      return `${raw}${key}`;
    };
    if (splitTender || paymentMethod === 'cash') {
      const next = append(String(cashTender || ''));
      setCashTender(next);
      if (splitTender) {
        const cash = Number(next);
        if (Number.isFinite(cash)) {
          setCardTender(String(Math.max(0, Math.round((cartTotal - cash) * 100) / 100)));
        }
      }
      return;
    }
    if (paymentMethod === 'credit') {
      setAmountPaidNow(append(String(amountPaidNow || '')));
      return;
    }
    const last = cart[cart.length - 1];
    if (!last) return;
    const next = append(String(last.quantity));
    const qty = Math.floor(Number(next) || 0);
    if (Number.isFinite(qty)) setLineQty(last.id, qty);
  }

  /** After a sale: clear the done panel and get ready to scan the next customer. */
  function startNextSale() {
    setPayAsReprint(false);
    setLastChange(null);
    setMessage('');
    setError('');
    document.querySelector<HTMLInputElement>('.tpos-search-input')?.focus();
  }

  function clearCart() {
    setCart([]);
    setCartDiscount('');
    setCouponCode('');
    setCashTender('');
    setCardTender('');
    setAmountPaidNow('');
  }

  function enableSplit(next: boolean) {
    setSplitTender(next);
    if (next) {
      const half = Math.round((cartTotal / 2) * 100) / 100;
      setCashTender(String(half || ''));
      setCardTender(String(Math.max(0, Math.round((cartTotal - half) * 100) / 100) || ''));
    }
  }

  function customerReceiptRouteNote(
    jobs: Array<{ purpose?: string; status?: string }>
  ): string {
    const receiptJobs = (jobs || []).filter((job) => job.purpose === 'customer_receipt');
    const bits: string[] = [];
    if (
      receiptJobs.some(
        (job) => job.status === 'queued' || job.status === 'claimed' || job.status === 'printing'
      )
    ) {
      bits.push(
        'The till agent uses the paper size stored on that printer, not the size next to Pay'
      );
    }
    if (receiptJobs.some((job) => job.status === 'printed')) {
      bits.push(
        'A network printer was sent this receipt at the size stored on that printer. This does not confirm that paper came out'
      );
    }
    return bits.join('. ');
  }

  async function printReceiptAfterPay(
    saleId: string,
    jobs: Array<{ id?: string; purpose?: string; status?: string }>,
    offline?: { rec: QueuedSale; lines: Array<{ name: string; quantity: number; unit: number }>; store: string }
  ) {
    if (!saleId || printedPayIds.current.has(saleId)) return;
    printedPayIds.current.add(saleId);
    const paper = receiptPaper === '58mm' ? '58mm' : '80mm';
    if (offline) {
      printProvisionalReceipt(offline.rec, offline.lines, offline.store, paper);
      return;
    }
    const receiptJobs = (jobs || []).filter((job) => job.purpose === 'customer_receipt');
    if (!receiptJobs.length) return;
    if (receiptJobs.some((job) => job.status === 'printed')) return;
    const browserJob = receiptJobs.find((job) => job.status === 'browser_pending' && job.id);
    if (!browserJob?.id) return;
    try {
      const detail = await api(`/pos/sales/${saleId}/receipt?paper=${encodeURIComponent(paper)}`);
      const payload = detail.data || {};
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
    setLastChange(null);
    const changeOnThisSale = cashChangeDue > 0 ? cashChangeDue : null;
    if (!session) {
      setError('Open a POS shift before selling');
      return;
    }
    if (!cart.length) {
      setError('Cart is empty');
      return;
    }
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
      customer_name: customerName.trim() || null,
      items,
    };
    let payments: { payment_method: string; amount: number; reference: string | null }[] | null = null;
    if (splitTender) {
      if (splitError) {
        setError(splitError);
        return;
      }
      payments = [
        { payment_method: 'cash', amount: cashTenderAmount, reference: null },
        { payment_method: splitOtherMethod, amount: otherTenderAmount, reference: null },
      ];
      body.payments = payments;
      body.payment_method = 'split';
    } else if (paymentMethod === 'gift_card') {
      const code = giftCardCode.trim();
      if (!code) {
        setError('Enter the gift card code');
        return;
      }
      payments = [{ payment_method: 'gift_card', amount: cartTotal, reference: code }];
      body.payments = payments;
      body.payment_method = 'gift_card';
    } else if (paymentMethod === 'credit') {
      const paidNow = Math.round((Number(amountPaidNow) || 0) * 100) / 100;
      const remaining = Math.max(0, Math.round((cartTotal - paidNow) * 100) / 100);
      if (paidNow > 0 && remaining > 0) {
        payments = [
          { payment_method: depositMethod, amount: paidNow, reference: null },
          { payment_method: 'credit', amount: remaining, reference: null },
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
    if (!splitTender && paymentMethod === 'loyalty' && !customerId) {
      setError('Select a customer before paying with loyalty points');
      return;
    }
    const attemptKey = JSON.stringify({
      session_id: body.session_id,
      items: body.items,
      party_id: body.party_id,
      customer_name: body.customer_name,
      payment_method: body.payment_method,
      payments: body.payments ?? null,
      discount_amount: body.discount_amount,
      discount_type: body.discount_type,
      discount_percent: body.discount_percent,
      coupon_code: body.coupon_code,
      prescription_id: body.prescription_id,
    });
    if (checkoutAttemptRef.current !== attemptKey) {
      checkoutReqRef.current = null;
      checkoutAttemptRef.current = attemptKey;
    }
    setBusy(true);
    try {
      const clientRequestId = checkoutReqRef.current || newClientRequestId();
      checkoutReqRef.current = clientRequestId;
      body.client_request_id = clientRequestId;

      // Offline tenders are recorded only; nothing is charged through a provider until the sale syncs.
      const takeOffline = async () => {
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
          throw new Error(explainOfflineAccess(env).message);
        }
        const catalog = await getCachedCatalogMeta();
        if (!catalog?.cached_at) {
          throw new Error(CATALOG_NOT_SAVED);
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
        const preview = receiptPreviewFromCart();
        setLastChange(changeOnThisSale);
        clearCart();
        clearCustomer();
        setGiftCardCode('');
        setCreditOverrideReason('');
        setSplitTender(false);
        setAllocationOverride(false);
        setLastSale({
          id: queued.id,
          reference: queued.local_receipt_number,
          offline: queued,
          ...preview,
        });
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
        setMessage('Offline sale — pending synchronization.');
        checkoutReqRef.current = null;
        checkoutAttemptRef.current = null;
        await refreshPendingCount();
        bumpOffline();
        await browse(q);
      };
      if (!online) {
        await takeOffline();
        return;
      }
      body.device_id = await hydrateDeviceId();

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
          detail &&
          typeof detail === 'object' &&
          detail.code === 'PAYMENT_TOTAL_MISMATCH'
        ) {
          const saleTotal =
            typeof detail.sale_total === 'number' ? money(detail.sale_total) : 'the sale total';
          throw new Error(
            `The cash and other amounts on this form do not add up to ${saleTotal}. Change those amounts, then charge again.`
          );
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
        } else if (err?.status === undefined) {
          setOnline(false);
          await takeOffline();
          return;
        } else {
          throw err;
        }
      }
      if (!r?.data?.id || !r?.data?.reference) {
        throw new Error(r?.message || 'Sale failed');
      }
      const preview = receiptPreviewFromCart();
      setLastChange(changeOnThisSale);
      clearCart();
      clearCustomer();
      setGiftCardCode('');
      setCreditOverrideReason('');
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
        ...preview,
      });
      setReprintTarget({ offline: false, id: r.data.id });
      setPayAsReprint(true);
      const jobs = Array.isArray(r.data.print_jobs) ? r.data.print_jobs : [];
      void printReceiptAfterPay(r.data.id, jobs);
      await refreshSession();
      await browse(q);
      const statusLabel = String(r.data.payment_status || '').replace(/_/g, ' ');
      const bal = Number(r.data.balance_due || 0);
      const routeNote = customerReceiptRouteNote(jobs);
      const extra =
        (r.data?.credit_limit_overridden
          ? ' (credit override)'
          : statusLabel
            ? ` · ${statusLabel}${bal > 0 ? ` · balance ${money(bal)}` : ''}`
            : '') + (routeNote ? ` · ${routeNote}` : '');
      setMessage(`Sale ${r.data.reference} saved${extra}`);
      checkoutReqRef.current = null;
      checkoutAttemptRef.current = null;
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
      const saveQueuedQuote = async () => {
        const env = await getOfflineAuthEnvelope();
        if (!isOfflineAuthValid(env)) throw new Error(explainOfflineAccess(env).message);
        const catalog = await getCachedCatalogMeta();
        if (!catalog?.cached_at) throw new Error(CATALOG_NOT_SAVED);
        const rec = await enqueueOfflineQuote({
          tenant_id: tenantId,
          store_id: session.store_id || storeId || null,
          store_code: store?.code || 'STORE',
          user_id: meId,
          payload: quoteBody,
        });
        setMessage(
          `Quote saved offline as ${rec.local_receipt_number}. Prices are confirmed by the server when it syncs.`
        );
        bumpOffline();
      };
      if (!online) {
        await saveQueuedQuote();
      } else {
        try {
          const r = await api('/sales/quotations', {
            method: 'POST',
            body: JSON.stringify({
              ...quoteBody,
              total: undefined,
              notes: null,
              client_request_id: newClientRequestId(),
            }),
          });
          setMessage(`Quote ${r.data?.number || r.data?.reference || ''} saved`);
        } catch (err: unknown) {
          const status = Number((err as { status?: number })?.status) || 0;
          if (!status || status >= 500 || status === 429 || status === 408) {
            await saveQueuedQuote();
          } else {
            throw err;
          }
        }
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
      const paper = receiptPaper === '58mm' ? '58mm' : '80mm';
      if (reprintTarget.offline) {
        printProvisionalReceipt(reprintTarget.rec, reprintTarget.lines, reprintTarget.store, paper);
        return;
      }
      const notes: string[] = [];
      let openedBrowser = false;
      try {
        const queued = await api('/printers/reprint', {
          method: 'POST',
          body: JSON.stringify({ source_type: 'pos_sale', source_id: reprintTarget.id }),
        });
        const jobs = Array.isArray(queued.data) ? queued.data : [];
        const receiptJobs = jobs.filter(
          (job: { purpose?: string }) => job.purpose === 'customer_receipt'
        );
        const browser = receiptJobs.find(
          (job: { id?: string; status?: string }) => job.status === 'browser_pending' && job.id
        );
        const agentQueued = receiptJobs.some(
          (job: { status?: string }) =>
            job.status === 'queued' || job.status === 'claimed' || job.status === 'printing'
        );
        const networkSent = receiptJobs.some((job: { status?: string }) => job.status === 'printed');
        if (browser?.id) {
          const detail = await api(`/pos/sales/${reprintTarget.id}/receipt?paper=${encodeURIComponent(paper)}`);
          const payload = detail.data || {};
          openedBrowser = openReceiptPrintWindow(payload.html, payload.text || '');
          if (openedBrowser) {
            await api(`/printers/jobs/${browser.id}/browser-ack`, {
              method: 'POST',
              body: JSON.stringify({ status: 'printed' }),
            });
          }
        } else if (!agentQueued && !networkSent) {
          const receipt = await api(`/pos/sales/${reprintTarget.id}/receipt?paper=${encodeURIComponent(paper)}`);
          openedBrowser = openReceiptPrintWindow(receipt.data?.html, receipt.data?.text || '');
        }
        if (openedBrowser) {
          notes.push(
            'Browser receipt uses the size next to Pay. This does not confirm that paper came out.'
          );
        }
        if (agentQueued) {
          notes.push(
            'Reprint is queued for the till agent. That printer uses the paper size stored on it, not the size next to Pay.'
          );
        }
        if (networkSent) {
          notes.push(
            'Reprint was sent to a network printer at the paper size stored on it. This does not confirm that paper came out.'
          );
        }
      } catch {
        const receipt = await api(`/pos/sales/${reprintTarget.id}/receipt?paper=${encodeURIComponent(paper)}`);
        openedBrowser = openReceiptPrintWindow(receipt.data?.html, receipt.data?.text || '');
        if (openedBrowser) {
          notes.push(
            'Browser receipt uses the size next to Pay. This does not confirm that paper came out.'
          );
        }
      }
      if (notes.length) setMessage(notes.join(' '));
      else if (!openedBrowser) setError('Reprint could not open the print dialog.');
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

  useEffect(() => {
    if (!meId || !tenantId) {
      setPosOfflinePanelProps(null);
      return;
    }
    setPosOfflinePanelProps({
      api: api as unknown as (path: string, opts?: RequestInit) => Promise<unknown>,
      online,
      tenantId,
      userId: meId,
      storeId: session?.store_id || storeId.trim() || null,
      storeLabel: stores.find((s) => s.id === (session?.store_id || storeId))?.name,
      canApprove: canApproveOffline,
      refreshToken: offlineRefresh,
      preparing: preparingOffline,
      prepareFailure,
      onStatus: handleOfflineStatus,
      onMessage: setMessage,
      onError: setError,
    });
  }, [
    meId,
    tenantId,
    online,
    session?.store_id,
    storeId,
    stores,
    canApproveOffline,
    offlineRefresh,
    preparingOffline,
    prepareFailure,
    handleOfflineStatus,
  ]);

  useEffect(() => () => setPosOfflinePanelProps(null), []);

  return (
    <>
      <div className="tpos pos-ui">
        <TillReturnPanel
          open={returnPanelOpen}
          onClose={() => setReturnPanelOpen(false)}
          money={money}
          onDone={({ message: note, session: fresh }) => {
            if (fresh) setSession(fresh as Session);
            setPayAsReprint(false);
            setError('');
            setMessage(note);
            setShiftReport(null);
          }}
        />
        <div
          className={`pos-shift-panel${shiftPanelOpen ? ' is-open' : ''}`}
          onClick={(e) => {
            if (e.target === e.currentTarget) setShiftPanelOpen(false);
          }}
        >
        <div
          className="pos-shift-panel-card"
          role={shiftPanelOpen ? 'dialog' : undefined}
          aria-modal={shiftPanelOpen ? true : undefined}
          aria-label="Till shift"
        >
        <div className="pos-shift-panel-head">
          <h2>Your shift</h2>
          <button type="button" className="tpos-btn" aria-label="Close till shift" onClick={() => setShiftPanelOpen(false)}>
            Close
          </button>
        </div>
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
          </div>
          <div className="tpos-shift pos-ui-shift">
            {!session ? (
              <>
                {shiftClosedNote ? (
                  <p className="muted" role="status">
                    {shiftClosedNote}{' '}
                    <button
                      type="button"
                      className="tpos-btn"
                      disabled={shiftBusy}
                      aria-label="Start a new shift"
                      onClick={() => void startNewShift()}
                    >
                      {shiftBusy ? 'Starting…' : 'Start a new shift'}
                    </button>
                  </p>
                ) : null}
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
                {shiftClosedNote && !shiftBusy ? null : (
                <span className="muted">
                  {shiftBusy || hideStorePicker || stores.length <= 1
                    ? 'Starting your shift…'
                    : 'Choose a store to start your shift.'}
                </span>
                )}
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
                    Amount to add or remove
                    <AmountField
                      className="tpos-input"
                      value={cashMoveAmount}
                      onChange={(e) => setCashMoveAmount(e.target.value)}
                      inputMode="decimal"
                      placeholder="0.00"
                      autoComplete="off"
                      aria-label="Drawer cash amount"
                    />
                  </label>
                  <label className="tpos-cash-field">
                    Reason
                    <input
                      className="tpos-input"
                      value={cashMoveReason}
                      onChange={(e) => setCashMoveReason(e.target.value)}
                      placeholder="Short note, such as a payout or a top-up"
                      maxLength={200}
                      autoComplete="off"
                      aria-label="Drawer cash movement reason"
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
              {shiftReport.payment_breakdown?.by_method ? (
                Object.entries(shiftReport.payment_breakdown.by_method as Record<string, number>)
                  .filter(([method, amount]) => method !== 'cash' && method !== 'card' && Number(amount) > 0)
                  .map(([method, amount]) => (
                    <div key={method}>
                      <span>{method === 'credit' ? 'On credit' : posPayLabel(method)}</span>
                      <strong>{money(Number(amount))}</strong>
                    </div>
                  ))
              ) : (
                <div>
                  <span>Other</span>
                  <strong>{money(Number(shiftReport.payment_breakdown?.other || 0))}</strong>
                </div>
              )}
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
            {session.status !== 'closed' ? (
              <form
                className="tpos-cash"
                aria-label="Cash count"
                onSubmit={(e) => {
                  e.preventDefault();
                  void recordCashCount();
                }}
              >
                <p className="muted">
                  Count the notes and coins in the drawer. Sign-out still closes at the expected amount if you leave this blank.
                </p>
                <label className="tpos-cash-field">
                  Counted cash
                  <AmountField
                    className="tpos-input"
                    value={countedCash}
                    onChange={(e) => setCountedCash(e.target.value)}
                    inputMode="decimal"
                    placeholder="0.00"
                    autoComplete="off"
                    aria-label="Counted cash"
                  />
                </label>
                <label className="tpos-cash-field">
                  Difference note
                  <input
                    className="tpos-input"
                    value={countNotes}
                    onChange={(e) => setCountNotes(e.target.value)}
                    placeholder="Required when the count differs"
                    maxLength={500}
                    autoComplete="off"
                    aria-label="Cash count notes"
                  />
                </label>
                <button
                  type="submit"
                  className="tpos-btn tpos-btn-primary"
                  disabled={countBusy}
                  aria-label="Record cash count and close shift"
                >
                  {countBusy ? 'Saving…' : 'Record cash count and close shift'}
                </button>
                {countError ? (
                  <p className="tpos-cash-error" role="alert">
                    {countError}
                  </p>
                ) : null}
              </form>
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
        </div>
        </div>

        <div className="tpos-body">
          <section className="tpos-catalog pos-ui-catalog" aria-label="Product catalog">
            <form className="tpos-search pos-ui-search" onSubmit={search}>
              <span className="pos-search-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
              </span>
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
                Search
              </button>
              <button
                type="button"
                className="tpos-btn"
                disabled={!session}
                onClick={() => {
                  setQ('');
                  setCategoryFilter('');
                  browse('').catch((err) => setError(err.message));
                }}
                aria-label="Browse all POS products"
              >
                All
              </button>
            </form>
            <p className="pos-shortcuts" aria-hidden>
              <kbd>F2</kbd> search · <kbd>F9</kbd> pay · <kbd>Enter</kbd> next sale
            </p>
            {session && catalogCategories.length > 0 ? (
              <nav className="tpos-cats" aria-label="POS product categories">
                <p className="tpos-cats-crumb">
                  {categoryFilter ? `All / ${categoryFilter}` : 'All products'}
                </p>
                <div className="tpos-cats-row" role="tablist">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={!categoryFilter}
                    className={`tpos-cat${categoryFilter ? '' : ' is-on'}`}
                    onClick={() => setCategoryFilter('')}
                    aria-label="Show all POS categories"
                  >
                    All
                  </button>
                  {catalogCategories.map((name) => (
                    <button
                      key={name}
                      type="button"
                      role="tab"
                      aria-selected={categoryFilter === name}
                      className={`tpos-cat${categoryFilter === name ? ' is-on' : ''}`}
                      onClick={() => setCategoryFilter(name)}
                      aria-label={`Show ${name} products`}
                    >
                      {name}
                    </button>
                  ))}
                </div>
              </nav>
            ) : null}

            {!session && (
              <div className="tpos-empty">
                {stores.length > 0 && !hideStorePicker ? (
                  <label className="tpos-field">
                    <span>Choose a store to start your shift.</span>
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
                    {error ? <p>{error}</p> : null}
                  </label>
                ) : (
                  <p>{error || 'Wait for your shift to open, then scan or search for a product.'}</p>
                )}
                {shiftClosedNote ? (
                  <button
                    type="button"
                    className="tpos-btn"
                    disabled={shiftBusy}
                    aria-label="Start a new shift"
                    onClick={() => void startNewShift()}
                  >
                    {shiftBusy ? 'Starting…' : 'Start a new shift'}
                  </button>
                ) : null}
              </div>
            )}

            {session && catalogLoading && rows.length === 0 && (
              <div className="tpos-skeleton-grid" aria-busy="true" aria-label="Loading products">
                {Array.from({ length: 8 }, (_, i) => (
                  <div key={i} className="tpos-skeleton-tile" />
                ))}
              </div>
            )}

            {session && !catalogLoading && visibleRows.length === 0 && (
              <div className="tpos-empty">
                <p>
                  {rows.length && categoryFilter
                    ? `No ${categoryFilter} items in this search. Choose another category or tap All.`
                    : lastBrowseQuery.trim()
                      ? `Nothing matches “${lastBrowseQuery.trim()}”. Check the spelling or scan the barcode.`
                      : `${session.store_name || 'This store'} has no products in stock to sell yet. Add products and their stock in Inventory, then come back.`}
                </p>
                {!lastBrowseQuery.trim() && !categoryFilter ? (
                  <a className="tpos-btn" href="/inventory" aria-label="Go to Inventory">
                    Go to Inventory
                  </a>
                ) : (
                <button
                  type="button"
                  className="tpos-btn"
                  aria-label="Show all products"
                  onClick={() => {
                    setQ('');
                    setCategoryFilter('');
                    browse('').catch((err) => setError(err.message));
                  }}
                >
                  Show all products
                </button>
                )}
              </div>
            )}

            <div className="tpos-grid">
              {visibleRows.map((r) => {
                const out = Number(r.stock_qty) <= 0 || Boolean(r.is_out_of_stock);
                const low = Boolean(r.is_low_stock) && !out;
                const inCart = cart.find((c) => c.id === r.id)?.quantity || 0;
                return (
                  <button
                    key={r.id}
                    type="button"
                    className={`tpos-tile${out ? ' out' : ''}${inCart > 0 ? ' in-cart' : ''}`}
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

          <aside className={`tpos-cart pos-ui-cart${payAsReprint && lastSale ? ' is-done' : ''}`} aria-label="Cart">
            <div className="tpos-cart-head">
              <h2>Current sale</h2>
              <span className="tpos-items-badge">{cartCount} {cartCount === 1 ? 'item' : 'items'}</span>
              <button
                type="button"
                className="pos-clear-link"
                onClick={clearCart}
                disabled={!cart.length}
                aria-label="Clear POS cart"
              >
                Clear
              </button>
            </div>
            <label className="tpos-field tpos-customer pos-ui-customer">
              <span>
                Customer
                <a className="pos-new-customer" href="/customers" target="_blank" rel="noreferrer">
                  + New customer
                </a>
              </span>
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
            <div className="pos-cart-scroll">
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

            <div className="tpos-cart-list pos-ui-list">
              {cart.length === 0 && !payAsReprint ? (
                <div className="tpos-cart-empty">
                  <p>Scan or search, then tap a product to add it.</p>
                </div>
              ) : cart.length === 0 && payAsReprint && lastSale?.lines?.length ? (
                <div className="tpos-receipt-preview" aria-label="Last receipt preview">
                  <p className="tpos-receipt-preview-head">
                    Receipt {lastSale.reference}
                    {lastSale.offline ? ' · pending sync' : ''}
                  </p>
                  <ul>
                    {lastSale.lines.map((line, i) => (
                      <li key={`${line.name}-${i}`}>
                        <span>
                          {line.quantity} × {line.name}
                        </span>
                        <strong>{money(line.line)}</strong>
                      </li>
                    ))}
                  </ul>
                  <p className="tpos-receipt-preview-total">
                    <span>Total</span>
                    <strong>{money(Number(lastSale.total || 0))}</strong>
                  </p>
                </div>
              ) : (
                <div className="tpos-order-head" aria-hidden>
                  <span>Product</span>
                  <span>Qty</span>
                  <span>Line total</span>
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
                  <div key={c.id} className="tpos-cart-row pos-ui-line">
                    <div className="tpos-cart-product">
                      <strong className="tpos-cart-name" title={c.name}>
                        <span className="tpos-cart-name-text">{c.name}</span>
                      </strong>
                      <span className="tpos-cart-line-sub">
                        {c.rx_only ? <span className="tpos-cart-flag">Prescription</span> : null}
                        {stockOut ? (
                          <span className="tpos-cart-flag tpos-cart-flag-out">Out</span>
                        ) : c.is_low_stock ? (
                          <span className="tpos-cart-flag tpos-cart-flag-low">Low</span>
                        ) : null}
                        <span className="tpos-cart-unit">{money(unit)} each</span>
                      </span>
                    </div>
                    <div className="tpos-qty pos-ui-qty">
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
                    <div className="tpos-line">{money(taxable)}</div>
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

            <div className="tpos-cart-dock pos-ui-pay">
              <div className="tpos-cart-lines">
                {splitTender || payAsReprint ? null : (
                  <div className="pos-pay-methods" role="radiogroup" aria-label="How the customer pays">
                    {[
                      ['cash', 'Cash'],
                      ['card', 'Card'],
                      ['mobile_money', 'MoMo'],
                      ['bank_transfer', 'Bank'],
                    ].map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        role="radio"
                        aria-checked={paymentMethod === value}
                        className={`pos-pay-method${paymentMethod === value ? ' is-on' : ''}`}
                        onClick={() => setPaymentMethod(value)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                )}
                <div className="pos-ui-pay-method-row">
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
                  <label className="tpos-pay-select">
                    <span>Payment method</span>
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
                ) : (
                  <label className="tpos-pay-select pos-pay-other">
                    <span>Or</span>
                    <select
                      value={MAIN_PAY_METHODS.has(paymentMethod) ? '' : paymentMethod}
                      onChange={(e) => setPaymentMethod(e.target.value || 'cash')}
                      aria-label="POS payment method"
                    >
                      <option value="">More ways to pay…</option>
                      {online ? <option value="wallet">Wallet</option> : null}
                      {online ? <option value="gift_card">Gift card</option> : null}
                      {online ? <option value="loyalty">Loyalty points</option> : null}
                      {canCreditSale && (online || offlinePerms.includes('credit_sale')) ? (
                        <option value="credit">Credit</option>
                      ) : null}
                    </select>
                  </label>
                )}
                </div>
                {splitTender ? (
                  <div className="tpos-split-panel">
                    <p className="tpos-split-due">
                      <span>Amount due</span>
                      <strong>{money(cartTotal)}</strong>
                    </p>
                    {payAsReprint ? null : <p className="tpos-split-hint">
                      Cash plus one other method. Change one amount and the other fills in.
                    </p>}
                    <div className="tpos-split-fields">
                      <label className="tpos-field">
                        <span>Cash amount</span>
                        <AmountField
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
                      <label className="tpos-field tpos-split-other-amount">
                        <span>{splitOtherLabel} amount</span>
                        <AmountField
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
                ) : null}
                {payingCash && !payAsReprint && cart.length > 0 ? (
                  <div className="pos-cash-received">
                    <label className="tpos-field">
                      <span>Cash received</span>
                      <AmountField
                        className="tpos-input"
                        value={cashTender}
                        onChange={(e) => setCashTender(e.target.value)}
                        placeholder={cartTotal.toFixed(2)}
                        inputMode="decimal"
                        aria-label="Cash received"
                      />
                    </label>
                    <div className="pos-quick-cash" aria-label="Quick cash amounts">
                      {quickCash.map((v, i) => (
                        <button key={v} type="button" onClick={() => setCashTender(v.toFixed(2))}>
                          {i === 0 ? 'Exact' : money(v)}
                        </button>
                      ))}
                    </div>
                    {cashChangeDue > 0 ? (
                      <p className="pos-change-due" role="status">
                        <span>Change</span>
                        <strong>{money(cashChangeDue)}</strong>
                      </p>
                    ) : cashShort ? (
                      <p className="pos-change-due is-short" role="status">
                        <span>Still to pay</span>
                        <strong>{money(Math.round((cartTotal - cashTenderAmount) * 100) / 100)}</strong>
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {!splitTender && paymentMethod === 'gift_card' ? (
                  <label className="tpos-field">
                    <span>Gift card code</span>
                    <input
                      value={giftCardCode}
                      onChange={(e) => setGiftCardCode(e.target.value)}
                      aria-label="Gift card code"
                      autoComplete="off"
                    />
                  </label>
                ) : null}
                {!payAsReprint && !splitTender && paymentMethod === 'mobile_money' ? (
                  <p className="tpos-split-hint">
                    The till does not charge a phone. Confirm the MoMo payment first.
                  </p>
                ) : null}
                {!payAsReprint && !splitTender && paymentMethod === 'card' ? (
                  <p className="tpos-split-hint">
                    The till does not charge the card. Take it on the card machine first.
                  </p>
                ) : null}
                {!payAsReprint && !splitTender && paymentMethod === 'bank_transfer' ? (
                  <p className="tpos-split-hint">
                    Check the transfer has arrived before you press Pay.
                  </p>
                ) : null}
                {!payAsReprint && !splitTender && (paymentMethod === 'wallet' || paymentMethod === 'gift_card' || paymentMethod === 'loyalty') ? (
                  <p className="tpos-split-hint">
                    {paymentMethod === 'wallet' ? 'Wallet' : paymentMethod === 'gift_card' ? 'Gift card' : 'Loyalty points'} is online only. This register does not send a live charge.
                  </p>
                ) : null}
                {!payAsReprint && !online ? (
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
                      <AmountField
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
              </div>
              <div className="tpos-cart-actions">
                <button
                  type="button"
                  className="tpos-btn tpos-keypad-toggle"
                  aria-expanded={keypadOpen}
                  onClick={() => setKeypadOpen((open) => !open)}
                  aria-label={keypadOpen ? 'Hide keypad' : 'Show keypad'}
                >
                  {keypadOpen ? 'Hide keypad' : 'Keypad'}
                </button>
                {keypadOpen ? (
                <div className="tpos-keypad" role="group" aria-label="POS keypad">
                  {['1', '2', '3', '4', '5', '6', '7', '8', '9', 'C', '0', '⌫'].map((key) => (
                    <button
                      key={key}
                      type="button"
                      className="tpos-key"
                      disabled={!session || payAsReprint}
                      onClick={() => applyKeypad(key)}
                      aria-label={
                        key === 'C' ? 'Clear keypad value' : key === '⌫' ? 'Delete last keypad digit' : `Keypad ${key}`
                      }
                    >
                      {key}
                    </button>
                  ))}
                </div>
                ) : null}
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
              <details className="pos-ui-optional">
                <summary>Discount, coupon and receipt options</summary>
                <div className="print-ui-row">
                  <label className="print-ui-paper">
                    Receipt paper
                    <select
                      value={receiptPaper === '58mm' ? '58mm' : '80mm'}
                      onChange={(e) => setReceiptPaper(e.target.value === '58mm' ? '58mm' : '80mm')}
                      aria-label="POS receipt paper"
                    >
                      <option value="58mm">58mm receipt</option>
                      <option value="80mm">80mm receipt</option>
                    </select>
                  </label>
                </div>

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
                      {cartDiscountType === 'percent' ? (
                        <input
                          className="tpos-input"
                          type="number"
                          min={0}
                          step="0.01"
                          value={cartDiscount}
                          onChange={(e) => setCartDiscount(e.target.value)}
                          placeholder="0"
                          inputMode="decimal"
                          aria-label="POS cart discount"
                        />
                      ) : (
                        <AmountField
                          inline
                          className="tpos-input"
                          type="number"
                          min={0}
                          step="0.01"
                          value={cartDiscount}
                          onChange={(e) => setCartDiscount(e.target.value)}
                          placeholder="0.00"
                          inputMode="decimal"
                          aria-label="POS cart discount"
                        />
                      )}
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
              </details>
              {payAsReprint && lastSale && !lastSale.offline ? null : message ? (
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
            </div>
            <div className="pos-cart-foot">
              {payAsReprint && lastSale ? (
                <div className="pos-done" role="status" aria-label="Sale complete">
                  <p className="pos-done-title">
                    <span aria-hidden>✓</span>{' '}
                    {lastSale.offline
                      ? 'Sale saved · sends when back online'
                      : String(lastSale.payment_status || '').toLowerCase() === 'paid' &&
                          !(Number(lastSale.balance_due || 0) > 0)
                        ? `Paid ${money(Number(lastSale.total || 0))}`
                        : `Sale saved ${money(Number(lastSale.total || 0))}`}
                  </p>
                  {lastChange ? (
                    <p className="pos-done-change">
                      <span>Give change</span>
                      <strong>{money(lastChange)}</strong>
                    </p>
                  ) : null}
                  <div className="pos-done-actions">
                    <button
                      type="button"
                      className="tpos-btn tpos-btn-primary pos-done-new"
                      onClick={startNextSale}
                      aria-label="Start new sale"
                    >
                      New sale
                    </button>
                    <button
                      type="button"
                      className="tpos-btn pos-done-print"
                      onClick={reprintLastReceipt}
                      disabled={!!receiptBusy}
                      aria-label="Print receipt"
                    >
                      {receiptBusy === 'reprint' ? 'Printing…' : 'Print receipt'}
                    </button>
                  </div>
                </div>
              ) : (
                <>
              <div className="tpos-total pos-ui-due" aria-label="POS cart totals">
                {payAsReprint ? null : (
                  <dl className="pos-totals">
                    <div>
                      <dt>Subtotal</dt>
                      <dd>{money(cartTotals.subtotal)}</dd>
                    </div>
                    {cartTotals.tax > 0 ? (
                      <div>
                        <dt>Tax</dt>
                        <dd>{money(cartTotals.tax)}</dd>
                      </div>
                    ) : null}
                    {cartDiscountAmount > 0 ? (
                      <div>
                        <dt>Discount</dt>
                        <dd>−{money(cartDiscountAmount)}</dd>
                      </div>
                    ) : null}
                    {paymentMethod === 'credit' && !splitTender ? (
                      <div>
                        <dt>On account</dt>
                        <dd>{money(creditRemaining)}</dd>
                      </div>
                    ) : null}
                  </dl>
                )}
                <p className="pos-total-row">
                  <span className="pos-ui-due-label">Total</span>
                  <strong>{money(cartTotal)}</strong>
                </p>
              </div>
              {error ? (
                <p className="tpos-banner tpos-banner-err" role="alert">
                  {error}
                </p>
              ) : null}
                <div className="tpos-pay-row">
                <button
                  type="button"
                  className="tpos-btn tpos-btn-pay"
                  onClick={checkout}
                  disabled={!cart.length || !session || busy}
                  title={
                    !session
                      ? 'Open a POS shift before charging'
                      : !cart.length
                        ? 'Add a product before charging'
                        : busy
                          ? 'This sale is already being saved'
                          : ''
                  }
                  aria-label="Charge"
                >
                  {busy ? 'Paying…' : `Pay ${money(cartTotal)}`}
                </button>
                </div>
                </>
              )}
            </div>
          </aside>
        </div>
      </div>
    </>
  );
}
