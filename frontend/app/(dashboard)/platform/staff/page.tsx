'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '../../../../lib/api';
import { getMe } from '../../../../lib/meCache';
import { getPrefetched } from '../../../../lib/prefetchCache';

type Staff = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active?: boolean;
  phone?: string | null;
  email_verified?: boolean;
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
  const [meRole, setMeRole] = useState('');
  const [meId, setMeId] = useState('');
  const [editingId, setEditingId] = useState('');
  const [editForm, setEditForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    role: 'platform_support',
    password: '',
  });

  const canEditStaff = meRole === 'platform_owner' || meRole === 'super_admin';

  async function refresh(options?: { force?: boolean }) {
    const force = Boolean(options?.force);
    const [me, s, r, a] = await Promise.all([
      getMe({ force }),
      getPrefetched('/platform/staff', { force }),
      getPrefetched('/platform/roles', { force }),
      getPrefetched('/platform/app-users', { force }),
    ]);
    if (!PLATFORM_ROLES.includes(me.data?.role)) {
      router.replace('/dashboard');
      return;
    }
    setMeRole(me.data?.role || '');
    setMeId(String(me.data?.id || '').trim());
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
    const fullName = form.full_name.trim();
    const trimmedPassword = form.password.trim();
    if (!fullName) {
      setError('Platform staff full name is required.');
      setMessage('');
      return;
    }
    if (!trimmedPassword) {
      setError('Platform staff password is required.');
      setMessage('');
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const r = await api('/platform/staff', {
        method: 'POST',
        body: JSON.stringify({
          email: form.email.trim(),
          full_name: fullName,
          password: trimmedPassword,
          role: form.role,
          phone: form.phone.trim() || null,
        }),
      });
      setForm({ email: '', full_name: '', password: '', role: 'platform_support', phone: '' });
      const sent = Boolean(r.data?.verification_email?.sent);
      setMessage(
        sent
          ? 'Staff user created. They must open the verification email before signing in with workspace "platform".'
          : 'Staff user created, but the verification email was not sent. Use Resend email after SMTP is on, or Verify account.'
      );
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message || 'Create failed');
    } finally {
      setBusy(false);
    }
  }

  function openEdit(row: Staff) {
    setEditingId(row.id);
    setEditForm({
      full_name: row.full_name || '',
      email: row.email || '',
      phone: row.phone || '',
      role: row.role,
      password: '',
    });
    setError('');
    setMessage('');
  }

  async function saveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editingId) return;
    const fullName = editForm.full_name.trim();
    const email = editForm.email.trim();
    const password = editForm.password.trim();
    if (!fullName) {
      setError('Staff full name is required.');
      setMessage('');
      return;
    }
    if (!email) {
      setError('Staff email is required.');
      setMessage('');
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const body: Record<string, string> = {
        full_name: fullName,
        email,
        role: editForm.role,
      };
      const phone = editForm.phone.trim();
      if (phone) body.phone = phone;
      if (password) body.password = password;
      await api(`/platform/staff/${editingId.trim()}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      setEditingId('');
      setEditForm({ full_name: '', email: '', phone: '', role: 'platform_support', password: '' });
      setMessage(password ? 'Staff user and password updated' : 'Staff user updated');
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message || 'Update failed');
    } finally {
      setBusy(false);
    }
  }

  async function verifyStaff(row: Staff) {
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const r = await api(`/platform/staff/${row.id}/verify-email`, { method: 'POST', body: '{}' });
      setMessage(r.message || `${row.email} can sign in.`);
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message || 'Could not verify this account');
    } finally {
      setBusy(false);
    }
  }

  async function resendStaffEmail(row: Staff) {
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const r = await api(`/platform/staff/${row.id}/resend-verification`, {
        method: 'POST',
        body: '{}',
      });
      setMessage(r.message || `Verification email sent to ${row.email}.`);
    } catch (err: any) {
      setError(err.message || 'Could not resend the verification email');
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
      await refresh({ force: true });
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
      await refresh({ force: true });
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
        // trim so Grant dashboard (UuidIdValue user_id) does not 422 on whitespace
        body: JSON.stringify({ user_id: String(row.id).trim(), role: grantRole }),
      });
      setMessage(`Granted software owner dashboard to ${row.full_name}`);
      await refresh({ force: true });
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
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message || 'Revoke failed');
    } finally {
      setBusy(false);
    }
  }

  async function deleteStaff(row: Staff) {
    if (meId && row.id === meId) {
      setError('You cannot delete your own account.');
      setMessage('');
      return;
    }
    const ok = window.confirm(
      `Delete ${row.full_name} (${row.email}) permanently?\n\nThis removes the account from the staff directory. This cannot be undone.`
    );
    if (!ok) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api(`/platform/staff/${String(row.id).trim()}`, { method: 'DELETE' });
      if (editingId === row.id) setEditingId('');
      setMessage(`Deleted ${row.full_name}`);
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message || 'Delete failed');
    } finally {
      setBusy(false);
    }
  }

  if (!ready && !error) {
    return (
      <>
        <p className="muted">Loading platform staff…</p>
      </>
    );
  }

  return (
    <>
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
            <button
              type="submit"
              disabled={busy || !form.full_name.trim() || !form.password.trim()}
              aria-label="Create platform staff"
            >
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
            <select
              value={grantRole}
              onChange={(e) => setGrantRole(e.target.value)}
              disabled={busy}
              aria-label="Platform grant role"
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
                      <button
                        type="button"
                        disabled={busy || u.is_active === false}
                        onClick={() => grantAccess(u)}
                        aria-label="Grant dashboard"
                      >
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
          <p className="muted" style={{ marginTop: 0 }}>
            The platform owner can edit a staff account, set a new password, or delete the account.
            Leave the password blank when editing to keep the current one. Deactivate keeps the
            account; Delete removes it permanently.
          </p>
          {canEditStaff && editingId ? (
            <form className="plat-form" onSubmit={saveEdit} style={{ marginBottom: 16 }}>
              <h3 style={{ margin: '0 0 4px', fontSize: 16 }}>Edit staff</h3>
              <label>
                <span>Full name</span>
                <input
                  value={editForm.full_name}
                  onChange={(e) => setEditForm((f) => ({ ...f, full_name: e.target.value }))}
                  aria-label="Edit platform staff full name"
                  required
                />
              </label>
              <label>
                <span>Email</span>
                <input
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                  aria-label="Edit platform staff email"
                  required
                />
              </label>
              <label>
                <span>New password</span>
                <input
                  type="password"
                  value={editForm.password}
                  onChange={(e) => setEditForm((f) => ({ ...f, password: e.target.value }))}
                  placeholder="Leave blank to keep current password"
                  aria-label="Edit platform staff password"
                  autoComplete="new-password"
                />
              </label>
              <label>
                <span>Role</span>
                <select
                  value={editForm.role}
                  onChange={(e) => setEditForm((f) => ({ ...f, role: e.target.value }))}
                  aria-label="Edit platform staff role"
                >
                  {roles
                    .filter((r) => r.key !== 'super_admin' || editForm.role === 'super_admin')
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
                  value={editForm.phone}
                  onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
                  placeholder="Phone (E.164 e.g. +233...). Leave blank to keep current."
                  aria-label="Edit platform staff phone"
                />
              </label>
              <div className="plat-actions">
                <button type="submit" disabled={busy || !editForm.full_name.trim()} aria-label="Save platform staff">
                  {busy ? 'Saving…' : 'Save staff'}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setEditingId('')}
                  aria-label="Cancel platform staff edit"
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : null}
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
                      aria-label={`Change platform staff role for ${u.email}`}
                    >
                      {roles.map((r) => (
                        <option key={r.key} value={r.key}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    {u.is_active === false ? 'inactive' : 'active'}
                    {u.email_verified === false ? ' · unverified' : ''}
                  </td>
                  <td>
                    <div className="plat-actions">
                      {canEditStaff && u.email_verified === false && (
                        <>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => resendStaffEmail(u)}
                            aria-label={`Resend verification email for ${u.email}`}
                          >
                            Resend email
                          </button>
                          <button
                            type="button"
                            className="btn-ok"
                            disabled={busy}
                            onClick={() => verifyStaff(u)}
                            aria-label={`Verify account for ${u.email}`}
                          >
                            Verify account
                          </button>
                        </>
                      )}
                      {canEditStaff && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => openEdit(u)}
                          aria-label={`Edit platform staff ${u.email}`}
                        >
                          Edit
                        </button>
                      )}
                      {u.is_active === false ? (
                        <button
                          type="button"
                          className="btn-ok"
                          disabled={busy}
                          onClick={() => setActive(u, true)}
                          aria-label={`Activate platform staff ${u.id}`}
                        >
                          Activate
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn-danger"
                          disabled={busy}
                          onClick={() => setActive(u, false)}
                          aria-label={`Deactivate platform staff ${u.id}`}
                        >
                          Deactivate
                        </button>
                      )}
                      {u.role !== 'super_admin' && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => revokeAccess(u)}
                          aria-label={`Revoke dashboard access ${u.id}`}
                        >
                          Revoke dashboard
                        </button>
                      )}
                      {canEditStaff && u.id !== meId && (
                        <button
                          type="button"
                          className="btn-danger"
                          disabled={busy}
                          onClick={() => deleteStaff(u)}
                          aria-label={`Delete platform staff ${u.email}`}
                        >
                          Delete
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
    </>
  );
}
