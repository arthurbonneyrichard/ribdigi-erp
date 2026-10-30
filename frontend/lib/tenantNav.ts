import { dashboardLayout, industryHomePath } from './industryDashboard';
import { industryAllowsModule, INDUSTRY_SPECIFIC_MODULES, moduleEnabledForTenant } from './industryModules';
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
export const ALWAYS_LIST_NAV_GROUP_IDS = new Set<string>();

/** Hotel hides the generic retail groups so pages are not listed twice.
 * Hotel-labeled mothers (Hotel, Sales and POS, Finance, Inventory, Users,
 * Reports, Settings) hold the children as sidebar dropdowns. */
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
  ['Supplies', '/inventory?tab=products', 'inventory'],
  ['Low supplies', '/inventory?tab=lowstock', 'inventory'],
  ['Stock adjustments', '/inventory?tab=adjust', 'inventory'],
  ['Lots', '/inventory?tab=batches', 'inventory'],
  ['Purchase orders', '/purchasing?tab=orders', 'purchasing'],
  ['Receive supplies', '/purchasing?tab=grn', 'purchasing'],
  ['Supplier bills', '/purchasing?tab=invoices', 'purchasing'],
  ['Purchase returns', '/purchasing?tab=returns', 'purchasing'],
  ['Suppliers', '/purchasing?tab=suppliers', 'purchasing'],
  ['Purchase history', '/purchasing?tab=history', 'purchasing'],
];

export const HOTEL_NAV_ITEMS: NavItem[] = [
  ['Hotel Dashboard', '/hotel', 'hotel'],
  ['Reservations and Booking', '/hotel?tab=reservations', 'hotel'],
  ['Group stays', '/hotel?tab=reservations#group-stay', 'hotel'],
  ['Online booking', '/hotel?tab=reservations#online-booking', 'hotel'],
  ['Front Desk', '/hotel?tab=front-desk', 'hotel'],
  ['Guest requests', '/hotel?tab=front-desk#guest-requests', 'hotel'],
  ['Rooms and Rates', '/hotel?tab=rooms', 'hotel'],
  ['Rate plans', '/hotel?tab=rooms#rate-plans', 'hotel'],
  ['Housekeeping', '/hotel?tab=housekeeping', 'hotel'],
  ['Lost and found', '/hotel?tab=housekeeping#lost-found', 'hotel'],
  ['Maintenance', '/hotel?tab=maintenance', 'hotel'],
  ['Guests and CRM', '/hotel?tab=guests', 'hotel'],
  ['Hotel Services', '/hotel?tab=services', 'hotel'],
  ['Hotel restaurant', '/hotel?tab=restaurant', 'hotel'],
  ['Hotel bar', '/hotel?tab=bar', 'hotel'],
  ['Sales', '/sales', 'sales'],
  ['Customers', '/customers', 'sales'],
  ['Discount codes', '/sales?tab=coupons', 'sales'],
  ['Gift cards', '/sales?tab=giftcards', 'sales'],
  ['Shop till', '/hotel/shop', 'hotel'],
  ['Billing and Guest Folios', '/hotel?tab=billing', 'hotel'],
  ['Hotel Finance and Cashiering', '/hotel?tab=cashier', 'hotel'],
  ['Night audit', '/hotel?tab=cashier#night-audit', 'hotel'],
  ['Expenses', '/expenses', 'expenses'],
  ['Accounting', '/accounting', 'accounting'],
  ['Payment notice', '/billing', 'accounting'],
  ['Customer credit', '/credit?kind=receivable', 'credit'],
  ['Tax', '/tax', 'tax'],
  ['Inventory and Procurement', HOTEL_INVENTORY_PARENT_HREF, 'inventory'],
  ['Staff and Permissions', '/users', 'users'],
  ['Departments', '/departments', 'users'],
  ['Hotel Reports', '/hotel?tab=reports', 'hotel'],
  ['Audit', '/audit', 'audit'],
  ['Events and Banquets', '/hotel?tab=events', 'hotel'],
  ['Notifications', '/notifications', 'notifications'],
  ['Hotel Profile and Settings', '/hotel?tab=settings', 'hotel'],
  ['Company profile', '/company', 'company'],
  ['Subscription billing', '/company/billing', 'company'],
  ['Integrations', '/integrations', 'company'],
  ['Security', '/security', 'security'],
  ['Printers', '/printers', 'printers'],
  ['Backup', '/backup', 'backup'],
  ['AI Assistant', '/ai', 'ai'],
];

/** Hotel sidebar mothers. Children sit under these labels as dropdowns.
 * Hotel Dashboard stays a standalone home link (`id: 'hotel'`). */
export const HOTEL_NAV_GROUPS: NavGroup[] = [
  { id: 'hotel', label: '', items: [['Hotel Dashboard', '/hotel', 'hotel']] },
  {
    id: 'hotel-ops',
    label: 'Hotel',
    items: [
      ['Reservations and Booking', '/hotel?tab=reservations', 'hotel'],
      ['Group stays', '/hotel?tab=reservations#group-stay', 'hotel'],
  ['Online booking', '/hotel?tab=reservations#online-booking', 'hotel'],
      ['Front Desk', '/hotel?tab=front-desk', 'hotel'],
      ['Guest requests', '/hotel?tab=front-desk#guest-requests', 'hotel'],
      ['Rooms and Rates', '/hotel?tab=rooms', 'hotel'],
      ['Rate plans', '/hotel?tab=rooms#rate-plans', 'hotel'],
      ['Housekeeping', '/hotel?tab=housekeeping', 'hotel'],
      ['Lost and found', '/hotel?tab=housekeeping#lost-found', 'hotel'],
      ['Maintenance', '/hotel?tab=maintenance', 'hotel'],
      ['Guests and CRM', '/hotel?tab=guests', 'hotel'],
      ['Hotel Services', '/hotel?tab=services', 'hotel'],
      ['Hotel restaurant', '/hotel?tab=restaurant', 'hotel'],
      ['Hotel bar', '/hotel?tab=bar', 'hotel'],
      ['Events and Banquets', '/hotel?tab=events', 'hotel'],
    ],
  },
  {
    id: 'hotel-sales',
    label: 'Sales and POS',
    items: [
      ['Sales', '/sales', 'sales'],
      ['Customers', '/customers', 'sales'],
      ['Discount codes', '/sales?tab=coupons', 'sales'],
      ['Gift cards', '/sales?tab=giftcards', 'sales'],
      ['Shop till', '/hotel/shop', 'hotel'],
    ],
  },
  {
    id: 'hotel-finance',
    label: 'Finance and Accounts',
    items: [
      ['Billing and Guest Folios', '/hotel?tab=billing', 'hotel'],
      ['Hotel Finance and Cashiering', '/hotel?tab=cashier', 'hotel'],
      ['Night audit', '/hotel?tab=cashier#night-audit', 'hotel'],
      ['Expenses', '/expenses', 'expenses'],
      ['Accounting', '/accounting', 'accounting'],
      ['Payment notice', '/billing', 'accounting'],
      ['Customer credit', '/credit?kind=receivable', 'credit'],
      ['Tax', '/tax', 'tax'],
    ],
  },
  {
    id: 'hotel-inventory',
    label: 'Inventory and Procurement',
    items: [...HOTEL_INVENTORY_PROCUREMENT_CHILDREN],
  },
  {
    id: 'hotel-people',
    label: 'User Management',
    items: [
      ['Staff and Permissions', '/users', 'users'],
      ['Departments', '/departments', 'users'],
    ],
  },
  {
    id: 'hotel-reports',
    label: 'Hotel Reports',
    items: [
      ['Hotel Reports', '/hotel?tab=reports', 'hotel'],
      ['Audit', '/audit', 'audit'],
    ],
  },
  { id: 'hotel-notifications', label: '', items: [['Notifications', '/notifications', 'notifications']] },
  {
    id: 'hotel-settings',
    label: 'Settings',
    items: [
      ['Hotel Profile and Settings', '/hotel?tab=settings', 'hotel'],
      ['Company profile', '/company', 'company'],
      ['Subscription billing', '/company/billing', 'company'],
      ['Integrations', '/integrations', 'company'],
      ['Security', '/security', 'security'],
      ['Printers', '/printers', 'printers'],
      ['Backup', '/backup', 'backup'],
      ['AI Assistant', '/ai', 'ai'],
    ],
  },
];

export const RESTAURANT_NAV_ITEMS: NavItem[] = [
  ['Restaurant dashboard', '/restaurant', 'restaurant'],
  ['Tables and floor', '/restaurant?tab=tables', 'restaurant'],
  ['Website and booking', '/restaurant?tab=booking', 'restaurant'],
  ['Orders', '/restaurant/orders', 'restaurant'],
  ['Kitchen', '/restaurant?tab=kitchen', 'restaurant'],
  ['Recipes', '/restaurant?tab=recipes', 'restaurant'],
  ['Waste', '/restaurant?tab=waste', 'restaurant'],
  ['Bills', '/restaurant/bills', 'restaurant'],
  ['Guests', '/restaurant/guests', 'restaurant'],
  ['Pay suppliers', '/restaurant/payables', 'credit'],
  ['Restaurant till', '/restaurant/till', 'restaurant'],
  ['Ingredients', '/restaurant/ingredients', 'inventory'],
  ['Menu items', '/restaurant/ingredients?tab=menu', 'inventory'],
  ['Purchasing', '/restaurant/purchasing', 'purchasing'],
  ['Suppliers', '/restaurant/purchasing?tab=suppliers', 'purchasing'],
  ['Expenses', '/restaurant/expenses', 'expenses'],
  ['Money', '/restaurant/money', 'accounting'],
  ['Tax', '/restaurant/tax', 'tax'],
  ['Reports', '/restaurant/reports', 'reports'],
  ['Profit and loss', '/reports?tab=pnl', 'reports'],
  ['Staff and Permissions', '/users', 'users'],
  ['Departments', '/departments', 'users'],
  ['Audit', '/audit', 'audit'],
  ['Notifications', '/notifications', 'notifications'],
  ['Company profile', '/company', 'company'],
  ['Security', '/security', 'security'],
  ['Printers', '/printers', 'printers'],
  ['Backup', '/backup', 'backup'],
];

/** Restaurant sidebar. Retail POS, Batches, and hotel rooms stay off this list. */
export const RESTAURANT_NAV_GROUPS: NavGroup[] = [
  { id: 'restaurant', label: '', items: [['Restaurant dashboard', '/restaurant', 'restaurant']] },
  {
    id: 'restaurant-floor',
    label: 'Restaurant',
    items: [
      ['Tables and floor', '/restaurant?tab=tables', 'restaurant'],
      ['Website and booking', '/restaurant?tab=booking', 'restaurant'],
      ['Orders', '/restaurant/orders', 'restaurant'],
      ['Kitchen', '/restaurant?tab=kitchen', 'restaurant'],
      ['Recipes', '/restaurant?tab=recipes', 'restaurant'],
      ['Waste', '/restaurant?tab=waste', 'restaurant'],
    ],
  },
  {
    id: 'restaurant-service',
    label: 'Service',
    items: [
      ['Restaurant till', '/restaurant/till', 'restaurant'],
      ['Bills', '/restaurant/bills', 'restaurant'],
      ['Guests', '/restaurant/guests', 'restaurant'],
    ],
  },
  {
    id: 'restaurant-places',
    label: 'Branches',
    items: [
      ['Branch', '/stores#branches', 'stores'],
      ['Store', '/stores#stores', 'stores'],
    ],
  },
  {
    id: 'restaurant-stock',
    label: 'Ingredients and purchasing',
    items: [
      ['Ingredients', '/restaurant/ingredients', 'inventory'],
      ['Menu items', '/restaurant/ingredients?tab=menu', 'inventory'],
      ['Purchasing', '/restaurant/purchasing', 'purchasing'],
      ['Suppliers', '/restaurant/purchasing?tab=suppliers', 'purchasing'],
    ],
  },
  {
    id: 'restaurant-finance',
    label: 'Finance',
    items: [
      ['Expenses', '/restaurant/expenses', 'expenses'],
      ['Pay suppliers', '/restaurant/payables', 'credit'],
      ['Money', '/restaurant/money', 'accounting'],
      ['Tax', '/restaurant/tax', 'tax'],
      ['Reports', '/restaurant/reports', 'reports'],
      ['Profit and loss', '/reports?tab=pnl', 'reports'],
    ],
  },
  {
    id: 'restaurant-people',
    label: 'User Management',
    items: [
      ['Staff and Permissions', '/users', 'users'],
      ['Departments', '/departments', 'users'],
    ],
  },
  { id: 'restaurant-notifications', label: '', items: [['Notifications', '/notifications', 'notifications']] },
  {
    id: 'restaurant-settings',
    label: 'Settings',
    items: [
      ['Company profile', '/company', 'company'],
      ['Security', '/security', 'security'],
      ['Printers', '/printers', 'printers'],
      ['Backup', '/backup', 'backup'],
      ['AI Assistant', '/ai', 'ai'],
      ['Audit', '/audit', 'audit'],
    ],
  },
];

export const FMCG_NAV_ITEMS: NavItem[] = [
  ['FMCG overview', '/fmcg', 'fmcg'],
  ['Trade schemes', '/fmcg?tab=schemes', 'fmcg'],
  ['Routes', '/fmcg?tab=routes', 'fmcg'],
  ['Deliveries', '/fmcg?tab=deliveries', 'fmcg'],
  ['Pack convert', '/fmcg?tab=packs', 'fmcg'],
];

export const HOSPITAL_NAV_ITEMS: NavItem[] = [
  ['Patients and visits', '/hospital', 'hospital'],
];

/** Wholesale extras: B2B quotes/orders. Shared stock stays on Inventory. */
export const WHOLESALE_NAV_ITEMS: NavItem[] = [
  ['Quotations', '/sales?tab=quotations', 'sales'],
  ['Sales orders', '/sales?tab=orders', 'sales'],
  ['B2B credit', '/credit', 'credit'],
];

export const RETAIL_WHOLESALE_NAV_ITEMS: NavItem[] = [
  ['Retail POS', '/pos', 'pos'],
  ...WHOLESALE_NAV_ITEMS,
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

/** Gift cards stay on retail. POS and the sales ledger follow the industries that use them.
 * Online store (`/ecommerce`) is a Settings item, not a Sales/POS sibling. */
export function industryNavHrefOk(href: string, industry: string | null | undefined): boolean {
  const path = (href.split('?')[0] || '').split('#')[0];
  const ind = normalizeIndustry(industry);
  if (path === '/hotel' || path.startsWith('/hotel/')) return ind === 'hotel';
  if (path === '/restaurant' || path.startsWith('/restaurant/')) return ind === 'restaurant';
  if (path === '/gift-cards') return ind === 'retail';
  if (path === '/ecommerce' || path.startsWith('/ecommerce/')) {
    return ind === 'retail' || ind === 'pharmacy';
  }
  // Restaurant rings on its own till (/restaurant/till); the retail POS stays off its menus.
  if (path === '/pos') {
    // Restaurant and hotel ring on their own tills (/restaurant/till, /hotel/shop).
    return ind === 'retail';
  }
  // A restaurant keeps its bills and guests on its own screens (/restaurant/bills, /restaurant/guests).
  if (path === '/sales' || path === '/customers') {
    return ind === 'retail' || ind === 'hotel' || ind === 'pharmacy';
  }
  return true;
}

const SHARED_ACCOUNT_MODULES = new Set([
  'dashboard',
  'company',
  'users',
  'notifications',
  'security',
  'backup',
  'audit',
  'reports',
  'expenses',
  'accounting',
  'tax',
  'credit',
  'integrations',
  'ai',
  'support',
]);

/** Platform console modules. The software industry layout must not drop these. */
export const PLATFORM_CONSOLE_MODULES = new Set([
  'platform',
  'platform_tenants',
  'platform_staff',
  'platform_reports',
  'jobs',
  'notifications',
  'audit',
  'security',
  'support',
]);

/** Existing platform destinations. Jobs uses platform:read; run stays owner-only on the page. */
export const PLATFORM_NAV_ITEMS: NavItem[] = [
  ['Platform', '/platform', 'platform'],
  ['Tenant', '/platform/tenants', 'platform_tenants'],
  ['Billing', '/platform/billing', 'platform'],
  ['Staff', '/platform/staff', 'platform_staff'],
  ['Reports', '/platform/reports', 'platform_reports'],
  ['Settings', '/platform/settings', 'platform'],
  ['Jobs', '/jobs', 'jobs'],
  ['Notifications', '/notifications', 'notifications'],
  ['Audit', '/audit', 'audit'],
  ['Security', '/security', 'security'],
  ['Support Desk', '/platform/support', 'support'],
];

const PLATFORM_OWNER_NAV_ROLES = new Set(['super_admin', 'platform_owner']);

const PLATFORM_SUPPORT_NAV_ROLES = new Set([
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
]);

/** Sidebar for platform staff. Support/finance stay on the permissions they already have. */
export function platformNavItemsForRole(
  role: string,
  permissions: Record<string, string[]> | null | undefined,
): NavItem[] {
  const allowed = navAllowlistFromPermissions(permissions);
  return PLATFORM_NAV_ITEMS.filter(([, href, module]) => {
    // Operational settings are for the software owner only (API also enforces this).
    if (href === '/platform/settings') return PLATFORM_OWNER_NAV_ROLES.has(role);
    if (module === 'support') return PLATFORM_SUPPORT_NAV_ROLES.has(role);
    if (module === 'platform' || module === 'platform_tenants' || module === 'jobs') return true;
    if (allowed === '*') return true;
    return allowed.includes(module);
  });
}

/** Live sidebar filter. groupedTenantNav still renders whatever hrefs a test passes in. */
export function filterNavForIndustry(items: NavItem[], industry: string | null | undefined): NavItem[] {
  const layout = dashboardLayout(industry);
  return items.filter((item) => {
    const [, href, module] = item;
    if (!industryNavHrefOk(href, industry)) return false;
    if (layout === 'platform') {
      return PLATFORM_CONSOLE_MODULES.has(module) || SHARED_ACCOUNT_MODULES.has(module);
    }
    if (layout === 'hotel' || layout === 'retail' || layout === 'pharmacy') {
      return true;
    }
    if (layout === 'restaurant') {
      return (
        module === 'restaurant' ||
        module === 'inventory' ||
        module === 'purchasing' ||
        module === 'printers' ||
        module === 'pos' ||
        module === 'sales' ||
        module === 'stores' ||
        SHARED_ACCOUNT_MODULES.has(module)
      );
    }
    return SHARED_ACCOUNT_MODULES.has(module);
  });
}

export function industryFeatureBlock(
  pathname: string,
  industry: string | null | undefined,
  enabledModules: string[] | null | undefined,
): string | null {
  if (!enabledModules) return null;
  const path = navPathname(pathname);
  const verticals: { prefix: string; module: string; label: string }[] = [
    { prefix: '/hotel', module: 'hotel', label: 'Hotel' },
    { prefix: '/fmcg', module: 'fmcg', label: 'FMCG' },
    { prefix: '/hospital', module: 'hospital', label: 'Hospital' },
    { prefix: '/restaurant', module: 'restaurant', label: 'Restaurant' },
  ];
  for (const row of verticals) {
    if (path === row.prefix || path.startsWith(`${row.prefix}/`)) {
      if (!moduleEnabledForTenant(enabledModules, industry, row.module)) {
        return `${row.label} is not available for this company.`;
      }
    }
  }
  if (path === '/prescriptions' || path.startsWith('/prescriptions/')) {
    if (normalizeIndustry(industry) !== 'pharmacy') {
      return 'This feature is not available for this company.';
    }
  }
  if (path === '/ecommerce' || path.startsWith('/ecommerce/')) {
    if (!moduleEnabledForTenant(enabledModules, industry, 'ecommerce')) {
      return 'Online store is not available for this company.';
    }
  }
  if (path === '/gift-cards' || path.startsWith('/gift-cards/')) {
    if (!industryNavHrefOk(path, industry)) {
      return 'This feature is not available for this company.';
    }
  }
  if ((path === '/pos' || path.startsWith('/pos/')) && !industryNavHrefOk('/pos', industry)) {
    return 'Point of sale is not available for this company.';
  }
  return null;
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
  const hrefVisible = (href: string) => allowed.has(href) && industryNavHrefOk(href, ind);
  const mapped = groups
    .map((group) => {
      if (ind === 'hotel' && HOTEL_OMIT_NAV_GROUP_IDS.has(group.id)) {
        return { ...group, items: [] as NavItem[] };
      }
      if (group.id === 'inventory') {
        return {
          ...group,
          label: 'Inventory',
          items: group.items.filter(([, href]) => hrefVisible(href)),
        };
      }
      if (group.id === 'industry') {
        if (ind === 'restaurant') {
          return {
            id: 'industry',
            label: 'Restaurant',
            items: RESTAURANT_NAV_ITEMS.filter(([, href]) => hrefVisible(href)),
          };
        }
        return { ...group, items: [] };
      }
      return {
        ...group,
        items: group.items.filter(([, href]) => hrefVisible(href)),
      };
    })
    .filter((group) => group.items.length > 0);

  const home = industryHomePath(ind);
  const pointed =
    home === '/dashboard'
      ? mapped
      : mapped.map((group) => ({
          ...group,
          items: group.items.map((item) =>
            item[1] === '/dashboard' ? ([item[0], home, item[2]] as NavItem) : item,
          ),
        }));

  if (ind === 'restaurant') {
    return RESTAURANT_NAV_GROUPS.map((group) => ({
      ...group,
      items: group.items.filter(([, href]) => hrefVisible(href)),
    })).filter((group) => group.items.length > 0);
  }

  if (ind !== 'hotel') return pointed;

  const hotelItems = HOTEL_NAV_ITEMS.filter(([, href, module]) => {
    if (module === 'hotel' && !industryAllowsModule(ind, 'hotel')) return false;
    return hrefVisible(href);
  });
  if (!hotelItems.length) return mapped;

  const allowedHotel = new Set(hotelItems.map(([, href]) => href));
  const hotelGroups = HOTEL_NAV_GROUPS.map((group) => {
    if (group.id === 'hotel-inventory') {
      const invChildren = HOTEL_INVENTORY_PROCUREMENT_CHILDREN.filter(([, href]) => hrefVisible(href));
      const showInvParent = hotelItems.some(([, href]) => href === HOTEL_INVENTORY_PARENT_HREF);
      if (showInvParent && invChildren.length) {
        return { ...group, items: invChildren };
      }
      if (showInvParent) {
        return {
          ...group,
          items: hotelItems.filter(([, href]) => href === HOTEL_INVENTORY_PARENT_HREF),
        };
      }
      return { ...group, items: invChildren };
    }
    return { ...group, items: group.items.filter(([, href]) => allowedHotel.has(href)) };
  }).filter((group) => group.items.length > 0);
  if (!hotelGroups.length) return mapped;

  return [...hotelGroups, ...pointed];
}

/** Cashier sidebar: Sales, POS, and Help & Support. */
export const CASHIER_NAV_MODULES: string[] = ['sales', 'pos', 'support'];

/** Gift cards share the POS module. Cashiers stay on the till; other roles keep the page. */
export function navItemVisibleForRole(role: string, href: string): boolean {
  if (role !== 'cashier') return true;
  const path = (href.split('?')[0] || '').split('#')[0];
  if (path === '/gift-cards' || path.startsWith('/gift-cards/')) return false;
  if (path === '/customers' || path.startsWith('/customers/')) return false;
  return true;
}

export const HOTEL_CASHIER_NAV_MODULES: string[] = [
  'hotel',
  'pos',
  'accounting',
  'notifications',
  'security',
  'support',
];

/** Path prefix → nav module. Longest prefix wins. Aligns with backend MENU_MODULE_BY_PATH. */
export const NAV_MODULE_BY_PATH: Record<string, string> = {
  '/platform/staff': 'platform_staff',
  '/platform/reports': 'platform_reports',
  '/platform/support': 'support',
  '/platform': 'platform',
  '/dashboard': 'dashboard',
  '/company': 'company',
  '/inventory': 'inventory',
  '/prescriptions': 'inventory',
  '/sales': 'sales',
  '/customers': 'sales',
  '/pos': 'pos',
  '/gift-cards': 'pos',
  '/ecommerce': 'ecommerce',
  '/purchasing': 'purchasing',
  '/expenses': 'expenses',
  '/accounting': 'accounting',
  '/billing': 'accounting',
  '/hospital': 'hospital',
  '/credit': 'credit',
  '/tax': 'tax',
  '/stores': 'stores',
  '/hotel': 'hotel',
  '/fmcg': 'fmcg',
  '/restaurant': 'restaurant',
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
  '/support': 'support',
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

export function roleHomePath(role: string, industry?: string | null): string {
  if (role === 'cashier') return '/pos';
  const ind = normalizeIndustry(industry);
  if (
    ind === 'restaurant' &&
    (role === 'store_manager' || role === 'sales_officer' || role === 'inventory_officer')
  ) {
    return '/restaurant';
  }
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
  allowed: string[] | '*',
  industry?: string | null,
): string | null {
  if (!role) return null;
  const path = navPathname(pathname);
  const home = roleHomePath(role, industry);
  // Role path blocks (cashier /customers, /gift-cards) apply even when the module is allowed.
  if (!navItemVisibleForRole(role, path)) {
    if (path === navPathname(home)) return null;
    return home;
  }
  if (allowed === '*') return null;
  const mod = navModuleForPath(path);
  if (!mod) return null;
  if (allowed.includes(mod)) return null;
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
