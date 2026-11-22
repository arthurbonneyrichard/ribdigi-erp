'use client';

/**
 * FMCG optional manufacturing: recipes, production orders, wastage and cost. Off until a manager
 * switches it on, so distributors never see it. Every rule and sum is done on the server.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const MFG_TABS = ['manufacturing'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin'];
const OVERHEADS = [{ id: 'labour', label: 'Labour' }, { id: 'power', label: 'Power' }, { id: 'packaging', label: 'Packaging' }, { id: 'transport', label: 'Transport' }, { id: 'other', label: 'Other' }];
const METHODS = [{ id: 'payable', label: 'Not paid yet' }, { id: 'cash', label: 'Cash' }, { id: 'bank_transfer', label: 'Bank transfer' }, { id: 'mobile_money', label: 'Mobile Money' }, { id: 'card', label: 'Card' }, { id: 'cheque', label: 'Cheque' }];
const STATUS_WORDS: Record<string, string> = { planned: 'Planned', in_progress: 'In production', completed: 'Done', cancelled: 'Cancelled' };
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export default function FmcgMfg({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [boms, setBoms] = useState<Row[]>([]);
  const [orders, setOrders] = useState<Row[]>([]);
  const [products, setProducts] = useState<Row[]>([]);
  const [report, setReport] = useState<Row | null>(null);
  const [recipe, setRecipe] = useState({ product_id: '', name: '', output_qty: '1', shelf_life_days: '' });
  const [lines, setLines] = useState<{ component_id: string; quantity: string; wastage_pct: string }[]>([{ component_id: '', quantity: '', wastage_pct: '0' }]);
  const [plan, setPlan] = useState({ bom_id: '', planned_qty: '', planned_date: '' });
  const [finish, setFinish] = useState<Row | null>(null);
  const [done, setDone] = useState({ produced_qty: '', batch_number: '', expiry_date: '', hold_for_qc: false });
  const [used, setUsed] = useState<Record<string, string>>({});
  const [over, setOver] = useState<{ kind: string; amount: string; pay_method: string }[]>([]);
  const [shortage, setShortage] = useState('');
  const manager = MANAGERS.includes(role);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    setError('');
    try {
      const on = (await api('/fmcg/manufacturing/settings'))?.data?.enabled === true;
      setEnabled(on);
      if (!on) return;
      const [b, o, p, r] = await Promise.all([
        api('/fmcg/manufacturing/boms'), api('/fmcg/manufacturing/orders'), api('/products'),
        api(`/fmcg/manufacturing/report?start=${iso(new Date(Date.now() - 29 * 86400000))}&end=${iso(new Date())}`),
      ]);
      setBoms(b?.data || []);
      setOrders(o?.data || []);
      setProducts(Array.isArray(p?.data) ? p.data : []);
      setReport(r?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }, []);

  useEffect(() => {
    if (manager) load();
  }, [manager, load]);

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    setError('');
    setNotice('');
    setShortage('');
    try {
      await fn();
      setNotice(ok);
      await load();
    } catch (err) {
      const msg = problem(err);
      if (/Not enough material/.test(msg)) setShortage(msg);
      else setError(msg);
    } finally {
      setBusy(false);
    }
  }
  const send = (path: string, body?: unknown, method = 'POST') => api(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  const num = (v: string) => Number(v);

  if (role && !manager) {
    return (
      <div className="fmcg-sell">
        <FmcgHead tab={tab} />
        <div className="fs-banner">Manufacturing is managed by a manager.</div>
      </div>
    );
  }

  if (enabled === false) {
    return (
      <div className="fmcg-sell">
        <FmcgHead tab={tab} />
        {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}
        <section className="fs-box">
          <p>Manufacturing is off for this company. Switch it on only if you make products from raw materials and packaging.</p>
          <button type="button" className="fs-primary" disabled={busy} onClick={() => run(() => send('/fmcg/manufacturing/settings', { enabled: true }, 'PUT'), 'Manufacturing is on.')}>Switch on manufacturing</button>
        </section>
      </div>
    );
  }

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {shortage ? <div className="fs-banner bad" role="alert">{shortage}. Buy or receive more first.</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      <section className="fs-box" aria-label="New recipe">
        <div className="fs-cardhead"><h2>New recipe</h2></div>
        <div className="fs-form">
          <label><span>Makes</span>
            <select value={recipe.product_id} onChange={(e) => setRecipe({ ...recipe, product_id: e.target.value })} aria-label="Recipe product">
              <option value="">Pick the finished product</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label><span>Recipe name</span><input value={recipe.name} onChange={(e) => setRecipe({ ...recipe, name: e.target.value })} aria-label="Recipe name" /></label>
          <label><span>Units one batch makes</span><input type="number" min="0" value={recipe.output_qty} onChange={(e) => setRecipe({ ...recipe, output_qty: e.target.value })} aria-label="Recipe output" /></label>
          <label><span>Shelf life (days)</span><input type="number" min="0" value={recipe.shelf_life_days} onChange={(e) => setRecipe({ ...recipe, shelf_life_days: e.target.value })} aria-label="Recipe shelf life" /></label>
        </div>
        {lines.map((l, i) => (
          <div className="fs-form" key={i}>
            <label><span>Material</span>
              <select value={l.component_id} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, component_id: e.target.value } : x)))} aria-label={`Material ${i + 1}`}>
                <option value="">Pick a material</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <label><span>Per batch</span><input type="number" min="0" value={l.quantity} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, quantity: e.target.value } : x)))} aria-label={`Material ${i + 1} quantity`} /></label>
            <label><span>Wastage allowed %</span><input type="number" min="0" max="100" value={l.wastage_pct} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, wastage_pct: e.target.value } : x)))} aria-label={`Material ${i + 1} wastage`} /></label>
            {lines.length > 1 ? <button type="button" onClick={() => setLines(lines.filter((_, j) => j !== i))} aria-label={`Remove material ${i + 1}`}>Remove</button> : null}
          </div>
        ))}
        <div className="fs-form">
          <button type="button" onClick={() => setLines([...lines, { component_id: '', quantity: '', wastage_pct: '0' }])}>Add material</button>
          <button type="button" className="fs-primary" disabled={busy || !recipe.product_id || recipe.name.trim().length < 2 || !(num(recipe.output_qty) > 0) || lines.some((l) => !l.component_id || !(num(l.quantity) > 0))}
            onClick={() => run(async () => {
              await send('/fmcg/manufacturing/boms', {
                product_id: recipe.product_id, name: recipe.name.trim(), output_qty: num(recipe.output_qty), ...(num(recipe.shelf_life_days) > 0 ? { shelf_life_days: num(recipe.shelf_life_days) } : {}),
                lines: lines.map((l) => ({ component_id: l.component_id, quantity: num(l.quantity), wastage_pct: num(l.wastage_pct) || 0 })),
              });
              setRecipe({ product_id: '', name: '', output_qty: '1', shelf_life_days: '' });
              setLines([{ component_id: '', quantity: '', wastage_pct: '0' }]);
            }, 'Recipe saved.')}>Save recipe</button>
        </div>
      </section>

      <section className="fs-box fs-scroll" aria-label="Recipes">
        <table>
          <thead><tr><th>Recipe</th><th>Makes</th><th>Per batch</th><th>Materials</th><th>Standard cost per unit</th><th /></tr></thead>
          <tbody>
            {boms.map((b) => (
              <tr key={b.id}>
                <td>{b.name}{b.is_active ? '' : ' (off)'}</td><td>{b.product}</td><td className="fs-num">{b.output_qty}</td>
                <td>{b.lines.map((l: Row) => `${l.component} ${l.quantity}${l.wastage_pct ? ` (+${l.wastage_pct}%)` : ''}`).join(', ')}</td>
                <td className="fs-num">{b.standard_unit_cost}</td>
                <td><button type="button" disabled={busy} aria-label={`${b.is_active ? 'Turn off' : 'Turn on'} ${b.name}`} onClick={() => run(() => send(`/fmcg/manufacturing/boms/${b.id}`, { is_active: !b.is_active }, 'PATCH'), 'Saved.')}>{b.is_active ? 'Turn off' : 'Turn on'}</button></td>
              </tr>
            ))}
            {boms.length === 0 ? <tr><td colSpan={6} className="fs-muted">No recipes yet.</td></tr> : null}
          </tbody>
        </table>
      </section>

      <section className="fs-box" aria-label="Plan production">
        <div className="fs-cardhead"><h2>Plan production</h2></div>
        <div className="fs-form">
          <label><span>Recipe</span>
            <select value={plan.bom_id} onChange={(e) => setPlan({ ...plan, bom_id: e.target.value })} aria-label="Production recipe">
              <option value="">Pick a recipe</option>{boms.filter((b) => b.is_active).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </label>
          <label><span>Units to make</span><input type="number" min="0" value={plan.planned_qty} onChange={(e) => setPlan({ ...plan, planned_qty: e.target.value })} aria-label="Units to make" /></label>
          <label><span>Date</span><input type="date" value={plan.planned_date} onChange={(e) => setPlan({ ...plan, planned_date: e.target.value })} aria-label="Production date" /></label>
          <button type="button" className="fs-primary" disabled={busy || !plan.bom_id || !(num(plan.planned_qty) > 0)}
            onClick={() => run(async () => { await send('/fmcg/manufacturing/orders', { bom_id: plan.bom_id, planned_qty: num(plan.planned_qty), ...(plan.planned_date ? { planned_date: plan.planned_date } : {}) }); setPlan({ bom_id: '', planned_qty: '', planned_date: '' }); }, 'Production planned.')}>Plan</button>
        </div>
      </section>

      {finish ? (
        <section className="fs-box" aria-label="Finish production">
          <div className="fs-cardhead"><h2>Finish {finish.order_number}: {finish.product}</h2></div>
          <div className="fs-form">
            <label><span>Units made</span><input type="number" min="0" value={done.produced_qty} onChange={(e) => setDone({ ...done, produced_qty: e.target.value })} aria-label="Units made" /></label>
            <label><span>Batch number (blank = order number)</span><input value={done.batch_number} onChange={(e) => setDone({ ...done, batch_number: e.target.value })} aria-label="Output batch number" /></label>
            <label><span>Expiry (blank = from shelf life)</span><input type="date" value={done.expiry_date} onChange={(e) => setDone({ ...done, expiry_date: e.target.value })} aria-label="Output expiry" /></label>
            <label><span>Hold for quality check</span><input type="checkbox" checked={done.hold_for_qc} onChange={(e) => setDone({ ...done, hold_for_qc: e.target.checked })} aria-label="Hold for quality check" /></label>
          </div>
          <p className="fs-muted">Material actually used (leave blank to use the recipe amount for the units made):</p>
          <div className="fs-form">
            {finish.materials_plan.map((r: Row) => (
              <label key={r.component_id}><span>{r.component} (recipe {r.needed})</span>
                <input type="number" min="0" value={used[r.component_id] ?? ''} onChange={(e) => setUsed({ ...used, [r.component_id]: e.target.value })} aria-label={`Used ${r.component}`} />
              </label>
            ))}
          </div>
          {over.map((o, i) => (
            <div className="fs-form" key={i}>
              <label><span>Cost</span><select value={o.kind} onChange={(e) => setOver(over.map((x, j) => (j === i ? { ...x, kind: e.target.value } : x)))} aria-label={`Overhead ${i + 1} kind`}>{OVERHEADS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select></label>
              <label><span>Amount</span><input type="number" min="0" value={o.amount} onChange={(e) => setOver(over.map((x, j) => (j === i ? { ...x, amount: e.target.value } : x)))} aria-label={`Overhead ${i + 1} amount`} /></label>
              <label><span>How paid</span><select value={o.pay_method} onChange={(e) => setOver(over.map((x, j) => (j === i ? { ...x, pay_method: e.target.value } : x)))} aria-label={`Overhead ${i + 1} payment`}>{METHODS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select></label>
              <button type="button" onClick={() => setOver(over.filter((_, j) => j !== i))} aria-label={`Remove overhead ${i + 1}`}>Remove</button>
            </div>
          ))}
          <div className="fs-form">
            <button type="button" onClick={() => setOver([...over, { kind: 'labour', amount: '', pay_method: 'payable' }])}>Add a cost (labour, power...)</button>
            <button type="button" className="fs-primary" disabled={busy || !(num(done.produced_qty) > 0) || over.some((o) => !(num(o.amount) > 0))}
              onClick={() => run(async () => {
                await send(`/fmcg/manufacturing/orders/${finish.id}/complete`, {
                  produced_qty: num(done.produced_qty), hold_for_qc: done.hold_for_qc,
                  ...(done.batch_number.trim().length >= 2 ? { batch_number: done.batch_number.trim() } : {}), ...(done.expiry_date ? { expiry_date: done.expiry_date } : {}),
                  materials: Object.entries(used).filter(([, v]) => v !== '').map(([component_id, v]) => ({ component_id, actual_qty: num(v) })),
                  overheads: over.map((o) => ({ kind: o.kind, amount: num(o.amount), pay_method: o.pay_method })),
                });
                setFinish(null); setUsed({}); setOver([]); setDone({ produced_qty: '', batch_number: '', expiry_date: '', hold_for_qc: false });
              }, 'Production completed.')}>Finish production</button>
            <button type="button" disabled={busy} onClick={() => setFinish(null)}>Cancel</button>
          </div>
        </section>
      ) : null}

      <section className="fs-box fs-scroll" aria-label="Production orders">
        <table>
          <thead><tr><th>No.</th><th>Product</th><th>Status</th><th>Planned</th><th>Made</th><th>Batch</th><th>Unit cost</th><th>Wastage</th><th /></tr></thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id}>
                <td>{o.order_number}</td><td>{o.product}</td><td>{o.status === 'completed' ? STATUS_WORDS.completed : <span className="fs-flag">{STATUS_WORDS[o.status]}</span>}</td>
                <td className="fs-num">{o.planned_qty}</td><td className="fs-num">{o.produced_qty ?? '-'}</td><td>{o.batch_number || '-'}{o.held_for_qc ? ' (held)' : ''}</td>
                <td className="fs-num">{o.unit_cost ?? '-'}</td><td className="fs-num">{o.wastage_pct != null ? `${o.wastage_pct}%` : '-'}</td>
                <td>
                  {o.status === 'planned' ? <button type="button" disabled={busy} aria-label={`Start ${o.order_number}`} onClick={() => run(() => send(`/fmcg/manufacturing/orders/${o.id}/start`), 'Production started.')}>Start</button> : null}{' '}
                  {o.status === 'in_progress' ? <button type="button" aria-label={`Finish ${o.order_number}`} onClick={async () => { const c = (await api(`/fmcg/manufacturing/orders/${o.id}/check`))?.data; setFinish({ ...o, materials_plan: c?.materials || [] }); setDone({ ...done, produced_qty: String(o.planned_qty) }); }}>Finish</button> : null}{' '}
                  {(o.status === 'planned' || o.status === 'in_progress') ? <button type="button" className="fs-danger" disabled={busy} aria-label={`Cancel ${o.order_number}`} onClick={() => { const why = window.prompt('Why is this cancelled?'); if (why && why.trim().length >= 3) run(() => send(`/fmcg/manufacturing/orders/${o.id}/cancel`, { reason: why.trim() }), 'Cancelled.'); }}>Cancel</button> : null}
                </td>
              </tr>
            ))}
            {orders.length === 0 ? <tr><td colSpan={9} className="fs-muted">No production orders yet.</td></tr> : null}
          </tbody>
        </table>
      </section>

      {report && report.by_product.length ? (
        <section className="fs-box fs-scroll" aria-label="Production summary">
          <div className="fs-cardhead"><h2>Last 30 days</h2></div>
          <table>
            <thead><tr><th>Product</th><th>Orders</th><th>Made</th><th>Cost</th><th>Average unit cost</th></tr></thead>
            <tbody>{report.by_product.map((g: Row) => <tr key={g.product}><td>{g.product}</td><td className="fs-num">{g.orders}</td><td className="fs-num">{g.produced}</td><td className="fs-num">{formatMoney(g.cost)}</td><td className="fs-num">{g.average_unit_cost}</td></tr>)}</tbody>
          </table>
          <p className="fs-muted">{report.note}</p>
        </section>
      ) : null}
    </div>
  );
}
