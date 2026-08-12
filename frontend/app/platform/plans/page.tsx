'use client';

import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { DonutChart } from '../../../components/DashboardCharts';
import { api } from '../../../lib/api';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type PlanItem = {
  code: string;
  label?: string;
  blurb?: string;
  soft_limits?: { stores?: number | null; users?: number | null };
};

type PlansPayload = {
  deferred_billing?: boolean;
  mrr?: number | null;
  checkout_enabled?: boolean;
  subscriptions_live?: boolean;
  message?: string;
  plan_codes?: string[];
  catalog?: PlanItem[];
  distribution?: { slices?: { plan_code: string; count: number }[]; total?: number };
};

export default function PlatformPlansPage() {
  const [data, setData] = useState<PlansPayload>({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api('/platform/plans')
      .then((r) => setData(r.data || {}))
      .catch((err) => setError(err.message || 'Failed to load'))
      .finally(() => setLoading(false));
  }, []);

  async function downloadPlansCsv() {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/platform/plans/export`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Plans export failed');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'platform_plans_export.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || 'Export failed');
    }
  }

  const catalog: PlanItem[] = data.catalog?.length
    ? data.catalog
    : (data.plan_codes || []).map((code) => ({ code }));

  return (
    <PlatformShell>
      <h1>Plans</h1>
      <p className="muted">
        RIBDIGI ERP · Plan codes are commercial metadata only (billing deferred — ADR-002). No
        prices, checkout, or fabricated MRR. Export via <code>GET /platform/plans/export</code>{' '}
        (Stage 150 P1).
      </p>
      {error && <p>{error}</p>}
      {loading && <p className="muted">Loading plans…</p>}
      {data.message && <p className="muted" style={{ marginTop: 12 }}>{data.message}</p>}
      <div style={{ marginTop: 12 }}>
        <button type="button" onClick={downloadPlansCsv}>
          Export plans CSV
        </button>
      </div>
      <div className="grid" style={{ marginTop: 20 }}>
        <div className="card">
          <div className="muted">Billing</div>
          <div className="kpi">{data.deferred_billing ? 'Deferred' : '—'}</div>
        </div>
        <div className="card">
          <div className="muted">MRR</div>
          <div className="kpi">{data.mrr == null ? 'n/a' : data.mrr}</div>
        </div>
        <div className="card">
          <div className="muted">Checkout</div>
          <div className="kpi">{data.checkout_enabled ? 'On' : 'Off'}</div>
        </div>
        <div className="card">
          <div className="muted">Live subscriptions</div>
          <div className="kpi">{data.subscriptions_live ? 'yes' : 'no'}</div>
        </div>
        <div className="card">
          <div className="muted">Tenants with plans</div>
          <div className="kpi">{data.distribution?.total ?? '—'}</div>
        </div>
      </div>
      <div className="grid" style={{ marginTop: 20 }}>
        <div className="card">
          <h2 style={{ fontSize: 16 }}>Plan catalog (metadata)</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Label</th>
                <th>Description</th>
                <th>Soft limits</th>
              </tr>
            </thead>
            <tbody>
              {catalog.map((p) => (
                <tr key={p.code}>
                  <td>{p.code}</td>
                  <td>{p.label || p.code}</td>
                  <td>{p.blurb || '—'}</td>
                  <td>
                    stores: {p.soft_limits?.stores ?? 'n/a'} · users:{' '}
                    {p.soft_limits?.users ?? 'n/a'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted" style={{ marginTop: 8 }}>
            Assign a tenant plan from the tenant detail page (metadata PATCH only). Soft limits are
            informational — not enforced checkout entitlements.
          </p>
        </div>
        <div className="card">
          <DonutChart
            title="Tenants by plan"
            slices={(data.distribution?.slices || []).map((s) => ({
              label: s.plan_code,
              value: s.count,
            }))}
          />
        </div>
      </div>
    </PlatformShell>
  );
}
