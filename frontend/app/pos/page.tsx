'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Product = {
  id: string;
  product_id?: string;
  variant_id?: string | null;
  name: string;
  sku: string;
  selling_price: number;
  stock_qty: number;
  kind?: string;
};

type CartItem = Product & { quantity: number };

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
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState<any>(null);

  async function refreshSession() {
    const r = await api('/pos/sessions/current');
    setSession(r.data || null);
  }

  useEffect(() => {
    refreshSession().catch((err) => setError(err.message));
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

  async function search() {
    setError('');
    try {
      const r = await api('/pos/products/search?q=' + encodeURIComponent(q));
      setRows(r.data || []);
    } catch (err: any) {
      setError(err.message);
    }
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
        },
      ];
    });
  }

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
    }));
    const subtotal = cart.reduce((sum, c) => sum + Number(c.selling_price) * c.quantity, 0);
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
      setMessage(`Sale recorded: ${r.data.reference} (tax ${r.data.tax ?? 0})${drawerNote}`);
      setCart([]);
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

      <div className="card">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search product or scan barcode"
          style={{ padding: 12, width: '70%' }}
          disabled={!session}
        />
        <button onClick={search} style={{ padding: 12 }} disabled={!session}>
          Search
        </button>
      </div>

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
        {cart.length === 0 && <p className="muted">No items</p>}
        {cart.map((c) => (
          <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span>
              {c.name} × {c.quantity}
            </span>
            <span>{(Number(c.selling_price) * c.quantity).toFixed(2)}</span>
          </div>
        ))}
        <label style={{ display: 'block', marginBottom: 8 }}>
          Payment{' '}
          <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
            <option value="cash">Cash</option>
            <option value="card">Card</option>
            <option value="wallet">Wallet</option>
            <option value="credit">Credit</option>
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
