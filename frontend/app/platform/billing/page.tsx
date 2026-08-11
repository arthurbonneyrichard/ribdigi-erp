'use client';

import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';

type RosterItem = {
  tenant_id: string;
  slug: string;
  company_name: string;
  status: string;
  plan_code: string;
  trial_ends_at?: string | null;
  billing?: string;
};

export default function PlatformBillingPage() {
  const [data, setData] = useState<any>(null);
  const [roster, setRoster] = useState<RosterItem[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api('/platform/billing'), api('/platform/subscriptions')])
      .then(([billing, subs]) => {
        setData(billing.data);
        const items = subs.data?.items || billing.data?.active_subscriptions || [];
        setRoster(Array.isArray(items) ? items : []);
      })
      .catch((err) => setError(err.message || 'Failed to load'));
  }, []);

  return (
    <PlatformShell>
      <h1>Billing</h1>
      <p className="muted">
        House subscriptions roster — tenant×plan commercial metadata (ADR-002 billing deferred).
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
                <th>Billing</th>
              </tr>
            </thead>
            <tbody>
              {roster.map((row) => (
                <tr key={row.tenant_id}>
                  <td>{row.company_name}</td>
                  <td>{row.slug}</td>
                  <td>{row.status}</td>
                  <td>{row.plan_code}</td>
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
