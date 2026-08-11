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

export default function PlatformTenantsPage() {
  const [items, setItems] = useState<TenantRow[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

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

  return (
    <PlatformShell>
      <h1>Customer tenants</h1>
      <p className="muted">Suspend and activate customer companies. Platform tenant is never listed.</p>
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
