'use client';

import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { DonutChart } from '../../../components/DashboardCharts';
import { api } from '../../../lib/api';

type PlansPayload = {
  deferred_billing?: boolean;
  mrr?: number | null;
  checkout_enabled?: boolean;
  message?: string;
  plan_codes?: string[];
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

  return (
    <PlatformShell>
      <h1>Plans</h1>
      <p className="muted">
        RIBDIGI ERP · Plan codes are commercial metadata only (billing deferred — ADR-002).
      </p>
      {error && <p>{error}</p>}
      {loading && <p className="muted">Loading plans…</p>}
      {data.message && <p className="muted" style={{ marginTop: 12 }}>{data.message}</p>}
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
          <div className="muted">Tenants with plans</div>
          <div className="kpi">{data.distribution?.total ?? '—'}</div>
        </div>
      </div>
      <div className="grid" style={{ marginTop: 20 }}>
        <div className="card">
          <h2 style={{ fontSize: 16 }}>Plan codes</h2>
          <ul>
            {(data.plan_codes || []).map((code) => (
              <li key={code}>{code}</li>
            ))}
          </ul>
          <p className="muted" style={{ marginTop: 8 }}>
            Assign a tenant plan from the tenant detail page (metadata PATCH only).
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
