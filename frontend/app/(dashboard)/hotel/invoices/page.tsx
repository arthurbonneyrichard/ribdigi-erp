'use client';

/**
 * Hotel guest invoices: the invoice each folio becomes at check-out, what guests and companies
 * still owe, taking a payment, and printing the invoice. The hotel's own screen over the shared
 * sales engine (replaces Sales, Customers and Customer credit on the hotel menu).
 */

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import { fetchAttachment } from '../../../../lib/attachments';
import { formatMoney } from '../../../../lib/format';
import './hotel-invoices.css';

type Row = Record<string, any>;
const METHODS: [string, string][] = [
  ['cash', 'Cash'],
  ['momo', 'MoMo'],
  ['card', 'Card'],
  ['bank', 'Bank transfer'],
  ['cheque', 'Cheque'],
];

function money(value: unknown) {
  return formatMoney(Number(value || 0));
}

function problem(err: unknown) {
  return err instanceof Error ? err.message : 'Something went wrong. Try again.';
}

function day(value: unknown) {
  if (!value) return '';
  const d = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

export default function HotelInvoicesPage() {
  const [show, setShow] = useState<'owed' | 'all'>('owed');
  const [data, setData] = useState<Row | null>(null);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [paying, setPaying] = useState<Row | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api(`/hotel/invoices?show=${show}`);
      setData(res?.data || null);
      setError('');
    } catch (err) {
      setError(problem(err));
    }
  }, [show]);

  useEffect(() => {
    void load();
  }, [load]);

  const items: Row[] = data?.items || [];
  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) => `${i.guest_name} ${i.company_name || ''} ${i.invoice_number} ${i.folio_number} ${i.room || ''}`.toLowerCase().includes(q));
  }, [items, search]);
  const byCompany = useMemo(() => {
    const out: Record<string, number> = {};
    for (const i of items) if (i.company_name && i.due > 0) out[i.company_name] = (out[i.company_name] || 0) + Number(i.due);
    return Object.entries(out).sort((a, b) => b[1] - a[1]);
  }, [items]);

  async function print(row: Row) {
    try {
      const { blob } = await fetchAttachment(`/hotel/invoices/${row.id}/print`);
      const url = URL.createObjectURL(blob);
      const win = window.open(url, '_blank');
      if (!win) setError('Allow pop-ups for this site to print the invoice.');
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      setError(problem(err));
    }
  }

  return (
    <div className="hinv">
      <header className="hi-head">
        <div>
          <h1>Guest invoices</h1>
          <p>Each stay becomes an invoice at check-out. See what guests and companies still owe and take payment.</p>
        </div>
        <Link href="/hotel?tab=billing" className="hi-link">Open folios →</Link>
      </header>

      {notice ? <div className="hi-notice" role="status" onClick={() => setNotice('')}>{notice}</div> : null}
      {error ? <div className="hi-error" role="alert" onClick={() => setError('')}>{error}</div> : null}

      <div className="hi-kpis">
        <div className="hi-kpi hero">
          <span>Still owed</span>
          <strong>{money(data?.owed_total)}</strong>
          <small>{data?.owed_count || 0} unpaid {data?.owed_count === 1 ? 'invoice' : 'invoices'}</small>
        </div>
        <div className="hi-kpi">
          <span>Companies that owe</span>
          {byCompany.length ? (
            <ul>
              {byCompany.slice(0, 3).map(([name, due]) => (
                <li key={name}>
                  <span>{name}</span>
                  <strong>{money(due)}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <small>None</small>
          )}
        </div>
      </div>

      <div className="hi-tools">
        <div className="hi-chips" role="group" aria-label="Which invoices">
          <button type="button" className={show === 'owed' ? 'on' : ''} aria-pressed={show === 'owed'} onClick={() => setShow('owed')}>Owed</button>
          <button type="button" className={show === 'all' ? 'on' : ''} aria-pressed={show === 'all'} onClick={() => setShow('all')}>All</button>
        </div>
        <input type="search" aria-label="Search guest invoices" placeholder="Guest, company, room or invoice" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <div className="hi-list" aria-label="Guest invoices">
        {!data ? <p className="hi-empty">Loading…</p> : null}
        {data && shown.length === 0 ? (
          <p className="hi-empty">{show === 'owed' ? 'Nobody owes anything. Every checked-out stay is paid.' : 'No guest invoices yet. They appear when a guest checks out.'}</p>
        ) : null}
        {shown.map((row) => (
          <div key={row.id} className={`hi-row${row.due > 0 ? ' owed' : ''}`}>
            <div className="who">
              <strong>{row.guest_name}</strong>
              <small>
                {row.company_name ? `${row.company_name} · ` : ''}
                {row.room ? `Room ${row.room} · ` : ''}
                {day(row.check_in)} to {day(row.check_out)}
              </small>
              <small className="ref">
                {row.invoice_number} · folio {row.folio_number}
              </small>
            </div>
            <div className="amt">
              <strong>{money(row.total)}</strong>
              <small>{row.due > 0 ? `${money(row.due)} owed` : 'Paid'}</small>
            </div>
            <div className="acts">
              <button type="button" aria-label={`Print invoice ${row.invoice_number}`} onClick={() => void print(row)}>Print</button>
              {row.due > 0 ? (
                <button type="button" className="hi-primary" aria-label={`Take payment for ${row.invoice_number}`} onClick={() => setPaying(row)}>Take payment</button>
              ) : null}
            </div>
          </div>
        ))}
      </div>

      {paying ? (
        <PaySheet
          row={paying}
          onClose={() => setPaying(null)}
          onDone={async (message) => {
            setPaying(null);
            setNotice(message);
            await load();
          }}
        />
      ) : null}
    </div>
  );
}

function PaySheet({ row, onClose, onDone }: { row: Row; onClose: () => void; onDone: (m: string) => Promise<void> }) {
  const [amount, setAmount] = useState(Number(row.due).toFixed(2));
  const [method, setMethod] = useState('cash');
  const [reference, setReference] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    const n = Number(amount);
    if (!(n > 0)) return setError('Enter the amount.');
    if (n > Number(row.due) + 0.004) return setError(`That is more than the ${money(row.due)} owed.`);
    setBusy(true);
    setError('');
    try {
      await api(`/hotel/invoices/${row.id}/payments`, {
        method: 'POST',
        body: JSON.stringify({ amount: n, method, reference: reference.trim() || null }),
      });
      await onDone(`${money(n)} received from ${row.company_name || row.guest_name}`);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="hi-sheet" role="dialog" aria-modal="true" aria-label={`Take payment for ${row.invoice_number}`} onClick={onClose}>
      <div className="hi-card" onClick={(e) => e.stopPropagation()}>
        <div className="hi-card-head">
          <h2>Take payment</h2>
          <button type="button" className="hi-plain" onClick={onClose}>Close</button>
        </div>
        <p className="hi-sub">
          {row.guest_name}
          {row.company_name ? ` · ${row.company_name}` : ''} · {row.invoice_number} · {money(row.due)} owed
        </p>
        <label className="hi-field">
          <span>Amount</span>
          <input aria-label="Payment amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ''))} autoFocus />
        </label>
        <div className="hi-chips" role="radiogroup" aria-label="Paid with">
          {METHODS.map(([key, label]) => (
            <button key={key} type="button" role="radio" aria-checked={method === key} className={method === key ? 'on' : ''} onClick={() => setMethod(key)}>
              {label}
            </button>
          ))}
        </div>
        <label className="hi-field">
          <span>Reference (optional)</span>
          <input aria-label="Payment reference" placeholder="MoMo or bank transaction ID" value={reference} onChange={(e) => setReference(e.target.value)} />
        </label>
        {error ? <div className="hi-error" role="alert">{error}</div> : null}
        <div className="hi-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="hi-primary" aria-label="Save payment" disabled={busy} onClick={() => void save()}>
            {busy ? 'Saving…' : `Receive ${money(amount)}`}
          </button>
        </div>
      </div>
    </div>
  );
}
