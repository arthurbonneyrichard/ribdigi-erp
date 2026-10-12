'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '../../../../lib/api';
import { getMe } from '../../../../lib/meCache';
import { getPrefetched } from '../../../../lib/prefetchCache';
import { industryAllowsModule } from '../../../../lib/industryModules';
import { INDUSTRIES, PROVISION_INDUSTRIES, industryLabel } from '../../../../lib/industries';

/** New companies: Retail, Hotel, and Restaurant. */
const CREATE_INDUSTRIES = [...PROVISION_INDUSTRIES] as const;

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
  store_mode?: string;
  user_count?: number;
  store_count?: number;
  branch_count?: number;
  account_status?: string;
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
  industry: '',
  currency: 'GHS',
  admin_email: '',
  admin_password: '',
  store_mode: 'single' as 'single' | 'multi',
  max_stores: '10',
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

function slugify(name: string) {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}

export default function PlatformTenantsPage() {
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
  const [deleteConfirmSlug, setDeleteConfirmSlug] = useState('');
  const [overrideDraft, setOverrideDraft] = useState('');
  const [industryDraft, setIndustryDraft] = useState('');
  const [industryReason, setIndustryReason] = useState('');
  const [meRole, setMeRole] = useState('');
  const managePanelRef = useRef<HTMLDivElement | null>(null);

  const selected = useMemo(
    () => tenants.find((t) => t.id === selectedId) || null,
    [tenants, selectedId]
  );
  const canDeleteTenant = meRole === 'platform_owner' || meRole === 'super_admin';
  const canHardDeleteTenant = canDeleteTenant;

  function openManage(row: TenantRow) {
    setError('');
    setSelectedId(row.id);
    setIndustryDraft(row.industry || '');
    setIndustryReason('');
    setMessage(`Managing ${row.company_name} (workspace: ${row.slug})`);
    // Defer scroll until the panel has rendered.
    window.setTimeout(() => {
      managePanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  }

  async function refresh(options?: { force?: boolean }) {
    const force = Boolean(options?.force);
    const [me, res, pkgs, directory] = await Promise.all([
      getMe({ force }),
      getPrefetched('/tenants', { force }),
      getPrefetched('/packages', { force }),
      api('/platform/directory'),
    ]);
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
    setMeRole(role);
    const summary = new Map((directory.data || []).map((row: TenantRow) => [row.id, row]));
    setTenants(
      (res.data || []).map((row: TenantRow) => ({ ...row, ...(summary.get(row.id) || {}) }))
    );
    setPackages(pkgs.data?.packages || []);
    setPackageable(pkgs.data?.packageable_modules || []);
    setReady(true);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message || 'Failed to load tenants'));
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
    api(`/tenants/${encodeURIComponent(sel.slug || sel.id)}/usage`)
      .then((r) => {
        const row = r.data as TenantRow;
        if (!row || typeof row !== 'object') return;
        setTenants((prev) =>
          prev.map((t) => (t.id === sel.id ? { ...t, ...row, id: t.id, slug: t.slug || row.slug } : t))
        );
      })
      .catch(() => undefined);
    window.setTimeout(() => {
      managePanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
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
    const trimmedPassword = form.admin_password.trim();
    if (!trimmedPassword) {
      setError('Tenant admin password is required.');
      setMessage('');
      return;
    }
    if (!form.industry) {
      setError('Business type is required.');
      setMessage('');
      return;
    }
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
          admin_password: trimmedPassword,
          store_mode: form.store_mode,
          ...(form.store_mode === 'multi' && form.max_stores.trim() !== ''
            ? { max_stores_override: Number(form.max_stores) }
            : {}),
        }),
      });
      setForm(emptyCreate);
      const createdSlug = String(r.data?.slug || form.slug).trim().toLowerCase();
      const sent = Boolean(r.data?.email?.sent);
      const createdId = String(r.data?.tenant_id || r.data?.id || '').trim();
      setMessage(
        sent
          ? `Created tenant "${createdSlug}". A verification email was sent to the company admin. They sign in with workspace "${createdSlug}" after they open that email. You can also click Verify account.`
          : `Created tenant "${createdSlug}". The verification email was not sent. Turn on SMTP, then click Resend email, or click Verify account. Workspace is "${createdSlug}", not "platform".`
      );
      setFilter('all');
      await refresh({ force: true });
      if (createdId) {
        openManage({
          id: createdId,
          slug: createdSlug,
          company_name: r.data.company_name || form.company_name,
          status: r.data.status || 'trial',
        } as TenantRow);
      }
    } catch (err: any) {
      setError(err.message || 'Create tenant failed');
    } finally {
      setCreating(false);
    }
  }

  async function resendAdminEmail(row: TenantRow) {
    setBusy(row.id);
    setError('');
    setMessage('');
    try {
      const r = await api(
        `/tenants/${encodeURIComponent(row.slug || row.id)}/resend-admin-verification`,
        { method: 'POST', body: '{}' }
      );
      setMessage(r.message || `Verification email resent for "${row.slug}".`);
    } catch (err: any) {
      setError(err.message || 'Could not resend the verification email');
    } finally {
      setBusy(null);
    }
  }

  async function allowAdminSignIn(row: TenantRow) {
    setBusy(row.id);
    setError('');
    setMessage('');
    try {
      const r = await api(`/tenants/${encodeURIComponent(row.slug || row.id)}/verify-admin`, {
        method: 'POST',
        body: '{}',
      });
      setMessage(
        r.message ||
          `Company admin for "${row.slug}" can sign in. Use workspace "${row.slug}", not "platform".`
      );
    } catch (err: any) {
      setError(err.message || 'Could not enable admin sign-in');
    } finally {
      setBusy(null);
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
      await refresh({ force: true });
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
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message || 'Activate failed');
    } finally {
      setBusy(null);
    }
  }

  async function deleteTenant(row: TenantRow) {
    const slug = String(row.slug || '').trim();
    if (!slug) {
      setError('This tenant has no slug to confirm deletion.');
      return;
    }
    if (slug === 'platform' || slug === 'ribdigi-platform') {
      setError('The platform owner workspace cannot be deleted.');
      return;
    }
    const typed = deleteConfirmSlug.trim();
    if (typed !== slug) {
      setError(`Type the tenant slug exactly to confirm: ${slug}`);
      setMessage('');
      return;
    }
    if (
      !window.confirm(
        `Delete ${row.company_name} permanently?\n\nThis removes the company workspace and all of its data. This cannot be undone.`
      )
    ) {
      return;
    }
    setBusy(row.id);
    setError('');
    setMessage('');
    try {
      await api(`/tenants/${encodeURIComponent(slug)}/delete`, {
        method: 'POST',
        body: JSON.stringify({ confirm_slug: slug }),
      });
      if (selectedId === row.id) setSelectedId(null);
      setDeleteConfirmSlug('');
      setMessage(`Deleted ${row.company_name}`);
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message || 'Delete failed');
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
      await refresh({ force: true });
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
      const enabled_modules = moduleDraft.filter((mod) =>
        industryAllowsModule(selected.industry, mod)
      );
      await api(`/tenants/${selected.slug || selected.id}/modules`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled_modules }),
      });
      setMessage(`Updated feature modules for ${selected.company_name}`);
      await refresh({ force: true });
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
      await refresh({ force: true });
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
    if (pkg) {
      setModuleDraft(pkg.modules.filter((mod) => industryAllowsModule(selected?.industry, mod)));
    }
  }

  async function resetTenantAdminPassword(row?: TenantRow) {
    const target = row || selected;
    if (!target) return;
    const ok = window.confirm(
      `Send a password reset link to the administrator of ${target.company_name}?\n\nThe current password is not shown, and a new password is not displayed here.`
    );
    if (!ok) return;
    setBusy(target.id);
    setError('');
    setMessage('');
    try {
      const res = await api(`/tenants/${target.slug || target.id}/admin-password-reset`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      const when = res.data?.initiated_at ? ` at ${fmtDate(res.data.initiated_at)}` : '';
      setMessage(
        `Password reset requested for the administrator of ${target.company_name}${when}. A reset link was emailed. No password is shown.`
      );
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message || 'Password reset failed');
    } finally {
      setBusy(null);
    }
  }

  if (!ready && !error) {
    return (
      <>
        <p className="muted">Loading tenants…</p>
      </>
    );
  }

  const sub = selected?.subscription;

  return (
    <>
      <div className="plat">
        <header className="plat-hero">
          <div>
            <p className="plat-kicker">Software owner</p>
            <h1>Tenants</h1>
            <p className="plat-sub">
              Create a workspace and manage its subscription, stores, and account. Paid self-serve
              checkout is not live — this page assigns entitlements only.
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
                aria-label="Tenant company name"
                required
              />
            </label>
            <label>
              <span>Slug</span>
              <input
                aria-label="Tenant slug"
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
                aria-label="Tenant industry"
                required
              >
                <option value="">Select business type</option>
                {CREATE_INDUSTRIES.map((i) => (
                  <option key={i} value={i}>
                    {industryLabel(i)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Currency</span>
              <input
                value={form.currency}
                onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value }))}
                aria-label="Tenant currency"
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
                aria-label="Tenant admin email"
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
                aria-label="Tenant admin password"
                required
              />
            </label>
            <fieldset style={{ border: '1px solid var(--border, #ddd)', borderRadius: 8, padding: 10 }}>
              <legend>Store layout</legend>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  type="radio"
                  name="create-store-mode"
                  checked={form.store_mode === 'single'}
                  onChange={() => setForm((f) => ({ ...f, store_mode: 'single' }))}
                  aria-label="Single store"
                />
                Single store
              </label>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  type="radio"
                  name="create-store-mode"
                  checked={form.store_mode === 'multi'}
                  onChange={() => setForm((f) => ({ ...f, store_mode: 'multi' }))}
                  aria-label="Multi-store"
                />
                Multi-store (includes branches)
              </label>
              {form.store_mode === 'multi' ? (
                <label style={{ marginTop: 8 }}>
                  <span>Max stores</span>
                  <input
                    type="number"
                    min={2}
                    value={form.max_stores}
                    onChange={(e) => setForm((f) => ({ ...f, max_stores: e.target.value }))}
                    aria-label="Create tenant max stores"
                  />
                </label>
              ) : (
                <p className="muted" style={{ fontSize: 13, margin: '8px 0 0' }}>
                  One operating store. Extra store create is blocked until you switch this tenant to
                  Multi-store.
                </p>
              )}
            </fieldset>
            <button
              type="submit"
              disabled={creating || !form.admin_password.trim()}
              aria-label="Create tenant"
            >
              {creating ? 'Creating…' : 'Create tenant'}
            </button>
          </form>
        </div>

        <div className="plat-panel">
          <h2>Tenant management</h2>
          <p className="muted" style={{ marginTop: 0, marginBottom: 12 }}>
            Click <strong>Manage</strong> for subscription and modules. A new company admin stays
            inactive until they open the verification email. <strong>Resend email</strong> sends that
            link again. <strong>Verify account</strong> is the platform owner override, so they can
            sign in without the email. They use that company&apos;s <strong>slug</strong>, not{' '}
            <code>platform</code>.
          </p>
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
            {canHardDeleteTenant ? (
              <>
                <label style={{ display: 'block', marginTop: 10 }}>
                  Delete confirmation{' '}
                  <input
                    value={deleteConfirmSlug}
                    onChange={(e) => setDeleteConfirmSlug(e.target.value)}
                    placeholder="Type the tenant slug"
                    aria-label="Delete tenant confirmation"
                    style={{ minWidth: 280 }}
                  />
                </label>
                <p className="muted" style={{ marginTop: 6 }}>
                  Delete removes the company and its data. Type that tenant&apos;s slug, then Delete.
                  Only the software owner can delete a company.
                </p>
              </>
            ) : null}
          </div>

          {selected ? (
            <div
              className="plat-msg"
              style={{ marginBottom: 12 }}
              role="status"
            >
              Managing <strong>{selected.company_name}</strong> — workspace/slug:{' '}
              <code>{selected.slug}</code>. Scroll to the panel below or use the highlighted
              section under the table.
            </div>
          ) : null}

          <table className="table">
            <thead>
              <tr>
                <th>Tenant</th>
                <th>Status</th>
                <th>Industry</th>
                <th>Store mode</th>
                <th>Users</th>
                <th>Stores / branches</th>
                <th>Created</th>
                <th>Account</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((t) => {
                return (
                  <tr key={t.id} className={selectedId === t.id ? 'plat-row-selected' : undefined}>
                    <td>
                      <div className="plat-co">{t.company_name}</div>
                      <div className="muted" style={{ fontSize: 12 }}>
                        {t.slug}
                      </div>
                    </td>
                    <td>
                      <span className={`status-pill ${statusClass(t.status)}`} style={{ margin: 0 }}>
                        {t.status}
                      </span>
                    </td>
                    <td>{industryLabel(t.industry)}</td>
                    <td>{t.store_mode === 'multi' ? 'Multi-store' : 'Single store'}</td>
                    <td>{t.user_count ?? '—'}</td>
                    <td>
                      {t.store_count ?? 0} / {t.branch_count ?? 0}
                    </td>
                    <td>{fmtDate(t.created_at)}</td>
                    <td style={{ fontSize: 13 }}>
                      {t.account_status === 'verified'
                        ? 'Verified'
                        : t.account_status === 'pending_verification'
                          ? 'Pending verification'
                          : t.account_status === 'no_administrator'
                            ? 'No administrator'
                            : t.account_status || '—'}
                    </td>
                    <td>
                      <div className="plat-actions">
                        <button
                          type="button"
                          disabled={busy === t.id}
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            openManage(t);
                          }}
                          aria-label={`Manage tenant ${t.slug || t.id}`}
                        >
                          {selectedId === t.id ? 'Managing…' : 'Manage'}
                        </button>
                        <button
                          type="button"
                          disabled={busy === t.id}
                          onClick={() => resendAdminEmail(t)}
                          aria-label={`Resend verification email for tenant ${t.slug || t.id}`}
                        >
                          Resend email
                        </button>
                        <button
                          type="button"
                          className="btn-ok"
                          disabled={busy === t.id}
                          onClick={() => allowAdminSignIn(t)}
                          aria-label={`Verify account for tenant ${t.slug || t.id}`}
                        >
                          Verify account
                        </button>
                        {canDeleteTenant ? (
                          <button
                            type="button"
                            disabled={busy === t.id}
                            onClick={() => resetTenantAdminPassword(t)}
                            aria-label={`Reset administrator password for tenant ${t.slug || t.id}`}
                          >
                            Reset admin password
                          </button>
                        ) : null}
                        {t.status === 'suspended' ? (
                          <button type="button" className="btn-ok" disabled={busy === t.id} onClick={() => activateTenant(t)} aria-label={`Activate tenant ${t.id}`}>
                            Activate
                          </button>
                        ) : t.slug !== 'platform' && t.slug !== 'ribdigi-platform' ? (
                          <button
                            type="button"
                            className="btn-danger"
                            disabled={busy === t.id}
                            onClick={() => suspendTenant(t)}
                            aria-label={`Suspend tenant ${t.id}`}
                          >
                            Suspend
                          </button>
                        ) : null}
                        {canHardDeleteTenant && t.slug !== 'platform' && t.slug !== 'ribdigi-platform' ? (
                          <button
                            type="button"
                            className="btn-danger"
                            disabled={busy === t.id}
                            onClick={() => deleteTenant(t)}
                            aria-label={`Delete tenant ${t.slug || t.id}`}
                          >
                            Delete
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {selected && (
          <div
            className="plat-panel plat-manage-panel"
            id="subscription-panel"
            ref={managePanelRef}
            tabIndex={-1}
            style={{ borderColor: 'var(--brand)', boxShadow: '0 0 0 2px #4AB01233' }}
          >
            <h2>
              Subscription & features — {selected.company_name}
              <span className="muted" style={{ fontWeight: 600, fontSize: 13, marginLeft: 8 }}>
                slug: {selected.slug}
              </span>
              <button
                type="button"
                style={{ float: 'right', fontSize: 13 }}
                onClick={() => {
                  setSelectedId(null);
                  setMessage('');
                }}
                aria-label="Close tenant management panel"
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

            <h3 style={{ marginTop: 20, fontSize: 15 }}>Business type</h3>
            <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              Current: {industryLabel(selected.industry)}. Only the Platform Owner can change this.
              Choose Retail, Hotel, or Restaurant. APIs follow the saved industry immediately. Ask
              staff to refresh or sign in again so the sidebar matches. Existing records are kept.
            </p>
            {canDeleteTenant ? (
              <div className="plat-form" style={{ marginTop: 8, display: 'grid', gap: 8 }}>
                <label>
                  <span>New business type</span>
                  <select
                    value={industryDraft || selected.industry || ''}
                    onChange={(e) => setIndustryDraft(e.target.value)}
                    aria-label="Change tenant business type"
                  >
                    {selected.industry &&
                    !(INDUSTRIES as readonly string[]).includes(selected.industry) ? (
                      <option value={selected.industry} disabled>
                        {industryLabel(selected.industry)} (current, not available)
                      </option>
                    ) : null}
                    {INDUSTRIES.map((i) => (
                      <option key={i} value={i}>
                        {industryLabel(i)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Reason</span>
                  <input
                    value={industryReason}
                    onChange={(e) => setIndustryReason(e.target.value)}
                    placeholder="Why this change is required"
                    aria-label="Business type change reason"
                  />
                </label>
                <button
                  type="button"
                  disabled={busy === selected.id}
                  aria-label="Save tenant business type"
                  onClick={async () => {
                    setError('');
                    const stored = selected.industry || '';
                    const selectable = INDUSTRIES as readonly string[];
                    const nextIndustry = (industryDraft || (selectable.includes(stored) ? stored : '')).trim();
                    if (!selectable.includes(nextIndustry)) {
                      setError('Choose retail, hotel, or restaurant.');
                      return;
                    }
                    setBusy(selected.id);
                    try {
                      await api(`/tenants/${selected.id}/industry`, {
                        method: 'PATCH',
                        body: JSON.stringify({
                          industry: nextIndustry,
                          reason: industryReason.trim(),
                        }),
                      });
                      setMessage('Business type updated');
                      setIndustryReason('');
                      await refresh({ force: true });
                    } catch (err: any) {
                      setError(err.message || 'Business type change failed');
                    } finally {
                      setBusy(null);
                    }
                  }}
                >
                  Save business type
                </button>
              </div>
            ) : (
              <p className="muted">Platform Owner access is required to change business type.</p>
            )}

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
                  aria-label="Subscription package"
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
                  aria-label="Subscription term length"
                  required
                />
              </label>
              <label>
                <span>Term unit</span>
                <select
                  value={subForm.term_unit}
                  onChange={(e) => setSubForm((f) => ({ ...f, term_unit: e.target.value }))}
                  aria-label="Subscription term unit"
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
              <fieldset style={{ border: '1px solid var(--border, #ddd)', borderRadius: 8, padding: 10 }}>
                <legend>Store layout</legend>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input
                    type="radio"
                    name="assign-store-mode"
                    checked={
                      subForm.max_stores_override === '1' ||
                      (subForm.max_stores_override === '' &&
                        (packages.find((p) => p.code === subForm.package_code)?.max_stores ?? 1) === 1)
                    }
                    onChange={() => setSubForm((f) => ({ ...f, max_stores_override: '1' }))}
                    aria-label="Assign single store"
                  />
                  Single store
                </label>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input
                    type="radio"
                    name="assign-store-mode"
                    checked={
                      subForm.max_stores_override !== '1' &&
                      !(
                        subForm.max_stores_override === '' &&
                        (packages.find((p) => p.code === subForm.package_code)?.max_stores ?? 1) === 1
                      )
                    }
                    onChange={() =>
                      setSubForm((f) => ({
                        ...f,
                        max_stores_override: f.max_stores_override === '1' ? '10' : f.max_stores_override || '10',
                      }))
                    }
                    aria-label="Assign multi-store"
                  />
                  Multi-store (includes branches)
                </label>
                <label style={{ marginTop: 8 }}>
                  <span>Store entitlement override</span>
                  <input
                    type="number"
                    min={0}
                    placeholder="Package default"
                    value={subForm.max_stores_override}
                    onChange={(e) =>
                      setSubForm((f) => ({ ...f, max_stores_override: e.target.value }))
                    }
                    aria-label="Store entitlement override"
                  />
                </label>
              </fieldset>
              <button
                type="submit"
                disabled={busy === selected.id}
                aria-label="Assign package and term"
              >
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
              <span className="muted">Save store layout</span>
              <button
                type="button"
                disabled={busy === selected.id}
                aria-label="Save as single store"
                onClick={async () => {
                  setBusy(selected.id);
                  setError('');
                  try {
                    await api(`/tenants/${selected.slug || selected.id}/store-entitlement`, {
                      method: 'PATCH',
                      body: JSON.stringify({ max_stores_override: 1 }),
                    });
                    setOverrideDraft('1');
                    setMessage('Store entitlement set to Single store');
                    await refresh({ force: true });
                  } catch (err: any) {
                    setError(err.message || 'Override failed');
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                Single store
              </button>
              <button
                type="button"
                disabled={busy === selected.id}
                aria-label="Save as multi-store"
                onClick={async () => {
                  setBusy(selected.id);
                  setError('');
                  try {
                    const raw = overrideDraft.trim();
                    const n = raw === '' || Number(raw) <= 1 ? 10 : Number(raw);
                    await api(`/tenants/${selected.slug || selected.id}/store-entitlement`, {
                      method: 'PATCH',
                      body: JSON.stringify({ max_stores_override: n }),
                    });
                    setOverrideDraft(String(n));
                    setMessage('Store entitlement set to Multi-store');
                    await refresh({ force: true });
                  } catch (err: any) {
                    setError(err.message || 'Override failed');
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                Multi-store
              </button>
              <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span>max_stores_override</span>
                <input
                  type="number"
                  min={0}
                  placeholder="Clear / package"
                  value={overrideDraft}
                  onChange={(e) => setOverrideDraft(e.target.value)}
                  aria-label="Store entitlement override draft"
                  style={{ width: 120 }}
                />
              </label>
              <button
                type="button"
                disabled={busy === selected.id}
                aria-label="Save store entitlement override"
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
                    await refresh({ force: true });
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
              Modules offered here match {industryLabel(selected.industry)}. Shared ERP modules stay
              available when the plan includes them. Another industry&apos;s features are not listed.
              Dashboard, notifications, and security stay on.
            </p>
            {canDeleteTenant ? (
              <div className="plat-actions" style={{ marginTop: 8 }}>
                <button
                  type="button"
                  disabled={busy === selected.id}
                  onClick={() => resetTenantAdminPassword(selected)}
                  aria-label={`Reset administrator password for ${selected.company_name}`}
                >
                  Reset administrator password
                </button>
              </div>
            ) : null}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                gap: 8,
                marginTop: 12,
              }}
            >
              {packageable
                .filter((mod) => industryAllowsModule(selected.industry, mod))
                .map((mod) => {
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
                      border: '1px solid var(--line, #D4E5C4)',
                      borderRadius: 8,
                      opacity: locked ? 0.7 : 1,
                    }}
                  >
                    <input
                      type="checkbox"
                      aria-label={`Platform feature module ${mod}`}
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
              <button type="button" disabled={busy === selected.id} onClick={saveModules} aria-label="Save feature modules">
                Save feature modules
              </button>
              <button
                type="button"
                disabled={busy === selected.id}
                onClick={resetModules}
                aria-label="Reset feature modules to package default"
              >
                Reset to package default
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
