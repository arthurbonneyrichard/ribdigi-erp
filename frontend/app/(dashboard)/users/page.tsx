'use client';

import { useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';

type RoleRow = {
  role: string;
  label: string;
  system?: boolean;
  base_role?: string | null;
  record_scope?: string;
  is_active?: boolean;
};
type BranchRow = { id: string; code: string; name: string; is_active?: boolean };
type DepartmentRow = {
  id: string;
  code: string;
  name: string;
  branch_id?: string | null;
  is_active?: boolean;
};
type StoreRow = { id: string; code: string; name: string; is_active?: boolean };
type UserRow = {
  id: string;
  full_name: string;
  email: string;
  role: string;
  email_verified?: boolean;
  is_active: boolean;
  phone?: string | null;
  branch_id?: string | null;
  department_id?: string | null;
  record_scope?: string | null;
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

const RECORD_SCOPES = [
  { value: '', label: 'Default for role' },
  { value: 'own', label: 'Own records' },
  { value: 'department', label: 'Department' },
  { value: 'branch', label: 'Branch' },
  { value: 'all', label: 'All records' },
];

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const PLATFORM_USER_ROLES = new Set([
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
]);

/** Roles that may create/edit tenant staff. Matches backend users:write for these principals. */
const USER_ADMIN_ROLES = new Set([
  'company_admin',
  'tenant_admin',
  'tenant_owner',
  'super_admin',
  'platform_owner',
  'platform_admin',
]);

function moduleActions(perms: Record<string, string[]> | undefined, module: string): string[] {
  const raw = perms?.[module] as unknown;
  if (Array.isArray(raw)) return raw;
  if (typeof raw === 'string') return [raw];
  return [];
}

/** Align with POST /users (require_permission users:write). Accept users:create as the same grant. */
function canWriteUsers(role: string, perms: Record<string, string[]> | undefined): boolean {
  if (USER_ADMIN_ROLES.has(role)) return true;
  if (moduleActions(perms, '*').includes('*')) return true;
  const actions = moduleActions(perms, 'users');
  return actions.includes('write') || actions.includes('create') || actions.includes('*');
}

type ImportReportRow = {
  line: number;
  email: string;
  full_name: string;
  role: string;
  ok: boolean;
  errors: string[];
};

type ImportReport = {
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  can_commit: boolean;
  imported?: number;
  rows: ImportReportRow[];
};

export default function Page() {
  const [rows, setRows] = useState<UserRow[]>([]);
  const [userManageFilter, setUserManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [roleManageFilter, setRoleManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [branches, setBranches] = useState<BranchRow[]>([]);
  const [departments, setDepartments] = useState<DepartmentRow[]>([]);
  const [stores, setStores] = useState<StoreRow[]>([]);
  const [userStoreIds, setUserStoreIds] = useState<Record<string, string[]>>({});
  const [form, setForm] = useState(emptyForm);
  const [roleForm, setRoleForm] = useState({
    key: '',
    label: '',
    base_role: 'inventory_officer',
  });
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [canWrite, setCanWrite] = useState(false);
  const [permChecked, setPermChecked] = useState(false);
  const [meRole, setMeRole] = useState('');
  const [meId, setMeId] = useState('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importReport, setImportReport] = useState<ImportReport | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [userQuery, setUserQuery] = useState('');
  const [deptFilter, setDeptFilter] = useState('');

  async function refresh() {
    const meRes = await getMe();
    const perms = (meRes.data?.permissions || {}) as Record<string, string[]>;
    const role = meRes.data?.role || '';
    setMeId(String(meRes.data?.id || '').trim());
    setMeRole(role);
    setCanWrite(canWriteUsers(role, perms));
    setPermChecked(true);

    const [usersRes, rolesRes, branchesRes, deptsRes, storesRes] = await Promise.all([
      api('/users'),
      // Manage list needs inactive custom roles for Activate / Deactivate (BR-3.2).
      api('/roles?include_inactive=true'),
      api('/branches').catch(() => ({ data: [] })),
      api('/departments').catch(() => ({ data: [] })),
      api('/stores').catch(() => ({ data: [] })),
    ]);
    const listed: UserRow[] = usersRes.data || [];
    const hidePlatform = !PLATFORM_USER_ROLES.has(role);
    setRows(hidePlatform ? listed.filter((u) => !PLATFORM_USER_ROLES.has(u.role)) : listed);
    setRoles(rolesRes.data || []);
    setBranches(branchesRes.data || []);
    setDepartments(deptsRes.data || []);
    setStores((storesRes.data || []).filter((s: StoreRow) => s.is_active !== false));
    const users: UserRow[] = hidePlatform
      ? listed.filter((u) => !PLATFORM_USER_ROLES.has(u.role))
      : listed;
    const membershipEntries = await Promise.all(
      users.map(async (u) => {
        try {
          const r = await api(`/users/${u.id}/stores`);
          return [u.id, r.data?.store_ids || []] as const;
        } catch {
          return [u.id, []] as const;
        }
      })
    );
    setUserStoreIds(Object.fromEntries(membershipEntries));
  }

  const isCustomRole = (r: RoleRow) => r.system === false;
  const isRoleActive = (r: RoleRow) => !isCustomRole(r) || r.is_active !== false;
  const assignableRoles = (currentRole?: string) =>
    roles.filter(
      (r) =>
        !PLATFORM_USER_ROLES.has(r.role) &&
        (isRoleActive(r) || (currentRole != null && r.role === currentRole)),
    );

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  const branchLabel = (id?: string | null) => {
    if (!id) return '—';
    const b = branches.find((x) => x.id === id);
    return b ? `${b.code} — ${b.name}` : id.slice(0, 8);
  };

  const deptLabel = (id?: string | null) => {
    if (!id) return '—';
    const d = departments.find((x) => x.id === id);
    return d ? `${d.code} — ${d.name}` : id.slice(0, 8);
  };

  const activeBranches = branches.filter((b) => b.is_active !== false);
  const managedUsers = rows.filter((r) => {
    if (userManageFilter === 'all') {
      /* keep */
    } else {
      const active = r.is_active !== false;
      if (userManageFilter === 'inactive' ? active : !active) return false;
    }
    if (deptFilter && r.department_id !== deptFilter) return false;
    const needle = userQuery.trim().toLowerCase();
    if (needle) {
      const hay = `${r.full_name} ${r.email} ${deptLabel(r.department_id)}`.toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  });
  const managedCustomRoles = roles.filter((r) => {
    if (!isCustomRole(r)) return false;
    if (roleManageFilter === 'all') return true;
    const active = r.is_active !== false;
    return roleManageFilter === 'inactive' ? !active : active;
  });
  const activeDepartments = (branchId?: string) =>
    departments.filter(
      (d) =>
        d.is_active !== false && (!branchId || !d.branch_id || d.branch_id === branchId),
    );

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    const fullName = form.full_name.trim();
    if (!fullName) {
      setError('User full name is required.');
      setMessage('');
      return;
    }
    const trimmedPassword = form.password.trim();
    if (!trimmedPassword) {
      setError('User password is required.');
      setMessage('');
      return;
    }
    setError('');
    setMessage('');
    setBusy(true);
    try {
      await api('/users', {
        method: 'POST',
        body: JSON.stringify({
          email: form.email.trim(),
          full_name: fullName,
          password: trimmedPassword,
          role: form.role,
          phone: form.phone.trim() || null,
          branch_id: form.branch_id.trim() || null,
          department_id: form.department_id.trim() || null,
          record_scope: form.record_scope || null,
        }),
      });
      setForm(emptyForm);
      setMessage('User created. They can sign in with this workspace.');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function createCustomRole(e: React.FormEvent) {
    e.preventDefault();
    const label = roleForm.label.trim();
    if (!label) {
      setError('Custom role label is required.');
      setMessage('');
      return;
    }
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const r = await api('/roles', {
        method: 'POST',
        body: JSON.stringify({
          key: roleForm.key.trim(),
          label,
          base_role: roleForm.base_role || null,
        }),
      });
      setRoleForm({ key: '', label: '', base_role: 'inventory_officer' });
      setMessage(`Custom role ${r.data?.role || roleForm.key} created`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteCustomRole(role: string) {
    setError('');
    setMessage('');
    try {
      await api(`/roles/${role}`, { method: 'DELETE' });
      setMessage(`Deleted role ${role}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setCustomRoleActive(role: string, is_active: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/roles/${role}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active }),
      });
      setMessage(is_active ? `Activated role ${role}` : `Deactivated role ${role}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function patchUser(userId: string, body: Record<string, unknown>, okMsg: string) {
    setError('');
    setMessage('');
    try {
      await api(`/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      setMessage(okMsg);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setRole(userId: string, role: string) {
    await patchUser(userId, { role }, 'Role updated');
  }

  async function setBranch(userId: string, branchId: string) {
    const trimmed = branchId.trim();
    await patchUser(
      userId,
      trimmed
        ? { branch_id: trimmed }
        : { clear_branch: true, clear_department: true },
      'Branch assignment updated',
    );
  }

  async function setDepartment(userId: string, departmentId: string) {
    const trimmed = departmentId.trim();
    await patchUser(
      userId,
      trimmed ? { department_id: trimmed } : { clear_department: true },
      'Department assignment updated',
    );
  }

  async function setRecordScope(userId: string, scope: string) {
    await patchUser(
      userId,
      { record_scope: scope || 'own' },
      'Record scope updated',
    );
  }

  async function setUserStores(userId: string, storeIds: string[]) {
    setError('');
    setMessage('');
    try {
      await api(`/users/${userId}/stores`, {
        method: 'PUT',
        body: JSON.stringify({ store_ids: storeIds }),
      });
      setUserStoreIds((prev) => ({ ...prev, [userId]: storeIds }));
      setMessage(
        storeIds.length
          ? `Store access limited to ${storeIds.length} store(s)`
          : 'Store access cleared (all stores)'
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function allowSignIn(userId: string, email: string) {
    setError('');
    setMessage('');
    try {
      await api(`/users/${userId}/confirm-email`, { method: 'POST', body: '{}' });
      setMessage(`${email} can sign in now.`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not enable sign-in');
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

  async function deleteUser(row: UserRow) {
    if (meId && row.id === meId) {
      setError('You cannot delete your own account.');
      setMessage('');
      return;
    }
    const ok = window.confirm(
      `Delete ${row.full_name} (${row.email}) permanently?\n\nThis removes the staff account. This cannot be undone.`
    );
    if (!ok) return;
    setError('');
    setMessage('');
    try {
      await api(`/users/${String(row.id).trim()}/account`, { method: 'DELETE' });
      setMessage(`Deleted ${row.full_name}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Delete failed');
    }
  }

  async function downloadImportTemplate() {
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
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Template download failed');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'users-import-template.csv';
      a.click();
      URL.revokeObjectURL(url);
      setMessage('CSV template downloaded');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function runUserImport(dryRun: boolean) {
    if (!importFile) {
      setError('Choose a CSV file first');
      return;
    }
    setError('');
    setMessage('');
    setImportBusy(true);
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const formData = new FormData();
      formData.append('file', importFile);
      const res = await fetch(`${apiBase}/users/import?dry_run=${dryRun ? 'true' : 'false'}`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body: formData,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = body.detail;
        if (detail && typeof detail === 'object' && detail.report) {
          setImportReport(detail.report);
          throw new Error(detail.message || 'Import validation failed');
        }
        throw new Error(
          typeof detail === 'string'
            ? detail
            : detail?.message || body.message || 'Import failed'
        );
      }
      setImportReport(body.data as ImportReport);
      if (dryRun) {
        setMessage(
          body.data?.can_commit
            ? `Validation OK — ${body.data.valid_rows} user(s) ready to import`
            : `Validation found ${body.data?.error_rows || 0} error row(s)`
        );
      } else {
        setMessage(`Imported ${body.data?.imported || 0} user(s)`);
        setImportFile(null);
        await refresh();
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setImportBusy(false);
    }
  }

  return (
    <>
      <div className="users-page-head">
        <div>
          <h1>User Management</h1>
          <p className="muted" style={{ margin: '8px 0 0' }}>
            Create users, assign roles, branch/department, and record scope; activate, deactivate, or
            permanently delete staff accounts (BR-3.1). Soft-deactivate custom roles without deleting
            assignees (BR-3.2). Deactivate keeps the account; Delete removes it.
          </p>
        </div>
        {canWrite ? (
          <a className="users-add-btn" href="#create-user" aria-label="Add User">
            Add User
          </a>
        ) : null}
      </div>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: 'var(--brand, #4AB012)' }}>{message}</p>}
      {permChecked && !canWrite ? (
        <div className="card users-perm-msg" role="status" style={{ margin: '12px 0' }}>
          <p style={{ margin: 0 }}>
            You can view users in this company, but you cannot create or edit them.
            Creating users requires <code>users:write</code> (Company Admin). Your role is{' '}
            <strong>{meRole || 'unknown'}</strong>. Cashiers and other read-only roles cannot
            create users from this page, by URL, or via the API.
          </p>
        </div>
      ) : null}

      {canWrite && (
        <form
          id="create-user"
          onSubmit={createUser}
          className="card users-create-card"
          style={{ margin: '20px 0', display: 'grid', gap: 8 }}
        >
          <h2 style={{ fontSize: 18, margin: 0 }}>Create User</h2>
          <input
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder="Full name"
            aria-label="User full name"
            required
          />
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="Email"
            aria-label="User email"
            required
          />
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Temporary password"
            aria-label="User password"
            required
          />
          <input
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="Phone (optional, E.164 e.g. +233...)"
            aria-label="User phone"
          />
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            aria-label="User role"
          >
            {assignableRoles().map((r) => (
              <option key={r.role} value={r.role}>
                {r.label}
                {isCustomRole(r) ? ' (custom)' : ''}
              </option>
            ))}
          </select>
          <select
            value={form.branch_id}
            onChange={(e) =>
              setForm({ ...form, branch_id: e.target.value, department_id: '' })
            }
            aria-label="User branch"
            title="Optional branch assignment (UuidIdValue)"
          >
            <option value="">Branch (optional)</option>
            {activeBranches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.code} — {b.name}
              </option>
            ))}
          </select>
          <select
            value={form.department_id}
            onChange={(e) => setForm({ ...form, department_id: e.target.value })}
            aria-label="User department"
            title="Optional department assignment (UuidIdValue)"
          >
            <option value="">Department (optional)</option>
            {activeDepartments(form.branch_id).map((d) => (
              <option key={d.id} value={d.id}>
                {d.code} — {d.name}
              </option>
            ))}
          </select>
          <select
            value={form.record_scope}
            onChange={(e) => setForm({ ...form, record_scope: e.target.value })}
            aria-label="User record scope"
          >
            {RECORD_SCOPES.map((s) => (
              <option key={s.value || 'default'} value={s.value}>
                Record scope: {s.label}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={busy || !form.full_name.trim() || !form.password.trim()}
            aria-label="Create user"
          >
            {busy ? 'Creating…' : 'Create User'}
          </button>
        </form>
      )}

      {canWrite && (
        <form onSubmit={createCustomRole} className="card" style={{ margin: '20px 0', display: 'grid', gap: 8 }}>
          <h2 style={{ fontSize: 18, margin: 0 }}>Custom roles</h2>
          <p className="muted" style={{ margin: 0 }}>
            Clone a system role&apos;s permissions into a tenant-specific role key, then assign it to
            users. Soft-deactivate with <strong>Deactivate</strong> (keeps assignees; blocks new
            assignment). Delete is blocked while any user still has the role. System roles stay
            immutable.
          </p>
          <input
            value={roleForm.key}
            onChange={(e) => setRoleForm({ ...roleForm, key: e.target.value })}
            placeholder="Role key (e.g. warehouse_lead)"
            required
            aria-label="Custom role key"
          />
          <input
            value={roleForm.label}
            onChange={(e) => setRoleForm({ ...roleForm, label: e.target.value })}
            placeholder="Display label"
            required
            aria-label="Custom role label"
          />
          <select
            value={roleForm.base_role}
            onChange={(e) => setRoleForm({ ...roleForm, base_role: e.target.value })}
            aria-label="Clone from system role"
          >
            {roles
              .filter((r) => !isCustomRole(r) && !PLATFORM_USER_ROLES.has(r.role))
              .map((r) => (
                <option key={r.role} value={r.role}>
                  Clone from {r.label}
                </option>
              ))}
          </select>
          <button type="submit" disabled={busy || !roleForm.key.trim() || !roleForm.label.trim()} aria-label="Create custom role">
            {busy ? 'Saving…' : 'Create custom role'}
          </button>
          <select
            value={roleManageFilter}
            onChange={(e) =>
              setRoleManageFilter(e.target.value as 'all' | 'active' | 'inactive')
            }
            title="Filter manage custom role list by status"
            aria-label="Custom role status filter"
          >
            <option value="all">All statuses</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {managedCustomRoles.map((r) => (
              <li key={r.role}>
                {r.label} <code>{r.role}</code>
                {r.is_active === false ? (
                  <span className="muted" style={{ marginLeft: 6 }}>
                    [inactive]
                  </span>
                ) : null}
                {r.is_active === false ? (
                  <button
                    type="button"
                    className="btn-ok"
                    style={{ marginLeft: 8 }}
                    onClick={() => setCustomRoleActive(r.role, true)}
                   aria-label={`Activate custom role ${r.role}`}>
                    Activate
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-danger"
                    style={{ marginLeft: 8 }}
                    onClick={() => setCustomRoleActive(r.role, false)}
                   aria-label={`Deactivate custom role ${r.role}`}>
                    Deactivate
                  </button>
                )}
                <button
                  type="button"
                  style={{ marginLeft: 8 }}
                  onClick={() => deleteCustomRole(r.role)}
                 aria-label={`Delete custom role ${r.role}`}>
                  Delete
                </button>
              </li>
            ))}
            {!managedCustomRoles.length && (
              <li className="muted">No custom roles for this filter</li>
            )}
          </ul>
        </form>
      )}

      {canWrite && (
        <div className="card" style={{ margin: '20px 0', display: 'grid', gap: 12 }}>
          <h2 style={{ fontSize: 18, margin: 0 }}>Bulk import users</h2>
          <p className="muted" style={{ margin: 0 }}>
            Download the CSV template, fill rows (role must be a system role; temporary password must
            meet policy), validate, then import. Import is all-or-nothing.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" onClick={downloadImportTemplate} aria-label="Download user CSV template">
              Download CSV template
            </button>
          </div>
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label="User CSV import file"
            onChange={(e) => {
              setImportFile(e.target.files?.[0] || null);
              setImportReport(null);
            }}
          />
          {importFile && <p className="muted">Selected: {importFile.name}</p>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => runUserImport(true)}
              disabled={!importFile || importBusy}
              aria-label="Validate user CSV import"
            >
              {importBusy ? 'Working…' : 'Validate'}
            </button>
            <button
              type="button"
              onClick={() => runUserImport(false)}
              disabled={!importFile || importBusy || !importReport?.can_commit}
              aria-label="Import valid user CSV rows"
            >
              Import valid rows
            </button>
          </div>
          {importReport && (
            <div>
              <p className="muted">
                {importReport.total_rows} rows · {importReport.valid_rows} valid ·{' '}
                {importReport.error_rows} errors
                {importReport.imported != null ? ` · imported ${importReport.imported}` : ''}
              </p>
              <table className="table">
                <thead>
                  <tr>
                    <th>Line</th>
                    <th>Email</th>
                    <th>Name</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Errors</th>
                  </tr>
                </thead>
                <tbody>
                  {importReport.rows.map((r) => (
                    <tr key={`${r.line}-${r.email}`}>
                      <td>{r.line}</td>
                      <td>{r.email || '—'}</td>
                      <td>{r.full_name || '—'}</td>
                      <td>{r.role || '—'}</td>
                      <td style={{ color: r.ok ? 'var(--brand, #4AB012)' : '#b91c1c' }}>{r.ok ? 'OK' : 'Error'}</td>
                      <td>{r.errors?.length ? r.errors.join('; ') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <select
        value={userManageFilter}
        onChange={(e) => setUserManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
        title="Filter manage user list by status"
        aria-label="User status filter"
        style={{ marginBottom: 8 }}
      >
        <option value="all">All statuses</option>
        <option value="active">Active only</option>
        <option value="inactive">Inactive only</option>
      </select>
      <input
        value={userQuery}
        onChange={(e) => setUserQuery(e.target.value)}
        placeholder="Search name, email, department"
        aria-label="Search users"
        style={{ marginLeft: 8, marginBottom: 8 }}
      />
      <select
        value={deptFilter}
        onChange={(e) => setDeptFilter(e.target.value)}
        aria-label="Filter users by department"
        style={{ marginLeft: 8, marginBottom: 8 }}
      >
        <option value="">All departments</option>
        {departments.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </select>

      <table className="table">
        <thead>
          <tr>
            <th>Full Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Branch</th>
            <th>Department</th>
            <th>Scope</th>
            <th>Stores</th>
            <th>Active</th>
            {canWrite && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {managedUsers.length === 0 && (
            <tr>
              <td colSpan={canWrite ? 9 : 8} className="muted">
                {rows.length ? 'No users for this filter' : 'No users yet'}
              </td>
            </tr>
          )}
          {managedUsers.map((r) => (
            <tr key={r.id}>
              <td>
                {r.full_name}
                {r.is_active === false ? (
                  <span className="muted" style={{ marginLeft: 6, fontSize: 12 }}>
                    [inactive]
                  </span>
                ) : null}
              </td>
              <td>{r.email}</td>
              <td>
                {canWrite ? (
                  <select
                    value={r.role}
                    onChange={(e) => setRole(r.id, e.target.value)}
                    aria-label={`Change role for ${r.email}`}
                  >
                    {assignableRoles(r.role).map((role) => (
                      <option key={role.role} value={role.role}>
                        {role.label}
                        {isCustomRole(role) ? ' (custom)' : ''}
                        {role.is_active === false ? ' [inactive]' : ''}
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
                    onChange={(e) => setBranch(r.id, e.target.value)}
                    aria-label={`Edit user branch for ${r.email}`}
                  >
                    <option value="">None</option>
                    {activeBranches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.code}
                      </option>
                    ))}
                  </select>
                ) : (
                  branchLabel(r.branch_id)
                )}
              </td>
              <td>
                {canWrite ? (
                  <select
                    value={r.department_id || ''}
                    onChange={(e) => setDepartment(r.id, e.target.value)}
                    aria-label={`Edit user department for ${r.email}`}
                  >
                    <option value="">None</option>
                    {activeDepartments(r.branch_id || undefined).map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.code}
                      </option>
                    ))}
                  </select>
                ) : (
                  deptLabel(r.department_id)
                )}
              </td>
              <td>
                {canWrite ? (
                  <select
                    value={r.record_scope || 'own'}
                    onChange={(e) => setRecordScope(r.id, e.target.value)}
                    aria-label={`Edit user record scope for ${r.email}`}
                  >
                    {RECORD_SCOPES.filter((s) => s.value).map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  r.record_scope || '—'
                )}
              </td>
              <td>
                {canWrite && !PLATFORM_USER_ROLES.has(r.role) && r.role !== 'company_admin' ? (
                  <select
                    multiple
                    value={userStoreIds[r.id] || []}
                    onChange={(e) => {
                      const selected = Array.from(e.target.selectedOptions).map((o) => o.value);
                      setUserStores(r.id, selected);
                    }}
                    aria-label={`Assign stores for ${r.email}`}
                    title="Empty = all stores. Select one or more to restrict POS/store access."
                    style={{ minWidth: 140, minHeight: 64 }}
                  >
                    {stores.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.code} — {s.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="muted">
                    {r.role === 'company_admin' || PLATFORM_USER_ROLES.has(r.role)
                      ? 'All stores'
                      : (userStoreIds[r.id] || []).length
                        ? `${(userStoreIds[r.id] || []).length} assigned`
                        : 'All stores'}
                  </span>
                )}
              </td>
              <td>{r.is_active ? 'Yes' : 'No'}</td>
              {canWrite && (
                <td>
                  {r.email_verified === false ? (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => allowSignIn(r.id, r.email)}
                      aria-label={`Allow sign-in for ${r.email}`}
                    >
                      Allow sign-in
                    </button>
                  ) : null}
                  {r.is_active ? (
                    <button type="button" className="btn-danger" onClick={() => setActive(r.id, false)} aria-label={`Deactivate user ${r.id}`}>
                      Deactivate
                    </button>
                  ) : (
                    <button type="button" className="btn-ok" onClick={() => setActive(r.id, true)} aria-label={`Activate user ${r.id}`}>
                      Activate
                    </button>
                  )}
                  {r.id !== meId ? (
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={() => deleteUser(r)}
                      aria-label={`Delete user ${r.email}`}
                    >
                      Delete
                    </button>
                  ) : null}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
