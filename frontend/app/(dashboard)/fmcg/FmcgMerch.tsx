'use client';

/**
 * FMCG merchandising: a shelf audit at an outlet (every must-stock product answered), competitor
 * price sightings, the must-stock list (managers) and a shelf report (managers). The score and
 * every rule are worked out on the server.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { enqueue, looksOffline, type OfflineKind } from '../../../lib/fmcgOffline';
import FmcgOfflineBar from '../../../components/FmcgOfflineBar';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const MERCH_TABS = ['merch'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin'];
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(new Error('Could not read that photo'));
    r.readAsDataURL(file);
  });
}

export default function FmcgMerch({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [must, setMust] = useState<Row[]>([]);
  const [products, setProducts] = useState<Row[]>([]);
  const [outlets, setOutlets] = useState<Row[]>([]);
  const [outletId, setOutletId] = useState('');
  const [answers, setAnswers] = useState<Record<string, { present: boolean; facings: string; price: string }>>({});
  const [displayOk, setDisplayOk] = useState('na');
  const [notes, setNotes] = useState('');
  const [photo, setPhoto] = useState('');
  const [audits, setAudits] = useState<Row[]>([]);
  const [price, setPrice] = useState({ product_id: '', competitor_brand: '', competitor_product: '', price: '' });
  const [pick, setPick] = useState({ product_id: '', min_facings: '1' });
  const [period, setPeriod] = useState({ start: iso(new Date(Date.now() - 29 * 86400000)), end: iso(new Date()) });
  const [report, setReport] = useState<Row | null>(null);
  const manager = MANAGERS.includes(role);

  const [tenant, setTenant] = useState('');
  const [tick, setTick] = useState(0);
  const queued = useRef(false);

  /** Send now; if the network is down, keep it on this device to send later. Server refusals still show as errors. */
  async function sendOrQueue(kind: OfflineKind, path: string, body: Record<string, any>, label: string, extra: Record<string, any> = {}) {
    try {
      await api(path, { method: 'POST', body: JSON.stringify(body) });
    } catch (err) {
      if (!tenant || !looksOffline(err)) throw err;
      await enqueue(tenant, kind, { ...extra, ...body }, label);
      queued.current = true;
      setTick((t) => t + 1);
    }
  }

  useEffect(() => {
    getMe().then((me: Row | null) => { setRole(String(me?.data?.role || '')); setTenant(String(me?.data?.tenant_id || '')); }).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    setError('');
    try {
      const [ms, a, o, p] = await Promise.all([
        api('/fmcg/merch/must-stock'), api('/fmcg/merch/audits'), api(manager ? '/fmcg/outlets' : '/fmcg/my-outlets'), api('/products').catch(() => null),
      ]);
      setMust(ms?.data || []);
      setAudits(a?.data || []);
      setOutlets(o?.data || []);
      setProducts(Array.isArray(p?.data) ? p.data : []);
      if (manager) setReport((await api(`/fmcg/merch/report?start=${period.start}&end=${period.end}`))?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }, [manager, period.start, period.end]);

  useEffect(() => {
    if (role) load();
  }, [role, load]);

  async function run(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      queued.current = false;
      await fn();
      if (queued.current) {
        setNotice('Saved on this device. It will be sent when you are back online.');
      } else {
        setNotice(done);
        await load();
      }
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  const send = (path: string, body: unknown, method = 'POST') => api(path, { method, body: JSON.stringify(body) });
  const ans = (id: string) => answers[id] || { present: true, facings: '1', price: '' };
  const setAns = (id: string, patch: Partial<{ present: boolean; facings: string; price: string }>) => setAnswers({ ...answers, [id]: { ...ans(id), ...patch } });

  const saveAudit = () =>
    run(async () => {
      const lines = must.map((p) => {
        const a = ans(p.product_id);
        return {
          product_id: p.product_id, present: a.present, facings: a.present ? Number(a.facings) || 1 : 0,
          ...(a.present && a.price !== '' ? { shelf_price: Number(a.price) } : {}),
        };
      });
      const outletName = outlets.find((o) => o.id === outletId)?.name || 'outlet';
      await sendOrQueue('shelf_audit', '/fmcg/merch/audits', {
        outlet_id: outletId, lines, ...(displayOk !== 'na' ? { display_ok: displayOk === 'yes' } : {}),
        ...(notes.trim().length >= 3 ? { notes: notes.trim() } : {}), ...(photo ? { photo } : {}),
      }, outletName);
      setAnswers({});
      setNotes('');
      setPhoto('');
      setOutletId('');
    }, 'Shelf audit saved.');

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      <FmcgOfflineBar tenant={tenant} tick={tick} onSynced={load} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      <section className="fs-box" aria-label="Shelf audit">
        <div className="fs-cardhead"><h2>Shelf audit</h2></div>
        {must.length === 0 ? <p className="fs-muted">{manager ? 'Set the must-stock list below first.' : 'A manager has not set the must-stock list yet.'}</p> : (
          <>
            <div className="fs-form">
              <label><span>Outlet</span>
                <select value={outletId} onChange={(e) => setOutletId(e.target.value)} aria-label="Audit outlet">
                  <option value="">Pick an outlet</option>{outlets.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              </label>
              <label><span>Display set up as planned</span>
                <select value={displayOk} onChange={(e) => setDisplayOk(e.target.value)} aria-label="Display ok">
                  <option value="na">Not checked</option><option value="yes">Yes</option><option value="no">No</option>
                </select>
              </label>
            </div>
            <table>
              <thead><tr><th>Product</th><th>On the shelf</th><th>Facings (need {'≥'} min)</th><th>Shelf price</th></tr></thead>
              <tbody>
                {must.map((p) => {
                  const a = ans(p.product_id);
                  return (
                    <tr key={p.product_id}>
                      <td>{p.product} <span className="fs-muted">(min {p.min_facings})</span></td>
                      <td><input type="checkbox" checked={a.present} onChange={(e) => setAns(p.product_id, { present: e.target.checked })} aria-label={`${p.product} on shelf`} /></td>
                      <td><input type="number" min="0" disabled={!a.present} value={a.present ? a.facings : '0'} onChange={(e) => setAns(p.product_id, { facings: e.target.value })} aria-label={`${p.product} facings`} /></td>
                      <td><input type="number" min="0" disabled={!a.present} value={a.price} onChange={(e) => setAns(p.product_id, { price: e.target.value })} aria-label={`${p.product} shelf price`} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="fs-form">
              <label><span>Notes</span><input value={notes} onChange={(e) => setNotes(e.target.value)} aria-label="Audit notes" /></label>
              <label><span>Photo of the shelf (optional)</span>
                <input type="file" accept="image/png,image/jpeg" capture="environment" aria-label="Shelf photo"
                  onChange={async (e) => { const f = e.target.files?.[0]; if (!f) return setPhoto(''); try { setPhoto(await readFile(f)); } catch (err) { setError(problem(err)); } }} />
              </label>
              <button type="button" className="fs-primary" disabled={busy || !outletId} onClick={saveAudit}>Save audit</button>
            </div>
          </>
        )}
      </section>

      <section className="fs-box fs-scroll" aria-label="Recent audits">
        <div className="fs-cardhead"><h2>{manager ? 'Recent audits' : 'My recent audits'}</h2></div>
        <table>
          <thead><tr><th>When</th><th>Outlet</th>{manager ? <th>By</th> : null}<th>Score</th><th>On shelf</th><th>Display</th></tr></thead>
          <tbody>
            {audits.map((a) => (
              <tr key={a.id}>
                <td>{String(a.audited_at).slice(0, 16).replace('T', ' ')}</td><td>{a.outlet}</td>{manager ? <td>{a.auditor || '-'}</td> : null}
                <td className="fs-num">{a.score_pct == null ? '-' : a.score_pct < 70 ? <span className="fs-flag">{a.score_pct}%</span> : `${a.score_pct}%`}</td>
                <td className="fs-num">{a.available}/{a.required}</td><td>{a.display_ok == null ? '-' : a.display_ok ? 'Yes' : 'No'}</td>
              </tr>
            ))}
            {audits.length === 0 ? <tr><td colSpan={manager ? 6 : 5} className="fs-muted">No audits yet.</td></tr> : null}
          </tbody>
        </table>
      </section>

      <section className="fs-box" aria-label="Competitor price">
        <div className="fs-cardhead"><h2>Note a competitor price</h2></div>
        <div className="fs-form">
          <label><span>Our product</span>
            <select value={price.product_id} onChange={(e) => setPrice({ ...price, product_id: e.target.value })} aria-label="Competitor price our product">
              <option value="">Pick a product</option>{(products.length ? products : must.map((m) => ({ id: m.product_id, name: m.product }))).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label><span>Their brand</span><input value={price.competitor_brand} onChange={(e) => setPrice({ ...price, competitor_brand: e.target.value })} aria-label="Competitor brand" /></label>
          <label><span>Their product</span><input value={price.competitor_product} onChange={(e) => setPrice({ ...price, competitor_product: e.target.value })} aria-label="Competitor product" /></label>
          <label><span>Shelf price</span><input type="number" min="0" value={price.price} onChange={(e) => setPrice({ ...price, price: e.target.value })} aria-label="Competitor shelf price" /></label>
          <button type="button" disabled={busy || !price.product_id || price.competitor_brand.trim().length < 2 || price.competitor_product.trim().length < 2 || !(Number(price.price) > 0)}
            onClick={() => run(async () => { await sendOrQueue('competitor_price', '/fmcg/merch/competitor-prices', { product_id: price.product_id, competitor_brand: price.competitor_brand.trim(), competitor_product: price.competitor_product.trim(), price: Number(price.price), ...(outletId ? { outlet_id: outletId } : {}) }, `${price.competitor_brand.trim()} ${price.competitor_product.trim()}`); setPrice({ ...price, competitor_product: '', price: '' }); }, 'Price noted.')}>Save price</button>
        </div>
      </section>

      {manager ? (
        <>
          <section className="fs-box" aria-label="Must-stock list">
            <div className="fs-cardhead"><h2>Must-stock list</h2></div>
            <p className="fs-muted">Every audit has to answer these products. Fewer facings than the minimum counts as not compliant.</p>
            <table>
              <thead><tr><th>Product</th><th>Minimum facings</th><th /></tr></thead>
              <tbody>
                {must.map((p) => (
                  <tr key={p.product_id}><td>{p.product}</td><td className="fs-num">{p.min_facings}</td>
                    <td><button type="button" className="fs-danger" disabled={busy} aria-label={`Remove ${p.product} from the list`} onClick={() => run(() => send('/fmcg/merch/must-stock', { items: must.filter((x) => x.product_id !== p.product_id).map((x) => ({ product_id: x.product_id, min_facings: x.min_facings })) }, 'PUT'), 'Removed.')}>Remove</button></td></tr>
                ))}
                {must.length === 0 ? <tr><td colSpan={3} className="fs-muted">Empty.</td></tr> : null}
              </tbody>
            </table>
            <div className="fs-form">
              <label><span>Add a product</span>
                <select value={pick.product_id} onChange={(e) => setPick({ ...pick, product_id: e.target.value })} aria-label="Must-stock product">
                  <option value="">Pick a product</option>{products.filter((p) => !must.some((x) => x.product_id === p.id)).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </label>
              <label><span>Minimum facings</span><input type="number" min="1" max="50" value={pick.min_facings} onChange={(e) => setPick({ ...pick, min_facings: e.target.value })} aria-label="Minimum facings" /></label>
              <button type="button" disabled={busy || !pick.product_id}
                onClick={() => run(async () => { await send('/fmcg/merch/must-stock', { items: [...must.map((x) => ({ product_id: x.product_id, min_facings: x.min_facings })), { product_id: pick.product_id, min_facings: Number(pick.min_facings) || 1 }] }, 'PUT'); setPick({ product_id: '', min_facings: '1' }); }, 'Added.')}>Add to list</button>
            </div>
          </section>

          {report ? (
            <section className="fs-box fs-scroll" aria-label="Shelf report">
              <div className="fs-cardhead"><h2>Shelf report</h2></div>
              <div className="fs-form">
                <label><span>From</span><input type="date" value={period.start} onChange={(e) => setPeriod({ ...period, start: e.target.value })} aria-label="Shelf report from" /></label>
                <label><span>To</span><input type="date" value={period.end} onChange={(e) => setPeriod({ ...period, end: e.target.value })} aria-label="Shelf report to" /></label>
              </div>
              <p>
                {report.summary.audits} audits at {report.summary.outlets_audited} of {report.summary.active_outlets} outlets
                {report.summary.coverage_pct != null ? ` (${report.summary.coverage_pct}% reached)` : ''} · average score {report.summary.average_score_pct ?? '-'}%
              </p>
              <h3>Outlets, weakest first</h3>
              <table>
                <thead><tr><th>Outlet</th><th>Last audit</th><th>Score</th><th>On shelf</th><th>Display</th></tr></thead>
                <tbody>{report.outlets.map((o: Row) => <tr key={o.outlet_id}><td>{o.outlet}</td><td>{o.audited_at}</td><td className="fs-num">{o.score_pct ?? '-'}%</td><td className="fs-num">{o.available}/{o.required}</td><td>{o.display_ok == null ? '-' : o.display_ok ? 'Yes' : 'No'}</td></tr>)}
                  {report.outlets.length === 0 ? <tr><td colSpan={5} className="fs-muted">No audits in this period.</td></tr> : null}</tbody>
              </table>
              <h3>Availability by product</h3>
              <table>
                <thead><tr><th>Product</th><th>Audited at</th><th>Missing at</th><th>On shelf</th></tr></thead>
                <tbody>{report.products.map((p: Row) => <tr key={p.product_id}><td>{p.product}{p.must_stock ? '' : ' (extra)'}</td><td className="fs-num">{p.audited_at_outlets}</td><td className="fs-num">{p.out_of_stock_at}</td><td className="fs-num">{p.availability_pct}%</td></tr>)}</tbody>
              </table>
              <h3>Reps</h3>
              <table>
                <thead><tr><th>Rep</th><th>Audits</th><th>Average score</th></tr></thead>
                <tbody>{report.reps.map((r: Row, i: number) => <tr key={i}><td>{r.auditor}</td><td className="fs-num">{r.audits}</td><td className="fs-num">{r.average_score_pct ?? '-'}%</td></tr>)}</tbody>
              </table>
              <h3>Prices against competitors</h3>
              <table>
                <thead><tr><th>Product</th><th>Our list price</th><th>Our shelf price</th><th>Competitor average</th><th>Low / high</th><th>Seen</th><th>Index</th></tr></thead>
                <tbody>{report.prices.map((p: Row) => <tr key={p.product_id}><td>{p.product}</td><td className="fs-num">{formatMoney(p.our_list_price)}</td><td className="fs-num">{p.our_shelf_price_avg ?? '-'}</td><td className="fs-num">{formatMoney(p.competitor_avg)}</td><td className="fs-num">{p.competitor_low} / {p.competitor_high}</td><td className="fs-num">{p.sightings}</td><td className="fs-num">{p.price_index}</td></tr>)}
                  {report.prices.length === 0 ? <tr><td colSpan={7} className="fs-muted">No competitor prices noted in this period.</td></tr> : null}</tbody>
              </table>
              <p className="fs-muted">{report.note}</p>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
