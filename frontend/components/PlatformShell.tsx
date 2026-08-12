'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { api } from '../lib/api';
import { canReadModule } from '../lib/rbac';

const items: [string, string, string][] = [
  ['Dashboard', '/platform/dashboard', 'platform_dashboard'],
  ['Tenants', '/platform/tenants', 'platform_tenants'],
  ['At-risk Tenants', '/platform/tenants?focus=at-risk#at-risk-queue', 'platform_tenants'],
  ['New Tenants', '/platform/tenants?created_this_month=true', 'platform_tenants'],
  ['Active Tenants', '/platform/tenants?status=active', 'platform_tenants'],
  ['Trial Tenants', '/platform/tenants?status=trial', 'platform_tenants'],
  ['Grace Tenants', '/platform/tenants?status=grace', 'platform_tenants'],
  ['Suspended Tenants', '/platform/tenants?status=suspended', 'platform_tenants'],
  ['Trial Plan Tenants', '/platform/tenants?plan_code=trial', 'platform_tenants'],
  ['Starter Plan Tenants', '/platform/tenants?plan_code=starter', 'platform_tenants'],
  ['Growth Plan Tenants', '/platform/tenants?plan_code=growth', 'platform_tenants'],
  ['Enterprise Plan Tenants', '/platform/tenants?plan_code=enterprise', 'platform_tenants'],
  ['Retail Tenants', '/platform/tenants?industry=retail', 'platform_tenants'],
  ['Pharmacy Tenants', '/platform/tenants?industry=pharmacy', 'platform_tenants'],
  ['Restaurant Tenants', '/platform/tenants?industry=restaurant', 'platform_tenants'],
  ['Bakery Tenants', '/platform/tenants?industry=bakery', 'platform_tenants'],
  ['Wholesale Tenants', '/platform/tenants?industry=wholesale', 'platform_tenants'],
  ['Manufacturing Tenants', '/platform/tenants?industry=manufacturing', 'platform_tenants'],
  ['Mart Tenants', '/platform/tenants?industry=mart', 'platform_tenants'],
  ['Plans', '/platform/plans', 'platform_plans'],
  ['Users', '/platform/users', 'platform_users'],
  ['Active Users', '/platform/users?is_active=true', 'platform_users'],
  ['Inactive Users', '/platform/users?is_active=false', 'platform_users'],
  ['Billing', '/platform/billing', 'platform_billing'],
  ['Settings', '/platform/settings', 'platform_settings'],
  ['Health', '/platform/health', 'platform_health'],
  ['Audit', '/platform/audit', 'platform_audit'],
  ['Activity', '/platform/activity', 'platform_audit'],
  ['Delivery Audit', '/platform/audit?delivery_only=true', 'platform_audit'],
  ['Security', '/security', 'security'],
];

export default function PlatformShell({ children }: { children: React.ReactNode }) {
  const [permissions, setPermissions] = useState<Record<string, string[]> | null>(null);
  const [idleMinutes, setIdleMinutes] = useState(30);
  const [ready, setReady] = useState(false);
  const [atRiskTotal, setAtRiskTotal] = useState<number | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const meRes = await api('/me');
        if (!active) return;
        if (meRes.data?.principal !== 'platform') {
          router.replace(meRes.data?.redirect_path || '/dashboard');
          return;
        }
        setPermissions(meRes.data?.permissions || {});
        setIdleMinutes(Number(meRes.data?.inactivity_timeout_minutes) || 30);
        setReady(true);
      } catch {
        if (active) {
          localStorage.removeItem('token');
          router.replace('/');
        }
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [router, pathname]);

  useEffect(() => {
    if (!ready || !canReadModule(permissions, 'platform_tenants')) return;
    let active = true;
    api('/platform/tenants/at-risk?within_days=14')
      .then((r) => {
        if (!active) return;
        const total = r.data?.total;
        if (typeof total === 'number') setAtRiskTotal(total);
      })
      .catch(() => {
        // omit badge on failure — never fabricate 0
      });
    return () => {
      active = false;
    };
  }, [ready, permissions]);

  useEffect(() => {
    if (typeof window === 'undefined' || !ready) return;
    const token = localStorage.getItem('token');
    if (!token) return;
    const timeoutMs = Math.max(5, idleMinutes) * 60 * 1000;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let loggingOut = false;

    async function performIdleLogout() {
      if (loggingOut) return;
      loggingOut = true;
      try {
        await api('/auth/idle-logout', { method: 'POST', body: '{}' });
      } catch {
        // clear local session anyway
      }
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/';
    }

    const reset = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        void performIdleLogout();
      }, timeoutMs);
    };
    const events = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll'] as const;
    events.forEach((ev) => window.addEventListener(ev, reset, { passive: true }));
    reset();
    return () => {
      if (timer) clearTimeout(timer);
      events.forEach((ev) => window.removeEventListener(ev, reset));
    };
  }, [idleMinutes, ready]);

  if (!ready) {
    return (
      <div className="shell">
        <main className="main">
          <p className="muted">Loading platform console…</p>
        </main>
      </div>
    );
  }

  const visible = items.filter(([, , module]) => canReadModule(permissions, module));

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">Ribdigi House</div>
        <p className="muted" style={{ color: '#94a3b8', fontSize: 12, marginTop: -16, marginBottom: 20 }}>
          Platform console
        </p>
        <nav className="nav">
          {visible.map(([n, h]) => (
            <Link key={h} href={h}>
              {n}
              {h === '/platform/tenants' && atRiskTotal != null ? (
                <span className="badge" style={{ marginLeft: 8 }} title="At-risk tenants (14d)">
                  {atRiskTotal} at-risk
                </span>
              ) : null}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
