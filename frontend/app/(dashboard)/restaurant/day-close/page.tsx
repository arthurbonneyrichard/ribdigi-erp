'use client';

/**
 * End of day: one sheet for one day — takings by how guests paid, each till shift's cash count,
 * refunds, cash spent, waste and anything still open. Printable for the owner's file.
 */

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../../lib/api';
import { METHOD_WORDS, money, problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function shift(dateText: string, days: number) {
  const d = new Date(`${dateText}T00:00:00`);
  d.setDate(d.getDate() + days);
  return iso(d);
}

function clock(value: unknown) {
  if (!value) return '';
  const d = new Date(String(value));
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

export default function RestaurantDayClosePage() {
  const today = iso(new Date());
  const [date, setDate] = useState(today);
  const [data, setData] = useState<Row | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (day: string) => {
    setLoading(true);
    try {
      const res = await api(`/restaurant/reports/day?date=${day}`);
      setData(res?.data || null);
      setError('');
    } catch (err) {
      setError(problem(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(date);
  }, [load, date]);

  const totals: Row = data?.totals || {};
  const shifts: Row[] = data?.shifts || [];
  const openOrders: Row[] = data?.open_orders || [];
  const variance = Number(data?.cash_variance || 0);
  const longDate = new Date(`${date}T00:00:00`).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  return (
    <div className="rdesk rd-dayclose">
      <header className="rd-head">
        <div>
          <h1>End of day</h1>
          <p>{longDate}</p>
        </div>
        <div className="rd-head-actions rd-noprint">
          <button type="button" aria-label="Previous day" onClick={() => setDate(shift(date, -1))}>←</button>
          <input type="date" className="rd-date-pick" aria-label="Day" value={date} max={today} onChange={(e) => e.target.value && setDate(e.target.value)} />
          <button type="button" aria-label="Next day" disabled={date >= today} onClick={() => setDate(shift(date, 1))}>→</button>
          <button type="button" className="rd-primary" aria-label="Print day sheet" onClick={() => window.print()}>Print</button>
        </div>
      </header>

      {error ? <div className="rd-error" role="alert">{error}</div> : null}
      {loading && !data ? <div className="rd-empty">Loading the day…</div> : null}

      {data ? (
        <div className={`rd-report${loading ? ' is-loading' : ''}`}>
          <div className={`rd-close-status${data.ready_to_close ? ' ok' : ''}`} role="status">
            <strong>{data.ready_to_close ? '✓ Day is closed off' : 'Still to do before you close'}</strong>
            {data.ready_to_close ? (
              <span>Every till shift is counted and every bill is paid.</span>
            ) : (
              <ul>
                {data.open_shifts ? (
                  <li>
                    {data.open_shifts} till {data.open_shifts === 1 ? 'shift is' : 'shifts are'} still open. <Link href="/restaurant/till">Count the cash and close it</Link>.
                  </li>
                ) : null}
                {openOrders.length ? (
                  <li>
                    {openOrders.length} {openOrders.length === 1 ? 'bill is' : 'bills are'} not paid ({money(openOrders.reduce((s, o) => s + Number(o.total_amount || 0), 0))}). <Link href="/restaurant/orders">Take payment or cancel</Link>.
                  </li>
                ) : null}
              </ul>
            )}
          </div>

          <div className="rd-kpis">
            <div className="rd-kpi hero">
              <span>Takings</span>
              <strong>{money(totals.sales)}</strong>
              <small>{totals.orders} paid {totals.orders === 1 ? 'bill' : 'bills'} · average {money(totals.average_order)}</small>
            </div>
            <div className="rd-kpi">
              <span>Cash count</span>
              <strong className={variance < 0 ? 'rd-bad-text' : ''}>{variance === 0 ? 'Exact' : `${variance > 0 ? '+' : '−'}${money(Math.abs(variance))}`}</strong>
              <small>{variance < 0 ? 'short' : variance > 0 ? 'over' : shifts.some((s) => s.status === 'closed') ? 'all counted shifts match' : 'no shift counted yet'}</small>
            </div>
            <div className="rd-kpi">
              <span>Refunds</span>
              <strong>{money(totals.refunds)}</strong>
              <small>{totals.refunded_orders} {totals.refunded_orders === 1 ? 'bill' : 'bills'}</small>
            </div>
            <div className="rd-kpi">
              <span>Cash spent</span>
              <strong>{money(data.cash_expenses_total)}</strong>
              <small>approved cash expenses</small>
            </div>
            <div className="rd-kpi">
              <span>Waste</span>
              <strong>{money(totals.waste_cost)}</strong>
              <small>at cost</small>
            </div>
          </div>

          <div className="rd-split">
            <section className="rd-panel">
              <div className="rd-panel-head">
                <h2>How guests paid</h2>
              </div>
              <ul className="rd-docs rd-sheet-list">
                {(data.by_payment_method as Row[]).length === 0 ? <li><span>No paid bills.</span></li> : null}
                {(data.by_payment_method as Row[]).map((r) => (
                  <li key={r.payment_method}>
                    <span>{METHOD_WORDS[r.payment_method] || r.payment_method}</span>
                    <span>{r.orders} {r.orders === 1 ? 'bill' : 'bills'}</span>
                    <span />
                    <strong>{money(r.sales)}</strong>
                  </li>
                ))}
              </ul>
            </section>
            <section className="rd-panel">
              <div className="rd-panel-head">
                <h2>Who took the bills</h2>
              </div>
              <ul className="rd-docs rd-sheet-list">
                {(data.by_staff as Row[]).length === 0 ? <li><span>No paid bills.</span></li> : null}
                {(data.by_staff as Row[]).map((r) => (
                  <li key={r.user_id || 'online'}>
                    <span>{r.name}</span>
                    <span>{r.orders} {r.orders === 1 ? 'bill' : 'bills'}</span>
                    <span />
                    <strong>{money(r.sales)}</strong>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <section className="rd-panel">
            <div className="rd-panel-head">
              <h2>Till shifts and cash</h2>
              <small>Expected cash = float + cash bills + cash put in − cash taken out − cash refunds.</small>
            </div>
            {shifts.length === 0 ? (
              <p className="rd-hint-line">No till shift that day.</p>
            ) : (
              <div className="rd-table-wrap">
                <table className="rd-table" aria-label="Till shifts">
                  <thead>
                    <tr>
                      <th>Shift</th>
                      <th>Cashier</th>
                      <th className="num">Float</th>
                      <th className="num">Cash bills</th>
                      <th className="num">In / out</th>
                      <th className="num">Expected</th>
                      <th className="num">Counted</th>
                      <th className="num">Over / short</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shifts.map((s) => (
                      <tr key={s.id}>
                        <td>
                          <strong>{s.shift_number}</strong>
                          <br />
                          <small>
                            {clock(s.opened_at)}–{s.closed_at ? clock(s.closed_at) : 'still open'}
                          </small>
                        </td>
                        <td>{s.cashier || '—'}</td>
                        <td className="num">{money(s.opening_cash)}</td>
                        <td className="num">{money(s.cash_sales)}</td>
                        <td className="num">
                          +{money(s.cash_in)} / −{money(Number(s.cash_out || 0) + Number(s.cash_refunds || 0))}
                        </td>
                        <td className="num">{money(s.expected_cash)}</td>
                        <td className="num">{s.counted_cash == null ? <span className="rd-pill wait">Not counted</span> : money(s.counted_cash)}</td>
                        <td className={`num strong${Number(s.variance) < 0 ? ' rd-bad-text' : ''}`}>
                          {s.variance == null ? '—' : Number(s.variance) === 0 ? 'Exact' : `${Number(s.variance) > 0 ? '+' : '−'}${money(Math.abs(Number(s.variance)))}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {shifts.some((s) => s.notes) ? (
              <p className="rd-hint-line">Notes: {shifts.filter((s) => s.notes).map((s) => `${s.shift_number}: ${s.notes}`).join(' · ')}</p>
            ) : null}
          </section>

          <div className="rd-split">
            <section className="rd-panel">
              <div className="rd-panel-head">
                <h2>Best sellers</h2>
              </div>
              <ul className="rd-docs rd-sheet-list">
                {(data.top_dishes as Row[]).length === 0 ? <li><span>Nothing sold.</span></li> : null}
                {(data.top_dishes as Row[]).map((d) => (
                  <li key={d.product_id}>
                    <span>{d.name}</span>
                    <span>{Number(d.quantity)} sold</span>
                    <span />
                    <strong>{money(d.sales)}</strong>
                  </li>
                ))}
              </ul>
            </section>
            <section className="rd-panel">
              <div className="rd-panel-head">
                <h2>Cash spent and waste</h2>
              </div>
              <ul className="rd-docs rd-sheet-list">
                {(data.cash_expenses as Row[]).map((e) => (
                  <li key={e.id}>
                    <span>{e.payee || e.category}</span>
                    <span>{e.description || e.category}</span>
                    <span />
                    <strong>{money(e.amount)}</strong>
                  </li>
                ))}
                {(data.waste as Row[]).map((w) => (
                  <li key={w.product_id}>
                    <span>Waste: {w.name}</span>
                    <span>{Number(w.quantity)}</span>
                    <span />
                    <strong>{money(w.cost)}</strong>
                  </li>
                ))}
                {!(data.cash_expenses as Row[]).length && !(data.waste as Row[]).length ? <li><span>None.</span></li> : null}
              </ul>
            </section>
          </div>

          {openOrders.length ? (
            <section className="rd-panel">
              <div className="rd-panel-head">
                <h2>Bills not paid</h2>
              </div>
              <ul className="rd-docs rd-sheet-list">
                {openOrders.map((o) => (
                  <li key={o.id}>
                    <span>{o.order_number}</span>
                    <span>{o.customer_name || 'Guest'} · opened {clock(o.created_at)}</span>
                    <span />
                    <strong>{money(o.total_amount)}</strong>
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
