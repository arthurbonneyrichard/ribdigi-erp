'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
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
  const [items, setItems] = useState<TenantRow[]>([]);
  const [atRisk, setAtRisk] = useState<TenantRow[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState(() => searchParams.get('status') || '');
  const [planCode, setPlanCode] = useState('');
  const [industry, setIndustry] = useState('');
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [creating, setCreating] = useState(false);
  const [catalog, setCatalog] = useState<PlanItem[]>([]);
  const [formats, setFormats] = useState(HOUSE_FORMAT_DEFAULTS);

  const selectedPlan = catalog.find((p) => p.code === form.plan_code);

  async function load(nextStatus?: string) {
    setError('');
    const statusFilter = nextStatus !== undefined ? nextStatus : status;
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set('q', q.trim());
      if (statusFilter) params.set('status', statusFilter);
      if (planCode) params.set('plan_code', planCode);
      if (industry) params.set('industry', industry);
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
  }, []);

  useEffect(() => {
    const fromQuery = searchParams.get('status') || '';
    setStatus(fromQuery);
    load(fromQuery);
    if (searchParams.get('focus') === 'at-risk') {
      const el = document.getElementById('at-risk-queue');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
          placeholder="Search slug, name, admin email, or notes"
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1', minWidth: 200 }}
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
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
          onChange={(e) => setIndustry(e.target.value)}
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
        >
          <option value="">All industries</option>
          <option value="retail">retail</option>
          <option value="pharmacy">pharmacy</option>
          <option value="restaurant">restaurant</option>
          <option value="bakery">bakery</option>
          <option value="wholesale">wholesale</option>
          <option value="manufacturing">manufacturing</option>
          <option value="mart">mart</option>
        </select>
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

      <h2 id="at-risk-queue" style={{ fontSize: 16, marginTop: 24 }}>
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
