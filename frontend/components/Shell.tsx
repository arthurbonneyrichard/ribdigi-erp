'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { api, clearSessionAndRedirect, idleTimeoutMs } from '../lib/api';
import { StoreProvider } from '../lib/storeContext';
import OnboardingChecklist from './OnboardingChecklist';
import StoreSwitcher from './StoreSwitcher';

type NavItem = [label: string, href: string, module: string];

/** Tenant ERP navigation (business workspace). */
const TENANT_ITEMS: NavItem[] = [
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
  ['Jobs', '/jobs', 'jobs'],
  ['Integrations', '/integrations', 'integrations'],
  ['Security', '/security', 'security'],
  ['AI Assistant', '/ai', 'ai'],
  ['Users', '/users', 'users'],
];

/** Software-owner / platform console navigation only. */
const PLATFORM_ITEMS: NavItem[] = [
  ['Platform', '/platform', 'platform'],
  ['Staff', '/platform/staff', 'platform_staff'],
  ['Reports', '/platform/reports', 'platform_reports'],
  ['Jobs', '/jobs', 'jobs'],
  ['Users', '/users', 'users'],
  ['Notifications', '/notifications', 'notifications'],
  ['Audit', '/audit', 'audit'],
  ['Security', '/security', 'security'],
];

const PLATFORM_ROLES = new Set([
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
]);

/**
 * Modules each tenant role should see in the sidebar.
 * `*` = all tenant modules the role can read via permissions.
 * super_admin is handled separately (platform nav only).
 */
const ROLE_NAV_MODULES: Record<string, string[] | '*'> = {
  company_admin: '*',
  store_manager: [
    'dashboard',
    'inventory',
    'sales',
    'pos',
    'purchasing',
    'expenses',
    'accounting',
    'credit',
    'tax',
    'stores',
    'reports',
    'notifications',
    'users',
    'audit',
    'ai',
    'security',
  ],
  sales_officer: [
    'dashboard',
    'inventory',
    'sales',
    'pos',
    'credit',
    'reports',
    'notifications',
    'ai',
    'security',
  ],
  inventory_officer: [
    'dashboard',
    'inventory',
    'purchasing',
    'reports',
    'notifications',
    'ai',
    'security',
  ],
  accountant: [
    'dashboard',
    'inventory',
    'sales',
    'purchasing',
    'expenses',
    'accounting',
    'credit',
    'tax',
    'reports',
    'notifications',
    'ai',
    'audit',
    'security',
  ],
  cashier: ['dashboard', 'inventory', 'pos', 'sales', 'notifications', 'security'],
};

// Monochrome line icons (inherit the nav text color via currentColor).
const ICONS: Record<string, React.ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </>
  ),
  company: (
    <>
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </>
  ),
  inventory: (
    <>
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <path d="M3.27 6.96 12 12.01l8.73-5.05" />
      <path d="M12 22.08V12" />
    </>
  ),
  sales: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M16 13H8" />
      <path d="M16 17H8" />
    </>
  ),
  pos: (
    <>
      <circle cx="9" cy="21" r="1" />
      <circle cx="20" cy="21" r="1" />
      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
    </>
  ),
  purchasing: (
    <>
      <rect x="1" y="3" width="15" height="13" />
      <path d="M16 8h4l3 3v5h-7V8z" />
      <circle cx="5.5" cy="18.5" r="2.5" />
      <circle cx="18.5" cy="18.5" r="2.5" />
    </>
  ),
  expenses: (
    <>
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </>
  ),
  accounting: (
    <>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </>
  ),
  credit: (
    <>
      <rect x="1" y="4" width="22" height="16" rx="2" />
      <line x1="1" y1="10" x2="23" y2="10" />
    </>
  ),
  tax: (
    <>
      <line x1="19" y1="5" x2="5" y2="19" />
      <circle cx="6.5" cy="6.5" r="2.5" />
      <circle cx="17.5" cy="17.5" r="2.5" />
    </>
  ),
  stores: (
    <>
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <path d="M16 10a4 4 0 0 1-8 0" />
    </>
  ),
  reports: (
    <>
      <line x1="12" y1="20" x2="12" y2="10" />
      <line x1="18" y1="20" x2="18" y2="4" />
      <line x1="6" y1="20" x2="6" y2="16" />
    </>
  ),
  notifications: (
    <>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </>
  ),
  audit: (
    <>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </>
  ),
  backup: (
    <>
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </>
  ),
  jobs: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </>
  ),
  integrations: (
    <>
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </>
  ),
  security: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />,
  ai: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3" />
    </>
  ),
  users: (
    <>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </>
  ),
  platform_staff: (
    <>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </>
  ),
  platform_reports: (
    <>
      <path d="M3 3v18h18" />
      <path d="M7 14l4-4 4 4 5-6" />
    </>
  ),
  platform: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </>
  ),
};

function NavIcon({ name }: { name: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONS[name] ?? ICONS.dashboard}
    </svg>
  );
}

function canReadModule(permissions: Record<string, string[]> | null | undefined, module: string) {
  if (!permissions) return false;
  if (permissions['*']?.includes('*')) return true;
  const actions = permissions[module] || [];
  return actions.includes('*') || actions.includes('read') || actions.includes('write');
}

function navItemsForRole(
  role: string,
  permissions: Record<string, string[]> | null,
  enabledModules: string[] | null
): NavItem[] {
  // Software owner staff: platform console nav only.
  if (PLATFORM_ROLES.has(role)) {
    return PLATFORM_ITEMS.filter(([, , module]) => {
      if (module === 'platform') return true;
      if (permissions?.['*']?.includes('*')) return true;
      return canReadModule(permissions, module);
    });
  }

  const allowed = ROLE_NAV_MODULES[role] ?? ROLE_NAV_MODULES.cashier;
  const packageSet =
    enabledModules && enabledModules.length > 0 ? new Set(enabledModules) : null;
  return TENANT_ITEMS.filter(([, , module]) => {
    // Integrations + Jobs are company-admin ops surfaces; gate like Company.
    const permModule =
      module === 'integrations' || module === 'jobs' ? 'company' : module;
    if (allowed !== '*' && !allowed.includes(permModule) && module !== 'integrations' && module !== 'jobs')
      return false;
    if (allowed !== '*' && (module === 'integrations' || module === 'jobs') && !allowed.includes('company'))
      return false;
    if (
      packageSet &&
      !packageSet.has(permModule) &&
      !['dashboard', 'notifications', 'security'].includes(module)
    ) {
      return false;
    }
    return canReadModule(permissions, permModule);
  });
}

type BellNote = {
  id: string;
  category: string;
  title: string;
  message: string;
  status: string;
  created_at: string;
};

export default function Shell({ children }: { children: React.ReactNode }) {
  const [unread, setUnread] = useState(0);
  const [permissions, setPermissions] = useState<Record<string, string[]> | null>(null);
  const [enabledModules, setEnabledModules] = useState<string[] | null>(null);
  const [role, setRole] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [fullName, setFullName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [hasLogo, setHasLogo] = useState(false);
  const [companyLogoUrl, setCompanyLogoUrl] = useState<string | null>(null);
  const [idleMinutes, setIdleMinutes] = useState(30);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [bellOpen, setBellOpen] = useState(false);
  const [bellNotes, setBellNotes] = useState<BellNote[]>([]);
  const [bellBusy, setBellBusy] = useState(false);
  const pathname = usePathname();
  const isPlatformOwner = PLATFORM_ROLES.has(role);

  useEffect(() => {
    const el = document.documentElement;
    setTheme((el.getAttribute('data-theme') as 'light' | 'dark') || 'light');
    const mql = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (e: MediaQueryListEvent) => {
      // Only follow the device when the user hasn't set an explicit preference.
      if (!localStorage.getItem('theme')) {
        const eff = e.matches ? 'dark' : 'light';
        el.setAttribute('data-theme', eff);
        setTheme(eff);
      }
    };
    mql.addEventListener?.('change', onChange);
    return () => mql.removeEventListener?.('change', onChange);
  }, []);

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    setTheme(next);
  }

  async function logout() {
    try {
      await api('/auth/logout', { method: 'POST' });
    } catch {
      /* revoke best-effort; clear client session regardless */
    }
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('tenant');
    window.location.href = '/';
  }

  async function refreshUnread() {
    try {
      const countRes = await api('/notifications/unread-count');
      setUnread(countRes.data?.count || 0);
    } catch {
      setUnread(0);
    }
  }

  async function loadBellNotes() {
    try {
      const res = await api('/notifications?status=unread&limit=8');
      setBellNotes(res.data || []);
    } catch {
      setBellNotes([]);
    }
  }

  async function openBell() {
    const next = !bellOpen;
    setBellOpen(next);
    if (next) {
      await Promise.all([refreshUnread(), loadBellNotes()]);
    }
  }

  async function markBellRead(id: string) {
    setBellBusy(true);
    try {
      await api(`/notifications/${id}/read`, { method: 'PATCH' });
      await Promise.all([refreshUnread(), loadBellNotes()]);
    } catch {
      /* ignore — panel stays open */
    } finally {
      setBellBusy(false);
    }
  }

  async function markBellAllRead() {
    setBellBusy(true);
    try {
      await api('/notifications/read-all', { method: 'POST' });
      await Promise.all([refreshUnread(), loadBellNotes()]);
    } catch {
      /* ignore */
    } finally {
      setBellBusy(false);
    }
  }

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
        setEnabledModules(
          Array.isArray(meRes.data?.enabled_modules) ? meRes.data.enabled_modules : null
        );
        setRole(meRes.data?.role || '');
        setFullName(meRes.data?.full_name || '');
        setCompanyName(meRes.data?.company_name || '');
        setHasLogo(Boolean(meRes.data?.has_logo));
        const mins = Number(meRes.data?.inactivity_timeout_minutes);
        if (Number.isFinite(mins)) setIdleMinutes(mins);
      } catch {
        if (active) {
          setUnread(0);
          setPermissions({});
          setEnabledModules(null);
          setRole('');
          setCompanyName('');
          setHasLogo(false);
          setCompanyLogoUrl(null);
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
    if (!bellOpen) return;
    function onDoc(e: MouseEvent) {
      const t = e.target as HTMLElement | null;
      if (t && t.closest('.bell-wrap')) return;
      setBellOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setBellOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [bellOpen]);

  useEffect(() => {
    setBellOpen(false);
  }, [pathname]);

  useEffect(() => {
    let revoked = false;
    let objectUrl: string | null = null;
    async function loadLogo() {
      if (!hasLogo) {
        setCompanyLogoUrl(null);
        return;
      }
      try {
        const token = localStorage.getItem('token');
        const tenantId = localStorage.getItem('tenant');
        const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
        const res = await fetch(`${apiBase}/tenants/me/logo`, {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenantId ? { 'X-Tenant-ID': tenantId } : {}),
          },
        });
        if (!res.ok) {
          if (!revoked) setCompanyLogoUrl(null);
          return;
        }
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!revoked) setCompanyLogoUrl(objectUrl);
      } catch {
        if (!revoked) setCompanyLogoUrl(null);
      }
    }
    loadLogo();
    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [hasLogo]);

  // BR-19.3: auto-logout after tenant-configured idle period (default 30 minutes).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const limitMs = idleTimeoutMs(idleMinutes);
    let last = Date.now();
    const bump = () => {
      last = Date.now();
    };
    const events: Array<keyof WindowEventMap> = [
      'mousemove',
      'mousedown',
      'keydown',
      'scroll',
      'touchstart',
      'click',
    ];
    events.forEach((e) => window.addEventListener(e, bump, { passive: true }));
    const onVis = () => {
      if (document.visibilityState === 'visible') bump();
    };
    document.addEventListener('visibilitychange', onVis);
    const id = window.setInterval(() => {
      if (Date.now() - last >= limitMs) {
        clearSessionAndRedirect();
      }
    }, 15000);
    return () => {
      events.forEach((e) => window.removeEventListener(e, bump));
      document.removeEventListener('visibilitychange', onVis);
      window.clearInterval(id);
    };
  }, [idleMinutes]);

  const visible = useMemo(
    () => navItemsForRole(role, permissions, enabledModules),
    [role, permissions, enabledModules]
  );
  const showAlerts = visible.some(([, href]) => href === '/notifications');
  const sidebarLogoSrc = companyLogoUrl || '/brand/logo-sidebar.svg';
  const sidebarLogoAlt = companyLogoUrl
    ? companyName || 'Company logo'
    : 'RIBDIGI ERP';

  return (
    <StoreProvider enabled={Boolean(role) && !isPlatformOwner}>
      <div className={`shell${menuOpen ? ' nav-open' : ''}`}>
      <aside className="side">
        <div className="brand" aria-label="Company brand">
          <img
            className="brand-logo"
            src={sidebarLogoSrc}
            alt={sidebarLogoAlt}
          />
          {companyName ? (
            <div className="brand-name">{companyName}</div>
          ) : isPlatformOwner ? (
            <div className="brand-name">RIBDIGI Platform</div>
          ) : null}
        </div>
        {isPlatformOwner ? <div className="brand-sub">Platform owner console</div> : null}
        <nav className="nav" aria-label={isPlatformOwner ? 'Platform navigation' : 'Tenant navigation'}>
          {visible.map(([n, h, module]) => {
            const active = pathname === h || pathname.startsWith(`${h}/`);
            return (
              <Link
                key={h}
                href={h}
                className={active ? 'active' : undefined}
                aria-current={active ? 'page' : undefined}
                onClick={() => setMenuOpen(false)}
              >
                <span className="nav-ico">
                  <NavIcon name={module} />
                </span>
                <span className="nav-label">
                  {n}
                  {h === '/notifications' && unread > 0 ? ` (${unread})` : ''}
                </span>
              </Link>
            );
          })}
        </nav>
        <div className="side-foot">A Ribdigi House Product</div>
      </aside>
      <div className="side-backdrop" onClick={() => setMenuOpen(false)} aria-hidden />
      <main className="main">
        <div className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="menu-btn"
              aria-label="Toggle navigation menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((v) => !v)}
            >
              <span aria-hidden>{'\u2630'}</span>
              <span className="menu-btn-label">Menu</span>
            </button>
          </div>
          {!isPlatformOwner ? (
            <div className="topbar-context">
              <StoreSwitcher visible />
            </div>
          ) : (
            <div className="topbar-context topbar-context-spacer" aria-hidden />
          )}
          <div className="topbar-right">
            <button
              type="button"
              className="theme-btn"
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              <span aria-hidden>{theme === 'dark' ? '\u2600\ufe0f' : '\ud83c\udf19'}</span>
            </button>
            {showAlerts && (
              <div className="bell-wrap">
                <button
                  type="button"
                  className="bell"
                  aria-label={unread > 0 ? `Alerts, ${unread} unread` : 'Alerts'}
                  aria-expanded={bellOpen}
                  aria-haspopup="dialog"
                  onClick={() => openBell()}
                >
                  <span className="bell-ico" aria-hidden>
                    {'\ud83d\udd14'}
                  </span>
                  <span className="bell-label">Alerts</span>
                  {unread > 0 ? <span className="bell-badge">{unread > 99 ? '99+' : unread}</span> : null}
                </button>
                {bellOpen && (
                  <div className="bell-panel" role="dialog" aria-label="Notification center">
                    <div className="bell-panel-head">
                      <strong>Notifications</strong>
                      <span className="muted">{unread} unread</span>
                    </div>
                    <div className="bell-panel-list">
                      {bellNotes.length === 0 ? (
                        <p className="muted bell-empty">No unread alerts</p>
                      ) : (
                        bellNotes.map((n) => (
                          <div key={n.id} className="bell-item">
                            <div className="bell-item-meta">
                              <span className="bell-cat">{n.category}</span>
                              <span className="muted">{n.created_at?.slice?.(0, 16) || ''}</span>
                            </div>
                            <div className="bell-item-title">{n.title}</div>
                            <div className="muted bell-item-msg">{n.message}</div>
                            <button
                              type="button"
                              className="bell-item-action"
                              disabled={bellBusy}
                              onClick={() => markBellRead(n.id)}
                            >
                              Mark read
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="bell-panel-foot">
                      <button type="button" disabled={bellBusy || unread === 0} onClick={markBellAllRead}>
                        Mark all read
                      </button>
                      <Link href="/notifications" className="bell-view-all" onClick={() => setBellOpen(false)}>
                        View all
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            )}
            {fullName && (
              <span className="userchip" title={fullName}>
                <span className="uavatar" aria-hidden>
                  {fullName.trim().charAt(0).toUpperCase() || 'U'}
                </span>
                <span className="uname">{fullName.trim().split(/\s+/)[0]}</span>
              </span>
            )}
            <button type="button" className="logout-btn" onClick={logout} aria-label="Log out" title="Log out">
              <span className="logout-ico" aria-hidden>
                {'\u21a9'}
              </span>
              <span className="logout-label">Log out</span>
            </button>
          </div>
        </div>
        {!isPlatformOwner && (
          <OnboardingChecklist
            canManage={role === 'company_admin' || role === 'super_admin'}
          />
        )}
        {children}
      </main>
    </div>
    </StoreProvider>
  );
}
