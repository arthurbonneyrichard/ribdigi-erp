'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';

type TenantRow = {
  id: string;
  slug: string;
  company_name: string;
  status: string;
  plan_code?: string;
  user_count?: number;
  store_count?: number;
  created_at?: string;
};

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
  const [items, setItems] = useState<TenantRow[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [creating, setCreating] = useState(false);

  async function load() {
    setError('');
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set('q', q.trim());
      if (status) params.set('status', status);
      const r = await api(`/platform/tenants?${params.toString()}`);
      setItems(r.data?.items || []);
      setTotal(r.data?.total || 0);
    } catch (err: any) {
      setError(err.message || 'Failed to load tenants');
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
          <option value="trial">trial</option>
          <option value="starter">starter</option>
          <option value="growth">growth</option>
          <option value="enterprise">enterprise</option>
        </select>
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
          placeholder="Search slug or name"
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
        <button type="submit" style={{ padding: '10px 14px', borderRadius: 8, background: '#111827', color: '#fff', border: 0 }}>
          Search
        </button>
      </form>
      {error && <p>{error}</p>}
      {msg && <p style={{ color: '#047857' }}>{msg}</p>}
      <p className="muted">{total} tenant(s)</p>
      <table className="table">
        <thead>
          <tr>
            <th>Company</th>
            <th>Slug</th>
            <th>Status</th>
            <th>Plan</th>
            <th>Users</th>
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
              <td>{t.user_count ?? 0}</td>
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
              <td colSpan={6} className="muted">
                No customer tenants found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </PlatformShell>
  );
}
