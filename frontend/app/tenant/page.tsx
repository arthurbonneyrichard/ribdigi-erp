'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { setWorkspaceContext } from '../../lib/workspaceContext';

type TenantDash = {
  tenant: { name: string; status: string; plan_code: string };
  subscription: {
    limits: Record<string, number | boolean | null>;
    usage: Record<string, number>;
    billing_deferred: boolean;
    store_entitlement?: {
      max_stores: number;
      max_stores_unlimited?: boolean;
      used: number;
      remaining: number | null;
      unallocated: number | null;
      over_entitlement?: boolean;
    };
    store_allocations?: {
      company_id: string;
      company_name: string;
      company_code: string;
      store_limit: number;
      used: number;
      remaining: number | null;
    }[];
  };
  counts: Record<string, number>;
  companies: { id: string; name: string; code: string; is_active: boolean; store_limit?: number | null }[];
};

export default function TenantDashboardPage() {
  const [data, setData] = useState<TenantDash | null>(null);
  const [error, setError] = useState('');
  const [allocBusy, setAllocBusy] = useState('');
  const [allocDraft, setAllocDraft] = useState<Record<string, string>>({});

  async function load() {
    const res = await api('/tenant/dashboard');
    setData(res.data);
    const drafts: Record<string, string> = {};
    for (const row of res.data?.subscription?.store_allocations || []) {
      drafts[row.company_id] = String(row.store_limit ?? 0);
    }
    setAllocDraft(drafts);
  }

  useEffect(() => {
    setWorkspaceContext('tenant');
    let active = true;
    (async () => {
      try {
        await load();
      } catch (e: unknown) {
        if (active) setError(e instanceof Error ? e.message : 'Failed to load tenant dashboard');
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function saveAllocation(companyId: string) {
    setAllocBusy(companyId);
    setError('');
    try {
      const store_limit = Number(allocDraft[companyId]);
      await api(`/companies/${companyId}/store-limit`, {
        method: 'PATCH',
        body: JSON.stringify({ store_limit }),
      });
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to update store allocation');
    } finally {
      setAllocBusy('');
    }
  }

  const storeEnt = data?.subscription?.store_entitlement;
  const storeLimitLabel = storeEnt?.max_stores_unlimited
    ? 'Unlimited'
    : String(storeEnt?.max_stores ?? data?.subscription?.limits?.max_stores ?? '—');

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
            <div
              className="card-grid"
              style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))' }}
            >
              <div className="card">
                <h3>Tenant</h3>
                <p>{data.tenant.name}</p>
                <p className="muted">
                  {data.tenant.status} · {data.tenant.plan_code}
                </p>
              </div>
              <div className="card">
                <h3>Companies</h3>
                <p style={{ fontSize: 28, margin: 0 }}>
                  {data.counts.companies} / {String(data.subscription.limits.max_companies)}
                </p>
              </div>
              <div className="card">
                <h3>Stores</h3>
                <p style={{ fontSize: 28, margin: 0 }}>
                  {storeEnt?.used ?? data.counts.stores} / {storeLimitLabel}
                </p>
                <p className="muted">
                  Remaining {storeEnt?.remaining ?? '—'}
                  {storeEnt?.over_entitlement ? ' · over entitlement' : ''}
                </p>
              </div>
              <div className="card">
                <h3>Users</h3>
                <p style={{ fontSize: 28, margin: 0 }}>{data.counts.users}</p>
                <p className="muted">Limit {String(data.subscription.limits.max_users)}</p>
              </div>
            </div>

            <section style={{ marginTop: 24 }}>
              <h2>Store allocations</h2>
              <p className="muted">
                Subscription store allowance is allocated to companies. Allocations cannot exceed the
                tenant entitlement. Downgrades never delete existing stores.
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Allocated</th>
                    <th>Used</th>
                    <th>Remaining</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {(data.subscription.store_allocations || []).map((row) => (
                    <tr key={row.company_id}>
                      <td>
                        {row.company_name} <span className="muted">({row.company_code})</span>
                      </td>
                      <td>
                        <input
                          style={{ width: 72 }}
                          value={allocDraft[row.company_id] ?? String(row.store_limit)}
                          onChange={(e) =>
                            setAllocDraft({ ...allocDraft, [row.company_id]: e.target.value })
                          }
                        />
                      </td>
                      <td>{row.used}</td>
                      <td>{row.remaining ?? '—'}</td>
                      <td>
                        <button
                          type="button"
                          disabled={allocBusy === row.company_id}
                          onClick={() => saveAllocation(row.company_id)}
                        >
                          Save
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

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
