'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

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
  stock_qty: number;
  kind?: string;
  has_image?: boolean;
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

type CartItem = Product & { quantity: number; discount: number };

type Customer = {
  id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
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
  card_sales: number;
  other_sales: number;
  total_sales: number;
  sale_count: number;
  actual_cash?: number | null;
  variance?: number | null;
  store_id?: string | null;
  store_name?: string | null;
  store_address?: string | null;
};

type RecentSale = {
  id: string;
  reference: string;
  total: number;
  tax?: number;
  payment_method?: string;
  payments?: { payment_method: string; amount: number }[];
  customer_name?: string | null;
  created_at?: string;
};

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

async function downloadReceiptPdf(saleId: string, paper: string) {
  const token = localStorage.getItem('token');
  const tenant = localStorage.getItem('tenant');
  const res = await fetch(`${apiBase}/pos/sales/${saleId}/receipt?format=pdf&paper=${paper}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
    },
  });
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

function ProductThumb({
  productId,
  hasImage,
  name,
}: {
  productId: string;
  hasImage?: boolean;
  name: string;
}) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    let objectUrl: string | null = null;
    async function load() {
      if (!hasImage || !productId) {
        setSrc(null);
        return;
      }
      try {
        const token = localStorage.getItem('token');
        const tenant = localStorage.getItem('tenant');
        const res = await fetch(`${apiBase}/products/${productId}/image`, {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
          },
          cache: 'no-store',
        });
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
  }, [productId, hasImage]);

  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img className="tpos-thumb-img" src={src} alt={name} draggable={false} />
    );
  }

  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || '')
    .join('');

  return (
    <div className="tpos-thumb-fallback" aria-hidden>
      <span>{initials || '?'}</span>
    </div>
  );
}

export default function Page() {
  const [q, setQ] = useState('');
  const [rows, setRows] = useState<Product[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [openingCash, setOpeningCash] = useState('100');
  const [actualCash, setActualCash] = useState('');
  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [splitTender, setSplitTender] = useState(false);
  const [cashTender, setCashTender] = useState('');
  const [cardTender, setCardTender] = useState('');
  const [paper, setPaper] = useState('80mm');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [cartDiscount, setCartDiscount] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [lastSale, setLastSale] = useState<{ id: string; reference: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [cashierName, setCashierName] = useState('');
  const [receiptBusy, setReceiptBusy] = useState('');
  const [shiftReport, setShiftReport] = useState<any>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [recentSales, setRecentSales] = useState<RecentSale[]>([]);

  const cartTotals = useMemo(() => {
    let subtotal = 0;
    let tax = 0;
    for (const c of cart) {
      const taxable = Math.max(
        0,
        Math.round((Number(c.selling_price) * c.quantity - (Number(c.discount) || 0)) * 100) / 100
      );
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
    const discount = Math.max(0, Number(cartDiscount) || 0);
    const due = Math.max(0, Math.round((subtotal + tax - discount) * 100) / 100);
    return { subtotal, tax, maxDiscount, due };
  }, [cart, cartDiscount]);
  const cartDiscountAmount = Math.max(0, Number(cartDiscount) || 0);
  const cartTotal = cartTotals.due;
  const cartCount = useMemo(() => cart.reduce((sum, c) => sum + c.quantity, 0), [cart]);

  async function refreshSession() {
    const r = await api('/pos/sessions/current');
    setSession(r.data || null);
  }

  async function loadRecentSales(sessionId?: string | null) {
    const sid = sessionId || session?.session_id;
    if (!sid) {
      setRecentSales([]);
      return;
    }
    try {
      const r = await api(`/pos/sessions/${sid}/report`);
      const sales: RecentSale[] = r.data?.sales || [];
      setRecentSales(sales.slice(0, 12));
    } catch {
      /* keep prior list if report fails mid-shift */
    }
  }

  const browse = useCallback(async (query = '') => {
    const r = await api('/pos/products/search?q=' + encodeURIComponent(query));
    setRows(r.data || []);
    return (r.data || []) as Product[];
  }, []);

  useEffect(() => {
    refreshSession()
      .then(() => browse(''))
      .catch((err) => setError(err.message));
    api('/customers')
      .then((r) => setCustomers(r.data || []))
      .catch(() => setCustomers([]));
    api('/me')
      .then((r) => setCashierName(r.data?.full_name || r.data?.email || ''))
      .catch(() => setCashierName(''));
    api('/pos/stores')
      .then((r) => {
        const list: Store[] = r.data || [];
        setStores(list);
        if (list.length === 1) setStoreId(list[0].id);
      })
      .catch(() => setStores([]));
  }, [browse]);

  useEffect(() => {
    if (session?.session_id) {
      loadRecentSales(session.session_id);
    } else {
      setRecentSales([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.session_id]);

  function selectCustomer(id: string) {
    setCustomerId(id);
    if (!id) return;
    const match = customers.find((c) => c.id === id);
    if (match) setCustomerName(match.name);
  }

  function clearCustomer() {
    setCustomerId('');
    setCustomerName('');
  }

  function setLineDiscount(id: string, discount: number) {
    setCart((prev) =>
      prev.map((p) => {
        if (p.id !== id) return p;
        const maxDisc = Number(p.selling_price) * p.quantity;
        return { ...p, discount: Math.min(Math.max(0, discount), maxDisc) };
      })
    );
  }

  async function openShift() {
    setError('');
    setMessage('');
    if (stores.length > 0 && !storeId) {
      setError('Select a store before opening the shift');
      return;
    }
    try {
      const r = await api('/pos/sessions/open', {
        method: 'POST',
        body: JSON.stringify({
          opening_cash: Number(openingCash) || 0,
          store_id: storeId || null,
        }),
      });
      setSession(r.data);
      setMessage('Shift opened');
      await browse(q);
    } catch (err: any) {
      setError(err.message);
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
        }),
      });
      setSession(null);
      setShiftReport(null);
      setRecentSales([]);
      setMessage(
        `Shift closed. Variance: ${r.data.variance ?? 0} (expected ${r.data.expected_cash})`
      );
      setActualCash('');
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
        const exact = await api(
          '/pos/products/search?barcode=' + encodeURIComponent(query)
        );
        const hits: Product[] = exact.data || [];
        if (hits.length === 1) {
          addToCart(hits[0]);
          setMessage(`Scanned ${hits[0].name} (${hits[0].barcode || hits[0].sku})`);
          setQ('');
          await browse('');
          return;
        }
        if (hits.length === 0) {
          // Fall back to SKU / name search for the same token.
          const soft = await browse(query);
          if (soft.length === 1) {
            addToCart(soft[0]);
            setMessage(`Added ${soft[0].name}`);
            setQ('');
            await browse('');
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
    if (Number(product.stock_qty) <= 0) {
      setError(`${product.name} is out of stock`);
      return;
    }
    const pid = product.product_id || product.id;
    setError('');
    setCart((prev) => {
      const existing = prev.find((p) => p.id === product.id);
      if (existing) {
        if (existing.quantity + 1 > Number(product.stock_qty)) {
          return prev;
        }
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
          discount: 0,
        },
      ];
    });
  }

  function bumpQty(id: string, delta: number) {
    setCart((prev) =>
      prev
        .map((p) => {
          if (p.id !== id) return p;
          const quantity = p.quantity + delta;
          const maxDisc = Number(p.selling_price) * Math.max(quantity, 0);
          return {
            ...p,
            quantity,
            discount: Math.min(p.discount || 0, maxDisc),
          };
        })
        .filter((p) => p.quantity > 0)
    );
  }

  function clearCart() {
    setCart([]);
    setCartDiscount('');
    setCashTender('');
    setCardTender('');
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
    const name = customerName.trim();
    if (!splitTender && paymentMethod === 'credit' && !customerId) {
      setError('Select a customer for credit sales');
      return;
    }
    if (cartDiscountAmount > cartTotals.maxDiscount + 1e-9) {
      setError('Cart discount exceeds sale total');
      return;
    }
    const items = cart.map((c) => ({
      product_id: c.product_id || c.id,
      variant_id: c.variant_id || null,
      quantity: c.quantity,
      discount: Number(c.discount) || 0,
    }));
    const body: Record<string, unknown> = {
      session_id: session.session_id,
      discount_amount: cartDiscountAmount,
      status: 'completed',
      party_id: customerId || null,
      customer_name: name || null,
      items,
    };
    let payments: { payment_method: string; amount: number }[] | null = null;
    if (splitTender) {
      payments = [
        { payment_method: 'cash', amount: Number(cashTender) || 0 },
        { payment_method: 'card', amount: Number(cardTender) || 0 },
      ].filter((p) => p.amount > 0);
      if (payments.length < 2) {
        setError('Split tender needs cash and card amounts');
        return;
      }
      body.payments = payments;
      body.payment_method = 'split';
    } else {
      body.payment_method = paymentMethod;
    }
    setBusy(true);
    try {
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
      setLastSale({ id: r.data.id, reference: r.data.reference });
      await refreshSession();
      await loadRecentSales(session.session_id);
      await browse(q);
      setMessage('Sale successful');
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
      await downloadReceiptPdf(lastSale.id, paper);
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
      await api(`/pos/sales/${lastSale.id}/receipt/send?channel=${channel}`, {
        method: 'POST',
        body: '{}',
      });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setReceiptBusy('');
    }
  }

  return (
    <Shell>
      <div className="tpos">
        <header className="tpos-top">
          <div>
            <h1>Point of Sale</h1>
            <p className="muted">
              {cashierName ? `Cashier: ${cashierName}` : 'Tap tiles or scan a barcode'}
            </p>
          </div>
          <div className="tpos-shift">
            {!session ? (
              <>
                {stores.length > 0 && (
                  <select
                    className="tpos-input"
                    value={storeId}
                    onChange={(e) => setStoreId(e.target.value)}
                    aria-label="Store"
                  >
                    <option value="">Select store</option>
                    {stores.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                        {s.code ? ` (${s.code})` : ''}
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
                <button type="button" className="tpos-btn tpos-btn-primary" onClick={openShift}>
                  Open shift
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
                <input
                  className="tpos-input"
                  value={actualCash}
                  onChange={(e) => setActualCash(e.target.value)}
                  inputMode="decimal"
                  placeholder={`Count ${session.expected_cash}`}
                  aria-label="Counted cash"
                />
                <button type="button" className="tpos-btn" onClick={closeShift}>
                  Close shift
                </button>
                <button
                  type="button"
                  className="tpos-btn"
                  onClick={loadShiftReport}
                  disabled={reportBusy}
                >
                  {reportBusy ? 'Loading…' : shiftReport ? 'Hide report' : 'Shift report'}
                </button>
                <button
                  type="button"
                  className="tpos-btn"
                  onClick={async () => {
                    setError('');
                    try {
                      const r = await api(`/pos/sessions/${session.session_id}/drawer/open`, {
                        method: 'POST',
                        body: JSON.stringify({ reason: 'manual' }),
                      });
                      setMessage(r.data?.message || r.message || 'Drawer opened');
                    } catch (err: any) {
                      setError(err.message);
                    }
                  }}
                >
                  Drawer
                </button>
              </>
            )}
          </div>
        </header>

        {shiftReport && session && (
          <section className="tpos-report" aria-label="Shift report">
            <div className="tpos-report-head">
              <h2>Shift report</h2>
              <button type="button" className="tpos-btn" onClick={() => setShiftReport(null)}>
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
                <span>Expected drawer</span>
                <strong>{money(Number(shiftReport.session?.expected_cash || 0))}</strong>
              </div>
              <div>
                <span>Total sales</span>
                <strong>{money(Number(shiftReport.payment_breakdown?.total || 0))}</strong>
              </div>
            </div>
            <div className="tpos-report-table-wrap">
              <table className="tpos-report-table">
                <thead>
                  <tr>
                    <th>Sale</th>
                    <th>Time</th>
                    <th>Customer</th>
                    <th>Pay</th>
                    <th>Tax</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {(shiftReport.sales || []).length === 0 && (
                    <tr>
                      <td colSpan={6} className="muted">
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
                      </td>
                      <td>{money(Number(sale.tax || 0))}</td>
                      <td>{money(Number(sale.total || 0))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {error && (
          <p className="tpos-banner tpos-banner-err" role="alert">
            {error}
          </p>
        )}
        {message && (
          <div className="tpos-banner tpos-banner-ok tpos-success-bar">
            <span>{message}</span>
            {message === 'Sale successful' && lastSale && (
              <div className="tpos-success-actions">
                <button
                  type="button"
                  className="tpos-btn"
                  onClick={printLastReceipt}
                  disabled={!!receiptBusy}
                >
                  {receiptBusy === 'print' ? 'Printing…' : 'Print'}
                </button>
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
            )}
          </div>
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
              <button type="submit" className="tpos-btn tpos-btn-primary" disabled={!session}>
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
              >
                All
              </button>
            </form>

            {!session && (
              <div className="tpos-empty">
                <p>Open a shift to unlock the product catalog.</p>
              </div>
            )}

            {session && rows.length === 0 && (
              <div className="tpos-empty">
                <p>No products match this search.</p>
              </div>
            )}

            <div className="tpos-grid">
              {rows.map((r) => {
                const out = Number(r.stock_qty) <= 0;
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
                    </div>
                    <div className="tpos-tile-body">
                      <strong>{r.name}</strong>
                      <span className="tpos-sku">
                        {r.sku}
                        {r.kind === 'variant' ? ' · variant' : ''}
                      </span>
                      <div className="tpos-tile-foot">
                        <span className="tpos-price">{money(Number(r.selling_price))}</span>
                        <span className="tpos-stock">{r.stock_qty} in stock</span>
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
              <span>
                {cartCount} item{cartCount === 1 ? '' : 's'}
              </span>
            </div>

            <div className="tpos-cart-list">
              {cart.length === 0 && <p className="muted">Tap a product image to add it.</p>}
              {cart.map((c) => {
                const lineMerch = Number(c.selling_price) * c.quantity;
                const taxable = Math.max(0, Math.round((lineMerch - (Number(c.discount) || 0)) * 100) / 100);
                const lineAmounts = computeLineTaxAmounts(
                  taxable,
                  Number(c.tax_rate_pct) || 0,
                  c.tax_pricing_mode || 'exclusive',
                  Boolean(c.tax_reverse_charge),
                  c.tax_components
                );
                return (
                  <div key={c.id} className="tpos-cart-row">
                    <div className="tpos-cart-mini">
                      <ProductThumb
                        productId={c.product_id || c.id}
                        hasImage={c.has_image}
                        name={c.name}
                      />
                    </div>
                    <div className="tpos-cart-info">
                      <strong>{c.name}</strong>
                      <span>{money(Number(c.selling_price))} each</span>
                      <label className="tpos-line-disc">
                        <span>Disc</span>
                        <input
                          type="number"
                          min={0}
                          max={lineMerch}
                          step="0.01"
                          value={c.discount || 0}
                          onChange={(e) => setLineDiscount(c.id, Number(e.target.value) || 0)}
                          aria-label={`Discount for ${c.name}`}
                        />
                      </label>
                    </div>
                    <div className="tpos-qty">
                      <button type="button" aria-label="Decrease" onClick={() => bumpQty(c.id, -1)}>
                        −
                      </button>
                      <span>{c.quantity}</span>
                      <button type="button" aria-label="Increase" onClick={() => bumpQty(c.id, 1)}>
                        +
                      </button>
                    </div>
                    <div className="tpos-line">{money(lineAmounts.gross)}</div>
                  </div>
                );
              })}
            </div>

            <div className="tpos-cart-foot">
              <label className="tpos-field">
                <span>Cart discount</span>
                <input
                  className="tpos-input"
                  type="number"
                  min={0}
                  step="0.01"
                  value={cartDiscount}
                  onChange={(e) => setCartDiscount(e.target.value)}
                  placeholder="0.00"
                  inputMode="decimal"
                />
              </label>

              <div className="tpos-totals">
                <div className="tpos-total-row">
                  <span>Subtotal</span>
                  <strong>{money(cartTotals.subtotal)}</strong>
                </div>
                <div className="tpos-total-row">
                  <span>Tax</span>
                  <strong>{money(cartTotals.tax)}</strong>
                </div>
                <div className="tpos-total">
                  <span>Amount due</span>
                  <strong>{money(cartTotal)}</strong>
                </div>
              </div>

              <label className="tpos-field">
                <span>Customer {paymentMethod === 'credit' ? '(required)' : '(optional)'}</span>
                <select value={customerId} onChange={(e) => selectCustomer(e.target.value)}>
                  <option value="">Walk-in / none</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="tpos-field">
                <span>Customer name</span>
                <input
                  className="tpos-input"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="Optional name on receipt"
                  maxLength={180}
                  autoComplete="off"
                />
              </label>

              <label className="tpos-split-toggle">
                <input
                  type="checkbox"
                  checked={splitTender}
                  onChange={(e) => enableSplit(e.target.checked)}
                />
                <span>Split tender (cash + card)</span>
              </label>

              {!splitTender ? (
                <label className="tpos-field">
                  <span>Payment</span>
                  <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
                    <option value="cash">Cash</option>
                    <option value="card">Card</option>
                    <option value="wallet">Wallet</option>
                    <option value="credit">Credit</option>
                  </select>
                </label>
              ) : (
                <div className="tpos-split-fields">
                  <label className="tpos-field">
                    <span>Cash</span>
                    <input
                      className="tpos-input"
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
                    />
                  </label>
                  <label className="tpos-field">
                    <span>Card</span>
                    <input
                      className="tpos-input"
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
                    />
                  </label>
                  <p className="tpos-split-hint">
                    Split {money((Number(cashTender) || 0) + (Number(cardTender) || 0))} · due{' '}
                    {money(cartTotal)}
                  </p>
                </div>
              )}

              <label className="tpos-field">
                <span>Receipt</span>
                <select value={paper} onChange={(e) => setPaper(e.target.value)}>
                  <option value="80mm">80mm thermal</option>
                  <option value="58mm">58mm thermal</option>
                </select>
              </label>

              <div className="tpos-cart-actions">
                <button
                  type="button"
                  className="tpos-btn"
                  onClick={clearCart}
                  disabled={!cart.length}
                >
                  Clear
                </button>
                <button
                  type="button"
                  className="tpos-btn tpos-btn-pay"
                  onClick={checkout}
                  disabled={!cart.length || !session || busy}
                >
                  {busy ? 'Processing…' : 'Charge · Complete sale'}
                </button>
              </div>
            </div>
          </aside>
        </div>

        <section className="tpos-recent" aria-label="Recent sales">
          <div className="tpos-recent-head">
            <h2>Recent sales</h2>
            <span>{session ? `${recentSales.length} this shift` : 'Open a shift to see sales'}</span>
          </div>
          {!session ? (
            <p className="muted">Recent POS sales for the open shift will appear here.</p>
          ) : recentSales.length === 0 ? (
            <p className="muted">No sales in this shift yet.</p>
          ) : (
            <div className="tpos-recent-table-wrap">
              <table className="tpos-recent-table">
                <thead>
                  <tr>
                    <th>Reference</th>
                    <th>Time</th>
                    <th>Customer</th>
                    <th>Pay</th>
                    <th>Tax</th>
                    <th>Total</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {recentSales.map((s) => {
                    const pay =
                      Array.isArray(s.payments) && s.payments.length > 1
                        ? s.payments.map((p) => p.payment_method).join('+')
                        : s.payment_method || '—';
                    const when = s.created_at ? String(s.created_at).slice(11, 19) : '—';
                    return (
                      <tr key={s.id}>
                        <td>{s.reference}</td>
                        <td>{when}</td>
                        <td>{s.customer_name || 'Walk-in'}</td>
                        <td>{pay}</td>
                        <td>{money(Number(s.tax || 0))}</td>
                        <td>
                          <strong>{money(Number(s.total || 0))}</strong>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="tpos-btn"
                            onClick={async () => {
                              setError('');
                              try {
                                await downloadReceiptPdf(s.id, paper);
                              } catch (err: any) {
                                setError(err.message);
                              }
                            }}
                          >
                            Print
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

      </div>
    </Shell>
  );
}
