'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { canReadModule } from '../lib/rbac';
import {
  getSelectedStoreId,
  setSelectedStoreId,
  subscribeStoreContext,
} from '../lib/storeContext';

const items: [string, string, string][] = [
  ['Dashboard', '/dashboard', 'dashboard'],
  ['Company', '/company', 'company'],
  ['Inventory', '/inventory', 'inventory'],
  ['Sales', '/sales', 'sales'],
  ['POS', '/pos', 'pos'],
  ['Purchasing', '/purchasing', 'purchasing'],
  ['Expenses', '/expenses', 'expenses'],
  ['Accounting', '/accounting', 'accounting'],
  ['Credit', '/credit', 'credit'],
  ['Tax', '/tax', 'tax'],
  ['Multi-Store', '/stores', 'stores'],
  ['Reports', '/reports', 'reports'],
  ['Notifications', '/notifications', 'notifications'],
  ['Audit', '/audit', 'audit'],
  ['Backup', '/backup', 'backup'],
  ['Security', '/security', 'security'],
  ['AI Assistant', '/ai', 'ai'],
  ['Users', '/users', 'users'],
];

type StoreOption = { id: string; code: string; name: string; is_active?: boolean };

type OnboardingStep = {
  id: string;
  title: string;
  description?: string;
  href: string;
  completed: boolean;
  auto_completed?: boolean;
  skipped?: boolean;
};

type OnboardingChecklist = {
  steps: OnboardingStep[];
  completed_count: number;
  total_count: number;
  progress_pct: number;
  dismissed: boolean;
  dismissible: boolean;
  visible: boolean;
};

export default function Shell({ children }: { children: React.ReactNode }) {
  const [unread, setUnread] = useState(0);
  const [permissions, setPermissions] = useState<Record<string, string[]> | null>(null);
  const [role, setRole] = useState('');
  const [idleMinutes, setIdleMinutes] = useState(30);
  const [stores, setStores] = useState<StoreOption[]>([]);
  const [storeId, setStoreId] = useState('');
  const [onboarding, setOnboarding] = useState<OnboardingChecklist | null>(null);
  const [onboardingBusy, setOnboardingBusy] = useState(false);
  const canManageOnboarding = role === 'company_admin' || role === 'super_admin';

  useEffect(() => {
    setStoreId(getSelectedStoreId());
    return subscribeStoreContext((id) => setStoreId(id));
  }, []);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [countRes, meRes] = await Promise.all([
          api('/notifications/unread-count').catch(() => ({ data: { count: 0 } })),
          api('/me'),
        ]);
        if (!active) return;
        setUnread(countRes.data?.count || 0);
        setPermissions(meRes.data?.permissions || {});
        setRole(meRes.data?.role || '');
        setIdleMinutes(Number(meRes.data?.inactivity_timeout_minutes) || 30);
      } catch {
        if (active) {
          setUnread(0);
          setPermissions({});
          setRole('');
        }
      }
    }
    load();
    const id = setInterval(load, 30000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    let active = true;
    async function loadOnboarding() {
      try {
        const res = await api('/onboarding/checklist');
        if (!active) return;
        setOnboarding(res.data || null);
      } catch {
        if (active) setOnboarding(null);
      }
    }
    loadOnboarding();
    const id = setInterval(loadOnboarding, 60000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  async function mutateOnboarding(path: string) {
    if (onboardingBusy) return;
    setOnboardingBusy(true);
    try {
      const res = await api(path, { method: 'POST', body: '{}' });
      setOnboarding(res.data || null);
    } catch {
      // Keep existing banner state; next poll will refresh.
    } finally {
      setOnboardingBusy(false);
    }
  }

  useEffect(() => {
    if (!canReadModule(permissions, 'stores')) {
      setStores([]);
      return;
    }
    let active = true;
    api('/stores')
      .then((res) => {
        if (!active) return;
        const rows = (res.data || []).filter((s: StoreOption) => s.is_active !== false);
        setStores(rows);
        const selected = getSelectedStoreId();
        if (selected && !rows.some((s: StoreOption) => s.id === selected)) {
          setSelectedStoreId('');
        }
      })
      .catch(() => {
        if (active) setStores([]);
      });
    return () => {
      active = false;
    };
  }, [permissions]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
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
        // Still clear local credentials if the server call fails (expired token, etc.)
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
  }, [idleMinutes]);

  const visible = items.filter(([, , module]) => canReadModule(permissions, module));
  const showStoreSwitcher = canReadModule(permissions, 'stores') && stores.length > 0;

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">RIBDIGI ERP</div>
        <nav className="nav">
          {visible.map(([n, h]) => (
            <Link key={h} href={h}>
              {n}
              {h === '/notifications' && unread > 0 ? ` (${unread})` : ''}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="main">
        <div className="topbar">
          {showStoreSwitcher && (
            <label className="store-switcher">
              <span className="muted">Store</span>
              <select
                value={storeId}
                onChange={(e) => setSelectedStoreId(e.target.value)}
                aria-label="Global store context"
              >
                <option value="">All stores</option>
                {stores.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {canReadModule(permissions, 'notifications') && (
            <Link href="/notifications" className="bell">
              Alerts{unread > 0 ? ` · ${unread}` : ''}
            </Link>
          )}
        </div>
        {onboarding?.visible ? (
          <section className="onboarding-banner" aria-label="Getting started checklist">
            <div className="onboarding-banner-head">
              <div>
                <strong>Getting started</strong>
                <span className="muted">
                  {' '}
                  · {onboarding.completed_count}/{onboarding.total_count} complete (
                  {onboarding.progress_pct}%)
                </span>
              </div>
              {canManageOnboarding ? (
                <div className="onboarding-actions">
                  {onboarding.dismissible ? (
                    <button
                      type="button"
                      className="onboarding-btn"
                      disabled={onboardingBusy}
                      onClick={() => mutateOnboarding('/onboarding/checklist/dismiss')}
                    >
                      Dismiss
                    </button>
                  ) : (
                    <span className="muted">Dismiss after 80%</span>
                  )}
                </div>
              ) : null}
            </div>
            <div
              className="onboarding-progress"
              role="progressbar"
              aria-valuenow={onboarding.progress_pct}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="onboarding-progress-bar"
                style={{ width: `${onboarding.progress_pct}%` }}
              />
            </div>
            <ul className="onboarding-steps">
              {onboarding.steps.map((step) => (
                <li key={step.id} className={step.completed ? 'done' : ''}>
                  <span className="onboarding-mark" aria-hidden>
                    {step.completed ? '✓' : '○'}
                  </span>
                  <Link href={step.href}>{step.title}</Link>
                  {canManageOnboarding && !step.auto_completed && !step.skipped ? (
                    <button
                      type="button"
                      className="onboarding-btn linkish"
                      disabled={onboardingBusy}
                      onClick={() =>
                        mutateOnboarding(`/onboarding/checklist/steps/${step.id}/skip`)
                      }
                    >
                      Skip
                    </button>
                  ) : null}
                  {canManageOnboarding && step.skipped ? (
                    <button
                      type="button"
                      className="onboarding-btn linkish"
                      disabled={onboardingBusy}
                      onClick={() =>
                        mutateOnboarding(`/onboarding/checklist/steps/${step.id}/unskip`)
                      }
                    >
                      Undo skip
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        {children}
      </main>
    </div>
  );
}
