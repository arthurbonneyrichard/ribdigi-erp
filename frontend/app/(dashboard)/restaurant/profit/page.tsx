'use client';

/**
 * Restaurant profit and loss in plain words: sales, food and drink cost, gross profit,
 * running costs line by line, and profit — against the period before, with a six-month trend.
 * Reads the shared books (/accounting/profit-loss); downloads use the shared report export.
 */

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../../lib/api';
import { downloadAttachment } from '../../../../lib/attachments';
import { money, problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Preset = 'month' | 'last' | 'quarter' | 'year' | 'custom';
const COGS_CODE = '5000';

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function rangeFor(preset: Preset): [string, string] {
  const now = new Date();
  if (preset === 'last') return [iso(new Date(now.getFullYear(), now.getMonth() - 1, 1)), iso(new Date(now.getFullYear(), now.getMonth(), 0))];
  if (preset === 'quarter') return [iso(new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1)), iso(now)];
  if (preset === 'year') return [iso(new Date(now.getFullYear(), 0, 1)), iso(now)];
  return [iso(new Date(now.getFullYear(), now.getMonth(), 1)), iso(now)];
}

/** The same number of days immediately before [from, to]. */
function previousRange(from: string, to: string): [string, string] {
  const a = new Date(`${from}T00:00:00`);
  const b = new Date(`${to}T00:00:00`);
  const days = Math.round((b.getTime() - a.getTime()) / 86400000) + 1;
  const end = new Date(a);
  end.setDate(end.getDate() - 1);
  const start = new Date(end);
  start.setDate(start.getDate() - (days - 1));
  return [iso(start), iso(end)];
}

function pctOf(part: number, whole: number) {
  return whole > 0 ? Math.round((part / whole) * 1000) / 10 : null;
}

function niceDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function RestaurantProfitPage() {
  const [preset, setPreset] = useState<Preset>('month');
  const [from, setFrom] = useState(() => rangeFor('month')[0]);
  const [to, setTo] = useState(() => rangeFor('month')[1]);
  const [now, setNow] = useState<Row | null>(null);
  const [before, setBefore] = useState<Row | null>(null);
  const [trend, setTrend] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (a: string, b: string) => {
    setLoading(true);
    try {
      const [pa, pb] = previousRange(a, b);
      const [cur, prev] = await Promise.all([
        api(`/accounting/profit-loss?from_date=${a}&to_date=${b}`),
        api(`/accounting/profit-loss?from_date=${pa}&to_date=${pb}`),
      ]);
      setNow(cur?.data || null);
      setBefore(prev?.data || null);
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

  useEffect(() => {
    // Six calendar months, oldest first.
    const today = new Date();
    const months = Array.from({ length: 6 }, (_, i) => {
      const first = new Date(today.getFullYear(), today.getMonth() - (5 - i), 1);
      const last = i === 5 ? today : new Date(first.getFullYear(), first.getMonth() + 1, 0);
      return { label: first.toLocaleDateString(undefined, { month: 'short' }), from: iso(first), to: iso(last) };
    });
    Promise.all(months.map((mo) => api(`/accounting/profit-loss?from_date=${mo.from}&to_date=${mo.to}`).catch(() => null)))
      .then((rows) => setTrend(months.map((mo, i) => ({ ...mo, sales: Number(rows[i]?.data?.revenue || 0), profit: Number(rows[i]?.data?.net_profit || 0) }))))
      .catch(() => setTrend([]));
  }, []);

  function pick(next: Preset) {
    setPreset(next);
    if (next !== 'custom') {
      const [a, b] = rangeFor(next);
      setFrom(a);
      setTo(b);
    }
  }

  async function download(format: 'xlsx' | 'pdf') {
    setError('');
    try {
      const params = new URLSearchParams({ report_type: 'profit_loss', format, from_date: from, to_date: to });
      await downloadAttachment(`/reports/export?${params}`, `profit-and-loss-${from}-to-${to}.${format}`);
    } catch (err) {
      setError(problem(err));
    }
  }

  const revenue = Number(now?.revenue || 0);
  const cogs = Number(now?.cogs || 0);
  const gross = Number(now?.gross_profit || 0);
  const net = Number(now?.net_profit || 0);
  const running: Row[] = ((now?.accounts as Row[]) || [])
    .filter((a) => a.account_type !== 'income' && String(a.code) !== COGS_CODE && Number(a.balance) !== 0)
    .sort((a, b) => Number(b.balance) - Number(a.balance));
  const income: Row[] = ((now?.accounts as Row[]) || []).filter((a) => a.account_type === 'income' && Number(a.balance) !== 0);
  const prevBalance = (code: string) => Number(((before?.accounts as Row[]) || []).find((a) => String(a.code) === String(code))?.balance || 0);
  const foodPct = pctOf(cogs, revenue);
  const marginPct = pctOf(net, revenue);
  const maxTrend = Math.max(1, ...trend.map((t) => Math.abs(t.profit)), ...trend.map((t) => t.sales));

  function change(nowValue: number, beforeValue: number, goodWhenUp = true) {
    if (!before || Math.abs(beforeValue) < 0.005) return <span className="rd-change">—</span>;
    const diff = nowValue - beforeValue;
    const up = diff >= 0;
    const good = up === goodWhenUp;
    return (
      <span className={`rd-change ${good ? 'good' : 'bad'}`}>
        {up ? '▲' : '▼'} {money(Math.abs(diff))}
      </span>
    );
  }

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Profit and loss</h1>
          <p>What the restaurant earned and spent, and what is left.</p>
        </div>
        <div className="rd-head-actions">
          <button type="button" aria-label="Download profit and loss Excel" onClick={() => void download('xlsx')}>Excel</button>
          <button type="button" aria-label="Download profit and loss PDF" onClick={() => void download('pdf')}>PDF</button>
        </div>
      </header>

      <div className="rd-period" role="group" aria-label="Profit period">
        <div className="rd-chips">
          {([['month', 'This month'], ['last', 'Last month'], ['quarter', 'This quarter'], ['year', 'This year'], ['custom', 'Pick dates']] as const).map(([key, label]) => (
            <button key={key} type="button" className={preset === key ? 'on' : ''} aria-pressed={preset === key} onClick={() => pick(key)}>
              {label}
            </button>
          ))}
        </div>
        {preset === 'custom' ? (
          <div className="rd-dates">
            <input type="date" aria-label="Profit from date" value={from} max={to} onChange={(e) => e.target.value && setFrom(e.target.value)} />
            <span>to</span>
            <input type="date" aria-label="Profit to date" value={to} min={from} onChange={(e) => e.target.value && setTo(e.target.value)} />
          </div>
        ) : null}
      </div>

      {error ? <div className="rd-error" role="alert" onClick={() => setError('')}>{error}</div> : null}
      {loading && !now ? <div className="rd-empty">Working it out…</div> : null}

      {now ? (
        <div className={`rd-report${loading ? ' is-loading' : ''}`}>
          <div className="rd-kpis">
            <div className={`rd-kpi hero${net < 0 ? ' loss' : ''}`}>
              <span>{net < 0 ? 'Loss' : 'Profit'}</span>
              <strong>{money(Math.abs(net))}</strong>
              <small>{marginPct == null ? 'No sales yet' : `${marginPct}% of sales kept as profit`}</small>
            </div>
            <div className="rd-kpi">
              <span>Sales (before tax)</span>
              <strong>{money(revenue)}</strong>
              <small>
                {Number(before?.revenue || 0) > 0 ? <>{change(revenue, Number(before?.revenue || 0))} on the period before</> : 'No sales in the period before'}
              </small>
            </div>
            <div className="rd-kpi">
              <span>Food and drink cost</span>
              <strong>{foodPct == null ? '—' : `${foodPct}%`}</strong>
              <small className={foodPct != null && foodPct > 35 ? 'rd-warn-text' : ''}>
                {foodPct == null ? 'of sales' : foodPct > 35 ? 'of sales · aim for 35% or less' : 'of sales · within the usual 28–35%'}
              </small>
            </div>
            <div className="rd-kpi">
              <span>Running costs</span>
              <strong>{money(now.operating_expenses)}</strong>
              <small>{pctOf(Number(now.operating_expenses || 0), revenue) ?? '—'}% of sales</small>
            </div>
          </div>

          <section className="rd-panel">
            <div className="rd-panel-head">
              <h2>The statement</h2>
              <small>
                {niceDate(from)} to {niceDate(to)}, against the {Math.round((new Date(`${to}T00:00:00`).getTime() - new Date(`${from}T00:00:00`).getTime()) / 86400000) + 1} days before
              </small>
            </div>
            <div className="rd-table-wrap">
              <table className="rd-table rd-statement" aria-label="Profit and loss statement">
                <thead>
                  <tr>
                    <th />
                    <th className="num">This period</th>
                    <th className="num col-sales">% of sales</th>
                    <th className="num">Period before</th>
                    <th className="num">Change</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="group">
                    <td>Sales</td>
                    <td className="num">{money(revenue)}</td>
                    <td className="num col-sales">100%</td>
                    <td className="num">{money(before?.revenue)}</td>
                    <td className="num">{change(revenue, Number(before?.revenue || 0))}</td>
                  </tr>
                  {income.length > 1
                    ? income.map((a) => (
                        <tr key={a.code} className="sub">
                          <td>{a.name}</td>
                          <td className="num">{money(a.balance)}</td>
                          <td className="num col-sales">{pctOf(Number(a.balance), revenue) ?? '—'}%</td>
                          <td className="num">{money(prevBalance(a.code))}</td>
                          <td className="num">{change(Number(a.balance), prevBalance(a.code))}</td>
                        </tr>
                      ))
                    : null}
                  <tr>
                    <td>Food and drink cost</td>
                    <td className="num">− {money(cogs)}</td>
                    <td className="num col-sales">{foodPct ?? '—'}%</td>
                    <td className="num">− {money(before?.cogs)}</td>
                    <td className="num">{change(cogs, Number(before?.cogs || 0), false)}</td>
                  </tr>
                  <tr className="group">
                    <td>Gross profit</td>
                    <td className="num">{money(gross)}</td>
                    <td className="num col-sales">{pctOf(gross, revenue) ?? '—'}%</td>
                    <td className="num">{money(before?.gross_profit)}</td>
                    <td className="num">{change(gross, Number(before?.gross_profit || 0))}</td>
                  </tr>
                  <tr className="label">
                    <td colSpan={5}>Running costs</td>
                  </tr>
                  {running.length === 0 ? (
                    <tr className="sub">
                      <td>None recorded</td>
                      <td className="num">{money(0)}</td>
                      <td className="num col-sales" />
                      <td className="num" />
                      <td className="num" />
                    </tr>
                  ) : null}
                  {running.map((a) => (
                    <tr key={a.code} className="sub">
                      <td>{a.name}</td>
                      <td className="num">− {money(a.balance)}</td>
                      <td className="num col-sales">{pctOf(Number(a.balance), revenue) ?? '—'}%</td>
                      <td className="num">− {money(prevBalance(a.code))}</td>
                      <td className="num">{change(Number(a.balance), prevBalance(a.code), false)}</td>
                    </tr>
                  ))}
                  <tr className={`total${net < 0 ? ' loss' : ''}`}>
                    <td>{net < 0 ? 'Loss' : 'Profit'}</td>
                    <td className="num">{money(net)}</td>
                    <td className="num col-sales">{marginPct ?? '—'}%</td>
                    <td className="num">{money(before?.net_profit)}</td>
                    <td className="num">{change(net, Number(before?.net_profit || 0))}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="rd-hint-line">
              Food and drink cost is what the ingredients of each sold dish cost. Waste, gas, wages and the rest are running costs. See
              them line by line under <Link href="/restaurant/expenses">Expenses</Link>; dish by dish under <Link href="/restaurant/reports">Reports</Link>.
            </p>
          </section>

          {trend.length ? (
            <section className="rd-panel">
              <div className="rd-panel-head">
                <h2>Last six months</h2>
                <small>Sales and profit each month. Hover a month for the figures.</small>
              </div>
              <div className="rd-trend" role="img" aria-label={`Last six months: ${trend.map((t) => `${t.label} sales ${money(t.sales)}, profit ${money(t.profit)}`).join('; ')}`}>
                {trend.map((t) => (
                  <div key={t.from} className="rd-trend-col" tabIndex={0} aria-label={`${t.label}: sales ${money(t.sales)}, profit ${money(t.profit)}`}>
                    <span className="rd-bar-tip">
                      {t.label}: sales {money(t.sales)} · {t.profit < 0 ? 'loss' : 'profit'} {money(Math.abs(t.profit))}
                    </span>
                    <div className="bars">
                      <div className="sales" style={{ height: `${(t.sales / maxTrend) * 100}%` }} />
                      <div className={`profit${t.profit < 0 ? ' loss' : ''}`} style={{ height: `${(Math.abs(t.profit) / maxTrend) * 100}%` }} />
                    </div>
                    <small>{t.label}</small>
                  </div>
                ))}
              </div>
              <div className="rd-legend-row" aria-hidden="true">
                <span><i className="sales" /> Sales</span>
                <span><i className="profit" /> Profit</span>
                <span><i className="loss" /> Loss</span>
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
