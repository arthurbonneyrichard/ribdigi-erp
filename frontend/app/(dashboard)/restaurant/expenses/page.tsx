'use client';

/**
 * Restaurant expenses: the month's running costs (gas, rent, wages, repairs…), approvals,
 * regular bills and monthly budgets. Ingredients are bought under Purchasing, not here.
 * Uses the shared expenses engine (journals, approvals) with restaurant words.
 */

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import { uploadAttachment } from '../../../../lib/attachments';
import { money, problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Tab = 'month' | 'regular' | 'budgets';
type Sheet = { kind: 'add' } | { kind: 'regular'; row?: Row } | { kind: 'category'; row?: Row } | null;

const PAID_WITH: [string, string][] = [
  ['cash', 'Cash'],
  ['mobile_money', 'MoMo'],
  ['bank_transfer', 'Bank'],
  ['card', 'Card'],
  ['cheque', 'Cheque'],
];
const FREQUENCY: Record<string, string> = { daily: 'Every day', weekly: 'Every week', monthly: 'Every month', yearly: 'Every year' };
// Restaurant running costs on top of the standard ones (rent, utilities, salaries…).
// Ingredients are bought under Purchasing.
const STARTER_CATEGORIES: [string, string][] = [
  ['GAS', 'Gas and fuel'],
  ['REPAIR', 'Repairs'],
  ['CLEAN', 'Cleaning'],
  ['PACK', 'Packaging'],
  ['DELIV', 'Delivery'],
];

function monthKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function monthLabel(key: string) {
  const [y, mo] = key.split('-').map(Number);
  return new Date(y, mo - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}

function shortDate(value: unknown) {
  if (!value) return '';
  const d = new Date(String(value));
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export default function RestaurantExpensesPage() {
  const router = useRouter();
  const param = useSearchParams().get('tab');
  const tab: Tab = param === 'regular' || param === 'budgets' ? param : 'month';
  const setTab = (next: Tab) => router.replace(next === 'month' ? '?' : `?tab=${next}`, { scroll: false });

  const [expenses, setExpenses] = useState<Row[]>([]);
  const [categories, setCategories] = useState<Row[]>([]);
  const [regular, setRegular] = useState<Row[]>([]);
  const [month, setMonth] = useState(() => monthKey(new Date()));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [sheet, setSheet] = useState<Sheet>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState('');

  const load = useCallback(async () => {
    try {
      const [exp, cats, rec] = await Promise.all([
        api('/expenses'),
        api('/expenses/categories'),
        api('/expenses/recurring').catch(() => ({ data: [] })),
      ]);
      setExpenses(exp?.data || []);
      setCategories(cats?.data || []);
      setRegular(rec?.data || []);
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

  const activeCategories = categories.filter((c) => c.is_active !== false);
  const missingStarters = STARTER_CATEGORIES.filter(([code]) => !categories.some((c) => String(c.code).toUpperCase() === code));
  const inMonth = expenses.filter((e) => String(e.expense_date || e.created_at || '').slice(0, 7) === month);
  const approved = inMonth.filter((e) => e.status === 'approved');
  const pending = expenses.filter((e) => e.status === 'pending');
  const spent = approved.reduce((s, e) => s + Number(e.amount || 0), 0);
  const budgetTotal = activeCategories.reduce((s, c) => s + Number(c.budget_amount || 0), 0);
  const byCategory = useMemo(() => {
    const out: Record<string, number> = {};
    for (const e of approved) {
      const key = e.category_id || e.category || 'Other';
      out[key] = (out[key] || 0) + Number(e.amount || 0);
    }
    return out;
  }, [approved]);
  const months = useMemo(() => {
    const keys = new Set<string>([monthKey(new Date())]);
    for (const e of expenses) keys.add(String(e.expense_date || e.created_at || '').slice(0, 7));
    return Array.from(keys).filter(Boolean).sort().reverse();
  }, [expenses]);
  const categoryName = (e: Row) => categories.find((c) => c.id === e.category_id)?.name || e.category || 'Other';
  const topCategory = Object.entries(byCategory).sort((a, b) => b[1] - a[1])[0];

  async function done(message: string) {
    setSheet(null);
    setNotice(message);
    await load();
  }

  async function decide(row: Row, approve: boolean) {
    try {
      if (approve) await api(`/expenses/${row.id}/approve`, { method: 'POST', body: JSON.stringify({}) });
      else await api(`/expenses/${row.id}/reject`, { method: 'POST', body: JSON.stringify({ reason: reason.trim() }) });
      setRejecting(null);
      setReason('');
      await done(approve ? `${money(row.amount)} approved` : `${money(row.amount)} rejected`);
    } catch (err) {
      setError(problem(err));
    }
  }

  async function setUpCategories() {
    try {
      const have = new Set(categories.map((c) => String(c.code).toUpperCase()));
      for (const [code, name] of STARTER_CATEGORIES) {
        if (!have.has(code)) await api('/expenses/categories', { method: 'POST', body: JSON.stringify({ code, name }) });
      }
      await done('Restaurant cost types added');
    } catch (err) {
      setError(problem(err));
    }
  }

  async function generateDue() {
    try {
      const res = await api('/expenses/recurring/generate', { method: 'POST' });
      const made = Number(res?.data?.created ?? res?.data?.count ?? (Array.isArray(res?.data) ? res.data.length : 0));
      await done(made ? `${made} due ${made === 1 ? 'bill' : 'bills'} recorded` : 'No regular bills are due yet');
    } catch (err) {
      setError(problem(err));
    }
  }

  async function toggleRegular(row: Row) {
    try {
      await api(`/expenses/recurring/${row.id}`, { method: 'PATCH', body: JSON.stringify({ is_active: !row.is_active }) });
      await done(row.is_active ? `${row.payee || row.description || 'Bill'} paused` : `${row.payee || row.description || 'Bill'} back on`);
    } catch (err) {
      setError(problem(err));
    }
  }

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Expenses</h1>
          <p>Running costs like gas, rent, wages and repairs. Buy ingredients under <Link href="/restaurant/purchasing">Purchasing</Link>.</p>
        </div>
        <div className="rd-head-actions">
          {tab === 'regular' ? (
            <button type="button" className="rd-primary" aria-label="Add a regular bill" onClick={() => setSheet({ kind: 'regular' })}>+ Regular bill</button>
          ) : tab === 'budgets' ? (
            <button type="button" className="rd-primary" aria-label="Add a cost type" onClick={() => setSheet({ kind: 'category' })}>+ Cost type</button>
          ) : (
            <button type="button" className="rd-primary" aria-label="Record an expense" onClick={() => setSheet({ kind: 'add' })}>+ Expense</button>
          )}
        </div>
      </header>

      <div className="rd-tabs" role="tablist" aria-label="Expense sections">
        {([['month', 'Spending'], ['regular', 'Regular bills'], ['budgets', 'Budgets']] as const).map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? 'on' : ''} onClick={() => setTab(key)}>
            {label}
            {key === 'month' && pending.length ? <small>{pending.length} to approve</small> : null}
            {key === 'regular' ? <small>{regular.filter((r) => r.is_active).length}</small> : null}
          </button>
        ))}
      </div>

      {notice ? <div className="rd-notice" role="status" onClick={() => setNotice('')}>{notice}</div> : null}
      {error ? <div className="rd-error" role="alert" onClick={() => setError('')}>{error}</div> : null}
      {loading ? <div className="rd-empty">Loading expenses…</div> : null}

      {!loading && missingStarters.length && tab !== 'regular' ? (
        <div className="rd-panel rd-needs rd-needs-inline">
          <span>
            <strong>Add restaurant cost types?</strong>{' '}
            <span className="rd-hint-line">{missingStarters.map(([, n]) => n).join(', ')}.</span>
          </span>
          <button type="button" className="rd-primary" aria-label="Add restaurant cost types" onClick={() => void setUpCategories()}>Add them</button>
        </div>
      ) : null}

      {!loading && tab === 'month' ? (
        <>
          <div className="rd-period">
            <div className="rd-chips" role="group" aria-label="Month">
              {months.slice(0, 4).map((key) => (
                <button key={key} type="button" className={month === key ? 'on' : ''} aria-pressed={month === key} onClick={() => setMonth(key)}>
                  {monthLabel(key)}
                </button>
              ))}
            </div>
          </div>
          <div className="rd-kpis">
            <div className="rd-kpi hero">
              <span>Spent in {monthLabel(month)}</span>
              <strong>{money(spent)}</strong>
              <small>{approved.length} approved {approved.length === 1 ? 'expense' : 'expenses'}</small>
            </div>
            <div className="rd-kpi">
              <span>Budget left</span>
              <strong>{budgetTotal ? money(budgetTotal - spent) : '—'}</strong>
              <small>{budgetTotal ? `of ${money(budgetTotal)} a month` : <button type="button" className="rd-link" onClick={() => setTab('budgets')}>Set budgets</button>}</small>
            </div>
            <div className="rd-kpi">
              <span>Waiting for approval</span>
              <strong>{pending.length}</strong>
              <small>{money(pending.reduce((s, e) => s + Number(e.amount || 0), 0))}</small>
            </div>
            <div className="rd-kpi">
              <span>Biggest cost</span>
              <strong>{topCategory ? categories.find((c) => c.id === topCategory[0])?.name || topCategory[0] : '—'}</strong>
              <small>{topCategory ? money(topCategory[1]) : 'Nothing spent yet'}</small>
            </div>
          </div>

          {pending.length ? (
            <section className="rd-panel">
              <div className="rd-panel-head">
                <h2>To approve</h2>
                <small>Approved costs go on the books; rejected ones do not.</small>
              </div>
              <div className="rd-list rd-list-flat" aria-label="Expenses to approve">
                {pending.map((row) => (
                  <div key={row.id} className="rd-stock-row">
                    <div className="what">
                      <strong>{row.payee || row.description || categoryName(row)}</strong>
                      <small>
                        {categoryName(row)} · {shortDate(row.expense_date)}
                        {row.description && row.payee ? ` · ${row.description}` : ''}
                      </small>
                    </div>
                    <div className="onhand">
                      <strong>{money(row.amount)}</strong>
                      <small>{PAID_WITH.find(([k]) => k === row.payment_method)?.[1] || row.payment_method}</small>
                    </div>
                    {rejecting === row.id ? (
                      <input className="rd-inline-input" aria-label="Reject reason" placeholder="Why reject?" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
                    ) : (
                      <span />
                    )}
                    <div className="acts">
                      {rejecting === row.id ? (
                        <>
                          <button type="button" onClick={() => setRejecting(null)}>Back</button>
                          <button type="button" className="rd-danger" aria-label={`Confirm reject ${row.payee || 'expense'}`} disabled={!reason.trim()} onClick={() => void decide(row, false)}>Reject</button>
                        </>
                      ) : (
                        <>
                          <button type="button" className="rd-go" aria-label={`Approve ${row.payee || 'expense'}`} onClick={() => void decide(row, true)}>Approve</button>
                          <button type="button" className="rd-danger" aria-label={`Reject ${row.payee || 'expense'}`} onClick={() => { setRejecting(row.id); setReason(''); }}>Reject</button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <div className="rd-list" aria-label={`Expenses in ${monthLabel(month)}`}>
            {inMonth.filter((e) => e.status !== 'pending').length === 0 ? (
              <div className="rd-empty">
                <strong>No expenses in {monthLabel(month)}</strong>Record gas, rent or a repair with “+ Expense”.
              </div>
            ) : null}
            {inMonth
              .filter((e) => e.status !== 'pending')
              .sort((a, b) => String(b.expense_date).localeCompare(String(a.expense_date)))
              .map((row) => (
                <div key={row.id} className={`rd-stock-row${row.status === 'rejected' ? ' muted' : ''}`}>
                  <div className="what">
                    <strong>{row.payee || row.description || categoryName(row)}</strong>
                    <small>
                      {shortDate(row.expense_date)} · {categoryName(row)}
                      {row.description && row.payee ? ` · ${row.description}` : ''}
                      {row.has_attachment ? ' · 📎 receipt' : ''}
                    </small>
                  </div>
                  <div className="onhand">
                    <strong>{money(row.amount)}</strong>
                    <small>{PAID_WITH.find(([k]) => k === row.payment_method)?.[1] || row.payment_method}</small>
                  </div>
                  <span className={`rd-pill ${row.status === 'rejected' ? 'grey' : ''}`}>
                    {row.status === 'rejected' ? `Rejected${row.rejection_reason ? `: ${row.rejection_reason}` : ''}` : 'Approved'}
                  </span>
                  <span />
                </div>
              ))}
          </div>
        </>
      ) : null}

      {!loading && tab === 'regular' ? (
        <>
          <div className="rd-row-actions">
            <p className="rd-hint-line">Bills that come round again, like rent or wages. Each one is recorded on its due date.</p>
            <button type="button" className="right" aria-label="Record due regular bills now" onClick={() => void generateDue()}>Record due bills now</button>
          </div>
          <div className="rd-list" aria-label="Regular bills">
            {regular.length === 0 ? (
              <div className="rd-empty">
                <strong>No regular bills yet</strong>Add rent, wages or the gas delivery so they are recorded for you.
              </div>
            ) : null}
            {regular.map((row) => (
              <div key={row.id} className={`rd-stock-row${row.is_active ? '' : ' muted'}`}>
                <div className="what">
                  <strong>{row.payee || row.description || row.category || 'Bill'}</strong>
                  <small>
                    {categories.find((c) => c.id === row.category_id)?.name || row.category || 'Other'} · {FREQUENCY[row.frequency] || row.frequency}
                  </small>
                </div>
                <div className="onhand">
                  <strong>{money(row.amount)}</strong>
                  <small>{row.is_active ? `next ${shortDate(row.next_run_at)}` : 'paused'}</small>
                </div>
                <span className={`rd-pill ${row.is_active ? '' : 'grey'}`}>{row.is_active ? 'On' : 'Paused'}</span>
                <div className="acts">
                  <button type="button" aria-label={`${row.is_active ? 'Pause' : 'Resume'} ${row.payee || 'bill'}`} onClick={() => void toggleRegular(row)}>
                    {row.is_active ? 'Pause' : 'Resume'}
                  </button>
                  <button type="button" aria-label={`Edit ${row.payee || 'bill'}`} onClick={() => setSheet({ kind: 'regular', row })}>Edit</button>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : null}

      {!loading && tab === 'budgets' ? (
        <div className="rd-list" aria-label="Monthly budgets">
          {categories.map((c) => {
            const used = byCategory[c.id] || 0;
            const budget = Number(c.budget_amount || 0);
            const pct = budget ? Math.min(100, (used / budget) * 100) : 0;
            return (
              <div key={c.id} className={`rd-stock-row rd-budget-row${c.is_active === false ? ' muted' : ''}${budget && used > budget ? ' low' : ''}`}>
                <div className="what">
                  <strong>{c.name}</strong>
                  <small>{monthLabel(month)}: {money(used)} spent</small>
                  {budget ? (
                    <div className="rd-meter" aria-label={`${Math.round((used / budget) * 100)}% of budget used`}>
                      <div style={{ width: `${pct}%` }} />
                    </div>
                  ) : null}
                </div>
                <div className="onhand">
                  <strong>{budget ? money(budget) : '—'}</strong>
                  <small>{budget ? (used > budget ? `${money(used - budget)} over` : `${money(budget - used)} left`) : 'no budget'}</small>
                </div>
                <span className={`rd-pill ${c.is_active === false ? 'grey' : ''}`}>{c.is_active === false ? 'Hidden' : 'In use'}</span>
                <div className="acts">
                  <button type="button" aria-label={`Edit ${c.name}`} onClick={() => setSheet({ kind: 'category', row: c })}>Edit</button>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}

      {sheet?.kind === 'add' ? <ExpenseSheet categories={activeCategories} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet?.kind === 'regular' ? <RegularSheet row={sheet.row} categories={activeCategories} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet?.kind === 'category' ? <CategorySheet row={sheet.row} taken={categories.map((c) => String(c.code).toUpperCase())} onClose={() => setSheet(null)} onDone={done} /> : null}
    </div>
  );
}

function Drawer({ title, sub, onClose, children }: { title: string; sub?: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={title} onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>{title}</h2>
            {sub ? <p>{sub}</p> : null}
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        {children}
      </aside>
    </div>
  );
}

function useSave(onDone: (message: string) => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function run(fn: () => Promise<string>) {
    setBusy(true);
    setError('');
    try {
      await onDone(await fn());
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, run };
}

function CategoryChips({ categories, value, onChange }: { categories: Row[]; value: string; onChange: (id: string) => void }) {
  return (
    <div className="rd-chips rd-span" role="radiogroup" aria-label="Cost type">
      {categories.map((c) => (
        <button key={c.id} type="button" role="radio" aria-checked={value === c.id} className={value === c.id ? 'on' : ''} onClick={() => onChange(c.id)}>
          {c.name}
        </button>
      ))}
    </div>
  );
}

function PaidWith({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="rd-chips rd-span" role="radiogroup" aria-label="Paid with">
      {PAID_WITH.map(([key, label]) => (
        <button key={key} type="button" role="radio" aria-checked={value === key} className={value === key ? 'on' : ''} onClick={() => onChange(key)}>
          {label}
        </button>
      ))}
    </div>
  );
}

function ExpenseSheet({ categories, onClose, onDone }: { categories: Row[]; onClose: () => void; onDone: (m: string) => Promise<void> }) {
  const [amount, setAmount] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [method, setMethod] = useState('cash');
  const [payee, setPayee] = useState('');
  const [what, setWhat] = useState('');
  const [date, setDate] = useState(today());
  const [file, setFile] = useState<File | null>(null);
  const { busy, error, run } = useSave(onDone);

  return (
    <Drawer title="Record an expense" sub="Waits for approval if it is over your approval limit." onClose={onClose}>
      <div className="rd-form-grid">
        <label className="rd-span">
          <span>Amount</span>
          <input className="rd-big-input" aria-label="Expense amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ''))} autoFocus />
        </label>
        <span className="rd-field-label rd-span">Cost type</span>
        <CategoryChips categories={categories} value={categoryId} onChange={setCategoryId} />
        <span className="rd-field-label rd-span">Paid with</span>
        <PaidWith value={method} onChange={setMethod} />
        <label>
          <span>Paid to</span>
          <input aria-label="Paid to" placeholder="Gas station, landlord…" value={payee} onChange={(e) => setPayee(e.target.value)} />
        </label>
        <label>
          <span>Date</span>
          <input aria-label="Expense date" type="date" value={date} max={today()} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="rd-span">
          <span>What for (optional)</span>
          <input aria-label="What for" placeholder="2 gas cylinders" value={what} onChange={(e) => setWhat(e.target.value)} />
        </label>
        <label className="rd-span">
          <span>Receipt photo (optional)</span>
          <input aria-label="Receipt photo" type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </label>
      </div>
      {error ? <div className="rd-error" role="alert">{error}</div> : null}
      <div className="rd-actions">
        <button type="button" onClick={onClose}>Cancel</button>
        <button
          type="button"
          className="rd-primary"
          aria-label="Save expense"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              if (!(Number(amount) > 0)) throw new Error('Enter the amount.');
              if (!categoryId) throw new Error('Pick the cost type.');
              const res = await api('/expenses', {
                method: 'POST',
                body: JSON.stringify({
                  amount: Number(amount),
                  category_id: categoryId,
                  payment_method: method,
                  payee: payee.trim() || null,
                  description: what.trim() || null,
                  expense_date: date || null,
                }),
              });
              const row = res?.data || {};
              if (file && row.id) await uploadAttachment(`/expenses/${row.id}/attachment`, file);
              return row.status === 'pending' ? `${money(amount)} recorded, waiting for approval` : `${money(amount)} recorded`;
            })
          }
        >
          {busy ? 'Saving…' : 'Save'}
        </button>
      </div>
    </Drawer>
  );
}

function RegularSheet({ row, categories, onClose, onDone }: { row?: Row; categories: Row[]; onClose: () => void; onDone: (m: string) => Promise<void> }) {
  const [amount, setAmount] = useState(row ? String(row.amount ?? '') : '');
  const [categoryId, setCategoryId] = useState(String(row?.category_id || ''));
  const [method, setMethod] = useState(String(row?.payment_method || 'bank_transfer'));
  const [payee, setPayee] = useState(String(row?.payee || ''));
  const [what, setWhat] = useState(String(row?.description || ''));
  const [frequency, setFrequency] = useState(String(row?.frequency || 'monthly'));
  const { busy, error, run } = useSave(onDone);

  return (
    <Drawer title={row ? 'Edit regular bill' : 'New regular bill'} sub="Recorded for you each time it comes round." onClose={onClose}>
      <div className="rd-form-grid">
        <label>
          <span>Paid to</span>
          <input aria-label="Regular bill paid to" placeholder="Landlord" value={payee} onChange={(e) => setPayee(e.target.value)} autoFocus />
        </label>
        <label>
          <span>Amount</span>
          <input aria-label="Regular bill amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ''))} />
        </label>
        <label>
          <span>How often</span>
          <select aria-label="How often" value={frequency} onChange={(e) => setFrequency(e.target.value)}>
            {Object.entries(FREQUENCY).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          <span>What for (optional)</span>
          <input aria-label="Regular bill what for" placeholder="Shop rent" value={what} onChange={(e) => setWhat(e.target.value)} />
        </label>
        <span className="rd-field-label rd-span">Cost type</span>
        <CategoryChips categories={categories} value={categoryId} onChange={setCategoryId} />
        <span className="rd-field-label rd-span">Paid with</span>
        <PaidWith value={method} onChange={setMethod} />
      </div>
      {error ? <div className="rd-error" role="alert">{error}</div> : null}
      <div className="rd-actions">
        <button type="button" onClick={onClose}>Cancel</button>
        <button
          type="button"
          className="rd-primary"
          aria-label="Save regular bill"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              if (!(Number(amount) > 0)) throw new Error('Enter the amount.');
              if (!categoryId) throw new Error('Pick the cost type.');
              const body = {
                amount: Number(amount),
                category_id: categoryId,
                payment_method: method,
                frequency,
                payee: payee.trim() || null,
                description: what.trim() || null,
              };
              if (row) await api(`/expenses/recurring/${row.id}`, { method: 'PATCH', body: JSON.stringify(body) });
              else await api('/expenses/recurring', { method: 'POST', body: JSON.stringify(body) });
              return `${payee.trim() || 'Bill'} saved`;
            })
          }
        >
          {busy ? 'Saving…' : 'Save'}
        </button>
      </div>
    </Drawer>
  );
}

function CategorySheet({ row, taken, onClose, onDone }: { row?: Row; taken: string[]; onClose: () => void; onDone: (m: string) => Promise<void> }) {
  const [name, setName] = useState(String(row?.name || ''));
  const [budget, setBudget] = useState(row ? String(row.budget_amount ?? '') : '');
  const [active, setActive] = useState(row ? row.is_active !== false : true);
  const { busy, error, run } = useSave(onDone);

  function codeFor(text: string) {
    const base = text.toUpperCase().replace(/[^A-Z0-9]+/g, '').slice(0, 8) || 'COST';
    let code = base;
    for (let i = 2; taken.includes(code); i += 1) code = `${base.slice(0, 6)}${i}`;
    return code;
  }

  return (
    <Drawer title={row ? `Edit ${row.name}` : 'New cost type'} sub="A monthly budget warns you when spending runs over." onClose={onClose}>
      <div className="rd-form-grid">
        <label className="rd-span">
          <span>Name</span>
          <input aria-label="Cost type name" placeholder="Gas and fuel" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </label>
        <label>
          <span>Monthly budget</span>
          <input aria-label="Monthly budget" inputMode="decimal" placeholder="0 = no budget" value={budget} onChange={(e) => setBudget(e.target.value.replace(/[^0-9.]/g, ''))} />
        </label>
        {row ? (
          <label>
            <span>Show when recording</span>
            <select aria-label="Show cost type" value={active ? 'yes' : 'no'} onChange={(e) => setActive(e.target.value === 'yes')}>
              <option value="yes">Yes</option>
              <option value="no">No, hide it</option>
            </select>
          </label>
        ) : null}
      </div>
      {error ? <div className="rd-error" role="alert">{error}</div> : null}
      <div className="rd-actions">
        <button type="button" onClick={onClose}>Cancel</button>
        <button
          type="button"
          className="rd-primary"
          aria-label="Save cost type"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              if (!name.trim()) throw new Error('Name the cost type.');
              if (row) {
                await api(`/expenses/categories/${row.id}`, {
                  method: 'PATCH',
                  body: JSON.stringify({ name: name.trim(), budget_amount: Number(budget || 0), is_active: active }),
                });
              } else {
                await api('/expenses/categories', {
                  method: 'POST',
                  body: JSON.stringify({ code: codeFor(name), name: name.trim(), budget_amount: Number(budget || 0) }),
                });
              }
              return `${name.trim()} saved`;
            })
          }
        >
          {busy ? 'Saving…' : 'Save'}
        </button>
      </div>
    </Drawer>
  );
}
