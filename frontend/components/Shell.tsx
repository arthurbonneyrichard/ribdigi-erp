'use client';

import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api, apiRoot, clearSessionAndRedirect, idleTimeoutMs, isConfirmedAuthExpiry, tenantHeaderValue, getAccessToken, hydrateAuth } from '../lib/api';
import { formatNoticeTime, notifyCategoryLabel } from '../lib/notifyText';
import { industryAllowsModule, INDUSTRY_SPECIFIC_MODULES } from '../lib/industryModules';
import { industryLabel, normalizeIndustry } from '../lib/industries';
import { isStoreNetworkNavItem, tenantIsMultiStore, type StoreEntitlementMe } from '../lib/tenantNav';
import { getMe, invalidateMeCache } from '../lib/meCache';
import { closeShiftForSignOut, openShiftForSignedInUser } from '../lib/cashierShift';
import { linkStatusText, type LinkSnapshot } from '../lib/connectivity';
import { requestPosReturnPanel, requestPosShiftPanel, subscribePosDrawerBridge, type PosDrawerBridgeState } from '../lib/posDrawerBridge';
import { PosOfflineTopSlot } from '../lib/posOfflineSlot';
import { prefetchGet } from '../lib/prefetchCache';
import { prefetchPathsForHref } from '../lib/navPrefetch';
import { loadUserTheme, writeUserTheme } from '../lib/theme';
import { StoreProvider } from '../lib/storeContext';
import {
  ACTIVITY_EVENTS,
  LAST_ACTIVITY_KEY,
  bumpLastActivity,
  hasStoredActivity,
  isIdleExpired,
  readLastActivity,
  resetIdleWriteThrottle,
  shouldWarnIdle,
} from '../lib/idleSession';
import {
  ALWAYS_LIST_NAV_GROUP_IDS,
  CASHIER_NAV_MODULES,
  RESTAURANT_NAV_ITEMS,
  filterNavForIndustry,
  groupedTenantNav,
  industryFeatureBlock,
  HOTEL_CASHIER_NAV_MODULES,
  HOTEL_INVENTORY_PROCUREMENT_CHILDREN,
  HOTEL_NAV_ITEMS,
  isHotelIndustry,
  navAllowlistFromPermissions,
  navItemVisibleForRole,
  PEOPLE_NAV_ITEMS,
  platformNavItemsForRole,
  unauthorizedNavRedirect,
  type NavGroup,
  type NavItem,
} from '../lib/tenantNav';
import { chromeLogoAlt, chromeLogoSrc, PLATFORM_SIDEBAR_LOGO } from '../lib/chromeBrand';
import OnboardingChecklist from './OnboardingChecklist';
import StoreSwitcher from './StoreSwitcher';

/** Tenant ERP navigation (business workspace).
 * Hotel/FMCG nav items are packageable but only appear when `/me.enabled_modules`
 * includes them — backend intersects package entitlements with business-type
 * (industry) allowlists, so menus alone are never the security boundary.
 */
const TENANT_ITEMS: NavItem[] = [
  ['Dashboard', '/dashboard', 'dashboard'],
  ['Company', '/company', 'company'],
  ['Subscription billing', '/company/billing', 'company'],
  ['Products', '/inventory?tab=products', 'inventory'],
  ['Categories', '/inventory?tab=categories', 'inventory'],
  ['Brands', '/inventory?tab=brands', 'inventory'],
  ['Units', '/inventory?tab=units', 'inventory'],
  ['Variants', '/inventory?tab=variants', 'inventory'],
  ['Manage Stock', '/inventory?tab=whstock', 'inventory'],
  ['Stock Adjustment', '/inventory?tab=adjust', 'inventory'],
  ['Stock Transfer', '/inventory?tab=transfers', 'inventory'],
  ['Stock Count', '/inventory?tab=counts', 'inventory'],
  ['Stock History', '/inventory?tab=movements', 'inventory'],
  ['Low Stock', '/inventory?tab=lowstock', 'inventory'],
  ['Expiry', '/inventory?tab=expiry', 'inventory'],
  ['Batches', '/inventory?tab=batches', 'inventory'],
  ['Sales', '/sales', 'sales'],
  ['Customers', '/customers', 'sales'],
  ['Gift cards', '/gift-cards', 'pos'],
  ['POS', '/pos', 'pos'],
  ['Suppliers', '/purchasing?tab=suppliers', 'purchasing'],
  ['Orders', '/purchasing?tab=orders', 'purchasing'],
  ['Receive Goods', '/purchasing?tab=grn', 'purchasing'],
  ['Supplier Bills', '/purchasing?tab=invoices', 'purchasing'],
  ['Returns', '/purchasing?tab=returns', 'purchasing'],
  ['Payments', '/credit?kind=payable&panel=pay', 'credit'],
  ['Balances', '/credit?kind=payable', 'credit'],
  ['History', '/purchasing?tab=history', 'purchasing'],
  ['Expenses', '/expenses', 'expenses'],
  ['Accounting', '/accounting', 'accounting'],
  ['Payment notice', '/billing', 'accounting'],
  ['Customer credit', '/credit?kind=receivable', 'credit'],
  ['Tax', '/tax', 'tax'],
  ...PEOPLE_NAV_ITEMS,
  ...HOTEL_NAV_ITEMS,
  ...HOTEL_INVENTORY_PROCUREMENT_CHILDREN,
  ...RESTAURANT_NAV_ITEMS,
  ['Reports', '/reports', 'reports'],
  ['Notifications', '/notifications', 'notifications'],
  ['Audit', '/audit', 'audit'],
  ['Backup', '/backup', 'backup'],
  ['Online store', '/ecommerce', 'ecommerce'],
  ['Integrations', '/integrations', 'integrations'],
  ['Security', '/security', 'security'],
  ['Printers', '/printers', 'printers'],
  ['AI Assistant', '/ai', 'ai'],
  ['Help & Support', '/support', 'support'],
];

/** Never accordion — click navigates even if later given extra children. */
const STANDALONE_NAV_IDS = new Set(['dashboard', 'notifications', 'hotel', 'support']);

const TENANT_NAV_GROUPS: NavGroup[] = [
  { id: 'dashboard', label: 'Dashboard', items: [['Dashboard', '/dashboard', 'dashboard']] },
  { id: 'inventory', label: 'Inventory', items: [
    ['Products', '/inventory?tab=products', 'inventory'],
    ['Categories', '/inventory?tab=categories', 'inventory'],
    ['Brands', '/inventory?tab=brands', 'inventory'],
    ['Units', '/inventory?tab=units', 'inventory'],
    ['Variants', '/inventory?tab=variants', 'inventory'],
    ['Manage Stock', '/inventory?tab=whstock', 'inventory'],
    ['Stock Adjustment', '/inventory?tab=adjust', 'inventory'],
    ['Stock Transfer', '/inventory?tab=transfers', 'inventory'],
    ['Stock Count', '/inventory?tab=counts', 'inventory'],
    ['Stock History', '/inventory?tab=movements', 'inventory'],
    ['Low Stock', '/inventory?tab=lowstock', 'inventory'],
    ['Expiry', '/inventory?tab=expiry', 'inventory'],
    ['Batches', '/inventory?tab=batches', 'inventory'],
  ] },
  {
    id: 'sales',
    label: 'Sales and POS',
    items: [
      ['Sales', '/sales', 'sales'],
      ['Customers', '/customers', 'sales'],
      ['Gift cards', '/gift-cards', 'pos'],
      ['POS', '/pos', 'pos'],
    ],
  },
  { id: 'purchases', label: 'Purchases', items: [
    ['Suppliers', '/purchasing?tab=suppliers', 'purchasing'],
    ['Orders', '/purchasing?tab=orders', 'purchasing'],
    ['Receive Goods', '/purchasing?tab=grn', 'purchasing'],
    ['Supplier Bills', '/purchasing?tab=invoices', 'purchasing'],
    ['Returns', '/purchasing?tab=returns', 'purchasing'],
    ['Payments', '/credit?kind=payable&panel=pay', 'credit'],
    ['Balances', '/credit?kind=payable', 'credit'],
    ['History', '/purchasing?tab=history', 'purchasing'],
  ] },
  {
    id: 'finance',
    label: 'Finance and Accounts',
    items: [
      ['Expenses', '/expenses', 'expenses'],
      ['Accounting', '/accounting', 'accounting'],
      ['Payment notice', '/billing', 'accounting'],
      ['Customer credit', '/credit?kind=receivable', 'credit'],
      ['Tax', '/tax', 'tax'],
    ],
  },
  {
    id: 'reports',
    label: 'Reports',
    items: [
      ['Reports', '/reports', 'reports'],
      ['Audit', '/audit', 'audit'],
    ],
  },
  {
    id: 'people',
    label: 'User Management',
    items: [...PEOPLE_NAV_ITEMS],
  },
  { id: 'notifications', label: 'Notifications', items: [['Notifications', '/notifications', 'notifications']] },
  { id: 'support', label: 'Help & Support', items: [['Help & Support', '/support', 'support']] },
  {
    id: 'settings',
    label: 'Settings',
    items: [
      ['Company', '/company', 'company'],
      ['Subscription billing', '/company/billing', 'company'],
      ['Online store', '/ecommerce', 'ecommerce'],
      ['Integrations', '/integrations', 'integrations'],
      ['Security', '/security', 'security'],
      ['Printers', '/printers', 'printers'],
      ['Backup', '/backup', 'backup'],
      ['AI Assistant', '/ai', 'ai'],
    ],
  },
  {
    id: 'industry',
    label: 'Industry-specific features',
    items: [
      ...HOTEL_NAV_ITEMS,
      ...RESTAURANT_NAV_ITEMS,
    ],
  },
];

function usesAccordion(group: NavGroup): boolean {
  if (!group.label || STANDALONE_NAV_IDS.has(group.id)) return false;
  if (ALWAYS_LIST_NAV_GROUP_IDS.has(group.id)) return false;
  if (group.id === 'hotel-inventory') return group.items.length > 0;
  return group.items.length > 1;
}

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
    'hotel',
    'fmcg',
    'hospital',
    'restaurant',
    'reports',
    'notifications',
    'users',
    'audit',
    'ai',
    'security',
    'printers',
    'support',
    'ecommerce',
  ],
  sales_officer: [
    'dashboard',
    'inventory',
    'sales',
    'pos',
    'credit',
    'hotel',
    'fmcg',
    'hospital',
    'restaurant',
    'reports',
    'notifications',
    'ai',
    'security',
    'support',
    'ecommerce',
  ],
  inventory_officer: [
    'dashboard',
    'inventory',
    'purchasing',
    'restaurant',
    'reports',
    'notifications',
    'ai',
    'security',
    'support',
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
    'support',
  ],
  cashier: [...CASHIER_NAV_MODULES],
  hotel_manager: [
    'dashboard',
    'hotel',
    'inventory',
    'pos',
    'purchasing',
    'expenses',
    'accounting',
    'credit',
    'reports',
    'notifications',
    'users',
    'audit',
    'security',
    'company',
    'printers',
    'support',
  ],
  hotel_front_desk: ['hotel', 'notifications', 'security', 'printers', 'support'],
  hotel_reservations: ['hotel', 'notifications', 'security', 'support'],
  hotel_housekeeping: ['hotel', 'inventory', 'notifications', 'security', 'support'],
  hotel_maintenance: ['hotel', 'inventory', 'notifications', 'security', 'support'],
  hotel_cashier: [...HOTEL_CASHIER_NAV_MODULES],
  hotel_auditor: ['hotel', 'reports', 'audit', 'accounting', 'notifications', 'security', 'support'],
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
  ecommerce: (
    <>
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </>
  ),
  printers: (
    <>
      <polyline points="6 9 6 2 18 2 18 9" />
      <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
      <rect x="6" y="14" width="12" height="8" />
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
  hotel: (
    <>
      <path d="M3 21h18" />
      <path d="M5 21V7l7-4 7 4v14" />
      <path d="M9 10h.01" />
      <path d="M15 10h.01" />
      <path d="M9 14h.01" />
      <path d="M15 14h.01" />
      <path d="M9 18h.01" />
      <path d="M15 18h.01" />
    </>
  ),
  fmcg: (
    <>
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <path d="M3.27 6.96 12 12.01l8.73-5.05" />
      <path d="M12 22.08V12" />
      <circle cx="12" cy="12" r="2" />
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
  platform_tenants: (
    <>
      <path d="M3 21h18" />
      <path d="M5 21V7l7-4 7 4v14" />
      <path d="M9 21v-6h6v6" />
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
  support: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2" />
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

const DEFAULT_NAV_TABS: Record<string, string> = {
  '/inventory': 'products',
  '/purchasing': 'orders',
  '/reports': 'summary',
};

function hrefParts(href: string): { path: string; params: URLSearchParams; hash: string } {
  const hashIdx = href.indexOf('#');
  const hash = hashIdx === -1 ? '' : href.slice(hashIdx + 1);
  const withoutHash = hashIdx === -1 ? href : href.slice(0, hashIdx);
  const q = withoutHash.indexOf('?');
  const path = ((q === -1 ? withoutHash : withoutHash.slice(0, q)).replace(/\/$/, '') || '/');
  const params = new URLSearchParams(q === -1 ? '' : withoutHash.slice(q + 1));
  return { path, params, hash };
}

function currentNavHash(path: string, locationHash: string): string {
  const h = (locationHash || '').replace(/^#/, '');
  if (h) return h;
  if (path === '/stores') return 'stores';
  return '';
}

function currentNavValue(key: string, path: string, current: URLSearchParams): string {
  const raw = current.get(key) || '';
  if (raw) return raw;
  if (key === 'tab') return DEFAULT_NAV_TABS[path] || '';
  if (key === 'kind' && path === '/credit') return 'receivable';
  return '';
}

/** Highlight the most specific item (query- and hash-aware). /platform must not stay active on /platform/staff. */
function navMatchScore(pathname: string, search: string, href: string, locationHash = ''): number {
  const currentPath = pathname.split('?')[0].replace(/\/$/, '') || '/';
  const current = new URLSearchParams((search || '').replace(/^\?/, ''));
  const target = hrefParts(href);
  if (!(currentPath === target.path || currentPath.startsWith(`${target.path}/`))) return -1;
  for (const pair of Array.from(target.params.entries())) {
    const [key, value] = pair;
    if (currentNavValue(key, currentPath, current) !== value) return -1;
  }
  if (!target.params.has('panel') && current.get('panel') && target.params.get('kind') === 'payable') {
    return -1;
  }
  const effectiveHash = currentNavHash(currentPath, locationHash);
  if (target.hash && effectiveHash !== target.hash) return -1;
  const hashBonus = target.hash && effectiveHash === target.hash ? 8 : 0;
  return target.path.length * 20 + Array.from(target.params.keys()).length * 5 + (currentPath === target.path ? 3 : 0) + hashBonus;
}

function isNavActive(pathname: string, href: string, items: NavItem[], search = '', locationHash = ''): boolean {
  const score = navMatchScore(pathname, search, href, locationHash);
  if (score < 0) return false;
  return !items.some(([, other]) => other !== href && navMatchScore(pathname, search, other, locationHash) > score);
}

function navAllowlistForRole(
  role: string,
  permissions: Record<string, string[]> | null,
): string[] | '*' {
  if (Object.prototype.hasOwnProperty.call(ROLE_NAV_MODULES, role)) {
    return ROLE_NAV_MODULES[role];
  }
  return navAllowlistFromPermissions(permissions);
}

function navItemsForRole(
  role: string,
  permissions: Record<string, string[]> | null,
  enabledModules: string[] | null,
  industry: string | null,
  multiStore = true
): NavItem[] {
  // Software owner staff: platform console only. Industry and package filters do not apply.
  if (PLATFORM_ROLES.has(role)) {
    return platformNavItemsForRole(role, permissions);
  }

  const allowed = navAllowlistForRole(role, permissions);
  const packageSet =
    enabledModules && enabledModules.length > 0 ? new Set(enabledModules.map((m) => m.toLowerCase())) : null;
  const industrySpecific = new Set<string>(INDUSTRY_SPECIFIC_MODULES);
  return TENANT_ITEMS.filter(([, href, module]) => {
    if (module === 'support') {
      return allowed === '*' || allowed.includes('support');
    }
    const permModule = module === 'integrations' ? 'company' : module;
    if (allowed !== '*' && !allowed.includes(permModule) && module !== 'integrations')
      return false;
    if (allowed !== '*' && module === 'integrations' && !allowed.includes('company'))
      return false;
    if (isHotelIndustry(industry) && permModule === 'stores') return false;
    if (!multiStore && isStoreNetworkNavItem(href, permModule)) return false;
    if (industrySpecific.has(permModule)) {
      if (!industryAllowsModule(industry, permModule)) return false;
      if (!packageSet || !packageSet.has(permModule)) return false;
    } else if (
      packageSet &&
      !packageSet.has(permModule) &&
      !['dashboard', 'notifications', 'security', 'users', 'printers', 'stores', 'support'].includes(module)
    ) {
      return false;
    }
    if (!navItemVisibleForRole(role, href)) return false;
    return canReadModule(permissions, permModule);
  });
}

const NAV_EXPANDED_KEY = 'ribdigi.nav.expanded';
const NAV_HIDDEN_KEY = 'ribdigi.nav.hidden';

function readNavCompact(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage.getItem(NAV_HIDDEN_KEY) === '1';
  } catch {
    return false;
  }
}

function writeNavCompact(compact: boolean) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(NAV_HIDDEN_KEY, compact ? '1' : '0');
  } catch {
    /* quota / private mode — the rail still toggles for this visit */
  }
}

function readExpandedNav(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(NAV_EXPANDED_KEY);
    const parsed = JSON.parse(raw || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((id): id is string => typeof id === 'string' && id.length > 0);
  } catch {
    return [];
  }
}

function writeExpandedNav(ids: Iterable<string>) {
  if (typeof window === 'undefined') return;
  try {
    const exclusive = Array.from(ids).slice(-1);
    window.localStorage.setItem(NAV_EXPANDED_KEY, JSON.stringify(exclusive));
  } catch {
    /* quota / private mode — navigation still works without persist */
  }
}

function exclusiveOpen(id: string | null | undefined): Set<string> {
  return id ? new Set([id]) : new Set();
}

function activeNavGroupId(
  groups: NavGroup[],
  pathname: string,
  items: NavItem[],
  search = '',
  locationHash = ''
): string | null {
  const path = pathname || '';
  for (const group of groups) {
    if (!usesAccordion(group)) continue;
    if (group.items.some(([, href]) => isNavActive(path, href, items, search, locationHash))) return group.id;
  }
  return null;
}

type BellNote = {
  id: string;
  category: string;
  title: string;
  message: string;
  status: string;
  created_at: string;
};

function isEditableTarget(target: EventTarget | null) {
  const el = target as HTMLElement | null;
  if (!el) return false;
  return Boolean(el.closest('input, textarea, select, [contenteditable="true"]'));
}

/** New admins must enroll 2FA. That 403 is not an expired session. */
function enrollmentRequired(err: unknown): boolean {
  const e = err as { status?: number; message?: string };
  return e?.status === 403 && /2fa enrollment/i.test(String(e?.message || ''));
}

function MobileSideNavButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const label = open ? 'Close sidebar' : 'Open sidebar';
  return (
    <button
      type="button"
      className="mobile-side-nav"
      aria-expanded={open}
      aria-controls="app-sidebar"
      aria-label={label}
      title={label}
      onClick={onToggle}
    >
      <span className="mobile-side-nav-mark" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 16 16" fill="none">
          <path
            d="M6 3.5 10.5 8 6 12.5"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    </button>
  );
}

function SideEdgeToggle({ compact, onToggle }: { compact: boolean; onToggle: () => void }) {
  const label = compact ? 'Expand sidebar' : 'Collapse sidebar';
  return (
    <button
      type="button"
      className="side-edge-toggle"
      aria-expanded={!compact}
      aria-controls="app-sidebar"
      aria-label={label}
      title={label}
      onClick={onToggle}
    >
      <span className="side-edge-chevron" aria-hidden="true">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path
            d="M10 3.5 5.5 8 10 12.5"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    </button>
  );
}

const DRAWER_REASON_PLACEHOLDERS = new Set(['manual', 'n/a', 'na', 'none', 'test']);

function drawerOpenReason(raw: string): string | null {
  const cleaned = raw.trim();
  if (cleaned.length < 3 || cleaned.length > 200) return null;
  if (!/[A-Za-z0-9]/.test(cleaned)) return null;
  if (cleaned.includes('://') || cleaned.includes('@')) return null;
  if (DRAWER_REASON_PLACEHOLDERS.has(cleaned.toLowerCase())) return null;
  return cleaned;
}

/** Opens the till's shift panel: report, cash in/out, count and close. */
function PosShiftTopButton() {
  return (
    <button
      type="button"
      className="tpos-btn pos-top-drawer-btn"
      aria-label="Open till shift"
      onClick={requestPosShiftPanel}
    >
      Shift
    </button>
  );
}

/** Opens the till's return panel: find a receipt, choose items, refund. */
function PosReturnTopButton() {
  return (
    <button
      type="button"
      className="tpos-btn pos-top-drawer-btn"
      aria-label="Open till return"
      onClick={requestPosReturnPanel}
    >
      Return
    </button>
  );
}

/** Sits in the POS top row, immediately to the right of the selling pill. */
function PosDrawerTopControls() {
  const [bridge, setBridge] = useState<PosDrawerBridgeState | null>(null);
  const [drawerReason, setDrawerReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [drawerNote, setDrawerNote] = useState('');
  const [drawerError, setDrawerError] = useState('');
  // The reason box appears only after Open drawer is pressed.
  const [asking, setAsking] = useState(false);

  useEffect(() => subscribePosDrawerBridge(setBridge), []);

  if (!bridge?.sessionId) return null;

  return (
    <div className="pos-top-drawer pos-ui-shift">
      <div className="pos-top-drawer-row">
      {asking ? (
      <input
        className="pos-top-drawer-reason"
        value={drawerReason}
        onChange={(e) => setDrawerReason(e.target.value)}
        placeholder="Drawer reason"
        maxLength={200}
        autoComplete="off"
        aria-label="Cash drawer open reason"
        autoFocus
      />
      ) : null}
      <button
        type="button"
        className="tpos-btn tpos-btn-primary pos-top-drawer-btn"
        aria-label="Open drawer"
        disabled={busy}
        onClick={() => {
          if (!asking) {
            setDrawerNote('');
            setDrawerError('');
            setAsking(true);
            return;
          }
          const sessionId = bridge.sessionId;
          const cleaned = drawerOpenReason(drawerReason);
          if (!cleaned) {
            setDrawerNote('');
            setDrawerError('Enter a short reason for opening the drawer.');
            return;
          }
          setDrawerError('');
          setBusy(true);
          void api(`/pos/sessions/${sessionId}/drawer/open`, {
            method: 'POST',
            body: JSON.stringify({ reason: cleaned }),
          })
            .then((r) => {
              setDrawerReason('');
              setAsking(false);
              setDrawerNote(r.data?.message || r.message || 'Drawer opened');
            })
            .catch((err: unknown) => {
              const message = err instanceof Error ? err.message : 'Could not open the drawer.';
              setDrawerError(message || 'Could not open the drawer.');
            })
            .finally(() => setBusy(false));
        }}
      >
        {busy ? 'Opening…' : 'Open drawer'}
      </button>
      {asking ? (
        <button
          type="button"
          className="tpos-btn pos-top-drawer-cancel"
          aria-label="Cancel opening drawer"
          disabled={busy}
          onClick={() => {
            setAsking(false);
            setDrawerReason('');
            setDrawerError('');
          }}
        >
          Cancel
        </button>
      ) : null}
      </div>
      {drawerNote ? (
        <span className="pos-top-drawer-note" role="status">
          {drawerNote}
        </span>
      ) : null}
      {drawerError ? (
        <span className="pos-top-drawer-note is-error" role="alert">
          {drawerError}
        </span>
      ) : null}
    </div>
  );
}

function PosSellingStatus() {
  const [snap, setSnap] = useState<LinkSnapshot>({
    phase: 'online',
    pending: 0,
    lastSyncAt: null,
    syncError: '',
  });
  useEffect(() => {
    let unsub = () => {};
    let stop = () => {};
    void import('../lib/connectivity').then((link) => {
      setSnap(link.getLinkSnapshot());
      unsub = link.subscribeLink(setSnap);
      stop = link.startLinkWatch();
    });
    return () => {
      unsub();
      stop();
    };
  }, []);
  const text = linkStatusText(snap);
  const tone =
    snap.phase === 'online' ? 'is-online' : snap.phase === 'syncing' ? 'is-syncing' : snap.phase === 'sync_failed' ? 'is-sync-failed' : 'is-offline';
  return (
    <details className="pos-sell-menu">
      <summary className={`pos-sell-mode ${tone}`} aria-label={`${text.label}. Offline selling`}>
        <span className="pos-sell-label" role="status" aria-live="polite">{text.label}</span>
        <span className="pos-sell-detail">{text.detail}</span>
      </summary>
      <div className="pos-sell-menu-body">
        <PosOfflineTopSlot embedded />
      </div>
    </details>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const [authReady, setAuthReady] = useState(false);
  const [authGateError, setAuthGateError] = useState('');
  const [unread, setUnread] = useState(0);
  const [permissions, setPermissions] = useState<Record<string, string[]> | null>(null);
  const [enabledModules, setEnabledModules] = useState<string[] | null>(null);
  const [industry, setIndustry] = useState<string | null>(null);
  const [industryValid, setIndustryValid] = useState<boolean | null>(null);
  const [multiStore, setMultiStore] = useState(true);
  const [role, setRole] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [navCompact, setNavCompact] = useState(false);
  const [fullName, setFullName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [hasLogo, setHasLogo] = useState(false);
  const [logoTick, setLogoTick] = useState(0);
  const [companyLogoUrl, setCompanyLogoUrl] = useState<string | null>(null);
  const [idleMinutes, setIdleMinutes] = useState(30);
  const [idleWarn, setIdleWarn] = useState(false);
  const idleLoggingOut = useRef(false);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [userId, setUserId] = useState('');
  const [bellOpen, setBellOpen] = useState(false);
  const [bellNotes, setBellNotes] = useState<BellNote[]>([]);
  const [bellLoading, setBellLoading] = useState(false);
  const [bellBusy, setBellBusy] = useState(false);
  const [expandedNav, setExpandedNav] = useState<Set<string>>(() => new Set());
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const navSearch = searchParams?.toString() || '';
  const [navHash, setNavHash] = useState('');
  const router = useRouter();
  const [navPending, setNavPending] = useState<string | null>(null);
  const isPlatformOwner = PLATFORM_ROLES.has(role);

  useEffect(() => {
    setNavPending(null);
  }, [pathname, navSearch]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const syncHash = () => setNavHash(window.location.hash || '');
    syncHash();
    window.addEventListener('hashchange', syncHash);
    return () => window.removeEventListener('hashchange', syncHash);
  }, [pathname, navSearch]);

  // Market readiness: no anonymous browsing of /pos, /inventory, etc.
  // Run once while this Shell stays mounted across dashboard navigations.
  useEffect(() => {
    let active = true;
    let timer = 0;
    async function requireAccount() {
      await hydrateAuth();
      const token = (getAccessToken() || '').trim();
      if (!token) {
        clearSessionAndRedirect();
        return;
      }
      const applyMe = (data: StoreEntitlementMe & {
        permissions?: Record<string, string[]>;
        enabled_modules?: string[];
        industry?: string | null;
        industry_valid?: boolean;
        role?: string;
        full_name?: string;
        company_name?: string;
        has_logo?: boolean;
        id?: string;
        inactivity_timeout_minutes?: number;
      }) => {
        if (!active) return;
        setAuthGateError('');
        setAuthReady(true);
        setPermissions(data.permissions || {});
        setEnabledModules(Array.isArray(data.enabled_modules) ? data.enabled_modules : []);
        setIndustry(data.industry ?? null);
        setIndustryValid(
          typeof data.industry_valid === 'boolean' ? data.industry_valid : Boolean(normalizeIndustry(data.industry))
        );
        setMultiStore(tenantIsMultiStore(data));
        setRole(data.role || '');
        setFullName(data.full_name || '');
        setCompanyName(data.company_name || '');
        setHasLogo(Boolean(data.has_logo));
        const uid = String(data.id || '').trim();
        if (uid) {
          setUserId(uid);
          setTheme(loadUserTheme(uid));
        }
        const mins = Number(data.inactivity_timeout_minutes);
        if (Number.isFinite(mins)) setIdleMinutes(mins);
      };
      const applyCachedAccount = async () => {
        const { getSnapshot } = await import('../lib/posOffline');
        const meSnap = await getSnapshot<Parameters<typeof applyMe>[0]>('me');
        if (!meSnap?.id) return false;
        applyMe(meSnap);
        return true;
      };
      // Ask the server first even when the browser says offline (no internet on the shop
      // network): only a failed request falls back to the saved account below.
      try {
        await Promise.race([
          getMe({ force: true }).then((meRes) => {
            applyMe(meRes.data || {});
            void import('../lib/posOffline')
              .then((offline) => offline.cacheSnapshot('me', meRes.data || null))
              .catch(() => undefined);
            return meRes;
          }),
          new Promise((_, reject) => {
            timer = window.setTimeout(() => {
              reject(new Error('The request timed out. Check your connection and try again.'));
            }, 25000);
          }),
        ]);
        if (active) {
          setAuthGateError('');
          setAuthReady(true);
        }
      } catch (err) {
        if (enrollmentRequired(err)) {
          if (active) setAuthReady(true);
          return;
        }
        if (isConfirmedAuthExpiry(err)) {
          clearSessionAndRedirect();
          return;
        }
        const status = (err as { status?: number }).status;
        if (status === undefined) {
          try {
            if (await applyCachedAccount()) return;
          } catch {
            /* keep the connection error below */
          }
        }
        const message = err instanceof Error ? err.message : 'Could not verify your account.';
        if (active) {
          setAuthGateError(message);
          setAuthReady(true);
        }
      } finally {
        window.clearTimeout(timer);
      }
    }
    requireAccount();
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(max-width: 900px)');
    const sync = () => {
      const isMobile = mq.matches;
      setMobileNav(isMobile);
      if (!isMobile) setMenuOpen(false);
    };
    sync();
    mq.addEventListener('change', sync);
    return () => mq.removeEventListener('change', sync);
  }, []);

  useEffect(() => {
    setNavCompact(readNavCompact());
  }, []);

  function toggleNavCompact() {
    setNavCompact((prev) => {
      const next = !prev;
      writeNavCompact(next);
      return next;
    });
  }

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const body = document.body;
    if (!menuOpen) {
      body.classList.remove('ribdigi-nav-lock');
      body.style.removeProperty('overflow');
      return;
    }
    const previousOverflow = body.style.overflow;
    body.classList.add('ribdigi-nav-lock');
    body.style.overflow = 'hidden';
    return () => {
      body.classList.remove('ribdigi-nav-lock');
      if (previousOverflow) body.style.overflow = previousOverflow;
      else body.style.removeProperty('overflow');
    };
  }, [menuOpen]);

  // Discourage copying app content (form fields stay selectable).
  useEffect(() => {
    if (!authReady) return;
    const block = (e: Event) => {
      if (isEditableTarget(e.target)) return;
      e.preventDefault();
    };
    const blockDrag = (e: DragEvent) => {
      if (isEditableTarget(e.target)) return;
      e.preventDefault();
    };
    document.addEventListener('copy', block, true);
    document.addEventListener('cut', block, true);
    document.addEventListener('contextmenu', block, true);
    document.addEventListener('dragstart', blockDrag, true);
    return () => {
      document.removeEventListener('copy', block, true);
      document.removeEventListener('cut', block, true);
      document.removeEventListener('contextmenu', block, true);
      document.removeEventListener('dragstart', blockDrag, true);
    };
  }, [authReady]);

  useEffect(() => {
    const el = document.documentElement;
    setTheme((el.getAttribute('data-theme') as 'light' | 'dark') || 'light');
  }, [userId]);

  useEffect(() => {
    if (!authReady) return;
    void openShiftForSignedInUser();
  }, [authReady]);

  async function logout() {
    try {
      await closeShiftForSignOut();
    } catch {
      /* sign-out still proceeds */
    }
    try {
      const offline = await import('../lib/posOffline');
      await offline.releaseOfflineGrantIfIdle(api);
    } catch {
      /* grant expires on its own; queued sales are never cleared on logout */
    }
    try {
      await api('/auth/logout', { method: 'POST' });
    } catch {
      /* revoke best-effort; clear client session regardless */
    }
    clearSessionAndRedirect();
  }

  function toggleTheme() {
    if (!userId) return;
    const next = theme === 'dark' ? 'light' : 'dark';
    writeUserTheme(userId, next);
    setTheme(next);
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
      setBellLoading(true);
      try {
        await Promise.all([refreshUnread(), loadBellNotes()]);
      } finally {
        setBellLoading(false);
      }
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
    if (!authReady) return;
    let active = true;
    async function load() {
      try {
        const meRes = await getMe({ force: true });
        let unreadCount = 0;
        try {
          const countRes = await api('/notifications/unread-count');
          unreadCount = countRes.data?.count || 0;
        } catch (err) {
          if (!enrollmentRequired(err)) unreadCount = 0;
        }
        if (!active) return;
        setUnread(unreadCount);
        setPermissions(meRes.data?.permissions || {});
        setEnabledModules(
          Array.isArray(meRes.data?.enabled_modules) ? meRes.data.enabled_modules : []
        );
        setIndustry(meRes.data?.industry ?? null);
        setIndustryValid(
          typeof meRes.data?.industry_valid === 'boolean'
            ? meRes.data.industry_valid
            : Boolean(normalizeIndustry(meRes.data?.industry))
        );
        setMultiStore(tenantIsMultiStore(meRes.data));
        setRole(meRes.data?.role || '');
        setFullName(meRes.data?.full_name || '');
        setCompanyName(meRes.data?.company_name || '');
        setHasLogo(Boolean(meRes.data?.has_logo));
        const uid = String(meRes.data?.id || '').trim();
        if (uid) {
          setUserId(uid);
          setTheme(loadUserTheme(uid));
        }
        const mins = Number(meRes.data?.inactivity_timeout_minutes);
        if (Number.isFinite(mins)) setIdleMinutes(mins);
      } catch (err) {
        if (enrollmentRequired(err)) return;
        if (isConfirmedAuthExpiry(err)) {
          clearSessionAndRedirect();
        }
      }
    }
    load();
    const id = setInterval(load, 30000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [authReady]);

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
    if (typeof document === 'undefined') return;
    const main = document.querySelector('.main');
    if (main instanceof HTMLElement) main.scrollTop = 0;
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
        await hydrateAuth();
        const token = getAccessToken();
        const tenantId = tenantHeaderValue(localStorage.getItem('tenant'));
        const res = await fetch(`${apiRoot()}/tenants/me/logo`, {
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
  }, [hasLogo, logoTick]);

  useEffect(() => {
    function onTenantLogoChanged() {
      void getMe({ force: true })
        .then((meRes) => {
          setHasLogo(Boolean(meRes.data?.has_logo));
          setCompanyName(meRes.data?.company_name || '');
          setLogoTick((n) => n + 1);
        })
        .catch(() => {
          /* ignore — next poll refreshes */
        });
    }
    window.addEventListener('ribdigi-tenant-logo', onTenantLogoChanged);
    return () => window.removeEventListener('ribdigi-tenant-logo', onTenantLogoChanged);
  }, []);

  async function staySignedIn() {
    resetIdleWriteThrottle();
    bumpLastActivity();
    try {
      await getMe({ force: true });
      setIdleWarn(false);
    } catch (err) {
      if (isConfirmedAuthExpiry(err)) {
        clearSessionAndRedirect();
        return;
      }
      setIdleWarn(false);
    }
  }

  async function idleLogout() {
    if (idleLoggingOut.current) return;
    idleLoggingOut.current = true;
    try {
      await closeShiftForSignOut();
    } catch {
      /* sign-out still proceeds */
    }
    try {
      await api('/auth/logout', { method: 'POST' });
    } catch {
      /* revoke best-effort */
    }
    clearSessionAndRedirect();
  }

  // BR-19.3: opening an already-idle session returns to login. Use does not reset that clock.
  useEffect(() => {
    if (typeof window === 'undefined' || !authReady) return;
    const limitMs = idleTimeoutMs(idleMinutes);
    const check = () => {
      const now = Date.now();
      const last = readLastActivity(now);
      if (isIdleExpired(limitMs, now, last)) {
        void idleLogout();
        return;
      }
      setIdleWarn(shouldWarnIdle(limitMs, now, last));
    };
    if (!hasStoredActivity()) {
      resetIdleWriteThrottle();
      bumpLastActivity();
    }
    if (isIdleExpired(limitMs)) {
      void idleLogout();
      return;
    }
    const bump = () => {
      bumpLastActivity();
      setIdleWarn(false);
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible') check();
    };
    const opts: AddEventListenerOptions = { capture: true, passive: true };
    ACTIVITY_EVENTS.forEach((name) => document.addEventListener(name, bump, opts));
    const onStorage = (ev: StorageEvent) => {
      if (ev.key === LAST_ACTIVITY_KEY) setIdleWarn(false);
    };
    window.addEventListener('storage', onStorage);
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', check);
    window.addEventListener('pageshow', check);
    const id = window.setInterval(check, 5000);
    return () => {
      ACTIVITY_EVENTS.forEach((name) => document.removeEventListener(name, bump, opts));
      window.removeEventListener('storage', onStorage);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', check);
      window.removeEventListener('pageshow', check);
      window.clearInterval(id);
    };
  }, [idleMinutes, authReady]);

  useEffect(() => {
    if (typeof window === 'undefined' || !authReady) return;
    let lastTenant = localStorage.getItem('tenant') || '';
    const applyTenantChange = () => {
      const next = localStorage.getItem('tenant') || '';
      if (next === lastTenant) return;
      lastTenant = next;
      invalidateMeCache();
      void getMe({ force: true })
        .then((meRes) => {
          setPermissions(meRes.data?.permissions || {});
          setEnabledModules(
            Array.isArray(meRes.data?.enabled_modules) ? meRes.data.enabled_modules : []
          );
          setIndustry(meRes.data?.industry ?? null);
          setIndustryValid(
            typeof meRes.data?.industry_valid === 'boolean'
              ? meRes.data.industry_valid
              : Boolean(normalizeIndustry(meRes.data?.industry))
          );
          setMultiStore(tenantIsMultiStore(meRes.data));
          setRole(meRes.data?.role || '');
          setCompanyName(meRes.data?.company_name || '');
          setHasLogo(Boolean(meRes.data?.has_logo));
          setLogoTick((n) => n + 1);
        })
        .catch(() => undefined);
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'tenant' || e.key === 'token') applyTenantChange();
    };
    window.addEventListener('storage', onStorage);
    const id = window.setInterval(applyTenantChange, 800);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.clearInterval(id);
    };
  }, [authReady]);

  const visible = useMemo(() => {
    const items = navItemsForRole(role, permissions, enabledModules, industry, multiStore);
    if (PLATFORM_ROLES.has(role)) return items;
    return filterNavForIndustry(items, industry);
  }, [role, permissions, enabledModules, industry, multiStore]);
  const navGroups = useMemo(
    () => groupedTenantNav(TENANT_NAV_GROUPS, visible, industry, multiStore),
    [visible, industry, multiStore]
  );
  const navRedirectTo = useMemo(() => {
    if (!authReady || !role || PLATFORM_ROLES.has(role)) return null;
    const allowed = navAllowlistForRole(role, permissions);
    return unauthorizedNavRedirect(pathname || '', role, allowed, industry);
  }, [authReady, role, permissions, pathname, industry]);
  const industryPageBlock = useMemo(() => {
    if (!role || PLATFORM_ROLES.has(role)) return null;
    return industryFeatureBlock(pathname || '/', industry, enabledModules);
  }, [role, pathname, industry, enabledModules]);

  useEffect(() => {
    if (!navRedirectTo) return;
    router.replace(navRedirectTo);
  }, [navRedirectTo, router]);
  const autoOpenedForPath = useRef('');
  const navStorageSeeded = useRef(false);

  useEffect(() => {
    const storedIds = navStorageSeeded.current ? null : readExpandedNav();
    navStorageSeeded.current = true;
    const path = pathname || '';
    const locKey = `${path}?${navSearch}`;
    const activeId = isPlatformOwner ? null : activeNavGroupId(navGroups, path, visible, navSearch, navHash);
    const accordionIds = new Set(navGroups.filter(usesAccordion).map((g) => g.id));
    const storedOne = storedIds?.filter((id) => accordionIds.has(id)).slice(-1)[0] ?? null;
    const shouldAutoOpen = Boolean(activeId) && autoOpenedForPath.current !== locKey;
    if (shouldAutoOpen) autoOpenedForPath.current = locKey;
    setExpandedNav((prev) => {
      let next: Set<string>;
      if (shouldAutoOpen && activeId) {
        next = exclusiveOpen(activeId);
      } else if (storedIds) {
        next = exclusiveOpen(activeId ?? storedOne);
      } else {
        return prev;
      }
      writeExpandedNav(next);
      return next;
    });
  }, [pathname, navSearch, navHash, navGroups, visible, isPlatformOwner]);

  const drawerClosed = (mobileNav && !menuOpen) || (!mobileNav && navCompact);

  function toggleNavGroup(id: string) {
    setExpandedNav((prev) => {
      const next = prev.has(id) ? exclusiveOpen(null) : exclusiveOpen(id);
      writeExpandedNav(next);
      return next;
    });
  }
  const showAlerts = visible.some(([, href]) => href === '/notifications');
  // App chrome only: RIBDIGI ERP default, then this tenant's uploaded logo.
  // Receipts/invoices stay name-only until upload (not this slot).
  const sidebarLogoSrc = chromeLogoSrc(companyLogoUrl, PLATFORM_SIDEBAR_LOGO);
  const sidebarLogoAlt = chromeLogoAlt(Boolean(companyLogoUrl), companyName);

  // Warm visible route JS as soon as the sidebar is up, then likely desk APIs.
  useEffect(() => {
    if (!authReady) return;
    try {
      router.prefetch('/dashboard');
    } catch {
      /* ignore */
    }
    const hrefs = visible.map(([, h]) => h);
    let cancelled = false;
    const warmRoutes = () => {
      if (cancelled) return;
      for (const h of hrefs) {
        try {
          router.prefetch(h);
        } catch {
          /* ignore */
        }
      }
    };
    const ric = typeof window !== 'undefined' ? window.requestIdleCallback : undefined;
    const routeId = ric ? ric(warmRoutes, { timeout: 1200 }) : window.setTimeout(warmRoutes, 200);
    return () => {
      cancelled = true;
      if (ric) window.cancelIdleCallback(routeId as number);
      else window.clearTimeout(routeId as number);
    };
  }, [authReady, router, visible]);

  function warmDestination(href: string) {
    try {
      router.prefetch(href);
    } catch {
      /* ignore */
    }
    for (const path of prefetchPathsForHref(href)) void prefetchGet(path);
  }

  if (!authReady) {
    return (
      <div className="auth-gate" role="status" aria-live="polite">
        <p>{authGateError || 'Checking your account…'}</p>
      </div>
    );
  }

  return (
    <StoreProvider enabled={Boolean(role) && !isPlatformOwner}>
      <div className={`shell shell-secure${menuOpen ? ' nav-open' : ''}${navCompact ? ' nav-compact' : ''}${pathname === '/pos' ? ' is-pos' : ''}`}>
      <aside
        id="app-sidebar"
        className="side"
        aria-hidden={drawerClosed}
        {...(drawerClosed ? { inert: true } : {})}
      >
        <div className="brand" aria-label="Workspace brand">
          <div className="brand-logo-slot">
            <img
              className="brand-logo"
              src={sidebarLogoSrc}
              alt={sidebarLogoAlt}
              draggable={false}
            />
          </div>
          {companyName ? (
            <div className="brand-name">{companyName}</div>
          ) : isPlatformOwner ? (
            <div className="brand-name">RIBDIGI Platform</div>
          ) : null}
        </div>
        {isPlatformOwner ? <div className="brand-sub">Platform owner console</div> : null}
        <nav
          className="nav"
          aria-label={isPlatformOwner ? 'Platform navigation' : 'Tenant navigation'}
          data-industry={isPlatformOwner ? 'platform' : normalizeIndustry(industry) || ''}
        >
          {(isPlatformOwner ? [{ id: 'platform', label: '', items: visible }] : navGroups).map((group) => {
            const links = group.items.map(([n, h, module]) => {
              const active = isNavActive(pathname || '', h, visible, navSearch, navHash);
              const label =
                n +
                ((h === '/notifications' || h.startsWith('/notifications?')) && unread > 0
                  ? ` (${unread})`
                  : '');
              return (
                <Link
                  key={h}
                  href={h}
                  className={active ? 'active' : undefined}
                  aria-current={active ? 'page' : undefined}
                  title={label}
                  onClick={() => {
                    setMenuOpen(false);
                    const dest = hrefParts(h);
                    if (dest.hash) setNavHash(`#${dest.hash}`);
                    else setNavHash('');
                    const destPath = dest.path;
                    if (destPath !== (pathname || '')) setNavPending(h);
                    else if (h !== `${pathname || ''}${navSearch ? `?${navSearch}` : ''}${navHash}`) setNavPending(h);
                  }}
                  onMouseEnter={() => warmDestination(h)}
                  onFocus={() => warmDestination(h)}
                  onTouchStart={() => warmDestination(h)}
                >
                  <span className="nav-ico">
                    <NavIcon name={module} />
                  </span>
                  <span className="nav-label">{label}</span>
                </Link>
              );
            });
            if (ALWAYS_LIST_NAV_GROUP_IDS.has(group.id) && group.label) {
              const childActive = group.items.some(([, h]) =>
                isNavActive(pathname || '', h, visible, navSearch, navHash)
              );
              return (
                <div
                  key={group.id}
                  className={`nav-group nav-group-static${childActive ? ' nav-group-has-active' : ''}`}
                >
                  <div className="nav-group-heading">{group.label}</div>
                  <div className="nav-group-items">{links}</div>
                </div>
              );
            }
            if (!group.label || !usesAccordion(group)) {
              return <div key={group.id} className="nav-standalone">{links}</div>;
            }
            const childActive = group.items.some(([, h]) => isNavActive(pathname || '', h, visible, navSearch, navHash));
            const isOpen = expandedNav.has(group.id);
            return (
              <details
                key={group.id}
                className={`nav-group${childActive ? ' nav-group-has-active' : ''}`}
                open={isOpen}
                onToggle={(e) => {
                  const el = e.currentTarget;
                  if (el.open !== isOpen) el.open = isOpen;
                }}
              >
                <summary
                  className={childActive ? 'nav-group-active' : undefined}
                  aria-expanded={isOpen}
                  onClick={(e) => {
                    e.preventDefault();
                    toggleNavGroup(group.id);
                  }}
                >
                  <span className="nav-group-title">{group.label}</span>
                  <span className="nav-group-arrow" aria-hidden="true" />
                </summary>
                <div className="nav-group-items">{links}</div>
              </details>
            );
          })}
        </nav>
        <div className="side-foot">
          <a href="https://ribdigihouse.com" target="_blank" rel="noopener noreferrer">
            A Ribdigi House Product
          </a>
        </div>
      </aside>
      <SideEdgeToggle compact={navCompact} onToggle={toggleNavCompact} />
      <MobileSideNavButton
        open={menuOpen}
        onToggle={() => {
          if (mobileNav) setMenuOpen((v) => !v);
        }}
      />
      <div className="side-backdrop" onClick={() => setMenuOpen(false)} aria-hidden />
      <main className="main">
        <div className="topbar">
          <div className="topbar-left">
            {pathname === '/pos' ? (
              <>
                <PosSellingStatus />
                <div className="pos-top-tools">
                  <PosShiftTopButton />
                  <PosReturnTopButton />
                  <PosDrawerTopControls />
                </div>
              </>
            ) : null}
            <button
              type="button"
              className="menu-btn"
              aria-label="Toggle navigation menu"
              aria-expanded={mobileNav ? menuOpen : undefined}
              onClick={() => {
                if (mobileNav) setMenuOpen((v) => !v);
              }}
            >
              <span aria-hidden>{'\u2630'}</span>
              <span className="menu-btn-label">Menu</span>
            </button>
          </div>
          {!isPlatformOwner ? (
            <div className="topbar-context">
              <StoreSwitcher visible={!isHotelIndustry(industry)} />
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
                      {bellLoading && bellNotes.length === 0 ? (
                        <p className="muted bell-empty">Loading alerts…</p>
                      ) : bellNotes.length === 0 ? (
                        <p className="muted bell-empty">No unread alerts</p>
                      ) : (
                        bellNotes.map((n) => (
                          <div key={n.id} className="bell-item">
                            <div className="bell-item-meta">
                              <span className={`bell-cat bell-cat-${n.category}`}>{notifyCategoryLabel(n.category)}</span>
                              <span className="muted">{formatNoticeTime(n.created_at)}</span>
                            </div>
                            <div className="bell-item-title">{n.title}</div>
                            <div className="muted bell-item-msg">{n.message}</div>
                            <button
                              type="button"
                              className="bell-item-action"
                              disabled={bellBusy}
                              onClick={() => markBellRead(n.id)}
                              aria-label={`Mark bell notification ${n.id} read`}
                            >
                              Mark read
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="bell-panel-foot">
                      <button
                        type="button"
                        disabled={bellBusy || unread === 0}
                        onClick={markBellAllRead}
                        aria-label="Mark all bell notifications read"
                      >
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
                <span className="uname">{fullName.trim()}</span>
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
        {!isPlatformOwner && industryValid === false && (
          <p className="login-error" role="alert">
            This company has no valid industry on file ({industryLabel(industry)}). Industry-specific
            modules stay off until an administrator sets a supported industry on the Company page.
            Shared modules such as finance and reports remain available.
          </p>
        )}
        {(role === 'company_admin' || role === 'super_admin') && (
          <div className="no-print">
            <OnboardingChecklist canManage />
          </div>
        )}
        {navPending ? <div className="nav-progress" role="progressbar" aria-label="Loading page" /> : null}
        <div key={pathname || '/'} className="page-view">
          {navRedirectTo ? (
            <p className="muted" role="status">
              Opening an allowed page…
            </p>
          ) : (
            children
          )}
        </div>
      </main>
      {idleWarn ? (
        <div className="idle-warn" role="alertdialog" aria-labelledby="idle-warn-title" aria-describedby="idle-warn-body">
          <p id="idle-warn-title" style={{ margin: '0 0 8px', fontWeight: 700 }}>
            You will be signed out soon
          </p>
          <p id="idle-warn-body" className="muted" style={{ margin: '0 0 12px' }}>
            This session is idle. Stay signed in if you are still working.
          </p>
          <button type="button" className="list-btn-primary" onClick={() => void staySignedIn()}>
            Stay signed in
          </button>
        </div>
      ) : null}
    </div>
    </StoreProvider>
  );
}
