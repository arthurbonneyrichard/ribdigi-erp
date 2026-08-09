'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type RoleRow = { role: string; label: string };
type UserRow = {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  phone?: string | null;
};

const emptyForm = {
  email: '',
  full_name: '',
  password: '',
  role: 'cashier',
  phone: '',
};

export default function Page() {
  const [rows, setRows] = useState<UserRow[]>([]);
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [canWrite, setCanWrite] = useState(false);

  async function refresh() {
    const [usersRes, rolesRes, meRes] = await Promise.all([
      api('/users'),
      api('/roles'),
      api('/me'),
    ]);
    setRows(usersRes.data || []);
    setRoles(rolesRes.data || []);
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

  return (
    <Shell>
      <h1>User Management</h1>
      <p className="muted">Create users, assign system roles, and activate or deactivate accounts.</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

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
                </option>
              ))}
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
                      </option>
                    ))}
                  </select>
                ) : (
                  r.role
                )}
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
