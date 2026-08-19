'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';
import { formatDateTime } from '../../../lib/format';
import { fetchHouseFormats, HOUSE_FORMAT_DEFAULTS } from '../../../lib/houseFormats';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

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
  last_invite_delivery?: {
    created_at?: string | null;
    sent?: boolean;
    mode?: string;
    error?: string | null;
    purpose?: string;
  } | null;
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

function PlatformUsersInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [items, setItems] = useState<PlatformUser[]>([]);
  const [sessions, setSessions] = useState<StaffSession[]>([]);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('platform_admin');
  const [busy, setBusy] = useState(false);
  const [formats, setFormats] = useState(HOUSE_FORMAT_DEFAULTS);
  // Stage 94 / Stage 108 U1 / Stage 115 O1 — shareable ?q=&role=&is_active= staff directory filters
  const [q, setQ] = useState(() => searchParams.get('q') || '');
  const [roleFilter, setRoleFilter] = useState(() => searchParams.get('role') || '');
  const [activeFilter, setActiveFilter] = useState(() => searchParams.get('is_active') || '');

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

  async function load(overrides?: { q?: string; role?: string; isActive?: string }) {
    setError('');
    const qf = overrides?.q !== undefined ? overrides.q : q;
    const rf = overrides?.role !== undefined ? overrides.role : roleFilter;
    const af = overrides?.isActive !== undefined ? overrides.isActive : activeFilter;
    try {
      const params = new URLSearchParams();
      if (qf.trim()) params.set('q', qf.trim());
      if (rf) params.set('role', rf);
      if (af === 'true' || af === 'false') params.set('is_active', af);
      const qs = params.toString();
      const r = await api(`/platform/users${qs ? `?${qs}` : ''}`);
      setItems(Array.isArray(r.data) ? r.data : r.data?.items || []);
      const s = await api('/platform/users/sessions');
      setSessions(s.data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load users');
    }
  }

  async function downloadPlatformCsv(path: string, filename: string) {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}${path}`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || `${filename} export failed`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || 'Export failed');
    }
  }

  useEffect(() => {
    fetchHouseFormats().then(setFormats);
  }, []);

  useEffect(() => {
    const fromQ = searchParams.get('q') || '';
    const fromRole = searchParams.get('role') || '';
    const fromActive = searchParams.get('is_active') || '';
    setQ(fromQ);
    setRoleFilter(fromRole);
    setActiveFilter(fromActive);
    load({ q: fromQ, role: fromRole, isActive: fromActive });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

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
        r.message ||
          (r.data?.invite_by_email
            ? r.data?.email_delivery?.sent
              ? `Invite email sent to ${r.data.email || email}`
              : `Invite email not sent (mode: ${r.data?.email_delivery?.mode || 'n/a'})`
            : 'Platform user created'),
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
      setMsg(
        r.message ||
          (r.data?.email_delivery?.sent
            ? `Password reset email sent to ${u.email}`
            : `Password reset email not sent (mode: ${r.data?.email_delivery?.mode || 'n/a'})`),
      );
      await load();
    } catch (err: any) {
      setError(err.message || 'Reset email failed');
    } finally {
      setBusy(false);
    }
  }

  async function revokeSession(s: StaffSession) {
    if (!window.confirm(`Revoke session for ${s.email}?`)) return;
    setBusy(true);
    setError('');
    setMsg('');
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

  const filtersActive = Boolean(q.trim() || roleFilter || activeFilter);

  return (
    <PlatformShell>
      <h1>Platform users</h1>
      <p className="muted">Ribdigi House staff on the reserved platform tenant only.</p>
      <p className="muted">
        Deactivate soft-disables login (ADR-003 — no hard delete in MVP; hard_delete_claimed:
        false). Export via <code>GET /platform/users/export</code> (Stage 149 U1) and{' '}
        <code>GET /platform/users/sessions/export</code> (Stage 149 S1; no refresh-token secrets / no
        jti).
      </p>
      {error && <p>{error}</p>}
      {msg && <p style={{ color: '#047857' }}>{msg}</p>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          syncUrl({ q, role: roleFilter, isActive: activeFilter });
          load();
        }}
        style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16, alignItems: 'center' }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name or email"
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1', minWidth: 200 }}
        />
        <select
          value={roleFilter}
          onChange={(e) => {
            const v = e.target.value;
            setRoleFilter(v);
            syncUrl({ role: v });
            load({ role: v });
          }}
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
        >
          <option value="">All roles</option>
          <option value="platform_admin">platform_admin</option>
          <option value="platform_super_admin">platform_super_admin</option>
        </select>
        <select
          value={activeFilter}
          onChange={(e) => {
            const v = e.target.value;
            setActiveFilter(v);
            syncUrl({ isActive: v });
            load({ isActive: v });
          }}
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
        >
          <option value="">All statuses</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
        <button type="submit" style={{ padding: '10px 14px', borderRadius: 8 }}>
          Apply
        </button>
        <button
          type="button"
          style={{ padding: '10px 14px', borderRadius: 8 }}
          onClick={() => {
            const params = new URLSearchParams();
            if (q.trim()) params.set('q', q.trim());
            if (roleFilter) params.set('role', roleFilter);
            if (activeFilter === 'true' || activeFilter === 'false') {
              params.set('is_active', activeFilter);
            }
            const qs = params.toString();
            downloadPlatformCsv(
              `/platform/users/export${qs ? `?${qs}` : ''}`,
              'platform_users_export.csv'
            );
          }}
        >
          Export users CSV
        </button>
      </form>

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
            <th>Last invite delivery</th>
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
              <td className="muted">
                {formatDateTime(u.last_session_at, formats.date_format, formats.time_format)}
              </td>
              <td>{u.active_session_count ?? 0}</td>
              <td className="muted" style={{ fontSize: 13 }}>
                {u.last_invite_delivery?.created_at
                  ? `${formatDateTime(
                      u.last_invite_delivery.created_at,
                      formats.date_format,
                      formats.time_format,
                    )} · sent=${String(u.last_invite_delivery.sent)} · mode=${
                      u.last_invite_delivery.mode || '—'
                    }${
                      u.last_invite_delivery.error
                        ? ` · error=${u.last_invite_delivery.error}`
                        : ''
                    }`
                  : '—'}
              </td>
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
              <td colSpan={9} className="muted">
                {filtersActive
                  ? 'No platform users match these filters.'
                  : 'No platform users yet. Use the bootstrap script or create one above.'}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <h2 style={{ fontSize: 16, marginTop: 32 }}>Active staff sessions</h2>
      <p className="muted">
        House operators can revoke platform staff AuthSessions. Export via{' '}
        <code>GET /platform/users/sessions/export</code> (Stage 149 S1).
      </p>
      <div style={{ marginBottom: 12 }}>
        <button
          type="button"
          onClick={() =>
            downloadPlatformCsv(
              '/platform/users/sessions/export',
              'platform_staff_sessions_export.csv'
            )
          }
        >
          Export sessions CSV
        </button>
      </div>
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
              <td className="muted">
                {formatDateTime(s.created_at, formats.date_format, formats.time_format)}
              </td>
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

export default function PlatformUsersPage() {
  return (
    <Suspense fallback={<main className="main"><p className="muted">Loading…</p></main>}>
      <PlatformUsersInner />
    </Suspense>
  );
}
