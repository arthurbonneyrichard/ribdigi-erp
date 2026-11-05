'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { formatNumber } from '../../../../lib/format';
import PageHeader from '../../../../components/PageHeader';
import PageSkeleton from '../../../../components/PageSkeleton';
import EmptyState from '../../../../components/EmptyState';
import { Metric, MonthBars, Tag, TenantStatus, daysLeft, plainWords } from '../../../../components/PlatformUi';
import { apiFetch } from '../../../../lib/api';
import { getMe } from '../../../../lib/meCache';
import { getPrefetched } from '../../../../lib/prefetchCache';
import { subscriptionAmountLabel } from '../../../../lib/platformBilling';
import { useCompanyFormat } from '../../../../lib/useCompanyFormat';

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
  const prefs = useCompanyFormat();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);

  async function exportCsv(report: 'summary' | 'subscriptions' | 'packages' | 'trials') {
    setError('');
    try {
      const res = await apiFetch(`/platform/reports/export?report=${report}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Export failed');
      }
      const blob = await res.blob();
      const cd = res.headers.get('Content-Disposition') || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = match?.[1] || `platform-${report}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e.message || 'Export failed');
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const [me, r] = await Promise.all([getMe(), getPrefetched('/platform/reports')]);
        if (!PLATFORM_ROLES.includes(me.data?.role)) {
          router.replace('/dashboard');
          return;
        }
        setData(r.data);
        setReady(true);
      } catch (e: any) {
        setError(e.message || 'Failed to load reports');
      }
    })();
  }, [router]);

  if (!ready && !error) {
    return <PageSkeleton label="Loading platform reports…" cards={3} />;
  }

  const summary = data?.summary || {};
  const packages = data?.packages?.packages || [];
  const subs = data?.subscriptions?.rows || [];
  const trials = data?.trials?.rows || [];
  const maxPackage = Math.max(1, ...packages.map((p: any) => Number(p.tenant_count) || 0));
  const signups: { month: string; count: number }[] = summary.new_companies_by_month || [];
  const revenueMonths = Object.entries(
    (summary.paid_revenue_by_month || {}) as Record<string, { month: string; amount: number }[]>,
  );

  return (
    <>
      <div className="plat">
        <PageHeader
          className="plat-hero"
          kicker="Software owner"
          kickerClassName="plat-kicker"
          title="Platform reports"
          subtitle="Cross-tenant overview: status mix, package distribution, subscription usage, and upcoming renewals / trial endings."
          subtitleClassName="plat-sub"
          actions={
            <details className="plat-menu">
              <summary>Export CSV</summary>
              <div className="plat-menu-pop">
                <button type="button" className="btn-primary" aria-label="Export platform summary CSV" onClick={() => exportCsv('summary')}>
                  Summary
                </button>
                <button type="button" className="btn-primary" aria-label="Export platform subscriptions CSV" onClick={() => exportCsv('subscriptions')}>
                  Subscriptions
                </button>
                <button type="button" className="btn-primary" aria-label="Export platform packages CSV" onClick={() => exportCsv('packages')}>
                  Packages
                </button>
                <button type="button" className="btn-primary" aria-label="Export platform trials CSV" onClick={() => exportCsv('trials')}>
                  Trials and renewals
                </button>
              </div>
            </details>
          }
        />

        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}

        <div className="plat-metrics">
          <Metric label="Total tenants" value={summary.tenant_count ?? 0} />
          {Object.entries(summary.by_status || {}).map(([k, v]) => (
            <Metric key={k} label={plainWords(k)} value={v as number} />
          ))}
        </div>

        <div className="plat-cols-even">
          <div className="plat-panel">
            <div className="plat-panel-head">
              <h2>New companies by month</h2>
              <span className="muted" style={{ fontSize: 13 }}>
                {signups.reduce((sum, row) => sum + row.count, 0)} in 12 months
              </span>
            </div>
            <MonthBars
              label="New companies"
              rows={signups.map((row) => ({ month: row.month, value: row.count }))}
            />
          </div>
          <div className="plat-panel">
            <div className="plat-panel-head">
              <h2>Paid revenue by month</h2>
            </div>
            {revenueMonths.length === 0 ? (
              <p className="muted">No paid subscription invoices in the last 12 months.</p>
            ) : (
              <div className="plat-stack">
                {revenueMonths.map(([currency, months]) => (
                  <div key={currency}>
                    {revenueMonths.length > 1 ? <p className="plat-months-title">{currency}</p> : null}
                    <MonthBars
                      label={`Paid revenue in ${currency}`}
                      rows={months.map((row) => ({ month: row.month, value: row.amount }))}
                      format={(value) => `${currency} ${formatNumber(value, prefs)}`}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="plat-panel">
          <div className="plat-panel-head">
            <h2>Package distribution</h2>
          </div>
          <div className="plat-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Package</th>
                  <th>Tenants</th>
                  <th className="col-right">Active</th>
                  <th className="col-right">Trial</th>
                  <th className="col-right">Grace</th>
                  <th className="col-right">Suspended</th>
                </tr>
              </thead>
              <tbody>
                {packages.map((p: any) => (
                  <tr key={p.package_code}>
                    <td className="plat-co">{p.package_name}</td>
                    <td>
                      <div className="plat-meter" title={`${p.tenant_count} tenants`}>
                        <span className="plat-meter-track">
                          <span style={{ width: `${(Number(p.tenant_count) / maxPackage) * 100}%` }} />
                        </span>
                        <b>{p.tenant_count}</b>
                      </div>
                    </td>
                    <td className="col-right">{p.active}</td>
                    <td className="col-right">{p.trial}</td>
                    <td className="col-right">{p.grace}</td>
                    <td className="col-right">{p.suspended}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="plat-panel">
          <div className="plat-panel-head">
            <h2>Subscription usage</h2>
          </div>
          {subs.length === 0 ? (
            <EmptyState title="No subscriptions yet." />
          ) : (
            <div className="plat-table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th className="plat-hide-sm">Package</th>
                    <th className="col-right">Amount</th>
                    <th className="plat-hide-sm">Term used</th>
                    <th className="plat-hide-sm">Remaining</th>
                    <th className="plat-hide-sm">Renewal</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {subs.map((r: any) => {
                    const assigned = Number(r.months_assigned) || 0;
                    const used = Number(r.months_used) || 0;
                    return (
                      <tr key={r.tenant_id}>
                        <td>
                          <div className="plat-co">{r.company_name}</div>
                          <span className="plat-small">{r.slug}</span>
                        </td>
                        <td className="plat-hide-sm">{r.package_name || r.package_code}</td>
                        <td className="col-right">
                          {subscriptionAmountLabel(
                            r.amount,
                            r.currency,
                            r.amount == null ? '' : formatNumber(r.amount, prefs),
                          )}
                        </td>
                        <td className="plat-hide-sm">
                          <div className="plat-meter">
                            <span className="plat-meter-track">
                              <span style={{ width: `${assigned ? Math.min(100, (used / assigned) * 100) : 0}%` }} />
                            </span>
                            <small>{used} mo</small>
                          </div>
                        </td>
                        <td className="plat-hide-sm">
                          {r.months_remaining != null ? `${r.months_remaining} mo` : '—'}
                          {r.days_remaining != null ? <span className="plat-small">{daysLeft(r.days_remaining)}</span> : null}
                        </td>
                        <td className="plat-hide-sm">{fmtDate(r.renewal_due)}</td>
                        <td>
                          <TenantStatus status={r.status} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="plat-panel">
          <div className="plat-panel-head">
            <h2>Upcoming renewals / trial ends ({data?.trials?.within_days ?? 45}d)</h2>
          </div>
          {trials.length === 0 ? (
            <p className="muted">None in window</p>
          ) : (
            <div className="plat-table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Kind</th>
                    <th className="plat-hide-sm">Package</th>
                    <th className="plat-hide-sm">Ends</th>
                    <th>Time left</th>
                    <th className="plat-hide-sm">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {trials.map((r: any) => (
                    <tr key={r.tenant_id + String(r.ends_at)}>
                      <td className="plat-co">{r.company_name}</td>
                      <td>{plainWords(r.kind)}</td>
                      <td className="plat-hide-sm">{plainWords(r.package_code)}</td>
                      <td className="plat-hide-sm">{fmtDate(r.ends_at)}</td>
                      <td>
                        <Tag tone={r.days_remaining < 0 ? 'bad' : r.days_remaining <= 7 ? 'warn' : 'none'}>
                          {daysLeft(r.days_remaining)}
                        </Tag>
                      </td>
                      <td className="plat-hide-sm">
                        <TenantStatus status={r.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

    </>
  );
}
