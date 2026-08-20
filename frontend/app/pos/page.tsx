'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { useStoreContext } from '../../lib/storeContext';

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
  status?: string | null;
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
  const [closeNotes, setCloseNotes] = useState('');
  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState('');
  const { storeId: ctxStoreId, setStoreId: setCtxStoreId } = useStoreContext();
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [splitTender, setSplitTender] = useState(false);
  const [cashTender, setCashTender] = useState('');
  const [cardTender, setCardTender] = useState('');
  const [paymentReference, setPaymentReference] = useState('');
  const [paper, setPaper] = useState('80mm');
  const [receiptTo, setReceiptTo] = useState('');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [creditOverrideReason, setCreditOverrideReason] = useState('');
  const [drawerReason, setDrawerReason] = useState('');
  const [cartDiscount, setCartDiscount] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [lastSale, setLastSale] = useState<{ id: string; reference: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [cashierName, setCashierName] = useState('');
  const [receiptBusy, setReceiptBusy] = useState('');
  const [shiftReport, setShiftReport] = useState<any>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [posPrefix, setPosPrefix] = useState('POS');
  const [posNext, setPosNext] = useState('1');
  const [posPreview, setPosPreview] = useState('');
  const [shiftPrefix, setShiftPrefix] = useState('SHIFT');
  const [shiftNext, setShiftNext] = useState('1');
  const [shiftPreview, setShiftPreview] = useState('');
  const [sessions, setSessions] = useState<Session[]>([]);
  const [shiftManageFilter, setShiftManageFilter] = useState<'all' | 'open' | 'closed'>('all');

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
      const taxable = Math.max(
        0,
        Math.round((unit * c.quantity - (Number(c.discount) || 0)) * 100) / 100
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
  }, [cart, cartDiscount, groupDiscountPct]);
  const cartDiscountAmount = Math.max(0, Number(cartDiscount) || 0);
  const cartTotal = cartTotals.due;
  const cartCount = useMemo(() => cart.reduce((sum, c) => sum + c.quantity, 0), [cart]);

  async function refreshSession() {
    const r = await api('/pos/sessions/current');
    setSession(r.data || null);
  }

  async function loadSessions() {
    try {
      const r = await api('/pos/sessions');
      setSessions(r.data || []);
    } catch {
      // Keep prior cache on transient failures (e.g. rate limit) so the
      // Recent shifts filter does not flash empty.
    }
  }

  const managedShifts = sessions.filter((s) => {
    if (shiftManageFilter === 'all') return true;
    return (s.status || '') === shiftManageFilter;
  });


  const browse = useCallback(async (query = '') => {
    const r = await api('/pos/products/search?q=' + encodeURIComponent(query));
    setRows(r.data || []);
    return (r.data || []) as Product[];
  }, []);

  useEffect(() => {
    refreshSession()
      .then(() => browse(''))
      .catch((err) => setError(err.message));
    loadSessions().catch(() => setSessions([]));
    api('/customers')
      .then((r) => setCustomers(r.data || []))
      .catch(() => setCustomers([]));
    api('/me')
      .then((r) => setCashierName(r.data?.full_name || r.data?.email || ''))
      .catch(() => setCashierName(''));
    api('/pos/settings')
      .then((r) => {
        const num = r.data?.pos_sale_numbering;
        if (num) {
          setPosPrefix(num.prefix || 'POS');
          setPosNext(String(num.next_number ?? 1));
          setPosPreview(num.preview || '');
        }
        const shift = r.data?.pos_session_numbering;
        if (shift) {
          setShiftPrefix(shift.prefix || 'SHIFT');
          setShiftNext(String(shift.next_number ?? 1));
          setShiftPreview(shift.preview || '');
        }
      })
      .catch(() => {});
    api('/pos/stores')
      .then((r) => {
        const list: Store[] = r.data || [];
        setStores(list);
        if (ctxStoreId && list.some((s) => s.id === ctxStoreId)) {
          setStoreId(ctxStoreId);
        } else if (list.length === 1) {
          setStoreId(list[0].id);
          setCtxStoreId(list[0].id);
        }
      })
      .catch(() => setStores([]));
    // setCtxStoreId intentionally omitted: stable setter (see storeContext noops);
    // including an unstable fallback previously caused a mount request storm.
  }, [browse, ctxStoreId]);

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
      await loadSessions();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function savePosNumbering() {
    setError('');
    setMessage('');
    try {
      const r = await api('/pos/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          pos_sale_numbering: {
            prefix: posPrefix.trim(),
            next_number: Math.max(1, Number(posNext) || 1),
          },
          pos_session_numbering: {
            prefix: shiftPrefix.trim(),
            next_number: Math.max(1, Number(shiftNext) || 1),
          },
        }),
      });
      const num = r.data?.pos_sale_numbering;
      if (num) {
        setPosPrefix(num.prefix || 'POS');
        setPosNext(String(num.next_number ?? 1));
        setPosPreview(num.preview || '');
      }
      const shift = r.data?.pos_session_numbering;
      if (shift) {
        setShiftPrefix(shift.prefix || 'SHIFT');
        setShiftNext(String(shift.next_number ?? 1));
        setShiftPreview(shift.preview || '');
      }
      setMessage(
        `Numbering saved — Sale ${num?.preview || ''} / Shift ${shift?.preview || ''}`.trim()
      );
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
      await loadSessions();
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
      setLastSale({ id: r.data.id, reference: r.data.reference });
      await refreshSession();
      await browse(q);
      setMessage(
        r.data?.credit_limit_overridden ? 'Sale successful (credit limit overridden)' : 'Sale successful',
      );
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
                    onChange={(e) => {
                      setStoreId(e.target.value);
                      setCtxStoreId(e.target.value);
                    }}
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
                <input
                  className="tpos-input"
                  value={closeNotes}
                  onChange={(e) => setCloseNotes(e.target.value)}
                  placeholder="Close notes (optional)"
                  aria-label="POS shift close notes"
                  title="Optional notes (1–500 chars; letters/digits required)"
                  style={{ minWidth: 180 }}
                />
                <button
                  type="button"
                  className="tpos-btn"
                  onClick={closeShift}
                  aria-label="Close shift"
                >
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
                <input
                  className="tpos-input"
                  value={drawerReason}
                  onChange={(e) => setDrawerReason(e.target.value)}
                  placeholder="Drawer reason (required)"
                  maxLength={200}
                  autoComplete="off"
                  aria-label="Cash drawer open reason"
                  title="Specific drawer reason (3–200 chars; not manual/n/a)"
                  style={{ minWidth: 200 }}
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
                      setError('Enter a specific drawer reason (min 3 characters)');
                      return;
                    }
                    try {
                      const r = await api(`/pos/sessions/${session.session_id}/drawer/open`, {
                        method: 'POST',
                        body: JSON.stringify({ reason: cleaned }),
                      });
                      setDrawerReason('');
                      setMessage(
                        r.data?.message ||
                          r.message ||
                          `Drawer opened (${r.data?.reason || cleaned})`
                      );
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

        <div className="card" style={{ margin: '12px 0', display: 'grid', gap: 8 }}>
          <strong>Document numbering</strong>
          <p className="muted" style={{ margin: 0 }}>
            Sale receipts use POS-YYYY-NNNN; shift sessions use SHIFT-YYYY-NNNN.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <span className="muted">Sale</span>
            <input
              className="tpos-input"
              value={posPrefix}
              onChange={(e) => setPosPrefix(e.target.value.toUpperCase())}
              placeholder="Prefix"
              style={{ width: 100 }}
            />
            <input
              className="tpos-input"
              value={posNext}
              onChange={(e) => setPosNext(e.target.value)}
              placeholder="Next #"
              style={{ width: 90 }}
            />
            <span className="muted">{posPreview || '—'}</span>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <span className="muted">Shift</span>
            <input
              className="tpos-input"
              value={shiftPrefix}
              onChange={(e) => setShiftPrefix(e.target.value.toUpperCase())}
              placeholder="Prefix"
              style={{ width: 100 }}
            />
            <input
              className="tpos-input"
              value={shiftNext}
              onChange={(e) => setShiftNext(e.target.value)}
              placeholder="Next #"
              style={{ width: 90 }}
            />
            <span className="muted">{shiftPreview || '—'}</span>
            <button type="button" className="tpos-btn" onClick={savePosNumbering}>
              Save numbering
            </button>
          </div>
        </div>

        <div className="card" style={{ margin: '12px 0' }}>
          <strong>Recent shifts</strong>
          <p className="muted" style={{ marginTop: 4 }}>
            Open vs closed POS sessions for this tenant (BR-8.2). Filter is client-side over the
            full list cache; API also accepts `?status=open|closed`.
          </p>
          <select
            className="tpos-input"
            value={shiftManageFilter}
            onChange={(e) =>
              setShiftManageFilter(e.target.value as 'all' | 'open' | 'closed')
            }
            title="Filter POS shifts by status"
            aria-label="POS shift status filter"
            style={{ marginBottom: 12 }}
          >
            <option value="all">All statuses</option>
            <option value="open">Open only</option>
            <option value="closed">Closed only</option>
          </select>
          <table className="table">
            <thead>
              <tr>
                <th>Shift</th>
                <th>Store</th>
                <th>Status</th>
                <th>Sales</th>
                <th>Variance</th>
              </tr>
            </thead>
            <tbody>
              {managedShifts.length === 0 ? (
                <tr>
                  <td colSpan={5} className="muted">
                    No shifts for this filter
                  </td>
                </tr>
              ) : (
                managedShifts.map((s) => (
                  <tr key={s.session_id}>
                    <td>{s.session_number}</td>
                    <td>{s.store_name || '—'}</td>
                    <td>{s.status}</td>
                    <td>
                      {s.sale_count} · {money(Number(s.total_sales || 0))}
                    </td>
                    <td>{s.variance == null ? '—' : s.variance}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

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
                <span>Discounts</span>
                <strong>{money(Number(shiftReport.summary?.discounts || 0))}</strong>
              </div>
              <div>
                <span>Returns</span>
                <strong>{money(Number(shiftReport.summary?.return_total || 0))}</strong>
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
              {shiftReport.summary?.sale_count ?? 0} sales · tax{' '}
              {money(Number(shiftReport.summary?.tax || 0))} · net after returns{' '}
              {money(Number(shiftReport.summary?.net_after_returns ?? 0))}
            </p>
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
                  aria-label="Print last receipt"
                >
                  {receiptBusy === 'print' ? 'Printing…' : 'Print'}
                </button>
                <input
                  type="text"
                  value={receiptTo}
                  onChange={(e) => setReceiptTo(e.target.value)}
                  placeholder="Optional to= (email or E.164)"
                  aria-label="POS receipt override to"
                  style={{ minWidth: 180 }}
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
                const unit = groupUnitPrice(Number(c.selling_price));
                const lineMerch = unit * c.quantity;
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
                      <span>
                        {money(unit)} each
                        {groupDiscountPct > 0 ? ` (−${groupDiscountPct}% group)` : ''}
                      </span>
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

              <label className="tpos-field">
                <span>Customer name</span>
                <input
                  className="tpos-input"
                  aria-label="POS customer name"
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
                    <option value="wallet">Digital wallet</option>
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

              <label className="tpos-field">
                <span>Credit override reason</span>
                <input
                  className="tpos-input"
                  value={creditOverrideReason}
                  onChange={(e) => setCreditOverrideReason(e.target.value)}
                  placeholder="Required if credit sale exceeds limit"
                  maxLength={500}
                  autoComplete="off"
                />
              </label>
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
                  aria-label="Charge complete sale"
                >
                  {busy ? 'Processing…' : 'Charge · Complete sale'}
                </button>
              </div>
            </div>
          </aside>
        </div>


      </div>
    </Shell>
  );
}
