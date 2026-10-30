'use client';

/**
 * Restaurant money owed: what the restaurant owes its suppliers (pay them here), and any old
 * guest balances. Restaurant bills cannot go on credit, so guest balances only come from before.
 * Uses the shared credit engine (supplier and customer payments post to the books).
 */

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../../lib/api';
import { money, problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

const DELIVERED = new Set(['received', 'partially_received']);
const PAID_WITH: [string, string][] = [
  ['cash', 'Cash'],
  ['mobile_money', 'MoMo'],
  ['bank_transfer', 'Bank'],
  ['cheque', 'Cheque'],
];

function shortDate(value: unknown) {
  if (!value) return '';
  const d = new Date(String(value));
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

type Pay = { kind: 'supplier' | 'guest'; party: Row; docs: Row[] } | null;

export default function RestaurantPayablesPage() {
  const [ap, setAp] = useState<Row | null>(null);
  const [ar, setAr] = useState<Row | null>(null);
  const [accounts, setAccounts] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const [pay, setPay] = useState<Pay>(null);

  const load = useCallback(async () => {
    try {
      const [payable, receivable, liquid] = await Promise.all([
        api('/credit/aging?kind=payable'),
        api('/credit/aging?kind=receivable').catch(() => ({ data: null })),
        api('/accounting/liquid-accounts').catch(() => ({ data: [] })),
      ]);
      setAp(payable?.data || null);
      setAr(receivable?.data || null);
      setAccounts((liquid?.data || []).filter((a: Row) => a.is_active !== false));
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

  // A delivered order is owed even when no supplier bill was recorded (the usual restaurant case);
  // orders not delivered yet stay "on order".
  const delivered: Row[] = (ap?.commitments || []).filter((c: Row) => DELIVERED.has(c.status));
  const docs: Row[] = [...(ap?.documents || []), ...delivered];
  const onOrder = (ap?.commitments || []).filter((c: Row) => !DELIVERED.has(c.status)).reduce((s: number, c: Row) => s + Number(c.balance_due_base ?? c.balance_due ?? 0), 0);
  const suppliers: Row[] = (ap?.parties || [])
    .map((p: Row) => ({
      ...p,
      total_due: docs.filter((d) => d.party_id === p.party_id).reduce((s, d) => s + Number(d.balance_due_base ?? d.balance_due ?? 0), 0),
    }))
    .filter((p: Row) => p.total_due > 0.004)
    .sort((a: Row, b: Row) => b.total_due - a.total_due);
  const owedTotal = suppliers.reduce((s, p) => s + p.total_due, 0);
  const notYetDue = owedTotal - Number(ap?.overdue_total || 0);
  const guests: Row[] = (ar?.parties || []).filter((p: Row) => Number(p.total_due) > 0.004);
  const guestDocs: Row[] = ar?.documents || [];

  async function done(message: string) {
    setPay(null);
    setNotice(message);
    await load();
  }

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Pay suppliers</h1>
          <p>What you owe for deliveries, oldest first. Paying takes it off what you owe and off your cash or bank.</p>
        </div>
        <div className="rd-head-actions">
          <Link className="rd-linkish" href="/restaurant/purchasing">Supplier orders →</Link>
        </div>
      </header>

      {notice ? <div className="rd-notice" role="status" onClick={() => setNotice('')}>{notice}</div> : null}
      {error ? <div className="rd-error" role="alert" onClick={() => setError('')}>{error}</div> : null}
      {loading ? <div className="rd-empty">Loading…</div> : null}

      {!loading && ap ? (
        <>
          <div className="rd-kpis">
            <div className="rd-kpi hero">
              <span>You owe suppliers</span>
              <strong>{money(owedTotal)}</strong>
              <small>{suppliers.length} {suppliers.length === 1 ? 'supplier' : 'suppliers'}</small>
            </div>
            <div className="rd-kpi">
              <span>Overdue</span>
              <strong>{money(ap.overdue_total)}</strong>
              <small>{Number(ap.overdue_total) > 0 ? 'Pay these first' : 'Nothing late'}</small>
            </div>
            <div className="rd-kpi">
              <span>Not due yet</span>
              <strong>{money(Math.max(0, notYetDue))}</strong>
            </div>
            <div className="rd-kpi">
              <span>Still on order</span>
              <strong>{money(onOrder)}</strong>
              <small>Owed once it is delivered</small>
            </div>
          </div>

          <div className="rd-list" aria-label="Suppliers you owe">
            {suppliers.length === 0 ? (
              <div className="rd-empty">
                <strong>You owe no suppliers</strong>When a delivery is received, what it cost shows here until you pay.
              </div>
            ) : null}
            {suppliers.map((party) => {
              const theirs = docs.filter((d) => d.party_id === party.party_id && Number(d.balance_due) > 0.004);
              const late = theirs.filter((d) => Number(d.days_overdue) > 0);
              const expanded = open === party.party_id;
              return (
                <div key={party.party_id} className={`rd-party${late.length ? ' late' : ''}`}>
                  <div className="rd-stock-row">
                    <div className="what">
                      <strong>{party.name}</strong>
                      <small>
                        {theirs.length} {theirs.length === 1 ? 'delivery' : 'deliveries'} unpaid
                        {late.length ? ` · ${late.length} overdue` : ''}
                      </small>
                    </div>
                    <div className="onhand">
                      <strong>{money(party.total_due)}</strong>
                      <small>{late.length ? `${Math.max(...late.map((d) => Number(d.days_overdue)))} days late` : 'owed'}</small>
                    </div>
                    <button type="button" className="rd-link" aria-expanded={expanded} onClick={() => setOpen(expanded ? null : party.party_id)}>
                      {expanded ? 'Hide' : 'Show'} details
                    </button>
                    <div className="acts">
                      <button type="button" className="rd-go" aria-label={`Pay ${party.name}`} onClick={() => setPay({ kind: 'supplier', party, docs: theirs })}>Pay</button>
                    </div>
                  </div>
                  {expanded ? (
                    <ul className="rd-docs">
                      {theirs.map((d) => (
                        <li key={d.id}>
                          <span>{d.document_number}</span>
                          <span>{d.document_type === 'purchase_order' ? (d.status === 'partially_received' ? 'Part delivered' : 'Delivered') : 'Supplier bill'}{d.invoice_date || d.due_date ? ` · ${shortDate(d.invoice_date || d.due_date)}` : ''}</span>
                          <span className={Number(d.days_overdue) > 0 ? 'rd-warn-text' : ''}>
                            {Number(d.days_overdue) > 0 ? `${d.days_overdue} days late` : d.due_date ? `due ${shortDate(d.due_date)}` : ''}
                          </span>
                          <strong>{money(d.balance_due)}</strong>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              );
            })}
          </div>
        </>
      ) : null}

      {!loading && guests.length ? (
        <section className="rd-panel">
          <div className="rd-panel-head">
            <h2>Old guest balances</h2>
            <small>From before restaurant bills had to be paid in full. Record what a guest pays to clear it.</small>
          </div>
          <div className="rd-list rd-list-flat" aria-label="Guest balances">
            {guests.map((party) => (
              <div key={party.party_id} className="rd-stock-row">
                <div className="what">
                  <strong>{party.name}</strong>
                  <small>{guestDocs.filter((d) => d.party_id === party.party_id).length} unpaid</small>
                </div>
                <div className="onhand">
                  <strong>{money(party.total_due)}</strong>
                  <small>owed to you</small>
                </div>
                <span />
                <div className="acts">
                  <button type="button" className="rd-go" aria-label={`Record payment from ${party.name}`} onClick={() => setPay({ kind: 'guest', party, docs: [] })}>Record payment</button>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {pay ? <PaySheet pay={pay} accounts={accounts} onClose={() => setPay(null)} onDone={done} /> : null}
    </div>
  );
}

function PaySheet({ pay, accounts, onClose, onDone }: { pay: NonNullable<Pay>; accounts: Row[]; onClose: () => void; onDone: (m: string) => Promise<void> }) {
  const owed = Number(pay.party.total_due || 0);
  const [amount, setAmount] = useState(owed.toFixed(2));
  const [method, setMethod] = useState(pay.kind === 'supplier' ? 'mobile_money' : 'cash');
  const [accountId, setAccountId] = useState('');
  const [reference, setReference] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const fitting = accounts.filter((a) => (method === 'cash' ? a.is_cash_account : !a.is_cash_account));

  async function save() {
    const n = Number(amount);
    if (!(n > 0)) return setError('Enter the amount.');
    if (n > owed + 0.004) return setError(`That is more than the ${money(owed)} owed.`);
    setBusy(true);
    setError('');
    try {
      const id = pay.party.party_id;
      const body = {
        amount: n,
        payment_method: method,
        reference: reference.trim() || null,
        liquid_account_id: accountId || null,
      };
      if (pay.kind === 'supplier') {
        await api(`/suppliers/${id}/payments`, { method: 'POST', body: JSON.stringify({ ...body, supplier_id: id }) });
      } else {
        await api(`/customers/${id}/payments`, { method: 'POST', body: JSON.stringify({ ...body, customer_id: id }) });
      }
      await onDone(pay.kind === 'supplier' ? `${money(n)} paid to ${pay.party.name}` : `${money(n)} received from ${pay.party.name}`);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={pay.kind === 'supplier' ? `Pay ${pay.party.name}` : `Payment from ${pay.party.name}`} onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>{pay.kind === 'supplier' ? `Pay ${pay.party.name}` : `Payment from ${pay.party.name}`}</h2>
            <p>{money(owed)} {pay.kind === 'supplier' ? 'owed. The oldest delivery is paid first.' : 'owed to you.'}</p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        <div className="rd-form-grid">
          <label className="rd-span">
            <span>Amount</span>
            <input className="rd-big-input" aria-label="Payment amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ''))} autoFocus />
          </label>
          <span className="rd-field-label rd-span">{pay.kind === 'supplier' ? 'Paid with' : 'Guest paid with'}</span>
          <div className="rd-chips rd-span" role="radiogroup" aria-label="Paid with">
            {PAID_WITH.map(([key, label]) => (
              <button key={key} type="button" role="radio" aria-checked={method === key} className={method === key ? 'on' : ''} onClick={() => { setMethod(key); setAccountId(''); }}>
                {label}
              </button>
            ))}
          </div>
          {fitting.length > 1 ? (
            <label>
              <span>{pay.kind === 'supplier' ? 'Paid from' : 'Paid into'}</span>
              <select aria-label="Money account" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                <option value="">Usual account</option>
                {fitting.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </label>
          ) : null}
          <label>
            <span>Reference (optional)</span>
            <input aria-label="Payment reference" placeholder="MoMo transaction ID" value={reference} onChange={(e) => setReference(e.target.value)} />
          </label>
        </div>
        {pay.docs.length ? (
          <ul className="rd-docs">
            {pay.docs.map((d) => (
              <li key={d.id}>
                <span>{d.document_number}</span>
                <span>{shortDate(d.invoice_date || d.due_date)}</span>
                <span />
                <strong>{money(d.balance_due)}</strong>
              </li>
            ))}
          </ul>
        ) : null}
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="rd-primary" aria-label="Save payment" disabled={busy} onClick={() => void save()}>
            {busy ? 'Saving…' : pay.kind === 'supplier' ? `Pay ${money(amount)}` : `Record ${money(amount)}`}
          </button>
        </div>
      </aside>
    </div>
  );
}
