'use client';

/** Pay out unused annual leave on a month's payroll. The days come off the person's leave at once. */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';

type Row = Record<string, any>;
const money = (value: unknown) => formatMoney(Number(value || 0));
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const thisMonth = () => new Date().toISOString().slice(0, 7);
const STATUS: Record<string, string> = { approved: 'Waiting for payroll', paid: 'Paid', cancelled: 'Cancelled' };

export default function LeavePay({ people }: { people: Row[] }) {
  const year = new Date().getFullYear();
  const [rows, setRows] = useState<Row[]>([]);
  const [form, setForm] = useState({ employee_id: '', year: String(year), days: '', period: thisMonth(), note: '' });
  const [balance, setBalance] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    try {
      setRows((await api('/hrm/leave-encashments'))?.data || []);
    } catch (err) {
      setError(problem(err));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (!form.employee_id) {
      setBalance(null);
      return;
    }
    api(`/hrm/employees/${form.employee_id}/leave-balance?year=${form.year}`)
      .then((r) => setBalance(r?.data || null))
      .catch(() => setBalance(null));
  }, [form.employee_id, form.year]);

  async function send(path: string, body: object, done: string) {
    setBusy(true);
    setError('');
    try {
      await api(path, { method: 'POST', body: JSON.stringify(body) });
      setNotice(done);
      await load();
      return true;
    } catch (err) {
      setError(problem(err));
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="hr-box hr-scroll" aria-label="Pay out unused leave">
      <div className="hr-cardhead"><h2>Pay out unused leave</h2></div>
      <p className="hr-muted">
        Pays annual leave days as money at the person&apos;s daily rate (basic ÷ working days). The days come off their leave now; the
        chosen month&apos;s payroll pays it, taxed as earnings with no SSNIT. Cancel before that payroll to give the days back.
      </p>
      {notice ? <p className="hr-ok" role="status">{notice}</p> : null}
      {error ? <p className="hr-bad" role="alert">{error}</p> : null}
      <div className="hr-row">
        <select value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })} aria-label="Leave payout person">
          <option value="">Choose who</option>
          {people.filter((p) => p.status === 'active' || !p.status).map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
        </select>
        <input type="number" min="2000" max={year} value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} aria-label="Leave year" style={{ maxWidth: 110 }} />
        <input type="number" min="1" placeholder="Days" value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })} aria-label="Days to pay out" style={{ maxWidth: 110 }} />
        <input type="month" value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} aria-label="Leave payout payroll month" style={{ maxWidth: 180 }} />
        <input placeholder="Note (optional)" maxLength={255} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} aria-label="Leave payout note" />
        <button
          type="button" className="hr-primary" disabled={busy || !form.employee_id || !(Number(form.days) > 0)}
          onClick={async () => {
            const ok = await send(
              '/hrm/leave-encashments',
              { employee_id: form.employee_id, year: Number(form.year), days: Number(form.days), period: form.period, note: form.note.trim() || null },
              'Leave payout approved for that month’s payroll.',
            );
            if (ok) setForm({ ...form, days: '', note: '' });
          }}
        >
          Approve payout
        </button>
      </div>
      {balance ? <p className="hr-muted">{balance.left} annual leave days left for {balance.year}.</p> : null}
      <table>
        <thead><tr><th>Who</th><th>Year</th><th>Days</th><th>Day rate</th><th>Amount</th><th>Payroll</th><th>Status</th><th /></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.employee_name}</td><td>{r.year}</td><td className="hr-num">{r.days}</td><td className="hr-num">{money(r.day_rate)}</td>
              <td className="hr-num">{money(r.amount)}</td><td>{r.period}</td><td>{STATUS[r.status] || r.status}</td>
              <td>
                {r.status === 'approved' && !r.on_payroll ? (
                  <button type="button" disabled={busy} aria-label={`Cancel leave payout for ${r.employee_name}`} onClick={() => void send(`/hrm/leave-encashments/${r.id}/cancel`, {}, 'Cancelled. The days are back.')}>
                    Cancel
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
          {rows.length === 0 ? <tr><td colSpan={8} className="hr-muted">No leave paid out yet.</td></tr> : null}
        </tbody>
      </table>
    </section>
  );
}
