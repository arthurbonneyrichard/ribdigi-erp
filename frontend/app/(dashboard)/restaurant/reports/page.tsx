'use client';

/**
 * Restaurant reports: one period at a time — what sold, when, by whom, how it was paid,
 * what the food cost and what was wasted. Accounting statements stay on the shared Reports.
 */

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import { METHOD_WORDS, MODE_WORDS, money, problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Preset = 'today' | '7' | '30' | 'month' | 'custom';

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function rangeFor(preset: Preset): [string, string] {
  const today = new Date();
  const back = (n: number) => iso(new Date(today.getFullYear(), today.getMonth(), today.getDate() - n));
  if (preset === 'today') return [iso(today), iso(today)];
  if (preset === '30') return [back(29), iso(today)];
  if (preset === 'month') return [iso(new Date(today.getFullYear(), today.getMonth(), 1)), iso(today)];
  return [back(6), iso(today)];
}

function qty(value: unknown) {
  const n = Number(value || 0);
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function dayLabel(date: string, many: boolean) {
  const d = new Date(`${date}T00:00:00`);
  return many ? String(d.getDate()) : d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' });
}

function hourLabel(h: number) {
  const suffix = h < 12 ? 'am' : 'pm';
  return `${h % 12 === 0 ? 12 : h % 12}${suffix}`;
}

export default function RestaurantReportsPage() {
  const [preset, setPreset] = useState<Preset>('7');
  const [from, setFrom] = useState(() => rangeFor('7')[0]);
  const [to, setTo] = useState(() => rangeFor('7')[1]);
  const [data, setData] = useState<Row | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [allDishes, setAllDishes] = useState(false);

  const load = useCallback(async (start: string, end: string) => {
    setLoading(true);
    try {
      const res = await api(`/restaurant/reports/period?from_date=${start}&to_date=${end}`);
      setData(res?.data || null);
      setError('');
    } catch (err) {
      setError(problem(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(from, to);
  }, [load, from, to]);

  function pick(next: Preset) {
    setPreset(next);
    if (next !== 'custom') {
      const [a, b] = rangeFor(next);
      setFrom(a);
      setTo(b);
    }
  }

  const totals: Row = data?.totals || {};
  const dishes: Row[] = data?.dishes || [];
  const shownDishes = allDishes ? dishes : dishes.slice(0, 10);
  const slow = dishes.length > 10 ? [...dishes].sort((a, b) => Number(a.quantity) - Number(b.quantity)).slice(0, 5) : [];
  const busyHours = useMemo(() => {
    const hours: Row[] = data?.by_hour || [];
    const used = hours.filter((h) => h.orders > 0);
    if (!used.length) return [];
    const first = Math.max(0, used[0].hour - 1);
    const last = Math.min(23, used[used.length - 1].hour + 1);
    return hours.slice(first, last + 1);
  }, [data]);
  const busiest = busyHours.reduce<Row | null>((best, h) => (!best || h.sales > best.sales ? h : best), null);
  const days: Row[] = data?.by_day || [];
  const bestDay = days.reduce<Row | null>((best, d) => (!best || d.sales > best.sales ? d : best), null);
  const foodPct = totals.food_cost_pct;
  const change = totals.sales_change_pct;

  function exportDishes() {
    const rows = [['Dish', 'Sold', 'Sales', 'Food cost', 'Food cost %', 'Profit'], ...dishes.map((d) => [d.name, d.quantity, d.sales, d.cost, d.food_cost_pct ?? '', d.profit])];
    const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `restaurant-dishes-${from}-to-${to}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Reports</h1>
          <p>How the restaurant did: sales, best sellers, food cost and waste.</p>
        </div>
        <div className="rd-head-actions">
          <Link className="rd-linkish" href="/reports?tab=pnl">Profit and loss →</Link>
        </div>
      </header>

      <div className="rd-period" role="group" aria-label="Report period">
        <div className="rd-chips">
          {([['today', 'Today'], ['7', 'Last 7 days'], ['30', 'Last 30 days'], ['month', 'This month'], ['custom', 'Pick dates']] as const).map(([key, label]) => (
            <button key={key} type="button" className={preset === key ? 'on' : ''} aria-pressed={preset === key} onClick={() => pick(key)}>
              {label}
            </button>
          ))}
        </div>
        {preset === 'custom' ? (
          <div className="rd-dates">
            <input type="date" aria-label="Report from date" value={from} max={to} onChange={(e) => e.target.value && setFrom(e.target.value)} />
            <span>to</span>
            <input type="date" aria-label="Report to date" value={to} min={from} onChange={(e) => e.target.value && setTo(e.target.value)} />
          </div>
        ) : null}
      </div>

      {error ? <div className="rd-error" role="alert">{error}</div> : null}
      {loading && !data ? <div className="rd-empty">Loading the report…</div> : null}

      {data ? (
        <div className={`rd-report${loading ? ' is-loading' : ''}`}>
          <div className="rd-kpis">
            <div className="rd-kpi hero">
              <span>Sales</span>
              <strong>{money(totals.sales)}</strong>
              <small>
                {change == null ? 'No sales in the period before' : `${change >= 0 ? '▲' : '▼'} ${Math.abs(change)}% on the ${data.days === 1 ? 'day' : `${data.days} days`} before`}
              </small>
            </div>
            <div className="rd-kpi">
              <span>Orders</span>
              <strong>{totals.orders}</strong>
              <small>Average {money(totals.average_order)}</small>
            </div>
            <div className="rd-kpi">
              <span>Food cost</span>
              <strong>{foodPct == null ? '—' : `${foodPct}%`}</strong>
              <small className={foodPct != null && foodPct > 35 ? 'rd-warn-text' : ''}>
                {money(totals.food_cost)} of ingredients{foodPct != null && foodPct > 35 ? ' · above 35%' : ''}
              </small>
            </div>
            <div className="rd-kpi">
              <span>Waste</span>
              <strong>{money(totals.waste_cost)}</strong>
              <small>
                <Link href="/restaurant?tab=waste">Record waste</Link>
              </small>
            </div>
            <div className="rd-kpi">
              <span>Refunds</span>
              <strong>{money(totals.refunds)}</strong>
              <small>{totals.refunded_orders} {totals.refunded_orders === 1 ? 'order' : 'orders'}</small>
            </div>
          </div>

          {totals.orders === 0 ? (
            <div className="rd-empty">
              <strong>No paid orders in this period</strong>Pick another period, or ring up an order on the till.
            </div>
          ) : (
            <>
              <div className="rd-split">
                <section className="rd-panel">
                  <div className="rd-panel-head">
                    <h2>Sales by day</h2>
                    {bestDay && bestDay.sales > 0 ? <small>Best: {dayLabel(bestDay.date, false)} · {money(bestDay.sales)}</small> : null}
                  </div>
                  <Bars
                    label="Sales by day"
                    rows={days.map((d) => ({ key: d.date, label: dayLabel(d.date, days.length > 10), value: Number(d.sales), detail: `${dayLabel(d.date, false)}: ${money(d.sales)} · ${d.orders} orders` }))}
                    sparseLabels={days.length > 14}
                  />
                </section>
                <section className="rd-panel">
                  <div className="rd-panel-head">
                    <h2>Busiest hours</h2>
                    {busiest ? <small>Peak: {hourLabel(busiest.hour)} · {money(busiest.sales)}</small> : null}
                  </div>
                  <Bars
                    label="Sales by hour"
                    rows={busyHours.map((h) => ({ key: String(h.hour), label: hourLabel(h.hour), value: Number(h.sales), detail: `${hourLabel(h.hour)}: ${money(h.sales)} · ${h.orders} orders` }))}
                    sparseLabels={busyHours.length > 12}
                  />
                </section>
              </div>

              <section className="rd-panel">
                <div className="rd-panel-head">
                  <h2>Dishes and drinks</h2>
                  <small>Food cost uses each recipe as it is today.</small>
                  <button type="button" className="rd-link" aria-label="Download dishes CSV" onClick={exportDishes}>
                    Download CSV
                  </button>
                </div>
                <div className="rd-table-wrap">
                  <table className="rd-table" aria-label="Dishes sold">
                    <thead>
                      <tr>
                        <th>Dish</th>
                        <th className="num">Sold</th>
                        <th className="num col-sales">Sales</th>
                        <th className="num">Food cost</th>
                        <th className="num">Profit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shownDishes.map((d, i) => (
                        <tr key={d.product_id}>
                          <td>
                            <span className="rank">{i + 1}</span>
                            {d.name}
                          </td>
                          <td className="num">{qty(d.quantity)}</td>
                          <td className="num col-sales">{money(d.sales)}</td>
                          <td className={`num${d.food_cost_pct > 35 ? ' rd-warn-text' : ''}`}>
                            {d.food_cost_pct == null ? '—' : `${d.food_cost_pct}%`}
                          </td>
                          <td className="num strong">{money(d.profit)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {dishes.length > 10 ? (
                  <button type="button" className="rd-link" onClick={() => setAllDishes(!allDishes)}>
                    {allDishes ? 'Show top 10' : `Show all ${dishes.length}`}
                  </button>
                ) : null}
                {slow.length ? (
                  <p className="rd-hint-line">
                    Slowest: {slow.map((d) => `${d.name} (${qty(d.quantity)})`).join(', ')}. Worth a special, or off the menu?
                  </p>
                ) : null}
              </section>

              <div className="rd-split rd-split-3">
                <Breakdown title="Who took the orders" rows={(data.by_staff || []).map((r: Row) => ({ key: r.user_id || 'online', label: r.name, value: Number(r.sales), orders: r.orders }))} />
                <Breakdown title="Order type" rows={(data.by_service_mode || []).map((r: Row) => ({ key: r.service_mode, label: MODE_WORDS[r.service_mode] || r.service_mode, value: Number(r.sales), orders: r.orders }))} />
                <Breakdown title="How guests paid" rows={(data.by_payment_method || []).map((r: Row) => ({ key: r.payment_method, label: METHOD_WORDS[r.payment_method] || r.payment_method, value: Number(r.sales), orders: r.orders }))} />
              </div>
            </>
          )}

          {(data.waste || []).length ? (
            <section className="rd-panel">
              <div className="rd-panel-head">
                <h2>Waste</h2>
                <small>{money(totals.waste_cost)} at cost</small>
              </div>
              <ul className="rd-waste-report">
                {(data.waste as Row[]).map((w) => (
                  <li key={w.product_id}>
                    <span>{w.name}</span>
                    <span>{qty(w.quantity)}</span>
                    <strong>{money(w.cost)}</strong>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Bars({ label, rows, sparseLabels }: { label: string; rows: { key: string; label: string; value: number; detail: string }[]; sparseLabels?: boolean }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className={`rd-bars${rows.length > 8 ? ' many' : ''}`} role="img" aria-label={`${label}: ${rows.map((r) => r.detail).join('; ')}`}>
      {rows.map((r, i) => (
        <div key={r.key} className="rd-bar-col" tabIndex={0} aria-label={r.detail}>
          <span className="rd-bar-tip">{r.detail}</span>
          <div className="rd-bar-track">
            <div className={`rd-bar${r.value === max && r.value > 0 ? ' top' : ''}`} style={{ height: `${Math.max(r.value > 0 ? 3 : 0, (r.value / max) * 100)}%` }} />
          </div>
          <small>{!sparseLabels || i % 2 === 0 ? r.label : ''}</small>
        </div>
      ))}
    </div>
  );
}

function Breakdown({ title, rows }: { title: string; rows: { key: string; label: string; value: number; orders: number }[] }) {
  const total = rows.reduce((s, r) => s + r.value, 0) || 1;
  return (
    <section className="rd-panel">
      <div className="rd-panel-head">
        <h2>{title}</h2>
      </div>
      <ul className="rd-breakdown">
        {rows.map((r) => (
          <li key={r.key}>
            <div className="line">
              <span>{r.label}</span>
              <strong>{money(r.value)}</strong>
            </div>
            <div className="track" aria-hidden="true">
              <div style={{ width: `${(r.value / total) * 100}%` }} />
            </div>
            <small>
              {r.orders} {r.orders === 1 ? 'order' : 'orders'} · {Math.round((r.value / total) * 100)}%
            </small>
          </li>
        ))}
      </ul>
    </section>
  );
}
