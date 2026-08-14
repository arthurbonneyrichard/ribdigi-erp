'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { setWorkspaceContext } from '../../lib/workspaceContext';

type TenantDash = {
  tenant: { name: string; status: string; plan_code: string };
  subscription: {
    limits: Record<string, number>;
    usage: Record<string, number>;
    billing_deferred: boolean;
  };
  counts: Record<string, number>;
  companies: { id: string; name: string; code: string; is_active: boolean }[];
};

export default function TenantDashboardPage() {
  const [data, setData] = useState<TenantDash | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setWorkspaceContext('tenant');
    let active = true;
    (async () => {
      try {
        const res = await api('/tenant/dashboard');
        if (active) setData(res.data);
      } catch (e: unknown) {
        if (active) setError(e instanceof Error ? e.message : 'Failed to load tenant dashboard');
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  return (
    <Shell>
      <div className="page">
        <h1>Tenant Dashboard</h1>
        <p className="muted">
          SaaS account administration only. Company operations (POS, sales, stock, finance) require
          switching into a company workspace.
        </p>
        {error && <p className="error">{error}</p>}
        {data && (
          <>
            <div className="card-grid" style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))' }}>
              <div className="card">
                <h3>Tenant</h3>
                <p>{data.tenant.name}</p>
                <p className="muted">{data.tenant.status} · {data.tenant.plan_code}</p>
              </div>
              <div className="card">
                <h3>Companies</h3>
                <p style={{ fontSize: 28, margin: 0 }}>{data.counts.companies}</p>
                <p className="muted">
                  Limit {data.subscription.limits.max_companies}
                </p>
              </div>
              <div className="card">
                <h3>Users</h3>
                <p style={{ fontSize: 28, margin: 0 }}>{data.counts.users}</p>
                <p className="muted">Limit {data.subscription.limits.max_users}</p>
              </div>
              <div className="card">
                <h3>Branches / Stores</h3>
                <p style={{ fontSize: 28, margin: 0 }}>
                  {data.counts.branches} / {data.counts.stores}
                </p>
                <p className="muted">
                  Warehouses {data.counts.warehouses}
                </p>
              </div>
            </div>
            <section style={{ marginTop: 24 }}>
              <h2>Companies</h2>
              <p>
                <Link href="/companies">Manage companies</Link>
              </p>
              <ul>
                {data.companies.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => {
                        setWorkspaceContext('company', c.id);
                        window.location.assign('/dashboard');
                      }}
                    >
                      Open {c.name}
                    </button>
                    <span className="muted"> · {c.code}</span>
                  </li>
                ))}
              </ul>
            </section>
            {data.subscription.billing_deferred && (
              <p className="muted" style={{ marginTop: 16 }}>
                Billing Complete remains deferred (ADR-002). Plan limits above are enforced on the
                backend.
              </p>
            )}
          </>
        )}
      </div>
    </Shell>
  );
}
