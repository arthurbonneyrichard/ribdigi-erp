'use client';

/**
 * Restaurant Orders: what is happening right now, in three columns
 * (not sent yet, in the kitchen, ready to serve). Tap an order to see its dishes,
 * send it, add dishes or take payment on the restaurant till.
 */

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import {
  LIVE_STATUSES,
  METHOD_WORDS,
  MODE_WORDS,
  PREP_WORDS,
  STATUS_WORDS,
  dishSummary,
  minutesSince,
  money,
  problem,
  type Row,
  waitWords,
  whereWords,
} from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Lane = 'open' | 'cooking' | 'ready';

const LANES: { id: Lane; title: string; empty: string }[] = [
  { id: 'open', title: 'Not sent yet', empty: 'Orders being taken show here.' },
  { id: 'cooking', title: 'In the kitchen', empty: 'Nothing cooking right now.' },
  { id: 'ready', title: 'Ready to serve', empty: 'Ready dishes show here.' },
];

const MODE_FILTERS = [
  { id: '', label: 'All' },
  { id: 'dine_in', label: 'Dine in' },
  { id: 'takeaway', label: 'Takeaway' },
  { id: 'delivery', label: 'Delivery' },
];

// Waiting longer than this turns the timer amber.
const LATE_MINUTES = 25;

function laneOf(status: string): Lane {
  if (status === 'ready') return 'ready';
  if (status === 'sent' || status === 'preparing') return 'cooking';
  return 'open';
}

export default function RestaurantOrdersPage() {
  const [orders, setOrders] = useState<Row[]>([]);
  const [tables, setTables] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [mode, setMode] = useState('');
  const [search, setSearch] = useState('');
  const [openId, setOpenId] = useState('');
  const [now, setNow] = useState(() => Date.now());

  const load = useCallback(async () => {
    try {
      const [orderRes, tableRes] = await Promise.all([api('/restaurant/orders'), api('/restaurant/tables')]);
      setOrders(orderRes?.data || []);
      setTables(tableRes?.data || []);
      setError('');
    } catch (err) {
      setError(problem(err));
    } finally {
      setLoading(false);
      setNow(Date.now());
    }
  }, []);

  useEffect(() => {
    void load();
    // The kitchen moves on its own, so the board refreshes itself.
    const timer = window.setInterval(() => void load(), 20000);
    return () => window.clearInterval(timer);
  }, [load]);

  const live = useMemo(() => {
    const q = search.trim().toLowerCase();
    return orders
      .filter((o) => LIVE_STATUSES.has(String(o.status)))
      .filter((o) => !mode || o.service_mode === mode)
      .filter((o) => {
        if (!q) return true;
        const hay = [o.order_number, o.customer_name, whereWords(o, tables), o.phone].join(' ').toLowerCase();
        return hay.includes(q);
      })
      .sort((a, b) => String(a.opened_at).localeCompare(String(b.opened_at)));
  }, [orders, tables, mode, search]);

  const counts = useMemo(() => {
    const out: Record<string, number> = { '': 0 };
    for (const o of orders) {
      if (!LIVE_STATUSES.has(String(o.status))) continue;
      out[''] += 1;
      out[o.service_mode] = (out[o.service_mode] || 0) + 1;
    }
    return out;
  }, [orders]);

  const liveTotal = live.reduce((sum, o) => sum + Number(o.total_amount || 0), 0);
  const selected = orders.find((o) => o.id === openId) || null;

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Orders</h1>
          <p>Everything on the floor right now. Tap an order to see it.</p>
        </div>
        <div className="rd-head-actions">
          <input
            className="rd-search"
            type="search"
            placeholder="Search table, guest or number"
            aria-label="Search orders"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Link href="/restaurant/bills" className="rd-linkish">
            Paid bills →
          </Link>
          <button type="button" className="rd-primary" aria-label="Take a new order" onClick={() => (window.location.href = '/restaurant/till')}>
            + New order
          </button>
        </div>
      </header>

      <div className="rd-kpis">
        <div className="rd-kpi hero">
          <span>Open orders</span>
          <strong>{live.length}</strong>
        </div>
        <div className="rd-kpi">
          <span>In the kitchen</span>
          <strong>{live.filter((o) => laneOf(o.status) === 'cooking').length}</strong>
        </div>
        <div className="rd-kpi">
          <span>Ready to serve</span>
          <strong>{live.filter((o) => laneOf(o.status) === 'ready').length}</strong>
        </div>
        <div className="rd-kpi">
          <span>Still to collect</span>
          <strong>{money(liveTotal)}</strong>
        </div>
      </div>

      <div className="rd-chips" role="tablist" aria-label="Service">
        {MODE_FILTERS.map((f) => (
          <button
            key={f.id || 'all'}
            type="button"
            role="tab"
            aria-selected={mode === f.id}
            className={mode === f.id ? 'on' : ''}
            onClick={() => setMode(f.id)}
          >
            {f.label} <small>{counts[f.id] || 0}</small>
          </button>
        ))}
      </div>

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

      {loading ? (
        <div className="rd-empty">Loading orders…</div>
      ) : (
        <div className="rd-board">
          {LANES.map((lane) => {
            const rows = live.filter((o) => laneOf(String(o.status)) === lane.id);
            return (
              <section key={lane.id} className={`rd-col ${lane.id}`} aria-label={lane.title}>
                <div className="rd-col-head">
                  <span className="dot" aria-hidden />
                  {lane.title}
                  <span className="n">{rows.length}</span>
                </div>
                {rows.length === 0 ? <div className="rd-col-empty">{lane.empty}</div> : null}
                {rows.map((o) => {
                  const mins = minutesSince(o.opened_at, now);
                  return (
                    <button
                      key={o.id}
                      type="button"
                      className="rd-card"
                      aria-label={`Order ${o.order_number}, ${whereWords(o, tables)}`}
                      onClick={() => setOpenId(o.id)}
                    >
                      <div className="rd-card-top">
                        <strong>{whereWords(o, tables)}</strong>
                        <span className="num">{o.order_number}</span>
                        <span className="amt">{money(o.total_amount)}</span>
                      </div>
                      <div className="rd-card-dishes">{dishSummary(o)}</div>
                      <div className="rd-card-foot">
                        <span className={`rd-pill ${mins >= LATE_MINUTES && lane.id !== 'ready' ? 'late' : 'grey'}`}>
                          ⏱ {waitWords(mins)}
                        </span>
                        {o.service_mode !== 'dine_in' ? <span className="rd-pill">{MODE_WORDS[o.service_mode]}</span> : null}
                        {o.allergy || o.allergen ? <span className="rd-pill bad">Allergy</span> : null}
                        {o.rush ? <span className="rd-pill wait">Rush</span> : null}
                        {o.bill_asked ? <span className="rd-pill wait">Wants the bill</span> : null}
                      </div>
                    </button>
                  );
                })}
              </section>
            );
          })}
        </div>
      )}

      {selected ? (
        <OrderDrawer
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

function OrderDrawer({
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
  const live = LIVE_STATUSES.has(status);
  const unsent = (order.items || []).some((i: Row) => i.prep_status === 'queued') && status === 'open';

  async function act(path: string, message: string, close = false) {
    setBusy(true);
    setError('');
    try {
      await api(path, { method: 'POST' });
      await onChanged(message);
      if (close) onClose();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  const facts: { text: string; tone?: string }[] = [];
  if (order.covers) facts.push({ text: `${order.covers} guests` });
  if (order.phone) facts.push({ text: order.phone });
  if (order.delivery_address) facts.push({ text: order.delivery_address });
  if (order.allergy) facts.push({ text: `Allergy: ${order.allergy}`, tone: 'bad' });
  if (order.allergen) facts.push({ text: `Allergen: ${order.allergen}`, tone: 'bad' });
  if (order.diet) facts.push({ text: order.diet });
  if (order.occasion) facts.push({ text: order.occasion });
  if (order.ready_by) facts.push({ text: `Ready by ${order.ready_by}`, tone: 'wait' });
  if (order.notes) facts.push({ text: order.notes, tone: 'wait' });
  if (order.server) facts.push({ text: `Server: ${order.server}`, tone: 'grey' });

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={`Order ${order.order_number}`} onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>{whereWords(order, tables)}</h2>
            <p>
              {order.order_number} · {MODE_WORDS[order.service_mode] || order.service_mode} ·{' '}
              {STATUS_WORDS[status] || status}
            </p>
          </div>
          <button type="button" className="rd-link" aria-label="Close order" onClick={onClose}>
            Close
          </button>
        </div>

        {facts.length ? (
          <div className="rd-facts">
            {facts.map((f) => (
              <span key={f.text} className={`rd-pill ${f.tone || ''}`}>
                {f.text}
              </span>
            ))}
          </div>
        ) : null}

        <section className="rd-section" aria-label="Dishes">
          <h3>Dishes</h3>
          {(order.items || []).length === 0 ? <p className="rd-empty">No dishes yet.</p> : null}
          {(order.items || []).map((item: Row) => (
            <div key={item.id} className="rd-item">
              <span className="q">{Number(item.quantity)}×</span>
              <div>
                {item.name}
                {item.modifiers?.length || item.note ? (
                  <small>{[...(item.modifiers || []), item.note].filter(Boolean).join(' · ')}</small>
                ) : null}
              </div>
              <div className="right">
                {money(item.line_total ?? Number(item.quantity) * Number(item.unit_price))}
                {live ? (
                  <span
                    className={`rd-pill ${
                      item.prep_status === 'ready' || item.prep_status === 'done'
                        ? ''
                        : item.prep_status === 'queued'
                          ? 'grey'
                          : 'wait'
                    }`}
                  >
                    {status === 'open' ? 'Not sent' : PREP_WORDS[item.prep_status] || item.prep_status}
                  </span>
                ) : null}
              </div>
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
            <dt>{live ? 'To pay' : `Paid · ${METHOD_WORDS[order.payment_method] || order.payment_method}`}</dt>
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
            {status === 'open'
              ? 'Cancel this order? Nothing has gone to the kitchen yet.'
              : 'Void this order? The kitchen has it, so the dishes are thrown away.'}
            <div>
              <button type="button" onClick={() => setConfirming(false)}>
                Keep it
              </button>
              <button
                type="button"
                className="rd-danger"
                aria-label={status === 'open' ? 'Yes, cancel the order' : 'Yes, void the order'}
                disabled={busy}
                onClick={() =>
                  void act(
                    `/restaurant/orders/${order.id}/${status === 'open' ? 'cancel' : 'void'}`,
                    `Order ${order.order_number} ${status === 'open' ? 'cancelled' : 'voided'}`,
                    true,
                  )
                }
              >
                {status === 'open' ? 'Yes, cancel' : 'Yes, void'}
              </button>
            </div>
          </div>
        ) : null}

        {live ? (
          <div className="rd-actions">
            {unsent ? (
              <button
                type="button"
                className="rd-go full"
                aria-label="Send to kitchen"
                disabled={busy}
                onClick={() => void act(`/restaurant/orders/${order.id}/send`, `Order ${order.order_number} sent to the kitchen`)}
              >
                Send to kitchen
              </button>
            ) : null}
            <button
              type="button"
              aria-label="Add dishes"
              onClick={() => (window.location.href = `/restaurant/till?order=${encodeURIComponent(order.id)}`)}
            >
              + Add dishes
            </button>
            <button
              type="button"
              className="rd-primary"
              aria-label="Take payment"
              onClick={() => (window.location.href = `/restaurant/till?order=${encodeURIComponent(order.id)}&pay=1`)}
            >
              Take payment
            </button>
            <button type="button" className="rd-danger full" aria-label="Cancel or void order" onClick={() => setConfirming(true)}>
              {status === 'open' ? 'Cancel order' : 'Void order'}
            </button>
            <Link className="rd-linkish full" href="/restaurant?tab=orders" style={{ textAlign: 'center' }}>
              More details (seat, course, pager…) in the full order editor
            </Link>
          </div>
        ) : null}
      </aside>
    </div>
  );
}
