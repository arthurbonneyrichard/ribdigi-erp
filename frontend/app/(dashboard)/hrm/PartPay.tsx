'use client';

/**
 * Weekly and fortnightly wages on a monthly payroll: pay part of the month during it; the
 * month's payroll works out PAYE and SSNIT on the whole month and takes these back.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';

type Row = Record<string, any>;
const money = (value: unknown) => formatMoney(Number(value || 0));
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const today = () => new Date().toISOString().slice(0, 10);
const FREQ: Record<string, string> = { weekly: 'Weekly', fortnightly: 'Fortnightly' };

export default function PartPay() {
  const [paidOn, setPaidOn] = useState(today());
  const [sheet, setSheet] = useState<Row | null>(null);
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [method, setMethod] = useState('mobile_money');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    try {
      const data = (await api(`/hrm/part-pay?paid_on=${paidOn}`))?.data || null;
      setSheet(data);
      const next: Record<string, string> = {};
      for (const p of data?.people || []) next[p.employee_id] = p.paid_on_this_day ? '' : String(p.suggested);
      setAmounts(next);
    } catch (err) {
      setError(problem(err));
    }
  }, [paidOn]);
  useEffect(() => {
    void load();
  }, [load]);

  if (!sheet || !sheet.people.length) {
    return (
      <section className="hr-box" aria-label="Weekly and fortnightly pay">
        <div className="hr-cardhead"><h2>Weekly and fortnightly pay</h2></div>
        <p className="hr-muted">Nobody is paid weekly or fortnightly. Set &quot;Paid&quot; on a staff record to use this.</p>
      </section>
    );
  }
  const lines = sheet.people.filter((p: Row) => Number(amounts[p.employee_id] || 0) > 0);
  const total = lines.reduce((sum: number, p: Row) => sum + Number(amounts[p.employee_id] || 0), 0);
  return (
    <section className="hr-box hr-scroll" aria-label="Weekly and fortnightly pay">
      <div className="hr-cardhead"><h2>Weekly and fortnightly pay</h2></div>
      <p className="hr-muted">
        Pays part of the month now. The {sheet.period} payroll works out PAYE and SSNIT on the whole month and takes these
        part-payments back, never below nil. Suggested: {sheet.percent}% of the week&apos;s or fortnight&apos;s basic.
      </p>
      {sheet.payroll ? <p className="hr-bad">The {sheet.period} payroll is already drawn up ({sheet.payroll}); part-payments for that month are closed.</p> : null}
      {notice ? <p className="hr-ok" role="status">{notice}</p> : null}
      {error ? <p className="hr-bad" role="alert">{error}</p> : null}
      <div className="hr-row">
        <input type="date" value={paidOn} onChange={(e) => setPaidOn(e.target.value)} aria-label="Part-payment date" />
        <select value={method} onChange={(e) => setMethod(e.target.value)} aria-label="Part-payment method">
          <option value="mobile_money">Mobile Money</option>
          <option value="cash">Cash</option>
          <option value="bank_transfer">Bank transfer</option>
          <option value="cheque">Cheque</option>
        </select>
      </div>
      <table>
        <thead><tr><th>Who</th><th>Paid</th><th>Already this month</th><th>Pay now</th></tr></thead>
        <tbody>
          {sheet.people.map((p: Row) => (
            <tr key={p.employee_id}>
              <td>{p.name}</td><td>{FREQ[p.frequency] || p.frequency}</td>
              <td className="hr-num">{money(p.paid_this_month)}</td>
              <td>
                {p.paid_on_this_day ? <span className="hr-muted">Paid on this day</span> : (
                  <input type="number" min="0" step="0.01" style={{ maxWidth: 130 }} value={amounts[p.employee_id] ?? ''} onChange={(e) => setAmounts({ ...amounts, [p.employee_id]: e.target.value })} aria-label={`Part-payment for ${p.name}`} />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        type="button" className="hr-primary" disabled={busy || !lines.length || Boolean(sheet.payroll)}
        onClick={async () => {
          setBusy(true);
          setError('');
          try {
            const res = await api('/hrm/part-pay', {
              method: 'POST',
              body: JSON.stringify({ paid_on: paidOn, method, lines: lines.map((p: Row) => ({ employee_id: p.employee_id, amount: Number(amounts[p.employee_id]) })) }),
            });
            setNotice(`Paid ${res?.data?.paid} people, ${money(res?.data?.total)}.`);
            await load();
          } catch (err) {
            setError(problem(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        Pay {money(total)}
      </button>
    </section>
  );
}
