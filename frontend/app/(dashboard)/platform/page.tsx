'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, apiFetch } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { getPrefetched } from '../../../lib/prefetchCache';
import { industryLabel } from '../../../lib/industries';

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

const PLATFORM_ROLES = [
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
];

const STATUS_BARS = [
  { key: 'active', label: 'Active', color: '#3D8B40' },
  { key: 'trial', label: 'Trial', color: '#C4A035' },
  { key: 'grace', label: 'Grace', color: '#D97706' },
  { key: 'suspended', label: 'Suspended', color: '#C24141' },
] as const;

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

function StatusBars({
  counts,
}: {
  counts: { active: number; trial: number; grace: number; suspended: number };
}) {
  const max = Math.max(1, ...STATUS_BARS.map((row) => counts[row.key]));
  return (
    <svg viewBox="0 0 360 168" width="100%" height="168" role="img" aria-label="Tenants by status">
      {STATUS_BARS.map((row, i) => {
        const value = counts[row.key];
        const width = Math.max(0, (value / max) * 220);
        const y = 18 + i * 38;
        return (
          <g key={row.key}>
            <text x="0" y={y + 14} className="vbar-label">
              {row.label}
            </text>
            <rect x="92" y={y} width="220" height="18" rx="4" fill="#E8F0E4" />
            <rect x="92" y={y} width={width} height="18" rx="4" fill={row.color} />
            <text x="320" y={y + 14} className="vbar-val">
              {value}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function IndustryBars({ rows }: { rows: { label: string; count: number }[] }) {
  const data = rows.length ? rows : [{ label: 'None', count: 0 }];
  const max = Math.max(1, ...data.map((row) => row.count));
  const height = Math.max(120, data.length * 28 + 8);
  return (
    <svg viewBox={`0 0 360 ${height}`} width="100%" height={height} role="img" aria-label="Tenants by industry">
      {data.map((row, i) => {
        const width = Math.max(0, (row.count / max) * 180);
        const y = 8 + i * 28;
        return (
          <g key={row.label}>
            <text x="0" y={y + 14} className="vbar-label">
              {row.label}
            </text>
            <rect x="128" y={y} width="180" height="16" rx="4" fill="#E8F0E4" />
            <rect x="128" y={y} width={width} height="16" rx="4" fill="#2F6B4F" />
            <text x="316" y={y + 13} className="vbar-val">
              {row.count}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function PlatformConsole() {
  const router = useRouter();
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [activity, setActivity] = useState<ActivityRow[]>([]);
  const [error, setError] = useState('');
  const [scriptBusy, setScriptBusy] = useState(false);
  const [scriptError, setScriptError] = useState('');
  const [ready, setReady] = useState(false);

  async function downloadLiveTestScript() {
    setScriptError('');
    setScriptBusy(true);
    try {
      const response = await apiFetch('/live-test-script');
      const type = (response.headers.get('content-type') || '').toLowerCase();
      if (!response.ok || !type.includes('pdf')) {
        setScriptError('Could not download the live test script.');
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'RIBDIGI-Retail-Pharmacy-Wholesale-Live-Test.pdf';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setScriptError('Could not download the live test script.');
    } finally {
      setScriptBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [me, tenantRes, activityRes] = await Promise.all([
        getMe(),
        getPrefetched('/tenants'),
        api('/platform/activity'),
      ]);
      if (cancelled) return;
      const role = me.data?.role || '';
      if (!PLATFORM_ROLES.includes(role)) {
        router.replace('/dashboard');
        return;
      }
      setTenants(tenantRes.data || []);
      setActivity(activityRes.data || []);
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

  if (!ready && !error) {
    return <p className="muted">Loading platform console…</p>;
  }

  return (
    <div className="plat">
      <header className="plat-hero">
        <div>
          <p className="plat-kicker">Software owner</p>
          <h1>Platform console</h1>
          <p className="plat-sub">
            Platform activity and workspace totals. Create and manage tenants from the Tenant page.
            Paid self-serve checkout is not live.
          </p>
          <button
            type="button"
            onClick={downloadLiveTestScript}
            disabled={scriptBusy}
            aria-label="Download live test script PDF"
          >
            {scriptBusy ? 'Preparing live test script…' : 'Download live test script (PDF)'}
          </button>
          {scriptError ? (
            <p className="login-error" role="alert">
              {scriptError}
            </p>
          ) : null}
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
          <strong>{counts.total}</strong>
        </div>
        <div className="plat-stat ok">
          <span>Active</span>
          <strong>{counts.active}</strong>
        </div>
        <div className="plat-stat trial">
          <span>Trial</span>
          <strong>{counts.trial}</strong>
        </div>
        <div className="plat-stat grace">
          <span>Grace</span>
          <strong>{counts.grace}</strong>
        </div>
        <div className="plat-stat bad">
          <span>Suspended</span>
          <strong>{counts.suspended}</strong>
        </div>
      </div>

      <div className="plat-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
        <div className="plat-panel">
          <h2>Tenants by status</h2>
          <StatusBars counts={counts} />
        </div>
        <div className="plat-panel">
          <h2>Tenants by industry</h2>
          <IndustryBars rows={industries} />
        </div>
      </div>

      <div className="plat-panel">
        <h2>Platform activity</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Tenant creation, industry and package changes, administrator password resets, and staff
          account changes. Store stock, orders, POS, and payments are not listed here.
        </p>
        {activity.length === 0 ? (
          <p className="muted">No platform events yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Event</th>
              </tr>
            </thead>
            <tbody>
              {activity.map((event) => (
                <tr key={event.id}>
                  <td>{fmtDate(event.created_at)}</td>
                  <td>{event.summary || `${event.module || ''} ${event.action || ''}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
