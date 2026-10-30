'use client';

/**
 * Restaurant Bills: every bill (restaurant orders), the day's takings, refunds,
 * and the till shifts with their cash counts. Retail invoices never show here.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import {
  LIVE_STATUSES,
  METHOD_WORDS,
  MODE_WORDS,
  STATUS_WORDS,
  dayAndTime,
  money,
  parseWhen,
  problem,
  type Row,
  whereWords,
} from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Range = 'today' | 'yesterday' | 'week' | 'all';
type Show = 'paid' | 'open' | 'refunded' | 'cancelled' | 'all';

const RANGES: { id: Range; label: string }[] = [
  { id: 'today', label: 'Today' },
  { id: 'yesterday', label: 'Yesterday' },
  { id: 'week', label: 'Last 7 days' },
  { id: 'all', label: 'All' },
];

const SHOWS: { id: Show; label: string }[] = [
  { id: 'paid', label: 'Paid' },
  { id: 'open', label: 'Not paid yet' },
  { id: 'refunded', label: 'Refunded' },
  { id: 'cancelled', label: 'Cancelled' },
  { id: 'all', label: 'Everything' },
];

function inRange(value: unknown, range: Range): boolean {
  if (range === 'all') return true;
  const date = parseWhen(value);
  if (!date) return false;
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  if (range === 'today') return date >= start;
  if (range === 'yesterday') {
    const from = new Date(start.getTime() - 86400000);
    return date >= from && date < start;
  }
  return date >= new Date(start.getTime() - 6 * 86400000);
}

function showOf(status: string): Show {
  if (status === 'completed') return 'paid';
  if (status === 'refunded') return 'refunded';
  if (status === 'cancelled' || status === 'voided') return 'cancelled';
  return 'open';
}

export default function RestaurantBillsPage() {
  const [tab, setTab] = useState<'bills' | 'shifts'>('bills');
  const [orders, setOrders] = useState<Row[]>([]);
  const [tables, setTables] = useState<Row[]>([]);
  const [shifts, setShifts] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [range, setRange] = useState<Range>('today');
  const [show, setShow] = useState<Show>('paid');
  const [search, setSearch] = useState('');
  const [openId, setOpenId] = useState('');

  const load = useCallback(async () => {
    try {
      const [orderRes, tableRes, shiftRes] = await Promise.all([
        api('/restaurant/orders'),
        api('/restaurant/tables'),
        api('/restaurant/till/shifts').catch(() => ({ data: [] })),
      ]);
      setOrders(orderRes?.data || []);
      setTables(tableRes?.data || []);
      setShifts(shiftRes?.data || []);
      setError('');
    } catch (err) {
      setError(problem(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const inDays = useMemo(
    () => orders.filter((o) => inRange(o.completed_at || o.opened_at, range)),
    [orders, range],
  );

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return inDays
      .filter((o) => show === 'all' || showOf(String(o.status)) === show)
      .filter((o) => {
        if (!q) return true;
        const hay = [o.order_number, o.customer_name, whereWords(o, tables), o.phone].join(' ').toLowerCase();
        return hay.includes(q);
      })
      .sort((a, b) => String(b.completed_at || b.opened_at).localeCompare(String(a.completed_at || a.opened_at)));
  }, [inDays, show, search, tables]);

  const paid = inDays.filter((o) => o.status === 'completed');
  const takings = paid.reduce((sum, o) => sum + Number(o.total_amount || 0), 0);
  const byMethod = (method: string) =>
    paid.filter((o) => o.payment_method === method).reduce((sum, o) => sum + Number(o.total_amount || 0), 0);
  const refunds = inDays.filter((o) => o.status === 'refunded').reduce((sum, o) => sum + Number(o.total_amount || 0), 0);
  const selected = orders.find((o) => o.id === openId) || null;

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Bills</h1>
          <p>Every bill from the restaurant, what came in, and each till shift.</p>
        </div>
        <div className="rd-head-actions">
          <div className="rd-tabs" role="tablist" aria-label="Bills or shifts">
            <button type="button" role="tab" aria-selected={tab === 'bills'} className={tab === 'bills' ? 'on' : ''} onClick={() => setTab('bills')}>
              Bills
            </button>
            <button type="button" role="tab" aria-selected={tab === 'shifts'} className={tab === 'shifts' ? 'on' : ''} onClick={() => setTab('shifts')}>
              Till shifts
            </button>
          </div>
        </div>
      </header>

      {notice ? (
        <div className="rd-notice" role="status" onClick={() => setNotice('')}>
          {notice}
        </div>
      ) : null}
      {error ? (
        <div className="rd-error" role="alert">
          {error}
        </div>
      ) : null}

      {tab === 'bills' ? (
        <>
          <div className="rd-chips" role="tablist" aria-label="Days">
            {RANGES.map((r) => (
              <button key={r.id} type="button" role="tab" aria-selected={range === r.id} className={range === r.id ? 'on' : ''} onClick={() => setRange(r.id)}>
                {r.label}
              </button>
            ))}
          </div>

          <div className="rd-kpis">
            <div className="rd-kpi hero">
              <span>Takings</span>
              <strong>{money(takings)}</strong>
            </div>
            <div className="rd-kpi">
              <span>Bills paid</span>
              <strong>{paid.length}</strong>
            </div>
            <div className="rd-kpi">
              <span>Cash</span>
              <strong>{money(byMethod('cash'))}</strong>
            </div>
            <div className="rd-kpi">
              <span>Card</span>
              <strong>{money(byMethod('card'))}</strong>
            </div>
            <div className="rd-kpi">
              <span>Mobile Money and wallet</span>
              <strong>{money(byMethod('mobile_money') + byMethod('wallet'))}</strong>
            </div>
            <div className="rd-kpi">
              <span>Refunded</span>
              <strong>{money(refunds)}</strong>
            </div>
          </div>

          <div className="rd-head">
            <div className="rd-chips" role="tablist" aria-label="Which bills">
              {SHOWS.map((s) => (
                <button key={s.id} type="button" role="tab" aria-selected={show === s.id} className={show === s.id ? 'on' : ''} onClick={() => setShow(s.id)}>
                  {s.label}
                </button>
              ))}
            </div>
            <div className="rd-head-actions">
              <input
                className="rd-search"
                type="search"
                placeholder="Search bill, guest or table"
                aria-label="Search bills"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          <div className="rd-list" aria-label="Bills">
            {loading ? <div className="rd-empty">Loading bills…</div> : null}
            {!loading && shown.length === 0 ? (
              <div className="rd-empty">
                <strong>No bills here</strong>
                Try another day or another filter.
              </div>
            ) : null}
            {shown.map((o) => {
              const status = String(o.status);
              return (
                <button key={o.id} type="button" className="rd-row" aria-label={`Bill ${o.order_number}`} onClick={() => setOpenId(o.id)}>
                  <span className="when">{dayAndTime(o.completed_at || o.opened_at)}</span>
                  <span className="who">
                    <strong>{whereWords(o, tables)}</strong>
                    <small>
                      {o.order_number} · {MODE_WORDS[o.service_mode] || o.service_mode}
                    </small>
                  </span>
                  <span className="hide-sm">
                    {status === 'completed' || status === 'refunded' ? (
                      <span className="rd-pill grey">{METHOD_WORDS[o.payment_method] || o.payment_method}</span>
                    ) : null}
                  </span>
                  <span className="hide-sm">
                    <span
                      className={`rd-pill ${
                        status === 'completed' ? '' : status === 'refunded' || showOf(status) === 'cancelled' ? 'bad' : 'wait'
                      }`}
                    >
                      {STATUS_WORDS[status] || status}
                    </span>
                  </span>
                  <span className="amt">{money(o.total_amount)}</span>
                </button>
              );
            })}
          </div>
        </>
      ) : (
        <ShiftList shifts={shifts} loading={loading} />
      )}

      {selected ? (
        <BillDrawer
          order={selected}
          tables={tables}
          onClose={() => setOpenId('')}
          onChanged={async (message) => {
            setNotice(message);
            await load();
          }}
        />
      ) : null}
    </div>
  );
}

function ShiftList({ shifts, loading }: { shifts: Row[]; loading: boolean }) {
  return (
    <div className="rd-list" aria-label="Till shifts">
      {loading ? <div className="rd-empty">Loading shifts…</div> : null}
      {!loading && shifts.length === 0 ? (
        <div className="rd-empty">
          <strong>No till shifts yet</strong>
          Cashiers open a shift on the restaurant till before taking money.
        </div>
      ) : null}
      {shifts.map((s) => {
        const diff = s.variance === null || s.variance === undefined ? null : Number(s.variance);
        return (
          <div key={s.id} className="rd-row" style={{ cursor: 'default' }}>
            <span className="when">{dayAndTime(s.opened_at)}</span>
            <span className="who">
              <strong>{s.cashier || 'Cashier'}</strong>
              <small>
                {s.shift_number} · {s.sale_count} bills · {money(s.total_sales)}
              </small>
            </span>
            <span className="hide-sm">
              <span className="rd-pill grey">Cash expected {money(s.expected_cash)}</span>
            </span>
            <span className="hide-sm">
              {s.status === 'open' ? (
                <span className="rd-pill wait">Still open</span>
              ) : diff === 0 ? (
                <span className="rd-pill">Exact</span>
              ) : diff !== null && diff > 0 ? (
                <span className="rd-pill wait">Over {money(diff)}</span>
              ) : (
                <span className="rd-pill bad">Short {money(-(diff || 0))}</span>
              )}
            </span>
            <span className="amt">{s.counted_cash === null || s.counted_cash === undefined ? '—' : money(s.counted_cash)}</span>
          </div>
        );
      })}
    </div>
  );
}

function BillDrawer({
  order,
  tables,
  onClose,
  onChanged,
}: {
  order: Row;
  tables: Row[];
  onClose: () => void;
  onChanged: (message: string) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState(false);
  const status = String(order.status);

  async function refund() {
    setBusy(true);
    setError('');
    try {
      await api(`/restaurant/orders/${order.id}/refund`, { method: 'POST' });
      setConfirming(false);
      await onChanged(`Bill ${order.order_number} refunded`);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={`Bill ${order.order_number}`} onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>Bill {order.order_number}</h2>
            <p>
              {whereWords(order, tables)} · {dayAndTime(order.completed_at || order.opened_at)}
            </p>
          </div>
          <button type="button" className="rd-link" aria-label="Close bill" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="rd-facts">
          <span className={`rd-pill ${status === 'completed' ? '' : 'wait'}`}>{STATUS_WORDS[status] || status}</span>
          {status === 'completed' || status === 'refunded' ? (
            <span className="rd-pill grey">{METHOD_WORDS[order.payment_method] || order.payment_method}</span>
          ) : null}
          {order.server ? <span className="rd-pill grey">Server: {order.server}</span> : null}
          {order.phone ? <span className="rd-pill grey">{order.phone}</span> : null}
        </div>

        <section className="rd-section" aria-label="Dishes">
          <h3>Dishes</h3>
          {(order.items || []).map((item: Row) => (
            <div key={item.id} className="rd-item">
              <span className="q">{Number(item.quantity)}×</span>
              <div>
                {item.name}
                {item.modifiers?.length || item.note ? (
                  <small>{[...(item.modifiers || []), item.note].filter(Boolean).join(' · ')}</small>
                ) : null}
              </div>
              <div className="right">{money(item.line_total ?? Number(item.quantity) * Number(item.unit_price))}</div>
            </div>
          ))}
        </section>

        <dl className="rd-sum">
          <div>
            <dt>Dishes</dt>
            <dd>{money(order.subtotal)}</dd>
          </div>
          {Number(order.service_amount || 0) > 0 ? (
            <div>
              <dt>Service</dt>
              <dd>{money(order.service_amount)}</dd>
            </div>
          ) : null}
          {Number(order.tax_amount || 0) > 0 ? (
            <div>
              <dt>Tax</dt>
              <dd>{money(order.tax_amount)}</dd>
            </div>
          ) : null}
          <div className="grand">
            <dt>Total</dt>
            <dd>{money(order.total_amount)}</dd>
          </div>
        </dl>

        {error ? (
          <div className="rd-error" role="alert">
            {error}
          </div>
        ) : null}

        {confirming ? (
          <div className="rd-confirm" role="alert">
            Refund {money(order.total_amount)} to the guest? The dishes go back into stock and the sale comes off the
            books.
            {order.payment_method === 'cash' ? ' The cash comes out of your open till drawer.' : ''}
            <div>
              <button type="button" onClick={() => setConfirming(false)}>
                Keep the bill
              </button>
              <button type="button" className="rd-danger" aria-label="Yes, refund the bill" disabled={busy} onClick={() => void refund()}>
                {busy ? 'Refunding…' : 'Yes, refund'}
              </button>
            </div>
          </div>
        ) : null}

        <div className="rd-actions">
          {LIVE_STATUSES.has(status) ? (
            <button
              type="button"
              className="rd-primary full"
              aria-label="Take payment"
              onClick={() => (window.location.href = `/restaurant/till?order=${encodeURIComponent(order.id)}&pay=1`)}
            >
              Take payment on the till
            </button>
          ) : null}
          {status === 'completed' ? (
            <>
              <button type="button" aria-label="Print bill" onClick={() => window.print()}>
                Print
              </button>
              <button type="button" className="rd-danger" aria-label="Refund bill" onClick={() => setConfirming(true)}>
                Refund
              </button>
            </>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
