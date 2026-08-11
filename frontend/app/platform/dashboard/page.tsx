'use client';

import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';

type Dash = {
  total_tenants?: number;
  active_tenants?: number;
  trial_tenants?: number;
  grace_tenants?: number;
  suspended_tenants?: number;
  new_tenants_this_month?: number;
  platform_users?: number;
  customer_users?: number;
  billing?: { deferred?: boolean; message?: string; mrr?: number | null };
  generated_at?: string;
};

export default function PlatformDashboardPage() {
  const [d, setD] = useState<Dash>({});
  const [error, setError] = useState('');

  useEffect(() => {
    api('/platform/dashboard')
      .then((r) => setD(r.data || {}))
      .catch((err) => setError(err.message || 'Failed to load'));
  }, []);

  return (
    <PlatformShell>
      <h1>Platform dashboard</h1>
      <p className="muted">Customer tenant overview for Ribdigi House operators.</p>
      {error && <p>{error}</p>}
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
          <div className="muted">Suspended</div>
          <div className="kpi">{d.suspended_tenants ?? '—'}</div>
        </div>
        <div className="card">
          <div className="muted">New this month</div>
          <div className="kpi">{d.new_tenants_this_month ?? '—'}</div>
        </div>
        <div className="card">
          <div className="muted">Customer users</div>
          <div className="kpi">{d.customer_users ?? '—'}</div>
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
