'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import PageHeader from '../../../components/PageHeader';
import PageSkeleton from '../../../components/PageSkeleton';
import { Metric, Tag, daysLeft, timeAgo } from '../../../components/PlatformUi';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { getPrefetched } from '../../../lib/prefetchCache';
import { industryLabel } from '../../../lib/industries';
import { platformNavItemsForRole } from '../../../lib/tenantNav';

type TenantRow = {
  id: string;
  status: string;
  industry?: string;
};

type ActivityRow = {
  id: string;
  created_at?: string;
  summary?: string;
  module?: string;
  action?: string;
};

type UpcomingRow = {
  tenant_id: string;
  company_name: string;
  status?: string;
  kind?: string;
  days_remaining?: number | null;
};

type PlatformSummary = {
  tenant_count?: number;
  by_package?: Record<string, number>;
  open_support_tickets?: number;
  paid_invoice_count?: number;
  paid_revenue_by_currency?: Record<string, number>;
  active_billing_accounts?: number;
  attention_count?: number;
};

function fmtMoney(currency: string, amount: number) {
  return `${currency} ${Number(amount || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

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
    return new Date(value).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

const STATUS_ROWS = [
  { key: 'active', label: 'Active', mark: 'plat-mark-ok' },
  { key: 'trial', label: 'Trial', mark: 'plat-mark-info' },
  { key: 'grace', label: 'Grace', mark: 'plat-mark-warn' },
  { key: 'suspended', label: 'Suspended', mark: 'plat-mark-bad' },
] as const;

type TodoItem = {
  key: string;
  count: number;
  tone: 'bad' | 'warn' | 'info';
  title: string;
  sub: string;
  href: string;
};

function plural(count: number, one: string, many: string) {
  return count === 1 ? one : many;
}

function StatusSplit({
  counts,
}: {
  counts: { total: number; active: number; trial: number; grace: number; suspended: number };
}) {
  const shown = STATUS_ROWS.filter((row) => counts[row.key] > 0);
  return (
    <>
      <div className={`plat-split${shown.length ? '' : ' is-empty'}`} role="img" aria-label="Tenants by status">
        {shown.map((row) => (
          <span
            key={row.key}
            className={row.mark}
            style={{ flexGrow: counts[row.key] }}
            title={`${row.label}: ${counts[row.key]}`}
          />
        ))}
      </div>
      <ul className="plat-legend">
        {STATUS_ROWS.map((row) => (
          <li key={row.key}>
            <i className={row.mark} aria-hidden="true" />
            {row.label}
            <b>{counts[row.key]}</b>
            <small>{counts.total ? `${Math.round((counts[row.key] / counts.total) * 100)}%` : '—'}</small>
          </li>
        ))}
      </ul>
    </>
  );
}

function IndustryBars({ rows }: { rows: { label: string; count: number }[] }) {
  if (!rows.length) return <p className="muted">No companies yet.</p>;
  const max = Math.max(1, ...rows.map((row) => row.count));
  return (
    <ul className="plat-bars" aria-label="Tenants by industry">
      {rows.map((row) => (
        <li key={row.label} title={`${row.label}: ${row.count}`}>
          <span>{row.label}</span>
          <b>{row.count}</b>
          <div>
            <span style={{ width: `${(row.count / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function PlatformConsole() {
  const router = useRouter();
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [activity, setActivity] = useState<ActivityRow[]>([]);
  const [summary, setSummary] = useState<PlatformSummary | null>(null);
  const [upcoming, setUpcoming] = useState<UpcomingRow[] | null>(null);
  const [summaryMissing, setSummaryMissing] = useState(false);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const [role, setRole] = useState('');
  const [permissions, setPermissions] = useState<Record<string, string[]> | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const me = await getMe();
      if (cancelled) return;
      const role = me.data?.role || '';
      if (!PLATFORM_ROLES.includes(role)) {
        router.replace('/dashboard');
        return;
      }
      setRole(role);
      setPermissions(me.data?.permissions || {});
      const [tenantRes, activityRes, summaryRes, upcomingRes] = await Promise.allSettled([
        getPrefetched('/tenants'),
        api('/platform/activity'),
        api('/platform/reports/summary'),
        api('/platform/reports/trials'),
      ]);
      if (cancelled) return;
      const problems: string[] = [];
      if (tenantRes.status === 'fulfilled') setTenants(tenantRes.value.data || []);
      else problems.push(tenantRes.reason?.message || 'Companies did not load');
      if (activityRes.status === 'fulfilled') setActivity(activityRes.value.data || []);
      else problems.push(activityRes.reason?.message || 'Platform activity did not load');
      if (summaryRes.status === 'fulfilled') {
        setSummary(summaryRes.value.data || {});
        setSummaryMissing(false);
      } else {
        setSummary(null);
        setSummaryMissing(true);
        problems.push(summaryRes.reason?.message || 'Platform counts did not load');
      }
      // Some staff roles cannot read reports. The panel just stays hidden for them.
      if (upcomingRes.status === 'fulfilled') setUpcoming(upcomingRes.value.data?.rows || []);
      if (problems.length) setError(problems.join(' '));
      setReady(true);
    })().catch((err) => {
      if (!cancelled) setError(err.message || 'Failed to load platform console');
    });
    return () => {
      cancelled = true;
    };
  }, [router]);

  const counts = useMemo(() => {
    const count = (status: string) => tenants.filter((row) => row.status === status).length;
    return {
      total: tenants.length,
      active: count('active'),
      trial: count('trial'),
      grace: count('grace'),
      suspended: count('suspended'),
    };
  }, [tenants]);

  const tools = useMemo(
    () => platformNavItemsForRole(role, permissions).map(([, href]) => href),
    [role, permissions],
  );

  const companyCount =
    typeof summary?.tenant_count === 'number'
      ? summary.tenant_count
      : summaryMissing && counts.total === 0
        ? null
        : counts.total;
  const subscriptionCount = summary?.by_package
    ? Object.values(summary.by_package).reduce((sum, value) => sum + Number(value || 0), 0)
    : null;
  const openTickets = typeof summary?.open_support_tickets === 'number' ? summary.open_support_tickets : null;
  const canOpenDesk = tools.includes('/platform/support');
  const paidCount = typeof summary?.paid_invoice_count === 'number' ? summary.paid_invoice_count : null;
  const paidRevenue = Object.entries(summary?.paid_revenue_by_currency || {});
  const activeBilling =
    typeof summary?.active_billing_accounts === 'number' ? summary.active_billing_accounts : null;
  const attention = typeof summary?.attention_count === 'number' ? summary.attention_count : null;

  const industries = useMemo(() => {
    const tally = new Map<string, number>();
    for (const row of tenants) {
      const label = industryLabel(row.industry);
      tally.set(label, (tally.get(label) || 0) + 1);
    }
    return Array.from(tally.entries())
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
  }, [tenants]);

  const endingSoon = (upcoming || []).filter(
    (row) => row.status !== 'suspended' && row.status !== 'grace' && (row.days_remaining ?? 99) <= 14,
  ).length;

  const todo: TodoItem[] = [];
  if (attention) {
    todo.push({
      key: 'billing',
      count: attention,
      tone: 'bad',
      title: `${plural(attention, 'Company needs', 'Companies need')} billing attention`,
      sub: 'Past due, payment needed, or suspended for billing.',
      href: '/platform/billing?tab=attention',
    });
  }
  if (openTickets && canOpenDesk) {
    todo.push({
      key: 'tickets',
      count: openTickets,
      tone: 'warn',
      title: `Open support ${plural(openTickets, 'ticket', 'tickets')}`,
      sub: 'Waiting on your team or the company.',
      href: '/platform/support',
    });
  }
  if (counts.grace) {
    todo.push({
      key: 'grace',
      count: counts.grace,
      tone: 'warn',
      title: `${plural(counts.grace, 'Company', 'Companies')} in grace period`,
      sub: 'Access ends unless the subscription is renewed.',
      href: '/platform/tenants?status=grace',
    });
  }
  if (endingSoon) {
    todo.push({
      key: 'ending',
      count: endingSoon,
      tone: 'info',
      title: `${plural(endingSoon, 'Trial or renewal', 'Trials and renewals')} ending within 14 days`,
      sub: 'A good moment to contact them.',
      href: '/platform/reports',
    });
  }
  if (counts.suspended) {
    todo.push({
      key: 'suspended',
      count: counts.suspended,
      tone: 'bad',
      title: `Suspended ${plural(counts.suspended, 'company', 'companies')}`,
      sub: 'Staff cannot sign in until reactivated.',
      href: '/platform/tenants?status=suspended',
    });
  }

  if (!ready && !error) {
    return <PageSkeleton label="Loading platform console…" cards={4} />;
  }

  const firstRevenue = paidRevenue[0];

  return (
    <div className="plat">
      <PageHeader
        className="plat-hero"
        kicker="Software owner"
        kickerClassName="plat-kicker"
        title="Platform console"
        subtitle="How every company on RIBDIGI is doing, and what needs you today."
        subtitleClassName="plat-sub"
      />

      {error && (
        <p className="login-error" role="alert">
          {error}
        </p>
      )}

      <div className="plat-metrics" aria-label="Platform counts">
        <Metric
          label="Companies"
          href="/platform/tenants"
          value={companyCount == null ? '—' : companyCount}
          note={
            companyCount == null
              ? 'Company count did not load.'
              : companyCount === 0
                ? 'No companies yet.'
                : `${counts.active} active · ${counts.trial} on trial`
          }
        />
        <Metric
          label="Subscriptions"
          href="/platform/reports"
          value={subscriptionCount == null ? '—' : subscriptionCount}
          note={
            subscriptionCount == null
              ? 'Subscription count did not load.'
              : subscriptionCount === 0
                ? 'No subscriptions yet.'
                : activeBilling == null
                  ? undefined
                  : `${activeBilling} active billing ${plural(activeBilling, 'account', 'accounts')}`
          }
        />
        <Metric
          label="Paid revenue (all time)"
          href="/platform/billing"
          note={
            summary == null
              ? 'Revenue did not load.'
              : paidRevenue.length === 0
                ? 'No paid subscription invoices yet.'
                : paidCount == null
                  ? undefined
                  : `${paidCount} paid ${plural(paidCount, 'invoice', 'invoices')}`
          }
        >
          <strong className="plat-metric-value is-sm">
            {firstRevenue ? fmtMoney(firstRevenue[0], firstRevenue[1]) : '—'}
          </strong>
          {paidRevenue.slice(1).map(([currency, amount]) => (
            <span key={currency} className="plat-metric-second">
              {fmtMoney(currency, amount)}
            </span>
          ))}
        </Metric>
        <Metric
          label="Open support tickets"
          href={canOpenDesk ? '/platform/support' : undefined}
          value={openTickets == null ? '—' : openTickets}
          note={
            openTickets == null
              ? 'Open ticket count did not load.'
              : openTickets === 0
                ? 'No open support tickets.'
                : undefined
          }
        />
      </div>

      <div className="plat-cols">
        <div className="plat-stack">
          <section className="plat-panel" aria-label="Needs attention">
            <div className="plat-panel-head">
              <h2>Needs attention</h2>
            </div>
            {todo.length === 0 ? (
              summary == null ? (
                <p className="muted">Counts did not load, so this list may be incomplete.</p>
              ) : (
                <p className="plat-allclear">Nothing needs you right now.</p>
              )
            ) : (
              <ul className="plat-todo">
                {todo.map((item) => (
                  <li key={item.key}>
                    <Link href={item.href}>
                      <span className={`plat-todo-count is-${item.tone}`}>{item.count}</span>
                      <span className="plat-todo-text">
                        <span className="plat-todo-title">{item.title}</span>
                        <span className="plat-todo-sub">{item.sub}</span>
                      </span>
                      <svg className="plat-todo-go" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M9 6l6 6-6 6" />
                      </svg>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="plat-panel" aria-label="Platform activity">
            <div className="plat-panel-head">
              <h2>Platform activity</h2>
            </div>
            <p className="plat-panel-sub">
              Tenant creation, industry and package changes, administrator password resets, and staff
              account changes. Store stock, orders, POS, and payments are not listed here.
            </p>
            {activity.length === 0 ? (
              <p className="muted">No platform events yet.</p>
            ) : (
              <ol className="plat-feed">
                {activity.map((event) => (
                  <li key={event.id}>
                    <span>{event.summary || `${event.module || ''} ${event.action || ''}`}</span>
                    <time dateTime={event.created_at} title={fmtDate(event.created_at)}>
                      {timeAgo(event.created_at)}
                    </time>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>

        <div className="plat-stack">
          <section className="plat-panel">
            <div className="plat-panel-head">
              <h2>Tenants by status</h2>
              <Link href="/platform/tenants">View all</Link>
            </div>
            <StatusSplit counts={counts} />
          </section>
          <section className="plat-panel">
            <div className="plat-panel-head">
              <h2>Tenants by industry</h2>
            </div>
            <IndustryBars rows={industries} />
          </section>
          {upcoming && upcoming.length > 0 ? (
            <section className="plat-panel">
              <div className="plat-panel-head">
                <h2>Coming up</h2>
                <Link href="/platform/reports">All renewals</Link>
              </div>
              <ul className="plat-upcoming">
                {upcoming.slice(0, 5).map((row) => (
                  <li key={`${row.tenant_id}-${row.kind}`}>
                    <span title={row.company_name}>{row.company_name}</span>
                    <Tag tone={(row.days_remaining ?? 0) < 0 ? 'bad' : (row.days_remaining ?? 0) <= 7 ? 'warn' : 'none'}>
                      {daysLeft(row.days_remaining)}
                    </Tag>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
