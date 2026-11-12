'use client';

/**
 * Tips: managers share out the tips guests left (by who served, evenly, or by hours clocked),
 * someone without a share approves, then they are paid in cash or on payroll.
 * Everyone else sees their own tips.
 */

import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../../lib/api';
import { getMe } from '../../../../lib/meCache';
import { money, problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

const MANAGERS = ['company_admin', 'restaurant_manager', 'super_admin'];
const HOW = [
  ['by_server', 'To whoever served', 'Each bill’s tip goes to the waiter who opened it.'],
  ['equal', 'Evenly', 'Split equally between the people you pick.'],
  ['hours', 'By hours worked', 'Split by hours each person clocked. Needs their staff record.'],
] as const;
const PAY_WITH = [
  ['cash', 'Cash'],
  ['mobile_money', 'Mobile Money'],
  ['bank_transfer', 'Bank transfer'],
] as const;
const STATUS: Record<string, string> = { draft: 'Waiting for approval', approved: 'Approved, to pay', paid: 'Paid', cancelled: 'Cancelled' };

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function daysAgo(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return iso(d);
}

function MyTips() {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    api('/restaurant/tips/mine').then((r) => setRows(r?.data || [])).catch((e) => setError(problem(e)));
  }, []);
  return (
    <section className="rd-panel">
      <div className="rd-panel-head"><h2>My tips</h2></div>
      {error ? <div className="rd-error" role="alert">{error}</div> : null}
      {rows.length === 0 ? <div className="rd-empty">No tips shared to you yet.</div> : (
        <div className="rd-table-wrap">
          <table className="rd-table">
            <thead><tr><th>Days</th><th>How paid</th><th className="num">Amount</th><th>Status</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.run_number}>
                  <td>{r.date_from === r.date_to ? r.date_from : `${r.date_from} to ${r.date_to}`}</td>
                  <td>{r.pay_by === 'payroll' ? `Payslip ${r.period}` : 'Cash'}</td>
                  <td className="num">{money(r.amount)}</td>
                  <td>{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function RestaurantTipsPage() {
  const [role, setRole] = useState('');
  const [from, setFrom] = useState(daysAgo(6));
  const [to, setTo] = useState(iso(new Date()));
  const [pool, setPool] = useState<Row | null>(null);
  const [runs, setRuns] = useState<Row[]>([]);
  const [staff, setStaff] = useState<Row[]>([]);
  const [method, setMethod] = useState<string>('by_server');
  const [payBy, setPayBy] = useState('cash');
  const [period, setPeriod] = useState(iso(new Date()).slice(0, 7));
  const [picked, setPicked] = useState<string[]>([]);
  const [payWith, setPayWith] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const manager = MANAGERS.includes(role);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    try {
      const [p, r, s] = await Promise.all([
        api(`/restaurant/tips/unshared?date_from=${from}&date_to=${to}`),
        api('/restaurant/tips/runs'),
        api('/restaurant/tips/staff'),
      ]);
      setPool(p?.data || null);
      setRuns(r?.data || []);
      setStaff(s?.data || []);
      setError('');
    } catch (err) {
      setError(problem(err));
    }
  }, [from, to]);

  useEffect(() => {
    if (manager) void load();
  }, [manager, load]);

  async function act(path: string, body: object, done: string) {
    setBusy(true);
    setError('');
    try {
      await api(path, { method: 'POST', body: JSON.stringify(body) });
      setNotice(done);
      await load();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  if (!role) return null;
  if (!manager) {
    return (
      <div className="rdesk">
        <header className="rd-head"><div><h1>Tips</h1><p>What has been shared to you, and whether it is paid.</p></div></header>
        <MyTips />
      </div>
    );
  }

  const needsRecord = method === 'hours' || payBy === 'payroll';
  const canShare = Number(pool?.total || 0) > 0 && (method === 'by_server' || picked.length > 0) && (payBy === 'cash' || period);

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Tips</h1>
          <p>Tips guests leave are held for staff, never counted as sales. Share them out, approve, then pay.</p>
        </div>
      </header>
      {notice ? <div className="rd-notice" role="status">{notice}</div> : null}
      {error ? <div className="rd-error" role="alert">{error}</div> : null}

      <section className="rd-panel">
        <div className="rd-panel-head"><h2>Share out tips</h2></div>
        <div className="rd-form-grid">
          <label><span>From</span><input type="date" aria-label="Tips from" value={from} max={to} onChange={(e) => e.target.value && setFrom(e.target.value)} /></label>
          <label><span>To</span><input type="date" aria-label="Tips to" value={to} min={from} onChange={(e) => e.target.value && setTo(e.target.value)} /></label>
        </div>
        <div className="rd-kpis">
          <div className="rd-kpi hero">
            <span>Not yet shared</span>
            <strong>{money(pool?.total)}</strong>
            <small>{pool?.tips || 0} {pool?.tips === 1 ? 'tip' : 'tips'}</small>
          </div>
          {(pool?.by_server || []).map((s: Row) => (
            <div className="rd-kpi" key={s.user_id || 'none'}><span>Served by {s.name}</span><strong>{money(s.amount)}</strong></div>
          ))}
        </div>

        <span className="rd-field-label">How to share</span>
        <div className="rd-chips" role="radiogroup" aria-label="How to share">
          {HOW.map(([key, label]) => (
            <button key={key} type="button" role="radio" aria-checked={method === key} className={method === key ? 'on' : ''} onClick={() => setMethod(key)}>{label}</button>
          ))}
        </div>
        <p className="rd-hint-line">{HOW.find(([k]) => k === method)?.[2]}</p>

        {method !== 'by_server' ? (
          <>
            <span className="rd-field-label">Who shares</span>
            <div className="rd-chips" role="group" aria-label="Who shares">
              {staff.map((p) => {
                const on = picked.includes(p.id);
                const blocked = needsRecord && !p.has_staff_record;
                return (
                  <button
                    key={p.id} type="button" aria-pressed={on} disabled={blocked} className={on ? 'on' : ''}
                    title={blocked ? 'Needs a staff record with the same email' : undefined}
                    onClick={() => setPicked(on ? picked.filter((x) => x !== p.id) : [...picked, p.id])}
                  >
                    {p.name}
                  </button>
                );
              })}
            </div>
          </>
        ) : null}

        <span className="rd-field-label">Pay by</span>
        <div className="rd-chips" role="radiogroup" aria-label="Pay tips by">
          {[['cash', 'Cash out'], ['payroll', 'On the payslip']].map(([key, label]) => (
            <button key={key} type="button" role="radio" aria-checked={payBy === key} className={payBy === key ? 'on' : ''} onClick={() => setPayBy(key)}>{label}</button>
          ))}
        </div>
        {payBy === 'payroll' ? (
          <div className="rd-form-grid">
            <label><span>Payroll month</span><input type="month" aria-label="Tips payroll month" value={period} onChange={(e) => setPeriod(e.target.value)} /></label>
          </div>
        ) : null}
        {needsRecord ? <p className="rd-hint-line">Hours and payslips need each person&apos;s staff record (HR) to have the email they sign in with.</p> : null}
        <div className="rd-actions">
          <button
            type="button" className="rd-primary" disabled={busy || !canShare}
            onClick={() =>
              void act(
                '/restaurant/tips/runs',
                { date_from: from, date_to: to, method, pay_by: payBy, period: payBy === 'payroll' ? period : null, user_ids: method === 'by_server' ? [] : picked },
                'Tips shared out. Someone who gets no share approves it next.',
              )
            }
          >
            Share out {money(pool?.total)}
          </button>
        </div>
      </section>

      <section className="rd-panel">
        <div className="rd-panel-head"><h2>Share-outs</h2></div>
        {runs.length === 0 ? <div className="rd-empty">No tips shared out yet.</div> : runs.map((r) => (
          <div className="rd-card" key={r.id}>
            <div className="rd-card-top">
              <strong>{r.run_number} · {r.date_from === r.date_to ? r.date_from : `${r.date_from} to ${r.date_to}`}</strong>
              <span className={`rd-pill ${r.status === 'cancelled' ? 'grey' : r.status === 'paid' ? '' : 'wait'}`}>{STATUS[r.status] || r.status}</span>
            </div>
            <p className="rd-hint-line">
              {money(r.total)} from {r.tips} {r.tips === 1 ? 'tip' : 'tips'} · {HOW.find(([k]) => k === r.method)?.[1]} · {r.pay_by === 'payroll' ? `on the ${r.period} payslips` : 'cash out'}
              {r.created_by ? ` · by ${r.created_by}` : ''}{r.approved_by ? `, approved by ${r.approved_by}` : ''}
            </p>
            <div className="rd-table-wrap">
              <table className="rd-table">
                <thead><tr><th>Person</th>{r.method === 'hours' ? <th className="num">Hours</th> : null}<th className="num">Share</th></tr></thead>
                <tbody>
                  {r.shares.map((s: Row) => (
                    <tr key={s.user_id}><td>{s.name}</td>{r.method === 'hours' ? <td className="num">{s.hours}</td> : null}<td className="num">{money(s.amount)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="rd-row-actions">
              {r.status === 'draft' ? (
                <button type="button" className="rd-primary" disabled={busy} aria-label={`Approve tips ${r.run_number}`} onClick={() => void act(`/restaurant/tips/runs/${r.id}/approve`, {}, 'Approved.')}>Approve</button>
              ) : null}
              {r.status === 'approved' && r.pay_by === 'cash' ? (
                <>
                  <select aria-label={`Pay tips ${r.run_number} with`} value={payWith[r.id] || 'cash'} onChange={(e) => setPayWith({ ...payWith, [r.id]: e.target.value })}>
                    {PAY_WITH.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select>
                  <button type="button" className="rd-primary" disabled={busy} aria-label={`Pay tips ${r.run_number}`} onClick={() => void act(`/restaurant/tips/runs/${r.id}/pay`, { method: payWith[r.id] || 'cash' }, 'Tips paid.')}>
                    Mark paid
                  </button>
                </>
              ) : null}
              {r.status === 'approved' && r.pay_by === 'payroll' ? <span className="rd-hint-line">Paid when the {r.period} payroll is approved.</span> : null}
              {r.status === 'draft' || (r.status === 'approved' && !r.shares.some((s: Row) => s.on_payroll)) ? (
                <button type="button" className="rd-danger" disabled={busy} aria-label={`Cancel tips ${r.run_number}`} onClick={() => void act(`/restaurant/tips/runs/${r.id}/cancel`, {}, 'Cancelled. The tips are back to be shared.')}>Cancel</button>
              ) : null}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
