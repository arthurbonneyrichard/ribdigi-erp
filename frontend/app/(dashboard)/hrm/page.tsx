'use client';

/**
 * HRM desk. Its own screen on its own tables (hrm_*): people, leave, attendance, payroll,
 * reports, settings, and each person's own file under My pay and leave.
 */

import { useSearchParams } from 'next/navigation';
import React, { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import DeskDashboard from '../../../components/DeskDashboard';
import DeskIcon from '../../../components/DeskIcon';
import './hrm.css';

type Row = Record<string, any>;

const SCREENS: Record<string, { title: string; sub: string; icon: string }> = {
  today: { title: 'Dashboard', sub: '', icon: 'home' },
  people: { title: 'Employees', sub: 'Everyone on the payroll, their pay and their department.', icon: 'users' },
  leave: { title: 'Leave', sub: 'Time off asked for, approved and taken.', icon: 'calendar' },
  attendance: { title: 'Attendance', sub: 'Who came in today, and when.', icon: 'clock' },
  payroll: { title: 'Payroll', sub: 'Draw up the month, check it, approve it and pay it.', icon: 'cash' },
  reports: { title: 'Reports', sub: 'Payroll by month and department, and leave taken.', icon: 'chart' },
  settings: { title: 'Pay rates', sub: 'PAYE bands, SSNIT and the other rates payroll uses.', icon: 'tag' },
  me: { title: 'My pay and leave', sub: 'Your payslips and your time off.', icon: 'wallet' },
};
const TABS = Object.keys(SCREENS).map((id) => ({ id }));

const ICON_WORDS: [string, string][] = [
  ['class', 'calendarCheck'],
  ['leave', 'calendar'],
  ['payslip', 'receipt'],
  ['pay', 'cash'],
  ['member', 'users'],
  ['staff', 'users'],
  ['employee', 'users'],
  ['plan', 'tag'],
  ['door', 'door'],
  ['ending', 'alert'],
  ['department', 'chart'],
  ['month', 'chart'],
  ['rate', 'tag'],
  ['attend', 'clock'],
  ['draw', 'plus'],
  ['add', 'plus'],
];
function Head({ title, icon, meta }: { title: string; icon?: string; meta?: React.ReactNode }) {
  const lower = title.toLowerCase();
  const pick = icon || ICON_WORDS.find(([word]) => lower.includes(word))?.[1] || 'chart';
  return (
    <div className="hr-cardhead">
      <span className="hr-ico" aria-hidden="true"><DeskIcon name={pick} size={18} /></span>
      <h2>{title}</h2>
      {meta ? <span className="hr-meta">{meta}</span> : null}
    </div>
  );
}
const ROLE_TABS: Record<string, string[]> = {
  hrm_officer: ['today', 'people', 'leave', 'attendance', 'me'],
  hrm_employee: ['me'],
};
const LEAVE = [
  { id: 'annual', label: 'Annual' },
  { id: 'sick', label: 'Sick' },
  { id: 'maternity', label: 'Maternity' },
  { id: 'paternity', label: 'Paternity' },
  { id: 'compassionate', label: 'Compassionate' },
  { id: 'unpaid', label: 'Unpaid' },
];
const PAY_METHODS = [
  { id: 'bank_transfer', label: 'Bank transfer' },
  { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'cheque', label: 'Cheque' },
  { id: 'cash', label: 'Cash' },
];
const MARKS = [
  { id: 'present', label: 'Present' },
  { id: 'late', label: 'Late' },
  { id: 'absent', label: 'Absent' },
  { id: 'leave', label: 'On leave' },
];
const RUN_WORDS: Record<string, string> = { draft: 'Draft', approved: 'Approved', paid: 'All paid' };

const money = (value: unknown) => formatMoney(Number(value || 0));
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const leaveWord = (id: string) => LEAVE.find((x) => x.id === id)?.label || id;
const safe = (value: unknown) =>
  String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string);
const iso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
const thisMonth = () => iso().slice(0, 7);

function printSlip(slip: Row, period: string) {
  const page = window.open('', '_blank', 'width=480,height=700');
  if (!page) return;
  const line = (label: string, value: unknown) => `<tr><td>${label}</td><td style="text-align:right">${money(value)}</td></tr>`;
  page.document.write(
    `<html><body style="font-family:sans-serif"><h3>Payslip ${safe(period)}</h3><p>${safe(slip.employee_name)} · ${safe(slip.employee_number)}<br/>${safe(slip.job_title)}</p><table style="width:100%">${line('Basic', slip.basic)}${line('Allowances', slip.allowances)}${line('Bonus', slip.bonus)}${line('Unpaid days', -Number(slip.unpaid_deduction))}${line('Gross', slip.gross)}${line('SSNIT', -Number(slip.ssnit_employee))}${Number(slip.tier3) > 0 ? line('Tier 3 pension', -Number(slip.tier3)) : ''}${line('PAYE', -Number(slip.paye))}${line('Other deductions', -Number(slip.other_deductions))}</table><h3>Net pay ${money(slip.net)}</h3></body></html>`,
  );
  page.document.close();
  page.print();
}

const BLANK = { full_name: '', phone: '', email: '', job_title: '', department: '', hired_on: '', basic_salary: '', allowances: '0', ssnit_number: '', tin: '', bank_name: '', bank_account: '', ghana_card: '', mobile_money: '', tier3_percent: '0' };

const GHANA_CARD = /^GHA-\d{9}-\d$/;

function firstOfNextMonth(): string {
  const d = new Date();
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1)).toISOString().slice(0, 10);
}

const RATE_BLANK = {
  effective_from: '',
  employee_percent: '5.5',
  employer_percent: '13',
  tier2_percent: '0',
  insurable_cap: '',
  tier3_relief_percent: '16.5',
  rounding: 'half_up',
  source_note: '',
};

function HrmDesk() {
  const params = useSearchParams();
  const [role, setRole] = useState('');
  const allowed = useMemo(() => TABS.filter((t) => !ROLE_TABS[role] || ROLE_TABS[role].includes(t.id)), [role]);
  const wanted = params.get('tab') || (role === 'hrm_employee' ? 'me' : 'today');
  const tab = allowed.some((t) => t.id === wanted) ? wanted : allowed[0]?.id || 'today';
  const seesPay = role !== 'hrm_officer' && role !== 'hrm_employee';

  const [summary, setSummary] = useState<Row | null>(null);
  const [people, setPeople] = useState<Row[]>([]);
  const [leave, setLeave] = useState<Row[]>([]);
  const [day, setDay] = useState(iso());
  const [marks, setMarks] = useState<Row[]>([]);
  const [runs, setRuns] = useState<Row[]>([]);
  const [period, setPeriod] = useState(thisMonth());
  const [openRun, setOpenRun] = useState('');
  const [report, setReport] = useState<Row | null>(null);
  const [settings, setSettings] = useState<Row | null>(null);
  const [rates, setRates] = useState<Row[]>([]);
  const [rateForm, setRateForm] = useState<Row>(RATE_BLANK);
  const [rateBands, setRateBands] = useState<Row[]>([]);
  const [me, setMe] = useState<Row | null>(null);
  const [form, setForm] = useState(BLANK);
  const [leaveForm, setLeaveForm] = useState({ employee_id: '', leave_type: 'annual', starts_on: '', ends_on: '', reason: '' });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState<Row | null>(null);

  useEffect(() => {
    getMe().then((u: Row | null) => setRole(String(u?.data?.role || 'unknown'))).catch(() => setRole('unknown'));
  }, []);

  const load = useCallback(async () => {
    const get = async (path: string) => (await api(path))?.data;
    setError('');
    try {
      if (tab === 'today') setSummary(await get('/hrm/summary'));
      if (tab === 'people') setPeople((await get('/hrm/employees')) || []);
      if (tab === 'leave') {
        const [l, p] = await Promise.all([get('/hrm/leave'), get('/hrm/employees')]);
        setLeave(l || []);
        setPeople(p || []);
      }
      if (tab === 'attendance') setMarks((await get(`/hrm/attendance?day=${day}`)) || []);
      if (tab === 'payroll') setRuns((await get('/hrm/payroll')) || []);
      if (tab === 'reports') setReport(await get('/hrm/reports'));
      if (tab === 'settings') {
        const [st, rt] = await Promise.all([get('/hrm/settings'), get('/hrm/statutory-rates')]);
        setSettings(st);
        setRates(rt || []);
        // A new dated row starts from the newest rules on record.
        const base = (rt && rt[0]) || st;
        setRateBands((base?.paye_bands || []).map((b: Row) => ({ width: b.width == null ? null : String(b.width), rate: String(b.rate) })));
        setRateForm({
          ...RATE_BLANK,
          effective_from: firstOfNextMonth(),
          employee_percent: String(rt?.[0]?.employee_percent ?? st?.ssnit_employee_percent ?? '5.5'),
          employer_percent: String(rt?.[0]?.employer_percent ?? st?.ssnit_employer_percent ?? '13'),
          tier2_percent: String(rt?.[0]?.tier2_percent ?? '0'),
          insurable_cap: rt?.[0]?.insurable_cap == null ? '' : String(rt[0].insurable_cap),
          tier3_relief_percent: String(rt?.[0]?.tier3_relief_percent ?? '16.5'),
          rounding: rt?.[0]?.rounding || 'half_up',
        });
      }
      if (tab === 'me') setMe(await get('/hrm/me'));
    } catch (err) {
      setError(problem(err));
    }
  }, [tab, day]);

  useEffect(() => {
    if (role) void load();
  }, [load, role]);

  async function run(path: string, body: object | null, done: string, method = 'POST') {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await api(path, { method, body: body ? JSON.stringify(body) : undefined });
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

  async function addPerson() {
    const blank = (value: string) => value.trim() || null;
    const ok = await run(
      '/hrm/employees',
      {
        full_name: form.full_name.trim(),
        phone: form.phone.replace(/[\s-]/g, '') || null,
        email: blank(form.email),
        job_title: blank(form.job_title),
        department: blank(form.department),
        hired_on: form.hired_on,
        basic_salary: Number(form.basic_salary || 0),
        allowances: Number(form.allowances || 0),
        ssnit_number: blank(form.ssnit_number),
        tin: blank(form.tin),
        bank_name: blank(form.bank_name),
        bank_account: blank(form.bank_account),
        ghana_card: blank(form.ghana_card.toUpperCase()),
        mobile_money: form.mobile_money.replace(/[\s-]/g, '') || null,
        tier3_percent: Number(form.tier3_percent || 0),
      },
      'Employee added',
    );
    if (ok) setForm(BLANK);
  }

  async function askLeave(mine: boolean) {
    const ok = await run(
      '/hrm/leave',
      {
        employee_id: mine ? null : leaveForm.employee_id,
        leave_type: leaveForm.leave_type,
        starts_on: leaveForm.starts_on,
        ends_on: leaveForm.ends_on,
        reason: leaveForm.reason.trim() || null,
      },
      'Leave requested',
    );
    if (ok) setLeaveForm({ employee_id: '', leave_type: 'annual', starts_on: '', ends_on: '', reason: '' });
  }

  async function confirmDialog() {
    if (!dialog) return;
    let ok: unknown = null;
    if (dialog.kind === 'left') ok = await run(`/hrm/employees/${dialog.row.id}/left`, { left_on: dialog.left_on, reason: dialog.reason.trim() }, 'Marked as left');
    if (dialog.kind === 'reject') ok = await run(`/hrm/leave/${dialog.row.id}/decide`, { approve: false, note: dialog.note.trim() }, 'Leave turned down');
    if (dialog.kind === 'pay') ok = await run(`/hrm/payroll/${dialog.row.id}/pay`, { what: dialog.what, method: dialog.method }, 'Recorded as paid');
    if (dialog.kind === 'slip') {
      ok = await run(`/hrm/payslips/${dialog.row.id}`, { bonus: Number(dialog.bonus || 0), other_deductions: Number(dialog.other || 0) }, 'Payslip saved', 'PATCH');
    }
    if (ok) setDialog(null);
  }

  const dialogReady = dialog
    ? dialog.kind === 'left'
      ? Boolean(dialog.left_on) && dialog.reason.trim().length >= 3
      : dialog.kind === 'reject'
        ? dialog.note.trim().length > 0
        : true
    : false;
  const leaveReady = leaveForm.starts_on && leaveForm.ends_on;
  const payWords: Record<string, string> = {
    staff: 'salaries',
    paye: 'PAYE to GRA',
    ssnit: 'SSNIT (Tier 1)',
    tier2: 'Tier 2 pension to the trustee',
    tier3: 'Tier 3 pension',
  };

  async function addRates() {
    const num = (v: unknown) => Number(String(v ?? '').trim());
    const ok = await run(
      '/hrm/statutory-rates',
      {
        effective_from: rateForm.effective_from,
        employee_percent: num(rateForm.employee_percent),
        employer_percent: num(rateForm.employer_percent),
        tier2_percent: num(rateForm.tier2_percent || 0),
        insurable_cap: String(rateForm.insurable_cap || '').trim() ? num(rateForm.insurable_cap) : null,
        tier3_relief_percent: num(rateForm.tier3_relief_percent || 0),
        rounding: rateForm.rounding,
        source_note: String(rateForm.source_note || '').trim() || null,
        paye_bands: rateBands.map((b) => ({ width: b.width == null ? null : num(b.width), rate: num(b.rate) })),
      },
      'Rates saved',
    );
    if (ok) setRateForm({ ...RATE_BLANK, effective_from: firstOfNextMonth() });
  }

  const leaveFields = (
    <>
      <label><span>Type</span>
        <select value={leaveForm.leave_type} onChange={(e) => setLeaveForm({ ...leaveForm, leave_type: e.target.value })} aria-label="Leave type">
          {LEAVE.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
        </select>
      </label>
      <label><span>From</span><input type="date" value={leaveForm.starts_on} onChange={(e) => setLeaveForm({ ...leaveForm, starts_on: e.target.value })} aria-label="Leave from" /></label>
      <label><span>To</span><input type="date" value={leaveForm.ends_on} onChange={(e) => setLeaveForm({ ...leaveForm, ends_on: e.target.value })} aria-label="Leave to" /></label>
      <label><span>Reason</span><input value={leaveForm.reason} onChange={(e) => setLeaveForm({ ...leaveForm, reason: e.target.value })} aria-label="Leave reason" /></label>
    </>
  );

  return (
    <div className="hrm">
      {dialog ? (
        <div className="hr-veil">
          <div className="hr-dialog" role="dialog" aria-modal="true" aria-label="HR action">
            {dialog.kind === 'left' ? (
              <>
                <h2>{dialog.row.full_name} is leaving</h2>
                <label><span>Last day</span><input type="date" value={dialog.left_on} onChange={(e) => setDialog({ ...dialog, left_on: e.target.value })} aria-label="Last day" /></label>
                <label><span>Reason</span><input value={dialog.reason} onChange={(e) => setDialog({ ...dialog, reason: e.target.value })} aria-label="Reason" /></label>
              </>
            ) : null}
            {dialog.kind === 'reject' ? (
              <>
                <h2>Turn down {dialog.row.employee_name}&apos;s leave</h2>
                <label><span>Why</span><input autoFocus value={dialog.note} onChange={(e) => setDialog({ ...dialog, note: e.target.value })} aria-label="Why" /></label>
              </>
            ) : null}
            {dialog.kind === 'pay' ? (
              <>
                <h2>Pay {payWords[dialog.what]} for {dialog.row.period}</h2>
                <p><b>{money(dialog.amount)}</b></p>
                <label><span>Paid by</span>
                  <select value={dialog.method} onChange={(e) => setDialog({ ...dialog, method: e.target.value })} aria-label="Paid by">
                    {PAY_METHODS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                  </select>
                </label>
              </>
            ) : null}
            {dialog.kind === 'slip' ? (
              <>
                <h2>{dialog.row.employee_name}</h2>
                <label><span>Bonus</span><input type="number" min="0" value={dialog.bonus} onChange={(e) => setDialog({ ...dialog, bonus: e.target.value })} aria-label="Bonus" /></label>
                <label><span>Other deductions</span><input type="number" min="0" value={dialog.other} onChange={(e) => setDialog({ ...dialog, other: e.target.value })} aria-label="Other deductions" /></label>
              </>
            ) : null}
            {error ? <div className="hr-banner bad">{error}</div> : null}
            <div className="hr-row">
              <button type="button" className="hr-primary" disabled={busy || !dialogReady} onClick={() => void confirmDialog()}>Confirm</button>
              <button type="button" onClick={() => setDialog(null)}>Go back</button>
            </div>
          </div>
        </div>
      ) : null}

      {tab !== 'today' ? (
        <header className="hr-head">
          <span className="hr-head-ico" aria-hidden="true"><DeskIcon name={SCREENS[tab].icon} size={26} /></span>
          <div className="hr-head-text">
            <h1>{SCREENS[tab].title}</h1>
            <p>{SCREENS[tab].sub}</p>
          </div>
        </header>
      ) : null}
      {notice ? <div className="hr-banner" role="status">{notice}</div> : null}
      {error && !dialog ? <div className="hr-banner bad" role="alert">{error}</div> : null}

      {tab === 'today' && summary ? (
        <DeskDashboard
          desk="HR dashboard"
          actions={[
            { label: 'Mark attendance', href: '/hrm?tab=attendance', primary: true, icon: 'check', hint: 'Who came in today' },
            { label: 'Record leave', href: '/hrm?tab=leave', icon: 'calendar', hint: 'Time off' },
            { label: 'Add an employee', href: '/hrm?tab=people', icon: 'users', hint: 'New starter' },
            ...(seesPay ? [{ label: 'Payroll', href: '/hrm?tab=payroll', icon: 'wallet', hint: 'Pay the month' }] : []),
          ]}
          tiles={[
            { label: 'Staff', icon: 'users', value: summary.headcount, href: '/hrm?tab=people' },
            {
              label: 'In today',
              icon: 'check',
              value: summary.attendance_today.present + summary.attendance_today.late,
              sub: summary.attendance_today.not_marked
                ? `${summary.attendance_today.not_marked} not marked yet`
                : `${summary.attendance_today.late} late · ${summary.attendance_today.absent} absent`,
              href: '/hrm?tab=attendance',
            },
            { label: 'Leave to decide', icon: 'calendar', value: summary.leave_pending, warn: summary.leave_pending > 0, href: '/hrm?tab=leave' },
            { label: 'Away on leave', icon: 'leaf', value: summary.on_leave_today.length, sub: summary.on_leave_today.slice(0, 2).join(', ') || 'Nobody' },
            ...('monthly_basic' in summary ? [{ label: 'Monthly pay bill', icon: 'wallet', value: money(summary.monthly_basic), sub: 'basic and allowances' }] : []),
            ...(summary.last_run ? [{ label: 'Last payroll', icon: 'receipt', value: summary.last_run.period, sub: RUN_WORDS[summary.last_run.status], href: '/hrm?tab=payroll' }] : []),
          ]}
          trend={summary.trend}
          attention={summary.attention}
        />
      ) : null}

      {tab === 'people' ? (
        <>
          <section className="hr-box" aria-label="Add employee">
            <Head title="Add an employee" />
            <div className="hr-form">
              <label><span>Full name</span><input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} aria-label="Employee name" /></label>
              <label><span>Job title</span><input value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} aria-label="Job title" /></label>
              <label><span>Department</span><input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} aria-label="Department" /></label>
              <label><span>Started on</span><input type="date" value={form.hired_on} onChange={(e) => setForm({ ...form, hired_on: e.target.value })} aria-label="Started on" /></label>
              <label><span>Phone</span><input value={form.phone} placeholder="+233…" onChange={(e) => setForm({ ...form, phone: e.target.value })} aria-label="Employee phone" /></label>
              <label><span>Email (their login)</span><input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} aria-label="Employee email" /></label>
              {seesPay ? (
                <>
                  <label><span>Basic salary a month</span><input type="number" min="0" value={form.basic_salary} onChange={(e) => setForm({ ...form, basic_salary: e.target.value })} aria-label="Basic salary" /></label>
                  <label><span>Allowances a month</span><input type="number" min="0" value={form.allowances} onChange={(e) => setForm({ ...form, allowances: e.target.value })} aria-label="Allowances" /></label>
                </>
              ) : null}
              <label><span>SSNIT number</span><input value={form.ssnit_number} onChange={(e) => setForm({ ...form, ssnit_number: e.target.value })} aria-label="SSNIT number" /></label>
              <label><span>TIN</span><input value={form.tin} onChange={(e) => setForm({ ...form, tin: e.target.value })} aria-label="TIN" /></label>
              <label><span>Bank</span><input value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} aria-label="Bank" /></label>
              <label><span>Account number</span><input value={form.bank_account} onChange={(e) => setForm({ ...form, bank_account: e.target.value })} aria-label="Account number" /></label>
              <label>
                <span>Ghana Card</span>
                <input value={form.ghana_card} placeholder="GHA-000000000-0" onChange={(e) => setForm({ ...form, ghana_card: e.target.value })} aria-label="Ghana Card number" />
              </label>
              <label><span>Mobile Money</span><input value={form.mobile_money} placeholder="+233…" onChange={(e) => setForm({ ...form, mobile_money: e.target.value })} aria-label="Mobile Money number" /></label>
              {seesPay ? (
                <label><span>Tier 3 voluntary %</span><input type="number" min="0" max="100" step="0.5" value={form.tier3_percent} onChange={(e) => setForm({ ...form, tier3_percent: e.target.value })} aria-label="Tier 3 voluntary percent" /></label>
              ) : null}
              {form.ghana_card.trim() && !GHANA_CARD.test(form.ghana_card.trim().toUpperCase()) ? (
                <p className="hr-muted" role="alert">A Ghana Card number looks like GHA-123456789-0.</p>
              ) : null}
              <button
                type="button" className="hr-primary"
                disabled={busy || !form.full_name.trim() || !form.hired_on || Boolean(form.ghana_card.trim() && !GHANA_CARD.test(form.ghana_card.trim().toUpperCase()))}
                onClick={() => void addPerson()}
              >Add employee</button>
            </div>
          </section>
          <section className="hr-box hr-scroll" aria-label="Staff">
            <Head title="Staff" />
            <table>
              <thead><tr><th>Name</th><th>Job</th><th>Department</th><th>Started</th>{seesPay ? <th>Basic</th> : null}<th /></tr></thead>
              <tbody>
                {people.map((p) => (
                  <tr key={p.id}>
                    <td>{p.full_name}<br /><small className="hr-muted">{p.employee_number}</small></td>
                    <td>{p.job_title || '—'}</td><td>{p.department || '—'}</td><td>{p.hired_on}</td>
                    {seesPay ? <td className="hr-num">{money(p.basic_salary)}</td> : null}
                    <td><button type="button" className="hr-danger" onClick={() => setDialog({ kind: 'left', row: p, left_on: iso(), reason: '' })}>Leaving</button></td>
                  </tr>
                ))}
                {people.length === 0 ? <tr><td colSpan={6} className="hr-muted">No staff yet. Add the first person above.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'leave' ? (
        <>
          <section className="hr-box" aria-label="Record leave">
            <Head title="Record leave" />
            <div className="hr-form">
              <label><span>Employee</span>
                <select value={leaveForm.employee_id} onChange={(e) => setLeaveForm({ ...leaveForm, employee_id: e.target.value })} aria-label="Leave employee">
                  <option value="">Choose</option>
                  {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
              </label>
              {leaveFields}
              <button type="button" className="hr-primary" disabled={busy || !leaveForm.employee_id || !leaveReady} onClick={() => void askLeave(false)}>Add request</button>
            </div>
          </section>
          <section className="hr-box hr-scroll" aria-label="Leave requests">
            <Head title="Leave" />
            <table>
              <thead><tr><th>Who</th><th>Type</th><th>From</th><th>To</th><th>Days</th><th>Status</th><th /></tr></thead>
              <tbody>
                {leave.map((l) => (
                  <tr key={l.id}>
                    <td>{l.employee_name}{l.reason ? <><br /><small className="hr-muted">{l.reason}</small></> : null}</td>
                    <td>{leaveWord(l.leave_type)}</td><td>{l.starts_on}</td><td>{l.ends_on}</td><td>{l.days}</td>
                    <td>{l.status}{l.decision_note ? <><br /><small className="hr-muted">{l.decision_note}</small></> : null}</td>
                    <td>
                      {l.status === 'pending' ? (
                        <div className="hr-row">
                          <button type="button" className="hr-primary" onClick={() => void run(`/hrm/leave/${l.id}/decide`, { approve: true }, 'Leave approved')}>Approve</button>
                          <button type="button" className="hr-danger" onClick={() => setDialog({ kind: 'reject', row: l, note: '' })}>Turn down</button>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
                {leave.length === 0 ? <tr><td colSpan={7} className="hr-muted">No leave yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'attendance' ? (
        <section className="hr-box hr-scroll" aria-label="Attendance">
          <div className="hr-row" style={{ justifyContent: 'space-between' }}>
            <label style={{ maxWidth: 200 }}><span>Day</span><input type="date" value={day} max={iso()} onChange={(e) => setDay(e.target.value)} aria-label="Attendance day" /></label>
            <button
              type="button" className="hr-primary" disabled={busy || !marks.some((x) => x.status)}
              onClick={() => void run('/hrm/attendance', { day, marks: marks.filter((x) => x.status).map((x) => ({ employee_id: x.employee_id, status: x.status })) }, 'Attendance saved')}
            >Save attendance</button>
          </div>
          <table>
            <thead><tr><th>Name</th><th>Department</th><th>Today</th></tr></thead>
            <tbody>
              {marks.map((x, i) => (
                <tr key={x.employee_id}>
                  <td>{x.full_name}</td><td>{x.department || '—'}</td>
                  <td>
                    <select
                      value={x.status || ''} aria-label={`Attendance ${x.full_name}`}
                      onChange={(e) => setMarks(marks.map((r, n) => (n === i ? { ...r, status: e.target.value || null } : r)))}
                    >
                      <option value="">Not marked</option>
                      {MARKS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
              {marks.length === 0 ? <tr><td colSpan={3} className="hr-muted">No staff yet.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}

      {tab === 'payroll' ? (
        <>
          <section className="hr-box" aria-label="New payroll">
            <Head title="Draw up a month" />
            <div className="hr-row">
              <input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} aria-label="Payroll month" style={{ maxWidth: 200 }} />
              <button type="button" className="hr-primary" disabled={busy || !period} onClick={() => void run('/hrm/payroll', { period }, 'Payroll drawn up')}>Draw up payroll</button>
            </div>
            <p className="hr-muted">Check the SSNIT and PAYE rates under Settings against the current official tables before you approve.</p>
          </section>
          {runs.map((r) => (
            <section className="hr-box hr-scroll" key={r.id} aria-label={`Payroll ${r.period}`}>
              <div className="hr-row" style={{ justifyContent: 'space-between' }}>
                <div><h2>{r.period} · {RUN_WORDS[r.status]}</h2><p className="hr-muted">Net {money(r.net)} · PAYE {money(r.paye)} · SSNIT {money(Number(r.ssnit_employee) + Number(r.ssnit_employer))}</p></div>
                <div className="hr-row">
                  <button type="button" onClick={() => setOpenRun(openRun === r.id ? '' : r.id)}>{openRun === r.id ? 'Hide payslips' : 'Payslips'}</button>
                  {r.status === 'draft' ? (
                    <>
                      <button type="button" className="hr-primary" disabled={busy} onClick={() => void run(`/hrm/payroll/${r.id}/approve`, null, 'Payroll approved')}>Approve</button>
                      <button type="button" className="hr-danger" disabled={busy} onClick={() => void run(`/hrm/payroll/${r.id}`, null, 'Draft thrown away', 'DELETE')}>Throw away</button>
                    </>
                  ) : null}
                  {r.status === 'approved' && !r.staff_paid ? <button type="button" className="hr-primary" onClick={() => setDialog({ kind: 'pay', row: r, what: 'staff', method: 'bank_transfer', amount: r.net })}>Pay salaries</button> : null}
                  {r.status === 'approved' && !r.paye_paid ? <button type="button" onClick={() => setDialog({ kind: 'pay', row: r, what: 'paye', method: 'bank_transfer', amount: r.paye })}>Pay PAYE</button> : null}
                  {r.status === 'approved' && !r.ssnit_paid ? <button type="button" onClick={() => setDialog({ kind: 'pay', row: r, what: 'ssnit', method: 'bank_transfer', amount: r.ssnit_due ?? Number(r.ssnit_employee) + Number(r.ssnit_employer) })}>Pay SSNIT</button> : null}
                  {r.status === 'approved' && Number(r.tier2) > 0 && !r.tier2_paid ? <button type="button" onClick={() => setDialog({ kind: 'pay', row: r, what: 'tier2', method: 'bank_transfer', amount: r.tier2 })}>Pay Tier 2</button> : null}
                  {r.status === 'approved' && Number(r.tier3) > 0 && !r.tier3_paid ? <button type="button" onClick={() => setDialog({ kind: 'pay', row: r, what: 'tier3', method: 'bank_transfer', amount: r.tier3 })}>Pay Tier 3</button> : null}
                </div>
              </div>
              {openRun === r.id ? (
                <table>
                  <thead><tr><th>Name</th><th>Gross</th><th>SSNIT</th><th>PAYE</th><th>Other</th><th>Net</th><th /></tr></thead>
                  <tbody>
                    {r.slips.map((s: Row) => (
                      <tr key={s.id}>
                        <td>{s.employee_name}{s.unpaid_days ? <><br /><small className="hr-muted">{s.unpaid_days} unpaid days</small></> : null}</td>
                        <td className="hr-num">{money(s.gross)}</td><td className="hr-num">{money(s.ssnit_employee)}</td><td className="hr-num">{money(s.paye)}</td><td className="hr-num">{money(s.other_deductions)}</td><td className="hr-num">{money(s.net)}</td>
                        <td>
                          <div className="hr-row">
                            {r.status === 'draft' ? <button type="button" onClick={() => setDialog({ kind: 'slip', row: s, bonus: String(s.bonus), other: String(s.other_deductions) })}>Change</button> : null}
                            <button type="button" onClick={() => printSlip(s, r.period)}>Print</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
            </section>
          ))}
          {runs.length === 0 ? <section className="hr-box hr-muted">No payroll yet.</section> : null}
        </>
      ) : null}

      {tab === 'reports' && report ? (
        <>
          <div className="hr-tiles">
            <div className="hr-tile"><span>Staff now</span><b>{report.headcount}</b></div>
            <div className="hr-tile"><span>Payroll cost {report.year}</span><b>{money(report.payroll_cost)}</b><small>with employer SSNIT</small></div>
          </div>
          <section className="hr-box hr-scroll" aria-label="Payroll by month">
            <Head title="Payroll by month" />
            <table>
              <thead><tr><th>Month</th><th>Gross</th><th>PAYE</th><th>SSNIT</th><th>Net</th></tr></thead>
              <tbody>
                {report.payroll.map((r: Row) => <tr key={r.id}><td>{r.period}</td><td className="hr-num">{money(r.gross)}</td><td className="hr-num">{money(r.paye)}</td><td className="hr-num">{money(Number(r.ssnit_employee) + Number(r.ssnit_employer))}</td><td className="hr-num">{money(r.net)}</td></tr>)}
                {report.payroll.length === 0 ? <tr><td colSpan={5} className="hr-muted">No approved payroll this year.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <section className="hr-box" aria-label="By department">
            <Head title="By department" />
            {report.by_department.map((d: Row) => <div className="hr-line" key={d.name}><span>{d.name}</span><span>{d.count}</span></div>)}
          </section>
          <section className="hr-box" aria-label="Leave taken">
            <Head title="Leave days taken" />
            {Object.entries(report.leave_days_by_type as Record<string, number>).map(([k, v]) => <div className="hr-line" key={k}><span>{leaveWord(k)}</span><span>{v}</span></div>)}
            {Object.keys(report.leave_days_by_type).length === 0 ? <p className="hr-muted">None this year.</p> : null}
          </section>
        </>
      ) : null}

      {tab === 'settings' && settings ? (
        <section className="hr-box" aria-label="HR settings">
          <Head title="Rates" />
          <p className="hr-muted">These start at Ghana&apos;s SSNIT rates and monthly PAYE bands. Check them with your accountant against the current GRA and SSNIT tables.</p>
          <div className="hr-form">
            <label><span>Annual leave days</span><input type="number" min="0" value={settings.annual_leave_days} onChange={(e) => setSettings({ ...settings, annual_leave_days: e.target.value })} aria-label="Annual leave days" /></label>
            <label><span>Working days a month</span><input type="number" min="1" value={settings.working_days_per_month} onChange={(e) => setSettings({ ...settings, working_days_per_month: e.target.value })} aria-label="Working days a month" /></label>
            <label><span>Staff SSNIT %</span><input type="number" min="0" value={settings.ssnit_employee_percent} onChange={(e) => setSettings({ ...settings, ssnit_employee_percent: e.target.value })} aria-label="Staff SSNIT percent" /></label>
            <label><span>Employer SSNIT %</span><input type="number" min="0" value={settings.ssnit_employer_percent} onChange={(e) => setSettings({ ...settings, ssnit_employer_percent: e.target.value })} aria-label="Employer SSNIT percent" /></label>
          </div>
          <h2 style={{ marginTop: 14 }}>PAYE bands a month</h2>
          <table>
            <thead><tr><th>Band size</th><th>Rate %</th></tr></thead>
            <tbody>
              {settings.paye_bands.map((b: Row, i: number) => (
                <tr key={i}>
                  <td>
                    {b.width == null ? 'Everything above' : (
                      <input
                        type="number" min="0" value={b.width} aria-label={`PAYE band ${i + 1} size`}
                        onChange={(e) => setSettings({ ...settings, paye_bands: settings.paye_bands.map((x: Row, n: number) => (n === i ? { ...x, width: e.target.value } : x)) })}
                      />
                    )}
                  </td>
                  <td>
                    <input
                      type="number" min="0" value={b.rate} aria-label={`PAYE band ${i + 1} rate`}
                      onChange={(e) => setSettings({ ...settings, paye_bands: settings.paye_bands.map((x: Row, n: number) => (n === i ? { ...x, rate: e.target.value } : x)) })}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="hr-row" style={{ marginTop: 10 }}>
            <button
              type="button" className="hr-primary" disabled={busy}
              onClick={() => void run('/hrm/settings', {
                annual_leave_days: Number(settings.annual_leave_days),
                working_days_per_month: Number(settings.working_days_per_month),
                ssnit_employee_percent: Number(settings.ssnit_employee_percent),
                ssnit_employer_percent: Number(settings.ssnit_employer_percent),
                paye_bands: settings.paye_bands.map((b: Row) => ({ width: b.width == null ? null : Number(b.width), rate: Number(b.rate) })),
              }, 'Settings saved', 'PATCH')}
            >Save rates</button>
          </div>
        </section>
      ) : null}

      {tab === 'settings' && settings ? (
        <section className="hr-box" aria-label="Dated payroll rates">
          <Head title="Dated rates" />
          <p className="hr-muted">
            When the GRA bands or SSNIT rules change, add the new rules with the date they start. Each payroll month uses
            the newest rules that start on or before its first day; the rates above are used only while no dated rules
            exist. Rules an approved payroll used are locked. Check every figure with your accountant against the current
            GRA and SSNIT tables: the system does not check them for you.
          </p>
          {rates.length ? (
            <table aria-label="Dated rates on record">
              <thead><tr><th>From</th><th>Staff %</th><th>Company %</th><th>Tier 2 %</th><th>SSNIT cap</th><th>Tier 3 relief %</th><th>Source</th><th /></tr></thead>
              <tbody>
                {rates.map((r) => (
                  <tr key={r.id}>
                    <td>{r.effective_from}</td>
                    <td>{r.employee_percent}</td>
                    <td>{r.employer_percent}</td>
                    <td>{r.tier2_percent}</td>
                    <td>{r.insurable_cap == null ? 'None' : money(r.insurable_cap)}</td>
                    <td>{r.tier3_relief_percent}</td>
                    <td>{r.source_note || '—'}</td>
                    <td>
                      {r.locked ? (
                        <span className="hr-muted">Used by payroll</span>
                      ) : (
                        <button type="button" aria-label={`Remove rates from ${r.effective_from}`} disabled={busy} onClick={() => void run(`/hrm/statutory-rates/${r.id}`, null, 'Rates removed', 'DELETE')}>Remove</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="hr-muted">No dated rules yet.</p>
          )}
          <h2 style={{ marginTop: 14 }}>Add rules from a date</h2>
          <div className="hr-form">
            <label><span>Start on</span><input type="date" value={rateForm.effective_from} onChange={(e) => setRateForm({ ...rateForm, effective_from: e.target.value })} aria-label="Rates start on" /></label>
            <label><span>Staff SSNIT %</span><input type="number" min="0" step="0.1" value={rateForm.employee_percent} onChange={(e) => setRateForm({ ...rateForm, employee_percent: e.target.value })} aria-label="Dated staff SSNIT percent" /></label>
            <label><span>Company SSNIT %</span><input type="number" min="0" step="0.1" value={rateForm.employer_percent} onChange={(e) => setRateForm({ ...rateForm, employer_percent: e.target.value })} aria-label="Dated company SSNIT percent" /></label>
            <label><span>Tier 2 % of insurable pay</span><input type="number" min="0" step="0.1" value={rateForm.tier2_percent} onChange={(e) => setRateForm({ ...rateForm, tier2_percent: e.target.value })} aria-label="Tier 2 percent" /></label>
            <label><span>SSNIT cap a month (blank = none)</span><input type="number" min="0" value={rateForm.insurable_cap} onChange={(e) => setRateForm({ ...rateForm, insurable_cap: e.target.value })} aria-label="SSNIT maximum insurable earnings" /></label>
            <label><span>Tier 3 tax relief %</span><input type="number" min="0" step="0.5" value={rateForm.tier3_relief_percent} onChange={(e) => setRateForm({ ...rateForm, tier3_relief_percent: e.target.value })} aria-label="Tier 3 tax relief percent" /></label>
            <label>
              <span>Rounding</span>
              <select value={rateForm.rounding} onChange={(e) => setRateForm({ ...rateForm, rounding: e.target.value })} aria-label="Payroll rounding">
                <option value="half_up">To the nearest pesewa</option>
                <option value="down">Down to the pesewa</option>
              </select>
            </label>
            <label><span>Where these come from</span><input value={rateForm.source_note} placeholder="GRA PAYE table, January 2027" onChange={(e) => setRateForm({ ...rateForm, source_note: e.target.value })} aria-label="Source of these rates" /></label>
          </div>
          <table aria-label="Dated PAYE bands">
            <thead><tr><th>Band size</th><th>Rate %</th></tr></thead>
            <tbody>
              {rateBands.map((b, i) => (
                <tr key={i}>
                  <td>
                    {b.width == null ? 'Everything above' : (
                      <input type="number" min="0" value={b.width} aria-label={`Dated PAYE band ${i + 1} size`}
                        onChange={(e) => setRateBands(rateBands.map((x, n) => (n === i ? { ...x, width: e.target.value } : x)))} />
                    )}
                  </td>
                  <td>
                    <input type="number" min="0" value={b.rate} aria-label={`Dated PAYE band ${i + 1} rate`}
                      onChange={(e) => setRateBands(rateBands.map((x, n) => (n === i ? { ...x, rate: e.target.value } : x)))} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="hr-row" style={{ marginTop: 10 }}>
            <button type="button" className="hr-primary" disabled={busy || !rateForm.effective_from || !rateBands.length} onClick={() => void addRates()}>
              Save dated rates
            </button>
          </div>
        </section>
      ) : null}

      {tab === 'me' && me ? (
        <>
          <div className="hr-tiles">
            <div className="hr-tile"><span>{me.employee.full_name}</span><b>{me.employee.job_title || me.employee.employee_number}</b></div>
            <div className="hr-tile"><span>Annual leave left</span><b>{me.leave_balance.left}</b><small>of {me.leave_balance.entitled} in {me.leave_balance.year}</small></div>
          </div>
          <section className="hr-box" aria-label="Ask for leave">
            <Head title="Ask for leave" />
            <div className="hr-form">
              {leaveFields}
              <button type="button" className="hr-primary" disabled={busy || !leaveReady} onClick={() => void askLeave(true)}>Ask</button>
            </div>
          </section>
          <section className="hr-box hr-scroll" aria-label="My leave">
            <Head title="My leave" />
            <table>
              <tbody>
                {me.leave.map((l: Row) => <tr key={l.id}><td>{leaveWord(l.leave_type)}</td><td>{l.starts_on} to {l.ends_on}</td><td>{l.days} days</td><td>{l.status}</td></tr>)}
                {me.leave.length === 0 ? <tr><td className="hr-muted">None yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <section className="hr-box hr-scroll" aria-label="My payslips">
            <Head title="My payslips" />
            <table>
              <tbody>
                {me.payslips.map((s: Row) => <tr key={s.id}><td>{s.period}</td><td className="hr-num">{money(s.net)}</td><td><button type="button" onClick={() => printSlip(s, s.period)}>Print</button></td></tr>)}
                {me.payslips.length === 0 ? <tr><td className="hr-muted">No payslips yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </div>
  );
}

export default function HrmPage() {
  return (
    <Suspense fallback={<div className="hrm"><p>Loading…</p></div>}>
      <HrmDesk />
    </Suspense>
  );
}
