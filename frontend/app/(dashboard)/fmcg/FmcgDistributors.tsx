'use client';

/**
 * FMCG distributors: trade terms on an outlet (kind, price tier, monthly target), a ranking that
 * shows who needs attention, and a statement and performance view for each. The numbers all come
 * from the same delivered orders, payments and returns as the rest of FMCG.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const DISTRIBUTOR_TABS = ['distributors'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin'];
const KINDS = [{ id: 'distributor', label: 'Distributor' }, { id: 'wholesaler', label: 'Wholesaler' }, { id: 'key_account', label: 'Key account' }, { id: 'supermarket', label: 'Supermarket' }];
const FLAG_WORDS: Record<string, string> = {
  behind_target: 'Behind target', sales_falling: 'Sales falling', paying_late: 'Paying late', over_credit_limit: 'Over credit limit', no_orders: 'No orders',
};
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export default function FmcgDistributors({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [list, setList] = useState<Row[]>([]);
  const [rank, setRank] = useState<Row[]>([]);
  const [outlets, setOutlets] = useState<Row[]>([]);
  const [territories, setTerritories] = useState<Row[]>([]);
  const [form, setForm] = useState({ customer_id: '', kind: 'distributor', price_discount_pct: '0', monthly_target: '', territory_id: '' });
  const [period, setPeriod] = useState({ start: iso(new Date(new Date().getFullYear(), new Date().getMonth(), 1)), end: iso(new Date()) });
  const [openId, setOpenId] = useState('');
  const [perf, setPerf] = useState<Row | null>(null);
  const [statement, setStatement] = useState<Row | null>(null);
  const [edit, setEdit] = useState<Row | null>(null);
  const manager = MANAGERS.includes(role);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    setError('');
    try {
      const q = `start=${period.start}&end=${period.end}`;
      const [d, r, o, t] = await Promise.all([api('/fmcg/distributors'), api(`/fmcg/distributors/ranking?${q}`), api('/fmcg/outlets'), api('/fmcg/territories').catch(() => null)]);
      setList(d?.data || []);
      setRank(r?.data || []);
      setOutlets(o?.data || []);
      setTerritories(Array.isArray(t?.data) ? t.data : []);
    } catch (err) {
      setError(problem(err));
    }
  }, [period.start, period.end]);

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
  const send = (path: string, body: unknown, method = 'POST') => api(path, { method, body: JSON.stringify(body) });

  async function openDistributor(id: string) {
    setOpenId(id);
    try {
      const q = `start=${period.start}&end=${period.end}`;
      const [p, s] = await Promise.all([api(`/fmcg/distributors/${id}/performance?${q}`), api(`/fmcg/distributors/${id}/statement?${q}`)]);
      setPerf(p?.data || null);
      setStatement(s?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }

  if (role && !manager) {
    return (
      <div className="fmcg-sell">
        <FmcgHead tab={tab} />
        <div className="fs-banner">Distributors are managed by a manager.</div>
      </div>
    );
  }

  const taken = new Set(list.map((d) => d.customer_id));

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      <section className="fs-box" aria-label="Period">
        <div className="fs-form">
          <label><span>From</span><input type="date" value={period.start} onChange={(e) => setPeriod({ ...period, start: e.target.value })} aria-label="Distributor period from" /></label>
          <label><span>To</span><input type="date" value={period.end} onChange={(e) => setPeriod({ ...period, end: e.target.value })} aria-label="Distributor period to" /></label>
        </div>
      </section>

      <section className="fs-box fs-scroll" aria-label="Who needs attention">
        <div className="fs-cardhead"><h2>Who needs attention</h2></div>
        <table>
          <thead><tr><th>Distributor</th><th>Sales</th><th>vs target</th><th>vs before</th><th>Owed late</th><th>Flags</th><th /></tr></thead>
          <tbody>
            {rank.map((r) => (
              <tr key={r.distributor_id}>
                <td>{r.distributor}</td><td className="fs-num">{formatMoney(r.net_sales)}</td>
                <td className="fs-num">{r.target_pct != null ? `${r.target_pct}%` : '-'}</td><td className="fs-num">{r.growth_pct != null ? `${r.growth_pct}%` : '-'}</td>
                <td className="fs-num">{formatMoney(r.owed_late)}</td>
                <td>{r.flags.length ? r.flags.map((f: string) => <span key={f} className="fs-flag">{FLAG_WORDS[f]}</span>) : 'On track'}</td>
                <td><button type="button" aria-label={`Open ${r.distributor}`} onClick={() => openDistributor(r.distributor_id)}>Open</button></td>
              </tr>
            ))}
            {rank.length === 0 ? <tr><td colSpan={7} className="fs-muted">No distributors yet. Add one below.</td></tr> : null}
          </tbody>
        </table>
        <p className="fs-muted">Flags: under 70% of target, sales down 20% or more on the period before, 30% or more of what they owe is late, over the credit limit, or no orders.</p>
      </section>

      <section className="fs-box" aria-label="Add a distributor">
        <div className="fs-cardhead"><h2>{edit ? `Change ${edit.name}` : 'Add a distributor'}</h2></div>
        <div className="fs-form">
          {!edit ? (
            <label><span>Outlet</span>
              <select value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })} aria-label="Distributor outlet">
                <option value="">Pick an outlet</option>{outlets.filter((o) => !taken.has(o.id)).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </label>
          ) : null}
          <label><span>Kind</span>
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} aria-label="Distributor kind">{KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select>
          </label>
          <label><span>Price off list (%)</span><input type="number" min="0" max="50" value={form.price_discount_pct} onChange={(e) => setForm({ ...form, price_discount_pct: e.target.value })} aria-label="Price tier discount" /></label>
          <label><span>Monthly target</span><input type="number" min="0" value={form.monthly_target} onChange={(e) => setForm({ ...form, monthly_target: e.target.value })} aria-label="Monthly target" /></label>
          <label><span>Territory</span>
            <select value={form.territory_id} onChange={(e) => setForm({ ...form, territory_id: e.target.value })} aria-label="Distributor territory">
              <option value="">None</option>{territories.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
          <button type="button" className="fs-primary" disabled={busy || (!edit && !form.customer_id)}
            onClick={() => run(async () => {
              const body: Row = { kind: form.kind, price_discount_pct: Number(form.price_discount_pct) || 0, ...(form.monthly_target !== '' ? { monthly_target: Number(form.monthly_target) } : {}), ...(form.territory_id ? { territory_id: form.territory_id } : {}) };
              if (edit) await send(`/fmcg/distributors/${edit.id}`, body, 'PATCH');
              else await send('/fmcg/distributors', { customer_id: form.customer_id, ...body });
              setEdit(null);
              setForm({ customer_id: '', kind: 'distributor', price_discount_pct: '0', monthly_target: '', territory_id: '' });
            }, 'Saved.')}>{edit ? 'Save changes' : 'Add distributor'}</button>
          {edit ? <button type="button" onClick={() => { setEdit(null); setForm({ customer_id: '', kind: 'distributor', price_discount_pct: '0', monthly_target: '', territory_id: '' }); }}>Cancel</button> : null}
        </div>
        <p className="fs-muted">The price off list is taken off every product for this outlet before any promotion, so a distributor always sees their own price on the order.</p>
      </section>

      <section className="fs-box fs-scroll" aria-label="Distributors">
        <table>
          <thead><tr><th>Name</th><th>Kind</th><th>Price off</th><th>Target</th><th>This month</th><th>Owes</th><th>Credit limit</th><th>Last order</th><th /></tr></thead>
          <tbody>
            {list.map((d) => (
              <tr key={d.id}>
                <td>{d.name}{d.is_active ? '' : ' (off)'}</td><td>{KINDS.find((k) => k.id === d.kind)?.label}</td><td className="fs-num">{d.price_discount_pct}%</td>
                <td className="fs-num">{d.monthly_target != null ? formatMoney(d.monthly_target) : '-'}</td>
                <td className="fs-num">{formatMoney(d.sales_this_month)}{d.target_pct != null ? ` (${d.target_pct}%)` : ''}</td>
                <td className="fs-num">{d.over_limit ? <span className="fs-flag">{formatMoney(d.balance)}</span> : formatMoney(d.balance)}</td>
                <td className="fs-num">{formatMoney(d.credit_limit)}</td><td>{d.last_order || '-'}</td>
                <td>
                  <button type="button" aria-label={`Change ${d.name}`} onClick={() => { setEdit(d); setForm({ customer_id: d.customer_id, kind: d.kind, price_discount_pct: String(d.price_discount_pct), monthly_target: d.monthly_target != null ? String(d.monthly_target) : '', territory_id: d.territory_id || '' }); }}>Change</button>{' '}
                  <button type="button" disabled={busy} aria-label={`${d.is_active ? 'Switch off' : 'Switch on'} ${d.name}`} onClick={() => run(() => send(`/fmcg/distributors/${d.id}`, { is_active: !d.is_active }, 'PATCH'), 'Saved.')}>{d.is_active ? 'Switch off' : 'Switch on'}</button>
                </td>
              </tr>
            ))}
            {list.length === 0 ? <tr><td colSpan={9} className="fs-muted">None yet.</td></tr> : null}
          </tbody>
        </table>
      </section>

      {openId && perf ? (
        <section className="fs-box fs-scroll" aria-label="Distributor detail">
          <div className="fs-cardhead"><h2>{perf.distributor}: {perf.period.start} to {perf.period.end}</h2></div>
          <p>
            {perf.orders} orders · net sales {formatMoney(perf.net_sales)} · returns {formatMoney(perf.returns)} ({perf.return_rate_pct}%) · gross profit {formatMoney(perf.gross_profit)}
            {perf.margin_pct != null ? ` (${perf.margin_pct}%)` : ''} · collected {formatMoney(perf.collected)}{perf.collection_rate_pct != null ? ` (${perf.collection_rate_pct}% of deliveries)` : ''}
          </p>
          <p>Owes {formatMoney(perf.owed)}, of which {formatMoney(perf.owed_late)} is late. Before this period: {formatMoney(perf.previous_period_sales)}{perf.target != null ? ` · target for the period ${formatMoney(perf.target)}` : ''}.</p>
          {perf.top_products.length ? <p>Top products: {perf.top_products.map((p: Row) => `${p.product} (${p.units})`).join(', ')}</p> : null}
          <p className="fs-muted">{perf.note}</p>
          {statement ? (
            <>
              <div className="fs-cardhead"><h2>Statement</h2></div>
              <table>
                <thead><tr><th>Date</th><th>What</th><th>Reference</th><th>Debit</th><th>Credit</th><th>Balance</th></tr></thead>
                <tbody>
                  <tr><td colSpan={5}>Opening balance</td><td className="fs-num">{formatMoney(statement.opening_balance)}</td></tr>
                  {statement.lines.map((l: Row, i: number) => <tr key={i}><td>{l.date}</td><td>{l.kind}</td><td>{l.reference}</td><td className="fs-num">{l.debit ? formatMoney(l.debit) : ''}</td><td className="fs-num">{l.credit ? formatMoney(l.credit) : ''}</td><td className="fs-num">{formatMoney(l.balance)}</td></tr>)}
                  <tr><td colSpan={5}><strong>Closing balance</strong></td><td className="fs-num"><strong>{formatMoney(statement.closing_balance)}</strong></td></tr>
                </tbody>
              </table>
              <p className="fs-muted">{statement.note}</p>
            </>
          ) : null}
          <button type="button" onClick={() => window.print()} aria-label="Print statement">Print</button>
        </section>
      ) : null}
    </div>
  );
}
