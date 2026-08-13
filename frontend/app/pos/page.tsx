'use client';

import { useEffect, useState } from 'react';
import BarcodeCameraScanner from '../../components/BarcodeCameraScanner';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import {
  getOfflineCatalogMeta,
  refreshOfflineCatalog,
  searchOfflineCatalog,
} from '../../lib/offlineCatalog';
import {
  enqueueOfflineOp,
  flushOfflineQueue,
  getBoundOfflineDeviceId,
  listPendingOfflineOps,
  newClientOpId,
} from '../../lib/offlineQueue';

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
};

type CartItem = Product & { quantity: number; discount: number };

type Customer = {
  id: string;
  name: string;
  code?: string | null;
  credit_limit?: number;
  balance?: number;
  group_discount_percent?: number;
  customer_group_name?: string | null;
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

export default function Page() {
  const [q, setQ] = useState('');
  const [rows, setRows] = useState<Product[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [openingCash, setOpeningCash] = useState('100');
  const [actualCash, setActualCash] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [splitTender, setSplitTender] = useState(false);
  const [tenders, setTenders] = useState<{ payment_method: string; amount: string }[]>([
    { payment_method: 'cash', amount: '' },
    { payment_method: 'card', amount: '' },
  ]);
  const [paper, setPaper] = useState('80mm');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [cartDiscount, setCartDiscount] = useState('0');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState<any>(null);
  const [scannerOpen, setScannerOpen] = useState(false);
  const [sessionHistory, setSessionHistory] = useState<any[]>([]);
  const [shiftReport, setShiftReport] = useState<any | null>(null);
  // Stage 130 P1 — pos_session_status → GET /pos/sessions?status=
  const [posSessionStatusFilter, setPosSessionStatusFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('pos_session_status') || '')
      .trim()
      .toLowerCase();
    return v === 'open' || v === 'closed' ? v : '';
  });
  // Stage 165 H1 / K1 / Stage 166 C1+S1 — holds, offline queue, catalog cache
  const [heldCarts, setHeldCarts] = useState<any[]>([]);
  const [holdLabel, setHoldLabel] = useState('');
  const [pendingOffline, setPendingOffline] = useState(0);
  const [online, setOnline] = useState(true);
  const [catalogAsOf, setCatalogAsOf] = useState<string | null>(null);
  const [catalogStaleNote, setCatalogStaleNote] = useState('');

  async function refreshSession() {
    const r = await api('/pos/sessions/current');
    setSession(r.data || null);
  }

  async function refreshHolds() {
    try {
      const r = await api('/pos/holds?status=held');
      setHeldCarts(r.data || []);
    } catch {
      setHeldCarts([]);
    }
  }

  async function refreshOfflinePending() {
    try {
      const rows = await listPendingOfflineOps();
      setPendingOffline(rows.length);
    } catch {
      setPendingOffline(0);
    }
  }

  async function refreshCatalogMeta() {
    try {
      const meta = await getOfflineCatalogMeta();
      setCatalogAsOf(meta?.as_of || null);
    } catch {
      setCatalogAsOf(null);
    }
  }

  async function pullCatalogCache() {
    setError('');
    try {
      const meta = await refreshOfflineCatalog(api);
      setCatalogAsOf(meta?.as_of || null);
      setMessage(
        meta
          ? `Offline catalog cached (${meta.count} products, stock non-authoritative)`
          : 'No catalog op returned from pull',
      );
    } catch (err: any) {
      setError(err.message || 'Catalog refresh failed');
    }
  }

  async function loadSessionHistory(opts?: { status?: string }) {
    const st = opts?.status !== undefined ? opts.status : posSessionStatusFilter;
    const qs = st === 'open' || st === 'closed' ? `?status=${st}` : '';
    const r = await api(`/pos/sessions${qs}`);
    setSessionHistory(r.data || []);
  }

  async function viewShiftReport(sessionId: string) {
    setError('');
    try {
      const r = await api(`/pos/sessions/${sessionId}/report`);
      setShiftReport(r.data || null);
      setMessage(`Shift report loaded for ${r.data?.session?.session_number || sessionId.slice(0, 8)}`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function downloadPosCsv(path: string, filename: string) {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}${path}`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || `${filename} export failed`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(`${filename} exported`);
    } catch (err: any) {
      setError(err.message || 'Export failed');
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ps = (params.get('pos_session_status') || '').trim().toLowerCase();
    const initial = ps === 'open' || ps === 'closed' ? ps : posSessionStatusFilter;
    if (initial) setPosSessionStatusFilter(initial);
    refreshSession().catch((err) => setError(err.message));
    loadSessionHistory({ status: initial }).catch((err) => setError(err.message));
    refreshHolds().catch(() => undefined);
    refreshOfflinePending().catch(() => undefined);
    refreshCatalogMeta().catch(() => undefined);
    api('/customers?active_only=true')
      .then((r) => setCustomers(r.data || []))
      .catch(() => setCustomers([]));
    api('/tenants/me')
      .then((r) => {
        const tpl = r.data?.receipt_print_template;
        if (tpl === 'thermal_58') setPaper('58mm');
        else if (tpl === 'thermal_80') setPaper('80mm');
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const sync = () => setOnline(navigator.onLine);
    sync();
    window.addEventListener('online', sync);
    window.addEventListener('offline', sync);
    return () => {
      window.removeEventListener('online', sync);
      window.removeEventListener('offline', sync);
    };
  }, []);

  // Stage 101 P1 / Stage 107 P1 / Stage 165 H1 — honor Shell /pos#sessions / #shift / #cart / #receipt / #holds
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hash = (window.location.hash || '').replace(/^#/, '');
    if (!['sessions', 'shift', 'cart', 'receipt', 'holds'].includes(hash)) return;
    const t = window.setTimeout(() => {
      const el = document.getElementById(hash);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(t);
  }, [sessionHistory, receipt, heldCarts]);

  async function openShift() {
    setError('');
    setMessage('');
    try {
      const r = await api('/pos/sessions/open', {
        method: 'POST',
        body: JSON.stringify({ opening_cash: Number(openingCash) || 0 }),
      });
      setSession(r.data);
      setMessage(`Shift opened: ${r.data.session_number}`);
      await loadSessionHistory().catch(() => undefined);
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
      setMessage(
        `Shift closed. Variance: ${r.data.variance ?? 0} (expected ${r.data.expected_cash})`,
      );
      setActualCash('');
      await loadSessionHistory().catch(() => undefined);
    } catch (err: any) {
      setError(err.message);
    }
  }

  function pickExactMatch(list: Product[], code: string): Product | null {
    const exact = list.filter((p) => p.sku === code || p.barcode === code);
    if (exact.length === 1) return exact[0];
    if (exact.length === 0 && list.length === 1) return list[0];
    return null;
  }

  async function searchProducts(query: string, { autoAdd = false }: { autoAdd?: boolean } = {}) {
    setError('');
    setCatalogStaleNote('');
    try {
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        const cached = await searchOfflineCatalog(query);
        const list: Product[] = cached.map((p) => ({
          id: p.id,
          product_id: p.id,
          name: p.name,
          sku: p.sku,
          barcode: p.barcode,
          selling_price: p.selling_price,
          stock_qty: p.stock_qty,
        }));
        setRows(list);
        setCatalogStaleNote(
          'Offline catalog — stock figures are stale / non-authoritative (Stage 166 C1). Checkout uses online integrity or sync push.',
        );
        if (autoAdd) {
          const match = pickExactMatch(list, query.trim());
          if (match) {
            addToCart(match);
            setMessage(`Scanned (offline cache): ${match.name}`);
            setQ('');
          } else if (!list.length) {
            setError(`No cached product for barcode ${query}`);
          }
        }
        return;
      }
      const params = new URLSearchParams();
      params.set('q', query);
      params.set('barcode', query);
      const r = await api('/pos/products/search?' + params.toString());
      const list: Product[] = r.data || [];
      setRows(list);
      if (autoAdd) {
        const match = pickExactMatch(list, query.trim());
        if (match) {
          addToCart(match);
          setMessage(`Scanned: ${match.name}`);
          setQ('');
        } else if (!list.length) {
          setError(`No product for barcode ${query}`);
        }
      }
    } catch (err: any) {
      // Online path failed — fall back to cached catalog if present.
      try {
        const cached = await searchOfflineCatalog(query);
        if (cached.length) {
          const list: Product[] = cached.map((p) => ({
            id: p.id,
            product_id: p.id,
            name: p.name,
            sku: p.sku,
            barcode: p.barcode,
            selling_price: p.selling_price,
            stock_qty: p.stock_qty,
          }));
          setRows(list);
          setCatalogStaleNote(
            'Search fell back to offline catalog — stock is non-authoritative (Stage 166 C1).',
          );
          return;
        }
      } catch {
        /* ignore cache miss */
      }
      setError(err.message);
    }
  }

  async function search() {
    await searchProducts(q, { autoAdd: false });
  }

  async function applyScan(code: string) {
    const value = code.trim();
    if (!value) return;
    setQ(value);
    setScannerOpen(false);
    await searchProducts(value, { autoAdd: true });
  }

  function addToCart(product: Product) {
    const pid = product.product_id || product.id;
    setCart((prev) => {
      const existing = prev.find((p) => p.id === product.id);
      if (existing) {
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

  function setCartQty(id: string, quantity: number) {
    setCart((prev) => {
      if (quantity <= 0) return prev.filter((p) => p.id !== id);
      return prev.map((p) => (p.id === id ? { ...p, quantity } : p));
    });
  }

  function setLineDiscount(id: string, discount: number) {
    setCart((prev) =>
      prev.map((p) => (p.id === id ? { ...p, discount: Math.max(0, discount) } : p)),
    );
  }

  const selectedCustomer = customers.find((c) => c.id === customerId);
  const groupDiscountPct = Number(selectedCustomer?.group_discount_percent || 0);
  function effectiveUnitPrice(base: number) {
    if (!groupDiscountPct) return Number(base || 0);
    return Math.round(Number(base || 0) * (1 - groupDiscountPct / 100) * 10000) / 10000;
  }

  const cartSubtotal = cart.reduce(
    (sum, c) =>
      sum + Math.max(0, effectiveUnitPrice(c.selling_price) * c.quantity - (c.discount || 0)),
    0,
  );

  async function checkout() {
    setError('');
    setMessage('');
    setReceipt(null);
    if (!session) {
      setError('Open a POS shift before selling');
      return;
    }
    if (!cart.length) {
      setError('Cart is empty');
      return;
    }
    const items = cart.map((c) => ({
      product_id: c.product_id || c.id,
      variant_id: c.variant_id || null,
      quantity: c.quantity,
      discount: c.discount || 0,
    }));
    const discountAmount = Number(cartDiscount) || 0;
    const clientRequestId = newClientOpId('pos');
    const body: Record<string, unknown> = {
      session_id: session.session_id,
      party_id: customerId || null,
      discount_amount: discountAmount,
      status: 'completed',
      client_request_id: clientRequestId,
      items,
    };
    if (splitTender) {
      const payments = tenders
        .map((t) => ({
          payment_method: t.payment_method,
          amount: Number(t.amount) || 0,
        }))
        .filter((t) => t.amount > 0);
      if (payments.length < 2) {
        setError('Split tender needs at least two payment amounts');
        return;
      }
      if (payments.some((p) => p.payment_method === 'credit') && !customerId) {
        setError('Select a customer for credit tenders');
        return;
      }
      body.payments = payments;
      body.payment_method = 'split';
    } else {
      if (paymentMethod === 'credit' && !customerId) {
        setError('Select a customer for credit sales');
        return;
      }
      body.payment_method = paymentMethod;
    }
    async function submitSale(payload: Record<string, unknown>) {
      const r = await api('/pos/sales', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      const receiptRes = await api(`/pos/sales/${r.data.id}/receipt?paper=${paper}`);
      setReceipt(receiptRes.data);
      const drawerNote =
        r.data?.drawer?.ok === true
          ? ` · drawer ${r.data.drawer.mode}`
          : r.data?.drawer?.skipped
            ? ''
            : r.data?.drawer?.error
              ? ` · drawer warn: ${r.data.drawer.error}`
              : '';
      const tenderNote =
        r.data?.payments?.length > 1
          ? ` · split ${r.data.payments.map((p: any) => `${p.payment_method} ${p.amount}`).join(' + ')}`
          : '';
      setMessage(
        `Sale recorded: ${r.data.reference} (tax ${r.data.tax ?? 0}` +
          (r.data.discount_amount ? `, discount ${r.data.discount_amount}` : '') +
          `)${tenderNote}${drawerNote}` +
          (r.data?.credit_limit_overridden ? ' · credit limit overridden' : ''),
      );
      setCart([]);
      setCartDiscount('0');
      setSplitTender(false);
      await refreshSession();
    }

    // Stage 165 K1 — when offline, enqueue for /sync/push flush (requires bound device).
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      const deviceId = getBoundOfflineDeviceId();
      if (!deviceId) {
        setError('Offline: bind a device in Settings → Offline sync before queuing sales');
        return;
      }
      try {
        await enqueueOfflineOp({
          client_op_id: clientRequestId,
          op_type: 'pos_sale',
          device_id: deviceId,
          payload: body,
        });
        setCart([]);
        setCartDiscount('0');
        setSplitTender(false);
        await refreshOfflinePending();
        setMessage(`Sale queued offline (${clientRequestId}). Flush when online.`);
      } catch (err: any) {
        setError(err.message || 'Failed to queue offline sale');
      }
      return;
    }

    try {
      await submitSale(body);
    } catch (err: any) {
      if (err?.code === 'CREDIT_LIMIT_EXCEEDED') {
        const reason = window.prompt(
          `${err.message}\n\nEnter override reason (requires credit:approve):`,
        );
        if (reason && reason.trim().length >= 3) {
          try {
            await submitSale({
              ...body,
              credit_limit_override: true,
              credit_override_reason: reason.trim(),
            });
            return;
          } catch (err2: any) {
            setError(err2.message);
            return;
          }
        }
      }
      setError(err.message);
    }
  }

  async function holdCart() {
    setError('');
    setMessage('');
    if (!cart.length) {
      setError('Cart is empty');
      return;
    }
    try {
      const r = await api('/pos/holds', {
        method: 'POST',
        body: JSON.stringify({
          session_id: session?.session_id || null,
          label: holdLabel || `Hold ${new Date().toLocaleTimeString()}`,
          reserve_stock: true,
          cart_payload: {
            items: cart.map((c) => ({
              product_id: c.product_id || c.id,
              variant_id: c.variant_id || null,
              quantity: c.quantity,
              discount: c.discount || 0,
              name: c.name,
              sku: c.sku,
              selling_price: c.selling_price,
            })),
            party_id: customerId || null,
            discount_amount: Number(cartDiscount) || 0,
            payment_method: paymentMethod,
          },
        }),
      });
      setCart([]);
      setCartDiscount('0');
      setHoldLabel('');
      await refreshHolds();
      const reserved = Boolean(r.data?.stock_reserved);
      setMessage(
        reserved
          ? 'Cart held with soft stock reservation (product.reserved_qty — Stage 166 S1; not a sale)'
          : 'Cart held (stock not reserved — Stage 165 H1 Partial)',
      );
    } catch (err: any) {
      setError(err.message || 'Hold failed');
    }
  }

  async function resumeHold(holdId: string) {
    setError('');
    setMessage('');
    try {
      const r = await api(`/pos/holds/${holdId}/resume`, { method: 'POST', body: '{}' });
      const payload = r.data?.cart_payload || {};
      const items = (payload.items || []).map((it: any) => ({
        id: it.variant_id || it.product_id,
        product_id: it.product_id,
        variant_id: it.variant_id || null,
        name: it.name || it.sku || 'Item',
        sku: it.sku || '',
        selling_price: Number(it.selling_price || 0),
        stock_qty: 0,
        quantity: Number(it.quantity || 1),
        discount: Number(it.discount || 0),
      }));
      setCart(items);
      setCustomerId(payload.party_id || '');
      setCartDiscount(String(payload.discount_amount || 0));
      if (payload.payment_method) setPaymentMethod(payload.payment_method);
      await refreshHolds();
      setMessage('Held cart resumed into cart (complete checkout to sell)');
    } catch (err: any) {
      setError(err.message || 'Resume failed');
    }
  }

  async function discardHold(holdId: string) {
    setError('');
    try {
      await api(`/pos/holds/${holdId}`, { method: 'DELETE' });
      await refreshHolds();
      setMessage('Held cart discarded');
    } catch (err: any) {
      setError(err.message || 'Discard failed');
    }
  }

  async function flushOfflineSales() {
    setError('');
    setMessage('');
    try {
      const out = await flushOfflineQueue(api);
      await refreshOfflinePending();
      if (online && getBoundOfflineDeviceId()) {
        try {
          const meta = await refreshOfflineCatalog(api);
          setCatalogAsOf(meta?.as_of || null);
        } catch {
          /* catalog refresh is best-effort after flush */
        }
      }
      setMessage(
        `Offline queue flush: ${out.flushed} applied/replayed, ${out.failed} failed/conflict`,
      );
    } catch (err: any) {
      setError(err.message || 'Flush failed');
    }
  }

  return (
    <Shell>
      <h1>Point of Sale</h1>
      <p className="muted">
        Open a shift, sell from cart, print thermal receipt. Stage 166: soft Hold reserve · offline
        catalog cache (stale stock) · IndexedDB queue when OFFLINE. Offline Complete remains deferred.
      </p>
      <p className="muted">
        Network: {online ? 'ONLINE' : 'OFFLINE'}
        {pendingOffline > 0 ? ` · Pending offline ops: ${pendingOffline}` : ''}
        {getBoundOfflineDeviceId()
          ? ` · Device ${getBoundOfflineDeviceId().slice(0, 8)}…`
          : ' · No offline device bound (Settings → Offline sync)'}
        {catalogAsOf ? ` · Catalog as of ${catalogAsOf}` : ' · No offline catalog cached'}
        {online && getBoundOfflineDeviceId() ? (
          <>
            {' '}
            <button type="button" onClick={() => pullCatalogCache()}>
              Refresh offline catalog
            </button>
          </>
        ) : null}
        {pendingOffline > 0 && online ? (
          <>
            {' '}
            <button type="button" onClick={() => flushOfflineSales()}>
              Flush offline queue
            </button>
          </>
        ) : null}
      </p>
      {catalogStaleNote ? <p className="muted">{catalogStaleNote}</p> : null}
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }} id="shift">
        <h3>Shift</h3>
        {!session ? (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              value={openingCash}
              onChange={(e) => setOpeningCash(e.target.value)}
              placeholder="Opening cash"
              style={{ padding: 10, width: 140 }}
            />
            <button onClick={openShift}>Open shift</button>
          </div>
        ) : (
          <div>
            <p>
              <b>{session.session_number}</b> · sales {session.sale_count} · total {session.total_sales}
            </p>
            <p className="muted">
              Opening {session.opening_cash} · cash sales {session.cash_sales} · expected drawer{' '}
              {session.expected_cash}
            </p>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                value={actualCash}
                onChange={(e) => setActualCash(e.target.value)}
                placeholder={`Counted cash (expected ${session.expected_cash})`}
                style={{ padding: 10, width: 220 }}
              />
              <button onClick={closeShift}>Close shift</button>
              <button
                type="button"
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
                Open cash drawer
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="sessions">
        <h3>POS session history</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Recent shifts (tenant-scoped). Filter via <code>pos_session_status</code> →{' '}
          <code>GET /pos/sessions?status=</code>; export via <code>/pos/sessions/export</code> (Stage
          130 P1). Sales register CSV via <code>GET /pos/sales/export</code> (Stage 142 S1); Z-report
          CSV via <code>GET /pos/sessions/&#123;id&#125;/report/export</code> (Stage 142 Z1).
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
          <select
            value={posSessionStatusFilter || 'default'}
            onChange={(e) => {
              const v = e.target.value === 'default' ? '' : e.target.value;
              setPosSessionStatusFilter(v);
              const url = new URL(window.location.href);
              if (v === 'open' || v === 'closed') url.searchParams.set('pos_session_status', v);
              else url.searchParams.delete('pos_session_status');
              window.history.replaceState({}, '', url.toString());
              loadSessionHistory({ status: v }).catch((err) => setError(err.message));
            }}
          >
            <option value="default">Status filter (all)</option>
            <option value="open">Open only</option>
            <option value="closed">Closed only</option>
          </select>
          <button
            type="button"
            onClick={async () => {
              const token = localStorage.getItem('token') || '';
              const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
              const qs =
                posSessionStatusFilter === 'open' || posSessionStatusFilter === 'closed'
                  ? `?status=${posSessionStatusFilter}`
                  : '';
              const res = await fetch(`${apiBase}/pos/sessions/export${qs}`, {
                headers: { Authorization: `Bearer ${token}` },
              });
              if (!res.ok) {
                setError(await res.text());
                return;
              }
              const blob = await res.blob();
              const a = document.createElement('a');
              a.href = URL.createObjectURL(blob);
              a.download = 'pos_sessions_export.csv';
              a.click();
              URL.revokeObjectURL(a.href);
              setMessage('POS sessions CSV downloaded');
            }}
          >
            Export sessions CSV
          </button>
          <button
            type="button"
            onClick={() => downloadPosCsv('/pos/sales/export', 'pos_sales_export.csv')}
          >
            Export sales CSV
          </button>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Session</th>
              <th>Status</th>
              <th>Opened</th>
              <th>Closed</th>
              <th>Sales</th>
              <th>Total</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sessionHistory.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  No POS sessions yet
                </td>
              </tr>
            )}
            {sessionHistory.map((s) => (
              <tr key={s.session_id || s.id}>
                <td>{s.session_number}</td>
                <td>{s.status}</td>
                <td>{s.opened_at ? String(s.opened_at).slice(0, 19) : '—'}</td>
                <td>{s.closed_at ? String(s.closed_at).slice(0, 19) : '—'}</td>
                <td>{s.sale_count ?? 0}</td>
                <td>{s.total_sales ?? 0}</td>
                <td>
                  <button type="button" onClick={() => viewShiftReport(s.session_id || s.id)}>
                    Report
                  </button>{' '}
                  <button
                    type="button"
                    onClick={() =>
                      downloadPosCsv(
                        `/pos/sessions/${s.session_id || s.id}/report/export`,
                        'pos_session_z_report_export.csv'
                      )
                    }
                  >
                    Export Z-report CSV
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {shiftReport && (
          <div style={{ marginTop: 12 }}>
            <h4 style={{ margin: '0 0 8px' }}>
              Shift report — {shiftReport.session?.session_number || '—'}
            </h4>
            <p className="muted">
              Cash {shiftReport.payment_breakdown?.cash ?? 0} · Card{' '}
              {shiftReport.payment_breakdown?.card ?? 0} · Other{' '}
              {shiftReport.payment_breakdown?.other ?? 0} · Lines{' '}
              {(shiftReport.sales || []).length}
            </p>
            <button
              type="button"
              style={{ marginTop: 8 }}
              onClick={() =>
                downloadPosCsv(
                  `/pos/sessions/${shiftReport.session?.session_id || ''}/report/export`,
                  'pos_session_z_report_export.csv'
                )
              }
              disabled={!shiftReport.session?.session_id}
            >
              Export Z-report CSV
            </button>
          </div>
        )}
      </div>

      <div className="card" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              applyScan(q);
            }
          }}
          placeholder="Search product or scan barcode (USB/Bluetooth or camera)"
          style={{ padding: 12, flex: '1 1 220px' }}
          disabled={!session}
          autoFocus
        />
        <button onClick={search} style={{ padding: 12 }} disabled={!session}>
          Search
        </button>
        <button type="button" onClick={() => setScannerOpen(true)} style={{ padding: 12 }} disabled={!session}>
          Camera scan
        </button>
      </div>

      <BarcodeCameraScanner
        open={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onScan={applyScan}
        title="POS barcode scan"
      />

      <div className="grid" style={{ marginTop: 16 }}>
        {rows.map((r) => (
          <div className="card" key={r.id}>
            <b>{r.name}</b>
            <p>
              {r.sku}
              {r.kind === 'variant' ? ' · variant' : ''}
            </p>
            <div className="kpi">{effectiveUnitPrice(r.selling_price)}</div>
            <p className="muted">Stock: {r.stock_qty}</p>
            <button onClick={() => addToCart(r)} disabled={!session}>
              Add
            </button>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 16 }} id="cart">
        <h3>Cart</h3>
        <label style={{ display: 'block', marginBottom: 12 }}>
          Customer{' '}
          <select
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            disabled={!session}
            style={{ minWidth: 220 }}
          >
            <option value="">Walk-in</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.code ? ` (${c.code})` : ''}
                {c.customer_group_name ? ` · ${c.customer_group_name}` : ''}
              </option>
            ))}
          </select>
        </label>
        {groupDiscountPct > 0 && (
          <p className="muted">
            {selectedCustomer?.customer_group_name || 'Group'} pricing: {groupDiscountPct}% off catalog
          </p>
        )}
        {cart.length === 0 && <p className="muted">No items</p>}
        {cart.map((c) => {
          const unit = effectiveUnitPrice(c.selling_price);
          const lineGross = unit * c.quantity;
          const lineNet = Math.max(0, lineGross - (c.discount || 0));
          return (
            <div
              key={c.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr auto',
                gap: 8,
                marginBottom: 12,
                alignItems: 'center',
              }}
            >
              <div>
                <div>{c.name}</div>
                <div className="muted" style={{ fontSize: 13 }}>
                  {c.sku} · {unit.toFixed(2)} each
                  {groupDiscountPct > 0 ? ` (${groupDiscountPct}% group)` : ''}
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  <button type="button" onClick={() => setCartQty(c.id, c.quantity - 1)} disabled={!session}>
                    −
                  </button>
                  <input
                    value={c.quantity}
                    onChange={(e) => setCartQty(c.id, Number(e.target.value) || 0)}
                    style={{ width: 56, padding: 6 }}
                    disabled={!session}
                  />
                  <button type="button" onClick={() => setCartQty(c.id, c.quantity + 1)} disabled={!session}>
                    +
                  </button>
                  <label style={{ fontSize: 13 }}>
                    Line disc{' '}
                    <input
                      value={c.discount || 0}
                      onChange={(e) => setLineDiscount(c.id, Number(e.target.value) || 0)}
                      style={{ width: 72, padding: 6 }}
                      disabled={!session}
                    />
                  </label>
                  <button type="button" onClick={() => setCartQty(c.id, 0)} disabled={!session}>
                    Remove
                  </button>
                </div>
              </div>
              <strong>{lineNet.toFixed(2)}</strong>
            </div>
          );
        })}
        <p>
          Cart lines: <b>{cartSubtotal.toFixed(2)}</b>
        </p>
        <label style={{ display: 'block', marginBottom: 8 }}>
          Cart discount{' '}
          <input
            value={cartDiscount}
            onChange={(e) => setCartDiscount(e.target.value)}
            style={{ width: 100, padding: 8 }}
            disabled={!session}
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <input
            type="checkbox"
            checked={splitTender}
            onChange={(e) => setSplitTender(e.target.checked)}
            disabled={!session}
          />
          Split tender
        </label>
        {!splitTender ? (
          <label style={{ display: 'block', marginBottom: 8 }}>
            Payment{' '}
            <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
              <option value="cash">Cash</option>
              <option value="card">Card</option>
              <option value="wallet">Digital wallet</option>
              <option value="credit">Credit (registered customer)</option>
            </select>
          </label>
        ) : (
          <div style={{ display: 'grid', gap: 8, marginBottom: 8, maxWidth: 420 }}>
            <p className="muted" style={{ margin: 0 }}>
              Enter amounts that sum to the sale total (after tax/discount).
            </p>
            {tenders.map((t, idx) => (
              <div key={idx} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <select
                  value={t.payment_method}
                  onChange={(e) => {
                    const next = [...tenders];
                    next[idx] = { ...next[idx], payment_method: e.target.value };
                    setTenders(next);
                  }}
                >
                  <option value="cash">Cash</option>
                  <option value="card">Card</option>
                  <option value="wallet">Wallet</option>
                  <option value="credit">Credit</option>
                </select>
                <input
                  value={t.amount}
                  onChange={(e) => {
                    const next = [...tenders];
                    next[idx] = { ...next[idx], amount: e.target.value };
                    setTenders(next);
                  }}
                  placeholder="Amount"
                  style={{ width: 120, padding: 8 }}
                />
              </div>
            ))}
            <button
              type="button"
              onClick={() =>
                setTenders([...tenders, { payment_method: 'cash', amount: '' }])
              }
            >
              Add tender line
            </button>
          </div>
        )}
        <label style={{ display: 'block', marginBottom: 8 }}>
          Receipt paper{' '}
          <select value={paper} onChange={(e) => setPaper(e.target.value)}>
            <option value="80mm">80mm thermal</option>
            <option value="58mm">58mm thermal</option>
          </select>
        </label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <button onClick={checkout} disabled={!cart.length || !session}>
            Complete sale
          </button>
          <input
            placeholder="Hold label"
            value={holdLabel}
            onChange={(e) => setHoldLabel(e.target.value)}
            style={{ padding: 8, minWidth: 140 }}
            disabled={!session}
          />
          <button type="button" onClick={holdCart} disabled={!cart.length || !session}>
            Hold cart
          </button>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          Hold soft-reserves via product.reserved_qty when online (Stage 166 S1). Not a sale; Offline
          Complete remains deferred. Default without reserve_stock remains Stage 165 park-only.
        </p>
      </div>

      <div className="card" style={{ marginTop: 16 }} id="holds">
        <h3>Held carts</h3>
        {heldCarts.length === 0 ? (
          <p className="muted">No held carts for this cashier.</p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {heldCarts.map((h) => (
              <li key={h.id} style={{ marginBottom: 8 }}>
                <strong>{h.label}</strong>{' '}
                <span className="muted">
                  · {(h.cart_payload?.items || []).length} lines · stock_reserved=
                  {String(h.stock_reserved)}
                </span>{' '}
                <button type="button" onClick={() => resumeHold(h.id)}>
                  Resume
                </button>{' '}
                <button type="button" onClick={() => discardHold(h.id)}>
                  Discard
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card" style={{ marginTop: 16 }} id="receipt">
        <h3>Receipt</h3>
        {receipt ? (
          <>
          <p>
            {receipt.reference} · Total {receipt.total} · {receipt.payment_method}
            {receipt.payments?.length > 1
              ? ` (${receipt.payments
                  .map((p: any) => `${p.payment_method} ${p.amount}`)
                  .join(' + ')})`
              : ''}
          </p>
          <pre
            style={{
              background: '#111',
              color: '#eee',
              padding: 12,
              overflow: 'auto',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
              fontSize: 12,
              lineHeight: 1.35,
              maxWidth: 360,
            }}
          >
            {receipt.text}
          </pre>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
            <button
              onClick={async () => {
                try {
                  await downloadReceiptPdf(receipt.sale_id, paper);
                  setMessage('Thermal PDF downloaded');
                } catch (err: any) {
                  setError(err.message);
                }
              }}
            >
              Download thermal PDF
            </button>
            <button
              onClick={async () => {
                try {
                  const r = await api(`/pos/sales/${receipt.sale_id}/receipt/send?channel=email`, {
                    method: 'POST',
                    body: '{}',
                  });
                  setMessage(r.message || 'Receipt emailed');
                } catch (err: any) {
                  setError(err.message);
                }
              }}
            >
              Email receipt
            </button>
            <button
              onClick={async () => {
                try {
                  const r = await api(`/pos/sales/${receipt.sale_id}/receipt/send?channel=sms`, {
                    method: 'POST',
                    body: '{}',
                  });
                  setMessage(r.message || 'Receipt SMS sent');
                } catch (err: any) {
                  setError(err.message);
                }
              }}
            >
              SMS receipt
            </button>
          </div>
          </>
        ) : (
          <p className="muted">Complete a sale to view the thermal receipt here.</p>
        )}
      </div>
    </Shell>
  );
}
