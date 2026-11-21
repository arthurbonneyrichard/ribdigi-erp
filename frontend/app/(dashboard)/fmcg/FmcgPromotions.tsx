'use client';

/**
 * FMCG promotions: create a deal with a budget, a use limit and the outlets it is for, get it
 * approved by a second person when it is risky, and see what it cost and earned. The server
 * decides which promotion applies to an order line; this screen only sets them up and shows them.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const PROMO_TABS = ['promotions'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin'];
const TYPES = [
  { id: 'percent', label: 'Percent off' },
  { id: 'fixed', label: 'Fixed amount off' },
  { id: 'bxgy', label: 'Buy X get Y' },
];
const STATUS_WORDS: Record<string, string> = { approved: 'Running', pending: 'Waiting for approval', rejected: 'Rejected' };
const KIND_WORDS: Record<string, string> = { customer: 'Outlet', route: 'Route', territory: 'Territory' };

const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const num = (v: string) => (v.trim() === '' ? undefined : Number(v));

export default function FmcgPromotions({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [promos, setPromos] = useState<Row[]>([]);
  const [policy, setPolicy] = useState({ approval_percent: '30', approval_budget: '0' });
  const [products, setProducts] = useState<Row[]>([]);
  const [outlets, setOutlets] = useState<Row[]>([]);
  const [routes, setRoutes] = useState<Row[]>([]);
  const [territories, setTerritories] = useState<Row[]>([]);
  const blank = { code: '', name: '', scheme_type: 'percent', value: '', buy_qty: '', get_qty: '', product_id: '', starts_on: '', ends_on: '', budget: '', max_uses: '', min_qty: '', notes: '' };
  const [form, setForm] = useState(blank);
  const [targets, setTargets] = useState<{ kind: string; ref_id: string }[]>([]);
  const [targetKind, setTargetKind] = useState('route');
  const [targetRef, setTargetRef] = useState('');
  const [rejecting, setRejecting] = useState<Row | null>(null);
  const [why, setWhy] = useState('');
  const [perf, setPerf] = useState<Row | null>(null);
  const manager = MANAGERS.includes(role);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    setError('');
    try {
      const [p, pol, prod, o, r, t] = await Promise.all([
        api('/fmcg/promotions'), api('/fmcg/promotions/policy'), api('/products'), api('/fmcg/outlets'),
        api('/fmcg/routes'), api('/fmcg/territories'),
      ]);
      setPromos(p?.data || []);
      setPolicy({ approval_percent: String(pol?.data?.approval_percent ?? 30), approval_budget: String(pol?.data?.approval_budget ?? 0) });
      setProducts(Array.isArray(prod?.data) ? prod.data : []);
      setOutlets(o?.data || []);
      setRoutes(r?.data || []);
      setTerritories(t?.data || []);
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
  const post = (path: string, body?: unknown, method = 'POST') =>
    api(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

  const options = targetKind === 'customer' ? outlets : targetKind === 'route' ? routes : territories;
  const nameOf = (t: { kind: string; ref_id: string }) =>
    (t.kind === 'customer' ? outlets : t.kind === 'route' ? routes : territories).find((x) => x.id === t.ref_id)?.name || t.ref_id.slice(0, 8);

  const save = () =>
    run(async () => {
      const body: Row = {
        code: form.code.trim(), name: form.name.trim(), scheme_type: form.scheme_type, targets,
        ...(form.scheme_type === 'bxgy' ? { buy_qty: Number(form.buy_qty), get_qty: Number(form.get_qty) } : { value: Number(form.value) }),
      };
      if (form.product_id) body.product_id = form.product_id;
      if (form.starts_on) body.starts_on = form.starts_on;
      if (form.ends_on) body.ends_on = form.ends_on;
      if (num(form.budget) !== undefined) body.budget = num(form.budget);
      if (num(form.max_uses) !== undefined) body.max_uses = num(form.max_uses);
      if (num(form.min_qty) !== undefined) body.min_qty = num(form.min_qty);
      if (form.notes.trim().length >= 3) body.notes = form.notes.trim();
      await post('/fmcg/promotions', body);
      setForm(blank);
      setTargets([]);
    }, 'Promotion saved.');

  async function showPerf(id: string) {
    try {
      setPerf((await api(`/fmcg/promotions/${id}/performance`))?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }

  if (role && !manager) {
    return (
      <div className="fmcg-sell">
        <FmcgHead tab={tab} />
        <div className="fs-banner">Promotions are managed by a manager.</div>
      </div>
    );
  }

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      <section className="fs-box" aria-label="Approval rules">
        <div className="fs-cardhead"><h2>When a second person must approve</h2></div>
        <div className="fs-form">
          <label><span>Percent off above (%)</span><input type="number" min="0" max="100" value={policy.approval_percent} onChange={(e) => setPolicy({ ...policy, approval_percent: e.target.value })} aria-label="Approval percent limit" /></label>
          <label><span>Budget above (0 = no rule)</span><input type="number" min="0" value={policy.approval_budget} onChange={(e) => setPolicy({ ...policy, approval_budget: e.target.value })} aria-label="Approval budget limit" /></label>
          <button type="button" disabled={busy} onClick={() => run(() => post('/fmcg/promotions/policy', { approval_percent: Number(policy.approval_percent), approval_budget: Number(policy.approval_budget) }, 'PUT'), 'Rules saved.')}>Save rules</button>
        </div>
      </section>

      <section className="fs-box" aria-label="New promotion">
        <div className="fs-cardhead"><h2>New promotion</h2></div>
        <div className="fs-form">
          <label><span>Code</span><input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} aria-label="Promotion code" /></label>
          <label><span>Name</span><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} aria-label="Promotion name" /></label>
          <label><span>Kind</span>
            <select value={form.scheme_type} onChange={(e) => setForm({ ...form, scheme_type: e.target.value })} aria-label="Promotion kind">
              {TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
            </select>
          </label>
          {form.scheme_type === 'bxgy' ? (
            <>
              <label><span>Buy</span><input type="number" min="1" value={form.buy_qty} onChange={(e) => setForm({ ...form, buy_qty: e.target.value })} aria-label="Promotion buy quantity" /></label>
              <label><span>Get</span><input type="number" min="1" value={form.get_qty} onChange={(e) => setForm({ ...form, get_qty: e.target.value })} aria-label="Promotion get quantity" /></label>
            </>
          ) : (
            <label><span>{form.scheme_type === 'percent' ? 'Percent' : 'Amount off'}</span><input type="number" min="0" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} aria-label="Promotion value" /></label>
          )}
          <label><span>Product (blank = all)</span>
            <select value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value })} aria-label="Promotion product">
              <option value="">All products</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label><span>Starts</span><input type="date" value={form.starts_on} onChange={(e) => setForm({ ...form, starts_on: e.target.value })} aria-label="Promotion start date" /></label>
          <label><span>Ends</span><input type="date" value={form.ends_on} onChange={(e) => setForm({ ...form, ends_on: e.target.value })} aria-label="Promotion end date" /></label>
          <label><span>Budget (most it may cost)</span><input type="number" min="0" value={form.budget} onChange={(e) => setForm({ ...form, budget: e.target.value })} aria-label="Promotion budget" /></label>
          <label><span>Most times used</span><input type="number" min="1" value={form.max_uses} onChange={(e) => setForm({ ...form, max_uses: e.target.value })} aria-label="Promotion use limit" /></label>
          <label><span>Smallest quantity</span><input type="number" min="0" value={form.min_qty} onChange={(e) => setForm({ ...form, min_qty: e.target.value })} aria-label="Promotion minimum quantity" /></label>
          <label><span>Notes</span><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} aria-label="Promotion notes" /></label>
        </div>
        <fieldset className="fs-pick">
          <legend>Who it is for (leave empty for every outlet)</legend>
          <div className="fs-form">
            <label><span>Kind</span>
              <select value={targetKind} onChange={(e) => { setTargetKind(e.target.value); setTargetRef(''); }} aria-label="Promotion target kind">
                {Object.entries(KIND_WORDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label><span>Pick</span>
              <select value={targetRef} onChange={(e) => setTargetRef(e.target.value)} aria-label="Promotion target">
                <option value="">Choose</option>{options.map((o: Row) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </label>
            <button type="button" disabled={!targetRef || targets.some((t) => t.kind === targetKind && t.ref_id === targetRef)} onClick={() => { setTargets([...targets, { kind: targetKind, ref_id: targetRef }]); setTargetRef(''); }}>Add</button>
          </div>
          {targets.map((t) => (
            <span key={`${t.kind}${t.ref_id}`} className="fs-flag">{KIND_WORDS[t.kind]}: {nameOf(t)} <button type="button" aria-label={`Remove ${nameOf(t)}`} onClick={() => setTargets(targets.filter((x) => x !== t))}>x</button></span>
          ))}
        </fieldset>
        <button type="button" className="fs-primary" disabled={busy || form.code.trim().length < 2 || form.name.trim().length < 2 || (form.scheme_type === 'bxgy' ? !(Number(form.buy_qty) >= 1 && Number(form.get_qty) >= 1) : !(Number(form.value) > 0))} onClick={save}>Save promotion</button>
        <p className="fs-muted">Only the best single promotion applies to a line, so deals never stack. Buy X get Y is given as a price reduction equal to the free units.</p>
      </section>

      {rejecting ? (
        <section className="fs-box" aria-label="Reject promotion">
          <div className="fs-cardhead"><h2>Reject {rejecting.code}</h2></div>
          <div className="fs-form">
            <label><span>Why</span><input value={why} onChange={(e) => setWhy(e.target.value)} aria-label="Rejection reason" /></label>
            <button type="button" className="fs-danger" disabled={busy || why.trim().length < 3} onClick={() => run(async () => { await post(`/fmcg/promotions/${rejecting.id}/reject`, { reason: why.trim() }); setRejecting(null); setWhy(''); }, 'Rejected.')}>Reject</button>
            <button type="button" disabled={busy} onClick={() => setRejecting(null)}>Cancel</button>
          </div>
        </section>
      ) : null}

      <section className="fs-box fs-scroll" aria-label="Promotions">
        <table>
          <thead><tr><th>Code</th><th>Name</th><th>Deal</th><th>Status</th><th>Spent / budget</th><th>Uses</th><th>For</th><th /></tr></thead>
          <tbody>
            {promos.map((p) => (
              <tr key={p.id}>
                <td>{p.code}</td><td>{p.name}</td>
                <td>{p.scheme_type === 'percent' ? `${p.value}% off` : p.scheme_type === 'fixed' ? `${formatMoney(p.value)} off` : `Buy ${p.buy_qty} get ${p.get_qty}`}</td>
                <td>{p.status === 'approved' ? (p.is_active ? STATUS_WORDS.approved : 'Stopped') : <span className="fs-flag">{STATUS_WORDS[p.status]}</span>}</td>
                <td className="fs-num">{formatMoney(p.spent)}{p.budget != null ? ` / ${formatMoney(p.budget)}` : ''}</td>
                <td className="fs-num">{p.uses}{p.max_uses != null ? ` / ${p.max_uses}` : ''}</td>
                <td>{p.targets.length ? p.targets.map((t: Row) => t.name || t.kind).join(', ') : 'Everyone'}</td>
                <td>
                  {p.status === 'pending' ? (
                    <>
                      <button type="button" className="fs-primary" disabled={busy} aria-label={`Approve ${p.code}`} onClick={() => run(() => post(`/fmcg/promotions/${p.id}/approve`), 'Approved.')}>Approve</button>{' '}
                      <button type="button" className="fs-danger" disabled={busy} aria-label={`Reject ${p.code}`} onClick={() => setRejecting(p)}>Reject</button>{' '}
                    </>
                  ) : null}
                  {p.status === 'approved' ? <button type="button" disabled={busy} aria-label={`${p.is_active ? 'Stop' : 'Restart'} ${p.code}`} onClick={() => run(() => post(`/fmcg/schemes/${p.id}`, { is_active: !p.is_active }, 'PATCH'), p.is_active ? 'Stopped.' : 'Running again.')}>{p.is_active ? 'Stop' : 'Restart'}</button> : null}{' '}
                  <button type="button" aria-label={`Results for ${p.code}`} onClick={() => showPerf(p.id)}>Results</button>
                </td>
              </tr>
            ))}
            {promos.length === 0 ? <tr><td colSpan={8} className="fs-muted">No promotions yet.</td></tr> : null}
          </tbody>
        </table>
      </section>

      {perf ? (
        <section className="fs-box" aria-label="Promotion results">
          <div className="fs-cardhead"><h2>Results: {perf.scheme.code} · {perf.scheme.name}</h2></div>
          <p>Booked so far: {perf.committed.lines} lines, {formatMoney(perf.committed.discount)} of discount.</p>
          <p>
            Delivered: {perf.delivered.units} units to {perf.delivered.outlets} outlets · discount given {formatMoney(perf.delivered.discount_given)} ·
            sales after discount {formatMoney(perf.delivered.revenue_after_discount)} · cost of goods {formatMoney(perf.delivered.cost_of_goods)} ·{' '}
            <strong>profit {formatMoney(perf.delivered.gross_profit)}{perf.delivered.margin_pct != null ? ` (${perf.delivered.margin_pct}%)` : ''}</strong>
          </p>
          {perf.budget_used_pct != null ? <p>Budget used: {perf.budget_used_pct}%</p> : null}
          <p className="fs-muted">{perf.note}</p>
        </section>
      ) : null}
    </div>
  );
}
