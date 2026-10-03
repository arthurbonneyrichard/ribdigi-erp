'use client';

import dynamic from 'next/dynamic';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, apiFetch, isAbortError } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { getPrefetched } from '../../../lib/prefetchCache';
import { pageLoadStarted } from '../../../lib/navTiming';
import { useStoreContext } from '../../../lib/storeContext';
import { isHotelIndustry, tenantIsMultiStore } from '../../../lib/tenantNav';
import { normalizeIndustry } from '../../../lib/industries';
import {
  cacheCatalogProducts,
  countPendingSales,
  downloadRecoveryPackage,
  enqueueOfflineSale,
  flushOfflineQueue,
  formatCacheAge,
  getCachedCatalogMeta,
  getCachedProducts,
  getOrCreateDeviceId,
  getOfflineAuthEnvelope,
  importRecoveryPackage,
  isOfflineAuthValid,
  newClientRequestId,
  saveOfflineAuthEnvelope,
  touchLastOnline,
} from '../../../lib/posOffline';

const PosPrintStatus = dynamic(() => import('../../../components/PosPrintStatus'), { ssr: false });

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
};

function looksLikeBarcode(value: string) {
  const text = value.trim();
  if (!text || /\s/.test(text)) return false;
  return /^[A-Za-z0-9\-._]{4,48}$/.test(text);
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
};

async function downloadReceiptPdf(saleId: string) {
  const res = await apiFetch(`/pos/sales/${saleId}/receipt?format=pdf`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.message || 'PDF download failed');
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `receipt-${saleId.slice(0, 8)}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

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
  const [q, setQ] = useState('');
  const [rows, setRows] = useState<Product[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [openingCash, setOpeningCash] = useState('100');
  const [actualCash, setActualCash] = useState('');
  const [closeNotes, setCloseNotes] = useState('');
  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState('');
  const { storeId: ctxStoreId, setStoreId: setCtxStoreId } = useStoreContext();
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [canCreditSale, setCanCreditSale] = useState(false);
  const [splitTender, setSplitTender] = useState(false);
  const [cashTender, setCashTender] = useState('');
  const [cardTender, setCardTender] = useState('');
  const [amountPaidNow, setAmountPaidNow] = useState('');
  const [depositMethod, setDepositMethod] = useState('cash');
  const [paymentReference, setPaymentReference] = useState('');
  const [receiptTo, setReceiptTo] = useState('');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [creditOverrideReason, setCreditOverrideReason] = useState('');
  const [drawerReason, setDrawerReason] = useState('');
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
  } | null>(null);
  const [printJobs, setPrintJobs] = useState<any[]>([]);
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
  const [showOfflineTools, setShowOfflineTools] = useState(false);
  const [newCustName, setNewCustName] = useState('');
  const [custBusy, setCustBusy] = useState(false);
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

  useEffect(() => {
    if (!canCreditSale && paymentMethod === 'credit') setPaymentMethod('cash');
  }, [canCreditSale, paymentMethod]);

  async function refreshSession() {
    const r = await api('/pos/sessions/current');
    setSession(r.data || null);
  }

  const browse = useCallback(async (query = '', opts?: { signal?: AbortSignal }) => {
    const posStore = (session?.store_id || storeId).trim();
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    if (posStore) params.set('store_id', posStore);
    const gen = ++browseGen.current;
    setCatalogLoading(true);
    try {
      const r = await api('/pos/products/search?' + params.toString(), {
        signal: opts?.signal,
      });
      const list = (r.data || []) as Product[];
      if (gen !== browseGen.current) return list;
      setRows(list);
      if (!query.trim()) {
        await cacheCatalogProducts(list as any[]);
        const meta = await getCachedCatalogMeta();
        setCatalogCachedAt(meta?.cached_at || new Date().toISOString());
      }
      await touchLastOnline();
      return list;
    } catch (err) {
      if (isAbortError(err)) return [];
      if (!navigator.onLine || query === '') {
        const cached = (await getCachedProducts()) as Product[];
        const filtered = query.trim()
          ? cached.filter(
              (p) =>
                String(p.name || '').toLowerCase().includes(query.toLowerCase()) ||
                String(p.sku || '').toLowerCase().includes(query.toLowerCase())
            )
          : cached;
        if (gen === browseGen.current) setRows(filtered);
        const meta = await getCachedCatalogMeta();
        setCatalogCachedAt(meta?.cached_at || null);
        return filtered;
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
    refreshPendingCount();
    getCachedCatalogMeta()
      .then((m) => setCatalogCachedAt(m?.cached_at || null))
      .catch(() => null);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);

  useEffect(() => {
    if (!online) return;
    flushOfflineQueue(api)
      .then(async (r) => {
        if (r.synced > 0) {
          setMessage(`Synced ${r.synced} offline sale(s)`);
          await refreshSession();
        }
        if (r.conflicts > 0) {
          setError(
            `${r.conflicts} offline sale(s) need review — stock or price differs from the server. Nothing was dropped.`
          );
        }
        if (r.expired > 0) {
          setError('Offline authorization expired — reconnect to revalidate before restore. Queued sales were not deleted.');
        }
        await refreshPendingCount();
      })
      .catch(() => undefined);
  }, [online]);

  useEffect(() => {
    if (!online) return;
    let cancelled = false;
    async function beat() {
      try {
        const pending = await countPendingSales();
        await api('/pos/devices/heartbeat', {
          method: 'POST',
          body: JSON.stringify({
            device_id: getOrCreateDeviceId(),
            store_id: storeId.trim() || session?.store_id || null,
            app_version: 'web-mvp',
            pending_queue_count: pending,
          }),
        });
      } catch {
        /* heartbeat best-effort */
      }
    }
    beat();
    const t = window.setInterval(() => {
      if (!cancelled && navigator.onLine) beat();
    }, 60000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, [online, storeId, session?.store_id]);

  async function exportRecovery() {
    setError('');
    try {
      const pkg = await downloadRecoveryPackage();
      setMessage(
        `Recovery package downloaded (${pkg.pending.length} pending sale(s)). Contains no passwords or tokens.`
      );
    } catch (err: any) {
      setError(err.message || 'Recovery export failed');
    }
  }

  async function importRecoveryFile(file: File | null) {
    if (!file) return;
    setError('');
    try {
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        throw new Error('Reconnect online before restoring a recovery package. The server remains the source of truth.');
      }
      const text = await file.text();
      const raw = JSON.parse(text);
      const r = await importRecoveryPackage(raw);
      await refreshPendingCount();
      setMessage(`Imported ${r.imported} queued sale(s) (${r.skipped} skipped). Sync when online.`);
    } catch (err: any) {
      setError(err.message || 'Recovery import failed');
    }
  }

  useEffect(() => {
    const ac = new AbortController();
    const done = pageLoadStarted('pos');
    let cancelled = false;
    (async () => {
      try {
        const [sess, storeRes, meRes] = await Promise.all([
          getPrefetched('/pos/sessions/current'),
          getPrefetched('/pos/stores'),
          getMe(),
        ]);
        if (cancelled) return;
        setSession(sess.data || null);
        const list: Store[] = storeRes.data || [];
        setStores(list);
        if (ctxStoreId && list.some((s) => s.id === ctxStoreId)) {
          setStoreId(ctxStoreId);
        } else if (list.length === 1) {
          setStoreId(list[0].id);
          setCtxStoreId(list[0].id);
        }
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
        if (pharmacy) {
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
      api('/customers')
        .then((r) => {
          if (!cancelled) setCustomers(r.data || []);
        })
        .catch(() => {
          if (!cancelled) setCustomers([]);
        });
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [session?.session_id]);

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

  async function createPosCustomer() {
    const name = newCustName.trim();
    if (!name) {
      setError('Enter a customer name');
      return;
    }
    if (custBusy) return;
    setCustBusy(true);
    setError('');
    try {
      const r = await api('/customers', {
        method: 'POST',
        body: JSON.stringify({ name, profile_type: 'registered', status: 'active' }),
      });
      const created = r.data;
      if (!created?.id) throw new Error(r.message || 'Could not create customer');
      setCustomers((prev) => [created, ...prev.filter((c) => c.id !== created.id)]);
      setCustomerId(created.id);
      setCustomerName(created.name || name);
      setNewCustName('');
      setMessage(`Customer ${created.name || name} saved`);
    } catch (err: any) {
      setError(err.message || 'Could not create customer');
    } finally {
      setCustBusy(false);
    }
  }

  async function openShift() {
    setError('');
    setMessage('');
    if (shiftBusy) return;
    if (stores.length > 0 && !storeId) {
      setError('Select a store before opening the shift');
      return;
    }
    setShiftBusy(true);
    try {
      const r = await api('/pos/sessions/open', {
        method: 'POST',
        body: JSON.stringify({
          opening_cash: Number(openingCash) || 0,
          // null when blank so Open shift (UuidIdValue store_id) does not 422
          store_id: storeId.trim() || null,
        }),
      });
      setSession(r.data);
      setMessage(
        r.data?.session_number
          ? `Shift opened · ${r.data.session_number}`
          : 'Shift opened'
      );
      try {
        const me = await getMe();
        const tenant = localStorage.getItem('tenant') || me.data?.tenant_id || '';
        let hours = 168;
        try {
          const policy = await api('/pos/offline-policy');
          hours = Number(policy.data?.offline_auth_hours) || 168;
        } catch {
          /* use default 168h */
        }
        const uid = String(me.data?.id || me.data?.user_id || '');
        if (uid) {
          try {
            sessionStorage.setItem('ribdigi:uid', uid);
            sessionStorage.setItem('ribdigi:store', String(r.data?.store_id || storeId.trim() || ''));
          } catch {
            /* ignore */
          }
        }
        const env = await saveOfflineAuthEnvelope({
          tenant_id: String(tenant),
          store_id: r.data?.store_id || storeId.trim() || null,
          user_id: uid,
          permissions: ['pos:write'],
          offline_auth_hours: hours,
        });
        void env;
      } catch {
        /* offline envelope best-effort */
      }
      await browse(q);
      await refreshPendingCount();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setShiftBusy(false);
    }
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

  async function closeShift() {
    if (!session) return;
    setError('');
    setMessage('');
    try {
      const r = await api(`/pos/sessions/${session.session_id}/close`, {
        method: 'POST',
        body: JSON.stringify({
          actual_cash: Number(actualCash || session.expected_cash),
          notes: closeNotes.trim() || null,
        }),
      });
      setSession(null);
      setShiftReport(null);
      setMessage(
        `Shift closed. Variance: ${r.data.variance ?? 0} (expected ${r.data.expected_cash})`
      );
      setActualCash('');
      setCloseNotes('');
      setCart([]);
    } catch (err: any) {
      setError(err.message);
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

  async function search(e?: React.FormEvent) {
    e?.preventDefault();
    setError('');
    const query = q.trim();
    try {
      // USB/Bluetooth wedge scanners type digits then Enter — accept as barcode.
      if (looksLikeBarcode(query)) {
        const params = new URLSearchParams();
        params.set('barcode', query);
        const posStore = (session?.store_id || storeId).trim();
        if (posStore) params.set('store_id', posStore);
        const exact = await api('/pos/products/search?' + params.toString());
        const hits: Product[] = exact.data || [];
        if (hits.length === 1) {
          addToCart(hits[0]);
          setMessage(`Scanned ${hits[0].name} (${hits[0].barcode || hits[0].sku})`);
          skipEmptyBrowse.current = true;
          setQ('');
          return;
        }
        if (hits.length === 0) {
          // Fall back to SKU / name search for the same token.
          const soft = await browse(query);
          if (soft.length === 1) {
            addToCart(soft[0]);
            setMessage(`Added ${soft[0].name}`);
            skipEmptyBrowse.current = true;
            setQ('');
            return;
          }
          if (soft.length === 0) {
            setError(`No product for barcode ${query}`);
            return;
          }
          setMessage(`${soft.length} matches — tap a tile`);
          return;
        }
        setRows(hits);
        setMessage(`${hits.length} barcode matches — tap a tile`);
        return;
      }
      await browse(query);
    } catch (err: any) {
      setError(err.message);
    }
  }

  function addToCart(product: Product) {
    if (!session) {
      setError('Open a POS shift before selling');
      return;
    }
    const avail = Math.max(0, Number(product.stock_qty) || 0);
    if (avail <= 0 || product.is_out_of_stock) {
      setError(`${product.name} is out of stock at this store`);
      return;
    }
    const pid = product.product_id || product.id;
    const existing = cart.find((p) => p.id === product.id);
    if (existing && existing.quantity >= avail) {
      setError(`Only ${avail} of ${product.name} in stock at this store`);
      return;
    }
    setError('');
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

  function bumpQty(id: string, delta: number) {
    const line = cart.find((p) => p.id === id);
    if (!line) return;
    if (delta > 0 && line.quantity + delta > Number(line.stock_qty)) {
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
    if (quantity > Number(line.stock_qty)) {
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
      customer_name: customerId.trim() ? name.trim() || null : null,
      items,
    };
    let payments: { payment_method: string; amount: number; reference?: string | null }[] | null =
      null;
    const tenderRef = paymentReference.trim() || null;
    if (splitTender) {
      payments = [
        { payment_method: 'cash', amount: Number(cashTender) || 0, reference: null },
        { payment_method: 'card', amount: Number(cardTender) || 0, reference: tenderRef },
      ].filter((p) => p.amount > 0);
      if (payments.length < 2) {
        setError('Split tender needs cash and card amounts');
        return;
      }
      body.payments = payments;
      body.payment_method = 'split';
    } else if (!splitTender && paymentMethod === 'credit') {
      const paidNow = Math.round((Number(amountPaidNow) || 0) * 100) / 100;
      const remaining = Math.max(0, Math.round((cartTotal - paidNow) * 100) / 100);
      if (paidNow > 0 && remaining > 0) {
        payments = [
          { payment_method: depositMethod, amount: paidNow, reference: tenderRef },
          { payment_method: 'credit', amount: remaining, reference: null },
        ];
        body.payments = payments;
        body.payment_method = 'split';
      } else if (paidNow > 0 && remaining <= 0) {
        body.payment_method = depositMethod;
        if (tenderRef) {
          payments = [{ payment_method: depositMethod, amount: cartTotal, reference: tenderRef }];
          body.payments = payments;
        }
      } else if (tenderRef) {
        payments = [{ payment_method: 'credit', amount: cartTotal, reference: tenderRef }];
        body.payments = payments;
        body.payment_method = 'credit';
      } else {
        body.payment_method = 'credit';
      }
    } else if (tenderRef) {
      // PosPaymentLine.reference only applies on payments[]; wrap single tender.
      payments = [
        {
          payment_method: paymentMethod,
          amount: cartTotal,
          reference: tenderRef,
        },
      ];
      body.payments = payments;
      body.payment_method = paymentMethod;
    } else {
      body.payment_method = paymentMethod;
    }
    setBusy(true);
    try {
      const clientRequestId = checkoutReqRef.current || newClientRequestId();
      checkoutReqRef.current = clientRequestId;
      body.client_request_id = clientRequestId;

      // Offline cash sales queue locally; card/momo never fabricate provider success.
      if (!navigator.onLine) {
        if (splitTender || paymentMethod !== 'cash') {
          throw new Error(
            'While offline, only cash sales can be completed. Card/mobile money require confirmation when online.'
          );
        }
        if (!isOfflineAuthValid(await getOfflineAuthEnvelope())) {
          throw new Error('Offline authorization expired — reconnect before selling');
        }
        const store = stores.find((s) => s.id === (session.store_id || storeId));
        const queued = await enqueueOfflineSale({
          tenant_id: localStorage.getItem('tenant') || '',
          store_id: session.store_id || storeId || null,
          store_code: store?.code || 'STORE',
          user_id: String((await getMe().catch(() => ({ data: {} }))).data?.id || ''),
          payload: { ...body, total: cartTotal },
        });
        setCart([]);
        setCartDiscount('');
        setCustomerId('');
        setCustomerName('');
        setCreditOverrideReason('');
        setPaymentReference('');
        setSplitTender(false);
        setCashTender('');
        setCardTender('');
        setLastSale({ id: queued.id, reference: queued.local_receipt_number });
        setMessage(
          `Queued offline sale ${queued.local_receipt_number} (will sync when online). Cached stock is not live.`
        );
        await refreshPendingCount();
        return;
      }

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
          setCashTender(String((body.payments as any[]).find((p) => p.payment_method === 'cash')?.amount ?? ''));
          setCardTender(String((body.payments as any[]).find((p) => p.payment_method === 'card')?.amount ?? ''));
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
      setPaymentReference('');
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
      setPrintJobs(Array.isArray(r.data.print_jobs) ? r.data.print_jobs : []);
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
    } catch (err: any) {
      setMessage('');
      setLastSale(null);
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function printLastReceipt() {
    if (!lastSale) return;
    setError('');
    setReceiptBusy('print');
    try {
      await downloadReceiptPdf(lastSale.id);
    } catch (err: any) {
      setError(err.message);
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
            <p className="muted">
              {cashierName ? cashierName : 'Tap a product or scan a barcode'}
              {' · '}
              {online ? 'Online' : 'Offline'}
              {pendingOffline > 0 ? ` · ${pendingOffline} waiting to sync` : ''}
              {!online ? ' · Cached stock may be stale' : ''}
              {!online && catalogCachedAt ? ` · Saved catalog ${formatCacheAge(catalogCachedAt)}` : ''}
            </p>
            {(pendingOffline > 0 || !online) && (
              <div className="tpos-offline-tools">
                <button
                  type="button"
                  className="tpos-btn tpos-btn-quiet"
                  onClick={() => setShowOfflineTools((v) => !v)}
                >
                  {showOfflineTools ? 'Hide backup' : 'Offline backup'}
                </button>
                {showOfflineTools && (
                  <div className="tpos-recovery">
                    <button type="button" className="tpos-btn" onClick={exportRecovery}>
                      Save backup
                    </button>
                    <label className="tpos-btn">
                      Restore backup
                      <input
                        type="file"
                        accept="application/json,.json"
                        aria-label="Restore offline backup"
                        style={{ display: 'none' }}
                        onChange={(e) => {
                          const f = e.target.files?.[0] || null;
                          importRecoveryFile(f).finally(() => {
                            e.target.value = '';
                          });
                        }}
                      />
                    </label>
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="tpos-shift">
            {!session ? (
              <>
                {stores.length > 0 && !hideStorePicker && (
                  <select
                    className="tpos-input"
                    value={storeId}
                    onChange={(e) => {
                      setStoreId(e.target.value);
                      setCtxStoreId(e.target.value);
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
                <input
                  className="tpos-input"
                  value={openingCash}
                  onChange={(e) => setOpeningCash(e.target.value)}
                  inputMode="decimal"
                  placeholder="Opening cash"
                  aria-label="Opening cash"
                />
                <button
                  type="button"
                  className="tpos-btn tpos-btn-primary"
                  onClick={openShift}
                  disabled={shiftBusy}
                  aria-label="Open shift"
                >
                  {shiftBusy ? 'Opening…' : 'Open shift'}
                </button>
              </>
            ) : (
              <>
                <div className="tpos-shift-meta">
                  <strong>{session.session_number}</strong>
                  <span>
                    {session.store_name ? `${session.store_name} · ` : ''}
                    {session.sale_count} sales · {money(Number(session.total_sales || 0))}
                  </span>
                </div>
                <button
                  type="button"
                  className="tpos-btn"
                  onClick={loadShiftReport}
                  disabled={reportBusy}
                  aria-label={shiftReport ? 'Hide shift report' : 'Show shift report'}
                >
                  {reportBusy ? 'Loading…' : shiftReport ? 'Hide report' : 'Shift report'}
                </button>
                <details className="tpos-more">
                  <summary>Drawer</summary>
                  <div className="tpos-more-body">
                    <input
                      className="tpos-input"
                      value={drawerReason}
                      onChange={(e) => setDrawerReason(e.target.value)}
                      placeholder="Reason"
                      maxLength={200}
                      autoComplete="off"
                      aria-label="Cash drawer open reason"
                    />
                    <button
                      type="button"
                      className="tpos-btn"
                      aria-label="Open cash drawer"
                      onClick={async () => {
                        setError('');
                        const cleaned = drawerReason.trim();
                        if (
                          cleaned.length < 3 ||
                          ['manual', 'n/a', 'na', 'none', 'test'].includes(cleaned.toLowerCase())
                        ) {
                          setError('Enter a drawer reason (at least 3 characters)');
                          return;
                        }
                        try {
                          const r = await api(`/pos/sessions/${session.session_id}/drawer/open`, {
                            method: 'POST',
                            body: JSON.stringify({ reason: cleaned }),
                          });
                          setDrawerReason('');
                          setMessage(r.data?.message || r.message || 'Drawer opened');
                        } catch (err: any) {
                          setError(err.message);
                        }
                      }}
                    >
                      Open drawer
                    </button>
                  </div>
                </details>
                <section className="tpos-cash" aria-label="Shift drawer cash">
                  <p className="tpos-cash-balance">
                    <span>Drawer</span>
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
                <details className="tpos-more">
                  <summary>Close shift</summary>
                  <div className="tpos-more-body">
                    <input
                      className="tpos-input"
                      value={actualCash}
                      onChange={(e) => setActualCash(e.target.value)}
                      inputMode="decimal"
                      placeholder={`Counted cash (${session.expected_cash})`}
                      aria-label="Counted cash"
                    />
                    <input
                      className="tpos-input"
                      value={closeNotes}
                      onChange={(e) => setCloseNotes(e.target.value)}
                      placeholder="Notes (optional)"
                      aria-label="POS shift close notes"
                    />
                    <button type="button" className="tpos-btn" onClick={closeShift} aria-label="Close shift">
                      Close shift
                    </button>
                  </div>
                </details>
              </>
            )}
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
              {shiftReport.session?.cashier_name
                ? `Cashier ${shiftReport.session.cashier_name} · `
                : ''}
              {shiftReport.summary?.sale_count ?? 0} sales · tax{' '}
              {money(Number(shiftReport.summary?.tax || 0))} · net after returns{' '}
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
                    <th>Disc</th>
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
                      <td>
                        {sale.created_at
                          ? String(sale.created_at).replace('T', ' ').slice(0, 16)
                          : '—'}
                      </td>
                      <td>{sale.customer_name || 'Walk-in'}</td>
                      <td>
                        {sale.payment_method === 'split' && sale.payments?.length
                          ? sale.payments
                              .map(
                                (p: any) =>
                                  `${String(p.payment_method || '').toUpperCase()} ${money(
                                    Number(p.amount || 0)
                                  )}`
                              )
                              .join(' + ')
                          : String(sale.payment_method || 'cash').toUpperCase()}
                        {sale.payment_status && sale.payment_status !== 'paid'
                          ? ` · ${String(sale.payment_status).replace(/_/g, ' ')}`
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
                        <td>{ret.reason}</td>
                        <td>{ret.status}</td>
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
                placeholder="Scan barcode or search name / SKU"
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
                <p>{bootLoading ? 'Loading POS…' : 'Open a shift to unlock the product catalog.'}</p>
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
                    </div>
                    <div className="tpos-tile-body">
                      <strong title={r.name}>{r.name}</strong>
                      <span className="tpos-sku" title={r.sku || undefined}>
                        {r.sku}
                      </span>
                      <div className="tpos-tile-foot">
                        <div className="tpos-price-pair">
                          {r.cost_price != null && Number.isFinite(Number(r.cost_price)) ? (
                            <span className="tpos-price-actual">
                              <span className="tpos-price-label">Actual</span>
                              <span className="tpos-price-value">{money(Number(r.cost_price))}</span>
                            </span>
                          ) : null}
                          <span className="tpos-price-selling">
                            <span className="tpos-price-label">Selling</span>
                            <span className="tpos-price-value">{money(Number(r.selling_price))}</span>
                          </span>
                        </div>
                        <span
                          className="tpos-stock"
                          title={
                            online
                              ? `${r.stock_qty} in stock`
                              : `Cached: ${r.stock_qty} · ${formatCacheAge(catalogCachedAt)}`
                          }
                        >
                          {online ? `${r.stock_qty} left` : `${r.stock_qty} left`}
                          {r.nearest_expiry_date ? ` · FEFO ${r.nearest_expiry_date}` : ''}
                          {r.rx_only ? ' · Rx' : ''}
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
                  <p>Tap a product or scan a barcode.</p>
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
                        {c.rx_only ? <span className="tpos-cart-flag">Rx</span> : null}
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
                <div className="tpos-name-ref">
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
                  <label className="tpos-field">
                    <span>Payment reference</span>
                    <input
                      className="tpos-input"
                      value={paymentReference}
                      onChange={(e) => setPaymentReference(e.target.value)}
                      placeholder="Card/auth ref (optional)"
                      aria-label="POS payment reference"
                      title="Optional tender reference (1–100 chars; letters/digits required)"
                      maxLength={100}
                      autoComplete="off"
                    />
                  </label>
                </div>
                <label className="tpos-split-toggle">
                  <input
                    type="checkbox"
                    aria-label="POS split tender"
                    checked={splitTender}
                    onChange={(e) => enableSplit(e.target.checked)}
                  />
                  <span>Split cash + card</span>
                </label>
                <label className="tpos-pay-select">
                  <span>Payment</span>
                  <select
                    value={paymentMethod}
                    onChange={(e) => setPaymentMethod(e.target.value)}
                    aria-label="POS payment method"
                  >
                    <option value="cash">Cash</option>
                    <option value="card">Card</option>
                    <option value="wallet">Wallet</option>
                    {canCreditSale ? <option value="credit">Credit</option> : null}
                  </select>
                </label>
                {splitTender ? (
                  <div className="tpos-split-fields">
                    <label className="tpos-field">
                      <span>Cash</span>
                      <input
                        className="tpos-input tpos-cash-tender"
                        type="number"
                        min={0}
                        step="0.01"
                        value={cashTender}
                        onChange={(e) => {
                          const cash = Number(e.target.value) || 0;
                          setCashTender(e.target.value);
                          setCardTender(String(Math.max(0, Math.round((cartTotal - cash) * 100) / 100)));
                        }}
                        inputMode="decimal"
                        aria-label="POS cash tender"
                      />
                    </label>
                    <label className="tpos-field">
                      <span>Card</span>
                      <input
                        className="tpos-input tpos-card-tender"
                        type="number"
                        min={0}
                        step="0.01"
                        value={cardTender}
                        onChange={(e) => {
                          const card = Number(e.target.value) || 0;
                          setCardTender(e.target.value);
                          setCashTender(String(Math.max(0, Math.round((cartTotal - card) * 100) / 100)));
                        }}
                        inputMode="decimal"
                        aria-label="POS card tender"
                      />
                    </label>
                  </div>
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
                        <span>Paid-now method</span>
                        <select
                          value={depositMethod}
                          onChange={(e) => setDepositMethod(e.target.value)}
                          aria-label="POS deposit method"
                        >
                          <option value="cash">Cash</option>
                          <option value="card">Card</option>
                          <option value="wallet">Digital wallet</option>
                        </select>
                      </label>
                    ) : null}
                  </>
                ) : splitTender ? (
                  <p className="tpos-split-hint">
                    Split {money((Number(cashTender) || 0) + (Number(cardTender) || 0))} · due{' '}
                    {money(cartTotal)}
                  </p>
                ) : null}
                {paymentMethod === 'credit' && !splitTender ? (
                  <label className="tpos-field">
                    <span>Credit override reason</span>
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
                <label className="tpos-field tpos-new-customer">
                  <span>New customer</span>
                  <input
                    className="tpos-input"
                    value={newCustName}
                    onChange={(e) => setNewCustName(e.target.value)}
                    placeholder="Name"
                    maxLength={180}
                    autoComplete="off"
                    aria-label="Create POS customer name"
                  />
                  <button
                    type="button"
                    className="tpos-btn"
                    onClick={createPosCustomer}
                    disabled={custBusy || !newCustName.trim()}
                    aria-label="Save new customer"
                  >
                    {custBusy ? 'Saving…' : 'Save'}
                  </button>
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
                  {cartDiscountAmount > 0 ? ` · Disc −${money(cartDiscountAmount)}` : ''}
                  {paymentMethod === 'credit' && !splitTender
                    ? ` · On account ${money(creditRemaining)}`
                    : ''}
                </span>
                <strong>{money(cartTotal)}</strong>
              </div>
              <div className="tpos-cart-actions">
                <button
                  type="button"
                  className="tpos-btn"
                  onClick={clearCart}
                  disabled={!cart.length}
                  aria-label="Clear POS cart"
                >
                  Clear
                </button>
                <button
                  type="button"
                  className="tpos-btn tpos-btn-pay"
                  onClick={checkout}
                  disabled={!cart.length || !session || busy}
                  aria-label="Pay"
                >
                  {busy ? 'Paying…' : `Pay ${money(cartTotal)}`}
                </button>
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
                      <button
                        type="button"
                        className="tpos-btn"
                        onClick={printLastReceipt}
                        disabled={!!receiptBusy}
                        aria-label="Print last receipt"
                      >
                        {receiptBusy === 'print' ? 'Printing…' : 'Print receipt'}
                      </button>
                      <input
                        type="text"
                        value={receiptTo}
                        onChange={(e) => setReceiptTo(e.target.value)}
                        placeholder="Email or phone"
                        aria-label="Receipt email or phone"
                        disabled={!!receiptBusy}
                      />
                      <button
                        type="button"
                        className="tpos-btn"
                        onClick={() => sendLastReceipt('email')}
                        disabled={!!receiptBusy}
                      >
                        {receiptBusy === 'email' ? 'Sending…' : 'Email'}
                      </button>
                      <button
                        type="button"
                        className="tpos-btn"
                        onClick={() => sendLastReceipt('sms')}
                        disabled={!!receiptBusy}
                      >
                        {receiptBusy === 'sms' ? 'Sending…' : 'SMS'}
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}
              {lastSale ? (
                <PosPrintStatus key={lastSale.id} jobs={printJobs} saleId={lastSale.id} />
              ) : null}
            </div>
          </aside>
        </div>
      </div>
    </>
  );
}
