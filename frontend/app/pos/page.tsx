'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

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
};

function looksLikeBarcode(value: string) {
  const text = value.trim();
  if (!text || /\s/.test(text)) return false;
  return /^[A-Za-z0-9\-._]{4,48}$/.test(text);
}

type CartItem = Product & { quantity: number };

type Customer = {
  id: string;
  name: string;
  email?: string | null;
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
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [paper, setPaper] = useState('80mm');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [lastSale, setLastSale] = useState<{ id: string; reference: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [cashierName, setCashierName] = useState('');
  const [receiptBusy, setReceiptBusy] = useState('');

  const cartTotal = useMemo(
    () => cart.reduce((sum, c) => sum + Number(c.selling_price) * c.quantity, 0),
    [cart]
  );
  const cartCount = useMemo(() => cart.reduce((sum, c) => sum + c.quantity, 0), [cart]);

  async function refreshSession() {
    const r = await api('/pos/sessions/current');
    setSession(r.data || null);
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
  }, [browse]);

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
      setMessage(
        `Shift closed. Variance: ${r.data.variance ?? 0} (expected ${r.data.expected_cash})`
      );
      setActualCash('');
      setCart([]);
    } catch (err: any) {
      setError(err.message);
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
        },
      ];
    });
  }

  function bumpQty(id: string, delta: number) {
    setCart((prev) =>
      prev
        .map((p) => (p.id === id ? { ...p, quantity: p.quantity + delta } : p))
        .filter((p) => p.quantity > 0)
    );
  }

  function clearCart() {
    setCart([]);
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
    if (paymentMethod === 'credit' && !customerId) {
      setError('Select a customer for credit sales');
      return;
    }
    const items = cart.map((c) => ({
      product_id: c.product_id || c.id,
      variant_id: c.variant_id || null,
      quantity: c.quantity,
    }));
    const subtotal = cart.reduce((sum, c) => sum + Number(c.selling_price) * c.quantity, 0);
    setBusy(true);
    try {
      const r = await api('/pos/sales', {
        method: 'POST',
        body: JSON.stringify({
          session_id: session.session_id,
          subtotal,
          tax: 0,
          total: subtotal,
          status: 'completed',
          payment_method: paymentMethod,
          party_id: customerId || null,
          customer_name: name || null,
          items,
        }),
      });
      if (!r?.data?.id || !r?.data?.reference) {
        throw new Error(r?.message || 'Sale failed');
      }
      setCart([]);
      clearCustomer();
      setLastSale({ id: r.data.id, reference: r.data.reference });
      await refreshSession();
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
              {cart.map((c) => (
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
                  <div className="tpos-line">{money(Number(c.selling_price) * c.quantity)}</div>
                </div>
              ))}
            </div>

            <div className="tpos-cart-foot">
              <div className="tpos-total">
                <span>Total</span>
                <strong>{money(cartTotal)}</strong>
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

              <label className="tpos-field">
                <span>Payment</span>
                <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
                  <option value="cash">Cash</option>
                  <option value="card">Card</option>
                  <option value="wallet">Wallet</option>
                  <option value="credit">Credit</option>
                </select>
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
