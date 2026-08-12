'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { canReadAnyModule, canReadModule } from '../lib/rbac';
import {
  getSelectedStoreId,
  setSelectedStoreId,
  subscribeStoreContext,
} from '../lib/storeContext';

/** Stage 95 N1/P1 — MVP Navigation IA (discoverability; existing engines). */
type NavLink = {
  kind: 'link';
  label: string;
  href: string;
  modules: string[];
};

type NavSection = { kind: 'section'; label: string };

type NavEntry = NavLink | NavSection;

const primaryNavSpec: NavEntry[] = [
  { kind: 'link', label: 'Dashboard', href: '/dashboard', modules: ['dashboard'] },
  { kind: 'section', label: 'Commerce' },
  { kind: 'link', label: 'Inventory', href: '/inventory', modules: ['inventory'] },
  {
    kind: 'link',
    label: 'Products',
    href: '/inventory?tab=products',
    modules: ['inventory'],
  },
  { kind: 'link', label: 'Stock', href: '/inventory?tab=stock', modules: ['inventory'] },
  { kind: 'link', label: 'Low stock', href: '/inventory?tab=lowstock', modules: ['inventory'] },
  {
    kind: 'link',
    label: 'Stock Counts',
    href: '/inventory?tab=counts',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Warehouse Transfers',
    href: '/inventory?tab=transfers',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Variants',
    href: '/inventory?tab=variants',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Batches',
    href: '/inventory?tab=batches',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Expiry',
    href: '/inventory?tab=expiry',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Stock Adjustments',
    href: '/inventory?tab=ops',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Opening Stock',
    href: '/inventory?tab=opening',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Movements',
    href: '/inventory?tab=movements',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Catalog Categories',
    href: '/inventory?tab=catalog#categories',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Catalog Brands',
    href: '/inventory?tab=catalog#brands',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Catalog Units',
    href: '/inventory?tab=catalog#units',
    modules: ['inventory'],
  },
  { kind: 'link', label: 'Sales', href: '/sales', modules: ['sales'] },
  {
    kind: 'link',
    label: 'Quotations',
    href: '/sales?tab=quotations',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Customer Groups',
    href: '/sales?tab=groups',
    modules: ['sales', 'customers'],
  },
  {
    kind: 'link',
    label: 'Sales Returns',
    href: '/sales?tab=returns',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Sales Invoices',
    href: '/sales?tab=invoices',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Draft Invoices',
    href: '/sales?tab=invoices&status=draft',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Overdue Invoices',
    href: '/sales?tab=invoices&status=overdue',
    modules: ['sales'],
  },
  { kind: 'link', label: 'POS', href: '/pos', modules: ['pos'] },
  {
    kind: 'link',
    label: 'POS Sessions',
    href: '/pos#sessions',
    modules: ['pos'],
  },
  { kind: 'link', label: 'Purchasing', href: '/purchasing', modules: ['purchasing'] },
  {
    kind: 'link',
    label: 'Purchase Requests',
    href: '/purchasing?tab=requests',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Pending PRs',
    href: '/purchasing?tab=requests&pr_status=pending',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Purchase Orders',
    href: '/purchasing?tab=orders',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Open POs',
    href: '/purchasing?tab=orders&po_status=open',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'GRN',
    href: '/purchasing?tab=grn',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Purchase Invoices',
    href: '/purchasing?tab=invoices',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Outstanding Purchases',
    href: '/purchasing?tab=invoices&status=outstanding',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Purchase Returns',
    href: '/purchasing?tab=returns',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Purchase Settings',
    href: '/purchasing?tab=settings',
    modules: ['purchasing'],
  },
  { kind: 'section', label: 'People' },
  {
    kind: 'link',
    label: 'Customers',
    href: '/sales?tab=customers',
    modules: ['sales', 'customers'],
  },
  {
    kind: 'link',
    label: 'Suppliers',
    href: '/purchasing?tab=suppliers',
    modules: ['purchasing', 'suppliers'],
  },
  // Stage 96 L1 — Billers alias (Users + salesperson report; not a parallel CRUD engine)
  {
    kind: 'link',
    label: 'Billers',
    href: '/reports?tab=salesperson',
    modules: ['reports', 'users'],
  },
  { kind: 'section', label: 'Finance' },
  { kind: 'link', label: 'Expenses', href: '/expenses', modules: ['expenses'] },
  {
    kind: 'link',
    label: 'Pending Expenses',
    href: '/expenses?status=pending',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Expense Approval Matrix',
    href: '/expenses#approval-matrix',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Recurring Expenses',
    href: '/expenses#recurring',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Expense Categories & Budgets',
    href: '/expenses#budgets',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Income',
    href: '/accounting?tab=ledger#profit-loss',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Money Transfer',
    href: '/accounting?tab=ledger#money-transfer',
    modules: ['accounting'],
  },
  { kind: 'link', label: 'Accounting', href: '/accounting', modules: ['accounting'] },
  {
    kind: 'link',
    label: 'Chart of Accounts',
    href: '/accounting?tab=ledger#coa',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Journals',
    href: '/accounting?tab=ledger#journals',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Unposted Journals',
    href: '/accounting?tab=ledger&status=unposted#journals',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Posted Journals',
    href: '/accounting?tab=ledger&status=posted#journals',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Trial Balance',
    href: '/accounting?tab=ledger#trial-balance',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Opening Balances',
    href: '/accounting?tab=ledger#opening-balances',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Bank Reconciliation',
    href: '/accounting?tab=reconcile',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Cheques',
    href: '/accounting?tab=cheques',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Pending Cheques',
    href: '/accounting?tab=cheques&cheque_status=pending',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Received Cheques',
    href: '/accounting?tab=cheques&cheque_direction=received',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Issued Cheques',
    href: '/accounting?tab=cheques&cheque_direction=issued',
    modules: ['accounting'],
  },
  { kind: 'link', label: 'Credit', href: '/credit', modules: ['credit'] },
  {
    kind: 'link',
    label: 'Outstanding Receivables',
    href: '/credit?kind=receivable',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Outstanding Payables',
    href: '/credit?kind=payable',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Credit Aging',
    href: '/credit#aging',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Early Pay Terms',
    href: '/credit#early-pay',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Exchange Rates',
    href: '/credit#exchange-rates',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Payment Schedule',
    href: '/credit?kind=payable#payment-schedule',
    modules: ['credit'],
  },
  { kind: 'link', label: 'Tax', href: '/tax', modules: ['tax'] },
  {
    kind: 'link',
    label: 'Tax Rates',
    href: '/tax#rates',
    modules: ['tax'],
  },
  {
    kind: 'link',
    label: 'Tax Calculator',
    href: '/tax#calculator',
    modules: ['tax'],
  },
  {
    kind: 'link',
    label: 'Tax Filing Pack',
    href: '/tax#filing',
    modules: ['tax'],
  },
  { kind: 'section', label: 'Operations' },
  { kind: 'link', label: 'Stores', href: '/stores', modules: ['stores'] },
  { kind: 'link', label: 'Warehouse', href: '/stores#warehouses', modules: ['stores'] },
  {
    kind: 'link',
    label: 'Inter-store Transfers',
    href: '/stores#transfers',
    modules: ['stores'],
  },
  {
    kind: 'link',
    label: 'Delivery status',
    href: '/sales?tab=orders',
    modules: ['sales'],
  },
  { kind: 'link', label: 'Reports', href: '/reports', modules: ['reports'] },
  {
    kind: 'link',
    label: 'Reports Summary',
    href: '/reports?tab=summary',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Sales Report',
    href: '/reports?tab=sales',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Customers Report',
    href: '/reports?tab=customers',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Stores Report',
    href: '/reports?tab=stores',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Transfers Report',
    href: '/reports?tab=transfers',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Report Schedules',
    href: '/reports?tab=schedules',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Profit & Loss',
    href: '/reports?tab=pnl',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Cash Flow',
    href: '/reports?tab=cashflow',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Balance Sheet',
    href: '/reports?tab=balancesheet',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Inventory Report',
    href: '/reports?tab=inventory',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Purchases Report',
    href: '/reports?tab=purchases',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Credit Report',
    href: '/reports?tab=credit',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Tax Report',
    href: '/reports?tab=tax',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Expenses Report',
    href: '/reports?tab=expenses',
    modules: ['reports'],
  },
  { kind: 'link', label: 'Notifications', href: '/notifications', modules: ['notifications'] },
  { kind: 'link', label: 'AI Assistant', href: '/ai', modules: ['ai'] },
  {
    kind: 'link',
    label: 'AI Chat',
    href: '/ai#chat',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Forecast',
    href: '/ai#forecast',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Dead Stock',
    href: '/ai#dead-stock',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Insights',
    href: '/ai#insights',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Security',
    href: '/ai#security',
    modules: ['ai'],
  },
  { kind: 'link', label: 'Settings', href: '/company', modules: ['company'] },
  {
    kind: 'link',
    label: 'Company Tax',
    href: '/company#tax',
    modules: ['company', 'tax'],
  },
  {
    kind: 'link',
    label: 'Fiscal Period',
    href: '/company#fiscal-period',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Email Settings',
    href: '/company#email',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'SMS Settings',
    href: '/company#sms',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Document templates',
    href: '/company#document-templates',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Branches',
    href: '/company#branches',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Document numbering',
    href: '/company#document-numbering',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Media storage',
    href: '/company#media',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Notification settings',
    href: '/notifications#preferences',
    modules: ['notifications'],
  },
];

const userMgmtLinks: NavLink[] = [
  { kind: 'link', label: 'Users', href: '/users', modules: ['users'] },
  { kind: 'link', label: 'Roles', href: '/admin/roles', modules: ['users'] },
  {
    kind: 'link',
    label: 'Custom Roles',
    href: '/admin/roles#custom',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'System Roles',
    href: '/admin/roles#system',
    modules: ['users'],
  },
  { kind: 'link', label: 'Permissions', href: '/admin/permissions', modules: ['users'] },
  { kind: 'link', label: 'Audit', href: '/audit', modules: ['audit'] },
  { kind: 'link', label: 'Activity', href: '/activity', modules: ['audit'] },
  { kind: 'link', label: 'Backup', href: '/backup#schedule', modules: ['backup'] },
  {
    kind: 'link',
    label: 'Backup & Restore',
    href: '/backup#restore',
    modules: ['backup'],
  },
  { kind: 'link', label: 'Security', href: '/security', modules: ['security'] },
  {
    kind: 'link',
    label: 'Passkeys',
    href: '/security#passkeys',
    modules: ['security'],
  },
  {
    kind: 'link',
    label: 'TOTP',
    href: '/security#totp',
    modules: ['security'],
  },
  {
    kind: 'link',
    label: 'Webhooks',
    href: '/security#webhooks',
    modules: ['security'],
  },
  {
    kind: 'link',
    label: 'API keys',
    href: '/security#api-keys',
    modules: ['security'],
  },
  {
    kind: 'link',
    label: 'Active sessions',
    href: '/security#sessions',
    modules: ['security'],
  },
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
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [principal, setPrincipal] = useState('');
  const [idleMinutes, setIdleMinutes] = useState(30);
  const [stores, setStores] = useState<StoreOption[]>([]);
  const [storeId, setStoreId] = useState('');
  const [onboarding, setOnboarding] = useState<OnboardingChecklist | null>(null);
  const [onboardingBusy, setOnboardingBusy] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchResults, setSearchResults] = useState<
    { kind: string; id?: string; label: string; meta?: string; href: string }[]
  >([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const canManageOnboarding = role === 'company_admin' || role === 'super_admin';

  useEffect(() => {
    setStoreId(getSelectedStoreId());
    return subscribeStoreContext((id) => setStoreId(id));
  }, []);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const meRes = await api('/me');
        if (!active) return;
        // ADR-137 — platform staff use Ribdigi House console, not tenant ERP nav
        // (allow /security for MFA enrollment).
        if (meRes.data?.principal === 'platform') {
          setPrincipal('platform');
          const path = typeof window !== 'undefined' ? window.location.pathname : '';
          if (path !== '/security' && !path.startsWith('/security/')) {
            window.location.replace(meRes.data?.redirect_path || '/platform/dashboard');
            return;
          }
          setPermissions(meRes.data?.permissions || {});
          setRole(meRes.data?.role || '');
          setFullName(meRes.data?.full_name || '');
          setEmail(meRes.data?.email || '');
          setIdleMinutes(Number(meRes.data?.inactivity_timeout_minutes) || 30);
          setUnread(0);
          return;
        }
        setPrincipal(meRes.data?.principal || 'tenant');
        const countRes = await api('/notifications/unread-count').catch(() => ({
          data: { count: 0 },
        }));
        if (!active) return;
        setUnread(countRes.data?.count || 0);
        setPermissions(meRes.data?.permissions || {});
        setRole(meRes.data?.role || '');
        setFullName(meRes.data?.full_name || '');
        setEmail(meRes.data?.email || '');
        setIdleMinutes(Number(meRes.data?.inactivity_timeout_minutes) || 30);
      } catch {
        if (active) {
          setUnread(0);
          setPermissions({});
          setRole('');
          setFullName('');
          setEmail('');
          setPrincipal('');
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

  async function logout() {
    try {
      await api('/auth/logout', { method: 'POST', body: '{}' });
    } catch {
      // clear local session anyway
    }
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/';
  }

  async function runSearch(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const q = searchQ.trim();
    if (!q) {
      setSearchResults([]);
      setSearchOpen(false);
      return;
    }
    setSearchBusy(true);
    try {
      const r = await api(`/search?q=${encodeURIComponent(q)}`);
      setSearchResults(r.data?.results || []);
      setSearchOpen(true);
    } catch {
      setSearchResults([]);
      setSearchOpen(true);
    } finally {
      setSearchBusy(false);
    }
  }

  const linkVisible = (link: NavLink) =>
    principal === 'platform'
      ? link.href === '/security' || link.href.startsWith('/security')
      : canReadAnyModule(permissions, link.modules);

  const visiblePrimary: NavEntry[] = [];
  if (principal !== 'platform') {
    for (const entry of primaryNavSpec) {
      if (entry.kind === 'section') {
        visiblePrimary.push(entry);
        continue;
      }
      if (linkVisible(entry)) visiblePrimary.push(entry);
    }
    // Drop empty section headers (no following visible link before next section/end).
    const pruned: NavEntry[] = [];
    for (let i = 0; i < visiblePrimary.length; i++) {
      const entry = visiblePrimary[i];
      if (entry.kind === 'section') {
        const hasLink = visiblePrimary
          .slice(i + 1)
          .find((e) => e.kind === 'section' || e.kind === 'link');
        if (hasLink && hasLink.kind === 'link') pruned.push(entry);
      } else {
        pruned.push(entry);
      }
    }
    visiblePrimary.length = 0;
    visiblePrimary.push(...pruned);
  }

  const visibleUserMgmt =
    principal === 'platform'
      ? userMgmtLinks.filter((l) => l.href === '/security')
      : userMgmtLinks.filter(linkVisible);

  const showStoreSwitcher =
    principal !== 'platform' && canReadModule(permissions, 'stores') && stores.length > 0;

  return (
    <div className={`shell${navOpen ? ' nav-open' : ''}`}>
      <aside className="side" id="tenant-side-nav">
        <div className="brand">{principal === 'platform' ? 'Ribdigi House' : 'RIBDIGI ERP'}</div>
        <nav className="nav" aria-label="Main">
          {principal === 'platform' && (
            <Link href="/platform/dashboard" onClick={() => setNavOpen(false)}>
              Platform console
            </Link>
          )}
          {visiblePrimary.map((entry, idx) =>
            entry.kind === 'section' ? (
              <div
                key={`section-${entry.label}-${idx}`}
                className="nav-section"
                aria-hidden={false}
              >
                {entry.label}
              </div>
            ) : (
              <Link
                key={entry.href + entry.label}
                href={entry.href}
                onClick={() => setNavOpen(false)}
              >
                {entry.label}
                {entry.href === '/notifications' && unread > 0 ? ` (${unread})` : ''}
              </Link>
            ),
          )}
          {visibleUserMgmt.length > 0 && (
            <>
              <div className="nav-section">User Management</div>
              {visibleUserMgmt.map((l) => (
                <Link key={l.href} href={l.href} onClick={() => setNavOpen(false)}>
                  {l.label}
                </Link>
              ))}
            </>
          )}
        </nav>
      </aside>
      <main className="main">
        <div className="topbar">
          <button
            type="button"
            className="nav-toggle"
            aria-expanded={navOpen}
            aria-controls="tenant-side-nav"
            onClick={() => setNavOpen((v) => !v)}
          >
            Menu
          </button>
          {principal !== 'platform' && (
            <form className="global-search" onSubmit={runSearch} role="search">
              <input
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                onFocus={() => {
                  if (searchResults.length) setSearchOpen(true);
                }}
                placeholder="Search products or customers"
                aria-label="Global search"
              />
              <button type="submit" disabled={searchBusy}>
                {searchBusy ? '…' : 'Search'}
              </button>
              {searchOpen && (
                <div className="global-search-results" role="listbox">
                  {searchResults.length === 0 ? (
                    <p className="muted" style={{ margin: 0, padding: 8 }}>
                      No matches
                    </p>
                  ) : (
                    searchResults.map((hit) => (
                      <Link
                        key={`${hit.kind}-${hit.id || hit.label}`}
                        href={hit.href}
                        role="option"
                        onClick={() => {
                          setSearchOpen(false);
                          setSearchQ('');
                        }}
                      >
                        <strong>{hit.label}</strong>
                        <span className="muted">
                          {' '}
                          · {hit.kind}
                          {hit.meta ? ` · ${hit.meta}` : ''}
                        </span>
                      </Link>
                    ))
                  )}
                </div>
              )}
            </form>
          )}
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
          <div className="topbar-spacer" />
          {canReadModule(permissions, 'notifications') && (
            <Link href="/notifications" className="bell">
              Alerts{unread > 0 ? ` · ${unread}` : ''}
            </Link>
          )}
          <div className="profile-menu">
            <button
              type="button"
              className="profile-trigger"
              aria-expanded={profileOpen}
              onClick={() => setProfileOpen((v) => !v)}
            >
              {fullName || email || 'Account'}
            </button>
            {profileOpen && (
              <div className="profile-dropdown" role="menu">
                <p className="muted" style={{ margin: '0 0 8px', fontSize: 12 }}>
                  {email || '—'}
                  {role ? ` · ${role}` : ''}
                </p>
                <Link
                  href="/security"
                  role="menuitem"
                  onClick={() => setProfileOpen(false)}
                >
                  Security / 2FA
                </Link>
                <button type="button" role="menuitem" onClick={() => void logout()}>
                  Log out
                </button>
              </div>
            )}
          </div>
        </div>
        {navOpen && (
          <button
            type="button"
            className="nav-backdrop"
            aria-label="Close menu"
            onClick={() => setNavOpen(false)}
          />
        )}
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
