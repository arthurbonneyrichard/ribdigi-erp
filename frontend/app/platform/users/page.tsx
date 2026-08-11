'use client';

import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';

type PlatformUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  email_verified?: boolean;
  totp_enabled?: boolean;
  last_session_at?: string | null;
  active_session_count?: number;
};

type StaffSession = {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  ip_address?: string;
  user_agent?: string;
  created_at?: string;
  current?: boolean;
};

export default function PlatformUsersPage() {
  const [items, setItems] = useState<PlatformUser[]>([]);
  const [sessions, setSessions] = useState<StaffSession[]>([]);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('platform_admin');
  const [busy, setBusy] = useState(false);

  async function load() {
    setError('');
    try {
      const r = await api('/platform/users');
      setItems(r.data || []);
      const s = await api('/platform/users/sessions');
      setSessions(s.data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load users');
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setMsg('');
    try {
      const body: Record<string, string> = {
        email,
        full_name: fullName,
        role,
      };
      if (password.trim()) body.password = password.trim();
      const r = await api('/platform/users', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setEmail('');
      setFullName('');
      setPassword('');
      setMsg(
        r.data?.invite_by_email
          ? `Invite email issued for ${r.data.email || email}`
          : 'Platform user created',
      );
      await load();
    } catch (err: any) {
      setError(err.message || 'Create failed');
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(u: PlatformUser) {
    setBusy(true);
    setError('');
    try {
      await api(`/platform/users/${u.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !u.is_active }),
      });
      await load();
    } catch (err: any) {
      setError(err.message || 'Update failed');
    } finally {
      setBusy(false);
    }
  }

  async function emailPasswordReset(u: PlatformUser) {
    if (!window.confirm(`Send a password reset email to ${u.email}?`)) return;
    setBusy(true);
    setError('');
    setMsg('');
    try {
      const r = await api(`/platform/users/${u.id}/password-reset-email`, {
        method: 'POST',
        body: '{}',
      });
      const sent = r.data?.email_delivery?.sent;
      setMsg(
        sent
          ? `Reset email sent to ${u.email}`
          : `Reset token issued for ${u.email} (email mode: ${r.data?.email_delivery?.mode || 'n/a'})`,
      );
    } catch (err: any) {
      setError(err.message || 'Email reset failed');
    } finally {
      setBusy(false);
    }
  }

  async function revokeSession(s: StaffSession) {
    if (s.current) {
      if (!window.confirm('Revoke your current session? You may be signed out.')) return;
    }
    setBusy(true);
    setError('');
    try {
      await api(`/platform/users/sessions/${s.id}`, { method: 'DELETE' });
      setMsg('Session revoked');
      await load();
    } catch (err: any) {
      setError(err.message || 'Revoke failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <PlatformShell>
      <h1>Platform users</h1>
      <p className="muted">Ribdigi House staff on the reserved platform tenant only.</p>
      <p className="muted">
        Deactivate soft-disables login (ADR-003 — no hard delete in MVP; hard_delete_claimed:
        false).
      </p>
      {error && <p>{error}</p>}
      {msg && <p style={{ color: '#047857' }}>{msg}</p>}

      <form onSubmit={createUser} className="card" style={{ marginTop: 16, maxWidth: 480 }}>
        <h2 style={{ fontSize: 16, marginTop: 0 }}>Invite platform user</h2>
        <p className="muted">
          Requires platform_super_admin. Leave password blank to send a set-password email invite.
        </p>
        <input
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Full name"
          required
          style={{ width: '100%', padding: 10, margin: '6px 0', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          type="email"
          required
          style={{ width: '100%', padding: 10, margin: '6px 0', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Temporary password (optional)"
          type="password"
          style={{ width: '100%', padding: 10, margin: '6px 0', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          style={{ width: '100%', padding: 10, margin: '6px 0', borderRadius: 8, border: '1px solid #cbd5e1' }}
        >
          <option value="platform_admin">platform_admin</option>
          <option value="platform_super_admin">platform_super_admin</option>
        </select>
        <button
          type="submit"
          disabled={busy}
          style={{ padding: '10px 14px', borderRadius: 8, background: '#111827', color: '#fff', border: 0 }}
        >
          {password.trim() ? 'Create' : 'Invite by email'}
        </button>
      </form>

      <table className="table" style={{ marginTop: 24 }}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Active</th>
            <th>2FA</th>
            <th>Last session</th>
            <th>Active sessions</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((u) => (
            <tr key={u.id}>
              <td>{u.full_name}</td>
              <td>{u.email}</td>
              <td>
                <span className="badge">{u.role}</span>
              </td>
              <td>{u.is_active ? 'yes' : 'no'}</td>
              <td>{u.totp_enabled ? 'yes' : 'no'}</td>
              <td className="muted">{u.last_session_at || '—'}</td>
              <td>{u.active_session_count ?? 0}</td>
              <td style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" disabled={busy} onClick={() => emailPasswordReset(u)}>
                  Email reset link
                </button>
                <button type="button" disabled={busy} onClick={() => toggleActive(u)}>
                  {u.is_active ? 'Deactivate' : 'Activate'}
                </button>
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={8} className="muted">
                No platform users yet. Use the bootstrap script or create one above.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <h2 style={{ fontSize: 16, marginTop: 32 }}>Active staff sessions</h2>
      <p className="muted">House operators can revoke platform staff AuthSessions.</p>
      <table className="table">
        <thead>
          <tr>
            <th>User</th>
            <th>IP</th>
            <th>Created</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.id}>
              <td>
                {s.full_name} ({s.email}){s.current ? ' · current' : ''}
              </td>
              <td>{s.ip_address || '—'}</td>
              <td>{s.created_at || '—'}</td>
              <td>
                <button type="button" disabled={busy} onClick={() => revokeSession(s)}>
                  Revoke
                </button>
              </td>
            </tr>
          ))}
          {sessions.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                No active platform staff sessions.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </PlatformShell>
  );
}
