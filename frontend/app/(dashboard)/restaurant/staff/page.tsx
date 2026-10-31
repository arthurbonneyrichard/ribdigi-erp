'use client';

/**
 * Restaurant staff: who works here, what each person can do, who is on the till now,
 * and the restaurant's departments (kitchen, bar, floor…). Uses the shared users and
 * departments engine; custom roles and CSV import stay on the full Staff and Permissions screen.
 */

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import { initials, problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Tab = 'people' | 'departments';

// What each role can do, in restaurant words. Order = how they are offered.
const ROLE_INFO: [string, string, string][] = [
  ['restaurant_waiter', 'Waiter', 'Takes orders and seats guests. Cannot take payment.'],
  ['restaurant_cashier', 'Restaurant Cashier', 'Takes orders and payment, runs the till shift and end of day.'],
  ['restaurant_kitchen', 'Kitchen', 'Kitchen screen, sold-out dishes and waste.'],
  ['restaurant_manager', 'Restaurant Manager', 'Everything in the restaurant: refunds, menu, stock, money and reports.'],
  ['accountant', 'Accountant', 'Money, expenses, tax and reports.'],
  ['company_admin', 'Owner / Admin', 'Everything, including adding staff and company settings.'],
];
const ROLE_LABEL: Record<string, string> = { ...Object.fromEntries(ROLE_INFO.map(([k, l]) => [k, l])), cashier: 'Cashier (older role)' };

const RESTAURANT_DEPARTMENTS: [string, string][] = [
  ['KITCHEN', 'Kitchen'],
  ['BAR', 'Bar'],
  ['FLOOR', 'Floor and service'],
  ['TILL', 'Till and cashiers'],
  ['DELIVERY', 'Delivery'],
  ['CLEANING', 'Cleaning'],
  ['MGMT', 'Management'],
];
const OFFICE_DEFAULTS = new Set(['ACCT', 'ADMIN', 'CS', 'FIN', 'HR', 'IT', 'INV', 'MKT', 'OPS', 'PROD', 'PURCH', 'SALES', 'WH']);

export default function RestaurantStaffPage() {
  const router = useRouter();
  const tab: Tab = useSearchParams().get('tab') === 'departments' ? 'departments' : 'people';
  const setTab = (next: Tab) => router.replace(next === 'people' ? '?' : `?tab=${next}`, { scroll: false });

  const [users, setUsers] = useState<Row[]>([]);
  const [roles, setRoles] = useState<Row[]>([]);
  const [departments, setDepartments] = useState<Row[]>([]);
  const [shifts, setShifts] = useState<Row[]>([]);
  const [showInactive, setShowInactive] = useState(false);
  const [settingUp, setSettingUp] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [sheet, setSheet] = useState<{ kind: 'person'; row?: Row } | { kind: 'department'; row?: Row } | null>(null);

  const load = useCallback(async () => {
    try {
      const [u, r, d, s] = await Promise.all([
        api('/users'),
        api('/roles').catch(() => ({ data: [] })),
        api('/departments'),
        api('/restaurant/till/shifts?limit=20').catch(() => ({ data: [] })),
      ]);
      setUsers(u?.data || []);
      setRoles(r?.data || []);
      setDepartments(d?.data || []);
      setShifts((s?.data || []).filter((x: Row) => x.status === 'open'));
      setError('');
    } catch (err) {
      setError(problem(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const roleKeys = useMemo(() => new Set(roles.map((r) => String(r.role || r.key))), [roles]);
  const roleLabel = (key: string) => ROLE_LABEL[key] || roles.find((r) => (r.role || r.key) === key)?.label || key;
  const deptName = (id: string) => departments.find((d) => d.id === id)?.name || '';
  const onShift = new Set(shifts.map((s) => s.user_id));
  const shown = users.filter((u) => (showInactive ? true : u.is_active !== false)).sort((a, b) => String(a.full_name).localeCompare(String(b.full_name)));
  const activeDepts = departments.filter((d) => d.is_active !== false);
  const missingDepts = RESTAURANT_DEPARTMENTS.filter(([code]) => !departments.some((d) => String(d.code).toUpperCase() === code && d.is_active !== false));
  const staffIn = (deptId: string) => users.filter((u) => u.department_id === deptId && u.is_active !== false).length;
  const officeLeftovers = activeDepts.filter((d) => OFFICE_DEFAULTS.has(String(d.code).toUpperCase()) && staffIn(d.id) === 0);

  async function done(message: string) {
    setSheet(null);
    setNotice(message);
    await load();
  }

  async function setUpDepartments() {
    setSettingUp(true);
    try {
      await Promise.all([
        ...missingDepts.map(([code, name]) => {
          const existing = departments.find((d) => String(d.code).toUpperCase() === code);
          return existing
            ? api(`/departments/${existing.id}`, { method: 'PATCH', body: JSON.stringify({ is_active: true }) })
            : api('/departments', { method: 'POST', body: JSON.stringify({ code, name }) });
        }),
        // Office departments nobody belongs to are hidden, not deleted.
        ...officeLeftovers.map((d) => api(`/departments/${d.id}`, { method: 'PATCH', body: JSON.stringify({ is_active: false }) })),
      ]);
      await done('Restaurant departments are set up');
    } catch (err) {
      setError(problem(err));
      await load();
    } finally {
      setSettingUp(false);
    }
  }

  async function toggleDepartment(d: Row) {
    try {
      await api(`/departments/${d.id}`, { method: 'PATCH', body: JSON.stringify({ is_active: d.is_active === false }) });
      await done(d.is_active === false ? `${d.name} is back` : `${d.name} hidden`);
    } catch (err) {
      setError(problem(err));
    }
  }

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Staff</h1>
          <p>Who works here and what each person can do. Everyone signs in with their own email and password.</p>
        </div>
        <div className="rd-head-actions">
          <Link className="rd-linkish" href="/users">Custom roles and import →</Link>
          {tab === 'people' ? (
            <button type="button" className="rd-primary" aria-label="Add a staff member" onClick={() => setSheet({ kind: 'person' })}>+ Staff</button>
          ) : (
            <button type="button" className="rd-primary" aria-label="Add a department" onClick={() => setSheet({ kind: 'department' })}>+ Department</button>
          )}
        </div>
      </header>

      <div className="rd-tabs" role="tablist" aria-label="Staff sections">
        <button type="button" role="tab" aria-selected={tab === 'people'} className={tab === 'people' ? 'on' : ''} onClick={() => setTab('people')}>
          People <small>{users.filter((u) => u.is_active !== false).length}</small>
        </button>
        <button type="button" role="tab" aria-selected={tab === 'departments'} className={tab === 'departments' ? 'on' : ''} onClick={() => setTab('departments')}>
          Departments <small>{activeDepts.length}</small>
        </button>
      </div>

      {notice ? <div className="rd-notice" role="status" onClick={() => setNotice('')}>{notice}</div> : null}
      {error ? <div className="rd-error" role="alert" onClick={() => setError('')}>{error}</div> : null}

      {tab === 'people' ? (
        <>
          {shifts.length ? (
            <div className="rd-close-status ok" role="status">
              <strong>On the till now: {shifts.map((s) => s.cashier || 'Someone').join(', ')}</strong>
            </div>
          ) : null}
          <div className="rd-staff-grid" aria-label="Staff">
            {shown.map((u) => (
              <button key={u.id} type="button" className={`rd-staff-card${u.is_active === false ? ' off' : ''}`} aria-label={`Open ${u.full_name}`} onClick={() => setSheet({ kind: 'person', row: u })}>
                <span className="rd-avatar">{initials(u.full_name)}</span>
                <span className="who">
                  <strong>{u.full_name}</strong>
                  <small>{u.email}</small>
                </span>
                <span className="role">{roleLabel(u.role)}</span>
                <span className="meta">
                  {u.department_id ? deptName(u.department_id) : 'No department'}
                  {onShift.has(u.id) ? <em className="rd-pill">On the till</em> : null}
                  {u.is_active === false ? <em className="rd-pill grey">Cannot sign in</em> : null}
                </span>
              </button>
            ))}
          </div>
          <label className="rd-check">
            <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} aria-label="Show staff who left" />
            <span>Show staff who left ({users.filter((u) => u.is_active === false).length})</span>
          </label>
          <section className="rd-panel">
            <div className="rd-panel-head">
              <h2>Who can do what</h2>
            </div>
            <ul className="rd-docs rd-sheet-list">
              {ROLE_INFO.filter(([key]) => roleKeys.has(key) || key === 'company_admin').map(([key, label, what]) => (
                <li key={key}>
                  <span><strong>{label}</strong></span>
                  <span>{what}</span>
                  <span />
                  <strong>{users.filter((u) => u.role === key && u.is_active !== false).length}</strong>
                </li>
              ))}
            </ul>
          </section>
        </>
      ) : (
        <>
          {missingDepts.length || officeLeftovers.length ? (
            <div className="rd-panel rd-needs rd-needs-inline">
              <span>
                <strong>Use restaurant departments?</strong>{' '}
                <span className="rd-hint-line">
                  {missingDepts.length ? `Adds ${missingDepts.map(([, n]) => n).join(', ')}.` : ''}
                  {officeLeftovers.length ? ` Hides ${officeLeftovers.length} office departments nobody is in (${officeLeftovers.map((d) => d.name).join(', ')}).` : ''}
                </span>
              </span>
              <button type="button" className="rd-primary" aria-label="Set up restaurant departments" disabled={settingUp} onClick={() => void setUpDepartments()}>
                {settingUp ? 'Setting up…' : 'Set them up'}
              </button>
            </div>
          ) : null}
          <div className="rd-list" aria-label="Departments">
            {departments
              .filter((d) => showInactive || d.is_active !== false)
              .sort((a, b) => Number(b.is_active !== false) - Number(a.is_active !== false) || String(a.name).localeCompare(String(b.name)))
              .map((d) => (
                <div key={d.id} className={`rd-stock-row${d.is_active === false ? ' muted' : ''}`}>
                  <div className="what">
                    <strong>{d.name}</strong>
                    <small>{users.filter((u) => u.department_id === d.id && u.is_active !== false).map((u) => u.full_name).join(', ') || 'Nobody yet'}</small>
                  </div>
                  <div className="onhand">
                    <strong>{staffIn(d.id)}</strong>
                    <small>staff</small>
                  </div>
                  <span className={`rd-pill ${d.is_active === false ? 'grey' : ''}`}>{d.is_active === false ? 'Hidden' : 'In use'}</span>
                  <div className="acts">
                    <button type="button" aria-label={`Rename ${d.name}`} onClick={() => setSheet({ kind: 'department', row: d })}>Rename</button>
                    <button type="button" aria-label={`${d.is_active === false ? 'Show' : 'Hide'} ${d.name}`} onClick={() => void toggleDepartment(d)}>
                      {d.is_active === false ? 'Show' : 'Hide'}
                    </button>
                  </div>
                </div>
              ))}
          </div>
          <label className="rd-check">
            <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} aria-label="Show hidden departments" />
            <span>Show hidden departments</span>
          </label>
        </>
      )}

      {sheet?.kind === 'person' ? (
        <PersonSheet
          row={sheet.row}
          roleKeys={roleKeys}
          roleLabel={roleLabel}
          departments={activeDepts}
          onClose={() => setSheet(null)}
          onDone={done}
        />
      ) : null}
      {sheet?.kind === 'department' ? <DepartmentSheet row={sheet.row} taken={departments.map((d) => String(d.code).toUpperCase())} onClose={() => setSheet(null)} onDone={done} /> : null}
    </div>
  );
}

function PersonSheet({
  row,
  roleKeys,
  roleLabel,
  departments,
  onClose,
  onDone,
}: {
  row?: Row;
  roleKeys: Set<string>;
  roleLabel: (key: string) => string;
  departments: Row[];
  onClose: () => void;
  onDone: (m: string) => Promise<void>;
}) {
  const [name, setName] = useState(String(row?.full_name || ''));
  const [email, setEmail] = useState(String(row?.email || ''));
  const [phone, setPhone] = useState(String(row?.phone || ''));
  const [role, setRole] = useState(String(row?.role || 'restaurant_waiter'));
  const [dept, setDept] = useState(String(row?.department_id || ''));
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const offered = ROLE_INFO.filter(([key]) => roleKeys.has(key));
  const extra = row && !offered.some(([key]) => key === row.role) ? [[row.role, roleLabel(row.role), 'Current role'] as [string, string, string]] : [];

  async function save() {
    if (!name.trim()) return setError('Enter their name.');
    if (!row && !email.trim()) return setError('Enter their email; they sign in with it.');
    if (!row && password.trim().length < 8) return setError('Give them a first password of at least 8 characters, with a number and a symbol.');
    const cleanPhone = phone.replace(/[\s-]/g, '');
    if (cleanPhone && !/^\+\d{8,15}$/.test(cleanPhone)) return setError('Phone needs the country code, like +233 24 123 4567.');
    setBusy(true);
    setError('');
    try {
      if (row) {
        const body: Row = { full_name: name.trim(), role };
        if (cleanPhone) body.phone = cleanPhone;
        if (dept) body.department_id = dept;
        else if (row.department_id) body.clear_department = true;
        if (password.trim()) body.password = password.trim();
        await api(`/users/${row.id}`, { method: 'PATCH', body: JSON.stringify(body) });
        await onDone(`${name.trim()} saved`);
      } else {
        await api('/users', {
          method: 'POST',
          body: JSON.stringify({
            full_name: name.trim(),
            email: email.trim(),
            password: password.trim(),
            role,
            phone: cleanPhone || null,
            department_id: dept || null,
          }),
        });
        await onDone(`${name.trim()} added. They can sign in now.`);
      }
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  async function setActive(active: boolean) {
    if (!row) return;
    setBusy(true);
    setError('');
    try {
      if (active) await api(`/users/${row.id}`, { method: 'PATCH', body: JSON.stringify({ is_active: true }) });
      else await api(`/users/${row.id}`, { method: 'DELETE' });
      await onDone(active ? `${row.full_name} can sign in again` : `${row.full_name} can no longer sign in. Their history stays.`);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={row ? `Edit ${row.full_name}` : 'New staff member'} onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>{row ? row.full_name : 'New staff member'}</h2>
            <p>{row ? row.email : 'They sign in with this email and the first password you give them.'}</p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        <div className="rd-form-grid">
          <label className="rd-span">
            <span>Name</span>
            <input aria-label="Staff name" value={name} onChange={(e) => setName(e.target.value)} autoFocus={!row} />
          </label>
          {!row ? (
            <label>
              <span>Email</span>
              <input aria-label="Staff email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
          ) : null}
          <label>
            <span>Phone (optional)</span>
            <input aria-label="Staff phone" placeholder="+233 24 123 4567" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
        </div>
        <span className="rd-field-label">What they do</span>
        <div className="rd-role-pick" role="radiogroup" aria-label="Staff role">
          {[...offered, ...extra].map(([key, label, what]) => (
            <button key={key} type="button" role="radio" aria-checked={role === key} className={role === key ? 'on' : ''} onClick={() => setRole(key)}>
              <strong>{label}</strong>
              <small>{what}</small>
            </button>
          ))}
        </div>
        <div className="rd-form-grid">
          <label>
            <span>Department</span>
            <select aria-label="Staff department" value={dept} onChange={(e) => setDept(e.target.value)}>
              <option value="">None</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>{row ? 'New password (optional)' : 'First password'}</span>
            <input aria-label={row ? 'New password' : 'First password'} type="text" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
        </div>
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          {row ? (
            row.is_active === false ? (
              <button type="button" aria-label="Let them sign in again" disabled={busy} onClick={() => void setActive(true)}>Let them sign in again</button>
            ) : row.role === 'company_admin' ? (
              <button type="button" onClick={onClose}>Cancel</button>
            ) : (
              <button type="button" className="rd-danger" aria-label="Stop them signing in" disabled={busy} onClick={() => void setActive(false)}>They left: stop sign-in</button>
            )
          ) : (
            <button type="button" onClick={onClose}>Cancel</button>
          )}
          <button type="button" className="rd-primary" aria-label="Save staff member" disabled={busy} onClick={() => void save()}>
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </aside>
    </div>
  );
}

function DepartmentSheet({ row, taken, onClose, onDone }: { row?: Row; taken: string[]; onClose: () => void; onDone: (m: string) => Promise<void> }) {
  const [name, setName] = useState(String(row?.name || ''));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  function codeFor(text: string) {
    const base = text.toUpperCase().replace(/[^A-Z0-9]+/g, '').slice(0, 10) || 'DEPT';
    let code = base;
    for (let i = 2; taken.includes(code); i += 1) code = `${base.slice(0, 8)}${i}`;
    return code;
  }

  async function save() {
    if (name.trim().length < 2) return setError('Name the department.');
    setBusy(true);
    setError('');
    try {
      if (row) await api(`/departments/${row.id}`, { method: 'PATCH', body: JSON.stringify({ name: name.trim() }) });
      else await api('/departments', { method: 'POST', body: JSON.stringify({ code: codeFor(name), name: name.trim() }) });
      await onDone(`${name.trim()} saved`);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={row ? `Rename ${row.name}` : 'New department'} onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>{row ? `Rename ${row.name}` : 'New department'}</h2>
            <p>Group staff, like Kitchen, Bar or Floor.</p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        <div className="rd-form-grid">
          <label className="rd-span">
            <span>Name</span>
            <input aria-label="Department name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </label>
        </div>
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="rd-primary" aria-label="Save department" disabled={busy} onClick={() => void save()}>
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </aside>
    </div>
  );
}
