'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Shell from '../../../components/Shell';
import { api } from '../../../lib/api';

type Staff = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active?: boolean;
  phone?: string | null;
};

type RoleOpt = { key: string; label: string };

const PLATFORM_ROLES = [
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
];

export default function PlatformStaffPage() {
  const router = useRouter();
  const [staff, setStaff] = useState<Staff[]>([]);
  const [roles, setRoles] = useState<RoleOpt[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [ready, setReady] = useState(false);
  const [form, setForm] = useState({
    email: '',
    full_name: '',
    password: '',
    role: 'platform_support',
  });
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const me = await api('/me');
    if (!PLATFORM_ROLES.includes(me.data?.role)) {
      router.replace('/dashboard');
      return;
    }
    const [s, r] = await Promise.all([api('/platform/staff'), api('/platform/roles')]);
    setStaff(s.data || []);
    setRoles((r.data || []).map((x: any) => ({ key: x.key, label: x.label })));
    setReady(true);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message || 'Failed to load staff'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function createStaff(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api('/platform/staff', {
        method: 'POST',
        body: JSON.stringify(form),
      });
      setForm({ email: '', full_name: '', password: '', role: 'platform_support' });
      setMessage('Staff user created');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Create failed');
    } finally {
      setBusy(false);
    }
  }

  async function setActive(row: Staff, is_active: boolean) {
    setBusy(true);
    setError('');
    try {
      await api(`/platform/staff/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active }),
      });
      setMessage(`${row.full_name} ${is_active ? 'activated' : 'deactivated'}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Update failed');
    } finally {
      setBusy(false);
    }
  }

  async function changeRole(row: Staff, role: string) {
    setBusy(true);
    setError('');
    try {
      await api(`/platform/staff/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      });
      setMessage(`Updated role for ${row.full_name}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Role update failed');
    } finally {
      setBusy(false);
    }
  }

  if (!ready && !error) {
    return (
      <Shell>
        <p className="muted">Loading platform staff…</p>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="plat">
        <header className="plat-hero">
          <div>
            <p className="plat-kicker">Software owner</p>
            <h1>Platform staff</h1>
            <p className="plat-sub">
              Invite RIBDIGI staff with roles (owner, admin, support, finance) so they can help
              manage tenants, packages, and reports.
            </p>
          </div>
        </header>

        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}
        {message && <p className="plat-msg">{message}</p>}

        <div className="plat-panel">
          <h2>Add staff user</h2>
          <form className="plat-form" onSubmit={createStaff}>
            <label>
              <span>Full name</span>
              <input
                value={form.full_name}
                onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                required
              />
            </label>
            <label>
              <span>Email</span>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                required
              />
            </label>
            <label>
              <span>Password</span>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                required
              />
            </label>
            <label>
              <span>Role</span>
              <select
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              >
                {roles
                  .filter((r) => r.key !== 'super_admin')
                  .map((r) => (
                    <option key={r.key} value={r.key}>
                      {r.label}
                    </option>
                  ))}
              </select>
            </label>
            <button type="submit" disabled={busy}>
              {busy ? 'Saving…' : 'Create staff'}
            </button>
          </form>
        </div>

        <div className="plat-panel">
          <h2>Staff directory</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {staff.map((u) => (
                <tr key={u.id}>
                  <td className="plat-co">{u.full_name}</td>
                  <td>{u.email}</td>
                  <td>
                    <select
                      value={u.role}
                      disabled={busy}
                      onChange={(e) => changeRole(u, e.target.value)}
                    >
                      {roles.map((r) => (
                        <option key={r.key} value={r.key}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>{u.is_active === false ? 'inactive' : 'active'}</td>
                  <td>
                    <div className="plat-actions">
                      {u.is_active === false ? (
                        <button type="button" disabled={busy} onClick={() => setActive(u, true)}>
                          Activate
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="danger"
                          disabled={busy}
                          onClick={() => setActive(u, false)}
                        >
                          Deactivate
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}
