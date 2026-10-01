import { industryAllowsModule, INDUSTRY_SPECIFIC_MODULES } from './industryModules';
import { normalizeIndustry } from './industries';

export type NavItem = [label: string, href: string, module: string];
export type NavGroup = { id: string; label: string; items: NavItem[] };

/** Org structure under User Management. Hrefs match stores page section ids
 * (`#branches`, `#stores`) and dedicated `/users` / `/departments` routes.
 * Group id is `people` (label "User Management") — not `user-management`. */
export const PEOPLE_NAV_ITEMS: NavItem[] = [
  ['Users', '/users', 'users'],
  ['Branch', '/stores#branches', 'stores'],
  ['Store', '/stores#stores', 'stores'],
  ['Departments', '/departments', 'users'],
];

/** These groups always render children in the sidebar (no collapsed <details>). */
export const ALWAYS_LIST_NAV_GROUP_IDS = new Set(['people']);

/** Hotel tenants use one flat Hotel Management list. Shared ERP pages are
 * reached only through Hotel-labeled items (no duplicate Reports/Settings). */
export const HOTEL_OMIT_NAV_GROUP_IDS = new Set([
  'dashboard',
  'company',
  'inventory',
  'sales',
  'purchases',
  'finance',
  'stores',
  'reports',
  'people',
  'notifications',
  'settings',
  'industry',
]);

export const HOTEL_INVENTORY_PARENT_HREF = '/hotel?tab=supplies';

/** Shared ERP inventory/purchasing destinations, hotel-labeled. No second stock ledger. */
export const HOTEL_INVENTORY_PROCUREMENT_CHILDREN: NavItem[] = [
  ['Products and stock', '/inventory?tab=products', 'inventory'],
  ['Low stock', '/inventory?tab=lowstock', 'inventory'],
  ['Stock adjustments', '/inventory?tab=adjust', 'inventory'],
  ['Purchase orders', '/purchasing?tab=orders', 'purchasing'],
  ['Goods received', '/purchasing?tab=grn', 'purchasing'],
  ['Suppliers', '/purchasing?tab=suppliers', 'purchasing'],
  ['Purchase history', '/purchasing?tab=history', 'purchasing'],
];

export const HOTEL_NAV_ITEMS: NavItem[] = [
  ['Hotel Dashboard', '/hotel', 'hotel'],
  ['Reservations and Booking', '/hotel?tab=reservations', 'hotel'],
  ['Front Desk', '/hotel?tab=front-desk', 'hotel'],
  ['Rooms and Rates', '/hotel?tab=rooms', 'hotel'],
  ['Housekeeping', '/hotel?tab=housekeeping', 'hotel'],
  ['Maintenance', '/hotel?tab=maintenance', 'hotel'],
  ['Guests and CRM', '/hotel?tab=guests', 'hotel'],
  ['Hotel Services', '/hotel?tab=services', 'hotel'],
  ['Restaurant and POS', '/pos', 'pos'],
  ['Billing and Guest Folios', '/hotel?tab=billing', 'hotel'],
  ['Hotel Finance and Cashiering', '/hotel?tab=cashier', 'hotel'],
  ['Inventory and Procurement', HOTEL_INVENTORY_PARENT_HREF, 'inventory'],
  ['Staff and Permissions', '/users', 'users'],
  ['Hotel Reports', '/hotel?tab=reports', 'hotel'],
  ['Events and Banquets', '/hotel?tab=events', 'hotel'],
  ['Notifications', '/notifications', 'notifications'],
  ['Hotel Profile and Settings', '/hotel?tab=settings', 'hotel'],
  ['Company profile', '/company', 'company'],
  ['Integrations', '/integrations', 'company'],
];

export const FMCG_NAV_ITEMS: NavItem[] = [
  ['FMCG overview', '/fmcg', 'fmcg'],
  ['Trade schemes', '/fmcg?tab=schemes', 'fmcg'],
  ['Routes', '/fmcg?tab=routes', 'fmcg'],
  ['Deliveries', '/fmcg?tab=deliveries', 'fmcg'],
];

/** Pharmacy extras: lots/batches plus catalog Rx/dosage and Rx records. Not HIS. */
export const PHARMACY_NAV_ITEMS: NavItem[] = [
  ['Expiring lots', '/inventory?tab=expiry', 'inventory'],
  ['Batches', '/inventory?tab=batches', 'inventory'],
  ['Rx-only products', '/inventory?tab=products&rx=1', 'inventory'],
  ['Prescriptions', '/prescriptions', 'inventory'],
];

export function isHotelIndustry(industry: string | null | undefined): boolean {
  return normalizeIndustry(industry) === 'hotel';
}

export function hotelNavLabels(items: NavItem[] = HOTEL_NAV_ITEMS): string[] {
  return items.map(([label]) => label);
}

export type StoreEntitlementMe = {
  multi_store?: boolean;
  max_stores?: number | null;
  subscription?: {
    multi_store?: boolean;
    max_stores?: number | null;
    subscription_store_entitlement?: number | null;
    effective_store_limit?: number | null;
  };
};

/** /me flags are UI-only; APIs still enforce store entitlements. */
export function tenantIsMultiStore(me?: StoreEntitlementMe | null): boolean {
  if (typeof me?.multi_store === 'boolean') return me.multi_store;
  if (typeof me?.subscription?.multi_store === 'boolean') return me.subscription.multi_store;
  const cap =
    me?.max_stores ??
    me?.subscription?.max_stores ??
    me?.subscription?.subscription_store_entitlement ??
    me?.subscription?.effective_store_limit;
  if (cap === null || cap === undefined) return true;
  return Number(cap) > 1;
}

/** Hotel always hides store-network UX. Single-store tenants hide Branch/Store pickers too. */
export function hideStoreUx(
  me?: (StoreEntitlementMe & { industry?: string | null }) | null,
): boolean {
  return isHotelIndustry(me?.industry) || !tenantIsMultiStore(me);
}

export function isStoreNetworkNavItem(href: string, module?: string): boolean {
  const path = (href.split('?')[0] || '').split('#')[0];
  if (module === 'stores') return true;
  if (path === '/stores' || path.startsWith('/stores/')) return true;
  if (href.includes('tab=transfers')) return true;
  return false;
}

/** Drop Branch/Store and store-transfer items for single-store tenants.
 * Users/Departments stay. Default multiStore=true so retail people children remain. */
export function filterNavForStoreMode(items: NavItem[], multiStore = true): NavItem[] {
  if (multiStore) return items;
  return items.filter(([, href, module]) => !isStoreNetworkNavItem(href, module));
}

export function groupedTenantNav(
  groups: NavGroup[],
  visible: NavItem[],
  industry: string | null,
  multiStore = true
): NavGroup[] {
  const scoped = filterNavForStoreMode(visible, multiStore);
  const allowed = new Set(scoped.map(([, href]) => href));
  const ind = normalizeIndustry(industry);
  const mapped = groups
    .map((group) => {
      if (ind === 'hotel' && HOTEL_OMIT_NAV_GROUP_IDS.has(group.id)) {
        return { ...group, items: [] as NavItem[] };
      }
      if (group.id === 'inventory') {
        return {
          ...group,
          label: 'Inventory',
          items: group.items.filter(([, href]) => allowed.has(href)),
        };
      }
      if (group.id === 'industry') {
        if (ind === 'fmcg') {
          return {
            id: 'industry',
            label: 'FMCG management',
            items: FMCG_NAV_ITEMS.filter(([, href]) => allowed.has(href)),
          };
        }
        if (ind === 'pharmacy') {
          return {
            id: 'industry',
            label: 'Pharmacy management',
            items: PHARMACY_NAV_ITEMS.filter(([, href]) => allowed.has(href)),
          };
        }
        return { ...group, items: [] };
      }
      return {
        ...group,
        items: group.items.filter(([, href]) => allowed.has(href)),
      };
    })
    .filter((group) => group.items.length > 0);

  if (ind !== 'hotel') return mapped;

  const hotelItems = HOTEL_NAV_ITEMS.filter(([, href, module]) => {
    if (module === 'hotel' && !industryAllowsModule(ind, 'hotel')) return false;
    return allowed.has(href);
  });
  if (!hotelItems.length) return mapped;

  const invChildren = HOTEL_INVENTORY_PROCUREMENT_CHILDREN.filter(([, href]) => allowed.has(href));
  const showInvParent = hotelItems.some(([, href]) => href === HOTEL_INVENTORY_PARENT_HREF);
  const splitAt = HOTEL_NAV_ITEMS.findIndex(([, href]) => href === HOTEL_INVENTORY_PARENT_HREF);
  const beforeHrefs = new Set(HOTEL_NAV_ITEMS.slice(0, Math.max(0, splitAt)).map(([, href]) => href));
  const hotelFlat = hotelItems.filter(([, href]) => href !== HOTEL_INVENTORY_PARENT_HREF);
  const before = hotelFlat.filter(([, href]) => beforeHrefs.has(href));
  const after = hotelFlat.filter(([, href]) => !beforeHrefs.has(href));

  const hotelGroups: NavGroup[] = [];
  if (before.length) hotelGroups.push({ id: 'hotel', label: '', items: before });
  if (showInvParent && invChildren.length) {
    hotelGroups.push({
      id: 'hotel-inventory',
      label: 'Inventory and Procurement',
      items: invChildren,
    });
  } else if (showInvParent) {
    hotelGroups.push({
      id: 'hotel-inventory',
      label: '',
      items: hotelItems.filter(([, href]) => href === HOTEL_INVENTORY_PARENT_HREF),
    });
  }
  if (after.length) hotelGroups.push({ id: 'hotel-rest', label: '', items: after });
  if (!hotelGroups.length) return mapped;

  // Hotel-only: flat ops items, plus an accordion for shared inventory/purchasing.
  return [...hotelGroups, ...mapped];
}

/** Retail cashier sidebar: POS plus dashboard (already granted). Other modules stay off the menu. */
export const CASHIER_NAV_MODULES: string[] = ['dashboard', 'pos'];

export const HOTEL_CASHIER_NAV_MODULES: string[] = [
  'hotel',
  'pos',
  'accounting',
  'notifications',
  'security',
];

/** Path prefix → nav module. Longest prefix wins. Aligns with backend MENU_MODULE_BY_PATH. */
export const NAV_MODULE_BY_PATH: Record<string, string> = {
  '/platform/staff': 'platform_staff',
  '/platform/reports': 'platform_reports',
  '/platform': 'platform',
  '/dashboard': 'dashboard',
  '/company': 'company',
  '/inventory': 'inventory',
  '/prescriptions': 'inventory',
  '/sales': 'sales',
  '/customers': 'sales',
  '/pos': 'pos',
  '/purchasing': 'purchasing',
  '/expenses': 'expenses',
  '/accounting': 'accounting',
  '/credit': 'credit',
  '/tax': 'tax',
  '/stores': 'stores',
  '/hotel': 'hotel',
  '/fmcg': 'fmcg',
  '/reports': 'reports',
  '/notifications': 'notifications',
  '/audit': 'audit',
  '/backup': 'backup',
  '/jobs': 'platform',
  '/integrations': 'company',
  '/security': 'security',
  '/ai': 'ai',
  '/users': 'users',
  '/departments': 'users',
  '/admin': 'users',
  '/printers': 'printers',
};

const NAV_PATH_PREFIXES = Object.keys(NAV_MODULE_BY_PATH).sort((a, b) => b.length - a.length);

export function navPathname(pathname: string): string {
  const noHash = pathname.split('#')[0] || '/';
  return (noHash.split('?')[0] || '/').replace(/\/$/, '') || '/';
}

export function navModuleForPath(pathname: string): string | null {
  const path = navPathname(pathname);
  for (const prefix of NAV_PATH_PREFIXES) {
    if (path === prefix || path.startsWith(`${prefix}/`)) return NAV_MODULE_BY_PATH[prefix];
  }
  return null;
}

export function roleHomePath(role: string): string {
  if (role === 'cashier') return '/pos';
  if (role.startsWith('hotel_')) return '/hotel';
  if (role === 'super_admin' || role.startsWith('platform_')) return '/platform';
  return '/dashboard';
}

const RECORD_SCOPE_KEY = '_record_scope';

/** Modules a custom role may open in nav. `*` = all (company-admin-style map). */
export function navAllowlistFromPermissions(
  permissions: Record<string, string[]> | null | undefined,
): string[] | '*' {
  if (!permissions) return [];
  if (permissions['*']?.includes('*')) return '*';
  const out: string[] = [];
  for (const [mod, actions] of Object.entries(permissions)) {
    if (mod === RECORD_SCOPE_KEY || mod === '*') continue;
    if (!Array.isArray(actions)) continue;
    if (actions.includes('*') || actions.includes('read') || actions.includes('write')) {
      out.push(mod);
    }
  }
  return out;
}

/** Return a replace target when the current path is outside the role's nav allowlist. */
export function unauthorizedNavRedirect(
  pathname: string,
  role: string,
  allowed: string[] | '*'
): string | null {
  if (!role || allowed === '*') return null;
  const path = navPathname(pathname);
  const mod = navModuleForPath(path);
  if (!mod) return null;
  if (allowed.includes(mod)) return null;
  const home = roleHomePath(role);
  if (path === navPathname(home)) return null;
  return home;
}

export function industrySpecificHrefAllowed(
  href: string,
  industry: string | null,
  enabledModules: string[] | null
): boolean {
  const path = href.split('?')[0];
  const packageSet =
    enabledModules && enabledModules.length > 0
      ? new Set(enabledModules.map((m) => m.toLowerCase()))
      : null;
  for (const mod of INDUSTRY_SPECIFIC_MODULES) {
    if (path === `/${mod}` || path.startsWith(`/${mod}/`)) {
      if (!industryAllowsModule(industry, mod)) return false;
      if (!packageSet || !packageSet.has(mod)) return false;
    }
  }
  return true;
}
