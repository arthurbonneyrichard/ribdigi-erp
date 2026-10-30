'use client';

/**
 * Restaurant Guests: the people who eat here, gathered from their orders and
 * bookings (GET /restaurant/guests). Retail customer records never show here.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import {
  METHOD_WORDS,
  STATUS_WORDS,
  dayAndTime,
  initials,
  minutesSince,
  money,
  problem,
  type Row,
  whereWords,
} from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Sort = 'recent' | 'visits' | 'spent';

const SORTS: { id: Sort; label: string }[] = [
  { id: 'recent', label: 'Seen lately' },
  { id: 'visits', label: 'Most visits' },
  { id: 'spent', label: 'Spent most' },
];

function lastSeen(value: unknown): string {
  if (!value) return 'Not seen yet';
  const days = Math.floor(minutesSince(value) / 1440);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  return months === 1 ? 'A month ago' : `${months} months ago`;
}

function sameGuest(order: Row, guest: Row): boolean {
  const digits = (v: unknown) => String(v || '').replace(/\D/g, '').slice(-9);
  if (guest.phone && order.phone && digits(guest.phone) === digits(order.phone)) return true;
  const name = (v: unknown) => String(v || '').trim().toLowerCase().replace(/\s+/g, ' ');
  return Boolean(guest.name) && name(order.customer_name) === name(guest.name) && !guest.phone;
}

export default function RestaurantGuestsPage() {
  const [guests, setGuests] = useState<Row[]>([]);
  const [orders, setOrders] = useState<Row[]>([]);
  const [tables, setTables] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<Sort>('recent');
  const [openKey, setOpenKey] = useState('');

  const load = useCallback(async () => {
    try {
      const [guestRes, orderRes, tableRes] = await Promise.all([
        api('/restaurant/guests'),
        api('/restaurant/orders'),
        api('/restaurant/tables'),
      ]);
      setGuests(guestRes?.data || []);
      setOrders(orderRes?.data || []);
      setTables(tableRes?.data || []);
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

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = guests.filter((g) => !q || [g.name, g.phone, g.email].join(' ').toLowerCase().includes(q));
    const by: Record<Sort, (a: Row, b: Row) => number> = {
      recent: (a, b) => String(b.last_visit || '').localeCompare(String(a.last_visit || '')),
      visits: (a, b) => Number(b.visits) - Number(a.visits),
      spent: (a, b) => Number(b.spent) - Number(a.spent),
    };
    return [...rows].sort(by[sort]);
  }, [guests, search, sort]);

  const regulars = guests.filter((g) => Number(g.visits) >= 2).length;
  const withAllergy = guests.filter((g) => g.allergy).length;
  const top = [...guests].sort((a, b) => Number(b.spent) - Number(a.spent))[0];
  const selected = guests.find((g) => g.key === openKey) || null;

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Guests</h1>
          <p>The people who eat here, from their orders and bookings.</p>
        </div>
        <div className="rd-head-actions">
          <input
            className="rd-search"
            type="search"
            placeholder="Search name or phone"
            aria-label="Search guests"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </header>

      <div className="rd-kpis">
        <div className="rd-kpi hero">
          <span>Guests</span>
          <strong>{guests.length}</strong>
        </div>
        <div className="rd-kpi">
          <span>Came back (2+ visits)</span>
          <strong>{regulars}</strong>
        </div>
        <div className="rd-kpi">
          <span>Have an allergy noted</span>
          <strong>{withAllergy}</strong>
        </div>
        <div className="rd-kpi">
          <span>Best guest</span>
          <strong style={{ fontSize: 18 }}>{top ? `${top.name || top.phone} · ${money(top.spent)}` : '—'}</strong>
        </div>
      </div>

      <div className="rd-chips" role="tablist" aria-label="Sort guests">
        {SORTS.map((s) => (
          <button key={s.id} type="button" role="tab" aria-selected={sort === s.id} className={sort === s.id ? 'on' : ''} onClick={() => setSort(s.id)}>
            {s.label}
          </button>
        ))}
      </div>

      {error ? (
        <div className="rd-error" role="alert">
          {error}
        </div>
      ) : null}

      {loading ? <div className="rd-empty">Loading guests…</div> : null}
      {!loading && shown.length === 0 ? (
        <div className="rd-list">
          <div className="rd-empty">
            <strong>{guests.length ? 'No guest matches' : 'No guests yet'}</strong>
            {guests.length
              ? 'Try another name or number.'
              : 'Put a name or phone on takeaway, delivery or booking orders and the guest shows up here.'}
          </div>
        </div>
      ) : null}

      <div className="rd-guests">
        {shown.map((g) => (
          <button key={g.key} type="button" className="rd-guest" aria-label={`Guest ${g.name || g.phone}`} onClick={() => setOpenKey(g.key)}>
            <span className="rd-avatar" aria-hidden>
              {initials(g.name || g.phone)}
            </span>
            <span className="rd-guest-body">
              <strong>{g.name || 'Guest'}</strong>
              <small>{g.phone || g.email || 'No phone saved'}</small>
              <span className="rd-guest-stats">
                <span>
                  <b>{g.visits}</b> {Number(g.visits) === 1 ? 'visit' : 'visits'}
                </span>
                <span>
                  <b>{money(g.spent)}</b> spent
                </span>
              </span>
              <span className="rd-facts">
                <span className="rd-pill grey">{lastSeen(g.last_visit)}</span>
                {g.favourite_dish ? <span className="rd-pill">Loves {g.favourite_dish}</span> : null}
                {g.allergy ? <span className="rd-pill bad">Allergy: {g.allergy}</span> : null}
                {Number(g.bookings) ? <span className="rd-pill wait">{g.bookings} bookings</span> : null}
              </span>
            </span>
          </button>
        ))}
      </div>

      {selected ? (
        <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={`Guest ${selected.name || selected.phone}`} onClick={() => setOpenKey('')}>
          <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="rd-drawer-head">
              <span className="rd-avatar" aria-hidden>
                {initials(selected.name || selected.phone)}
              </span>
              <div>
                <h2>{selected.name || 'Guest'}</h2>
                <p>{[selected.phone, selected.email].filter(Boolean).join(' · ') || 'No contact saved'}</p>
              </div>
              <button type="button" className="rd-link" aria-label="Close guest" onClick={() => setOpenKey('')}>
                Close
              </button>
            </div>
            <div className="rd-kpis">
              <div className="rd-kpi">
                <span>Visits</span>
                <strong>{selected.visits}</strong>
              </div>
              <div className="rd-kpi">
                <span>Spent</span>
                <strong>{money(selected.spent)}</strong>
              </div>
            </div>
            <div className="rd-facts">
              {selected.favourite_dish ? <span className="rd-pill">Favourite: {selected.favourite_dish}</span> : null}
              {selected.allergy ? <span className="rd-pill bad">Allergy: {selected.allergy}</span> : null}
              <span className="rd-pill grey">Last seen {lastSeen(selected.last_visit).toLowerCase()}</span>
            </div>
            <section className="rd-section" aria-label="Bills">
              <h3>Their bills</h3>
              {orders
                .filter((o) => sameGuest(o, selected))
                .slice(0, 12)
                .map((o) => (
                  <div key={o.id} className="rd-item">
                    <span className="q">#{Number(String(o.order_number).replace(/\D/g, '')) || ''}</span>
                    <div>
                      {whereWords(o, tables)}
                      <small>
                        {dayAndTime(o.completed_at || o.opened_at)} · {STATUS_WORDS[o.status] || o.status}
                        {o.status === 'completed' ? ` · ${METHOD_WORDS[o.payment_method] || o.payment_method}` : ''}
                      </small>
                    </div>
                    <div className="right">{money(o.total_amount)}</div>
                  </div>
                ))}
            </section>
            <div className="rd-actions">
              <button
                type="button"
                className="rd-primary full"
                aria-label="New order for this guest"
                onClick={() => (window.location.href = '/restaurant/till')}
              >
                New order
              </button>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
