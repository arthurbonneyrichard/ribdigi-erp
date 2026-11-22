'use client';

/**
 * FMCG batches and recalls. Managers watch expiry, put a batch on hold, write off bad stock and
 * run a product recall that names every outlet that received the batch. All rules (FEFO,
 * blocking expired stock, journals) live on the server; this screen only asks and shows.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const BATCH_TABS = ['batches', 'recalls'];
const FULL = ['company_admin', 'fmcg_manager', 'super_admin'];
const MANAGERS = [...FULL, 'fmcg_storekeeper', 'fmcg_quality'];
const STATE_WORDS: Record<string, string> = { ok: 'Good', near: 'Expiring soon', expired: 'Expired', held: 'On hold' };
const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'near', label: 'Expiring soon' },
  { id: 'expired', label: 'Expired' },
  { id: 'held', label: 'On hold' },
];
const REASONS = [
  { id: 'expiry', label: 'Expired' },
  { id: 'damage', label: 'Damaged' },
  { id: 'recall', label: 'Recalled' },
  { id: 'other', label: 'Other loss' },
];

const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';

export default function FmcgBatches({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [data, setData] = useState<Row | null>(null);
  const [warn, setWarn] = useState('');
  const [action, setAction] = useState<{ kind: 'hold' | 'writeoff'; batch: Row } | null>(null);
  const [text, setText] = useState('');
  const [qty, setQty] = useState('');
  const [code, setCode] = useState('expiry');
  const [picked, setPicked] = useState<string[]>([]);
  const [recalls, setRecalls] = useState<Row[]>([]);
  const [open, setOpen] = useState<Row | null>(null);
  const [form, setForm] = useState({ title: '', reason: '' });
  const [back, setBack] = useState<Record<string, string>>({});
  const manager = MANAGERS.includes(role);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    setError('');
    try {
      if (tab === 'batches') {
        const res = await api(`/fmcg/batches?status=${filter}${search.trim() ? `&q=${encodeURIComponent(search.trim())}` : ''}`);
        setData(res?.data || null);
        setWarn((res?.data?.policy?.warn_days || []).join(', '));
      } else {
        const [r, b] = await Promise.all([api('/fmcg/recalls'), api('/fmcg/batches?status=all')]);
        setRecalls(r?.data || []);
        setData(b?.data || null);
      }
    } catch (err) {
      setError(problem(err));
    }
  }, [tab, filter, search]);

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
      setAction(null);
      setText('');
      setQty('');
      await load();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  const post = (path: string, body?: unknown, method = 'POST') =>
    api(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

  const savePolicy = () =>
    run(async () => {
      const days = warn.split(',').map((x) => Number(x.trim())).filter((x) => x > 0);
      await post('/fmcg/batch-policy', { warn_days: days }, 'PUT');
    }, 'Warning periods saved.');

  const submitAction = () =>
    run(async () => {
      if (!action) return;
      if (action.kind === 'hold') await post(`/fmcg/batches/${action.batch.id}/hold`, { reason: text.trim() });
      else await post(`/fmcg/batches/${action.batch.id}/write-off`, { quantity: Number(qty), reason_code: code, reason: text.trim() });
    }, action?.kind === 'hold' ? 'Batch put on hold.' : 'Stock written off.');

  const openRecall = () =>
    run(async () => {
      await post('/fmcg/recalls', { title: form.title.trim(), reason: form.reason.trim(), batch_ids: picked });
      setForm({ title: '', reason: '' });
      setPicked([]);
    }, 'Recall opened. Those batches are blocked.');

  async function showRecall(id: string) {
    try {
      setOpen((await api(`/fmcg/recalls/${id}`))?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }

  if (role && (!manager || (tab === 'recalls' && !FULL.includes(role)))) {
    return (
      <div className="fmcg-sell">
        <FmcgHead tab={tab} />
        <div className="fs-banner">Batches and recalls are managed by a manager.</div>
      </div>
    );
  }

  const batches: Row[] = data?.batches || [];
  const counts: Row = data?.counts || {};

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      {tab === 'batches' ? (
        <>
          <section className="fs-box" aria-label="Batch summary">
            <div className="fs-form">
              {['ok', 'near', 'expired', 'held'].map((k) => (
                <span key={k}><strong>{counts[k] ?? 0}</strong> {STATE_WORDS[k].toLowerCase()}</span>
              ))}
            </div>
            <div className="fs-form">
              <label><span>Warn me this many days before expiry</span>
                <input value={warn} onChange={(e) => setWarn(e.target.value)} aria-label="Expiry warning days" placeholder="90, 60, 30, 14, 7" />
              </label>
              <button type="button" disabled={busy} onClick={savePolicy}>Save warning days</button>
            </div>
          </section>

          <section className="fs-box" aria-label="Batch filters">
            <div className="fs-form">
              {FILTERS.map((f) => (
                <button key={f.id} type="button" className={filter === f.id ? 'fs-primary' : ''} onClick={() => setFilter(f.id)} aria-label={`Show ${f.label} batches`}>{f.label}</button>
              ))}
              <label><span>Search</span><input value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search batches" placeholder="Product or batch" /></label>
            </div>
          </section>

          {action ? (
            <section className="fs-box" aria-label="Batch action">
              <div className="fs-cardhead"><h2>{action.kind === 'hold' ? 'Put on hold' : 'Write off'}: {action.batch.product_name} · {action.batch.batch_number}</h2></div>
              <div className="fs-form">
                {action.kind === 'writeoff' ? (
                  <>
                    <label><span>Quantity (max {action.batch.quantity})</span><input type="number" min="0" value={qty} onChange={(e) => setQty(e.target.value)} aria-label="Write-off quantity" /></label>
                    <label><span>Why</span>
                      <select value={code} onChange={(e) => setCode(e.target.value)} aria-label="Write-off reason type">
                        {REASONS.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
                      </select>
                    </label>
                  </>
                ) : null}
                <label><span>Reason (shown in the audit trail)</span><input value={text} onChange={(e) => setText(e.target.value)} aria-label="Batch action reason" /></label>
                <button type="button" className="fs-primary" disabled={busy || text.trim().length < 3 || (action.kind === 'writeoff' && !(Number(qty) > 0))} onClick={submitAction}>Confirm</button>
                <button type="button" disabled={busy} onClick={() => setAction(null)}>Cancel</button>
              </div>
            </section>
          ) : null}

          <section className="fs-box fs-scroll" aria-label="Batches">
            <table>
              <thead><tr><th>Product</th><th>Batch</th><th>Qty</th><th>Expires</th><th>Days left</th><th>Status</th><th>Value at cost</th><th /></tr></thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.id}>
                    <td>{b.product_name}</td><td>{b.batch_number}</td><td className="fs-num">{b.quantity}</td>
                    <td>{b.expiry_date || '-'}</td><td className="fs-num">{b.days_to_expiry ?? '-'}</td>
                    <td>{b.state === 'ok' ? STATE_WORDS.ok : <span className="fs-flag">{STATE_WORDS[b.state]}</span>}</td>
                    <td className="fs-num">{formatMoney(b.value_at_cost)}</td>
                    <td>
                      {b.state === 'held' ? (
                        <button type="button" disabled={busy} aria-label={`Release batch ${b.batch_number}`} onClick={() => run(() => post(`/fmcg/batches/${b.id}/release`), 'Batch released.')}>Release</button>
                      ) : (
                        <button type="button" disabled={busy} aria-label={`Hold batch ${b.batch_number}`} onClick={() => { setAction({ kind: 'hold', batch: b }); setText(''); }}>Hold</button>
                      )}{' '}
                      {FULL.includes(role) ? <button type="button" className="fs-danger" disabled={busy} aria-label={`Write off batch ${b.batch_number}`} onClick={() => { setAction({ kind: 'writeoff', batch: b }); setCode(b.state === 'expired' ? 'expiry' : 'damage'); setText(''); }}>Write off</button> : null}
                    </td>
                  </tr>
                ))}
                {batches.length === 0 ? <tr><td colSpan={8} className="fs-muted">No batches here. Batches appear when goods with a batch number and expiry date are received.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'recalls' ? (
        <>
          <section className="fs-box" aria-label="Open a recall">
            <div className="fs-cardhead"><h2>Open a recall</h2></div>
            <div className="fs-form">
              <label><span>Title</span><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} aria-label="Recall title" /></label>
              <label><span>Reason</span><input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} aria-label="Recall reason" /></label>
            </div>
            <fieldset className="fs-pick">
              <legend>Batches to recall</legend>
              {(data?.batches || []).map((b: Row) => (
                <label key={b.id}>
                  <input type="checkbox" checked={picked.includes(b.id)} aria-label={`Recall batch ${b.batch_number}`}
                    onChange={() => setPicked(picked.includes(b.id) ? picked.filter((x) => x !== b.id) : [...picked, b.id])} />
                  {b.product_name} · {b.batch_number}
                </label>
              ))}
            </fieldset>
            <p className="fs-muted">Opening a recall blocks those batches from every sale and delivery straight away.</p>
            <button type="button" className="fs-primary" disabled={busy || form.title.trim().length < 3 || form.reason.trim().length < 3 || picked.length === 0} onClick={openRecall}>Open recall</button>
          </section>

          <section className="fs-box fs-scroll" aria-label="Recalls">
            <table>
              <thead><tr><th>No.</th><th>Title</th><th>Status</th><th>Opened</th><th /></tr></thead>
              <tbody>
                {recalls.map((r) => (
                  <tr key={r.id}>
                    <td>{r.recall_number}</td><td>{r.title}</td><td>{r.status === 'open' ? <span className="fs-flag">Open</span> : 'Closed'}</td>
                    <td>{(r.created_at || '').slice(0, 10)}</td>
                    <td><button type="button" aria-label={`Open recall ${r.recall_number}`} onClick={() => showRecall(r.id)}>Trace</button></td>
                  </tr>
                ))}
                {recalls.length === 0 ? <tr><td colSpan={5} className="fs-muted">No recalls.</td></tr> : null}
              </tbody>
            </table>
          </section>

          {open ? (
            <section className="fs-box fs-scroll" aria-label="Recall trace">
              <div className="fs-cardhead"><h2>{open.recall_number} · {open.title}</h2></div>
              <p>{open.reason}</p>
              {open.batches.map((b: Row) => (
                <div key={b.batch_id}>
                  <h3>{b.product_name} · {b.batch_number}</h3>
                  <p className="fs-muted">In stock now {b.quantity_in_stock_now} · delivered {b.quantity_delivered} · recovered {b.recovered} · still out {b.outstanding}</p>
                  <table>
                    <thead><tr><th>Outlet</th><th>Order</th><th>Delivered</th><th>Qty</th></tr></thead>
                    <tbody>
                      {b.outlets.map((o: Row, i: number) => (
                        <tr key={i}><td>{o.outlet}</td><td>{o.order_number}</td><td>{(o.delivered_at || '').slice(0, 10)}</td><td className="fs-num">{o.quantity}</td></tr>
                      ))}
                      {b.outlets.length === 0 ? <tr><td colSpan={4} className="fs-muted">None delivered.</td></tr> : null}
                    </tbody>
                  </table>
                  {open.status === 'open' && b.outstanding > 0 ? (
                    <div className="fs-form">
                      <label><span>Recovered from outlets</span>
                        <input type="number" min="0" value={back[b.batch_id] || ''} aria-label={`Recovered quantity ${b.batch_number}`} onChange={(e) => setBack({ ...back, [b.batch_id]: e.target.value })} />
                      </label>
                      <button type="button" disabled={busy || !(Number(back[b.batch_id]) > 0)}
                        onClick={() => run(async () => { setOpen((await post(`/fmcg/recalls/${open.id}/recovered`, { batch_id: b.batch_id, quantity: Number(back[b.batch_id]) }))?.data); setBack({ ...back, [b.batch_id]: '' }); }, 'Recorded.')}>Record recovery</button>
                    </div>
                  ) : null}
                </div>
              ))}
              {open.status === 'open' ? (
                <button type="button" className="fs-danger" disabled={busy} onClick={() => run(async () => { setOpen((await post(`/fmcg/recalls/${open.id}/close`))?.data); }, 'Recall closed. Batches stay on hold until you release them.')}>Close recall</button>
              ) : null}
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
