'use client';

import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';

export default function PlatformBillingPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/platform/billing')
      .then((r) => setData(r.data))
      .catch((err) => setError(err.message || 'Failed to load'));
  }, []);

  return (
    <PlatformShell>
      <h1>Billing</h1>
      <p className="muted">Subscription billing status for Ribdigi House operators.</p>
      {error && <p>{error}</p>}
      {data && (
        <div className="card" style={{ marginTop: 16, maxWidth: 640 }}>
          <p>
            <strong>Status:</strong> {data.deferred ? 'Deferred (ADR-002)' : 'Active'}
          </p>
          <p>{data.message}</p>
          <p className="muted" style={{ marginTop: 12 }}>
            Provider: {data.provider ?? 'none'} · MRR: {data.mrr == null ? 'n/a' : data.mrr} ·
            Checkout: {data.checkout_enabled ? 'enabled' : 'disabled'}
          </p>
          {Array.isArray(data.plan_codes) && (
            <p className="muted">Plan codes (metadata only): {data.plan_codes.join(', ')}</p>
          )}
        </div>
      )}
    </PlatformShell>
  );
}
