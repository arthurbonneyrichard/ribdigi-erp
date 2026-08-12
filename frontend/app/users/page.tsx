'use client';

import { Suspense, useEffect, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type RoleRow = {
  role: string;
  label: string;
  system?: boolean;
  permissions?: Record<string, string[]>;
  record_scope?: string;
};

type UserRow = {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  phone?: string | null;
  branch_id?: string | null;
  department_id?: string | null;
  record_scope?: string;
};


const emptyForm = {
  email: '',
  full_name: '',
  password: '',
  role: 'cashier',
  phone: '',
  branch_id: '',
  department_id: '',
  record_scope: '',
};


function PageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [rows, setRows] = useState<UserRow[]>([]);
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [canWrite, setCanWrite] = useState(false);
  const [importReport, setImportReport] = useState<any>(null);
  const [q, setQ] = useState(() => searchParams.get('q') || '');
  const [roleFilter, setRoleFilter] = useState(() => searchParams.get('role') || '');
  const [activeFilter, setActiveFilter] = useState(() => searchParams.get('is_active') || '');
  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  function syncUrl(next: { q?: string; role?: string; isActive?: string }) {
    const params = new URLSearchParams();
    const nq = next.q !== undefined ? next.q : q;
    const nr = next.role !== undefined ? next.role : roleFilter;
    const na = next.isActive !== undefined ? next.isActive : activeFilter;
    if (nq.trim()) params.set('q', nq.trim());
    if (nr) params.set('role', nr);
    if (na) params.set('is_active', na);
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  }

  async function refresh(overrides?: { q?: string; role?: string; isActive?: string }) {
    const qf = overrides?.q !== undefined ? overrides.q : q;
    const rf = overrides?.role !== undefined ? overrides.role : roleFilter;
    const af = overrides?.isActive !== undefined ? overrides.isActive : activeFilter;
    const params = new URLSearchParams();
    if (qf.trim()) params.set('q', qf.trim());
    if (rf) params.set('role', rf);
    if (af === 'true' || af === 'false') params.set('is_active', af);
    const qs = params.toString();
    const [usersRes, rolesRes, meRes, br, dep] = await Promise.all([
      api(`/users${qs ? `?${qs}` : ''}`),
      api('/roles'),
      api('/me'),
      api('/branches').catch(() => ({ data: [] })),
      api('/departments').catch(() => ({ data: [] })),
    ]);
    setRows(usersRes.data || []);
    setRoles(rolesRes.data || []);
    setBranches(br.data || []);
    setDepartments(dep.data || []);
    const perms = meRes.data?.permissions || {};
    const role = meRes.data?.role || '';
    setCanWrite(
      role === 'super_admin' ||
        role === 'company_admin' ||
        perms?.['*']?.includes('*') ||
        (perms.users || []).includes('write') ||
        (perms.users || []).includes('*')
    );
  }

  useEffect(() => {
    const fromQ = searchParams.get('q') || '';
    const fromRole = searchParams.get('role') || '';
    const fromActive = searchParams.get('is_active') || '';
    setQ(fromQ);
    setRoleFilter(fromRole);
    setActiveFilter(fromActive);
    refresh({ q: fromQ, role: fromRole, isActive: fromActive }).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);


  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setMessage('');
    setBusy(true);
    try {
      await api('/users', {
        method: 'POST',
        body: JSON.stringify({
          email: form.email,
          full_name: form.full_name,
          password: form.password,
          role: form.role,
          phone: form.phone || null,
          branch_id: form.branch_id || null,
          department_id: form.department_id || null,
          record_scope: form.record_scope || null,
        }),
      });
      setForm(emptyForm);
      setMessage('User created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function downloadUserImportTemplate() {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/users/import/template`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) throw new Error('Template download failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'user_import_template.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function importUsersCsv(file: File, dryRun: boolean) {
    setError('');
    setMessage('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const body = new FormData();
      body.append('file', file);
      const res = await fetch(`${apiBase}/users/import?dry_run=${dryRun}`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body,
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json.detail || json.message || 'Import failed');
      setImportReport(json.data);
      setMessage(json.message || (dryRun ? 'Dry-run complete' : 'Import complete'));
      if (!dryRun) await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setRole(userId: string, role: string) {
    setError('');
    setMessage('');
    try {
      await api(`/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      });
      setMessage('Role updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setActive(userId: string, is_active: boolean) {
    setError('');
    setMessage('');
    try {
      if (is_active) {
        await api(`/users/${userId}`, {
          method: 'PATCH',
          body: JSON.stringify({ is_active: true }),
        });
        setMessage('User activated');
      } else {
        await api(`/users/${userId}`, { method: 'DELETE' });
        setMessage('User deactivated');
      }
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function resetPassword(userId: string, email: string) {
    setError('');
    setMessage('');
    const password = window.prompt(
      `Set a temporary password for ${email} (min 8 chars, must meet policy):`
    );
    if (!password) return;
    try {
      await api(`/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ password }),
      });
      setMessage('Password reset — sessions revoked');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function emailPasswordReset(userId: string, email: string) {
    setError('');
    setMessage('');
    if (!window.confirm(`Send a password reset email to ${email}?`)) return;
    try {
      const r = await api(`/users/${userId}/password-reset-email`, {
        method: 'POST',
        body: '{}',
      });
      const sent = r.data?.email_delivery?.sent;
      setMessage(
        sent
          ? `Reset email sent to ${email}`
          : `Reset token issued for ${email} (email mode: ${r.data?.email_delivery?.mode || 'n/a'})`,
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setOrg(userId: string, patch: { branch_id?: string | null; department_id?: string | null; clear_branch?: boolean; clear_department?: boolean }) {
    setError('');
    setMessage('');
    try {
      await api(`/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      });
      setMessage('Org assignment updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <Shell>
      <h1>Users</h1>
      <p className="muted">
        Tenant user lifecycle, password reset, and branch/department assignment. Manage custom
        roles at Admin → Roles and permission matrices at Admin → Permissions. Deactivate
        soft-disables login (ADR-003 — no hard delete / permanent erasure in MVP;
        hard_delete_claimed: false).
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          syncUrl({ q, role: roleFilter, isActive: activeFilter });
          refresh().catch((err) => setError(err.message));
        }}
        style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '16px 0', alignItems: 'center' }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name or email"
          style={{ padding: 10, minWidth: 200 }}
        />
        <select
          value={roleFilter}
          onChange={(e) => {
            const v = e.target.value;
            setRoleFilter(v);
            syncUrl({ role: v });
            refresh({ role: v }).catch((err) => setError(err.message));
          }}
          style={{ padding: 10 }}
          aria-label="Role filter"
        >
          <option value="">All roles</option>
          {roles.map((r) => (
            <option key={r.role} value={r.role}>
              {r.label}
            </option>
          ))}
        </select>
        <select
          value={activeFilter}
          onChange={(e) => {
            const v = e.target.value;
            setActiveFilter(v);
            syncUrl({ isActive: v });
            refresh({ isActive: v }).catch((err) => setError(err.message));
          }}
          style={{ padding: 10 }}
          aria-label="Active filter"
        >
          <option value="">All statuses</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
        <button type="submit">Apply</button>
      </form>

      {canWrite && (
        <div className="card" style={{ margin: '20px 0', maxWidth: 640 }}>
          <h2 style={{ fontSize: 18 }}>Bulk CSV import</h2>
          <p className="muted">
            Columns: full_name, email, phone, role, branch_code, department_code, password
            (optional), record_scope.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <button type="button" onClick={downloadUserImportTemplate}>
              Download template
            </button>
            <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              Dry-run
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) importUsersCsv(f, true);
                  e.target.value = '';
                }}
              />
            </label>
            <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              Commit
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) importUsersCsv(f, false);
                  e.target.value = '';
                }}
              />
            </label>
          </div>
          {importReport && (
            <p className="muted">
              Rows {importReport.total_rows} · valid {importReport.valid_rows} · errors{' '}
              {importReport.error_rows}
              {importReport.errors?.length
                ? ` · first error: ${(importReport.errors[0].errors || []).join('; ')}`
                : ''}
            </p>
          )}
        </div>
      )}

      {canWrite && (
        <form onSubmit={createUser} style={{ margin: '20px 0', maxWidth: 520 }}>
          <h2 style={{ fontSize: 18 }}>Create user</h2>
          <input
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder="Full name"
            required
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="Email"
            required
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Temporary password"
            required
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <input
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="Phone (optional)"
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          >
            {roles
              .filter((r) => r.role !== 'super_admin')
              .map((r) => (
                <option key={r.role} value={r.role}>
                  {r.label}
                  {r.system ? '' : ' (custom)'}
                </option>
              ))}
          </select>
          <select
            value={form.branch_id}
            onChange={(e) => setForm({ ...form, branch_id: e.target.value })}
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          >
            <option value="">No branch</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <select
            value={form.department_id}
            onChange={(e) => setForm({ ...form, department_id: e.target.value })}
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          >
            <option value="">No department</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
          <select
            value={form.record_scope}
            onChange={(e) => setForm({ ...form, record_scope: e.target.value })}
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          >
            <option value="">Default role record scope</option>
            <option value="own">own</option>
            <option value="department">department</option>
            <option value="branch">branch</option>
            <option value="all">all</option>
          </select>
          <button type="submit" disabled={busy} style={{ padding: '10px 16px' }}>
            {busy ? 'Creating…' : 'Create user'}
          </button>
        </form>
      )}

      <table className="table">
        <thead>
          <tr>
            <th>Full Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Branch</th>
            <th>Department</th>
            <th>Active</th>
            {canWrite && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.full_name}</td>
              <td>{r.email}</td>
              <td>
                {canWrite ? (
                  <select value={r.role} onChange={(e) => setRole(r.id, e.target.value)}>
                    {roles.map((role) => (
                      <option key={role.role} value={role.role}>
                        {role.label}
                        {role.system ? '' : ' (custom)'}
                      </option>
                    ))}
                  </select>
                ) : (
                  r.role
                )}
              </td>
              <td>
                {canWrite ? (
                  <select
                    value={r.branch_id || ''}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (!v) setOrg(r.id, { clear_branch: true, clear_department: true });
                      else setOrg(r.id, { branch_id: v });
                    }}
                  >
                    <option value="">—</option>
                    {branches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="muted">{r.branch_id ? 'B' : '—'}</span>
                )}
              </td>
              <td>
                {canWrite ? (
                  <select
                    value={r.department_id || ''}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (!v) setOrg(r.id, { clear_department: true });
                      else setOrg(r.id, { department_id: v });
                    }}
                  >
                    <option value="">—</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="muted">{r.department_id ? 'D' : '—'}</span>
                )}
              </td>
              <td>{r.is_active ? 'Yes' : 'No'}</td>
              {canWrite && (
                <td style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button type="button" onClick={() => resetPassword(r.id, r.email)}>
                    Set temp password
                  </button>
                  <button type="button" onClick={() => emailPasswordReset(r.id, r.email)}>
                    Email reset link
                  </button>
                  {r.is_active ? (
                    <button type="button" onClick={() => setActive(r.id, false)}>
                      Deactivate
                    </button>
                  ) : (
                    <button type="button" onClick={() => setActive(r.id, true)}>
                      Activate
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<main className="main"><p className="muted">Loading…</p></main>}>
      <PageInner />
    </Suspense>
  );
}
