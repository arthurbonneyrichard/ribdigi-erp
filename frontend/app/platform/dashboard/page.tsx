'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { BarChart, DonutChart } from '../../../components/DashboardCharts';
import { api } from '../../../lib/api';

type Dash = {
  total_tenants?: number;
  active_tenants?: number;
  trial_tenants?: number;
  grace_tenants?: number;
  suspended_tenants?: number;
  at_risk_count?: number;
  at_risk_within_days?: number;
  new_tenants_this_month?: number;
  platform_users?: number;
  customer_users?: number;
  billing?: { deferred?: boolean; message?: string; mrr?: number | null };
  tenant_growth?: { series?: { month: string; tenants: number }[] };
  tenant_status?: { slices?: { status: string; count: number }[] };
  plan_distribution?: { slices?: { plan_code: string; count: number }[] };
  industry_distribution?: { slices?: { industry: string; count: number }[] };
  user_growth?: { series?: { month: string; users: number }[] };
  generated_at?: string;
};

export default function PlatformDashboardPage() {
  const [d, setD] = useState<Dash>({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api('/platform/dashboard')
      .then((r) => setD(r.data || {}))
      .catch((err) => setError(err.message || 'Failed to load'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <PlatformShell>
      <h1>Platform Administration</h1>
      <p className="muted">RIBDIGI ERP · A Ribdigi House Product — customer tenant overview (real aggregates).</p>
      {error && <p>{error}</p>}
      {loading && <p className="muted">Loading platform metrics…</p>}
      <div className="grid" style={{ marginTop: 20 }}>
        <div className="card">
          <div className="muted">Total tenants</div>
          <div className="kpi">{d.total_tenants ?? '—'}</div>
        </div>
        <div className="card">
          <div className="muted">Active</div>
          <div className="kpi">{d.active_tenants ?? '—'}</div>
        </div>
        <div className="card">
          <div className="muted">Trial</div>
          <div className="kpi">{d.trial_tenants ?? '—'}</div>
        </div>
        <div className="card">
          <div className="muted">Grace</div>
          <div className="kpi">{d.grace_tenants ?? '—'}</div>
        </div>
        <div className="card">
          <div className="muted">At-risk ({d.at_risk_within_days ?? 14}d)</div>
          <div className="kpi">{d.at_risk_count ?? '—'}</div>
          <p style={{ marginTop: 8 }}>
            <Link href="/platform/tenants">View tenants / at-risk queue →</Link>
          </p>
        </div>
        <div className="card">
          <div className="muted">Suspended</div>
          <div className="kpi">{d.suspended_tenants ?? '—'}</div>
        </div>
        <div className="card">
          <div className="muted">New this month</div>
          <div className="kpi">{d.new_tenants_this_month ?? '—'}</div>
        </div>
        <div className="card">
          <div className="muted">Platform users</div>
          <div className="kpi">{d.platform_users ?? '—'}</div>
        </div>
        <div className="card">
          <div className="muted">Customer users</div>
          <div className="kpi">{d.customer_users ?? '—'}</div>
        </div>
      </div>

      <div className="grid" style={{ marginTop: 20 }}>
        <div className="card">
          <BarChart
            title="Tenant growth (by month)"
            series={(d.tenant_growth?.series || []).map((p) => ({ label: p.month, value: p.tenants }))}
            emptyLabel="No customer tenants created in this window"
          />
        </div>
        <div className="card">
          <DonutChart
            title="Tenant status"
            slices={(d.tenant_status?.slices || []).map((s) => ({ label: s.status, value: s.count }))}
            emptyLabel="No customer tenants"
          />
        </div>
        <div className="card">
          <DonutChart
            title="Plan distribution (metadata)"
            slices={(d.plan_distribution?.slices || []).map((s) => ({ label: s.plan_code, value: s.count }))}
            emptyLabel="No plan codes yet"
          />
        </div>
        <div className="card">
          <DonutChart
            title="Industry distribution"
            slices={(d.industry_distribution?.slices || []).map((s) => ({ label: s.industry, value: s.count }))}
            emptyLabel="No industry data"
          />
        </div>
        <div className="card">
          <BarChart
            title="Customer user growth (by month)"
            series={(d.user_growth?.series || []).map((p) => ({ label: p.month, value: p.users }))}
            emptyLabel="No customer users created in this window"
          />
        </div>
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <div className="muted">Billing / MRR</div>
        <p style={{ marginTop: 8 }}>
          {d.billing?.message ||
            'Subscription billing is deferred (ADR-002). No fabricated MRR is shown.'}
        </p>
        <p className="muted" style={{ marginTop: 8 }}>
          MRR: {d.billing?.mrr == null ? 'n/a (deferred)' : d.billing.mrr}
        </p>
      </div>
      {d.generated_at && (
        <p className="muted" style={{ marginTop: 16 }}>
          Generated {d.generated_at}
        </p>
      )}
    </PlatformShell>
  );
}
