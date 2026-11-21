'use client';

/**
 * FMCG business overview (command centre) and report centre. Everything is read from the server;
 * the charts are plain bars with the numbers beside them, so nothing depends on colour alone.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api, apiFetch } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const CENTRE_TABS = ['command', 'centre'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin'];
const FILTER_LABELS: Record<string, string> = {
  product_id: 'Product', category_id: 'Category', brand_id: 'Brand', outlet_id: 'Outlet', route_id: 'Route', territory_id: 'Territory',
  supplier_id: 'Supplier', vehicle_id: 'Vehicle', rep: 'Sales rep', status: 'Status',
};
const STATUS_CHOICES: Record<string, string[]> = {
  promotions: ['pending', 'approved', 'rejected'], batch_expiry: ['ok', 'near', 'expired', 'held'],
  forecast_orders: ['stockout_risk', 'ok', 'overstock', 'dead', 'no_forecast'], complaints: ['open', 'investigating', 'resolved', 'rejected'], recalls: ['open', 'closed'],
};
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

function Card({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="fs-card">
      <p className="fs-muted">{label}</p>
      <p><strong style={{ fontSize: 22 }}>{value}</strong></p>
      {sub ? <p className="fs-muted">{sub}</p> : null}
    </div>
  );
}

/** Horizontal bars with the value written next to each, longest first. */
function Bars({ rows, label, value, money = true }: { rows: Row[]; label: string; value: string; money?: boolean }) {
  const max = Math.max(1, ...rows.map((r) => Number(r[value]) || 0));
  if (!rows.length) return <p className="fs-muted">Nothing yet.</p>;
  return (
    <div>
      {rows.map((r) => (
        <div key={String(r[label])} style={{ display: 'grid', gridTemplateColumns: 'minmax(90px,1fr) 2fr auto', gap: 8, alignItems: 'center', margin: '4px 0' }}>
          <span>{r[label]}</span>
          <span aria-hidden="true" style={{ background: 'var(--fs-line)', borderRadius: 6, height: 10 }}>
            <span style={{ display: 'block', height: 10, borderRadius: 6, background: 'var(--fs-brand)', width: `${Math.max(2, (100 * (Number(r[value]) || 0)) / max)}%` }} />
          </span>
          <strong>{money ? formatMoney(r[value]) : r[value]}</strong>
        </div>
      ))}
    </div>
  );
}

/** A column chart for a time series with a visible table underneath for exact figures. */
function Columns({ rows, x, series }: { rows: Row[]; x: string; series: { key: string; label: string }[] }) {
  const max = Math.max(1, ...rows.flatMap((r) => series.map((s) => Number(r[s.key]) || 0)));
  const w = 12, gap = 4, h = 90;
  return (
    <div>
      <svg role="img" aria-label={series.map((s) => s.label).join(' and ') + ' over time'} viewBox={`0 0 ${rows.length * (series.length * w + gap)} ${h}`} style={{ width: '100%', maxHeight: 120 }}>
        {rows.map((r, i) =>
          series.map((s, j) => {
            const bar = ((Number(r[s.key]) || 0) / max) * (h - 4);
            return <rect key={`${i}${s.key}`} x={i * (series.length * w + gap) + j * w} y={h - bar} width={w - 1} height={bar} fill={j === 0 ? 'var(--fs-brand)' : 'var(--fs-gold)'}><title>{`${r[x]} ${s.label}: ${formatMoney(r[s.key])}`}</title></rect>;
          }),
        )}
      </svg>
      <details>
        <summary>Show the figures</summary>
        <table>
          <thead><tr><th>{x === 'date' ? 'Day' : 'Month'}</th>{series.map((s) => <th key={s.key}>{s.label}</th>)}</tr></thead>
          <tbody>{rows.map((r) => <tr key={r[x]}><td>{r[x]}</td>{series.map((s) => <td key={s.key} className="fs-num">{formatMoney(r[s.key])}</td>)}</tr>)}</tbody>
        </table>
      </details>
    </div>
  );
}

export default function FmcgCentre({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [dash, setDash] = useState<Row | null>(null);
  const [catalogue, setCatalogue] = useState<Row[]>([]);
  const [report, setReport] = useState('sales_by_product');
  const [period, setPeriod] = useState({ start: iso(new Date(Date.now() - 29 * 86400000)), end: iso(new Date()) });
  const [result, setResult] = useState<Row | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [alerts, setAlerts] = useState<Row[]>([]);
  const [options, setOptions] = useState<Record<string, Row[]>>({});
  const manager = MANAGERS.includes(role);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    setError('');
    try {
      if (tab === 'command') {
        setDash((await api('/fmcg/dashboard'))?.data || null);
        setAlerts((await api('/fmcg/alerts/log').catch(() => null))?.data || []);
      }
      else {
        setCatalogue((await api('/fmcg/reports/centre'))?.data || []);
        const get = async (path: string) => { try { const r = await api(path); return Array.isArray(r?.data) ? r.data : []; } catch { return []; } };
        const [product_id, category_id, brand_id, outlet_id, route_id, territory_id, supplier_id, vehicle_id] = await Promise.all([
          get('/products'), get('/catalog/categories'), get('/catalog/brands'), get('/fmcg/outlets'), get('/fmcg/routes'),
          get('/fmcg/territories'), get('/suppliers'), get('/fmcg/fleet/vehicles'),
        ]);
        setOptions({ product_id, category_id, brand_id, outlet_id, route_id, territory_id, supplier_id, vehicle_id });
      }
    } catch (err) {
      setError(problem(err));
    }
  }, [tab]);

  useEffect(() => {
    if (manager) load();
  }, [manager, load]);

  const entry = catalogue.find((c) => c.id === report);
  const active = (entry?.filters || []).filter((k: string) => (filters[k] || '').trim() !== '');
  const query = `report=${report}${entry?.period ? `&start=${period.start}&end=${period.end}` : ''}${active.map((k: string) => `&${k}=${encodeURIComponent(filters[k].trim())}`).join('')}`;

  async function run() {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      setResult((await api(`/fmcg/reports/run?${query}`))?.data || null);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  async function download(format: 'csv' | 'xlsx' | 'pdf') {
    setBusy(true);
    setError('');
    try {
      const res = await apiFetch(`/fmcg/reports/run?${query}&format=${format}`);
      if (!res.ok) throw new Error('The export failed. Try again.');
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement('a');
      a.href = url;
      a.download = `fmcg-${report}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      setNotice(format === 'pdf' ? 'PDF downloaded.' : format === 'xlsx' ? 'Excel file downloaded.' : 'CSV downloaded. Open it in Excel or Sheets.');
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
        <div className="fs-banner">This screen is for managers.</div>
      </div>
    );
  }

  const cell = (c: Row, v: any) => (v == null || v === '' ? '-' : c.kind === 'money' ? formatMoney(v) : String(v));

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      {tab === 'command' && dash ? (
        <>
          <p className="fs-muted">{dash.note} Updated {String(dash.as_of).replace('T', ' ')}.</p>
          {dash.attention.length ? (
            <section className="fs-box" aria-label="Needs attention">
              <div className="fs-cardhead"><h2>Needs attention</h2></div>
              {dash.attention.map((a: Row, i: number) => <p key={i}><span className="fs-flag">{a.level === 'warning' ? 'Check' : 'Note'}</span> <a href={a.href}>{a.text}</a></p>)}
            </section>
          ) : null}

          <section className="fs-box fs-scroll" aria-label="Alerts sent">
            <div className="fs-cardhead"><h2>Alerts</h2></div>
            <p className="fs-muted">Expiring batches (your warning days) and vehicle papers are alerted once per stage, by notification and email. Each person chooses email or SMS under Notifications.</p>
            <button type="button" disabled={busy} aria-label="Check for alerts now" onClick={async () => { setBusy(true); try { const r = await api('/fmcg/alerts/scan', { method: 'POST', body: '{}' }); setNotice(`Checked: ${r?.data?.batch ?? 0} batch and ${r?.data?.vehicle ?? 0} vehicle alerts sent.`); await load(); } catch (e) { setError(problem(e)); } finally { setBusy(false); } }}>Check now</button>
            <table>
              <thead><tr><th>Sent</th><th>About</th><th>Stage</th></tr></thead>
              <tbody>
                {alerts.slice(0, 10).map((a) => <tr key={a.id}><td>{String(a.sent_at).slice(0, 16).replace('T', ' ')}</td><td>{a.summary}</td><td>{a.band === 0 ? 'Expired' : `Within ${a.band} days`}</td></tr>)}
                {alerts.length === 0 ? <tr><td colSpan={3} className="fs-muted">None sent yet.</td></tr> : null}
              </tbody>
            </table>
          </section>

          <section className="fs-box" aria-label="Sales">
            <div className="fs-cardhead"><h2>Sales and profit</h2></div>
            <div className="fs-form">
              <Card label="Today" value={formatMoney(dash.sales.today.net_sales)} sub={`${dash.sales.today.orders} orders`} />
              <Card label="Last 7 days" value={formatMoney(dash.sales.week.net_sales)} sub={`${dash.sales.week.orders} orders`} />
              <Card label="This month" value={formatMoney(dash.sales.month.net_sales)} sub={`Profit ${formatMoney(dash.sales.month.gross_profit)} (${dash.sales.month.margin_pct}%)`} />
              <Card label="This year" value={formatMoney(dash.sales.year.net_sales)} sub={`Profit ${formatMoney(dash.sales.year.gross_profit)}`} />
              <Card label="Collected this month" value={formatMoney(dash.sales.month.collected)} sub={`Returns ${formatMoney(dash.sales.month.returns)}`} />
              <Card label="Credit sales this month" value={formatMoney(dash.money.credit_sales_this_month)} />
            </div>
          </section>

          <section className="fs-box" aria-label="Money">
            <div className="fs-cardhead"><h2>Money</h2></div>
            <div className="fs-form">
              <Card label="Owed by outlets" value={formatMoney(dash.money.owed_by_outlets)} sub={`Late ${formatMoney(dash.money.owed_late)}`} />
              <Card label="Owed to suppliers" value={formatMoney(dash.money.owed_to_suppliers)} />
              <Card label="Bought this month" value={formatMoney(dash.money.purchases_this_month)} />
            </div>
            <Bars rows={dash.money.aging.map((a: Row) => ({ name: ({ current: 'Not yet due', d1_30: '1-30 days late', d31_60: '31-60 days late', d61_plus: 'Over 60 days late' } as Record<string, string>)[a.bucket], amount: a.amount }))} label="name" value="amount" />
          </section>

          <section className="fs-box" aria-label="Stock">
            <div className="fs-cardhead"><h2>Stock</h2></div>
            <div className="fs-form">
              <Card label="Stock value (cost)" value={formatMoney(dash.stock.valuation)} sub={`${dash.stock.products} products, ${dash.stock.units} units`} />
              <Card label="Low / out of stock" value={`${dash.stock.low_stock} / ${dash.stock.out_of_stock}`} />
              <Card label="Expiring soon / expired / held" value={`${dash.stock.batches.near} / ${dash.stock.batches.expired} / ${dash.stock.batches.held}`} sub={`At risk ${formatMoney(dash.stock.value_at_risk)}`} />
              <Card label="Not sold in 90 days" value={dash.stock.dead_stock_products} sub={`Lost or written off this month: ${dash.stock.units_lost_this_month} units`} />
            </div>
            <div className="fs-form">
              <div><h3>Fastest sellers (30 days)</h3><Bars rows={dash.stock.fast_movers} label="product" value="units" money={false} /></div>
              <div><h3>Stuck stock (by value)</h3><Bars rows={dash.stock.dead_stock} label="product" value="value" /></div>
            </div>
          </section>

          <section className="fs-box" aria-label="Operations">
            <div className="fs-cardhead"><h2>Operations</h2></div>
            <div className="fs-form">
              <Card label="Orders to load / on trucks" value={`${dash.operations.orders_to_load} / ${dash.operations.orders_on_trucks}`} />
              <Card label="Open dispatches / vans out" value={`${dash.operations.open_dispatches} / ${dash.operations.vans_out}`} sub={`${dash.operations.stale_dispatches} from an earlier day`} />
              <Card label="Outlets / reps / vehicles" value={`${dash.operations.outlets} / ${dash.operations.reps} / ${dash.operations.active_vehicles}`} sub={`${dash.operations.outlets_over_limit} over their credit limit`} />
              <Card label="Open purchase orders" value={dash.operations.purchase_orders_open} />
              <Card label="No proof of delivery (7 days)" value={dash.operations.deliveries_without_proof_7d} />
              <Card label="Complaints / recalls open" value={`${dash.operations.open_complaints} / ${dash.operations.open_recalls}`} sub={`${dash.operations.inspections_pending} inspections waiting`} />
            </div>
          </section>

          <section className="fs-box" aria-label="Sales trend">
            <div className="fs-cardhead"><h2>Sales, last 30 days</h2></div>
            <Columns rows={dash.charts.daily_sales_30} x="date" series={[{ key: 'value', label: 'Sales' }]} />
            <div className="fs-cardhead"><h2>Sales and purchases, 12 months</h2></div>
            <Columns rows={dash.charts.monthly_12} x="month" series={[{ key: 'sales', label: 'Sales' }, { key: 'purchases', label: 'Purchases' }]} />
          </section>

          <section className="fs-box" aria-label="Who sells and who buys">
            <div className="fs-form">
              <div><h3>By category</h3><Bars rows={dash.charts.by_category_30} label="name" value="sales" /></div>
              <div><h3>By sales rep</h3><Bars rows={dash.charts.by_rep_30} label="name" value="sales" /></div>
              <div><h3>By route</h3><Bars rows={dash.charts.by_route} label="name" value="total" /></div>
              <div><h3>Top outlets</h3><Bars rows={dash.charts.top_customers_30} label="name" value="sales" /></div>
              <div><h3>Top products</h3><Bars rows={dash.charts.top_products_30} label="name" value="sales" /></div>
            </div>
          </section>
        </>
      ) : null}

      {tab === 'centre' ? (
        <>
          <section className="fs-box" aria-label="Choose a report">
            <div className="fs-form">
              <label><span>Report</span>
                <select value={report} onChange={(e) => { setReport(e.target.value); setResult(null); setFilters({}); }} aria-label="Report">
                  {Array.from(new Set(catalogue.map((c) => c.group))).map((g) => (
                    <optgroup key={g} label={g}>{catalogue.filter((c) => c.group === g).map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}</optgroup>
                  ))}
                </select>
              </label>
              {entry?.period ? (
                <>
                  <label><span>From</span><input type="date" value={period.start} onChange={(e) => setPeriod({ ...period, start: e.target.value })} aria-label="Report from" /></label>
                  <label><span>To</span><input type="date" value={period.end} onChange={(e) => setPeriod({ ...period, end: e.target.value })} aria-label="Report to" /></label>
                </>
              ) : null}
              <button type="button" className="fs-primary" disabled={busy || !catalogue.length} onClick={run}>Show report</button>
              <button type="button" disabled={busy || !catalogue.length} onClick={() => download('xlsx')} aria-label="Download report as Excel">Excel</button>
              <button type="button" disabled={busy || !catalogue.length} onClick={() => download('pdf')} aria-label="Download report as PDF">PDF</button>
              <button type="button" disabled={busy || !catalogue.length} onClick={() => download('csv')} aria-label="Download report as CSV">CSV</button>
              <button type="button" onClick={() => window.print()} aria-label="Print report">Print</button>
            </div>
          </section>
          {entry?.filters?.length ? (
            <section className="fs-box" aria-label="Report filters">
              <div className="fs-form">
                {entry.filters.map((k: string) => (
                  <label key={k}><span>{FILTER_LABELS[k]}</span>
                    {k === 'rep' ? (
                      <input value={filters[k] || ''} onChange={(e) => setFilters({ ...filters, [k]: e.target.value })} aria-label="Filter sales rep" placeholder="Exact name" />
                    ) : k === 'status' ? (
                      <select value={filters[k] || ''} onChange={(e) => setFilters({ ...filters, [k]: e.target.value })} aria-label="Filter status">
                        <option value="">All</option>{(STATUS_CHOICES[report] || []).map((v) => <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>)}
                      </select>
                    ) : (
                      <select value={filters[k] || ''} onChange={(e) => setFilters({ ...filters, [k]: e.target.value })} aria-label={`Filter ${FILTER_LABELS[k].toLowerCase()}`}>
                        <option value="">All</option>{(options[k] || []).map((o: Row) => <option key={o.id} value={o.id}>{o.name || o.plate}</option>)}
                      </select>
                    )}
                  </label>
                ))}
                {active.length ? <button type="button" onClick={() => setFilters({})}>Clear filters</button> : null}
              </div>
            </section>
          ) : null}
          {result ? (
            <section className="fs-box fs-scroll" aria-label="Report">
              <div className="fs-cardhead"><h2>{result.title}</h2></div>
              {result.period ? <p className="fs-muted">{result.period.start} to {result.period.end}</p> : null}
              {result.filters_text ? <p className="fs-muted">Filters: {result.filters_text}</p> : null}
              {result.note ? <p className="fs-muted">{result.note}</p> : null}
              <table>
                <thead><tr>{result.columns.map((c: Row) => <th key={c.key}>{c.label}</th>)}</tr></thead>
                <tbody>
                  {result.rows.map((r: Row, i: number) => <tr key={i}>{result.columns.map((c: Row) => <td key={c.key} className={c.kind === 'text' ? '' : 'fs-num'}>{cell(c, r[c.key])}</td>)}</tr>)}
                  {result.rows.length === 0 ? <tr><td colSpan={result.columns.length} className="fs-muted">Nothing to show for this report and period.</td></tr> : null}
                </tbody>
              </table>
              {result.truncated ? <p className="fs-muted">Showing the first {result.rows.length} of {result.row_count} rows.</p> : null}
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
