'use client';

/**
 * Sales, discounts, refunds and voids by cashier. Each desk passes its own endpoint, so
 * retail reads till sales and restaurant reads restaurant orders.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { formatMoney, formatWhen, plainLabel } from '../lib/format';
import './cashier-performance.css';

type Row = Record<string, any>;
type Period = 'day' | 'week' | 'month';

const PERIODS: [Period, string][] = [
  ['day', 'Daily'],
  ['week', 'Weekly'],
  ['month', 'Monthly'],
];

function isoDay(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export default function CashierPerformance({
  base,
  from,
  to,
  storeId,
  showDiscounts = true,
}: {
  base: string;
  from?: string;
  to?: string;
  storeId?: string;
  showDiscounts?: boolean;
}) {
  const [period, setPeriod] = useState<Period>('day');
  const [fromDate, setFromDate] = useState(() => from || isoDay(new Date(Date.now() - 29 * 86400000)));
  const [toDate, setToDate] = useState(() => to || isoDay(new Date()));
  const [cashier, setCashier] = useState('');
  const [data, setData] = useState<Row | null>(null);
  const [detail, setDetail] = useState<Row | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const controlled = from !== undefined || to !== undefined;
  const start = controlled ? from || '' : fromDate;
  const end = controlled ? to || '' : toDate;

  const query = useCallback(
    (extra: Record<string, string> = {}) => {
      const params = new URLSearchParams();
      if (start) params.set('from_date', start);
      if (end) params.set('to_date', end);
      if (storeId) params.set('store_id', storeId);
      if (cashier) params.set('cashier_id', cashier);
      Object.entries(extra).forEach(([key, value]) => params.set(key, value));
      return params.toString();
    },
    [cashier, end, start, storeId]
  );

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError('');
    Promise.all([api(`${base}?${query({ period })}`), api(`${base}/transactions?${query({ limit: '200' })}`)])
      .then(([summary, lines]) => {
        if (!live) return;
        setData(summary.data);
        setDetail(lines.data);
      })
      .catch((err) => {
        if (live) setError(err instanceof Error ? err.message : 'Could not load this report.');
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [base, period, query]);

  const cashiers: Row[] = data?.cashiers || [];
  const periods: Row[] = data?.periods || [];
  const totals: Row = data?.totals || {};
  const pickable = useMemo(() => cashiers.map((c) => ({ id: c.cashier_id, name: c.name })), [cashiers]);

  return (
    <div className="cperf">
      <div className="cperf-controls">
        <div className="cperf-chips" role="group" aria-label="Group cashier sales by">
          {PERIODS.map(([key, label]) => (
            <button key={key} type="button" className={period === key ? 'on' : ''} aria-pressed={period === key} onClick={() => setPeriod(key)}>
              {label}
            </button>
          ))}
        </div>
        {controlled ? null : (
          <>
            <label>
              From
              <input type="date" aria-label="Cashier report from date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
            </label>
            <label>
              To
              <input type="date" aria-label="Cashier report to date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
            </label>
          </>
        )}
        <label>
          Cashier
          <select aria-label="Cashier filter" value={cashier} onChange={(e) => setCashier(e.target.value)}>
            <option value="">All cashiers</option>
            {pickable.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? <p className="cperf-error" role="alert">{error}</p> : null}
      {loading && !data ? <p className="cperf-note">Loading…</p> : null}
      {data && cashiers.length === 0 ? <p className="cperf-note">No till sales in this period.</p> : null}

      {cashiers.length > 0 ? (
        <>
          <div className="cperf-scroll">
            <table className="cperf-table">
              <caption>Sales by cashier</caption>
              <thead>
                <tr>
                  <th scope="col">Cashier</th>
                  <th scope="col" className="num">Sales</th>
                  <th scope="col" className="num">Total</th>
                  <th scope="col" className="num">Average</th>
                  {showDiscounts ? <th scope="col" className="num">Discounts</th> : null}
                  <th scope="col" className="num">Refunds</th>
                  <th scope="col" className="num">Voids</th>
                </tr>
              </thead>
              <tbody>
                {cashiers.map((row) => (
                  <tr key={row.cashier_id}>
                    <th scope="row">{row.name}</th>
                    <td className="num">{row.sale_count}</td>
                    <td className="num">{formatMoney(row.sales_total)}</td>
                    <td className="num">{formatMoney(row.avg_sale)}</td>
                    {showDiscounts ? <td className="num">{formatMoney(row.discounts)}</td> : null}
                    <td className="num">
                      {row.refund_count} · {formatMoney(row.refunds_total)}
                    </td>
                    <td className="num">{row.void_count}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">Total</th>
                  <td className="num">{totals.sale_count}</td>
                  <td className="num">{formatMoney(totals.sales_total)}</td>
                  <td />
                  {showDiscounts ? <td className="num">{formatMoney(totals.discounts)}</td> : null}
                  <td className="num">{formatMoney(totals.refunds_total)}</td>
                  <td className="num">{totals.void_count}</td>
                </tr>
              </tfoot>
            </table>
          </div>

          <div className="cperf-scroll">
            <table className="cperf-table">
              <caption>{PERIODS.find(([key]) => key === period)?.[1]} performance</caption>
              <thead>
                <tr>
                  <th scope="col">{period === 'week' ? 'Week of' : period === 'month' ? 'Month' : 'Day'}</th>
                  <th scope="col">Cashier</th>
                  <th scope="col" className="num">Sales</th>
                  <th scope="col" className="num">Total</th>
                </tr>
              </thead>
              <tbody>
                {periods.map((row) => (
                  <tr key={`${row.period}-${row.cashier_id}`}>
                    <td>{row.period}</td>
                    <td>{row.name}</td>
                    <td className="num">{row.sale_count}</td>
                    <td className="num">{formatMoney(row.sales_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {(detail?.transactions || []).length > 0 ? (
        <div className="cperf-scroll">
          <table className="cperf-table">
            <caption>Transactions</caption>
            <thead>
              <tr>
                <th scope="col">Reference</th>
                <th scope="col">When</th>
                <th scope="col">Cashier</th>
                <th scope="col">Till</th>
                <th scope="col">Paid by</th>
                <th scope="col" className="num">Total</th>
              </tr>
            </thead>
            <tbody>
              {detail?.transactions.map((row: Row) => (
                <tr key={row.id}>
                  <td>{row.reference}</td>
                  <td>{formatWhen(row.at)}</td>
                  <td>
                    {row.name}
                    {row.started_by ? <small> · started by {row.started_by}</small> : null}
                  </td>
                  <td>{row.terminal || '—'}</td>
                  <td>{plainLabel(row.payment_method || '')}</td>
                  <td className="num">{formatMoney(row.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {(detail?.activity || []).length > 0 ? (
        <div className="cperf-scroll">
          <table className="cperf-table">
            <caption>Sensitive activity</caption>
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Cashier</th>
                <th scope="col">What happened</th>
                <th scope="col">Reference</th>
                <th scope="col" className="num">Amount</th>
              </tr>
            </thead>
            <tbody>
              {detail?.activity.map((row: Row, index: number) => (
                <tr key={`${row.at}-${index}`}>
                  <td>{formatWhen(row.at)}</td>
                  <td>{row.name}</td>
                  <td>{row.label}</td>
                  <td>{row.reference || '—'}</td>
                  <td className="num">{row.amount === null || row.amount === undefined ? '—' : formatMoney(row.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
