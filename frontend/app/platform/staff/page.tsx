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
  const [appUsers, setAppUsers] = useState<Staff[]>([]);
  const [roles, setRoles] = useState<RoleOpt[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [ready, setReady] = useState(false);
  const [form, setForm] = useState({
    email: '',
    full_name: '',
    password: '',
    role: 'platform_support',
    phone: '',
  });
  const [grantRole, setGrantRole] = useState('platform_support');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const me = await api('/me');
    if (!PLATFORM_ROLES.includes(me.data?.role)) {
      router.replace('/dashboard');
      return;
    }
    const [s, r, a] = await Promise.all([
      api('/platform/staff'),
      api('/platform/roles'),
      api('/platform/app-users'),
    ]);
    setStaff(s.data || []);
    setRoles((r.data || []).map((x: any) => ({ key: x.key, label: x.label })));
    setAppUsers(a.data || []);
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
        body: JSON.stringify({
          email: form.email.trim(),
          full_name: form.full_name.trim(),
          password: form.password,
          role: form.role,
          phone: form.phone.trim() || null,
        }),
      });
      setForm({ email: '', full_name: '', password: '', role: 'platform_support', phone: '' });
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

  async function grantAccess(row: Staff) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api('/platform/staff/grant', {
        method: 'POST',
        body: JSON.stringify({ user_id: row.id, role: grantRole }),
      });
      setMessage(`Granted software owner dashboard to ${row.full_name}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Grant failed');
    } finally {
      setBusy(false);
    }
  }

  async function revokeAccess(row: Staff) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api(`/platform/staff/${row.id}/revoke`, {
        method: 'POST',
        body: JSON.stringify({ fallback_role: 'company_admin' }),
      });
      setMessage(`Revoked dashboard access for ${row.full_name}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Revoke failed');
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
              Invite RIBDIGI staff, or grant an existing app user permission to open the software
              owner dashboard (platform console).
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
                aria-label="Platform staff full name"
                required
              />
            </label>
            <label>
              <span>Email</span>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                aria-label="Platform staff email"
                required
              />
            </label>
            <label>
              <span>Password</span>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                aria-label="Platform staff password"
                required
              />
            </label>
            <label>
              <span>Role</span>
              <select
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
                aria-label="Platform staff role"
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
            <label>
              <span>Phone</span>
              <input
                value={form.phone}
                onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                placeholder="Phone (E.164 e.g. +233...)"
                aria-label="Platform staff phone"
              />
            </label>
            <button type="submit" disabled={busy} aria-label="Create platform staff">
              {busy ? 'Saving…' : 'Create staff'}
            </button>
          </form>
        </div>

        <div className="plat-panel">
          <h2>App users → software owner dashboard</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            Workspace app users without platform roles. Grant a platform role so they land on the
            software owner console after login.
          </p>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
            <span>Grant as</span>
            <select value={grantRole} onChange={(e) => setGrantRole(e.target.value)} disabled={busy}>
              {roles
                .filter((r) => r.key !== 'super_admin')
                .map((r) => (
                  <option key={r.key} value={r.key}>
                    {r.label}
                  </option>
                ))}
            </select>
          </label>
          {appUsers.length === 0 ? (
            <p className="muted">No app users without dashboard access on this workspace.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Current role</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {appUsers.map((u) => (
                  <tr key={u.id}>
                    <td className="plat-co">{u.full_name}</td>
                    <td>{u.email}</td>
                    <td>
                      <code>{u.role}</code>
                    </td>
                    <td>
                      <button type="button" disabled={busy || u.is_active === false} onClick={() => grantAccess(u)}>
                        Grant dashboard
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
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
                        <button
                          type="button"
                          className="btn-ok"
                          disabled={busy}
                          onClick={() => setActive(u, true)}
                        >
                          Activate
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn-danger"
                          disabled={busy}
                          onClick={() => setActive(u, false)}
                        >
                          Deactivate
                        </button>
                      )}
                      {u.role !== 'super_admin' && (
                        <button type="button" disabled={busy} onClick={() => revokeAccess(u)}>
                          Revoke dashboard
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
