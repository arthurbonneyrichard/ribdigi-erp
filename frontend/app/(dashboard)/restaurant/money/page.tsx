'use client';

/**
 * Restaurant money: cash, bank and MoMo balances, moving money between them (banking the
 * takings), the month's profit in plain words, and recent money movements. The full books
 * (chart of accounts, journals, bank match, cheques) stay on the shared Accounting screen.
 */

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import { money, problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Move = 'transfer' | 'deposit' | 'withdrawal';
const MOVE_WORDS: Record<Move, [string, string]> = {
  transfer: ['Move between accounts', 'Bank the till takings, or top up the till float.'],
  deposit: ['Owner puts money in', 'Money the owner adds to the business.'],
  withdrawal: ['Owner takes money out', 'Money the owner takes for themselves.'],
};
const SOURCE_WORDS: Record<string, string> = {
  restaurant_order: 'Restaurant bill',
  pos_sale: 'Till sale',
  restaurant_waste: 'Waste',
  expense: 'Expense',
  grn: 'Delivery received',
  supplier_payment: 'Paid supplier',
  customer_payment: 'Guest paid',
  cash_transfer: 'Money moved',
  purchase_invoice: 'Supplier bill',
  purchase_return: 'Returned to supplier',
  opening_stock: 'Opening stock',
  coa_opening: 'Opening balances',
  other_income: 'Other income',
};

function monthRange(offset: number): [string, string, string] {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() - offset, 1);
  const last = offset === 0 ? now : new Date(now.getFullYear(), now.getMonth() - offset + 1, 0);
  const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return [iso(first), iso(last), first.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })];
}

function shortDate(value: unknown) {
  if (!value) return '';
  const d = new Date(String(value));
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

function kindOf(a: Row) {
  if (a.is_cash_account) return 'Cash';
  if (/momo|mobile|mtn|telecel|airtel|vodafone/i.test(`${a.bank_name || ''} ${a.name || ''}`)) return 'MoMo';
  return 'Bank';
}

export default function RestaurantMoneyPage() {
  const [accounts, setAccounts] = useState<Row[]>([]);
  const [allCodes, setAllCodes] = useState<string[]>([]);
  const [pnl, setPnl] = useState<Row | null>(null);
  const [journals, setJournals] = useState<Row[]>([]);
  const [monthOffset, setMonthOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [sheet, setSheet] = useState<{ kind: 'move'; move: Move } | { kind: 'account' } | null>(null);

  const [from, to, monthName] = monthRange(monthOffset);

  const load = useCallback(async () => {
    try {
      const [liquid, coa, je] = await Promise.all([
        api('/accounting/liquid-accounts'),
        api('/accounting/accounts').catch(() => ({ data: [] })),
        api('/accounting/journal-entries?status=posted').catch(() => ({ data: [] })),
      ]);
      setAccounts((liquid?.data || []).filter((a: Row) => a.is_active !== false));
      setAllCodes(((coa?.data as Row[]) || []).map((a) => String(a.code)));
      setJournals((je?.data || []).slice(0, 15));
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

  useEffect(() => {
    api(`/accounting/profit-loss?from_date=${from}&to_date=${to}`)
      .then((res) => setPnl(res?.data || null))
      .catch((err) => setError(problem(err)));
  }, [from, to]);

  const total = accounts.reduce((s, a) => s + Number(a.balance || 0), 0);
  const cash = accounts.filter((a) => a.is_cash_account).reduce((s, a) => s + Number(a.balance || 0), 0);
  const names = useMemo(() => Object.fromEntries(accounts.map((a) => [a.id, a.name])), [accounts]);
  const revenue = Number(pnl?.revenue || 0);
  const pct = (n: number) => (revenue > 0 ? `${Math.round((n / revenue) * 100)}% of sales` : '');

  async function done(message: string) {
    setSheet(null);
    setNotice(message);
    await load();
  }

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Money</h1>
          <p>Where your money is, what the month made, and money moved in and out.</p>
        </div>
        <div className="rd-head-actions">
          <Link className="rd-linkish" href="/accounting">Full books (for your accountant) →</Link>
          <button type="button" className="rd-primary" aria-label="Move money" onClick={() => setSheet({ kind: 'move', move: 'transfer' })}>
            Move money
          </button>
        </div>
      </header>

      {notice ? <div className="rd-notice" role="status" onClick={() => setNotice('')}>{notice}</div> : null}
      {error ? <div className="rd-error" role="alert" onClick={() => setError('')}>{error}</div> : null}
      {loading ? <div className="rd-empty">Loading…</div> : null}

      {!loading ? (
        <>
          <section className="rd-panel">
            <div className="rd-panel-head">
              <h2>Your money now</h2>
              <small>{money(total)} in all · {money(cash)} in cash</small>
              <button type="button" className="rd-link" aria-label="Add a bank or MoMo account" onClick={() => setSheet({ kind: 'account' })}>
                + Bank or MoMo account
              </button>
            </div>
            <div className="rd-accounts" aria-label="Money accounts">
              {accounts.map((a) => (
                <div key={a.id} className={`rd-account ${kindOf(a).toLowerCase()}`}>
                  <span className="kind">{kindOf(a)}</span>
                  <strong>{money(a.balance)}</strong>
                  <small>
                    {a.name}
                    {a.account_number ? ` · ${String(a.account_number).slice(-4).padStart(4, '•')}` : ''}
                  </small>
                </div>
              ))}
            </div>
          </section>

          <section className="rd-panel">
            <div className="rd-panel-head">
              <h2>What the month made</h2>
              <div className="rd-chips">
                {[0, 1, 2].map((n) => (
                  <button key={n} type="button" className={monthOffset === n ? 'on' : ''} aria-pressed={monthOffset === n} onClick={() => setMonthOffset(n)}>
                    {monthRange(n)[2]}
                  </button>
                ))}
              </div>
            </div>
            {pnl ? (
              <div className="rd-pnl" aria-label={`Profit for ${monthName}`}>
                <div>
                  <span>Sales (before tax)</span>
                  <strong>{money(pnl.revenue)}</strong>
                </div>
                <div className="minus">
                  <span>Food and drink cost</span>
                  <strong>− {money(pnl.cogs)}</strong>
                  <small>{pct(Number(pnl.cogs || 0))}</small>
                </div>
                <div className="sub">
                  <span>Gross profit</span>
                  <strong>{money(pnl.gross_profit)}</strong>
                </div>
                <div className="minus">
                  <span>Running costs</span>
                  <strong>− {money(pnl.operating_expenses)}</strong>
                  <small>
                    {pct(Number(pnl.operating_expenses || 0))} · <Link href="/restaurant/expenses">see expenses</Link>
                  </small>
                </div>
                <div className={`total${Number(pnl.net_profit) < 0 ? ' loss' : ''}`}>
                  <span>{Number(pnl.net_profit) < 0 ? 'Loss' : 'Profit'}</span>
                  <strong>{money(Math.abs(Number(pnl.net_profit || 0)))}</strong>
                </div>
              </div>
            ) : (
              <div className="rd-empty">Working it out…</div>
            )}
            <p className="rd-hint-line">Waste is counted in running costs. Full statement: <Link href="/reports?tab=pnl">Profit and loss</Link>.</p>
          </section>

          <section className="rd-panel">
            <div className="rd-panel-head">
              <h2>Recent money movements</h2>
              <div className="rd-row-actions right">
                <button type="button" aria-label="Owner puts money in" onClick={() => setSheet({ kind: 'move', move: 'deposit' })}>Owner puts in</button>
                <button type="button" aria-label="Owner takes money out" onClick={() => setSheet({ kind: 'move', move: 'withdrawal' })}>Owner takes out</button>
              </div>
            </div>
            <ul className="rd-docs rd-moves" aria-label="Recent money movements">
              {journals.length === 0 ? <li><span>Nothing posted yet.</span></li> : null}
              {journals.map((j) => (
                <li key={j.id}>
                  <span>{shortDate(j.entry_date || j.created_at)}</span>
                  <span>{SOURCE_WORDS[j.source_type] || 'Book entry'}</span>
                  <span className="desc">{j.description}</span>
                  <strong>{money(j.total_debit)}</strong>
                </li>
              ))}
            </ul>
          </section>
        </>
      ) : null}

      {sheet?.kind === 'move' ? <MoveSheet move={sheet.move} accounts={accounts} names={names} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet?.kind === 'account' ? <AccountSheet codes={allCodes} onClose={() => setSheet(null)} onDone={done} /> : null}
    </div>
  );
}

function MoveSheet({
  move: initial,
  accounts,
  names,
  onClose,
  onDone,
}: {
  move: Move;
  accounts: Row[];
  names: Record<string, string>;
  onClose: () => void;
  onDone: (m: string) => Promise<void>;
}) {
  const cashFirst = accounts.find((a) => a.is_cash_account)?.id || '';
  const bankFirst = accounts.find((a) => !a.is_cash_account)?.id || '';
  const [move, setMove] = useState<Move>(initial);
  const [fromId, setFromId] = useState(initial === 'deposit' ? '' : cashFirst);
  const [toId, setToId] = useState(initial === 'withdrawal' ? '' : initial === 'deposit' ? cashFirst : bankFirst);
  const [amount, setAmount] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const needsFrom = move !== 'deposit';
  const needsTo = move !== 'withdrawal';
  const fromBalance = Number(accounts.find((a) => a.id === fromId)?.balance || 0);

  async function save() {
    const n = Number(amount);
    if (!(n > 0)) return setError('Enter the amount.');
    if (needsFrom && !fromId) return setError('Pick where the money comes from.');
    if (needsTo && !toId) return setError('Pick where the money goes.');
    if (move === 'transfer' && fromId === toId) return setError('Pick two different accounts.');
    setBusy(true);
    setError('');
    try {
      await api('/accounting/transfers', {
        method: 'POST',
        body: JSON.stringify({
          kind: move,
          from_account_id: needsFrom ? fromId : null,
          to_account_id: needsTo ? toId : null,
          amount: n,
          notes: notes.trim() || null,
        }),
      });
      await onDone(
        move === 'transfer'
          ? `${money(n)} moved from ${names[fromId]} to ${names[toId]}`
          : move === 'deposit'
            ? `${money(n)} put into ${names[toId]}`
            : `${money(n)} taken out of ${names[fromId]}`,
      );
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  const pick = (label: string, value: string, set: (v: string) => void) => (
    <label>
      <span>{label}</span>
      <select aria-label={label} value={value} onChange={(e) => set(e.target.value)}>
        <option value="">Pick an account</option>
        {accounts.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name} ({money(a.balance)})
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={MOVE_WORDS[move][0]} onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>{MOVE_WORDS[move][0]}</h2>
            <p>{MOVE_WORDS[move][1]}</p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        <div className="rd-chips" role="radiogroup" aria-label="Kind of move">
          {(Object.keys(MOVE_WORDS) as Move[]).map((k) => (
            <button key={k} type="button" role="radio" aria-checked={move === k} className={move === k ? 'on' : ''} onClick={() => setMove(k)}>
              {MOVE_WORDS[k][0]}
            </button>
          ))}
        </div>
        <div className="rd-form-grid">
          <label className="rd-span">
            <span>Amount</span>
            <input className="rd-big-input" aria-label="Amount to move" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ''))} autoFocus />
          </label>
          {needsFrom ? pick('From', fromId, setFromId) : null}
          {needsTo ? pick('To', toId, setToId) : null}
          {needsFrom && fromId && Number(amount) > fromBalance ? (
            <p className="rd-hint-line rd-warn-text rd-span">That is more than the {money(fromBalance)} the books show in {names[fromId]}.</p>
          ) : null}
          <label className="rd-span">
            <span>Note (optional)</span>
            <input aria-label="Move note" placeholder="Friday takings to bank" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
        </div>
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="rd-primary" aria-label="Save money move" disabled={busy} onClick={() => void save()}>
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </aside>
    </div>
  );
}

function AccountSheet({ codes, onClose, onDone }: { codes: string[]; onClose: () => void; onDone: (m: string) => Promise<void> }) {
  const [kind, setKind] = useState<'bank' | 'momo'>('momo');
  const [name, setName] = useState('');
  const [provider, setProvider] = useState('');
  const [number, setNumber] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  function nextCode() {
    for (let n = 1110; n < 1200; n += 1) if (!codes.includes(String(n))) return String(n);
    return `11${Date.now() % 100000}`;
  }

  async function save() {
    if (!name.trim()) return setError('Name the account.');
    if (!provider.trim()) return setError(kind === 'momo' ? 'Pick the network.' : 'Enter the bank.');
    setBusy(true);
    setError('');
    try {
      await api('/accounting/accounts', {
        method: 'POST',
        body: JSON.stringify({
          code: nextCode(),
          name: name.trim(),
          account_type: 'asset',
          liquid_kind: 'bank',
          bank_name: provider.trim(),
          account_number: number.replace(/[^0-9A-Za-z -]/g, '').trim() || null,
        }),
      });
      await onDone(`${name.trim()} added`);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label="New money account" onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>New money account</h2>
            <p>A bank account or a MoMo wallet the restaurant uses.</p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        <div className="rd-chips" role="radiogroup" aria-label="Account kind">
          <button type="button" role="radio" aria-checked={kind === 'momo'} className={kind === 'momo' ? 'on' : ''} onClick={() => { setKind('momo'); setProvider(''); }}>MoMo wallet</button>
          <button type="button" role="radio" aria-checked={kind === 'bank'} className={kind === 'bank' ? 'on' : ''} onClick={() => { setKind('bank'); setProvider(''); }}>Bank account</button>
        </div>
        <div className="rd-form-grid">
          <label className="rd-span">
            <span>Name</span>
            <input aria-label="Account name" placeholder={kind === 'momo' ? 'Restaurant MoMo' : 'GCB current account'} value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </label>
          {kind === 'momo' ? (
            <label>
              <span>Network</span>
              <select aria-label="MoMo network" value={provider} onChange={(e) => setProvider(e.target.value)}>
                <option value="">Pick a network</option>
                <option value="MTN MoMo">MTN MoMo</option>
                <option value="Telecel Cash">Telecel Cash</option>
                <option value="AirtelTigo Money">AirtelTigo Money</option>
              </select>
            </label>
          ) : (
            <label>
              <span>Bank</span>
              <input aria-label="Bank name" placeholder="GCB Bank" value={provider} onChange={(e) => setProvider(e.target.value)} />
            </label>
          )}
          <label>
            <span>{kind === 'momo' ? 'Wallet number' : 'Account number'} (optional)</span>
            <input aria-label="Account number" inputMode="numeric" value={number} onChange={(e) => setNumber(e.target.value)} />
          </label>
        </div>
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="rd-primary" aria-label="Save money account" disabled={busy} onClick={() => void save()}>
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </aside>
    </div>
  );
}
