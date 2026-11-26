'use client';

/**
 * FMCG van sales. Pick an open dispatch, load stock on the van, sell from it, record damages,
 * samples and costs, then count up at the end of the day. The server does every sum and
 * decides whether a difference is allowed; this screen only asks and shows.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { printPaymentReceipt } from '../../../lib/receiptPrint';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const VAN_TABS = ['van'];
const METHODS = [
  { id: 'cash', label: 'Cash' },
  { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'card', label: 'Card' },
  { id: 'bank_transfer', label: 'Bank transfer' },
];
const EXPENSES = ['fuel', 'toll', 'parking', 'meal', 'other'];

const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';

export default function FmcgVan({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [dispatches, setDispatches] = useState<Row[]>([]);
  const [dispatchId, setDispatchId] = useState('');
  const [van, setVan] = useState<Row | null>(null);
  const [outlets, setOutlets] = useState<Row[]>([]);
  const [products, setProducts] = useState<Row[]>([]);
  const [load, setLoad] = useState({ product_id: '', quantity: '' });
  const [sale, setSale] = useState({ customer_id: '', product_id: '', quantity: '', terms: 'cash', payment_method: 'cash' });
  const [loss, setLoss] = useState({ product_id: '', quantity: '', kind: 'damaged', note: '' });
  const [spend, setSpend] = useState({ kind: 'fuel', amount: '', note: '' });
  const [counts, setCounts] = useState<Record<string, string>>({});
  const [cash, setCash] = useState('');
  const [why, setWhy] = useState('');
  const manager = ['company_admin', 'fmcg_manager', 'super_admin'].includes(role);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const refresh = useCallback(async () => {
    setError('');
    try {
      const [d, o] = await Promise.all([api('/fmcg/dispatches'), api('/fmcg/outlets')]);
      const open = (d?.data || []).filter((x: Row) => x.status === 'open');
      setDispatches(open);
      setOutlets(o?.data || []);
      setDispatchId((cur) => (open.some((x: Row) => x.id === cur) ? cur : open[0]?.id || ''));
    } catch (err) {
      setError(problem(err));
    }
  }, []);

  const loadVan = useCallback(async () => {
    if (!dispatchId) return setVan(null);
    try {
      setVan((await api(`/fmcg/dispatches/${dispatchId}/van`))?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }, [dispatchId]);

  useEffect(() => {
    if (role) refresh();
  }, [role, refresh]);
  useEffect(() => {
    loadVan();
  }, [loadVan]);
  useEffect(() => {
    if (!manager) return;
    api('/products').then((r: Row) => setProducts(Array.isArray(r?.data) ? r.data : [])).catch(() => setProducts([]));
  }, [manager]);

  async function run(fn: () => Promise<Row | void>, done: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await fn();
      if (res?.data?.van) setVan(res.data.van);
      else if (res?.data?.lines) setVan(res.data);
      setNotice(done);
      await refresh();
      await loadVan();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  const post = (path: string, body: unknown) => api(`/fmcg/dispatches/${dispatchId}/van/${path}`, { method: 'POST', body: JSON.stringify(body) });
  const onVan: Row[] = van?.lines || [];
  const money: Row = van?.money || {};
  const closed = van?.status === 'closed';

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      <section className="fs-box" aria-label="Choose a van">
        <div className="fs-form">
          <label><span>Open dispatch</span>
            <select value={dispatchId} onChange={(e) => setDispatchId(e.target.value)} aria-label="Van dispatch">
              {dispatches.length === 0 ? <option value="">None open</option> : null}
              {dispatches.map((d) => <option key={d.id} value={d.id}>{d.dispatch_number} · {d.route_code || ''} · {d.dispatch_date}</option>)}
            </select>
          </label>
        </div>
        {dispatches.length === 0 ? <p className="fs-muted">A manager opens a dispatch for the route on the Deliveries screen first.</p> : null}
      </section>

      {van ? (
        <>
          <section className="fs-box fs-scroll" aria-label="Van stock">
            <div className="fs-cardhead"><h2>On the van</h2></div>
            <table>
              <thead><tr><th>Product</th><th>Loaded</th><th>Sold</th><th>Damaged</th><th>Samples</th><th>Should be left</th></tr></thead>
              <tbody>
                {onVan.map((l) => (
                  <tr key={l.product_id}>
                    <td>{l.product_name}</td><td className="fs-num">{l.loaded}</td><td className="fs-num">{l.sold}</td>
                    <td className="fs-num">{l.damaged}</td><td className="fs-num">{l.samples}</td><td className="fs-num"><strong>{l.expected_back}</strong></td>
                  </tr>
                ))}
                {onVan.length === 0 ? <tr><td colSpan={6} className="fs-muted">Nothing loaded yet.</td></tr> : null}
              </tbody>
            </table>
            <p>
              Cash in {formatMoney(money.cash_collected)} · Mobile Money {formatMoney(money.mobile_money)} · Card {formatMoney(money.card)} ·
              On credit {formatMoney(money.credit_sales)} · Costs {formatMoney(money.expenses)} ·{' '}
              <strong>Cash to hand in {formatMoney(money.cash_to_hand_in)}</strong>
            </p>
          </section>

          {!closed ? (
            <>
              {manager ? (
                <section className="fs-box" aria-label="Load the van">
                  <div className="fs-cardhead"><h2>Load stock on the van</h2></div>
                  <div className="fs-form">
                    <label><span>Product</span>
                      <select value={load.product_id} onChange={(e) => setLoad({ ...load, product_id: e.target.value })} aria-label="Load product">
                        <option value="">Pick a product</option>
                        {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </label>
                    <label><span>Quantity</span><input type="number" min="0" value={load.quantity} onChange={(e) => setLoad({ ...load, quantity: e.target.value })} aria-label="Load quantity" /></label>
                    <button type="button" className="fs-primary" disabled={busy || !load.product_id || !(Number(load.quantity) > 0)}
                      onClick={() => run(async () => { const r = await post('load', { lines: [{ product_id: load.product_id, quantity: Number(load.quantity) }] }); setLoad({ product_id: '', quantity: '' }); return r; }, 'Loaded.')}>Load</button>
                  </div>
                </section>
              ) : null}

              <section className="fs-box" aria-label="Sell from the van">
                <div className="fs-cardhead"><h2>Sell from the van</h2></div>
                <div className="fs-form">
                  <label><span>Outlet</span>
                    <select value={sale.customer_id} onChange={(e) => setSale({ ...sale, customer_id: e.target.value })} aria-label="Van sale outlet">
                      <option value="">Pick an outlet</option>
                      {outlets.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                    </select>
                  </label>
                  <label><span>Product</span>
                    <select value={sale.product_id} onChange={(e) => setSale({ ...sale, product_id: e.target.value })} aria-label="Van sale product">
                      <option value="">Pick a product</option>
                      {onVan.filter((l) => l.expected_back > 0).map((l) => <option key={l.product_id} value={l.product_id}>{l.product_name} ({l.expected_back} left)</option>)}
                    </select>
                  </label>
                  <label><span>Quantity</span><input type="number" min="0" value={sale.quantity} onChange={(e) => setSale({ ...sale, quantity: e.target.value })} aria-label="Van sale quantity" /></label>
                  <label><span>Terms</span>
                    <select value={sale.terms} onChange={(e) => setSale({ ...sale, terms: e.target.value })} aria-label="Van sale terms">
                      <option value="cash">Paid now</option><option value="credit">On credit</option>
                    </select>
                  </label>
                  {sale.terms === 'cash' ? (
                    <label><span>How paid</span>
                      <select value={sale.payment_method} onChange={(e) => setSale({ ...sale, payment_method: e.target.value })} aria-label="Van sale payment method">
                        {METHODS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                      </select>
                    </label>
                  ) : null}
                  <button type="button" className="fs-primary" disabled={busy || !sale.customer_id || !sale.product_id || !(Number(sale.quantity) > 0)}
                    onClick={() => run(() => post('sales', {
                      customer_id: sale.customer_id, terms: sale.terms,
                      lines: [{ product_id: sale.product_id, quantity: Number(sale.quantity) }],
                      ...(sale.terms === 'cash' ? { payment_method: sale.payment_method } : {}),
                    }).then((r: Row) => { printPaymentReceipt('fmcg_payment', r?.data?.payment_id); setSale({ ...sale, product_id: '', quantity: '' }); return r; }), 'Sold.')}>Sell</button>
                </div>
                <p className="fs-muted">This records the sale and the money. It does not take the payment: Mobile Money and card are what the outlet already paid you.</p>
              </section>

              <section className="fs-box" aria-label="Damages and samples">
                <div className="fs-cardhead"><h2>Damaged or given away</h2></div>
                <div className="fs-form">
                  <label><span>Product</span>
                    <select value={loss.product_id} onChange={(e) => setLoss({ ...loss, product_id: e.target.value })} aria-label="Loss product">
                      <option value="">Pick a product</option>
                      {onVan.map((l) => <option key={l.product_id} value={l.product_id}>{l.product_name}</option>)}
                    </select>
                  </label>
                  <label><span>Quantity</span><input type="number" min="0" value={loss.quantity} onChange={(e) => setLoss({ ...loss, quantity: e.target.value })} aria-label="Loss quantity" /></label>
                  <label><span>What happened</span>
                    <select value={loss.kind} onChange={(e) => setLoss({ ...loss, kind: e.target.value })} aria-label="Loss kind">
                      <option value="damaged">Damaged</option><option value="sample">Free sample</option>
                    </select>
                  </label>
                  <label><span>Note</span><input value={loss.note} onChange={(e) => setLoss({ ...loss, note: e.target.value })} aria-label="Loss note" /></label>
                  <button type="button" disabled={busy || !loss.product_id || !(Number(loss.quantity) > 0) || loss.note.trim().length < 3}
                    onClick={() => run(async () => { const r = await post('losses', { product_id: loss.product_id, quantity: Number(loss.quantity), kind: loss.kind, note: loss.note.trim() }); setLoss({ ...loss, quantity: '', note: '' }); return r; }, 'Recorded.')}>Record</button>
                </div>
              </section>

              <section className="fs-box" aria-label="Van costs">
                <div className="fs-cardhead"><h2>Costs paid from the takings</h2></div>
                <div className="fs-form">
                  <label><span>Type</span>
                    <select value={spend.kind} onChange={(e) => setSpend({ ...spend, kind: e.target.value })} aria-label="Cost type">
                      {EXPENSES.map((x) => <option key={x} value={x}>{x}</option>)}
                    </select>
                  </label>
                  <label><span>Amount</span><input type="number" min="0" value={spend.amount} onChange={(e) => setSpend({ ...spend, amount: e.target.value })} aria-label="Cost amount" /></label>
                  <label><span>Note</span><input value={spend.note} onChange={(e) => setSpend({ ...spend, note: e.target.value })} aria-label="Cost note" /></label>
                  <button type="button" disabled={busy || !(Number(spend.amount) > 0)}
                    onClick={() => run(async () => { const r = await post('expenses', { kind: spend.kind, amount: Number(spend.amount), ...(spend.note.trim().length >= 3 ? { note: spend.note.trim() } : {}) }); setSpend({ ...spend, amount: '', note: '' }); return r; }, 'Recorded.')}>Record cost</button>
                </div>
              </section>

              <section className="fs-box" aria-label="Close the van">
                <div className="fs-cardhead"><h2>End of day: count up and close</h2></div>
                <div className="fs-form">
                  {onVan.map((l) => (
                    <label key={l.product_id}><span>{l.product_name} (should be {l.expected_back})</span>
                      <input type="number" min="0" value={counts[l.product_id] ?? ''} onChange={(e) => setCounts({ ...counts, [l.product_id]: e.target.value })} aria-label={`Counted ${l.product_name}`} />
                    </label>
                  ))}
                  <label><span>Cash counted (should be {formatMoney(money.cash_to_hand_in)})</span>
                    <input type="number" min="0" value={cash} onChange={(e) => setCash(e.target.value)} aria-label="Cash counted" />
                  </label>
                  <label><span>Reason, if there is a difference</span><input value={why} onChange={(e) => setWhy(e.target.value)} aria-label="Reason for the difference" /></label>
                  <button type="button" className="fs-primary" disabled={busy || cash === '' || onVan.some((l) => (counts[l.product_id] ?? '') === '')}
                    onClick={() => run(() => post('close', {
                      counted: onVan.map((l) => ({ product_id: l.product_id, quantity: Number(counts[l.product_id]) })),
                      counted_cash: Number(cash), ...(why.trim() ? { note: why.trim() } : {}),
                    }), 'Van closed.')}>Close van</button>
                </div>
                <p className="fs-muted">If the count or the cash is off, only a manager can close the van, and a reason is required. The difference is booked as a loss or gain.</p>
              </section>
            </>
          ) : (
            <div className="fs-banner">This van is closed.</div>
          )}
        </>
      ) : null}
    </div>
  );
}
