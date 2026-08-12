'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Shell from '../../../components/Shell';
import { api } from '../../../lib/api';

const PLATFORM_ROLES = [
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
];

function fmtDate(value?: string | null) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return String(value);
  }
}

export default function PlatformReportsPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const me = await api('/me');
        if (!PLATFORM_ROLES.includes(me.data?.role)) {
          router.replace('/dashboard');
          return;
        }
        const r = await api('/platform/reports');
        setData(r.data);
        setReady(true);
      } catch (e: any) {
        setError(e.message || 'Failed to load reports');
      }
    })();
  }, [router]);

  if (!ready && !error) {
    return (
      <Shell>
        <p className="muted">Loading platform reports…</p>
      </Shell>
    );
  }

  const summary = data?.summary || {};
  const packages = data?.packages?.packages || [];
  const subs = data?.subscriptions?.rows || [];
  const trials = data?.trials?.rows || [];

  return (
    <Shell>
      <div className="plat">
        <header className="plat-hero">
          <div>
            <p className="plat-kicker">Software owner</p>
            <h1>Platform reports</h1>
            <p className="plat-sub">
              Cross-tenant overview: status mix, package distribution, subscription usage, and
              upcoming renewals / trial endings.
            </p>
          </div>
        </header>

        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}

        <div className="plat-stats">
          <div className="plat-stat">
            <span>Total tenants</span>
            <strong>{summary.tenant_count ?? 0}</strong>
          </div>
          {Object.entries(summary.by_status || {}).map(([k, v]) => (
            <div key={k} className="plat-stat">
              <span>{k}</span>
              <strong>{v as number}</strong>
            </div>
          ))}
        </div>

        <div className="plat-panel">
          <h2>Package distribution</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Package</th>
                <th>Tenants</th>
                <th>Active</th>
                <th>Trial</th>
                <th>Grace</th>
                <th>Suspended</th>
              </tr>
            </thead>
            <tbody>
              {packages.map((p: any) => (
                <tr key={p.package_code}>
                  <td className="plat-co">{p.package_name}</td>
                  <td>{p.tenant_count}</td>
                  <td>{p.active}</td>
                  <td>{p.trial}</td>
                  <td>{p.grace}</td>
                  <td>{p.suspended}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="plat-panel">
          <h2>Subscription usage</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Package</th>
                <th>Used</th>
                <th>Remaining</th>
                <th>Renewal</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {subs.map((r: any) => (
                <tr key={r.tenant_id}>
                  <td>
                    <div className="plat-co">{r.company_name}</div>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {r.slug}
                    </div>
                  </td>
                  <td>{r.package_name || r.package_code}</td>
                  <td>{r.months_used ?? 0} mo</td>
                  <td>
                    {r.months_remaining != null ? `${r.months_remaining} mo` : '—'}
                    {r.days_remaining != null ? (
                      <div className="muted" style={{ fontSize: 11 }}>
                        {r.days_remaining}d
                      </div>
                    ) : null}
                  </td>
                  <td>{fmtDate(r.renewal_due)}</td>
                  <td>{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="plat-panel">
          <h2>Upcoming renewals / trial ends ({data?.trials?.within_days ?? 45}d)</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Kind</th>
                <th>Package</th>
                <th>Ends</th>
                <th>Days left</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {trials.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted">
                    None in window
                  </td>
                </tr>
              ) : (
                trials.map((r: any) => (
                  <tr key={r.tenant_id + String(r.ends_at)}>
                    <td className="plat-co">{r.company_name}</td>
                    <td>{r.kind}</td>
                    <td>{r.package_code}</td>
                    <td>{fmtDate(r.ends_at)}</td>
                    <td>{r.days_remaining}</td>
                    <td>{r.status}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}
