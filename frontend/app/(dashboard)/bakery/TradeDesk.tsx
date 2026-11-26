'use client';

/**
 * Bakery trade: shops, hotels and schools supplied on account. Standing orders become one
 * invoice per customer a day; payments clear the oldest invoices first; statements print.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { printPaymentReceipt } from '../../../lib/receiptPrint';
import { bakeryApi, openPrintable } from '../../../lib/bakeryTill';
import { formatMoney } from '../../../lib/format';

type Row = Record<string, any>;
const money = (value: unknown) => formatMoney(Number(value || 0));
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const PAY = [
  { id: 'cash', label: 'Cash (into the till)' },
  { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'bank_transfer', label: 'Bank transfer' },
  { id: 'card', label: 'Card' },
];

export default function TradeDesk({ items, isManager }: { items: Row[]; isManager: boolean }) {
  const [customers, setCustomers] = useState<Row[]>([]);
  const [invoices, setInvoices] = useState<Row[]>([]);
  const [pick, setPick] = useState('');
  const [statement, setStatement] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const blank = { name: '', phone: '', address: '', credit_limit: '', trade_discount_pct: '', terms_days: '7' };
  const [form, setForm] = useState(blank);
  const [standing, setStanding] = useState({ product_id: '', quantity: '', days: '1111100' });
  const [invoiceLines, setInvoiceLines] = useState<{ product_id: string; quantity: string }[]>([{ product_id: '', quantity: '' }]);
  const [override, setOverride] = useState(false);
  const [payment, setPayment] = useState({ amount: '', method: 'mobile_money', reference: '' });
  const [voiding, setVoiding] = useState<{ id: string; reason: string; restock: boolean } | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, i] = await Promise.all([bakeryApi('/bakery/trade/customers'), bakeryApi('/bakery/trade/invoices')]);
      setCustomers(c?.data || []);
      setInvoices(i?.data || []);
    } catch (err) {
      setError(problem(err));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  async function run(path: string, body: object | null, done: string, method = 'POST') {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await bakeryApi(path, { method, body: body ? JSON.stringify(body) : undefined });
      setNotice(done);
      await load();
      return res?.data ?? true;
    } catch (err) {
      setError(problem(err));
      return null;
    } finally {
      setBusy(false);
    }
  }

  const customer = customers.find((c) => c.id === pick) || null;
  const owedTotal = customers.reduce((t, c) => t + Number(c.balance || 0), 0);
  const overdueTotal = customers.reduce((t, c) => t + Number(c.overdue || 0), 0);
  const mine = invoices.filter((i) => !pick || i.customer_id === pick);

  async function loadStatement() {
    if (!pick) return;
    try {
      setStatement((await bakeryApi(`/bakery/trade/customers/${pick}/statement`))?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }

  function printStatement() {
    if (!statement) return;
    const page = window.open('', '_blank', 'width=720,height=900');
    if (!page) return;
    const esc = (v: unknown) => String(v ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] as string);
    const rows = statement.lines
      .map((l: Row) => `<tr><td>${esc(l.date)}</td><td>${esc(l.what)}</td><td style="text-align:right">${l.debit ? money(l.debit) : ''}</td><td style="text-align:right">${l.credit ? money(l.credit) : ''}</td><td style="text-align:right">${money(l.balance)}</td></tr>`)
      .join('');
    const age = statement.owed_by_age;
    page.document.write(
      `<html><body style="font-family:Arial;max-width:720px;margin:24px auto"><h2>Statement: ${esc(statement.customer.name)}</h2>`
        + `<p>${esc(statement.start_date)} to ${esc(statement.end_date)}</p><p>Opening balance ${money(statement.opening_balance)}</p>`
        + `<table style="width:100%;border-collapse:collapse"><tr><th align="left">Date</th><th align="left">What</th><th>Charged</th><th>Paid</th><th>Balance</th></tr>${rows}</table>`
        + `<h3>Owed now ${money(statement.closing_balance)}</h3>`
        + `<p>Not yet due ${money(age.current)} · 1–30 days late ${money(age['1_30'])} · 31–60 days ${money(age['31_60'])} · over 60 days ${money(age.over_60)}</p>`
        + '</body></html>',
    );
    page.document.close();
    page.focus();
    setTimeout(() => page.print(), 300); // printed from here: the strict script policy blocks scripts written into the page
  }

  return (
    <div className="bk-trade">
      {error ? <div className="bk-banner bad" role="alert">{error}</div> : null}
      {notice ? <div className="bk-banner ok" role="status">{notice}</div> : null}

      <section className="bk-box" aria-label="Today's trade deliveries">
        <div className="bk-row bk-spread">
          <h2>Today&apos;s trade deliveries</h2>
          <span className="bk-muted">Owed by trade customers {money(owedTotal)}{overdueTotal > 0 ? ` · ${money(overdueTotal)} late` : ''}</span>
        </div>
        <p className="bk-muted">Turns every standing order due today into one invoice per customer. It runs once a day per customer.</p>
        <button
          type="button" className="bk-primary" disabled={busy}
          onClick={async () => {
            const res = (await run('/bakery/trade/run', null, 'Deliveries made')) as Row | null;
            if (res) {
              const skipped = (res.skipped || []).map((s: Row) => `${s.customer}: ${s.reason}`).join('; ');
              setNotice(`${res.made.length} invoice(s) made.${skipped ? ` Not made: ${skipped}` : ''}`);
            }
          }}
        >Make today&apos;s deliveries</button>
      </section>

      <section className="bk-box bk-scroll" aria-label="Trade customers">
        <h2>Trade customers</h2>
        <table>
          <thead><tr><th>Customer</th><th>Owes</th><th>Late</th><th>Limit</th><th>Trade price</th><th>Standing orders</th><th /></tr></thead>
          <tbody>
            {customers.map((c) => (
              <tr key={c.id} className={c.id === pick ? 'on' : ''}>
                <td>{c.name}{!c.is_active ? <div className="bk-muted">Switched off</div> : null}<div className="bk-muted">{c.phone || ''}</div></td>
                <td className="bk-num">{money(c.balance)}</td>
                <td className="bk-num">{Number(c.overdue) > 0 ? <span className="bk-pill bad">{money(c.overdue)}</span> : '—'}</td>
                <td className="bk-num">{Number(c.credit_limit) > 0 ? money(c.credit_limit) : 'No limit'}</td>
                <td>{Number(c.trade_discount_pct) > 0 ? `${c.trade_discount_pct}% off` : 'Shop price'} · {c.terms_days} days</td>
                <td>{(c.standing_orders || []).map((s: Row) => `${s.quantity} ${s.name} (${DAYS.filter((_, i) => s.days[i] === '1').join(' ')})`).join('; ') || '—'}</td>
                <td><button type="button" onClick={() => { setPick(c.id); setStatement(null); }} aria-label={`Open ${c.name}`}>Open</button></td>
              </tr>
            ))}
            {customers.length === 0 ? <tr><td colSpan={7} className="bk-muted">No trade customers yet.</td></tr> : null}
          </tbody>
        </table>
      </section>

      {isManager ? (
        <section className="bk-box" aria-label="Add a trade customer">
          <h2>Add a trade customer</h2>
          <div className="bk-form">
            <label className="bk-span2"><span>Name</span><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} aria-label="Customer name" /></label>
            <label><span>Phone</span><input value={form.phone} placeholder="+233…" onChange={(e) => setForm({ ...form, phone: e.target.value })} aria-label="Customer phone" /></label>
            <label className="bk-span2"><span>Address</span><input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} aria-label="Customer address" /></label>
            <label><span>Credit limit</span><input type="number" min="0" step="0.01" value={form.credit_limit} placeholder="0 = no limit" onChange={(e) => setForm({ ...form, credit_limit: e.target.value })} aria-label="Credit limit" /></label>
            <label><span>Trade discount %</span><input type="number" min="0" max="60" value={form.trade_discount_pct} onChange={(e) => setForm({ ...form, trade_discount_pct: e.target.value })} aria-label="Trade discount percent" /></label>
            <label><span>Days to pay</span><input type="number" min="0" max="120" value={form.terms_days} onChange={(e) => setForm({ ...form, terms_days: e.target.value })} aria-label="Days to pay" /></label>
            <button
              type="button" className="bk-primary" disabled={busy || form.name.trim().length < 1}
              onClick={async () => {
                const ok = await run('/bakery/trade/customers', {
                  name: form.name.trim(), phone: form.phone.replace(/[\s-]/g, '') || null, address: form.address.trim() || null,
                  credit_limit: Number(form.credit_limit || 0), trade_discount_pct: Number(form.trade_discount_pct || 0),
                  terms_days: Number(form.terms_days || 0),
                }, 'Customer added');
                if (ok) setForm(blank);
              }}
            >Add customer</button>
          </div>
        </section>
      ) : null}

      {customer ? (
        <section className="bk-box" aria-label={`Customer ${customer.name}`}>
          <div className="bk-row bk-spread">
            <h2>{customer.name}</h2>
            <span>Owes <b>{money(customer.balance)}</b>{customer.available_credit != null ? ` · ${money(customer.available_credit)} credit left` : ''}</span>
          </div>

          {isManager ? (
            <>
              <h3 className="bk-sub">Standing order</h3>
              <div className="bk-form">
                <label><span>Item</span>
                  <select value={standing.product_id} onChange={(e) => setStanding({ ...standing, product_id: e.target.value })} aria-label="Standing order item">
                    <option value="">Choose</option>
                    {items.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
                  </select>
                </label>
                <label><span>How many</span><input type="number" min="0" value={standing.quantity} onChange={(e) => setStanding({ ...standing, quantity: e.target.value })} aria-label="Standing order quantity" /></label>
                <div className="bk-days" role="group" aria-label="Days">
                  {DAYS.map((d, i) => (
                    <label key={d} className="bk-check">
                      <input
                        type="checkbox" checked={standing.days[i] === '1'}
                        onChange={(e) => setStanding({ ...standing, days: standing.days.slice(0, i) + (e.target.checked ? '1' : '0') + standing.days.slice(i + 1) })}
                      /> <span>{d}</span>
                    </label>
                  ))}
                </div>
                <button
                  type="button" disabled={busy || !standing.product_id || !(Number(standing.quantity) > 0) || !standing.days.includes('1')}
                  onClick={async () => {
                    if (await run(`/bakery/trade/customers/${customer.id}/standing`, { product_id: standing.product_id, quantity: Number(standing.quantity), days: standing.days }, 'Standing order saved', 'PUT')) {
                      setStanding({ product_id: '', quantity: '', days: '1111100' });
                    }
                  }}
                >Save standing order</button>
              </div>
              {(customer.standing_orders || []).map((s: Row) => (
                <div className="bk-line" key={s.id}>
                  <span>{s.quantity} {s.name} · {DAYS.filter((_, i) => s.days[i] === '1').join(' ')}</span>
                  <button type="button" className="bk-danger" disabled={busy} onClick={() => run(`/bakery/trade/standing/${s.id}`, null, 'Standing order stopped', 'DELETE')}>Stop</button>
                </div>
              ))}
            </>
          ) : null}

          <h3 className="bk-sub">Deliver now (invoice on account)</h3>
          {invoiceLines.map((line, idx) => (
            <div className="bk-form" key={idx}>
              <label><span>Item</span>
                <select value={line.product_id} onChange={(e) => setInvoiceLines(invoiceLines.map((l, j) => (j === idx ? { ...l, product_id: e.target.value } : l)))} aria-label={`Invoice item ${idx + 1}`}>
                  <option value="">Choose</option>
                  {items.map((i) => <option key={i.id} value={i.id}>{i.name} ({i.stock_qty} left)</option>)}
                </select>
              </label>
              <label><span>How many</span><input type="number" min="0" value={line.quantity} onChange={(e) => setInvoiceLines(invoiceLines.map((l, j) => (j === idx ? { ...l, quantity: e.target.value } : l)))} aria-label={`Invoice quantity ${idx + 1}`} /></label>
            </div>
          ))}
          <div className="bk-row">
            <button type="button" onClick={() => setInvoiceLines([...invoiceLines, { product_id: '', quantity: '' }])}>Add a line</button>
            {isManager ? <label className="bk-check"><input type="checkbox" checked={override} onChange={(e) => setOverride(e.target.checked)} /> <span>Allow past the credit limit</span></label> : null}
            <button
              type="button" className="bk-primary"
              disabled={busy || !invoiceLines.some((l) => l.product_id && Number(l.quantity) > 0)}
              onClick={async () => {
                const lines = invoiceLines.filter((l) => l.product_id && Number(l.quantity) > 0).map((l) => ({ product_id: l.product_id, quantity: Number(l.quantity) }));
                if (await run('/bakery/trade/invoices', { customer_id: customer.id, lines, override_limit: override }, 'Invoice made')) {
                  setInvoiceLines([{ product_id: '', quantity: '' }]);
                  setOverride(false);
                }
              }}
            >Make invoice</button>
          </div>

          <h3 className="bk-sub">Take a payment</h3>
          <div className="bk-form">
            <label><span>Amount</span><input type="number" min="0" step="0.01" value={payment.amount} onChange={(e) => setPayment({ ...payment, amount: e.target.value })} aria-label="Payment amount" /></label>
            <label><span>Paid by</span>
              <select value={payment.method} onChange={(e) => setPayment({ ...payment, method: e.target.value })} aria-label="Payment method">
                {PAY.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </label>
            <label><span>Reference</span><input value={payment.reference} onChange={(e) => setPayment({ ...payment, reference: e.target.value })} aria-label="Payment reference" /></label>
            <button
              type="button" className="bk-primary" disabled={busy || !(Number(payment.amount) > 0)}
              onClick={async () => {
                const paid = await run(`/bakery/trade/customers/${customer.id}/payments`, { amount: Number(payment.amount), method: payment.method, reference: payment.reference.trim() || null }, 'Payment recorded');
                if (paid) {
                  printPaymentReceipt('bakery_customer_payment', paid.id);
                  setPayment({ ...payment, amount: '', reference: '' });
                }
              }}
            >Record payment</button>
          </div>

          <div className="bk-row">
            <button type="button" onClick={() => void loadStatement()}>Statement this month</button>
            {statement ? <button type="button" onClick={printStatement}>Print statement</button> : null}
            {isManager ? (
              <button type="button" className="bk-danger" disabled={busy} onClick={() => run(`/bakery/trade/customers/${customer.id}`, { is_active: !customer.is_active }, customer.is_active ? 'Customer switched off' : 'Customer switched on', 'PATCH')}>
                {customer.is_active ? 'Switch off' : 'Switch on'}
              </button>
            ) : null}
          </div>
          {statement ? (
            <table aria-label="Statement">
              <thead><tr><th>Date</th><th>What</th><th>Charged</th><th>Paid</th><th>Balance</th></tr></thead>
              <tbody>
                <tr><td>{statement.start_date}</td><td>Opening balance</td><td /><td /><td className="bk-num">{money(statement.opening_balance)}</td></tr>
                {statement.lines.map((l: Row, i: number) => (
                  <tr key={i}><td>{l.date}</td><td>{l.what}</td><td className="bk-num">{l.debit ? money(l.debit) : ''}</td><td className="bk-num">{l.credit ? money(l.credit) : ''}</td><td className="bk-num">{money(l.balance)}</td></tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </section>
      ) : null}

      <section className="bk-box bk-scroll" aria-label="Trade invoices">
        <h2>{customer ? `Invoices: ${customer.name}` : 'Trade invoices'}</h2>
        <table>
          <thead><tr><th>Invoice</th><th>Customer</th><th>Date</th><th>Pay by</th><th>Total</th><th>Still owed</th><th>Status</th><th /></tr></thead>
          <tbody>
            {mine.map((i) => (
              <tr key={i.id}>
                <td>{i.invoice_number}{i.from_standing ? <div className="bk-muted">Standing order</div> : null}</td>
                <td>{i.customer_name}</td><td>{i.invoice_date}</td><td>{i.due_date}</td>
                <td className="bk-num">{money(i.total)}</td><td className="bk-num">{money(i.balance)}</td>
                <td><span className={`bk-pill ${i.status === 'paid' ? 'ok' : i.overdue || i.status === 'void' ? 'bad' : ''}`}>{i.status === 'void' ? 'Void' : i.overdue ? 'Late' : i.status === 'part_paid' ? 'Part paid' : i.status === 'paid' ? 'Paid' : 'Open'}</span></td>
                <td className="bk-row">
                  <button type="button" onClick={() => void openPrintable(`/bakery/trade/invoices/${i.id}/print`)} aria-label={`Print ${i.invoice_number}`}>Print</button>
                  {isManager && i.status === 'open' ? <button type="button" className="bk-danger" onClick={() => setVoiding({ id: i.id, reason: '', restock: false })}>Void</button> : null}
                </td>
              </tr>
            ))}
            {mine.length === 0 ? <tr><td colSpan={8} className="bk-muted">No invoices yet.</td></tr> : null}
          </tbody>
        </table>
        {voiding ? (
          <div className="bk-form" aria-label="Void invoice">
            <label className="bk-span2"><span>Why void it</span><input autoFocus value={voiding.reason} onChange={(e) => setVoiding({ ...voiding, reason: e.target.value })} aria-label="Void reason" /></label>
            <label className="bk-check"><input type="checkbox" checked={voiding.restock} onChange={(e) => setVoiding({ ...voiding, restock: e.target.checked })} /> <span>The goods came back and can be sold</span></label>
            <button type="button" className="bk-danger" disabled={busy || voiding.reason.trim().length < 3} onClick={async () => { if (await run(`/bakery/trade/invoices/${voiding.id}/void`, { reason: voiding.reason.trim(), restock: voiding.restock }, 'Invoice voided')) setVoiding(null); }}>Void invoice</button>
            <button type="button" onClick={() => setVoiding(null)}>Go back</button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
