'use client';

/**
 * Gym desk. Its own screen on its own tables (gym_*): today, the door, members, classes,
 * plans and reports. Nothing here uses the retail till.
 */

import { useSearchParams } from 'next/navigation';
import React, { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import DeskDashboard from '../../../components/DeskDashboard';
import DeskIcon from '../../../components/DeskIcon';
import './gym.css';

type Row = Record<string, any>;

const SCREENS: Record<string, { title: string; sub: string; icon: string }> = {
  today: { title: 'Dashboard', sub: '', icon: 'home' },
  door: { title: 'Door', sub: 'Check members in. The screen says who may train.', icon: 'door' },
  members: { title: 'Members', sub: 'Add members, sell and renew plans, and see who is due.', icon: 'users' },
  classes: { title: 'Classes', sub: 'Group classes, trainers and who has booked a place.', icon: 'calendarCheck' },
  plans: { title: 'Plans', sub: 'What you sell: monthly, yearly, day passes.', icon: 'tag' },
  reports: { title: 'Reports', sub: 'What the gym brought in and who is about to leave.', icon: 'chart' },
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
    <div className="gm-cardhead">
      <span className="gm-ico" aria-hidden="true"><DeskIcon name={pick} size={18} /></span>
      <h2>{title}</h2>
      {meta ? <span className="gm-meta">{meta}</span> : null}
    </div>
  );
}
const ROLE_TABS: Record<string, string[]> = {
  gym_trainer: ['today', 'door', 'classes'],
  gym_frontdesk: ['today', 'door', 'members', 'classes'],
};
const METHODS = [
  { id: 'cash', label: 'Cash' },
  { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'card', label: 'Card' },
  { id: 'bank_transfer', label: 'Bank transfer' },
];
const STATE_WORDS: Record<string, string> = {
  active: 'Active', expired: 'Ended', frozen: 'Frozen', none: 'No membership', upcoming: 'Starts soon', cancelled: 'Cancelled',
};

const money = (value: unknown) => formatMoney(Number(value || 0));
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const iso = (offset = 0) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
const when = (value?: string) => (value ? new Date(`${value}Z`).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '');

function GymDesk() {
  const params = useSearchParams();
  const [role, setRole] = useState('');
  const allowed = useMemo(() => TABS.filter((t) => !ROLE_TABS[role] || ROLE_TABS[role].includes(t.id)), [role]);
  const wanted = params.get('tab') || 'today';
  const tab = allowed.some((t) => t.id === wanted) ? wanted : 'today';

  const [today, setToday] = useState<Row | null>(null);
  const [members, setMembers] = useState<Row[]>([]);
  const [plans, setPlans] = useState<Row[]>([]);
  const [classes, setClasses] = useState<Row[]>([]);
  const [visits, setVisits] = useState<Row[]>([]);
  const [shift, setShift] = useState<Row | null>(null);
  const [report, setReport] = useState<Row | null>(null);
  const [range, setRange] = useState({ start: iso(-29), end: iso() });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [doorResult, setDoorResult] = useState<Row | null>(null);
  const [memberForm, setMemberForm] = useState({ full_name: '', phone: '', email: '', emergency_contact: '' });
  const [planForm, setPlanForm] = useState({ name: '', price: '', duration_days: '30', visit_limit: '' });
  const [classForm, setClassForm] = useState({ name: '', trainer_name: '', starts_at: '', capacity: '15' });
  const [floatCash, setFloatCash] = useState('');
  const [counted, setCounted] = useState('');
  const [dialog, setDialog] = useState<Row | null>(null);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || 'unknown'))).catch(() => setRole('unknown'));
  }, []);

  const load = useCallback(async () => {
    const get = async (path: string) => (await api(path))?.data;
    try {
      if (tab === 'today') setToday(await get('/gym/today'));
      if (tab === 'door') {
        const [m, v] = await Promise.all([get('/gym/members'), get('/gym/check-ins')]);
        setMembers(m || []);
        setVisits(v || []);
      }
      if (tab === 'members') {
        const [m, p, s] = await Promise.all([get('/gym/members'), get('/gym/plans'), get('/gym/till/shift')]);
        setMembers(m || []);
        setPlans((p || []).filter((x: Row) => x.is_active));
        setShift(s || null);
      }
      if (tab === 'classes') {
        const [c, m] = await Promise.all([get('/gym/classes'), get('/gym/members')]);
        setClasses(c || []);
        setMembers(m || []);
      }
      if (tab === 'plans') setPlans((await get('/gym/plans')) || []);
      if (tab === 'reports') setReport(await get(`/gym/reports?start_date=${range.start}&end_date=${range.end}`));
    } catch (err) {
      setError(problem(err));
    }
  }, [tab, range.start, range.end]);

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

  async function letIn(member: Row) {
    const res = (await run('/gym/check-ins', { member_id: member.id }, '')) as Row | null;
    setNotice('');
    if (res) setDoorResult(res);
    setSearch('');
  }

  async function confirmDialog() {
    if (!dialog) return;
    let ok: unknown = null;
    if (dialog.kind === 'sell') {
      ok = await run('/gym/memberships', { member_id: dialog.row.id, plan_id: dialog.plan_id, method: dialog.method }, 'Membership sold');
    }
    if (dialog.kind === 'cancel') {
      const refund = Number(dialog.refund || 0);
      ok = await run(
        `/gym/memberships/${dialog.row.membership_id}/cancel`,
        { reason: dialog.reason.trim(), refund, method: refund > 0 ? dialog.method : null },
        'Membership cancelled',
      );
    }
    if (dialog.kind === 'book') ok = await run(`/gym/classes/${dialog.row.id}/book`, { member_id: dialog.member_id }, 'Booked');
    if (ok) setDialog(null);
  }

  const match = search.trim().toLowerCase();
  const shown = match
    ? members.filter((m) => `${m.full_name} ${m.member_number} ${m.phone || ''}`.toLowerCase().includes(match))
    : members;
  const dialogReady = dialog
    ? dialog.kind === 'sell'
      ? Boolean(dialog.plan_id)
      : dialog.kind === 'cancel'
        ? dialog.reason.trim().length >= 3
        : Boolean(dialog.member_id)
    : false;

  return (
    <div className="gym">
      {dialog ? (
        <div className="gm-veil">
          <div className="gm-dialog" role="dialog" aria-modal="true" aria-label="Gym action">
            {dialog.kind === 'sell' ? (
              <>
                <h2>Sell a plan to {dialog.row.full_name}</h2>
                <label><span>Plan</span>
                  <select value={dialog.plan_id} onChange={(e) => setDialog({ ...dialog, plan_id: e.target.value })} aria-label="Plan">
                    <option value="">Choose</option>
                    {plans.map((p) => <option key={p.id} value={p.id}>{p.name} · {money(p.price)} · {p.duration_days} days</option>)}
                  </select>
                </label>
                <label><span>How they paid</span>
                  <select value={dialog.method} onChange={(e) => setDialog({ ...dialog, method: e.target.value })} aria-label="How they paid">
                    {METHODS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                  </select>
                </label>
                {dialog.row.state === 'active' ? <p className="gm-muted">This starts the day after the current plan ends on {dialog.row.ends_on}.</p> : null}
              </>
            ) : null}
            {dialog.kind === 'cancel' ? (
              <>
                <h2>Cancel {dialog.row.full_name}&apos;s membership</h2>
                <label><span>Reason</span><input autoFocus value={dialog.reason} onChange={(e) => setDialog({ ...dialog, reason: e.target.value })} aria-label="Reason" /></label>
                <label><span>Refund (0 for none)</span><input type="number" min="0" value={dialog.refund} onChange={(e) => setDialog({ ...dialog, refund: e.target.value })} aria-label="Refund" /></label>
                {Number(dialog.refund) > 0 ? (
                  <label><span>Paid back by</span>
                    <select value={dialog.method} onChange={(e) => setDialog({ ...dialog, method: e.target.value })} aria-label="Paid back by">
                      {METHODS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                    </select>
                  </label>
                ) : null}
              </>
            ) : null}
            {dialog.kind === 'book' ? (
              <>
                <h2>Book {dialog.row.name}</h2>
                <label><span>Member</span>
                  <select value={dialog.member_id} onChange={(e) => setDialog({ ...dialog, member_id: e.target.value })} aria-label="Member">
                    <option value="">Choose</option>
                    {members.filter((m) => m.state === 'active').map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
                  </select>
                </label>
              </>
            ) : null}
            {error ? <div className="gm-banner bad">{error}</div> : null}
            <div className="gm-row">
              <button type="button" className="gm-primary" disabled={busy || !dialogReady} onClick={() => void confirmDialog()}>Confirm</button>
              <button type="button" onClick={() => setDialog(null)}>Go back</button>
            </div>
          </div>
        </div>
      ) : null}

      {tab !== 'today' ? (
        <header className="gm-head">
          <span className="gm-head-ico" aria-hidden="true"><DeskIcon name={SCREENS[tab].icon} size={26} /></span>
          <div className="gm-head-text">
            <h1>{SCREENS[tab].title}</h1>
            <p>{SCREENS[tab].sub}</p>
          </div>
        </header>
      ) : null}
      {notice ? <div className="gm-banner" role="status">{notice}</div> : null}
      {error && !dialog ? <div className="gm-banner bad" role="alert">{error}</div> : null}

      {tab === 'today' && today ? (
        <DeskDashboard
          desk="Gym dashboard"
          actions={[
            { label: 'Open the door', href: '/gym?tab=door', primary: true, icon: 'door', hint: 'Let members in' },
            ...(role === 'gym_trainer' ? [] : [{ label: 'Add a member', href: '/gym?tab=members', icon: 'users', hint: 'Sell or renew a plan' }]),
            { label: 'Classes', href: '/gym?tab=classes', icon: 'calendarCheck', hint: 'Book a place' },
          ]}
          tiles={[
            { label: 'Visits today', icon: 'door', spark: (today.trend?.points || []).map((p: Row) => Number(p.value)), value: today.visits_today, before: { now: Number(today.visits_today), value: Number(today.visits_yesterday || 0), word: 'yesterday' }, href: '/gym?tab=door' },
            { label: 'Active members', icon: 'users', value: today.active_members, href: role === 'gym_trainer' ? undefined : '/gym?tab=members' },
            ...('takings_today' in today
              ? [{ label: 'Taken today', icon: 'cash', value: money(today.takings_today), before: { now: Number(today.takings_today), value: Number(today.takings_yesterday || 0), word: 'yesterday' } }]
              : []),
            { label: 'Ending this week', icon: 'calendar', value: today.expiring.length, sub: 'members to call', warn: today.expiring.length > 0 },
            ...('takings_today' in today
              ? [{ label: 'Till', icon: 'wallet', value: today.till_open ? 'Open' : 'Closed', sub: today.till_open ? 'Selling plans' : 'Open it to sell plans', warn: !today.till_open, href: role === 'gym_trainer' ? undefined : '/gym?tab=members' }]
              : []),
          ]}
          trend={today.trend}
          attention={today.attention}
        >
          <div className="gm-grid2">
            <section className="gm-box" aria-label="Classes today">
              <Head title="Classes today" />
              {today.classes.length === 0 ? <p className="gm-muted">No classes today.</p> : today.classes.map((c: Row) => (
                <div className="gm-line" key={c.id}>
                  <span><b>{when(c.starts_at).split(', ').pop()}</b> {c.name}{c.trainer_name ? <small className="gm-muted"> · {c.trainer_name}</small> : null}</span>
                  <span>{c.booked} of {c.capacity}</span>
                </div>
              ))}
            </section>
            <section className="gm-box gm-scroll" aria-label="Ending soon">
              <Head title="Ending this week" />
              {today.expiring.length === 0 ? <p className="gm-muted">Nobody is due this week.</p> : (
                <table>
                  <tbody>
                    {today.expiring.map((e: Row) => (
                      <tr key={e.member_id}><td>{e.member_name}<br /><small className="gm-muted">{e.plan_name}</small></td><td>{e.phone ? <a href={`tel:${e.phone}`}>{e.phone}</a> : '—'}</td><td>{e.ends_on}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          </div>
        </DeskDashboard>
      ) : null}

      {tab === 'door' ? (
        <>
          {doorResult ? (
            <div className={`gm-door ${doorResult.allowed ? 'yes' : 'no'}`} role="status">
              <b>{doorResult.allowed ? 'Let in' : 'Stop'}</b>
              <span>{doorResult.message}</span>
              {doorResult.member?.days_left != null ? <small>{doorResult.member.days_left} days left{doorResult.member.visits_left != null ? ` · ${doorResult.member.visits_left} visits left` : ''}</small> : null}
            </div>
          ) : null}
          <section className="gm-box" aria-label="Find member">
            <label><span>Name, number or phone</span><input autoFocus value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Find member" /></label>
            {match ? (
              <div className="gm-list">
                {shown.slice(0, 8).map((m) => (
                  <button type="button" key={m.id} disabled={busy} onClick={() => void letIn(m)}>
                    {m.full_name} <small>{m.member_number} · {STATE_WORDS[m.state]}</small>
                  </button>
                ))}
                {shown.length === 0 ? <p className="gm-muted">Nobody matches.</p> : null}
              </div>
            ) : null}
          </section>
          <section className="gm-box gm-scroll" aria-label="Recent visits">
            <Head title="At the door" />
            <table>
              <tbody>
                {visits.map((v) => <tr key={v.id}><td>{v.member_name}</td><td>{v.allowed ? 'In' : v.refused_reason}</td><td>{when(v.checked_in_at)}</td></tr>)}
                {visits.length === 0 ? <tr><td className="gm-muted">Nobody yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'members' ? (
        <>
          <section className="gm-box" aria-label="Till">
            {shift ? (
              <div className="gm-row">
                <span>Till open. Cash should be <b>{money(shift.expected_cash)}</b>.</span>
                <input type="number" min="0" placeholder="Cash counted" value={counted} onChange={(e) => setCounted(e.target.value)} aria-label="Cash counted" style={{ maxWidth: 170 }} />
                <button
                  type="button" disabled={busy || counted === ''}
                  onClick={async () => {
                    const res = (await run('/gym/till/shift/close', { counted_cash: Number(counted) }, 'Till closed')) as Row | null;
                    if (res) {
                      setCounted('');
                      const gap = Number(res.over_short);
                      setNotice(gap === 0 ? 'Till closed. The cash matches.' : `Till closed. ${gap < 0 ? 'Short' : 'Over'} by ${money(Math.abs(gap))}.`);
                    }
                  }}
                >Close till</button>
              </div>
            ) : (
              <div className="gm-row">
                <span>The till is closed. Open it to sell plans.</span>
                <input type="number" min="0" placeholder="Starting cash" value={floatCash} onChange={(e) => setFloatCash(e.target.value)} aria-label="Starting cash" style={{ maxWidth: 170 }} />
                <button type="button" className="gm-primary" disabled={busy} onClick={() => void run('/gym/till/shift/open', { opening_cash: Number(floatCash || 0) }, 'Till open')}>Open till</button>
              </div>
            )}
          </section>
          <section className="gm-box" aria-label="Add member">
            <Head title="Add a member" />
            <div className="gm-form">
              <label><span>Full name</span><input value={memberForm.full_name} onChange={(e) => setMemberForm({ ...memberForm, full_name: e.target.value })} aria-label="Member name" /></label>
              <label><span>Phone</span><input value={memberForm.phone} placeholder="+233…" onChange={(e) => setMemberForm({ ...memberForm, phone: e.target.value })} aria-label="Member phone" /></label>
              <label><span>Email</span><input value={memberForm.email} onChange={(e) => setMemberForm({ ...memberForm, email: e.target.value })} aria-label="Member email" /></label>
              <label><span>Emergency contact</span><input value={memberForm.emergency_contact} onChange={(e) => setMemberForm({ ...memberForm, emergency_contact: e.target.value })} aria-label="Emergency contact" /></label>
              <button
                type="button" className="gm-primary" disabled={busy || !memberForm.full_name.trim()}
                onClick={async () => {
                  const ok = await run('/gym/members', {
                    full_name: memberForm.full_name.trim(),
                    phone: memberForm.phone.replace(/[\s-]/g, '') || null,
                    email: memberForm.email.trim() || null,
                    emergency_contact: memberForm.emergency_contact.trim() || null,
                  }, 'Member added');
                  if (ok) setMemberForm({ full_name: '', phone: '', email: '', emergency_contact: '' });
                }}
              >Add member</button>
            </div>
          </section>
          <section className="gm-box gm-scroll" aria-label="Members">
            <Head title="Members" />
            <input placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search members" />
            <table>
              <thead><tr><th>Member</th><th>Plan</th><th>Status</th><th>Ends</th><th /></tr></thead>
              <tbody>
                {shown.map((m) => (
                  <tr key={m.id}>
                    <td>{m.full_name}<br /><small className="gm-muted">{m.member_number} {m.phone || ''}</small></td>
                    <td>{m.plan_name || '—'}</td><td>{STATE_WORDS[m.state]}</td><td>{m.ends_on || '—'}</td>
                    <td>
                      <div className="gm-row">
                        <button type="button" className="gm-primary" disabled={!shift} onClick={() => setDialog({ kind: 'sell', row: m, plan_id: '', method: 'cash' })}>{m.state === 'none' ? 'Sell plan' : 'Renew'}</button>
                        {m.state === 'active' ? <button type="button" onClick={() => void run(`/gym/memberships/${m.membership_id}/freeze`, null, 'Membership frozen')}>Freeze</button> : null}
                        {m.state === 'frozen' ? <button type="button" onClick={() => void run(`/gym/memberships/${m.membership_id}/unfreeze`, null, 'Membership running again')}>Unfreeze</button> : null}
                        {['active', 'frozen', 'upcoming'].includes(m.state) && role !== 'gym_frontdesk' ? (
                          <button type="button" className="gm-danger" onClick={() => setDialog({ kind: 'cancel', row: m, reason: '', refund: '0', method: 'cash' })}>Cancel</button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
                {shown.length === 0 ? <tr><td colSpan={5} className="gm-muted">No members yet. Add the first one above.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'classes' ? (
        <>
          <section className="gm-box" aria-label="Add class">
            <Head title="Add a class" />
            <div className="gm-form">
              <label><span>Class</span><input value={classForm.name} onChange={(e) => setClassForm({ ...classForm, name: e.target.value })} aria-label="Class name" /></label>
              <label><span>Trainer</span><input value={classForm.trainer_name} onChange={(e) => setClassForm({ ...classForm, trainer_name: e.target.value })} aria-label="Trainer" /></label>
              <label><span>When</span><input type="datetime-local" value={classForm.starts_at} onChange={(e) => setClassForm({ ...classForm, starts_at: e.target.value })} aria-label="Class time" /></label>
              <label><span>Places</span><input type="number" min="1" value={classForm.capacity} onChange={(e) => setClassForm({ ...classForm, capacity: e.target.value })} aria-label="Places" /></label>
              <button
                type="button" className="gm-primary" disabled={busy || !classForm.name.trim() || !classForm.starts_at}
                onClick={async () => {
                  const ok = await run('/gym/classes', {
                    name: classForm.name.trim(),
                    trainer_name: classForm.trainer_name.trim() || null,
                    starts_at: new Date(classForm.starts_at).toISOString().slice(0, 19),
                    capacity: Number(classForm.capacity),
                  }, 'Class added');
                  if (ok) setClassForm({ name: '', trainer_name: '', starts_at: '', capacity: '15' });
                }}
              >Add class</button>
            </div>
          </section>
          {classes.map((c) => (
            <section className="gm-box" key={c.id} aria-label={c.name}>
              <div className="gm-row" style={{ justifyContent: 'space-between' }}>
                <div><h2>{c.name}</h2><p className="gm-muted">{when(c.starts_at)}{c.trainer_name ? ` · ${c.trainer_name}` : ''} · {c.booked} of {c.capacity} booked</p></div>
                <div className="gm-row">
                  <button type="button" className="gm-primary" disabled={c.booked >= c.capacity} onClick={() => setDialog({ kind: 'book', row: c, member_id: '' })}>Book a member</button>
                  <button type="button" className="gm-danger" onClick={() => void run(`/gym/classes/${c.id}/cancel`, null, 'Class cancelled')}>Cancel class</button>
                </div>
              </div>
              {c.bookings.map((b: Row) => (
                <div className="gm-line" key={b.id}>
                  <span>{b.member_name}{b.status === 'attended' ? ' · came' : b.status === 'no_show' ? ' · did not come' : ''}</span>
                  <span className="gm-row">
                    <button type="button" onClick={() => void run(`/gym/bookings/${b.id}`, { status: 'attended' }, 'Saved')}>Came</button>
                    <button type="button" onClick={() => void run(`/gym/bookings/${b.id}`, { status: 'no_show' }, 'Saved')}>Did not come</button>
                    <button type="button" onClick={() => void run(`/gym/bookings/${b.id}`, { status: 'cancelled' }, 'Booking removed')}>Remove</button>
                  </span>
                </div>
              ))}
            </section>
          ))}
          {classes.length === 0 ? <section className="gm-box gm-muted">No classes coming up.</section> : null}
        </>
      ) : null}

      {tab === 'plans' ? (
        <>
          <section className="gm-box" aria-label="Add plan">
            <Head title="Add a plan" />
            <div className="gm-form">
              <label><span>Plan name</span><input value={planForm.name} onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })} aria-label="Plan name" /></label>
              <label><span>Price</span><input type="number" min="0" value={planForm.price} onChange={(e) => setPlanForm({ ...planForm, price: e.target.value })} aria-label="Plan price" /></label>
              <label><span>Days it lasts (1 for a day pass)</span><input type="number" min="1" value={planForm.duration_days} onChange={(e) => setPlanForm({ ...planForm, duration_days: e.target.value })} aria-label="Plan days" /></label>
              <label><span>Visit limit (blank for none)</span><input type="number" min="1" value={planForm.visit_limit} onChange={(e) => setPlanForm({ ...planForm, visit_limit: e.target.value })} aria-label="Visit limit" /></label>
              <button
                type="button" className="gm-primary" disabled={busy || !planForm.name.trim() || !(Number(planForm.price) > 0)}
                onClick={async () => {
                  const ok = await run('/gym/plans', {
                    name: planForm.name.trim(), price: Number(planForm.price), duration_days: Number(planForm.duration_days),
                    visit_limit: planForm.visit_limit ? Number(planForm.visit_limit) : null,
                  }, 'Plan added');
                  if (ok) setPlanForm({ name: '', price: '', duration_days: '30', visit_limit: '' });
                }}
              >Add plan</button>
            </div>
          </section>
          <section className="gm-box gm-scroll" aria-label="Plans">
            <table>
              <thead><tr><th>Plan</th><th>Price</th><th>Days</th><th>Visits</th><th /></tr></thead>
              <tbody>
                {plans.map((p) => (
                  <tr key={p.id}>
                    <td>{p.name}</td><td className="gm-num">{money(p.price)}</td><td>{p.duration_days}</td><td>{p.visit_limit ?? 'No limit'}</td>
                    <td><button type="button" onClick={() => void run(`/gym/plans/${p.id}`, { is_active: !p.is_active }, 'Plan saved', 'PATCH')}>{p.is_active ? 'Stop selling' : 'Sell again'}</button></td>
                  </tr>
                ))}
                {plans.length === 0 ? <tr><td colSpan={5} className="gm-muted">No plans yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'reports' && report ? (
        <>
          <section className="gm-box" aria-label="Report dates">
            <div className="gm-form">
              <label><span>From</span><input type="date" value={range.start} onChange={(e) => setRange((r) => ({ ...r, start: e.target.value }))} aria-label="Report from" /></label>
              <label><span>To</span><input type="date" value={range.end} onChange={(e) => setRange((r) => ({ ...r, end: e.target.value }))} aria-label="Report to" /></label>
            </div>
          </section>
          <div className="gm-tiles">
            <div className="gm-tile"><span>Taken</span><b>{money(report.takings)}</b><small>after {money(report.refunds)} refunds</small></div>
            <div className="gm-tile"><span>Plans sold</span><b>{report.sold}</b><small>{report.renewals} renewals</small></div>
            <div className="gm-tile"><span>New members</span><b>{report.new_members}</b></div>
            <div className="gm-tile"><span>Visits</span><b>{report.visits}</b></div>
            <div className="gm-tile"><span>Active members now</span><b>{report.active_members}</b></div>
          </div>
          <section className="gm-box gm-scroll" aria-label="By plan">
            <Head title="By plan" />
            <table>
              <thead><tr><th>Plan</th><th>Sold</th><th>Total</th></tr></thead>
              <tbody>
                {report.by_plan.map((p: Row) => <tr key={p.name}><td>{p.name}</td><td>{p.sold}</td><td className="gm-num">{money(p.total)}</td></tr>)}
                {report.by_plan.length === 0 ? <tr><td colSpan={3} className="gm-muted">Nothing sold in these dates.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <section className="gm-box gm-scroll" aria-label="Ending in 30 days">
            <Head title="Ending in the next 30 days" />
            <table>
              <tbody>
                {report.expiring.map((e: Row) => <tr key={e.member_id}><td>{e.member_name}</td><td>{e.phone || '—'}</td><td>{e.plan_name}</td><td>{e.ends_on}</td></tr>)}
                {report.expiring.length === 0 ? <tr><td className="gm-muted">Nobody is due.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </div>
  );
}

export default function GymPage() {
  return (
    <Suspense fallback={<div className="gym"><p>Loading…</p></div>}>
      <GymDesk />
    </Suspense>
  );
}
