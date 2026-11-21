'use client';

/**
 * FMCG demand forecast. Shows what is likely to sell, when stock runs out and what to order. It is
 * an estimate from delivered orders and says so on screen, with the data period and a backtest
 * error. All numbers come from the server.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const FORECAST_TABS = ['forecast'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin'];
const STATUS_WORDS: Record<string, string> = {
  stockout_risk: 'May run out', ok: 'Fine', overstock: 'Too much stock', dead: 'Not selling', no_forecast: 'Too little history',
};
const FILTERS = [
  { id: 'all', label: 'All' }, { id: 'stockout_risk', label: 'May run out' }, { id: 'overstock', label: 'Too much stock' },
  { id: 'dead', label: 'Not selling' },
];
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';

export default function FmcgForecast({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState<Row | null>(null);
  const [history, setHistory] = useState('90');
  const [horizon, setHorizon] = useState('30');
  const [filter, setFilter] = useState('all');
  const [policy, setPolicy] = useState({ lead_time_days: '7', service_level: '95', overstock_days: '120' });
  const manager = MANAGERS.includes(role);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    setError('');
    try {
      const [f, p] = await Promise.all([
        api(`/fmcg/forecast?history_days=${Number(history)}&horizon_days=${Number(horizon)}`), api('/fmcg/forecast/policy'),
      ]);
      setData(f?.data || null);
      setPolicy({ lead_time_days: String(p?.data?.lead_time_days), service_level: String(p?.data?.service_level), overstock_days: String(p?.data?.overstock_days) });
    } catch (err) {
      setError(problem(err));
    }
  }, [history, horizon]);

  useEffect(() => {
    if (manager) load();
  }, [manager, load]);

  async function savePolicy() {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api('/fmcg/forecast/policy', {
        method: 'PUT',
        body: JSON.stringify({ lead_time_days: Number(policy.lead_time_days), service_level: Number(policy.service_level), overstock_days: Number(policy.overstock_days) }),
      });
      setNotice('Saved.');
      await load();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  if (role && !manager) {
    return (
      <div className="fmcg-sell">
        <FmcgHead tab={tab} />
        <div className="fs-banner">The forecast is for managers.</div>
      </div>
    );
  }

  const meta: Row = data?.meta || {};
  const rows: Row[] = (data?.products || []).filter((p: Row) => filter === 'all' || p.status === filter);

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      <div className="fs-banner" role="note">
        Estimate, not sales. Based on delivered orders from {meta.history_from || '...'} to {meta.history_to || '...'}.
        {data?.accuracy?.error_pct != null ? ` Last 28 days predicted from the days before: off by ${data.accuracy.error_pct}%.` : ' Not enough history to test the method yet.'}
      </div>

      <section className="fs-box" aria-label="Forecast settings">
        <div className="fs-form">
          <label><span>Look back (days)</span><input type="number" min="28" max="365" value={history} onChange={(e) => setHistory(e.target.value)} aria-label="Forecast history days" /></label>
          <label><span>Look ahead (days)</span><input type="number" min="7" max="180" value={horizon} onChange={(e) => setHorizon(e.target.value)} aria-label="Forecast horizon days" /></label>
          <label><span>Supplier lead time (days)</span><input type="number" min="1" max="120" value={policy.lead_time_days} onChange={(e) => setPolicy({ ...policy, lead_time_days: e.target.value })} aria-label="Lead time days" /></label>
          <label><span>Never run out (% of the time)</span>
            <select value={policy.service_level} onChange={(e) => setPolicy({ ...policy, service_level: e.target.value })} aria-label="Service level">
              {[90, 95, 97, 99].map((v) => <option key={v} value={v}>{v}%</option>)}
            </select>
          </label>
          <label><span>Too much stock above (days of cover)</span><input type="number" min="30" max="720" value={policy.overstock_days} onChange={(e) => setPolicy({ ...policy, overstock_days: e.target.value })} aria-label="Overstock days" /></label>
          <button type="button" disabled={busy} onClick={savePolicy}>Save and refresh</button>
        </div>
      </section>

      {data ? (
        <section className="fs-box" aria-label="Forecast summary">
          <p>
            <strong>{data.counts.stockout_risk}</strong> may run out · <strong>{data.counts.overstock}</strong> too much stock ·{' '}
            <strong>{data.counts.dead}</strong> not selling · <strong>{data.counts.no_forecast}</strong> too little history
          </p>
        </section>
      ) : null}

      <section className="fs-box" aria-label="Product filters">
        <div className="fs-form">
          {FILTERS.map((f) => (
            <button key={f.id} type="button" className={filter === f.id ? 'fs-primary' : ''} onClick={() => setFilter(f.id)} aria-label={`Show ${f.label} products`}>{f.label}</button>
          ))}
        </div>
      </section>

      <section className="fs-box fs-scroll" aria-label="Product forecast">
        <table>
          <thead>
            <tr><th>Product</th><th>Status</th><th>In stock</th><th>On order</th><th>Per day (est.)</th><th>Next {meta.horizon_days || 30} days (est.)</th><th>Days left</th><th>Runs out</th><th>Reorder at</th><th>Order (est.)</th><th>Trust</th></tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.product_id}>
                <td>{p.product}</td>
                <td>{p.status === 'ok' ? STATUS_WORDS.ok : <span className="fs-flag">{STATUS_WORDS[p.status]}</span>}</td>
                <td className="fs-num">{p.stock}</td>
                <td className="fs-num">{p.on_order ?? '-'}</td>
                <td className="fs-num">{p.daily_forecast ?? '-'}</td>
                <td className="fs-num">{p.forecast_horizon_qty ?? '-'}</td>
                <td className="fs-num">{p.days_of_cover ?? '-'}</td>
                <td>{p.stockout_date || '-'}</td>
                <td className="fs-num">{p.reorder_point ?? '-'}</td>
                <td className="fs-num">{p.suggested_order ?? '-'}</td>
                <td>{p.confidence ? `${p.confidence}${p.promo_share_pct > 30 ? `, ${p.promo_share_pct}% on promotion` : ''}` : (p.note || '-')}</td>
              </tr>
            ))}
            {rows.length === 0 ? <tr><td colSpan={11} className="fs-muted">Nothing here.</td></tr> : null}
          </tbody>
        </table>
      </section>

      {data ? (
        <>
          <section className="fs-box fs-scroll" aria-label="Forecast by route">
            <div className="fs-cardhead"><h2>By route</h2></div>
            <table>
              <thead><tr><th>Route</th><th>Sold in the period</th><th>Next {meta.horizon_days} days (est.)</th><th>Share</th></tr></thead>
              <tbody>
                {data.by_route.map((r: Row) => <tr key={r.route}><td>{r.route}</td><td className="fs-num">{r.history_qty}</td><td className="fs-num">{r.forecast_qty}</td><td className="fs-num">{r.share_pct}%</td></tr>)}
                {data.by_route.length === 0 ? <tr><td colSpan={4} className="fs-muted">No deliveries in the period.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <section className="fs-box fs-scroll" aria-label="Forecast by category">
            <div className="fs-cardhead"><h2>By category</h2></div>
            <table>
              <thead><tr><th>Category</th><th>Next {meta.horizon_days} days (est.)</th></tr></thead>
              <tbody>
                {data.by_category.map((c: Row) => <tr key={c.category}><td>{c.category}</td><td className="fs-num">{c.forecast_qty}</td></tr>)}
                {data.by_category.length === 0 ? <tr><td colSpan={2} className="fs-muted">Nothing to forecast yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <p className="fs-muted">{meta.note} Orders already placed with suppliers and not yet received are taken off the suggested order.</p>
        </>
      ) : null}
    </div>
  );
}
