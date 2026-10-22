'use client';

import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { formatElapsed, formatMoney, formatWhen } from '../lib/format';
import { useCompanyFormat } from '../lib/useCompanyFormat';

export type CashierPresenceRow = {
  user_id: string;
  full_name: string;
  email?: string | null;
  role: string;
  status: 'online' | 'offline' | 'no_signal';
  offline_since?: string | null;
  offline_duration_seconds?: number | null;
  last_seen_at?: string | null;
  store_name?: string | null;
  pending_queue_count?: number | null;
  shift_number?: string | null;
  shift_status?: string | null;
  shift_sale_count?: number | null;
  shift_sales?: number | null;
};

function sellingLabel(status: CashierPresenceRow['status']): string {
  if (status === 'online') return 'Online';
  if (status === 'offline') return 'Offline';
  return 'No POS signal';
}

function countOf(rows: CashierPresenceRow[], status: CashierPresenceRow['status']): number {
  return rows.filter((row) => row.status === status).length;
}

function saleCountLabel(count: number | null | undefined): string {
  const n = count || 0;
  return `${n} sale${n === 1 ? '' : 's'}`;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.slice(0, 2).map((part) => part[0] || '');
  return (letters.join('') || '?').toUpperCase();
}

function byAttention(a: CashierPresenceRow, b: CashierPresenceRow): number {
  const rank = { offline: 0, online: 1, no_signal: 2 };
  return rank[a.status] - rank[b.status] || a.full_name.localeCompare(b.full_name);
}

/** Company admin view of each cashier's POS connection and open shift. */
export default function CashierPresencePanel() {
  const formatPrefs = useCompanyFormat();
  const [rows, setRows] = useState<CashierPresenceRow[] | null>(null);

  useEffect(() => {
    let stop = false;
    async function load() {
      try {
        const res = await api('/users/cashier-presence');
        if (!stop) setRows(res.data || []);
      } catch {
        if (!stop) setRows(null);
      }
    }
    load();
    const timer = window.setInterval(load, 30000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, []);

  if (!rows) return null;

  const online = countOf(rows, 'online');
  const offline = countOf(rows, 'offline');
  const quiet = countOf(rows, 'no_signal');

  return (
    <section className="cashier-board" aria-label="Cashier offline status">
      <header className="cashier-board-head">
        <div>
          <h2>Cashiers</h2>
          <p>Who is selling, who is offline, and which shift is still open.</p>
          {offline > 0 ? (
            <p className="cashier-board-note">Saved sales leave an offline till on their own once it connects. The waiting count is the last report from that till.</p>
          ) : null}
        </div>
        {rows.length > 0 ? (
          <div className="cashier-board-counts" role="status">
            <span className={online ? 'is-online' : 'is-quiet'}><strong>{online}</strong> Online</span>
            <span className={offline ? 'is-offline' : 'is-quiet'}><strong>{offline}</strong> Offline</span>
            <span className={quiet ? 'is-unknown' : 'is-quiet'}><strong>{quiet}</strong> No POS signal</span>
          </div>
        ) : null}
      </header>
      {rows.length === 0 ? (
        <p className="cashier-board-empty">No active cashiers.</p>
      ) : (
        <div className="cashier-board-grid">
          {rows.slice().sort(byAttention).map((row) => {
            const tone = row.status === 'online' ? 'is-online' : row.status === 'offline' ? 'is-offline' : 'is-unknown';
            const waiting = row.pending_queue_count || 0;
            const shiftOpen = row.shift_status === 'open' && Boolean(row.shift_number);
            const offlineFor =
              row.status === 'offline' ? formatElapsed(row.offline_duration_seconds) || 'under a minute' : '';
            const waitingText = waiting ? `${waiting} to send` : 'None';
            return (
              <article className={`cashier-card ${tone}`} key={row.user_id}>
                <header className="cashier-card-head">
                  <span className={`cashier-avatar ${tone}`} aria-hidden="true">{initials(row.full_name)}</span>
                  <div className="cashier-card-who">
                    <strong>{row.full_name}</strong>
                    <span>{row.store_name || 'Not on a till'}</span>
                    {row.email ? <span className="cashier-card-mail">{row.email}</span> : null}
                  </div>
                  <span className={`cashier-sell-status ${tone}`}>{sellingLabel(row.status)}</span>
                </header>
                <dl className="cashier-card-facts">
                  <div>
                    <dt>Shift sales</dt>
                    <dd>{shiftOpen ? formatMoney(row.shift_sales) : '—'}</dd>
                  </div>
                  <div>
                    <dt>Sales</dt>
                    <dd>{shiftOpen ? saleCountLabel(row.shift_sale_count) : '—'}</dd>
                  </div>
                  <div>
                    <dt>Waiting</dt>
                    <dd className={waiting ? 'is-waiting' : undefined}>{waitingText}</dd>
                  </div>
                </dl>
                <p className="cashier-card-meta">
                  {shiftOpen ? row.shift_number : 'No open shift'}
                  {offlineFor ? ` · Offline ${offlineFor}` : ''}
                  {row.last_seen_at ? ` · Last seen ${formatWhen(row.last_seen_at, formatPrefs)}` : ''}
                  {waiting && row.status === 'offline' ? ' · Sends when the till connects' : ''}
                  {waiting && row.status === 'online' ? ' · Sending' : ''}
                </p>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
