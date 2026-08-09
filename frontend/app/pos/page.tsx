'use client';

import { useEffect, useState } from 'react';
import BarcodeCameraScanner from '../../components/BarcodeCameraScanner';
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
};

type CartItem = Product & { quantity: number; discount: number };

type Customer = { id: string; name: string; code?: string | null; credit_limit?: number; balance?: number };

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
  const [paper, setPaper] = useState('80mm');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [cartDiscount, setCartDiscount] = useState('0');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState<any>(null);
  const [scannerOpen, setScannerOpen] = useState(false);

  async function refreshSession() {
    const r = await api('/pos/sessions/current');
    setSession(r.data || null);
  }

  useEffect(() => {
    refreshSession().catch((err) => setError(err.message));
    api('/customers?active_only=true')
      .then((r) => setCustomers(r.data || []))
      .catch(() => setCustomers([]));
  }, []);

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
    try {
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

  const cartSubtotal = cart.reduce(
    (sum, c) => sum + Math.max(0, Number(c.selling_price) * c.quantity - (c.discount || 0)),
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
    if (paymentMethod === 'credit' && !customerId) {
      setError('Select a customer for credit sales');
      return;
    }
    const items = cart.map((c) => ({
      product_id: c.product_id || c.id,
      variant_id: c.variant_id || null,
      quantity: c.quantity,
      discount: c.discount || 0,
    }));
    const discountAmount = Number(cartDiscount) || 0;
    try {
      const r = await api('/pos/sales', {
        method: 'POST',
        body: JSON.stringify({
          session_id: session.session_id,
          party_id: customerId || null,
          discount_amount: discountAmount,
          status: 'completed',
          payment_method: paymentMethod,
          items,
        }),
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
      setMessage(
        `Sale recorded: ${r.data.reference} (tax ${r.data.tax ?? 0}` +
          (r.data.discount_amount ? `, discount ${r.data.discount_amount}` : '') +
          `)${drawerNote}`,
      );
      setCart([]);
      setCartDiscount('0');
      await refreshSession();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <Shell>
      <h1>Point of Sale</h1>
      <p className="muted">Open a shift, sell from cart, print thermal receipt</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
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
            <div className="kpi">{r.selling_price}</div>
            <p className="muted">Stock: {r.stock_qty}</p>
            <button onClick={() => addToCart(r)} disabled={!session}>
              Add
            </button>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
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
              </option>
            ))}
          </select>
        </label>
        {cart.length === 0 && <p className="muted">No items</p>}
        {cart.map((c) => {
          const lineGross = Number(c.selling_price) * c.quantity;
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
                  {c.sku} · {Number(c.selling_price).toFixed(2)} each
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
        <label style={{ display: 'block', marginBottom: 8 }}>
          Payment{' '}
          <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
            <option value="cash">Cash</option>
            <option value="card">Card</option>
            <option value="wallet">Digital wallet</option>
            <option value="credit">Credit (registered customer)</option>
          </select>
        </label>
        <label style={{ display: 'block', marginBottom: 8 }}>
          Receipt paper{' '}
          <select value={paper} onChange={(e) => setPaper(e.target.value)}>
            <option value="80mm">80mm thermal</option>
            <option value="58mm">58mm thermal</option>
          </select>
        </label>
        <button onClick={checkout} disabled={!cart.length || !session}>
          Complete sale
        </button>
      </div>

      {receipt && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Receipt</h3>
          <p>
            {receipt.reference} · Total {receipt.total} · {receipt.payment_method}
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
        </div>
      )}
    </Shell>
  );
}
