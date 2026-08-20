'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type SubscriptionInfo = {
  package_code?: string;
  package_name?: string;
  term_value?: number | null;
  term_unit?: string | null;
  months_assigned?: number | null;
  years_assigned?: number | null;
  months_used?: number | null;
  years_used?: number | null;
  months_remaining?: number | null;
  years_remaining?: number | null;
  days_remaining?: number | null;
  subscription_starts_at?: string | null;
  subscription_ends_at?: string | null;
  enabled_modules?: string[];
  modules_customized?: boolean;
  max_stores_override?: number | null;
  package_max_stores?: number | null;
  effective_store_limit?: number | null;
  stores_active?: number | null;
  stores_remaining?: number | null;
  over_entitlement?: boolean;
  unlimited_stores?: boolean;
};

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
  package_code?: string;
  max_stores_override?: number | null;
  store_limit?: number | null;
  store_usage?: {
    stores_active?: number;
    effective_store_limit?: number | null;
    over_entitlement?: boolean;
  };
  subscription?: SubscriptionInfo;
  enabled_modules?: string[];
};

type PackageInfo = {
  code: string;
  name: string;
  description: string;
  modules: string[];
  max_stores?: number | null;
  max_companies?: number | null;
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
  const [packages, setPackages] = useState<PackageInfo[]>([]);
  const [packageable, setPackageable] = useState<string[]>([]);
  const [filter, setFilter] = useState('all');
  const [form, setForm] = useState(emptyCreate);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [ready, setReady] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [subForm, setSubForm] = useState({
    package_code: 'professional',
    term_value: 12,
    term_unit: 'months',
    start_at: '',
    max_stores_override: '' as string,
  });
  const [moduleDraft, setModuleDraft] = useState<string[]>([]);
  const [suspendReason, setSuspendReason] = useState('');
  const [overrideDraft, setOverrideDraft] = useState('');

  const selected = useMemo(
    () => tenants.find((t) => t.id === selectedId) || null,
    [tenants, selectedId]
  );

  async function refresh() {
    const me = await api('/me');
    const role = me.data?.role || '';
    const platformRoles = [
      'super_admin',
      'platform_owner',
      'platform_admin',
      'platform_support',
      'platform_finance',
    ];
    if (!platformRoles.includes(role)) {
      router.replace('/dashboard');
      return;
    }
    const [res, pkgs] = await Promise.all([api('/tenants'), api('/packages')]);
    setTenants(res.data || []);
    setPackages(pkgs.data?.packages || []);
    setPackageable(pkgs.data?.packageable_modules || []);
    setReady(true);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message || 'Failed to load platform console'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setModuleDraft([]);
      return;
    }
    const sel = tenants.find((t) => t.id === selectedId);
    if (!sel) return;
    setSubForm({
      package_code: sel.package_code || sel.subscription?.package_code || 'professional',
      term_value: sel.subscription?.term_value || 12,
      term_unit: sel.subscription?.term_unit || 'months',
      start_at: '',
      max_stores_override:
        sel.max_stores_override != null
          ? String(sel.max_stores_override)
          : sel.subscription?.max_stores_override != null
            ? String(sel.subscription.max_stores_override)
            : '',
    });
    setOverrideDraft(
      sel.max_stores_override != null
        ? String(sel.max_stores_override)
        : sel.subscription?.max_stores_override != null
          ? String(sel.subscription.max_stores_override)
          : ''
    );
    setModuleDraft(sel.enabled_modules || sel.subscription?.enabled_modules || []);
    api(`/tenants/${sel.slug || sel.id}/usage`)
      .then((r) => {
        const row = r.data as TenantRow;
        setTenants((prev) => prev.map((t) => (t.id === sel.id ? { ...t, ...row } : t)));
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

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
        `Created tenant ${r.data?.slug || form.slug} (trial). Assign a paid package below when ready.`
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
    const reason = suspendReason.trim();
    if (!reason) {
      setError('Enter a suspend reason before suspending a tenant');
      return;
    }
    if (!window.confirm(`Suspend ${row.company_name}?`)) return;
    setBusy(row.id);
    setError('');
    setMessage('');
    try {
      await api(`/tenants/${row.slug || row.id}/suspend`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      setSuspendReason('');
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

  async function assignSubscription(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setBusy(selected.id);
    setError('');
    setMessage('');
    try {
      const body: Record<string, unknown> = {
        package_code: subForm.package_code,
        term_value: Number(subForm.term_value),
        term_unit: subForm.term_unit,
        activate: true,
      };
      if (subForm.start_at.trim()) body.start_at = subForm.start_at.trim();
      if (subForm.max_stores_override.trim() !== '') {
        body.max_stores_override = Number(subForm.max_stores_override);
      }
      const r = await api(`/tenants/${selected.slug || selected.id}/subscription`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setMessage(
        `Assigned ${r.data?.subscription?.package_name || subForm.package_code} for ${subForm.term_value} ${subForm.term_unit} to ${selected.company_name}`
      );
      await refresh();
      setSelectedId(r.data?.id || selected.id);
    } catch (err: any) {
      setError(err.message || 'Assign subscription failed');
    } finally {
      setBusy(null);
    }
  }

  async function saveModules() {
    if (!selected) return;
    setBusy(selected.id);
    setError('');
    setMessage('');
    try {
      await api(`/tenants/${selected.slug || selected.id}/modules`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled_modules: moduleDraft }),
      });
      setMessage(`Updated feature modules for ${selected.company_name}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Update modules failed');
    } finally {
      setBusy(null);
    }
  }

  async function resetModules() {
    if (!selected) return;
    if (!window.confirm('Reset modules to the package default?')) return;
    setBusy(selected.id);
    setError('');
    setMessage('');
    try {
      await api(`/tenants/${selected.slug || selected.id}/modules`, {
        method: 'PATCH',
        body: JSON.stringify({ reset_to_package: true }),
      });
      setMessage(`Reset modules to package default for ${selected.company_name}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Reset modules failed');
    } finally {
      setBusy(null);
    }
  }

  function toggleModule(mod: string) {
    if (['dashboard', 'notifications', 'security'].includes(mod)) return;
    setModuleDraft((prev) =>
      prev.includes(mod) ? prev.filter((m) => m !== mod) : [...prev, mod]
    );
  }

  function applyPackageModules(code: string) {
    const pkg = packages.find((p) => p.code === code);
    if (pkg) setModuleDraft(pkg.modules);
  }

  if (!ready && !error) {
    return (
      <Shell>
        <p className="muted">Loading platform console…</p>
      </Shell>
    );
  }

  const sub = selected?.subscription;

  return (
    <Shell>
      <div className="plat">
        <header className="plat-hero">
          <div>
            <p className="plat-kicker">Software owner</p>
            <h1>Platform console</h1>
            <p className="plat-sub">
              Create workspaces, assign subscription terms (months/years), track usage and renewal,
              and control package features per tenant.
            </p>
          </div>
          <div className="plat-filters" role="group" aria-label="Tenant status">
            {['all', 'active', 'trial', 'grace', 'suspended'].map((s) => (
              <button
                key={s}
                type="button"
                className={filter === s ? 'plat-chip active' : 'plat-chip'}
                aria-pressed={filter === s}
                aria-label={s === 'all' ? 'Tenant status all' : `Tenant status ${s}`}
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
                onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value }))}
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
          <div className="card" style={{ marginBottom: 12 }}>
            <label>
              Suspend reason{' '}
              <input
                value={suspendReason}
                onChange={(e) => setSuspendReason(e.target.value)}
                placeholder="Required before Suspend"
                title="Required suspend reason (1–500 chars; letters/digits required)"
                aria-label="Tenant suspend reason"
                style={{ minWidth: 280 }}
              />
            </label>
            <p className="muted" style={{ marginTop: 6 }}>
              Used by Suspend on non-suspended tenants (stored as <code>suspended_reason</code>).
            </p>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Package</th>
                <th>Term / usage</th>
                <th>Remaining</th>
                <th>Status</th>
                <th>Suspend reason</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((t) => {
                const s = t.subscription || {};
                return (
                  <tr key={t.id} className={selectedId === t.id ? 'plat-row-selected' : undefined}>
                    <td>
                      <div className="plat-co">{t.company_name}</div>
                      <div className="muted" style={{ fontSize: 12 }}>
                        {t.slug} · {t.email || 'No email'}
                      </div>
                    </td>
                    <td>
                      <strong>{s.package_name || t.package_code || 'trial'}</strong>
                      {s.modules_customized ? (
                        <div className="muted" style={{ fontSize: 11 }}>
                          custom modules
                        </div>
                      ) : null}
                    </td>
                    <td style={{ fontSize: 13 }}>
                      {s.term_value != null
                        ? `${s.term_value} ${s.term_unit || 'months'}`
                        : '—'}
                      <div className="muted" style={{ fontSize: 11 }}>
                        used {s.months_used ?? 0} mo
                        {s.years_used != null ? ` (${s.years_used} y)` : ''}
                      </div>
                    </td>
                    <td style={{ fontSize: 13 }}>
                      {s.months_remaining != null ? `${s.months_remaining} mo` : '—'}
                      {s.days_remaining != null ? (
                        <div className="muted" style={{ fontSize: 11 }}>
                          {s.days_remaining}d · renew {fmtDate(s.subscription_ends_at)}
                        </div>
                      ) : null}
                    </td>
                    <td>
                      <span className={`status-pill ${statusClass(t.status)}`} style={{ margin: 0 }}>
                        {t.status}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, maxWidth: 220 }}>
                      {t.suspended_reason || '—'}
                    </td>
                    <td>
                      <div className="plat-actions">
                        <button type="button" disabled={busy === t.id} onClick={() => setSelectedId(t.id)}>
                          Manage
                        </button>
                        {t.status === 'suspended' ? (
                          <button type="button" className="btn-ok" disabled={busy === t.id} onClick={() => activateTenant(t)}>
                            Activate
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="btn-danger"
                            disabled={busy === t.id}
                            onClick={() => suspendTenant(t)}
                            aria-label={`Suspend tenant ${t.id}`}
                          >
                            Suspend
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {selected && (
          <div className="plat-panel" id="subscription-panel">
            <h2>
              Subscription & features — {selected.company_name}
              <button
                type="button"
                style={{ float: 'right', fontSize: 13 }}
                onClick={() => setSelectedId(null)}
              >
                Close
              </button>
            </h2>
            <div className="plat-stats" style={{ marginBottom: 16 }}>
              <div className="plat-stat">
                <span>Assigned</span>
                <strong style={{ fontSize: 18 }}>
                  {sub?.months_assigned ?? '—'} mo
                  {sub?.years_assigned != null ? ` / ${sub.years_assigned} y` : ''}
                </strong>
              </div>
              <div className="plat-stat trial">
                <span>Used</span>
                <strong style={{ fontSize: 18 }}>
                  {sub?.months_used ?? 0} mo
                  {sub?.years_used != null ? ` / ${sub.years_used} y` : ''}
                </strong>
              </div>
              <div className="plat-stat ok">
                <span>Remaining</span>
                <strong style={{ fontSize: 18 }}>
                  {sub?.months_remaining ?? '—'} mo
                  {sub?.days_remaining != null ? ` (${sub.days_remaining}d)` : ''}
                </strong>
              </div>
              <div className="plat-stat">
                <span>Renewal</span>
                <strong style={{ fontSize: 16 }}>{fmtDate(sub?.subscription_ends_at)}</strong>
              </div>
            </div>

            <form className="plat-form" onSubmit={assignSubscription}>
              <label>
                <span>Package</span>
                <select
                  value={subForm.package_code}
                  onChange={(e) => {
                    const package_code = e.target.value;
                    setSubForm((f) => ({ ...f, package_code }));
                    applyPackageModules(package_code);
                  }}
                >
                  {packages.map((p) => (
                    <option key={p.code} value={p.code}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Term length</span>
                <input
                  type="number"
                  min={1}
                  max={120}
                  value={subForm.term_value}
                  onChange={(e) =>
                    setSubForm((f) => ({ ...f, term_value: Number(e.target.value) || 1 }))
                  }
                  required
                />
              </label>
              <label>
                <span>Term unit</span>
                <select
                  value={subForm.term_unit}
                  onChange={(e) => setSubForm((f) => ({ ...f, term_unit: e.target.value }))}
                >
                  <option value="months">Months</option>
                  <option value="years">Years</option>
                </select>
              </label>
              <label>
                <span>Start date</span>
                <input
                  aria-label="Subscription start date"
                  type="text"
                  placeholder="YYYY-MM-DD (blank = now)"
                  title="Optional subscription start (YYYY-MM-DD or ISO; blank = now)"
                  value={subForm.start_at}
                  onChange={(e) => setSubForm((f) => ({ ...f, start_at: e.target.value }))}
                />
              </label>
              <label>
                <span>Store entitlement override</span>
                <input
                  type="number"
                  min={0}
                  placeholder="Package default"
                  value={subForm.max_stores_override}
                  onChange={(e) =>
                    setSubForm((f) => ({ ...f, max_stores_override: e.target.value }))
                  }
                />
              </label>
              <button type="submit" disabled={busy === selected.id}>
                {busy === selected.id ? 'Saving…' : 'Assign package & term'}
              </button>
            </form>
            <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>
              Package max stores:{' '}
              {packages.find((p) => p.code === subForm.package_code)?.max_stores ?? '—'}{' '}
              (blank override = catalog / unlimited for Enterprise). Active stores:{' '}
              {selected.subscription?.stores_active ?? selected.store_usage?.stores_active ?? '—'} /{' '}
              {selected.subscription?.effective_store_limit ??
                selected.store_usage?.effective_store_limit ??
                '∞'}
              {selected.subscription?.over_entitlement || selected.store_usage?.over_entitlement
                ? ' · over entitlement'
                : ''}
            </p>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8, flexWrap: 'wrap' }}>
              <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span>max_stores_override</span>
                <input
                  type="number"
                  min={0}
                  placeholder="Clear / package"
                  value={overrideDraft}
                  onChange={(e) => setOverrideDraft(e.target.value)}
                  style={{ width: 120 }}
                />
              </label>
              <button
                type="button"
                disabled={busy === selected.id}
                onClick={async () => {
                  setBusy(selected.id);
                  setError('');
                  try {
                    const raw = overrideDraft.trim();
                    await api(`/tenants/${selected.slug || selected.id}/store-entitlement`, {
                      method: 'PATCH',
                      body: JSON.stringify(
                        raw === ''
                          ? { clear: true }
                          : { max_stores_override: Number(raw) }
                      ),
                    });
                    setMessage('Store entitlement override updated');
                    await refresh();
                  } catch (err: any) {
                    setError(err.message || 'Override failed');
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                Save store override
              </button>
            </div>

            <h3 style={{ marginTop: 20, fontSize: 15 }}>Feature modules (package control)</h3>
            <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              Toggle which modules this tenant can use. Dashboard, notifications, and security stay on.
            </p>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                gap: 8,
                marginTop: 12,
              }}
            >
              {packageable.map((mod) => {
                const locked = ['dashboard', 'notifications', 'security'].includes(mod);
                const on = moduleDraft.includes(mod) || locked;
                return (
                  <label
                    key={mod}
                    style={{
                      display: 'flex',
                      gap: 8,
                      alignItems: 'center',
                      fontSize: 13,
                      padding: '6px 8px',
                      border: '1px solid #e2e8f0',
                      borderRadius: 8,
                      opacity: locked ? 0.7 : 1,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={on}
                      disabled={locked}
                      onChange={() => toggleModule(mod)}
                    />
                    {mod}
                  </label>
                );
              })}
            </div>
            <div className="plat-actions" style={{ marginTop: 14 }}>
              <button type="button" disabled={busy === selected.id} onClick={saveModules}>
                Save feature modules
              </button>
              <button type="button" disabled={busy === selected.id} onClick={resetModules}>
                Reset to package default
              </button>
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}
