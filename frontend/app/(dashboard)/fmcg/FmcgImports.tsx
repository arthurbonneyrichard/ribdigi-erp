'use client';

/**
 * FMCG import shipments and landed cost. Add what a consignment cost to bring in, see how it
 * spreads over the products before committing, then allocate it once. The goods themselves are
 * bought and received through Purchasing; this only adds the freight, duty and clearing on top.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const IMPORT_TABS = ['imports'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin'];
const KINDS = [
  { id: 'freight', label: 'Freight' }, { id: 'insurance', label: 'Insurance' }, { id: 'customs_duty', label: 'Customs duty' },
  { id: 'port', label: 'Port charges' }, { id: 'clearing', label: 'Clearing agent' }, { id: 'transport', label: 'Transport to us' }, { id: 'other', label: 'Other' },
];
const METHODS = [
  { id: 'payable', label: 'Not paid yet (owed)' }, { id: 'cash', label: 'Cash' }, { id: 'bank_transfer', label: 'Bank transfer' },
  { id: 'mobile_money', label: 'Mobile Money' }, { id: 'card', label: 'Card' }, { id: 'cheque', label: 'Cheque' },
];
const STATUS_WORDS: Record<string, string> = { open: 'Open', allocated: 'Costs added', cancelled: 'Cancelled' };
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';

export default function FmcgImports({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [list, setList] = useState<Row[]>([]);
  const [openId, setOpenId] = useState('');
  const [products, setProducts] = useState<Row[]>([]);
  const [form, setForm] = useState({ reference: '', container_no: '', eta: '', basis: 'value' });
  const [line, setLine] = useState({ product_id: '', quantity: '', goods_value: '' });
  const [cost, setCost] = useState({ kind: 'freight', amount: '', vendor: '', pay_method: 'payable' });
  const manager = MANAGERS.includes(role);
  const ship = list.find((s) => s.id === openId) || null;

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    setError('');
    try {
      const [s, p] = await Promise.all([api('/fmcg/shipments'), api('/products')]);
      setList(s?.data || []);
      setProducts(Array.isArray(p?.data) ? p.data : []);
    } catch (err) {
      setError(problem(err));
    }
  }, []);

  useEffect(() => {
    if (manager) load();
  }, [manager, load]);

  async function run(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await fn();
      setNotice(done);
      await load();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  const send = (path: string, body?: unknown, method = 'POST') => api(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

  if (role && !manager) {
    return (
      <div className="fmcg-sell">
        <FmcgHead tab={tab} />
        <div className="fs-banner">Import shipments are managed by a manager.</div>
      </div>
    );
  }

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      <section className="fs-box" aria-label="New shipment">
        <div className="fs-cardhead"><h2>New shipment</h2></div>
        <div className="fs-form">
          <label><span>Bill of lading / reference</span><input value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} aria-label="Shipment reference" /></label>
          <label><span>Container number</span><input value={form.container_no} onChange={(e) => setForm({ ...form, container_no: e.target.value })} aria-label="Container number" /></label>
          <label><span>Expected arrival</span><input type="date" value={form.eta} onChange={(e) => setForm({ ...form, eta: e.target.value })} aria-label="Expected arrival" /></label>
          <label><span>Spread costs by</span>
            <select value={form.basis} onChange={(e) => setForm({ ...form, basis: e.target.value })} aria-label="Spread basis">
              <option value="value">Value of goods</option><option value="quantity">Number of units</option>
            </select>
          </label>
          <button type="button" className="fs-primary" disabled={busy}
            onClick={() => run(async () => {
              const res = await send('/fmcg/shipments', {
                basis: form.basis, ...(form.reference.trim().length >= 2 ? { reference: form.reference.trim() } : {}),
                ...(form.container_no.trim().length >= 2 ? { container_no: form.container_no.trim() } : {}), ...(form.eta ? { eta: form.eta } : {}),
              });
              setOpenId(res?.data?.id || '');
              setForm({ reference: '', container_no: '', eta: '', basis: 'value' });
            }, 'Shipment opened.')}>Open shipment</button>
        </div>
        <p className="fs-muted">Buy and receive the goods in Purchasing first. A shipment adds what it cost to bring them in.</p>
      </section>

      <section className="fs-box fs-scroll" aria-label="Shipments">
        <table>
          <thead><tr><th>No.</th><th>Reference</th><th>Status</th><th>Goods</th><th>Costs</th><th>Added to goods</th><th /></tr></thead>
          <tbody>
            {list.map((s) => (
              <tr key={s.id}>
                <td>{s.shipment_number}</td><td>{s.reference || '-'}</td><td>{s.status === 'open' ? STATUS_WORDS.open : <span className="fs-flag">{STATUS_WORDS[s.status]}</span>}</td>
                <td className="fs-num">{formatMoney(s.goods_value)}</td><td className="fs-num">{formatMoney(s.total_costs)}</td>
                <td className="fs-num">{s.uplift_pct != null ? `${s.uplift_pct}%` : '-'}</td>
                <td><button type="button" aria-label={`Open ${s.shipment_number}`} onClick={() => setOpenId(s.id)}>Open</button></td>
              </tr>
            ))}
            {list.length === 0 ? <tr><td colSpan={7} className="fs-muted">No shipments yet.</td></tr> : null}
          </tbody>
        </table>
      </section>

      {ship ? (
        <section className="fs-box fs-scroll" aria-label="Shipment detail">
          <div className="fs-cardhead"><h2>{ship.shipment_number} · {ship.reference || 'no reference'} · {STATUS_WORDS[ship.status]}</h2></div>
          <table>
            <thead><tr><th>Product</th><th>Units</th><th>Goods value</th><th>Costs share</th><th>Cost per unit with costs</th><th>To stock</th><th>To cost of goods sold</th><th /></tr></thead>
            <tbody>
              {ship.lines.map((l: Row) => (
                <tr key={l.id}>
                  <td>{l.product}</td><td className="fs-num">{l.quantity}</td><td className="fs-num">{formatMoney(l.goods_value)}</td>
                  <td className="fs-num">{l.allocated != null ? formatMoney(l.allocated) : '-'}</td><td className="fs-num">{l.landed_unit_cost}</td>
                  <td className="fs-num">{l.to_stock != null ? formatMoney(l.to_stock) : '-'}</td><td className="fs-num">{l.to_cost_of_goods != null ? formatMoney(l.to_cost_of_goods) : '-'}</td>
                  <td>{ship.status === 'open' ? <button type="button" disabled={busy} aria-label={`Remove ${l.product}`} onClick={() => run(() => send(`/fmcg/shipments/${ship.id}/lines/${l.id}`, undefined, 'DELETE'), 'Removed.')}>Remove</button> : null}</td>
                </tr>
              ))}
              {ship.lines.length === 0 ? <tr><td colSpan={8} className="fs-muted">No products yet.</td></tr> : null}
            </tbody>
          </table>
          <table>
            <thead><tr><th>Cost</th><th>Amount</th><th>Vendor</th><th>Paid</th><th /></tr></thead>
            <tbody>
              {ship.costs.map((c: Row) => (
                <tr key={c.id}>
                  <td>{KINDS.find((k) => k.id === c.kind)?.label}</td><td className="fs-num">{formatMoney(c.amount)}</td><td>{c.vendor || '-'}</td>
                  <td>{METHODS.find((k) => k.id === c.pay_method)?.label}</td>
                  <td>{ship.status === 'open' ? <button type="button" disabled={busy} aria-label={`Remove ${c.kind} cost`} onClick={() => run(() => send(`/fmcg/shipments/${ship.id}/costs/${c.id}`, undefined, 'DELETE'), 'Removed.')}>Remove</button> : null}</td>
                </tr>
              ))}
              {ship.costs.length === 0 ? <tr><td colSpan={5} className="fs-muted">No costs yet.</td></tr> : null}
            </tbody>
          </table>

          {ship.status === 'open' ? (
            <>
              <div className="fs-form">
                <label><span>Product</span>
                  <select value={line.product_id} onChange={(e) => setLine({ ...line, product_id: e.target.value })} aria-label="Shipment product">
                    <option value="">Pick a product</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </label>
                <label><span>Units received</span><input type="number" min="0" value={line.quantity} onChange={(e) => setLine({ ...line, quantity: e.target.value })} aria-label="Shipment units" /></label>
                <label><span>Goods value (invoice)</span><input type="number" min="0" value={line.goods_value} onChange={(e) => setLine({ ...line, goods_value: e.target.value })} aria-label="Shipment goods value" /></label>
                <button type="button" disabled={busy || !line.product_id || !(Number(line.quantity) > 0) || line.goods_value === ''}
                  onClick={() => run(async () => { await send(`/fmcg/shipments/${ship.id}/lines`, { product_id: line.product_id, quantity: Number(line.quantity), goods_value: Number(line.goods_value) }); setLine({ product_id: '', quantity: '', goods_value: '' }); }, 'Product added.')}>Add product</button>
              </div>
              <div className="fs-form">
                <label><span>Cost</span>
                  <select value={cost.kind} onChange={(e) => setCost({ ...cost, kind: e.target.value })} aria-label="Cost kind">{KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select>
                </label>
                <label><span>Amount</span><input type="number" min="0" value={cost.amount} onChange={(e) => setCost({ ...cost, amount: e.target.value })} aria-label="Cost amount" /></label>
                <label><span>Vendor</span><input value={cost.vendor} onChange={(e) => setCost({ ...cost, vendor: e.target.value })} aria-label="Cost vendor" /></label>
                <label><span>How paid</span>
                  <select value={cost.pay_method} onChange={(e) => setCost({ ...cost, pay_method: e.target.value })} aria-label="Cost payment">{METHODS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select>
                </label>
                <button type="button" disabled={busy || !(Number(cost.amount) > 0)}
                  onClick={() => run(async () => { await send(`/fmcg/shipments/${ship.id}/costs`, { kind: cost.kind, amount: Number(cost.amount), pay_method: cost.pay_method, ...(cost.vendor.trim().length >= 2 ? { vendor: cost.vendor.trim() } : {}) }); setCost({ ...cost, amount: '', vendor: '' }); }, 'Cost added.')}>Add cost</button>
              </div>
              <div className="fs-form">
                <button type="button" className="fs-primary" disabled={busy || !ship.lines.length || !ship.costs.length}
                  onClick={() => { if (window.confirm('Add these costs to the cost of the goods? This cannot be undone.')) run(() => send(`/fmcg/shipments/${ship.id}/allocate`), 'Costs added to the goods.'); }}>Add costs to the goods</button>
                <button type="button" className="fs-danger" disabled={busy} onClick={() => run(() => send(`/fmcg/shipments/${ship.id}/cancel`), 'Cancelled.')}>Cancel shipment</button>
              </div>
              <p className="fs-muted">The table above shows how the costs will spread. Stock still on hand gets its share added to its unit cost. The share for units already sold goes to cost of goods sold.</p>
            </>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
