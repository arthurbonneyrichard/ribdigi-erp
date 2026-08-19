'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';
import { formatDateTime } from '../../../lib/format';
import { fetchHouseFormats, HOUSE_FORMAT_DEFAULTS } from '../../../lib/houseFormats';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type RosterItem = {
  tenant_id: string;
  slug: string;
  company_name: string;
  status: string;
  plan_code: string;
  industry?: string | null;
  admin_email?: string | null;
  user_count?: number;
  store_count?: number;
  trial_ends_at?: string | null;
  grace_ends_at?: string | null;
  created_at?: string | null;
  billing?: string;
};

function fmtTs(
  value: string | null | undefined,
  formats: { date_format?: string | null; time_format?: string | null },
) {
  return formatDateTime(value, formats.date_format, formats.time_format);
}

export default function PlatformBillingPage() {
  const [data, setData] = useState<any>(null);
  const [roster, setRoster] = useState<RosterItem[]>([]);
  const [error, setError] = useState('');
  const [formats, setFormats] = useState(HOUSE_FORMAT_DEFAULTS);

  useEffect(() => {
    fetchHouseFormats().then(setFormats);
    Promise.all([api('/platform/billing'), api('/platform/subscriptions')])
      .then(([billing, subs]) => {
        setData(billing.data);
        const items = subs.data?.items || billing.data?.active_subscriptions || [];
        setRoster(Array.isArray(items) ? items : []);
      })
      .catch((err) => setError(err.message || 'Failed to load'));
  }, []);

  async function downloadSubscriptionsCsv() {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/platform/subscriptions/export`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Subscriptions export failed');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'platform_subscriptions_export.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || 'Export failed');
    }
  }

  return (
    <PlatformShell>
      <h1>Billing</h1>
      <p className="muted">
        House subscriptions roster — tenant×plan commercial metadata (ADR-002 billing deferred).
        Export via <code>GET /platform/subscriptions/export</code> (Stage 150 R1).
      </p>
      {error && <p>{error}</p>}
      {data && (
        <div className="card" style={{ marginTop: 16, maxWidth: 720 }}>
          <p>
            <strong>Status:</strong> {data.deferred ? 'Deferred (ADR-002)' : 'Active'}
          </p>
          <p>{data.message}</p>
          <p className="muted" style={{ marginTop: 12 }}>
            Provider: {data.provider ?? 'none'} · MRR: {data.mrr == null ? 'n/a' : data.mrr} ·
            Checkout: {data.checkout_enabled ? 'enabled' : 'disabled'} · Live subscriptions:{' '}
            {data.subscriptions_live ? 'yes' : 'no'}
          </p>
          {Array.isArray(data.plan_codes) && (
            <p className="muted">Plan codes (metadata only): {data.plan_codes.join(', ')}</p>
          )}
        </div>
      )}

      <div className="card" style={{ marginTop: 20 }}>
        <h2 style={{ fontSize: 18, marginTop: 0 }}>Subscriptions roster</h2>
        <p className="muted">
          Customer tenants with assigned plan codes. Not checkout, not fabricated MRR.
        </p>
        <div style={{ marginBottom: 12 }}>
          <button type="button" onClick={downloadSubscriptionsCsv}>
            Export subscriptions CSV
          </button>
        </div>
        {roster.length === 0 ? (
          <p className="muted">No customer tenants yet</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Slug</th>
                <th>Status</th>
                <th>Plan</th>
                <th>Industry</th>
                <th>Admin</th>
                <th>Users</th>
                <th>Stores</th>
                <th>Trial ends</th>
                <th>Grace ends</th>
                <th>Created</th>
                <th>Billing</th>
              </tr>
            </thead>
            <tbody>
              {roster.map((row) => (
                <tr key={row.tenant_id}>
                  <td>
                    <Link href={`/platform/tenants/${row.tenant_id}`}>{row.company_name}</Link>
                  </td>
                  <td>{row.slug}</td>
                  <td>{row.status}</td>
                  <td>{row.plan_code}</td>
                  <td>{row.industry || '—'}</td>
                  <td className="muted">{row.admin_email || '—'}</td>
                  <td>{row.user_count ?? '—'}</td>
                  <td>{row.store_count ?? '—'}</td>
                  <td>{fmtTs(row.trial_ends_at, formats)}</td>
                  <td>{fmtTs(row.grace_ends_at, formats)}</td>
                  <td>{fmtTs(row.created_at, formats)}</td>
                  <td>{row.billing || 'deferred'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </PlatformShell>
  );
}
