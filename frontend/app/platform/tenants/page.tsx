'use client';

import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';
import { formatDateTime } from '../../../lib/format';
import { fetchHouseFormats, HOUSE_FORMAT_DEFAULTS } from '../../../lib/houseFormats';

type TenantRow = {
  id: string;
  slug: string;
  company_name: string;
  status: string;
  plan_code?: string;
  user_count?: number;
  store_count?: number;
  created_at?: string;
  days_remaining?: number | null;
  risk_ends_at?: string;
  last_house_email_delivery?: {
    created_at?: string | null;
    sent?: boolean;
    mode?: string;
    purpose?: string;
  } | null;
};

type PlanItem = {
  code: string;
  label?: string;
  blurb?: string;
  soft_limits?: { stores?: number | null; users?: number | null };
};

type IndustryItem = { code: string; label?: string };

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const emptyForm = {
  company_name: '',
  slug: '',
  admin_email: '',
  admin_password: '',
  admin_full_name: 'Company Administrator',
  industry: 'retail',
  currency: 'GHS',
  plan_code: 'trial',
};

export default function PlatformTenantsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [items, setItems] = useState<TenantRow[]>([]);
  const [atRisk, setAtRisk] = useState<TenantRow[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState(() => searchParams.get('q') || '');
  const [status, setStatus] = useState(() => searchParams.get('status') || '');
  const [planCode, setPlanCode] = useState(() => searchParams.get('plan_code') || '');
  const [industry, setIndustry] = useState(() => searchParams.get('industry') || '');
  const [createdThisMonth, setCreatedThisMonth] = useState(
    () => searchParams.get('created_this_month') === 'true',
  );
  const [focusAtRisk, setFocusAtRisk] = useState(() => searchParams.get('focus') === 'at-risk');
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [creating, setCreating] = useState(false);
  const [catalog, setCatalog] = useState<PlanItem[]>([]);
  const [industries, setIndustries] = useState<IndustryItem[]>([]);
  const [formats, setFormats] = useState(HOUSE_FORMAT_DEFAULTS);

  const selectedPlan = catalog.find((p) => p.code === form.plan_code);

  function syncUrl(next: {
    q?: string;
    status?: string;
    planCode?: string;
    industry?: string;
    createdThisMonth?: boolean;
    focusAtRisk?: boolean;
  }) {
    const params = new URLSearchParams();
    const nq = next.q !== undefined ? next.q : q;
    const ns = next.status !== undefined ? next.status : status;
    const np = next.planCode !== undefined ? next.planCode : planCode;
    const ni = next.industry !== undefined ? next.industry : industry;
    const nm = next.createdThisMonth !== undefined ? next.createdThisMonth : createdThisMonth;
    const nf = next.focusAtRisk !== undefined ? next.focusAtRisk : focusAtRisk;
    if (nq.trim()) params.set('q', nq.trim());
    if (ns) params.set('status', ns);
    if (np) params.set('plan_code', np);
    if (ni) params.set('industry', ni);
    if (nm) params.set('created_this_month', 'true');
    if (nf) params.set('focus', 'at-risk');
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  }

  async function load(overrides?: {
    q?: string;
    status?: string;
    planCode?: string;
    industry?: string;
    createdThisMonth?: boolean;
  }) {
    setError('');
    const qf = overrides?.q !== undefined ? overrides.q : q;
    const statusFilter = overrides?.status !== undefined ? overrides.status : status;
    const planFilter = overrides?.planCode !== undefined ? overrides.planCode : planCode;
    const industryFilter = overrides?.industry !== undefined ? overrides.industry : industry;
    const monthFilter =
      overrides?.createdThisMonth !== undefined ? overrides.createdThisMonth : createdThisMonth;
    try {
      const params = new URLSearchParams();
      if (qf.trim()) params.set('q', qf.trim());
      if (statusFilter) params.set('status', statusFilter);
      if (planFilter) params.set('plan_code', planFilter);
      if (industryFilter) params.set('industry', industryFilter);
      if (monthFilter) params.set('created_this_month', 'true');
      const r = await api(`/platform/tenants?${params.toString()}`);
      setItems(r.data?.items || []);
      setTotal(r.data?.total || 0);
      const risk = await api('/platform/tenants/at-risk?within_days=14');
      setAtRisk(risk.data?.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load tenants');
    }
  }

  useEffect(() => {
    fetchHouseFormats().then(setFormats);
    api('/platform/plans')
      .then((r) => setCatalog(r.data?.catalog || []))
      .catch(() => setCatalog([]));
    api('/platform/industries')
      .then((r) => setIndustries(r.data?.catalog || []))
      .catch(() => setIndustries([]));
  }, []);

  useEffect(() => {
    const fromStatus = searchParams.get('status') || '';
    const fromQ = searchParams.get('q') || '';
    const fromPlan = searchParams.get('plan_code') || '';
    const fromIndustry = searchParams.get('industry') || '';
    const fromMonth = searchParams.get('created_this_month') === 'true';
    const fromFocus = searchParams.get('focus') === 'at-risk';
    setStatus(fromStatus);
    setQ(fromQ);
    setPlanCode(fromPlan);
    setIndustry(fromIndustry);
    setCreatedThisMonth(fromMonth);
    setFocusAtRisk(fromFocus);
    load({
      q: fromQ,
      status: fromStatus,
      planCode: fromPlan,
      industry: fromIndustry,
      createdThisMonth: fromMonth,
    });
    if (fromFocus) {
      const el = document.getElementById('at-risk-queue');
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        el.focus();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  async function setLifecycle(id: string, action: 'suspend' | 'activate') {
    setBusy(id);
    setError('');
    try {
      await api(`/platform/tenants/${id}/${action}`, { method: 'POST', body: '{}' });
      await load();
    } catch (err: any) {
      setError(err.message || `Failed to ${action}`);
    } finally {
      setBusy(null);
    }
  }

  async function provisionTenant(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError('');
    setMsg('');
    try {
      const r = await api('/platform/tenants', {
        method: 'POST',
        body: JSON.stringify(form),
      });
      setForm(emptyForm);
      setMsg(`Provisioned ${r.data?.slug || 'tenant'} (${r.data?.status || 'trial'})`);
      await load();
    } catch (err: any) {
      setError(err.message || 'Provision failed');
    } finally {
      setCreating(false);
    }
  }

  async function exportFmt(fmt: 'csv' | 'pdf') {
    setError('');
    setMsg('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const params = new URLSearchParams();
      if (q.trim()) params.set('q', q.trim());
      if (status) params.set('status', status);
      if (planCode) params.set('plan_code', planCode);
      if (industry) params.set('industry', industry);
      if (createdThisMonth) params.set('created_this_month', 'true');
      params.set('format', fmt);
      const res = await fetch(`${apiBase}/platform/tenants/export?${params}`, {
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          'X-Tenant-ID': tenant || '',
        },
      });
      if (!res.ok) throw new Error(`${fmt.toUpperCase()} export failed`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `platform-tenants.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
      setMsg(`${fmt.toUpperCase()} downloaded`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <PlatformShell>
      <h1>Customer tenants</h1>
      <p className="muted">
        Provision, suspend, and activate customer companies. Platform tenant is never listed.
        Public self-serve registration remains at /register.
      </p>

      <form onSubmit={provisionTenant} className="card" style={{ marginTop: 16, maxWidth: 520 }}>
        <h2 style={{ fontSize: 16, marginTop: 0 }}>Provision tenant</h2>
        <p className="muted">Requires platform_super_admin. Creates Tenant Admin + trial defaults.</p>
        <input
          value={form.company_name}
          onChange={(e) => setForm({ ...form, company_name: e.target.value })}
          placeholder="Company name"
          required
          style={{ width: '100%', padding: 10, margin: '6px 0', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <input
          value={form.slug}
          onChange={(e) => setForm({ ...form, slug: e.target.value })}
          placeholder="Slug (e.g. acme)"
          required
          style={{ width: '100%', padding: 10, margin: '6px 0', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <input
          value={form.admin_full_name}
          onChange={(e) => setForm({ ...form, admin_full_name: e.target.value })}
          placeholder="Tenant Admin full name"
          style={{ width: '100%', padding: 10, margin: '6px 0', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <input
          value={form.admin_email}
          onChange={(e) => setForm({ ...form, admin_email: e.target.value })}
          placeholder="Tenant Admin email"
          type="email"
          required
          style={{ width: '100%', padding: 10, margin: '6px 0', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <input
          value={form.admin_password}
          onChange={(e) => setForm({ ...form, admin_password: e.target.value })}
          placeholder="Temporary admin password"
          type="password"
          required
          style={{ width: '100%', padding: 10, margin: '6px 0', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <select
          value={form.industry}
          onChange={(e) => setForm({ ...form, industry: e.target.value })}
          style={{ width: '100%', padding: 10, margin: '6px 0', borderRadius: 8, border: '1px solid #cbd5e1' }}
        >
          {(industries.length
            ? industries
            : [
                { code: 'retail' },
                { code: 'pharmacy' },
                { code: 'restaurant' },
                { code: 'bakery' },
                { code: 'wholesale' },
                { code: 'manufacturing' },
                { code: 'mart' },
              ]
          ).map((i) => (
            <option key={i.code} value={i.code}>
              {i.label || i.code}
            </option>
          ))}
        </select>
        <select
          value={form.plan_code}
          onChange={(e) => setForm({ ...form, plan_code: e.target.value })}
          style={{ width: '100%', padding: 10, margin: '6px 0', borderRadius: 8, border: '1px solid #cbd5e1' }}
        >
          {(catalog.length
            ? catalog
            : [
                { code: 'trial' },
                { code: 'starter' },
                { code: 'growth' },
                { code: 'enterprise' },
              ]
          ).map((p) => (
            <option key={p.code} value={p.code}>
              {p.label || p.code}
            </option>
          ))}
        </select>
        {selectedPlan && (
          <p className="muted" style={{ margin: '4px 0 12px', fontSize: 13 }}>
            {selectedPlan.blurb || selectedPlan.label || selectedPlan.code}
            {selectedPlan.soft_limits
              ? ` · Soft limits (metadata only): users=${
                  selectedPlan.soft_limits.users ?? 'unlimited'
                }, stores=${selectedPlan.soft_limits.stores ?? 'unlimited'}`
              : ''}
            . Not checkout entitlements.
          </p>
        )}
        <button
          type="submit"
          disabled={creating}
          style={{ padding: '10px 14px', borderRadius: 8, background: '#111827', color: '#fff', border: 0 }}
        >
          {creating ? 'Provisioning…' : 'Provision tenant'}
        </button>
      </form>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
        style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '16px 0' }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search slug, name, admin email, notes, or suspend reason"
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1', minWidth: 200 }}
        />
        <select
          value={status}
          onChange={(e) => {
            const v = e.target.value;
            setStatus(v);
            syncUrl({ status: v });
          }}
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
        >
          <option value="">All statuses</option>
          <option value="active">active</option>
          <option value="trial">trial</option>
          <option value="grace">grace</option>
          <option value="suspended">suspended</option>
        </select>
        <select
          value={planCode}
          onChange={(e) => setPlanCode(e.target.value)}
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
        >
          <option value="">All plans</option>
          <option value="trial">trial</option>
          <option value="starter">starter</option>
          <option value="growth">growth</option>
          <option value="enterprise">enterprise</option>
        </select>
        <select
          value={industry}
          onChange={(e) => {
            const v = e.target.value;
            setIndustry(v);
            syncUrl({ industry: v });
          }}
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
        >
          <option value="">All industries</option>
          {(industries.length
            ? industries
            : [
                { code: 'retail' },
                { code: 'pharmacy' },
                { code: 'restaurant' },
                { code: 'bakery' },
                { code: 'wholesale' },
                { code: 'manufacturing' },
                { code: 'mart' },
              ]
          ).map((i) => (
            <option key={i.code} value={i.code}>
              {i.label || i.code}
            </option>
          ))}
        </select>
        <label className="muted" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input
            type="checkbox"
            checked={createdThisMonth}
            onChange={(e) => {
              const v = e.target.checked;
              setCreatedThisMonth(v);
              syncUrl({ createdThisMonth: v });
            }}
          />
          Created this month
        </label>
        <button type="submit" style={{ padding: '10px 14px', borderRadius: 8, background: '#111827', color: '#fff', border: 0 }}>
          Search
        </button>
        <button type="button" onClick={() => exportFmt('csv')}>
          Export CSV
        </button>
        <button type="button" onClick={() => exportFmt('pdf')}>
          Export PDF
        </button>
      </form>
      {error && <p>{error}</p>}
      {msg && <p style={{ color: '#047857' }}>{msg}</p>}

      <h2
        id="at-risk-queue"
        tabIndex={-1}
        style={{
          fontSize: 16,
          marginTop: 24,
          outline: focusAtRisk ? '2px solid #2563eb' : undefined,
          background: focusAtRisk ? '#eff6ff' : undefined,
          padding: focusAtRisk ? 8 : undefined,
          borderRadius: focusAtRisk ? 8 : undefined,
        }}
      >
        At-risk (trial/grace within 14 days)
      </h2>
      <p className="muted">{atRisk.length} tenant(s) in queue</p>
      <table className="table">
        <thead>
          <tr>
            <th>Company</th>
            <th>Status</th>
            <th>Ends</th>
            <th>Days left</th>
          </tr>
        </thead>
        <tbody>
          {atRisk.map((t) => (
            <tr key={t.id}>
              <td>
                <Link href={`/platform/tenants/${t.id}`}>{t.company_name}</Link>
              </td>
              <td>
                <span className="badge">{t.status}</span>
              </td>
              <td>{t.risk_ends_at || '—'}</td>
              <td>{t.days_remaining ?? '—'}</td>
            </tr>
          ))}
          {atRisk.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                No at-risk tenants in the 14-day window.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <p className="muted" style={{ marginTop: 24 }}>
        {total} tenant(s)
      </p>
      <table className="table">
        <thead>
          <tr>
            <th>Company</th>
            <th>Slug</th>
            <th>Status</th>
            <th>Plan</th>
            <th>Industry</th>
            <th>Users</th>
            <th>Last House email</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((t) => (
            <tr key={t.id}>
              <td>
                <Link href={`/platform/tenants/${t.id}`}>{t.company_name}</Link>
              </td>
              <td>{t.slug}</td>
              <td>
                <span className="badge">{t.status}</span>
              </td>
              <td>{t.plan_code || '—'}</td>
              <td>{(t as any).industry || '—'}</td>
              <td>{t.user_count ?? 0}</td>
              <td className="muted" style={{ fontSize: 13 }}>
                {t.last_house_email_delivery?.created_at
                  ? `${formatDateTime(
                      t.last_house_email_delivery.created_at,
                      formats.date_format,
                      formats.time_format,
                    )} · sent=${String(t.last_house_email_delivery.sent)}`
                  : '—'}
              </td>
              <td style={{ display: 'flex', gap: 8 }}>
                {t.status !== 'suspended' ? (
                  <button
                    type="button"
                    disabled={busy === t.id}
                    onClick={() => setLifecycle(t.id, 'suspend')}
                  >
                    Suspend
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={busy === t.id}
                    onClick={() => setLifecycle(t.id, 'activate')}
                  >
                    Activate
                  </button>
                )}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={8} className="muted">
                No customer tenants found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </PlatformShell>
  );
}
