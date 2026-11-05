'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import PageHeader from '../../../../components/PageHeader';
import PageSkeleton from '../../../../components/PageSkeleton';
import EmptyState from '../../../../components/EmptyState';
import FormModal from '../../../../components/FormModal';
import RowActions from '../../../../components/RowActions';
import { Avatar, Drawer, Tabs, TenantStatus, moduleName, plainWords } from '../../../../components/PlatformUi';
import { api } from '../../../../lib/api';
import { getMe } from '../../../../lib/meCache';
import { getPrefetched } from '../../../../lib/prefetchCache';
import { formatNumber } from '../../../../lib/format';
import { AmountField } from '../../../../components/AmountField';
import { industryAllowsModule } from '../../../../lib/industryModules';
import { INDUSTRIES, PROVISION_INDUSTRIES, industryLabel } from '../../../../lib/industries';
import { subscriptionAmountLabel, subscriptionAmountToSend } from '../../../../lib/platformBilling';
import { useCompanyFormat } from '../../../../lib/useCompanyFormat';

/** New companies: Retail, Hotel, and Restaurant. */
const CREATE_INDUSTRIES = [...PROVISION_INDUSTRIES] as const;

function platformPackagesWriteDeniedMessage(raw: unknown): string | null {
  const text = String(raw || '');
  if (
    /platform_packages:write/i.test(text) ||
    (/package/i.test(text) && /contact/i.test(text) && /admin/i.test(text))
  ) {
    return 'Contact a platform admin or owner to assign a package or change feature modules.';
  }
  return null;
}

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
  admin_email?: string | null;
  ecommerce_health?: {
    entitled?: boolean;
    storefront_enabled?: boolean;
    open_orders?: number;
    domains?: { hostname: string; display_status?: string; https_ready?: boolean }[];
    connectors?: { platform: string; enabled?: boolean; last_error?: string | null }[];
    gateway?: { configured?: boolean; provider?: string | null; mode?: string };
  };
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

const LOCKED_MODULES = ['dashboard', 'notifications', 'security'];

function accountLabel(status?: string) {
  if (status === 'verified') return 'Verified';
  if (status === 'pending_verification') return 'Pending verification';
  if (status === 'no_administrator') return 'No administrator';
  return status || '—';
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
  const prefs = useCompanyFormat();
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [packages, setPackages] = useState<PackageInfo[]>([]);
  const [packageable, setPackageable] = useState<string[]>([]);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
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
    amount: '',
  });
  const [planAmounts, setPlanAmounts] = useState<Record<string, { amount: number | null; currency: string | null }>>({});
  const [moduleDraft, setModuleDraft] = useState<string[]>([]);
  const [suspendReason, setSuspendReason] = useState('');
  const [deleteConfirmSlug, setDeleteConfirmSlug] = useState('');
  const [adminPasswordDraft, setAdminPasswordDraft] = useState('');
  const [overrideDraft, setOverrideDraft] = useState('');
  const [industryDraft, setIndustryDraft] = useState('');
  const [industryReason, setIndustryReason] = useState('');
  const [meRole, setMeRole] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [suspendTarget, setSuspendTarget] = useState<TenantRow | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TenantRow | null>(null);
  const [manageTab, setManageTab] = useState('overview');
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
    // A password typed for one company must never carry over to the next one.
    setAdminPasswordDraft('');
    setManageTab('overview');
  }

  function closeManage() {
    setSelectedId(null);
    setAdminPasswordDraft('');
  }

  async function refresh(options?: { force?: boolean }) {
    const force = Boolean(options?.force);
    const [me, res, pkgs, directory] = await Promise.all([
      getMe({ force }),
      getPrefetched('/tenants', { force }),
      getPrefetched('/packages', { force }),
      api('/platform/directory'),
    ]);
    let billed: { data?: Array<{ slug?: string; amount?: number | null; currency?: string | null }> } = { data: [] };
    try {
      billed = await api('/platform/billing/companies');
    } catch {
      billed = { data: [] };
    }
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
    const amounts: Record<string, { amount: number | null; currency: string | null }> = {};
    for (const row of billed.data || []) {
      if (!row?.slug) continue;
      amounts[row.slug] = { amount: row.amount ?? null, currency: row.currency ?? null };
    }
    setPlanAmounts(amounts);
    setReady(true);
  }

  useEffect(() => {
    // The console links here with ?status=grace and similar.
    const wanted = new URLSearchParams(window.location.search).get('status') || '';
    if (['active', 'trial', 'grace', 'suspended'].includes(wanted)) setFilter(wanted);
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
    const billed = planAmounts[sel.slug];
    setSubForm({
      package_code: sel.package_code || sel.subscription?.package_code || 'professional',
      term_value: sel.subscription?.term_value || 12,
      term_unit: sel.subscription?.term_unit || 'months',
      start_at: '',
      amount: billed?.amount == null ? '' : formatNumber(billed.amount, prefs),
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
          prev.map((t) =>
            t.id === sel.id
              ? {
                  ...t,
                  ...row,
                  id: t.id,
                  slug: t.slug || row.slug,
                  admin_email: row.admin_email || t.admin_email || null,
                }
              : t
          )
        );
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
    () => {
      const needle = search.trim().toLowerCase();
      return tenants.filter(
        (t) =>
          (filter === 'all' || t.status === filter) &&
          (!needle ||
            String(t.company_name || '').toLowerCase().includes(needle) ||
            String(t.slug || '').toLowerCase().includes(needle)),
      );
    },
    [tenants, filter, search]
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
      setCreateOpen(false);
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
      setSuspendTarget(null);
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
      setDeleteTarget(null);
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
    const parsed = subscriptionAmountToSend(subForm.amount, subForm.package_code, prefs);
    if ('error' in parsed) {
      setError(parsed.error);
      setMessage('');
      return;
    }
    setBusy(selected.id);
    setError('');
    setMessage('');
    try {
      const body: Record<string, unknown> = {
        package_code: subForm.package_code,
        term_value: Number(subForm.term_value),
        term_unit: subForm.term_unit,
        activate: true,
        amount: parsed.amount,
      };
      if (subForm.start_at.trim()) body.start_at = subForm.start_at.trim();
      if (subForm.max_stores_override.trim() !== '') {
        body.max_stores_override = Number(subForm.max_stores_override);
      }
      const r = await api(`/tenants/${selected.slug || selected.id}/subscription`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      const shown = subscriptionAmountLabel(
        parsed.amount,
        planAmounts[selected.slug]?.currency || selected.currency,
        formatNumber(parsed.amount, prefs),
      );
      setMessage(
        `Assigned ${r.data?.subscription?.package_name || subForm.package_code} for ${subForm.term_value} ${subForm.term_unit} at ${shown} to ${selected.company_name}. No payment was recorded.`
      );
      await refresh({ force: true });
      setSelectedId(r.data?.id || selected.id);
    } catch (err: any) {
      setError(
        platformPackagesWriteDeniedMessage(err?.message) ||
          err.message ||
          'Assign subscription failed'
      );
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
      setError(
        platformPackagesWriteDeniedMessage(err?.message) ||
          err.message ||
          'Update modules failed'
      );
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
      setError(
        platformPackagesWriteDeniedMessage(err?.message) ||
          err.message ||
          'Reset modules failed'
      );
    } finally {
      setBusy(null);
    }
  }

  function toggleModule(mod: string) {
    if (LOCKED_MODULES.includes(mod)) return;
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
    const typed = adminPasswordDraft.trim();
    const adminEmail = target.admin_email || 'the company administrator';
    const ok = window.confirm(
      typed
        ? `Set a new password for ${adminEmail} on ${target.company_name}?\n\nTell them this password yourself. It is not shown again after you save.`
        : `Send a password reset link to ${adminEmail} on ${target.company_name}?\n\nLeave the temporary password blank to email a link instead.`
    );
    if (!ok) return;
    setBusy(target.id);
    setError('');
    setMessage('');
    try {
      const body = typed ? { new_password: typed } : {};
      const res = await api(`/tenants/${target.slug || target.id}/admin-password-reset`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      const when = res.data?.initiated_at ? ` at ${fmtDate(res.data.initiated_at)}` : '';
      const emailed = res.data?.email || adminEmail;
      setMessage(
        res.data?.password_set
          ? `Password updated for ${emailed} on ${target.company_name}${when}. Tell them the password you entered; it is not shown here.`
          : `Password reset link sent to ${emailed} for ${target.company_name}${when}.`
      );
      setAdminPasswordDraft('');
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message || 'Password reset failed');
    } finally {
      setBusy(null);
    }
  }

  if (!ready && !error) {
    return <PageSkeleton label="Loading tenants…" cards={3} />;
  }

  const sub = selected?.subscription;
  const assignPackage = packages.find((p) => p.code === subForm.package_code);
  const storesActive = selected?.subscription?.stores_active ?? selected?.store_usage?.stores_active ?? null;
  const storeLimit =
    selected?.subscription?.effective_store_limit ?? selected?.store_usage?.effective_store_limit ?? null;
  const overEntitlement = Boolean(
    selected?.subscription?.over_entitlement || selected?.store_usage?.over_entitlement,
  );
  const offeredModules = selected
    ? packageable.filter((mod) => industryAllowsModule(selected.industry, mod))
    : [];
  const enabledCount = offeredModules.filter(
    (mod) => moduleDraft.includes(mod) || LOCKED_MODULES.includes(mod),
  ).length;

  return (
    <>
      <div className="plat">
        <PageHeader
          className="plat-hero"
          kicker="Software owner"
          kickerClassName="plat-kicker"
          title="Tenants"
          subtitle="Create a workspace and manage its subscription, stores, and account. Paid self-serve checkout is not live — this page assigns entitlements only."
          subtitleClassName="plat-sub"
          actions={
            <button
              type="button"
              className="plat-cta"
              onClick={() => {
                setError('');
                setCreateOpen(true);
              }}
              aria-label="Open new tenant form"
            >
              New tenant
            </button>
          }
        />

        <div className="plat-toolbar">
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
                <span className="plat-chip-count">
                  {s === 'all' ? stats.total : stats[s as 'active' | 'trial' | 'grace' | 'suspended']}
                </span>
              </button>
            ))}
          </div>
          <div className="plat-search">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-3.5-3.5" />
            </svg>
            <input
              type="search"
              aria-label="Search tenants"
              placeholder="Search company or slug"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="plat-panel">
          <div className="plat-panel-head">
            <h2>Tenant management</h2>
            <span className="muted" style={{ fontSize: 13 }}>
              {visible.length} of {stats.total}
            </span>
          </div>
          <p className="plat-panel-sub">
            A new company admin stays inactive until they open the verification email. They sign in
            with that company&apos;s slug, not <code>platform</code>.
          </p>
          {visible.length === 0 ? (
            <EmptyState
              title={stats.total === 0 ? 'No tenants yet' : 'No tenants match'}
              detail={stats.total === 0 ? 'Create the first company to get started.' : 'Try another search or status.'}
            />
          ) : (
            <div className="plat-table-wrap is-open">
              <table className="table">
                <thead>
                  <tr>
                    <th>Tenant</th>
                    <th>Status</th>
                    <th className="plat-hide-sm">Plan</th>
                    <th className="plat-hide-sm">Industry</th>
                    <th className="plat-hide-md">Stores</th>
                    <th className="plat-hide-md">Users</th>
                    <th className="plat-hide-sm">Administrator</th>
                    <th className="plat-hide-lg">Created</th>
                    <th className="col-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((t) => {
                    const canBeRemoved = t.slug !== 'platform' && t.slug !== 'ribdigi-platform';
                    const verified = t.account_status === 'verified' || t.account_status === 'no_administrator';
                    return (
                      <tr key={t.id} className={selectedId === t.id ? 'plat-row-selected' : undefined}>
                        <td>
                          <div className="plat-who">
                            <Avatar name={t.company_name} />
                            <div>
                              <div className="plat-co">{t.company_name}</div>
                              <span className="plat-small">{t.slug}</span>
                            </div>
                          </div>
                        </td>
                        <td>
                          <TenantStatus status={t.status} />
                          {t.status === 'suspended' && t.suspended_reason ? (
                            <span className="plat-small" title={t.suspended_reason}>
                              {t.suspended_reason.length > 34
                                ? `${t.suspended_reason.slice(0, 34)}…`
                                : t.suspended_reason}
                            </span>
                          ) : null}
                        </td>
                        <td className="plat-hide-sm">
                          {t.subscription?.package_name || plainWords(t.package_code) || '—'}
                        </td>
                        <td className="plat-hide-sm">{industryLabel(t.industry)}</td>
                        <td className="plat-hide-md">
                          {t.store_count ?? 0} {t.store_count === 1 ? 'store' : 'stores'}
                          <span className="plat-small">
                            {t.store_mode === 'multi' ? 'Multi-store' : 'Single store'}
                          </span>
                        </td>
                        <td className="plat-hide-md">{t.user_count ?? '—'}</td>
                        <td className="plat-hide-sm">
                          <span className="plat-clip" title={t.admin_email || undefined}>
                            {t.admin_email || '—'}
                          </span>
                          <span className="plat-small">{accountLabel(t.account_status)}</span>
                        </td>
                        <td className="plat-hide-lg" style={{ whiteSpace: 'nowrap' }}>
                          {fmtDate(t.created_at)}
                        </td>
                        <td className="plat-actions-cell col-right">
                          <RowActions
                            label={`More actions for ${t.company_name}`}
                            items={[
                              {
                                key: 'manage',
                                label: 'Manage',
                                ariaLabel: `Manage tenant ${t.slug || t.id}`,
                                disabled: busy === t.id,
                                onClick: () => openManage(t),
                              },
                              {
                                key: 'resend',
                                label: 'Resend verification email',
                                ariaLabel: `Resend verification email for tenant ${t.slug || t.id}`,
                                disabled: busy === t.id,
                                hidden: verified,
                                onClick: () => resendAdminEmail(t),
                              },
                              {
                                key: 'verify',
                                label: 'Verify account',
                                ariaLabel: `Verify account for tenant ${t.slug || t.id}`,
                                variant: 'ok',
                                disabled: busy === t.id,
                                hidden: verified,
                                onClick: () => allowAdminSignIn(t),
                              },
                              {
                                key: 'password',
                                label: 'Reset admin password',
                                ariaLabel: `Reset administrator password for tenant ${t.slug || t.id}`,
                                disabled: busy === t.id,
                                hidden: !canDeleteTenant,
                                onClick: () => resetTenantAdminPassword(t),
                              },
                              {
                                key: 'status',
                                hidden: t.status !== 'suspended' && !canBeRemoved,
                                closeOnClick: true,
                                node:
                                  t.status === 'suspended' ? (
                                    <button type="button" className="btn-ok" disabled={busy === t.id} onClick={() => activateTenant(t)} aria-label={`Activate tenant ${t.id}`}>
                                      Activate
                                    </button>
                                  ) : (
                                    <button
                                      type="button"
                                      className="btn-danger"
                                      disabled={busy === t.id}
                                      onClick={() => {
                                        setError('');
                                        setSuspendReason('');
                                        setSuspendTarget(t);
                                      }}
                                      aria-label={`Suspend tenant ${t.id}`}
                                    >
                                      Suspend
                                    </button>
                                  ),
                              },
                              {
                                key: 'delete',
                                hidden: !canHardDeleteTenant || !canBeRemoved,
                                closeOnClick: true,
                                node: (
                                  <button
                                    type="button"
                                    className="btn-danger"
                                    disabled={busy === t.id}
                                    onClick={() => {
                                      setError('');
                                      setDeleteConfirmSlug('');
                                      setDeleteTarget(t);
                                    }}
                                    aria-label={`Delete tenant ${t.slug || t.id}`}
                                  >
                                    Delete
                                  </button>
                                ),
                              },
                            ]}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {createOpen ? (
          <FormModal
            title="Create tenant"
            busy={creating}
            dirty={Boolean(form.company_name.trim() || form.admin_email.trim() || form.admin_password.trim())}
            onClose={() => setCreateOpen(false)}
          >
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
                  aria-label="Tenant admin password"
                  autoComplete="new-password"
                  required
                />
                <small className="plat-hint">At least 8 characters with upper, lower, number, and symbol. No spaces.</small>
              </label>
              <fieldset>
                <legend>Store layout</legend>
                <div className="plat-radio-row">
                  <label className="plat-radio">
                    <input
                      type="radio"
                      name="create-store-mode"
                      checked={form.store_mode === 'single'}
                      onChange={() => setForm((f) => ({ ...f, store_mode: 'single' }))}
                      aria-label="Single store"
                    />
                    Single store
                  </label>
                  <label className="plat-radio">
                    <input
                      type="radio"
                      name="create-store-mode"
                      checked={form.store_mode === 'multi'}
                      onChange={() => setForm((f) => ({ ...f, store_mode: 'multi' }))}
                      aria-label="Multi-store"
                    />
                    Multi-store (includes branches)
                  </label>
                </div>
                {form.store_mode === 'multi' ? (
                  <label className="plat-field" style={{ marginTop: 10 }}>
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
                  <p className="plat-hint">
                    One operating store. Extra store create is blocked until you switch this tenant to
                    Multi-store.
                  </p>
                )}
              </fieldset>
              <div className="plat-form-actions">
                <button
                  type="submit"
                  disabled={creating || !form.admin_password.trim()}
                  aria-label="Create tenant"
                >
                  {creating ? 'Creating…' : 'Create tenant'}
                </button>
              </div>
            </form>
          </FormModal>
        ) : null}

        {suspendTarget ? (
          <FormModal
            title={`Suspend ${suspendTarget.company_name}`}
            busy={busy === suspendTarget.id}
            dirty={Boolean(suspendReason.trim())}
            onClose={() => setSuspendTarget(null)}
          >
            <form
              className="plat-form"
              style={{ gridTemplateColumns: 'minmax(0,1fr)' }}
              onSubmit={(e) => {
                e.preventDefault();
                suspendTenant(suspendTarget);
              }}
            >
              <p className="plat-note">
                Staff lose access until you activate this company again. The reason is saved as{' '}
                <code>suspended_reason</code>.
              </p>
              <label>
                <span>Suspend reason</span>
                <input
                  value={suspendReason}
                  onChange={(e) => setSuspendReason(e.target.value)}
                  placeholder="Required before Suspend"
                  title="Required suspend reason"
                  aria-label="Tenant suspend reason"
                />
              </label>
              <div className="plat-form-actions">
                <button
                  type="submit"
                  className="btn-danger plat-quiet"
                  disabled={busy === suspendTarget.id || !suspendReason.trim()}
                  aria-label="Confirm suspend tenant"
                >
                  Suspend company
                </button>
              </div>
            </form>
          </FormModal>
        ) : null}

        {deleteTarget ? (
          <FormModal
            title={`Delete ${deleteTarget.company_name}`}
            busy={busy === deleteTarget.id}
            dirty={Boolean(deleteConfirmSlug.trim())}
            onClose={() => setDeleteTarget(null)}
          >
            <form
              className="plat-form"
              style={{ gridTemplateColumns: 'minmax(0,1fr)' }}
              onSubmit={(e) => {
                e.preventDefault();
                deleteTenant(deleteTarget);
              }}
            >
              <p className="plat-note is-bad">
                Delete removes the company and its data. This cannot be undone.{' '}
                Only the software owner can delete a company.
              </p>
              <label>
                <span>
                  Type <code>{deleteTarget.slug}</code> to confirm
                </span>
                <input
                  value={deleteConfirmSlug}
                  onChange={(e) => setDeleteConfirmSlug(e.target.value)}
                  placeholder="Type the tenant slug"
                  aria-label="Delete tenant confirmation"
                  autoComplete="off"
                />
              </label>
              <div className="plat-form-actions">
                <button
                  type="submit"
                  className="btn-danger plat-quiet"
                  disabled={busy === deleteTarget.id || deleteConfirmSlug.trim() !== deleteTarget.slug}
                  aria-label="Confirm delete tenant"
                >
                  Delete company
                </button>
              </div>
            </form>
          </FormModal>
        ) : null}

        {selected && (
          <Drawer
            id="subscription-panel"
            title={selected.company_name}
            subtitle={`${selected.slug} · ${industryLabel(selected.industry)}`}
            badge={<TenantStatus status={selected.status} />}
            closeLabel="Close tenant management panel"
            busy={busy === selected.id}
            panelRef={managePanelRef}
            onClose={closeManage}
            tabs={
              <Tabs
                label="Tenant sections"
                active={manageTab}
                onChange={setManageTab}
                tabs={[
                  { key: 'overview', label: 'Overview' },
                  { key: 'subscription', label: 'Subscription' },
                  { key: 'stores', label: 'Stores' },
                  { key: 'modules', label: 'Feature modules', count: enabledCount },
                  { key: 'account', label: 'Account' },
                ]}
              />
            }
          >
            {manageTab === 'overview' ? (
              <>
                <div className="plat-section">
                  <h3>Subscription</h3>
                  <div className="plat-facts">
                    <div className="plat-fact">
                      <small>Package</small>
                      <strong>{sub?.package_name || plainWords(selected.package_code) || '—'}</strong>
                    </div>
                    <div className="plat-fact">
                      <small>Amount</small>
                      <strong>
                        {subscriptionAmountLabel(
                          planAmounts[selected.slug]?.amount,
                          planAmounts[selected.slug]?.currency || selected.currency,
                          planAmounts[selected.slug]?.amount == null
                            ? ''
                            : formatNumber(planAmounts[selected.slug]?.amount, prefs),
                        )}
                      </strong>
                    </div>
                    <div className="plat-fact">
                      <small>Renewal</small>
                      <strong>{fmtDate(sub?.subscription_ends_at)}</strong>
                    </div>
                    <div className="plat-fact">
                      <small>Assigned</small>
                      <strong>
                        {sub?.months_assigned ?? '—'} mo
                        {sub?.years_assigned != null ? ` / ${sub.years_assigned} y` : ''}
                      </strong>
                    </div>
                    <div className="plat-fact">
                      <small>Used</small>
                      <strong>
                        {sub?.months_used ?? 0} mo
                        {sub?.years_used != null ? ` / ${sub.years_used} y` : ''}
                      </strong>
                    </div>
                    <div className="plat-fact">
                      <small>Remaining</small>
                      <strong>
                        {sub?.months_remaining ?? '—'} mo
                        {sub?.days_remaining != null ? ` (${sub.days_remaining}d)` : ''}
                      </strong>
                    </div>
                  </div>
                </div>
                <div className="plat-section">
                  <h3>Contacts</h3>
                  <div className="plat-facts">
                    <div className="plat-fact">
                      <small>Administrator email</small>
                      <strong aria-label="Tenant administrator email">{selected.admin_email || '—'}</strong>
                    </div>
                    <div className="plat-fact">
                      <small>Account</small>
                      <strong>{accountLabel(selected.account_status)}</strong>
                    </div>
                    <div className="plat-fact">
                      <small>Created</small>
                      <strong>{fmtDate(selected.created_at)}</strong>
                    </div>
                    {selected.email && selected.email !== selected.admin_email ? (
                      <div className="plat-fact">
                        <small>Company contact</small>
                        <strong>{selected.email}</strong>
                      </div>
                    ) : null}
                  </div>
                </div>
                <div className="plat-section">
                  <h3>Online store</h3>
                  <p className="muted" style={{ fontSize: 13 }} aria-label="Tenant ecommerce health">
                    {selected.ecommerce_health
                      ? `${selected.ecommerce_health.entitled ? 'Entitled' : 'Not entitled'} · ${
                          selected.ecommerce_health.storefront_enabled ? 'enabled' : 'disabled'
                        } · ${(selected.ecommerce_health.domains || [])
                          .map((d) => `${d.hostname} ${d.display_status || ''}`)
                          .join(', ') || 'no domain'} · gateway ${
                          selected.ecommerce_health.gateway?.configured ? 'configured' : 'not configured'
                        }`
                      : 'Health not loaded'}
                  </p>
                </div>
              </>
            ) : null}

            {manageTab === 'subscription' ? (
              <div className="plat-section">
                <h3>Assign package and term</h3>
                <p className="muted" style={{ fontSize: 13 }}>
                  This changes the entitlement only. No payment is recorded.
                </p>
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
                    <span>Amount</span>
                    <AmountField
                      aria-label="Subscription amount"
                      currency={planAmounts[selected.slug]?.currency || selected.currency}
                      inputMode="decimal"
                      value={subForm.amount}
                      onChange={(e) => setSubForm((f) => ({ ...f, amount: e.target.value }))}
                      required
                    />
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
                      title="Start date (optional; today if blank)"
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
                      aria-label="Store entitlement override"
                    />
                  </label>
                  <fieldset>
                    <legend>Store layout</legend>
                    <div className="plat-radio-row">
                      <label className="plat-radio">
                        <input
                          type="radio"
                          name="assign-store-mode"
                          checked={
                            subForm.max_stores_override === '1' ||
                            (subForm.max_stores_override === '' && (assignPackage?.max_stores ?? 1) === 1)
                          }
                          onChange={() => setSubForm((f) => ({ ...f, max_stores_override: '1' }))}
                          aria-label="Assign single store"
                        />
                        Single store
                      </label>
                      <label className="plat-radio">
                        <input
                          type="radio"
                          name="assign-store-mode"
                          checked={
                            subForm.max_stores_override !== '1' &&
                            !(subForm.max_stores_override === '' && (assignPackage?.max_stores ?? 1) === 1)
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
                    </div>
                    <p className="plat-hint">
                      Package max stores: {assignPackage?.max_stores ?? '—'} (blank override = catalog /
                      unlimited for Enterprise).
                    </p>
                  </fieldset>
                  <div className="plat-form-actions">
                    <button
                      type="submit"
                      disabled={busy === selected.id}
                      aria-label="Assign package and term"
                    >
                      {busy === selected.id ? 'Saving…' : 'Assign package & term'}
                    </button>
                  </div>
                </form>
              </div>
            ) : null}

            {manageTab === 'stores' ? (
              <>
                <div className="plat-section">
                  <h3>Store usage</h3>
                  <div className="plat-facts">
                    <div className="plat-fact">
                      <small>Active stores</small>
                      <strong>
                        {storesActive ?? '—'} / {storeLimit ?? '∞'}
                      </strong>
                    </div>
                    <div className="plat-fact">
                      <small>Package max stores</small>
                      <strong>{sub?.package_max_stores ?? '—'}</strong>
                    </div>
                    <div className="plat-fact">
                      <small>Branches</small>
                      <strong>{selected.branch_count ?? 0}</strong>
                    </div>
                  </div>
                  {overEntitlement ? (
                    <p className="plat-note is-bad">
                      This company is over its store entitlement. Nothing is deleted, but new stores are
                      blocked until this is resolved.
                    </p>
                  ) : null}
                </div>
                <div className="plat-section">
                  <h3>Save store layout</h3>
                  <div className="plat-row-actions" style={{ justifyContent: 'flex-start' }}>
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
                  </div>
                  <div className="plat-inline">
                    <label className="plat-field">
                      <span>Store limit override</span>
                      <input
                        type="number"
                        min={0}
                        placeholder="Blank clears it back to the package"
                        value={overrideDraft}
                        onChange={(e) => setOverrideDraft(e.target.value)}
                        aria-label="Store entitlement override draft"
                      />
                    </label>
                    <button
                      type="button"
                      className="plat-cta"
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
                </div>
              </>
            ) : null}

            {manageTab === 'modules' ? (
              <div className="plat-section">
                <h3>Feature modules (package control)</h3>
                <p className="muted" style={{ fontSize: 13 }}>
                  Modules offered here match {industryLabel(selected.industry)}. Shared ERP modules stay
                  available when the plan includes them. Another industry&apos;s features are not listed.
                </p>
                <div className="plat-modules">
                  {packageable
                    .filter((mod) => industryAllowsModule(selected.industry, mod))
                    .map((mod) => {
                      const locked = LOCKED_MODULES.includes(mod);
                      const on = moduleDraft.includes(mod) || locked;
                      return (
                        <label key={mod} className={`plat-module${locked ? ' is-locked' : ''}`}>
                          <span>
                            {moduleName(mod)}
                            {locked ? <small>Always on</small> : null}
                          </span>
                          <input
                            type="checkbox"
                            role="switch"
                            aria-label={`Platform feature module ${mod}`}
                            checked={on}
                            disabled={locked}
                            onChange={() => toggleModule(mod)}
                          />
                        </label>
                      );
                    })}
                </div>
                <div className="plat-row-actions" style={{ justifyContent: 'flex-start' }}>
                  <button type="button" className="plat-cta" disabled={busy === selected.id} onClick={saveModules} aria-label="Save feature modules">
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
            ) : null}

            {manageTab === 'account' ? (
              <>
                <div className="plat-section">
                  <h3>Administrator password</h3>
                  {canDeleteTenant ? (
                    <>
                      <p className="muted" style={{ fontSize: 13 }}>
                        {selected.admin_email || 'No company administrator'}. Enter a temporary password
                        to set it for them, or leave blank to email a reset link. The password is never
                        shown back on this page.
                      </p>
                      <div className="plat-inline">
                        <label className="plat-field">
                          <span>Temporary password</span>
                          <input
                            type="password"
                            value={adminPasswordDraft}
                            onChange={(e) => setAdminPasswordDraft(e.target.value)}
                            placeholder="Leave blank to email a reset link"
                            aria-label="Tenant administrator temporary password"
                            autoComplete="new-password"
                          />
                        </label>
                        <button
                          type="button"
                          disabled={busy === selected.id}
                          onClick={() => resetTenantAdminPassword(selected)}
                          aria-label={`Reset administrator password for ${selected.company_name}`}
                        >
                          {adminPasswordDraft.trim() ? 'Set administrator password' : 'Email reset link'}
                        </button>
                      </div>
                    </>
                  ) : (
                    <p className="muted">Platform Owner access is required to reset this password.</p>
                  )}
                </div>
                <div className="plat-section">
                  <h3>Business type</h3>
                  <p className="muted" style={{ fontSize: 13 }}>
                    Current: {industryLabel(selected.industry)}. Only the Platform Owner can change this.
                    Choose Retail, Hotel, or Restaurant. APIs follow the saved industry immediately. Ask
                    staff to refresh or sign in again so the sidebar matches. Existing records are kept.
                  </p>
                  {canDeleteTenant ? (
                    <div className="plat-form">
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
                      <div className="plat-form-actions">
                        <button
                          type="button"
                          className="plat-cta"
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
                    </div>
                  ) : (
                    <p className="muted">Platform Owner access is required to change business type.</p>
                  )}
                </div>
              </>
            ) : null}
          </Drawer>
        )}

        {(error || message) && (
          <div className="plat-feedback-dock" aria-live="polite">
            {error ? (
              <div className="plat-toast is-bad" role="alert">
                <p>{error}</p>
                <button type="button" aria-label="Dismiss error" onClick={() => setError('')}>
                  ×
                </button>
              </div>
            ) : null}
            {message ? (
              <div className="plat-toast" role="status">
                <p>{message}</p>
                <button type="button" aria-label="Dismiss message" onClick={() => setMessage('')}>
                  ×
                </button>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </>
  );
}
