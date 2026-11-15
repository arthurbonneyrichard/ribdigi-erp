'use client';

/**
 * Retail till: hold a sale (park the cart and serve the next customer) and layaway (set goods aside
 * for a customer who pays in parts). Layaway money is held for the customer until the last part is
 * paid; then the goods are handed over and the sale is booked.
 */

import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api';

type Line = { product_id: string; quantity: number; unit_price?: number; name?: string };
type Row = Record<string, any>;

type Props = {
  storeId: string | null;
  cart: Line[];
  customerName?: string;
  customerId?: string;
  online: boolean;
  formatMoney: (n: number) => string;
  onHeld: () => void;
  onResume: (lines: Line[]) => void | Promise<void>;
};

const METHODS: [string, string][] = [
  ['cash', 'Cash'],
  ['mobile_money', 'MoMo'],
  ['card', 'Card'],
  ['bank_transfer', 'Bank'],
];

function problem(err: unknown) {
  return err instanceof Error ? err.message : 'Something went wrong. Try again.';
}

export default function PosHoldLayaway({ storeId, cart, customerName, customerId, online, formatMoney, onHeld, onResume }: Props) {
  const [held, setHeld] = useState<Row[]>([]);
  const [panel, setPanel] = useState<'' | 'held' | 'layaway'>('');
  const [layaways, setLayaways] = useState<Row[]>([]);
  const [form, setForm] = useState({ name: '', phone: '', deposit: '', method: 'cash', due: '' });
  const [pay, setPay] = useState<Record<string, { amount: string; method: string }>>({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  const loadHeld = useCallback(async () => {
    try {
      const res = await api(`/pos/held${storeId ? `?store_id=${storeId}` : ''}`);
      setHeld((res?.data || []) as Row[]);
    } catch {
      /* offline: nothing to show */
    }
  }, [storeId]);

  const loadLayaways = useCallback(async () => {
    try {
      const res = await api('/pos/layaways?status=open');
      setLayaways((res?.data || []) as Row[]);
    } catch (err) {
      setError(problem(err));
    }
  }, []);

  useEffect(() => {
    if (online) void loadHeld();
  }, [online, loadHeld]);

  useEffect(() => {
    setForm((f) => ({ ...f, name: f.name || customerName || '' }));
  }, [customerName]);

  async function run(work: () => Promise<string>) {
    setBusy(true);
    setError('');
    try {
      setNotice(await work());
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  function holdSale() {
    if (!cart.length) return;
    const label = window.prompt('Name this sale so you can find it again (for example the customer)', customerName || '');
    if (label === null) return;
    void run(async () => {
      await api('/pos/held', {
        method: 'POST',
        body: JSON.stringify({ label: label.trim() || 'Held sale', store_id: storeId, items: cart }),
      });
      onHeld();
      await loadHeld();
      return 'Sale on hold. Serve the next customer.';
    });
  }

  if (!online) return null;

  return (
    <div className="tpos-hold-bar" style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '6px 0' }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button type="button" disabled={busy || !cart.length} aria-label="Hold this sale" onClick={holdSale}>
          Hold sale
        </button>
        <button type="button" aria-label="Show held sales" aria-expanded={panel === 'held'} onClick={() => { setPanel(panel === 'held' ? '' : 'held'); void loadHeld(); }}>
          Held ({held.length})
        </button>
        <button type="button" aria-label="Layaway" aria-expanded={panel === 'layaway'} onClick={() => { setPanel(panel === 'layaway' ? '' : 'layaway'); void loadLayaways(); }}>
          Layaway
        </button>
      </div>
      {notice ? <p role="status" style={{ margin: 0, fontWeight: 600 }} onClick={() => setNotice('')}>{notice}</p> : null}
      {error ? <p role="alert" style={{ margin: 0, fontWeight: 600 }} onClick={() => setError('')}>{error}</p> : null}

      {panel === 'held' ? (
        <div role="region" aria-label="Held sales" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {held.length === 0 ? <p style={{ margin: 0 }}>No sales on hold.</p> : null}
          {held.map((h) => (
            <div key={h.id} style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'space-between' }}>
              <span>
                <strong>{h.label}</strong> · {h.item_count} {h.item_count === 1 ? 'item' : 'items'} · {formatMoney(Number(h.total || 0))}
              </span>
              <button
                type="button"
                disabled={busy || cart.length > 0}
                title={cart.length ? 'Finish or hold the cart on screen first' : undefined}
                aria-label={`Pick up held sale ${h.label}`}
                onClick={() =>
                  void run(async () => {
                    const res = await api(`/pos/held/${h.id}/take`, { method: 'POST', body: '{}' });
                    await onResume(((res?.data?.cart?.items || []) as Line[]));
                    await loadHeld();
                    setPanel('');
                    return `${h.label} is back on the till.`;
                  })
                }
              >
                Pick up
              </button>
            </div>
          ))}
        </div>
      ) : null}

      {panel === 'layaway' ? (
        <div role="region" aria-label="Layaways" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {cart.length ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <strong>Put the cart on layaway</strong>
              <input aria-label="Layaway customer name" placeholder="Customer name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input aria-label="Layaway customer phone" placeholder="Phone (+233…)" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value.replace(/[^0-9+]/g, '') })} />
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <input aria-label="Layaway deposit" inputMode="decimal" placeholder="Deposit now" value={form.deposit} onChange={(e) => setForm({ ...form, deposit: e.target.value.replace(/[^0-9.]/g, '') })} />
                <select aria-label="Layaway deposit method" value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })}>
                  {METHODS.map(([k, label]) => (
                    <option key={k} value={k}>{label}</option>
                  ))}
                </select>
                <input type="date" aria-label="Layaway collect by date" value={form.due} onChange={(e) => setForm({ ...form, due: e.target.value })} />
              </div>
              <button
                type="button"
                disabled={busy || !form.name.trim() || !form.phone.trim()}
                aria-label="Open layaway"
                onClick={() =>
                  void run(async () => {
                    let phone = form.phone.trim();
                    if (/^0\d{9}$/.test(phone)) phone = `+233${phone.slice(1)}`;
                    const res = await api('/pos/layaways', {
                      method: 'POST',
                      body: JSON.stringify({
                        store_id: storeId,
                        customer_id: customerId || null,
                        customer_name: form.name.trim(),
                        phone,
                        items: cart.map((l) => ({ product_id: l.product_id, quantity: l.quantity })),
                        deposit: Number(form.deposit) || 0,
                        deposit_method: form.method,
                        due_date: form.due || null,
                      }),
                    });
                    onHeld();
                    setForm({ name: '', phone: '', deposit: '', method: 'cash', due: '' });
                    await loadLayaways();
                    const row = res?.data || {};
                    return `${row.layaway_number}: goods set aside. ${formatMoney(Number(row.balance || 0))} left to pay.`;
                  })
                }
              >
                Set the goods aside
              </button>
            </div>
          ) : (
            <p style={{ margin: 0 }}>Add the goods to the cart, then open a layaway. Payments on open layaways are below.</p>
          )}
          {layaways.length === 0 ? <p style={{ margin: 0 }}>No open layaways.</p> : null}
          {layaways.map((l) => {
            const p = pay[l.id] || { amount: '', method: 'cash' };
            return (
              <div key={l.id} style={{ borderTop: '1px solid currentColor', paddingTop: 6, display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span>
                  <strong>{l.layaway_number}</strong> · {l.customer_name} · {l.phone} · paid {formatMoney(Number(l.paid || 0))} of {formatMoney(Number(l.total || 0))}
                  {l.due_date ? ` · collect by ${l.due_date}` : ''}
                </span>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <input
                    aria-label={`Payment for ${l.layaway_number}`}
                    inputMode="decimal"
                    placeholder={String(l.balance)}
                    value={p.amount}
                    onChange={(e) => setPay({ ...pay, [l.id]: { ...p, amount: e.target.value.replace(/[^0-9.]/g, '') } })}
                  />
                  <select aria-label={`Payment method for ${l.layaway_number}`} value={p.method} onChange={(e) => setPay({ ...pay, [l.id]: { ...p, method: e.target.value } })}>
                    {METHODS.map(([k, label]) => (
                      <option key={k} value={k}>{label}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={busy}
                    aria-label={`Take payment for ${l.layaway_number}`}
                    onClick={() =>
                      void run(async () => {
                        const amount = Number(p.amount) || Number(l.balance);
                        const res = await api(`/pos/layaways/${l.id}/payments`, { method: 'POST', body: JSON.stringify({ amount, method: p.method }) });
                        await loadLayaways();
                        return res?.data?.status === 'completed'
                          ? `${l.layaway_number} is paid in full. Hand over the goods.`
                          : `${formatMoney(amount)} received. ${formatMoney(Number(res?.data?.balance || 0))} left.`;
                      })
                    }
                  >
                    Take payment
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    aria-label={`Cancel ${l.layaway_number}`}
                    onClick={() => {
                      const reason = window.prompt('Why is this layaway cancelled?');
                      if (!reason || reason.trim().length < 3) return;
                      const keepText = window.prompt(`Keep a cancellation fee? Enter the amount to keep from the ${formatMoney(Number(l.paid || 0))} paid, or 0 to refund it all.`, '0');
                      if (keepText === null) return;
                      void run(async () => {
                        await api(`/pos/layaways/${l.id}/cancel`, {
                          method: 'POST',
                          body: JSON.stringify({ reason: reason.trim(), keep: Number(keepText) || 0 }),
                        });
                        await loadLayaways();
                        return `${l.layaway_number} cancelled. The goods are back on sale.`;
                      });
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
