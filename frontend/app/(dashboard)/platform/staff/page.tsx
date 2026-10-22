'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import FormModal from '../../../../components/FormModal';
import PageHeader from '../../../../components/PageHeader';
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
  const [busy, setBusy] = useState(false);
  const [staffAddOpen, setStaffAddOpen] = useState(false);
  const [meRole, setMeRole] = useState('');
  const [grantUserId, setGrantUserId] = useState('');
  const [grantRole, setGrantRole] = useState('platform_support');
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
    const [me, s, r] = await Promise.all([
      getMe({ force }),
      getPrefetched('/platform/staff', { force }),
      getPrefetched('/platform/roles', { force }),
    ]);
    if (!PLATFORM_ROLES.includes(me.data?.role)) {
      router.replace('/dashboard');
      return;
    }
    setMeRole(me.data?.role || '');
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
    if (busy) return;
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
    const phone = form.phone.trim();
    if (phone && !/^\+[1-9]\d{7,14}$/.test(phone.replace(/[^\d+]/g, '').replace(/^00/, '+'))) {
      setError('Phone must be E.164 (e.g. +233241111111). Leave blank if you have no number.');
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
      setStaffAddOpen(false);
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
        <PageHeader
          className="plat-hero"
          kicker="Software owner"
          kickerClassName="plat-kicker"
          title="Platform staff"
          subtitle="Invite RIBDIGI staff who open the software owner dashboard."
          subtitleClassName="plat-sub"
        />

        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}
        {message && <p className="plat-msg">{message}</p>}

        <div style={{ marginBottom: 12 }}>
          <button type="button" className="list-btn-primary" onClick={() => setStaffAddOpen(true)} aria-label="Add staff user">
            Add staff user
          </button>
        </div>
        {staffAddOpen ? (
        <FormModal
          title="Add staff user"
          busy={busy}
          dirty={Boolean(form.full_name.trim() || form.email.trim() || form.password.trim())}
          onClose={() => setStaffAddOpen(false)}
        >
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
        </FormModal>
        ) : null}

        <div className="plat-panel">
          <h2>Staff directory</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            The platform owner can edit a staff account or set a new password. Leave the password
            blank when editing to keep the current one. Deactivate keeps the account signed out but
            listed.
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
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <form
          className="card"
          onSubmit={async (e) => {
            e.preventDefault();
            setError('');
            setMessage('');
            try {
              await api('/platform/staff/grant', {
                method: 'POST',
                body: JSON.stringify({ user_id: grantUserId.trim(), role: grantRole }),
              });
              setMessage('Dashboard access granted');
              await refresh({ force: true });
            } catch (err: any) {
              setError(err.message || 'Could not grant access');
            }
          }}
        >
          <h2>Grant as</h2>
          <select value={grantUserId} onChange={(e) => setGrantUserId(e.target.value)} aria-label="Grant access user">
            <option value="">Select user</option>
            {staff.map((u) => (
              <option key={u.id} value={u.id}>{u.full_name}</option>
            ))}
          </select>
          <select value={grantRole} onChange={(e) => setGrantRole(e.target.value)} aria-label="Platform grant role">
            {PLATFORM_ROLES.map((role) => (
              <option key={role} value={role}>{role}</option>
            ))}
          </select>
          <button type="submit">Grant as</button>
        </form>
      </div>
    </>
  );
}
