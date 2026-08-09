'use client';

import { useEffect, useState } from 'react';
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

const MODULES = [
  'dashboard',
  'inventory',
  'sales',
  'pos',
  'purchasing',
  'expenses',
  'accounting',
  'credit',
  'tax',
  'stores',
  'reports',
  'notifications',
  'audit',
  'ai',
  'security',
  'users',
  'customers',
  'suppliers',
];

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

const emptyRoleForm = {
  slug: '',
  label: '',
  base_role: 'cashier',
  record_scope: 'own',
};

export default function Page() {
  const [rows, setRows] = useState<UserRow[]>([]);
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [roleForm, setRoleForm] = useState(emptyRoleForm);
  const [editRole, setEditRole] = useState<string>('');
  const [matrix, setMatrix] = useState<Record<string, string[]>>({});
  const [matrixScope, setMatrixScope] = useState('own');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [canWrite, setCanWrite] = useState(false);

  async function refresh() {
    const [usersRes, rolesRes, meRes, br, dep] = await Promise.all([
      api('/users'),
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
    refresh().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!editRole) return;
    const role = roles.find((r) => r.role === editRole);
    if (!role || role.system) return;
    setMatrix({ ...(role.permissions || {}) });
    setMatrixScope(role.record_scope || 'own');
  }, [editRole, roles]);

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

  async function createRole(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setMessage('');
    setBusy(true);
    try {
      await api('/roles', {
        method: 'POST',
        body: JSON.stringify({
          slug: roleForm.slug.trim().toLowerCase(),
          label: roleForm.label.trim(),
          base_role: roleForm.base_role,
          record_scope: roleForm.record_scope,
        }),
      });
      setRoleForm(emptyRoleForm);
      setMessage('Custom role created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveMatrix() {
    if (!editRole) return;
    setError('');
    setMessage('');
    try {
      await api(`/roles/${editRole}/permissions`, {
        method: 'PUT',
        body: JSON.stringify({ permissions: matrix, record_scope: matrixScope }),
      });
      setMessage('Role permissions updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function toggleAction(module: string, action: string) {
    setMatrix((prev) => {
      const current = new Set(prev[module] || []);
      if (current.has(action)) current.delete(action);
      else current.add(action);
      const next = { ...prev };
      if (current.size) next[module] = Array.from(current);
      else delete next[module];
      return next;
    });
  }

  async function deleteRole(slug: string) {
    setError('');
    setMessage('');
    try {
      await api(`/roles/${slug}`, { method: 'DELETE' });
      if (editRole === slug) setEditRole('');
      setMessage('Custom role deleted');
      await refresh();
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

  const systemBases = roles.filter((r) => r.system && r.role !== 'super_admin' && r.role !== 'company_admin');
  const customRoles = roles.filter((r) => !r.system);

  return (
    <Shell>
      <h1>User Management</h1>
      <p className="muted">
        Users, custom roles, org assignment, and module permission matrix.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      {canWrite && (
        <form onSubmit={createRole} style={{ margin: '20px 0', maxWidth: 520 }}>
          <h2 style={{ fontSize: 18 }}>Create custom role</h2>
          <input
            value={roleForm.slug}
            onChange={(e) => setRoleForm({ ...roleForm, slug: e.target.value })}
            placeholder="Slug (e.g. floor_lead)"
            required
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <input
            value={roleForm.label}
            onChange={(e) => setRoleForm({ ...roleForm, label: e.target.value })}
            placeholder="Label"
            required
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <select
            value={roleForm.base_role}
            onChange={(e) => setRoleForm({ ...roleForm, base_role: e.target.value })}
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          >
            {systemBases.map((r) => (
              <option key={r.role} value={r.role}>
                Copy permissions from {r.label}
              </option>
            ))}
          </select>
          <select
            value={roleForm.record_scope}
            onChange={(e) => setRoleForm({ ...roleForm, record_scope: e.target.value })}
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          >
            <option value="own">Record scope: own</option>
            <option value="department">Record scope: department</option>
            <option value="branch">Record scope: branch</option>
            <option value="all">Record scope: all</option>
          </select>
          <button type="submit" disabled={busy} style={{ padding: '10px 16px' }}>
            {busy ? 'Saving…' : 'Create role'}
          </button>
        </form>
      )}

      {customRoles.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 18 }}>Custom roles</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Slug</th>
                <th>Label</th>
                <th>Scope</th>
                {canWrite && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {customRoles.map((r) => (
                <tr key={r.role}>
                  <td>{r.role}</td>
                  <td>{r.label}</td>
                  <td>{r.record_scope || 'own'}</td>
                  {canWrite && (
                    <td style={{ display: 'flex', gap: 8 }}>
                      <button type="button" onClick={() => setEditRole(r.role)}>
                        Permissions
                      </button>
                      <button type="button" onClick={() => deleteRole(r.role)}>
                        Delete
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {canWrite && editRole && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 18 }}>Permission matrix · {editRole}</h2>
          <select
            value={matrixScope}
            onChange={(e) => setMatrixScope(e.target.value)}
            style={{ marginBottom: 12, padding: 8 }}
          >
            <option value="own">own</option>
            <option value="department">department</option>
            <option value="branch">branch</option>
            <option value="all">all</option>
          </select>
          <table className="table">
            <thead>
              <tr>
                <th>Module</th>
                <th>read</th>
                <th>write</th>
                <th>approve</th>
              </tr>
            </thead>
            <tbody>
              {MODULES.map((mod) => (
                <tr key={mod}>
                  <td>{mod}</td>
                  {(['read', 'write', 'approve'] as const).map((action) => (
                    <td key={action}>
                      <input
                        type="checkbox"
                        checked={(matrix[mod] || []).includes(action)}
                        onChange={() => toggleAction(mod, action)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button type="button" onClick={saveMatrix}>
              Save permissions
            </button>
            <button type="button" onClick={() => setEditRole('')}>
              Close
            </button>
          </div>
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
            <th>Org</th>
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
              <td className="muted">
                {[r.branch_id ? 'B' : null, r.department_id ? 'D' : null].filter(Boolean).join('/') || '—'}
              </td>
              <td>{r.is_active ? 'Yes' : 'No'}</td>
              {canWrite && (
                <td>
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
