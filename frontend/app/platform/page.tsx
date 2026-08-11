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

const emptyCreate = {
  company_name: '',
  slug: '',
  industry: 'retail',
  currency: 'GHS',
  admin_email: '',
  admin_password: '',
};

const INDUSTRIES = ['retail', 'mart', 'pharmacy', 'restaurant', 'bakery', 'wholesale', 'manufacturing'];

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

function slugify(name: string) {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}

export default function PlatformConsole() {
  const router = useRouter();
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [filter, setFilter] = useState('all');
  const [form, setForm] = useState(emptyCreate);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [ready, setReady] = useState(false);

  async function refresh() {
    const me = await api('/me');
    if (me.data?.role !== 'super_admin') {
      router.replace('/dashboard');
      return;
    }
    const res = await api('/tenants');
    setTenants(res.data || []);
    setReady(true);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message || 'Failed to load platform console'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stats = useMemo(() => {
    const count = (s: string) => tenants.filter((t) => t.status === s).length;
    return {
      total: tenants.length,
      active: count('active'),
      trial: count('trial'),
      grace: count('grace'),
      suspended: count('suspended'),
    };
  }, [tenants]);

  const visible = useMemo(
    () => (filter === 'all' ? tenants : tenants.filter((t) => t.status === filter)),
    [tenants, filter]
  );

  async function createTenant(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError('');
    setMessage('');
    try {
      const r = await api('/tenants', {
        method: 'POST',
        body: JSON.stringify({
          company_name: form.company_name.trim(),
          slug: form.slug.trim().toLowerCase(),
          industry: form.industry,
          currency: form.currency.trim().toUpperCase() || 'GHS',
          admin_email: form.admin_email.trim(),
          admin_password: form.admin_password,
        }),
      });
      setForm(emptyCreate);
      setMessage(
        `Created tenant ${r.data?.slug || form.slug} (trial). Admin must verify email before production use.`
      );
      setFilter('all');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Create tenant failed');
    } finally {
      setCreating(false);
    }
  }

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
            <p className="plat-sub">
              Create workspaces, monitor trial/active/grace status, and suspend or activate tenants.
            </p>
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

        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}
        {message && <p className="plat-msg">{message}</p>}

        <div className="plat-panel">
          <h2>Create tenant</h2>
          <form className="plat-form" onSubmit={createTenant}>
            <label>
              <span>Company name</span>
              <input
                value={form.company_name}
                onChange={(e) => {
                  const company_name = e.target.value;
                  setForm((f) => ({
                    ...f,
                    company_name,
                    slug: f.slug && f.slug !== slugify(f.company_name) ? f.slug : slugify(company_name),
                  }));
                }}
                placeholder="Sunrise Mart Ltd"
                required
              />
            </label>
            <label>
              <span>Slug</span>
              <input
                value={form.slug}
                onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value.toLowerCase() }))}
                placeholder="sunrise-mart"
                pattern="[a-z0-9-]{2,80}"
                required
              />
            </label>
            <label>
              <span>Industry</span>
              <select
                value={form.industry}
                onChange={(e) => setForm((f) => ({ ...f, industry: e.target.value }))}
              >
                {INDUSTRIES.map((i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Currency</span>
              <input
                value={form.currency}
                onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))}
                placeholder="GHS"
                maxLength={10}
                required
              />
            </label>
            <label>
              <span>Admin email</span>
              <input
                type="email"
                value={form.admin_email}
                onChange={(e) => setForm((f) => ({ ...f, admin_email: e.target.value }))}
                placeholder="admin@company.example.com"
                required
              />
            </label>
            <label>
              <span>Admin password</span>
              <input
                type="password"
                value={form.admin_password}
                onChange={(e) => setForm((f) => ({ ...f, admin_password: e.target.value }))}
                placeholder="Min 8 chars, upper/lower/number/symbol"
                required
              />
            </label>
            <button type="submit" disabled={creating}>
              {creating ? 'Creating…' : 'Create tenant'}
            </button>
          </form>
        </div>

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
              {visible.map((t) => (
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
                        <button type="button" disabled={busy === t.id} onClick={() => activateTenant(t)}>
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
