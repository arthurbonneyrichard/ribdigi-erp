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
import { hrTabAllowed } from '../../../lib/tenantNav';
import DeskDashboard from '../../../components/DeskDashboard';
import DeskIcon from '../../../components/DeskIcon';
import { MyMore, PEOPLE_WORK_SCREENS, PeopleWork } from './PeopleWork';
import { MyClock, TIME_SCREENS, TimeWork } from './TimeWork';
import LeavePay from './LeavePay';
import { MyDocuments, StaffFiles } from './Documents';
import Org from './Org';
import Cover from './Cover';
import PartPay from './PartPay';
import Signals from './Signals';
import AskHr from './AskHr';
import SuggestedRates from './SuggestedRates';
import './hrm.css';

type Row = Record<string, any>;

const SCREENS: Record<string, { title: string; sub: string; icon: string }> = {
  today: { title: 'Dashboard', sub: '', icon: 'home' },
  people: { title: 'Employees', sub: 'Everyone on the payroll, their pay and their department.', icon: 'users' },
  leave: { title: 'Leave', sub: 'Time off asked for, approved and taken.', icon: 'calendar' },
  attendance: { title: 'Attendance', sub: 'Who came in today, and when.', icon: 'clock' },
  payroll: { title: 'Payroll', sub: 'Draw up the month, check it, approve it and pay it.', icon: 'cash' },
  loans: { title: 'Loans and advances', sub: 'Lent to staff, paid back from payroll each month.', icon: 'wallet' },
  reports: { title: 'Reports', sub: 'Payroll by month and department, and leave taken.', icon: 'chart' },
  settings: { title: 'Pay rates', sub: 'PAYE bands, SSNIT and the other rates payroll uses.', icon: 'tag' },
  ...TIME_SCREENS,
  ...PEOPLE_WORK_SCREENS,
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
const OFFICER_TABS = ['today', 'people', 'leave', 'attendance', 'shifts', 'clock', 'devices', 'hiring', 'training', 'contracts', 'kit', 'notices', 'me'];
// Mirrors backend hrm.job: HR managers and company admins see everything; officers and each
// desk's manager run people admin without pay; everyone else sees only their own file.
const FULL_HR_ROLES = new Set(['company_admin', 'hrm_manager', 'super_admin']);
const ROLE_TABS: Record<string, string[]> = {
  hrm_officer: OFFICER_TABS,
  store_manager: OFFICER_TABS,
  restaurant_manager: OFFICER_TABS,
  hotel_manager: OFFICER_TABS,
  bakery_manager: OFFICER_TABS,
  fmcg_manager: OFFICER_TABS,
  gym_manager: OFFICER_TABS,
};
const roleTabs = (role: string) => (FULL_HR_ROLES.has(role) ? null : ROLE_TABS[role] || ['me']);
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

function downloadCsv(name: string, rows: (string | number | null | undefined)[][]) {
  const text = rows.map((r) => r.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}

function printStatement(st: Row) {
  const page = window.open('', '_blank', 'width=640,height=800');
  if (!page) return;
  const rows = (st.months || [])
    .map((r: Row) => `<tr><td>${safe(r.period)}</td><td style="text-align:right">${money(r.gross)}</td><td style="text-align:right">${money(r.ssnit_employee)}</td><td style="text-align:right">${money(r.taxable)}</td><td style="text-align:right">${money(r.paye)}</td><td style="text-align:right">${money(r.net)}</td></tr>`)
    .join('');
  const t = st.totals || {};
  page.document.write(
    `<html><body style="font-family:sans-serif"><h3>Tax statement ${safe(st.year)}</h3><p>${safe(st.employee?.full_name)} · ${safe(st.employee?.employee_number)}<br/>TIN ${safe(st.employee?.tin || '—')} · Ghana Card ${safe(st.employee?.ghana_card || '—')} · SSNIT ${safe(st.employee?.ssnit_number || '—')}</p><table style="width:100%;border-collapse:collapse"><tr><th align="left">Month</th><th>Gross</th><th>SSNIT</th><th>Taxable</th><th>PAYE</th><th>Net</th></tr>${rows}<tr><th align="left">Total</th><th>${money(t.gross)}</th><th>${money(t.ssnit_employee)}</th><th>${money(t.taxable)}</th><th>${money(t.paye)}</th><th>${money(t.net)}</th></tr></table><p style="font-size:12px">${safe(st.note)}</p></body></html>`,
  );
  page.document.close();
  page.print();
}

const METHOD_WORDS: Record<string, string> = { cash: 'Cash', mobile_money: 'Mobile Money', bank_transfer: 'Bank transfer', cheque: 'Cheque' };

/** A note for one weekly / fortnightly part-payment. The month's payslip is the tax record. */
const EDIT_FIELDS: { key: string; label: string; pay?: boolean; kind?: string }[] = [
  { key: 'full_name', label: 'Full name' },
  { key: 'phone', label: 'Phone', kind: 'phone' },
  { key: 'email', label: 'Email (their login)' },
  { key: 'job_title', label: 'Job title' },
  { key: 'department', label: 'Department' },
  { key: 'biometric_id', label: 'Terminal ID (fingerprint / face)' },
  { key: 'ghana_card', label: 'Ghana Card', pay: true },
  { key: 'ssnit_number', label: 'SSNIT number', pay: true },
  { key: 'tin', label: 'TIN', pay: true },
  { key: 'bank_name', label: 'Bank', pay: true },
  { key: 'bank_account', label: 'Bank account', pay: true },
  { key: 'mobile_money', label: 'Mobile Money', pay: true, kind: 'phone' },
  { key: 'commission_percent', label: 'Sales commission %', pay: true, kind: 'number' },
  { key: 'tier3_percent', label: 'Tier 3 voluntary %', pay: true, kind: 'number' },
];

function printPayNote(l: Row) {
  const page = window.open('', '_blank', 'width=480,height=600');
  if (!page) return;
  const period = String(l.first_period || '');
  page.document.write(
    `<html><body style="font-family:sans-serif"><h3>Pay note</h3><p>${safe(l.employee_name)}<br/>${safe(l.reason || 'Part-payment of wages')}</p>`
      + `<table style="width:100%"><tr><td>Paid on</td><td style="text-align:right">${safe(String(l.paid_out_at || '').slice(0, 10))}</td></tr>`
      + `<tr><td>Paid by</td><td style="text-align:right">${safe(METHOD_WORDS[l.paid_out_method] || l.paid_out_method || '')}</td></tr>`
      + `<tr><td><b>Amount</b></td><td style="text-align:right"><b>${money(l.principal)}</b></td></tr></table>`
      + `<p style="font-size:12px">This is part of your pay for ${safe(period)}. PAYE and SSNIT are worked out on the whole month and shown on the ${safe(period)} payslip, which takes this amount back as &quot;Paid during the month&quot;. Reference ${safe(l.loan_number)}.</p></body></html>`,
  );
  page.document.close();
  page.print();
}

function printSlip(slip: Row, period: string) {
  const page = window.open('', '_blank', 'width=480,height=700');
  if (!page) return;
  const line = (label: string, value: unknown) => `<tr><td>${label}</td><td style="text-align:right">${money(value)}</td></tr>`;
  page.document.write(
    `<html><body style="font-family:sans-serif"><h3>Payslip ${safe(period)}</h3><p>${safe(slip.employee_name)} · ${safe(slip.employee_number)}<br/>${safe(slip.job_title)}</p><table style="width:100%">${line('Basic', slip.basic)}${line('Allowances', slip.allowances)}${line('Bonus', slip.bonus)}${Number(slip.arrears_basic) ? line('Back pay of basic', slip.arrears_basic) : ''}${Number(slip.adjustment) ? line('Correction', slip.adjustment) : ''}${Number(slip.overtime) ? line('Overtime', slip.overtime) : ''}${Number(slip.commission) ? line('Commission', slip.commission) : ''}${Number(slip.tips) ? line('Tips', slip.tips) : ''}${Number(slip.leave_pay) ? line('Unused leave paid', slip.leave_pay) : ''}${line('Unpaid days', -Number(slip.unpaid_deduction))}${line('Gross', slip.gross)}${line('SSNIT', -Number(slip.ssnit_employee))}${Number(slip.tier3) > 0 ? line('Tier 3 pension', -Number(slip.tier3)) : ''}${Number(slip.part_paid) > 0 ? line('Paid during the month', -Number(slip.part_paid)) : ''}${Number(slip.loan_deduction) - Number(slip.part_paid || 0) > 0 ? line('Loan repayment', -(Number(slip.loan_deduction) - Number(slip.part_paid || 0))) : ''}${line('PAYE', -Number(slip.paye))}${Number(slip.overtime_tax) ? line('of which overtime tax', -Number(slip.overtime_tax)) : ''}${Number(slip.bonus_tax) ? line('of which bonus tax', -Number(slip.bonus_tax)) : ''}${slip.non_resident ? '<tr><td colspan="2"><small>Taxed as non-resident</small></td></tr>' : ''}${line('Other deductions', -Number(slip.other_deductions))}</table><h3>Net pay ${money(slip.net)}</h3></body></html>`,
  );
  page.document.close();
  page.print();
}

const BLANK = { full_name: '', phone: '', email: '', job_title: '', department: '', hired_on: '', basic_salary: '', allowances: '0', ssnit_number: '', tin: '', bank_name: '', bank_account: '', ghana_card: '', mobile_money: '', tier3_percent: '0', manager_id: '', biometric_id: '', commission_percent: '0', pay_frequency: 'monthly', non_resident: false };

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
  overtime_junior_cap: '',
  overtime_low_rate: '5',
  overtime_high_rate: '10',
  overtime_low_share_percent: '50',
  minimum_daily_wage: '',
  source_note: '',
};

function HrmDesk() {
  const params = useSearchParams();
  const [role, setRole] = useState('');
  const [industry, setIndustry] = useState('');
  const allowed = useMemo(() => {
    const mine = roleTabs(role);
    return TABS.filter((t) => (!mine || mine.includes(t.id)) && (!industry || hrTabAllowed(t.id, industry)));
  }, [role, industry]);
  const wanted = params.get('tab') || (roleTabs(role)?.length === 1 ? 'me' : 'today');
  const tab = allowed.some((t) => t.id === wanted) ? wanted : allowed[0]?.id || 'today';
  const seesPay = FULL_HR_ROLES.has(role);

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
  const [loans, setLoans] = useState<Row[]>([]);
  const [teamLeave, setTeamLeave] = useState<Row[]>([]);
  const [adjustments, setAdjustments] = useState<Row[]>([]);
  const [commPeriod, setCommPeriod] = useState(thisMonth());
  const [commissions, setCommissions] = useState<Row[] | null>(null);
  const [adjForm, setAdjForm] = useState({ employee_id: '', kind: 'correction', amount: '', for_period: '', reason: '' });
  const [schedPeriod, setSchedPeriod] = useState(thisMonth());
  const [paye, setPaye] = useState<Row | null>(null);
  const [ssnit, setSsnit] = useState<Row | null>(null);
  const [stmtYear, setStmtYear] = useState(new Date().getFullYear());
  const [stmtPerson, setStmtPerson] = useState('');
  const [loanForm, setLoanForm] = useState({ employee_id: '', kind: 'loan', principal: '', monthly_deduction: '', first_period: '', reason: '' });
  const [myLoan, setMyLoan] = useState({ kind: 'advance', principal: '', monthly_deduction: '', reason: '' });
  const [holidays, setHolidays] = useState<Row[]>([]);
  const [suggested, setSuggested] = useState<Row[]>([]);
  const [holidayYear, setHolidayYear] = useState(new Date().getFullYear());
  const [holidayForm, setHolidayForm] = useState({ day: '', name: '' });
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
    getMe()
      .then((u: Row | null) => {
        setIndustry(String(u?.data?.industry || u?.data?.tenant?.industry || ''));
        setRole(String(u?.data?.role || 'unknown'));
      })
      .catch(() => setRole('unknown'));
  }, []);

  const load = useCallback(async () => {
    const get = async (path: string) => (await api(path))?.data;
    setError('');
    try {
      if (tab === 'today') setSummary(await get('/hrm/summary'));
      if (tab === 'people') setPeople((await get('/hrm/employees')) || []);
      if (tab === 'leave') {
        const [l, p, hol] = await Promise.all([get('/hrm/leave'), get('/hrm/employees'), get(`/hrm/holidays?year=${holidayYear}`)]);
        setLeave(l || []);
        setPeople(p || []);
        setHolidays(hol || []);
      }
      if (tab === 'loans') {
        const [ln, p] = await Promise.all([get('/hrm/loans'), get('/hrm/employees')]);
        setLoans(ln || []);
        setPeople(p || []);
      }
      if (tab === 'attendance') setMarks((await get(`/hrm/attendance?day=${day}`)) || []);
      if (tab === 'payroll') {
        const [r, adj, p] = await Promise.all([get('/hrm/payroll'), get('/hrm/adjustments'), get('/hrm/employees')]);
        setRuns(r || []);
        setAdjustments(adj || []);
        setPeople(p || []);
      }
      if (tab === 'reports') {
        const [rep, p] = await Promise.all([get('/hrm/reports'), get('/hrm/employees?show=all')]);
        setReport(rep);
        setPeople(p || []);
      }
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
          overtime_junior_cap: rt?.[0]?.overtime_junior_cap == null ? '' : String(rt[0].overtime_junior_cap),
          overtime_low_rate: String(rt?.[0]?.overtime_low_rate ?? '5'),
          overtime_high_rate: String(rt?.[0]?.overtime_high_rate ?? '10'),
          overtime_low_share_percent: String(rt?.[0]?.overtime_low_share_percent ?? '50'),
          minimum_daily_wage: rt?.[0]?.minimum_daily_wage == null ? '' : String(rt[0].minimum_daily_wage),
          rounding: rt?.[0]?.rounding || 'half_up',
        });
      }
      if (tab === 'me') {
        const [mine, team] = await Promise.all([get('/hrm/me'), get('/hrm/team/leave').catch(() => [])]);
        setMe(mine);
        setTeamLeave(team || []);
      }
    } catch (err) {
      setError(problem(err));
    }
  }, [tab, day, holidayYear]);

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
        manager_id: form.manager_id || null,
        biometric_id: form.biometric_id.trim() || null,
        commission_percent: Number(form.commission_percent || 0),
        pay_frequency: form.pay_frequency || 'monthly',
        non_resident: Boolean(form.non_resident),
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
    if (dialog.kind === 'edit') {
      // Send only what changed, so nobody trips a check on a field they did not touch.
      const body: Row = {};
      for (const f of EDIT_FIELDS) {
        if (f.pay && !seesPay) continue;
        const before = dialog.row[f.key] ?? '';
        let after: unknown = dialog.values[f.key] ?? '';
        if (String(after) === String(before)) continue;
        if (f.kind === 'number') after = Number(after || 0);
        else if (f.kind === 'phone') after = String(after).replace(/[\s-]/g, '') || null;
        else if (f.key === 'ghana_card') after = String(after).trim().toUpperCase() || null;
        else after = String(after).trim() || null;
        body[f.key] = after;
      }
      if (seesPay && dialog.values.pay_frequency !== (dialog.row.pay_frequency || 'monthly')) body.pay_frequency = dialog.values.pay_frequency;
      if (seesPay && Boolean(dialog.values.non_resident) !== Boolean(dialog.row.non_resident)) body.non_resident = Boolean(dialog.values.non_resident);
      if ((dialog.values.manager_id || '') !== (dialog.row.manager_id || '')) body.manager_id = dialog.values.manager_id || null;
      ok = Object.keys(body).length ? await run(`/hrm/employees/${dialog.row.id}`, body, 'Staff record saved', 'PATCH') : true;
    }
    if (dialog.kind === 'reject') ok = await run(`/hrm/leave/${dialog.row.id}/decide`, { approve: false, note: dialog.note.trim() }, 'Leave turned down');
    if (dialog.kind === 'pay') ok = await run(`/hrm/payroll/${dialog.row.id}/pay`, { what: dialog.what, method: dialog.method }, 'Recorded as paid');
    if (dialog.kind === 'loan') {
      ok = await run(
        `/hrm/loans/${dialog.row.id}/decide`,
        { approve: dialog.approve, method: dialog.approve ? dialog.method : null, note: dialog.note.trim() || null },
        dialog.approve ? 'Approved and paid out' : 'Turned down',
      );
    }
    if (dialog.kind === 'salary') {
      ok = await run(
        `/hrm/employees/${dialog.row.id}/salary`,
        { effective_from: dialog.effective_from, basic_salary: Number(dialog.basic), allowances: Number(dialog.allowances || 0), reason: dialog.reason.trim() },
        'Salary change saved',
      );
    }
    if (dialog.kind === 'repay') ok = await run(`/hrm/loans/${dialog.row.id}/repay`, { amount: Number(dialog.amount), method: dialog.method }, 'Repayment recorded');
    if (dialog.kind === 'slip') {
      ok = await run(`/hrm/payslips/${dialog.row.id}`, { bonus: Number(dialog.bonus || 0), other_deductions: Number(dialog.other || 0) }, 'Payslip saved', 'PATCH');
    }
    if (ok) setDialog(null);
  }

  const dialogReady = dialog
    ? dialog.kind === 'edit'
      ? String(dialog.values.full_name || '').trim().length > 1
      : dialog.kind === 'left'
      ? Boolean(dialog.left_on) && dialog.reason.trim().length >= 3
      : dialog.kind === 'reject' || (dialog.kind === 'loan' && !dialog.approve)
        ? dialog.note.trim().length > 0
        : dialog.kind === 'salary'
          ? Boolean(dialog.effective_from) && Number(dialog.basic) >= 0 && dialog.basic !== '' && dialog.reason.trim().length >= 3
          : dialog.kind === 'repay'
          ? Number(dialog.amount) > 0 && Number(dialog.amount) <= Number(dialog.row.balance)
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
        overtime_junior_cap: String(rateForm.overtime_junior_cap || '').trim() ? num(rateForm.overtime_junior_cap) : null,
        overtime_low_rate: num(rateForm.overtime_low_rate || 0),
        overtime_high_rate: num(rateForm.overtime_high_rate || 0),
        overtime_low_share_percent: num(rateForm.overtime_low_share_percent || 0),
        minimum_daily_wage: String(rateForm.minimum_daily_wage || '').trim() ? num(rateForm.minimum_daily_wage) : null,
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
          <div className={`hr-dialog${dialog.kind === 'edit' ? ' wide' : ''}`} role="dialog" aria-modal="true" aria-label="HR action">
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
            {dialog.kind === 'loan' ? (
              <>
                <h2>{dialog.approve ? 'Approve and pay out' : 'Turn down'} {dialog.row.loan_number}</h2>
                <p>{dialog.row.employee_name}: <b>{money(dialog.row.principal)}</b>, {money(dialog.row.monthly_deduction)} a month</p>
                {dialog.approve ? (
                  <label><span>Paid out by</span>
                    <select value={dialog.method} onChange={(e) => setDialog({ ...dialog, method: e.target.value })} aria-label="Loan paid out by">
                      {PAY_METHODS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                    </select>
                  </label>
                ) : null}
                <label><span>{dialog.approve ? 'Note (optional)' : 'Why'}</span><input value={dialog.note} onChange={(e) => setDialog({ ...dialog, note: e.target.value })} aria-label="Loan decision note" /></label>
              </>
            ) : null}
            {dialog.kind === 'edit' ? (
              <>
                <h2>Edit {dialog.row.full_name}</h2>
                <div className="hr-dialog-grid">
                {EDIT_FIELDS.filter((f) => !f.pay || seesPay).map((f) => (
                  <label key={f.key}><span>{f.label}</span>
                    <input
                      type={f.kind === 'number' ? 'number' : 'text'} value={dialog.values[f.key] ?? ''}
                      onChange={(e) => setDialog({ ...dialog, values: { ...dialog.values, [f.key]: e.target.value } })}
                      aria-label={`Edit ${f.label}`}
                    />
                  </label>
                ))}
                <label><span>Reports to</span>
                  <select value={dialog.values.manager_id} onChange={(e) => setDialog({ ...dialog, values: { ...dialog.values, manager_id: e.target.value } })} aria-label="Edit reports to">
                    <option value="">Nobody (HR decides their leave)</option>
                    {people.filter((x) => x.id !== dialog.row.id).map((x) => <option key={x.id} value={x.id}>{x.full_name}</option>)}
                  </select>
                </label>
                {seesPay ? (
                  <label><span>Paid</span>
                    <select value={dialog.values.pay_frequency} onChange={(e) => setDialog({ ...dialog, values: { ...dialog.values, pay_frequency: e.target.value } })} aria-label="Edit pay frequency">
                      <option value="monthly">Monthly</option>
                      <option value="weekly">Weekly (part-payments)</option>
                      <option value="fortnightly">Fortnightly (part-payments)</option>
                    </select>
                  </label>
                ) : null}
                {seesPay ? (
                  <label><span>Tax residence</span>
                    <select value={dialog.values.non_resident ? 'yes' : 'no'} onChange={(e) => setDialog({ ...dialog, values: { ...dialog.values, non_resident: e.target.value === 'yes' } })} aria-label="Edit tax residence">
                      <option value="no">Resident</option>
                      <option value="yes">Non-resident (flat 25%)</option>
                    </select>
                  </label>
                ) : null}
                </div>
                {seesPay ? null : <p className="hr-muted">Bank, Mobile Money, ID numbers and pay are changed by an HR manager.</p>}
                <p className="hr-muted">To change pay, use Change salary: it keeps a dated history and pays any back pay.</p>
              </>
            ) : null}
            {dialog.kind === 'salary' ? (
              <>
                <h2>Change salary for {dialog.row.full_name}</h2>
                <p className="hr-muted">
                  Payroll uses the new pay from the first month that starts on or after this date. If the date is before a month
                  already approved, the difference is paid as back pay on the next payroll; approved months are not changed.
                </p>
                <label><span>From</span><input type="date" value={dialog.effective_from} onChange={(e) => setDialog({ ...dialog, effective_from: e.target.value })} aria-label="Salary change from" /></label>
                <label><span>Basic a month</span><input type="number" min="0" step="0.01" value={dialog.basic} onChange={(e) => setDialog({ ...dialog, basic: e.target.value })} aria-label="New basic salary" /></label>
                <label><span>Allowances a month</span><input type="number" min="0" step="0.01" value={dialog.allowances} onChange={(e) => setDialog({ ...dialog, allowances: e.target.value })} aria-label="New allowances" /></label>
                <label><span>Why</span><input value={dialog.reason} onChange={(e) => setDialog({ ...dialog, reason: e.target.value })} aria-label="Salary change reason" /></label>
              </>
            ) : null}
            {dialog.kind === 'repay' ? (
              <>
                <h2>Paid back {dialog.row.loan_number}</h2>
                <p>Still owed {money(dialog.row.balance)}</p>
                <label><span>Amount</span><input type="number" min="0" step="0.01" value={dialog.amount} onChange={(e) => setDialog({ ...dialog, amount: e.target.value })} aria-label="Repayment amount" /></label>
                <label><span>Paid by</span>
                  <select value={dialog.method} onChange={(e) => setDialog({ ...dialog, method: e.target.value })} aria-label="Repayment paid by">
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

      {PEOPLE_WORK_SCREENS[tab] ? <PeopleWork tab={tab} seesPay={seesPay} /> : null}
      {TIME_SCREENS[tab] ? <TimeWork tab={tab} seesPay={seesPay} /> : null}

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
              <label><span>Reports to</span>
                <select value={form.manager_id} onChange={(e) => setForm({ ...form, manager_id: e.target.value })} aria-label="Reports to">
                  <option value="">Nobody (HR decides their leave)</option>
                  {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
              </label>
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
              <label><span>Terminal ID (fingerprint / face)</span><input value={form.biometric_id} onChange={(e) => setForm({ ...form, biometric_id: e.target.value })} aria-label="Terminal ID" /></label>
              <label><span>Mobile Money</span><input value={form.mobile_money} placeholder="+233…" onChange={(e) => setForm({ ...form, mobile_money: e.target.value })} aria-label="Mobile Money number" /></label>
              {seesPay ? (
                <>
                <label><span>Sales commission %</span><input type="number" min="0" max="100" step="0.25" value={form.commission_percent} onChange={(e) => setForm({ ...form, commission_percent: e.target.value })} aria-label="Sales commission percent" /></label>
                <label><span>Tax residence</span>
                  <select value={form.non_resident ? 'yes' : 'no'} onChange={(e) => setForm({ ...form, non_resident: e.target.value === 'yes' })} aria-label="Tax residence">
                    <option value="no">Resident</option>
                    <option value="yes">Non-resident (flat 25%)</option>
                  </select>
                </label>
                <label><span>Paid</span>
                  <select value={form.pay_frequency || 'monthly'} onChange={(e) => setForm({ ...form, pay_frequency: e.target.value })} aria-label="Pay frequency">
                    <option value="monthly">Monthly</option>
                    <option value="weekly">Weekly (part-payments)</option>
                    <option value="fortnightly">Fortnightly (part-payments)</option>
                  </select>
                </label>
                </>
              ) : null}
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
                    <td>
                      <div className="hr-row">
                        {seesPay ? <button type="button" onClick={() => setDialog({ kind: 'salary', row: p, effective_from: iso(), basic: String(p.basic_salary ?? ''), allowances: String(p.allowances ?? '0'), reason: '' })}>Change salary</button> : null}
                        <button
                          type="button" aria-label={`Edit ${p.full_name}`}
                          onClick={() => setDialog({
                            kind: 'edit', row: p,
                            values: { ...Object.fromEntries(EDIT_FIELDS.map((f) => [f.key, p[f.key] ?? ''])), manager_id: p.manager_id || '', pay_frequency: p.pay_frequency || 'monthly', non_resident: Boolean(p.non_resident) },
                          })}
                        >Edit</button>
                        <button type="button" className="hr-danger" onClick={() => setDialog({ kind: 'left', row: p, left_on: iso(), reason: '' })}>Leaving</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {people.length === 0 ? <tr><td colSpan={6} className="hr-muted">No staff yet. Add the first person above.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <AskHr examples={['Who is on leave today?', 'Leave waiting', 'Headcount', 'Contracts ending', 'Payroll this month']} />
          <Signals />
          <StaffFiles people={people} canConfidential={seesPay} />
          <Org canPlan={seesPay} />
        </>
      ) : null}

      {tab === 'leave' ? (
        <>
          <Cover asHr />
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
                    <td>
                      {l.status === 'pending' ? (l.stage === 'manager' ? 'Waiting for their manager' : 'Waiting for HR') : l.status}
                      {l.manager_note ? <><br /><small className="hr-muted">Manager: {l.manager_note}</small></> : null}
                      {l.decision_note ? <><br /><small className="hr-muted">{l.decision_note}</small></> : null}
                    </td>
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
          <section className="hr-box hr-scroll" aria-label="Public holidays">
            <Head
              title={`Public holidays ${holidayYear}`}
              meta={
                <span className="hr-row">
                  <button type="button" aria-label="Previous year" onClick={() => { setSuggested([]); setHolidayYear(holidayYear - 1); }}>‹</button>
                  <button type="button" aria-label="Next year" onClick={() => { setSuggested([]); setHolidayYear(holidayYear + 1); }}>›</button>
                </span>
              }
            />
            <p className="hr-muted">Leave and unpaid days skip these days. Add each holiday on the day it is taken off, including a moved one.</p>
            <table>
              <tbody>
                {holidays.map((hday) => (
                  <tr key={hday.id}>
                    <td>{hday.day}</td><td>{hday.weekday}</td><td>{hday.name}</td>
                    <td><button type="button" className="hr-danger" aria-label={`Remove ${hday.name}`} disabled={busy} onClick={() => void run(`/hrm/holidays/${hday.id}`, null, 'Holiday removed', 'DELETE')}>Remove</button></td>
                  </tr>
                ))}
                {holidays.length === 0 ? <tr><td className="hr-muted">No holidays for this year yet.</td></tr> : null}
              </tbody>
            </table>
            <div className="hr-form" style={{ marginTop: 10 }}>
              <label><span>Day</span><input type="date" value={holidayForm.day} onChange={(e) => setHolidayForm({ ...holidayForm, day: e.target.value })} aria-label="Holiday date" /></label>
              <label><span>Name</span><input value={holidayForm.name} onChange={(e) => setHolidayForm({ ...holidayForm, name: e.target.value })} aria-label="Holiday name" /></label>
              <button
                type="button" className="hr-primary" disabled={busy || !holidayForm.day || holidayForm.name.trim().length < 2}
                onClick={async () => { if (await run('/hrm/holidays', { holidays: [{ day: holidayForm.day, name: holidayForm.name.trim() }] }, 'Holiday saved')) setHolidayForm({ day: '', name: '' }); }}
              >Add holiday</button>
              <button
                type="button" disabled={busy}
                onClick={async () => { try { setSuggested(((await api(`/hrm/holidays/suggested?year=${holidayYear}`))?.data || []).map((r: Row) => ({ ...r, pick: true }))); } catch (err) { setError(problem(err)); } }}
              >Show Ghana&apos;s usual holidays</button>
            </div>
            {suggested.length ? (
              <>
                <p className="hr-muted" role="note">
                  A starting list only. Check it against the current Public Holidays Act and government notices before saving: a holiday
                  on a weekend may be moved, and the two Eid holidays are announced each year, so add them yourself.
                </p>
                <table aria-label="Suggested holidays">
                  <tbody>
                    {suggested.map((r, i) => (
                      <tr key={r.day}>
                        <td><input type="checkbox" checked={r.pick} aria-label={`Use ${r.name}`} onChange={(e) => setSuggested(suggested.map((x, n) => (n === i ? { ...x, pick: e.target.checked } : x)))} /></td>
                        <td>{r.day}</td><td>{r.weekday}</td><td>{r.name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <button
                  type="button" className="hr-primary" disabled={busy || !suggested.some((r) => r.pick)}
                  onClick={async () => { if (await run('/hrm/holidays', { holidays: suggested.filter((r) => r.pick).map((r) => ({ day: r.day, name: r.name })) }, 'Holidays saved')) setSuggested([]); }}
                >Save the ticked holidays</button>
              </>
            ) : null}
          </section>
        </>
      ) : null}

      {tab === 'loans' ? (
        <>
          <section className="hr-box" aria-label="Lend to a member of staff">
            <Head title="Record a loan or advance" />
            <p className="hr-muted">
              Someone other than you must approve it, which pays it out and books it to Staff Loans and Advances. Each approved
              payroll then takes the monthly amount until it is paid back, never more than the person&apos;s pay. No interest is charged.
            </p>
            <div className="hr-form">
              <label><span>Employee</span>
                <select value={loanForm.employee_id} onChange={(e) => setLoanForm({ ...loanForm, employee_id: e.target.value })} aria-label="Loan employee">
                  <option value="">Choose</option>
                  {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
              </label>
              <label><span>Kind</span>
                <select value={loanForm.kind} onChange={(e) => setLoanForm({ ...loanForm, kind: e.target.value, monthly_deduction: e.target.value === 'advance' ? loanForm.principal : loanForm.monthly_deduction })} aria-label="Loan kind">
                  <option value="loan">Loan, paid back over months</option>
                  <option value="advance">Salary advance, back from the next payroll</option>
                </select>
              </label>
              <label><span>Amount</span><input type="number" min="0" step="0.01" value={loanForm.principal} onChange={(e) => setLoanForm({ ...loanForm, principal: e.target.value, monthly_deduction: loanForm.kind === 'advance' ? e.target.value : loanForm.monthly_deduction })} aria-label="Loan amount" /></label>
              <label><span>Taken each month</span><input type="number" min="0" step="0.01" disabled={loanForm.kind === 'advance'} value={loanForm.monthly_deduction} onChange={(e) => setLoanForm({ ...loanForm, monthly_deduction: e.target.value })} aria-label="Monthly repayment" /></label>
              <label><span>First payroll month (optional)</span><input type="month" value={loanForm.first_period} onChange={(e) => setLoanForm({ ...loanForm, first_period: e.target.value })} aria-label="First repayment month" /></label>
              <label><span>Reason</span><input value={loanForm.reason} onChange={(e) => setLoanForm({ ...loanForm, reason: e.target.value })} aria-label="Loan reason" /></label>
              <button
                type="button" className="hr-primary"
                disabled={busy || !loanForm.employee_id || !(Number(loanForm.principal) > 0) || !(Number(loanForm.monthly_deduction) > 0)}
                onClick={async () => {
                  const ok = await run('/hrm/loans', {
                    employee_id: loanForm.employee_id,
                    kind: loanForm.kind,
                    principal: Number(loanForm.principal),
                    monthly_deduction: Number(loanForm.monthly_deduction),
                    first_period: loanForm.first_period || null,
                    reason: loanForm.reason.trim() || null,
                  }, 'Request recorded');
                  if (ok) setLoanForm({ employee_id: '', kind: 'loan', principal: '', monthly_deduction: '', first_period: '', reason: '' });
                }}
              >Record request</button>
            </div>
          </section>
          <section className="hr-box hr-scroll" aria-label="Loans and advances">
            <Head title="Loans and advances" />
            <table>
              <thead><tr><th>Number</th><th>Who</th><th>Kind</th><th>Amount</th><th>Each month</th><th>Still owed</th><th>Status</th><th /></tr></thead>
              <tbody>
                {loans.map((l) => (
                  <tr key={l.id}>
                    <td>{l.loan_number}</td>
                    <td>{l.employee_name}{l.reason ? <><br /><small className="hr-muted">{l.reason}</small></> : null}</td>
                    <td>{l.kind === 'part_pay' ? 'Part-payment' : l.kind === 'advance' ? 'Advance' : 'Loan'}</td>
                    <td className="hr-num">{money(l.principal)}</td>
                    <td className="hr-num">{money(l.monthly_deduction)}</td>
                    <td className="hr-num">{money(l.balance)}</td>
                    <td>{({ pending: 'Waiting for a decision', active: 'Being repaid', settled: 'Paid back', rejected: 'Turned down' } as Record<string, string>)[l.status] || l.status}{l.decision_note ? <><br /><small className="hr-muted">{l.decision_note}</small></> : null}</td>
                    <td>
                      {l.status === 'pending' ? (
                        <div className="hr-row">
                          <button type="button" className="hr-primary" onClick={() => setDialog({ kind: 'loan', row: l, approve: true, method: 'bank_transfer', note: '' })}>Approve and pay out</button>
                          <button type="button" className="hr-danger" onClick={() => setDialog({ kind: 'loan', row: l, approve: false, method: '', note: '' })}>Turn down</button>
                        </div>
                      ) : l.kind === 'part_pay' ? (
                        <button type="button" aria-label={`Print pay note ${l.loan_number}`} onClick={() => printPayNote(l)}>Pay note</button>
                      ) : l.status === 'active' ? (
                        <button type="button" onClick={() => setDialog({ kind: 'repay', row: l, amount: String(l.balance), method: 'cash' })}>Paid back in cash</button>
                      ) : null}
                    </td>
                  </tr>
                ))}
                {loans.length === 0 ? <tr><td colSpan={8} className="hr-muted">No loans or advances yet.</td></tr> : null}
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
          <section className="hr-box hr-scroll" aria-label="Sales commission">
            <Head title="Sales commission" />
            <p className="hr-muted">
              Net sales come from the Sales by salesperson report (FMCG: delivered orders the person booked), matched by the email on the
              staff record. Approve a month to pay it on that month&apos;s payroll: taxed as earnings, no SSNIT.
            </p>
            <div className="hr-row">
              <input type="month" value={commPeriod} onChange={(e) => setCommPeriod(e.target.value)} aria-label="Commission month" style={{ maxWidth: 200 }} />
              <button type="button" disabled={busy} onClick={async () => {
                try { setCommissions((await api(`/hrm/commissions?period=${commPeriod}`))?.data || []); } catch (err) { setError(problem(err)); }
              }}>Show commission</button>
            </div>
            {commissions ? (
              <table>
                <thead><tr><th>Who</th><th>Rate</th><th>Net sales</th><th>Commission</th><th>Approved</th><th /></tr></thead>
                <tbody>
                  {commissions.map((c) => (
                    <tr key={c.employee_id}>
                      <td>{c.employee_name}{c.linked_login ? null : <><br /><small className="hr-muted">No sign-in with this email</small></>}</td>
                      <td>{c.percent}%</td><td className="hr-num">{money(c.net_sales)}</td><td className="hr-num">{money(c.commission)}</td>
                      <td>{c.approved ? `${money(c.approved.amount)}${c.approved.status === 'paid' ? ' (paid)' : ''}` : '—'}</td>
                      <td>
                        {c.linked_login && c.approved?.status !== 'paid' ? (
                          <button type="button" className="hr-primary" disabled={busy} onClick={async () => {
                            if (await run('/hrm/commissions', { employee_id: c.employee_id, period: commPeriod }, 'Commission approved')) {
                              setCommissions((await api(`/hrm/commissions?period=${commPeriod}`))?.data || []);
                            }
                          }}>Approve {money(c.commission)}</button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                  {commissions.length === 0 ? <tr><td colSpan={6} className="hr-muted">Nobody has a commission percent.</td></tr> : null}
                </tbody>
              </table>
            ) : null}
          </section>
          <LeavePay people={people} />
          <PartPay />
          <section className="hr-box hr-scroll" aria-label="Corrections to approved pay">
            <Head title="Corrections for the next payroll" />
            <p className="hr-muted">
              An approved month never changes. Put a mistake right here, with a reason: it is paid (or taken back) on the next
              payroll you draw up. Back pay of basic attracts SSNIT; other corrections attract PAYE only.
            </p>
            <div className="hr-form">
              <label><span>Employee</span>
                <select value={adjForm.employee_id} onChange={(e) => setAdjForm({ ...adjForm, employee_id: e.target.value })} aria-label="Correction employee">
                  <option value="">Choose</option>
                  {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
              </label>
              <label><span>Kind</span>
                <select value={adjForm.kind} onChange={(e) => setAdjForm({ ...adjForm, kind: e.target.value })} aria-label="Correction kind">
                  <option value="correction">Other earning put right</option>
                  <option value="arrears">Back pay of basic</option>
                </select>
              </label>
              <label><span>Amount (minus to take back)</span><input type="number" step="0.01" value={adjForm.amount} onChange={(e) => setAdjForm({ ...adjForm, amount: e.target.value })} aria-label="Correction amount" /></label>
              <label><span>For month (optional)</span><input type="month" value={adjForm.for_period} onChange={(e) => setAdjForm({ ...adjForm, for_period: e.target.value })} aria-label="Correction for month" /></label>
              <label><span>Why</span><input value={adjForm.reason} onChange={(e) => setAdjForm({ ...adjForm, reason: e.target.value })} aria-label="Correction reason" /></label>
              <button
                type="button" className="hr-primary"
                disabled={busy || !adjForm.employee_id || !Number(adjForm.amount) || adjForm.reason.trim().length < 3}
                onClick={async () => {
                  const ok = await run('/hrm/adjustments', { employee_id: adjForm.employee_id, kind: adjForm.kind, amount: Number(adjForm.amount), for_period: adjForm.for_period || null, reason: adjForm.reason.trim() }, 'Correction saved');
                  if (ok) setAdjForm({ employee_id: '', kind: 'correction', amount: '', for_period: '', reason: '' });
                }}
              >Save correction</button>
            </div>
            {adjustments.filter((a) => a.status !== 'cancelled').length ? (
              <table>
                <thead><tr><th>Who</th><th>What</th><th>Amount</th><th>Status</th><th /></tr></thead>
                <tbody>
                  {adjustments.filter((a) => a.status !== 'cancelled').map((a) => (
                    <tr key={a.id}>
                      <td>{a.employee_name}</td>
                      <td>{a.reason}</td>
                      <td className="hr-num">{money(a.amount)}</td>
                      <td>{({ pending: 'Waiting for the next payroll', in_run: 'On a draft payroll', applied: 'Paid' } as Record<string, string>)[a.status] || a.status}</td>
                      <td>{a.status === 'pending' ? <button type="button" className="hr-danger" aria-label={`Cancel correction for ${a.employee_name}`} onClick={() => void run(`/hrm/adjustments/${a.id}`, null, 'Correction cancelled', 'DELETE')}>Cancel</button> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
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
              {(r.warnings || []).map((w: string) => <p key={w} className="hr-bad" role="alert">{w}</p>)}
              {openRun === r.id ? (
                <table>
                  <thead><tr><th>Name</th><th>Gross</th><th>SSNIT</th><th>PAYE</th><th>Other</th><th>Net</th><th /></tr></thead>
                  <tbody>
                    {r.slips.map((s: Row) => (
                      <tr key={s.id}>
                        <td>
                          {s.employee_name}{s.unpaid_days ? <><br /><small className="hr-muted">{s.unpaid_days} unpaid days</small></> : null}
                          {(s.warnings || []).includes('below_minimum_wage') ? <><br /><small className="hr-bad">Under the daily minimum wage. Raise the basic before approving.</small></> : null}
                          {Number(s.overtime_tax) ? <><br /><small className="hr-muted">Overtime tax {money(s.overtime_tax)} (in PAYE)</small></> : null}
                        </td>
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
          <section className="hr-box hr-scroll" aria-label="PAYE and SSNIT schedules">
            <Head title="PAYE and SSNIT schedules" />
            <p className="hr-muted">Read from approved payslips: working papers for your own GRA and SSNIT returns. The system does not file them.</p>
            <div className="hr-row">
              <input type="month" value={schedPeriod} onChange={(e) => setSchedPeriod(e.target.value)} aria-label="Schedule month" style={{ maxWidth: 200 }} />
              <button type="button" disabled={busy} onClick={async () => {
                try {
                  const [a, b] = await Promise.all([api(`/hrm/reports/paye?period=${schedPeriod}`), api(`/hrm/reports/ssnit?period=${schedPeriod}`)]);
                  setPaye(a?.data || null);
                  setSsnit(b?.data || null);
                } catch (err) { setError(problem(err)); }
              }}>Show schedules</button>
            </div>
            {paye ? (
              <>
                <h2 style={{ marginTop: 12 }}>PAYE {paye.period}</h2>
                {paye.missing_tax_id?.length ? <p className="hr-banner bad">No TIN or Ghana Card: {paye.missing_tax_id.join(', ')}</p> : null}
                <table>
                  <thead><tr><th>Employee</th><th>TIN</th><th>Gross</th><th>Taxable</th><th>PAYE</th></tr></thead>
                  <tbody>
                    {paye.rows.map((r: Row) => <tr key={r.employee_number}><td>{r.full_name}</td><td>{r.tin || r.ghana_card || '—'}</td><td className="hr-num">{money(r.gross)}</td><td className="hr-num">{money(r.taxable)}</td><td className="hr-num">{money(r.paye)}</td></tr>)}
                    <tr><th>Total</th><th /><th className="hr-num">{money(paye.totals.gross)}</th><th className="hr-num">{money(paye.totals.taxable)}</th><th className="hr-num">{money(paye.totals.paye)}</th></tr>
                  </tbody>
                </table>
                <button type="button" onClick={() => downloadCsv(`paye-${paye.period}.csv`, [['Employee number', 'Name', 'TIN', 'Ghana Card', 'Gross', 'SSNIT', 'Tier 3 relief', 'Taxable', 'PAYE'], ...paye.rows.map((r: Row) => [r.employee_number, r.full_name, r.tin, r.ghana_card, r.gross, r.ssnit_employee, r.tier3_relief, r.taxable, r.paye])])}>Download PAYE CSV</button>
              </>
            ) : null}
            {ssnit ? (
              <>
                <h2 style={{ marginTop: 12 }}>SSNIT {ssnit.period}</h2>
                {ssnit.missing_ssnit_number?.length ? <p className="hr-banner bad">No SSNIT number: {ssnit.missing_ssnit_number.join(', ')}</p> : null}
                <table>
                  <thead><tr><th>Employee</th><th>SSNIT no.</th><th>Insurable</th><th>Staff</th><th>Company</th><th>Tier 1</th><th>Tier 2</th></tr></thead>
                  <tbody>
                    {ssnit.rows.map((r: Row) => <tr key={r.employee_number}><td>{r.full_name}</td><td>{r.ssnit_number || '—'}</td><td className="hr-num">{money(r.insurable)}</td><td className="hr-num">{money(r.employee_share)}</td><td className="hr-num">{money(r.employer_share)}</td><td className="hr-num">{money(r.tier1)}</td><td className="hr-num">{money(r.tier2)}</td></tr>)}
                  </tbody>
                </table>
                <button type="button" onClick={() => downloadCsv(`ssnit-${ssnit.period}.csv`, [['Employee number', 'Name', 'SSNIT number', 'Ghana Card', 'Insurable', 'Staff share', 'Company share', 'Tier 1', 'Tier 2', 'Tier 3'], ...ssnit.rows.map((r: Row) => [r.employee_number, r.full_name, r.ssnit_number, r.ghana_card, r.insurable, r.employee_share, r.employer_share, r.tier1, r.tier2, r.tier3])])}>Download SSNIT CSV</button>
              </>
            ) : null}
          </section>
          <section className="hr-box" aria-label="Yearly tax statement">
            <Head title="Yearly tax statement" />
            <div className="hr-row">
              <select value={stmtPerson} onChange={(e) => setStmtPerson(e.target.value)} aria-label="Tax statement employee">
                <option value="">Choose a person</option>
                {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
              </select>
              <input type="number" min="2000" max="2100" value={stmtYear} onChange={(e) => setStmtYear(Number(e.target.value))} aria-label="Tax statement year" style={{ maxWidth: 110 }} />
              <button type="button" disabled={!stmtPerson} onClick={async () => {
                try { printStatement((await api(`/hrm/reports/tax-statement?employee_id=${stmtPerson}&year=${stmtYear}`))?.data || {}); } catch (err) { setError(problem(err)); }
              }}>Print statement</button>
            </div>
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
            <label><span>Annual leave is earned</span>
              <select value={settings.leave_accrual || 'upfront'} onChange={(e) => setSettings({ ...settings, leave_accrual: e.target.value })} aria-label="How annual leave is earned">
                <option value="upfront">All at the start of the year</option>
                <option value="monthly">A twelfth each month</option>
              </select>
            </label>
            <label><span>Working hours a day</span><input type="number" min="1" max="24" step="0.5" value={settings.hours_per_day ?? 8} onChange={(e) => setSettings({ ...settings, hours_per_day: e.target.value })} aria-label="Working hours a day" /></label>
            <label><span>Overtime pay rate (x hourly)</span><input type="number" min="1" max="5" step="0.25" value={settings.overtime_rate ?? 1.5} onChange={(e) => setSettings({ ...settings, overtime_rate: e.target.value })} aria-label="Overtime rate" /></label>
            <label className="hr-check">
              <input type="checkbox" checked={Boolean(settings.clock_needs_site)} onChange={(e) => setSettings({ ...settings, clock_needs_site: e.target.checked })} aria-label="Clock-ins must be at a site" />
              <span>Clock-ins from phones must be at a work site</span>
            </label>
            <label><span>Unused days that carry into next year</span><input type="number" min="0" value={settings.carry_over_days ?? 0} onChange={(e) => setSettings({ ...settings, carry_over_days: e.target.value })} aria-label="Carry-over days" /></label>
            <label><span>Weekly / fortnightly part-pay, % of basic</span><input type="number" min="0" max="100" value={settings.part_pay_percent ?? 80} onChange={(e) => setSettings({ ...settings, part_pay_percent: e.target.value })} aria-label="Part-pay percent" /></label>
            <label><span>Tell HR when leave waits on a manager for (working days, 0 = never)</span><input type="number" min="0" max="60" value={settings.escalate_after_days ?? 3} onChange={(e) => setSettings({ ...settings, escalate_after_days: e.target.value })} aria-label="Escalate leave after days" /></label>
            <label><span>Working days a month</span><input type="number" min="1" value={settings.working_days_per_month} onChange={(e) => setSettings({ ...settings, working_days_per_month: e.target.value })} aria-label="Working days a month" /></label>
            <label><span>Staff SSNIT %</span><input type="number" min="0" value={settings.ssnit_employee_percent} onChange={(e) => setSettings({ ...settings, ssnit_employee_percent: e.target.value })} aria-label="Staff SSNIT percent" /></label>
            <label><span>Employer SSNIT %</span><input type="number" min="0" value={settings.ssnit_employer_percent} onChange={(e) => setSettings({ ...settings, ssnit_employer_percent: e.target.value })} aria-label="Employer SSNIT percent" /></label>
            <label className="hr-check">
              <input type="checkbox" checked={Boolean(settings.two_person_payroll)} onChange={(e) => setSettings({ ...settings, two_person_payroll: e.target.checked })} aria-label="Two people for payroll" />
              <span>Someone other than the person who drew up a payroll must approve it</span>
            </label>
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
                two_person_payroll: Boolean(settings.two_person_payroll),
                leave_accrual: settings.leave_accrual || 'upfront',
                carry_over_days: Number(settings.carry_over_days || 0),
                escalate_after_days: Number(settings.escalate_after_days ?? 3),
                part_pay_percent: Number(settings.part_pay_percent ?? 80),
                hours_per_day: Number(settings.hours_per_day || 8),
                overtime_rate: Number(settings.overtime_rate || 1.5),
                clock_needs_site: Boolean(settings.clock_needs_site),
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
          <SuggestedRates have={rates.map((r) => String(r.effective_from))} onAdded={() => void load()} />
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
            <label><span>Junior overtime: employment income up to a month (GRA: GH₵18,000 a year = 1,500; blank = off)</span><input type="number" min="0" value={rateForm.overtime_junior_cap} onChange={(e) => setRateForm({ ...rateForm, overtime_junior_cap: e.target.value })} aria-label="Junior overtime basic limit" /></label>
            <label><span>Overtime tax % (first part)</span><input type="number" min="0" step="0.5" value={rateForm.overtime_low_rate} onChange={(e) => setRateForm({ ...rateForm, overtime_low_rate: e.target.value })} aria-label="Overtime tax low rate" /></label>
            <label><span>First part: overtime up to % of basic</span><input type="number" min="0" step="1" value={rateForm.overtime_low_share_percent} onChange={(e) => setRateForm({ ...rateForm, overtime_low_share_percent: e.target.value })} aria-label="Overtime low part share" /></label>
            <label><span>Overtime tax % (the rest)</span><input type="number" min="0" step="0.5" value={rateForm.overtime_high_rate} onChange={(e) => setRateForm({ ...rateForm, overtime_high_rate: e.target.value })} aria-label="Overtime tax high rate" /></label>
            <label><span>Daily minimum wage (blank = no check)</span><input type="number" min="0" step="0.01" value={rateForm.minimum_daily_wage} onChange={(e) => setRateForm({ ...rateForm, minimum_daily_wage: e.target.value })} aria-label="Daily minimum wage" /></label>
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
            <div className="hr-tile">
              <span>Annual leave left</span><b>{me.leave_balance.left}</b>
              <small>of {me.leave_balance.entitled} in {me.leave_balance.year}{me.leave_balance.carried ? ` (${me.leave_balance.carried} carried over)` : ''}</small>
            </div>
          </div>
          <MyClock />
          {teamLeave.length ? (
            <section className="hr-box hr-scroll" aria-label="My team's leave">
              <Head title="Leave from my team" />
              <p className="hr-muted">You decide first; HR has the last word.</p>
              <table>
                <tbody>
                  {teamLeave.map((l) => (
                    <tr key={l.id}>
                      <td>{l.employee_name}</td><td>{leaveWord(l.leave_type)}</td><td>{l.starts_on} to {l.ends_on}</td><td>{l.days} days</td>
                      <td>
                        <div className="hr-row">
                          <button type="button" className="hr-primary" onClick={() => void run(`/hrm/leave/${l.id}/decide`, { approve: true }, 'Passed to HR')}>Agree</button>
                          <button type="button" className="hr-danger" onClick={() => setDialog({ kind: 'reject', row: l, note: '' })}>Turn down</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}
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
          <section className="hr-box" aria-label="Ask for a loan or advance">
            <Head title="Ask for a loan or advance" />
            <div className="hr-form">
              <label><span>Kind</span>
                <select value={myLoan.kind} onChange={(e) => setMyLoan({ ...myLoan, kind: e.target.value, monthly_deduction: e.target.value === 'advance' ? myLoan.principal : myLoan.monthly_deduction })} aria-label="My loan kind">
                  <option value="advance">Salary advance, back from the next payroll</option>
                  <option value="loan">Loan, paid back over months</option>
                </select>
              </label>
              <label><span>Amount</span><input type="number" min="0" step="0.01" value={myLoan.principal} onChange={(e) => setMyLoan({ ...myLoan, principal: e.target.value, monthly_deduction: myLoan.kind === 'advance' ? e.target.value : myLoan.monthly_deduction })} aria-label="My loan amount" /></label>
              {myLoan.kind === 'loan' ? (
                <label><span>Taken each month</span><input type="number" min="0" step="0.01" value={myLoan.monthly_deduction} onChange={(e) => setMyLoan({ ...myLoan, monthly_deduction: e.target.value })} aria-label="My monthly repayment" /></label>
              ) : null}
              <label><span>Why</span><input value={myLoan.reason} onChange={(e) => setMyLoan({ ...myLoan, reason: e.target.value })} aria-label="My loan reason" /></label>
              <button
                type="button" className="hr-primary"
                disabled={busy || !(Number(myLoan.principal) > 0) || !(Number(myLoan.monthly_deduction) > 0) || myLoan.reason.trim().length < 3}
                onClick={async () => {
                  const ok = await run('/hrm/me/loans', { kind: myLoan.kind, principal: Number(myLoan.principal), monthly_deduction: Number(myLoan.monthly_deduction), reason: myLoan.reason.trim() }, 'Request sent to payroll');
                  if (ok) setMyLoan({ kind: 'advance', principal: '', monthly_deduction: '', reason: '' });
                }}
              >Send request</button>
            </div>
            {(me.loans || []).length ? (
              <table aria-label="My loans">
                <tbody>
                  {me.loans.map((l: Row) => (
                    <tr key={l.id}><td>{l.kind === 'part_pay' ? 'Part-payment' : l.kind === 'advance' ? 'Advance' : 'Loan'} {l.loan_number}</td><td className="hr-num">{money(l.principal)}</td><td>{l.kind === 'part_pay' ? `Paid ${String(l.paid_out_at || '').slice(0, 10)}` : `Still owed ${money(l.balance)}`}</td><td>{l.kind === 'part_pay' ? <button type="button" aria-label={`Print my pay note ${l.loan_number}`} onClick={() => printPayNote(l)}>Pay note</button> : l.status}</td></tr>
                  ))}
                </tbody>
              </table>
            ) : null}
          </section>
          <section className="hr-box hr-scroll" aria-label="My payslips">
            <Head title="My payslips" />
            <table>
              <tbody>
                {me.payslips.map((s: Row) => <tr key={s.id}><td>{s.period}</td><td className="hr-num">{money(s.net)}</td><td><button type="button" onClick={() => printSlip(s, s.period)}>Print</button></td></tr>)}
                {me.payslips.length === 0 ? <tr><td className="hr-muted">No payslips yet.</td></tr> : null}
                {me.payslips.length ? (
                  <tr>
                    <td colSpan={3}>
                      <button type="button" onClick={async () => {
                        try { printStatement((await api(`/hrm/me/tax-statement?year=${new Date().getFullYear()}`))?.data || {}); } catch (err) { setError(problem(err)); }
                      }}>Print my tax statement for {new Date().getFullYear()}</button>
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </section>
          <AskHr examples={['How many leave days do I have?', 'Who approves my leave?', 'My payslip', 'Documents to accept', 'My claims']} />
          <MyDocuments />
          <Cover />
          <MyMore />
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
