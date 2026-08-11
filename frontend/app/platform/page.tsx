'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type TenantRow = {
  id: string;
  slug: string;
  company_name: string;
  industry?: string;
  currency?: string;
  status: string;
  email?: string | null;
  phone?: string | null;
  days_remaining?: number | null;
  trial_ends_at?: string | null;
  grace_ends_at?: string | null;
  suspended_reason?: string | null;
  created_at?: string | null;
};

function statusClass(status: string) {
  if (status === 'active') return 'st-active';
  if (status === 'trial') return 'st-trial';
  if (status === 'grace') return 'st-grace';
  if (status === 'suspended') return 'st-suspended';
  return '';
}

function fmtDate(value?: string | null) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return value;
  }
}

export default function PlatformConsole() {
  const router = useRouter();
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [filter, setFilter] = useState('all');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  async function refresh() {
    const me = await api('/me');
    if (me.data?.role !== 'super_admin') {
      router.replace('/dashboard');
      return;
    }
    const q = filter === 'all' ? '' : `?status=${encodeURIComponent(filter)}`;
    const res = await api(`/tenants${q}`);
    setTenants(res.data || []);
    setReady(true);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message || 'Failed to load platform console'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const stats = useMemo(() => {
    const all = tenants;
    const count = (s: string) => all.filter((t) => t.status === s).length;
    return {
      total: all.length,
      active: count('active'),
      trial: count('trial'),
      grace: count('grace'),
      suspended: count('suspended'),
    };
  }, [tenants]);

  async function suspendTenant(row: TenantRow) {
    const reason = window.prompt(`Suspend ${row.company_name}? Optional reason:`, '') ?? null;
    if (reason === null) return;
    setBusy(row.id);
    setError('');
    setMessage('');
    try {
      await api(`/tenants/${row.slug || row.id}/suspend`, {
        method: 'POST',
        body: JSON.stringify({ reason: reason || null }),
      });
      setMessage(`Suspended ${row.company_name}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Suspend failed');
    } finally {
      setBusy(null);
    }
  }

  async function activateTenant(row: TenantRow) {
    if (!window.confirm(`Activate ${row.company_name}?`)) return;
    setBusy(row.id);
    setError('');
    setMessage('');
    try {
      await api(`/tenants/${row.slug || row.id}/activate`, { method: 'POST', body: '{}' });
      setMessage(`Activated ${row.company_name}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Activate failed');
    } finally {
      setBusy(null);
    }
  }

  if (!ready && !error) {
    return (
      <Shell>
        <p className="muted">Loading platform console…</p>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="plat">
        <header className="plat-hero">
          <div>
            <p className="plat-kicker">Software owner</p>
            <h1>Platform console</h1>
            <p className="plat-sub">Tenant lifecycle across RIBDIGI ERP — activate, monitor, and suspend workspaces.</p>
          </div>
          <div className="plat-filters">
            {['all', 'active', 'trial', 'grace', 'suspended'].map((s) => (
              <button
                key={s}
                type="button"
                className={filter === s ? 'plat-chip active' : 'plat-chip'}
                onClick={() => setFilter(s)}
              >
                {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </header>

        <div className="plat-stats">
          <div className="plat-stat">
            <span>Total tenants</span>
            <strong>{stats.total}</strong>
          </div>
          <div className="plat-stat ok">
            <span>Active</span>
            <strong>{stats.active}</strong>
          </div>
          <div className="plat-stat trial">
            <span>Trial</span>
            <strong>{stats.trial}</strong>
          </div>
          <div className="plat-stat grace">
            <span>Grace</span>
            <strong>{stats.grace}</strong>
          </div>
          <div className="plat-stat bad">
            <span>Suspended</span>
            <strong>{stats.suspended}</strong>
          </div>
        </div>

        {error && <p className="login-error">{error}</p>}
        {message && <p className="muted">{message}</p>}

        <div className="plat-panel">
          <h2>Tenant management</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Slug</th>
                <th>Status</th>
                <th>Industry</th>
                <th>Currency</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((t) => (
                <tr key={t.id}>
                  <td>
                    <div className="plat-co">{t.company_name}</div>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {t.email || 'No email'}
                    </div>
                  </td>
                  <td>{t.slug}</td>
                  <td>
                    <span className={`status-pill ${statusClass(t.status)}`} style={{ margin: 0 }}>
                      {t.status}
                      {typeof t.days_remaining === 'number' ? ` · ${t.days_remaining}d` : ''}
                    </span>
                  </td>
                  <td>{t.industry || '—'}</td>
                  <td>{t.currency || '—'}</td>
                  <td>{fmtDate(t.created_at)}</td>
                  <td>
                    <div className="plat-actions">
                      {t.status === 'suspended' ? (
                        <button
                          type="button"
                          disabled={busy === t.id}
                          onClick={() => activateTenant(t)}
                        >
                          Activate
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="danger"
                          disabled={busy === t.id}
                          onClick={() => suspendTenant(t)}
                        >
                          Suspend
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
