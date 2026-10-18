import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
  ALWAYS_LIST_NAV_GROUP_IDS,
  CASHIER_NAV_MODULES,
  filterNavForStoreMode,
  filterNavForIndustry,
  groupedTenantNav,
  industryFeatureBlock,
  industryNavHrefOk,
  PLATFORM_NAV_ITEMS,
  platformNavItemsForRole,
  RESTAURANT_NAV_ITEMS,
  hideStoreUx,
  HOTEL_CASHIER_NAV_MODULES,
  HOTEL_OMIT_NAV_GROUP_IDS,
  navAllowlistFromPermissions,
  navItemVisibleForRole,
  PEOPLE_NAV_ITEMS,
  roleHomePath,
  tenantIsMultiStore,
  unauthorizedNavRedirect,
  type NavGroup,
  type NavItem,
} from './tenantNav';

const PEOPLE_GROUP: NavGroup = {
  id: 'people',
  label: 'User Management',
  items: [...PEOPLE_NAV_ITEMS],
};

const STORES_GROUP: NavGroup = {
  id: 'stores',
  label: 'Stores',
  items: [
    ['Store', '/stores#stores', 'stores'],
    ['Branch', '/stores#branches', 'stores'],
  ],
};

test('people nav ids match users/departments routes and stores section hashes', () => {
  const byLabel = Object.fromEntries(PEOPLE_NAV_ITEMS.map(([label, href, module]) => [label, { href, module }]));
  assert.deepEqual(byLabel.Users, { href: '/users', module: 'users' });
  assert.deepEqual(byLabel.Branch, { href: '/stores#branches', module: 'stores' });
  assert.deepEqual(byLabel.Store, { href: '/stores#stores', module: 'stores' });
  assert.deepEqual(byLabel.Departments, { href: '/departments', module: 'users' });
  assert.equal(PEOPLE_NAV_ITEMS.some(([label]) => /brand/i.test(label)), false);
  assert.equal(ALWAYS_LIST_NAV_GROUP_IDS.has('people'), false);
});

test('retail grouped nav lists Branch and Store under people', () => {
  const visible: NavItem[] = [...PEOPLE_NAV_ITEMS];
  const out = groupedTenantNav([PEOPLE_GROUP, STORES_GROUP], visible, 'retail');
  const people = out.find((g) => g.id === 'people');
  assert.ok(people);
  assert.equal(people.label, 'User Management');
  assert.deepEqual(
    people.items.map(([label, href]) => [label, href]),
    [
      ['Users', '/users'],
      ['Branch', '/stores#branches'],
      ['Store', '/stores#stores'],
      ['Departments', '/departments'],
    ],
  );
});

test('single-store hides Branch/Store people children and keeps Users/Departments', () => {
  const visible: NavItem[] = [...PEOPLE_NAV_ITEMS];
  const out = groupedTenantNav([PEOPLE_GROUP, STORES_GROUP], visible, 'retail', false);
  const people = out.find((g) => g.id === 'people');
  assert.ok(people);
  assert.deepEqual(
    people.items.map(([label, href]) => [label, href]),
    [
      ['Users', '/users'],
      ['Departments', '/departments'],
    ],
  );
  assert.equal(out.some((g) => g.id === 'stores'), false);
  const kept = filterNavForStoreMode(PEOPLE_NAV_ITEMS, false).map(([label]) => label);
  assert.deepEqual(kept, ['Users', 'Departments']);
});

test('hotel omit empties people and leftover stores groups', () => {
  assert.equal(HOTEL_OMIT_NAV_GROUP_IDS.has('people'), true);
  assert.equal(HOTEL_OMIT_NAV_GROUP_IDS.has('stores'), true);
  const visible: NavItem[] = [...PEOPLE_NAV_ITEMS, ['Hotel Dashboard', '/hotel', 'hotel']];
  const out = groupedTenantNav([PEOPLE_GROUP, STORES_GROUP], visible, 'hotel');
  assert.equal(out.some((g) => g.id === 'people' || g.id === 'stores'), false);
});

test('tenantIsMultiStore follows /me flags and max_stores==1', () => {
  assert.equal(tenantIsMultiStore({ multi_store: false, max_stores: 10 }), false);
  assert.equal(tenantIsMultiStore({ multi_store: true, max_stores: 1 }), true);
  assert.equal(tenantIsMultiStore({ max_stores: 1 }), false);
  assert.equal(tenantIsMultiStore({ max_stores: 10 }), true);
  assert.equal(tenantIsMultiStore({ max_stores: null }), true);
});

test('hideStoreUx covers hotel and single-store, keeps multi-store retail', () => {
  assert.equal(hideStoreUx({ industry: 'hotel', multi_store: true, max_stores: 10 }), true);
  assert.equal(hideStoreUx({ industry: 'retail', multi_store: false, max_stores: 1 }), true);
  assert.equal(hideStoreUx({ industry: 'retail', max_stores: 1 }), true);
  assert.equal(hideStoreUx({ industry: 'retail', multi_store: true, max_stores: 10 }), false);
  assert.equal(hideStoreUx({ industry: 'mart', max_stores: 10 }), false);
});

test('cashier nav allowlist is POS and Help & Support', () => {
  assert.deepEqual([...CASHIER_NAV_MODULES].sort(), ['pos', 'sales', 'support']);
  assert.equal(CASHIER_NAV_MODULES.includes('dashboard'), false);
  assert.equal(CASHIER_NAV_MODULES.includes('inventory'), false);
  assert.equal(CASHIER_NAV_MODULES.includes('sales'), true);
  assert.equal(CASHIER_NAV_MODULES.includes('users'), false);
  assert.equal(CASHIER_NAV_MODULES.includes('purchasing'), false);
  assert.equal(unauthorizedNavRedirect('/pos', 'cashier', CASHIER_NAV_MODULES), null);
  assert.equal(unauthorizedNavRedirect('/support', 'cashier', CASHIER_NAV_MODULES), null);
  assert.equal(unauthorizedNavRedirect('/dashboard', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/restaurant', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/restaurant?tab=kitchen', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/gift-cards', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(roleHomePath('cashier'), '/pos');
  assert.equal(roleHomePath('cashier', 'restaurant'), '/pos');
  assert.equal(roleHomePath('cashier', 'retail'), '/pos');
  assert.equal(roleHomePath('store_manager', 'restaurant'), '/restaurant');
  assert.equal(roleHomePath('company_admin'), '/dashboard');
  assert.equal(navItemVisibleForRole('cashier', '/gift-cards'), false);
  assert.equal(navItemVisibleForRole('cashier', '/customers'), false);
  assert.equal(navItemVisibleForRole('cashier', '/sales'), true);
  assert.equal(navItemVisibleForRole('cashier', '/pos'), true);
  assert.equal(navItemVisibleForRole('cashier', '/support'), true);
  assert.equal(navItemVisibleForRole('company_admin', '/gift-cards'), true);
  assert.equal(navItemVisibleForRole('store_manager', '/gift-cards'), true);
  assert.equal(unauthorizedNavRedirect('/gift-cards', 'store_manager', ['dashboard', 'pos']), null);
  assert.equal(unauthorizedNavRedirect('/gift-cards', 'company_admin', '*'), null);
});

test('roles that can use restaurant in the API keep it on the sidebar allowlist', () => {
  const shell = readFileSync(new URL('../components/Shell.tsx', import.meta.url), 'utf8');
  function roleBlock(name: string): string {
    const start = shell.indexOf(`${name}: [`);
    assert.ok(start >= 0, name);
    const end = shell.indexOf('],', start);
    return shell.slice(start, end);
  }
  for (const role of ['store_manager', 'sales_officer', 'inventory_officer']) {
    assert.equal(roleBlock(role).includes("'restaurant'"), true, role);
  }
  assert.equal(unauthorizedNavRedirect('/restaurant', 'store_manager', ['dashboard', 'restaurant']), null);
  assert.equal(unauthorizedNavRedirect('/restaurant?tab=orders', 'sales_officer', ['sales', 'restaurant']), null);
});

test('custom role permissions drive nav, not cashier fallback', () => {
  const allowed = navAllowlistFromPermissions({
    dashboard: ['read'],
    inventory: ['read', 'write'],
  });
  assert.ok(Array.isArray(allowed));
  assert.deepEqual([...(allowed as string[])].sort(), ['dashboard', 'inventory']);
  assert.equal(unauthorizedNavRedirect('/inventory', 'warehouse_lead', allowed), null);
  assert.equal(unauthorizedNavRedirect('/pos', 'warehouse_lead', allowed), '/dashboard');
  assert.equal(unauthorizedNavRedirect('/users', 'warehouse_lead', allowed), '/dashboard');
  assert.equal(navAllowlistFromPermissions({ '*': ['*'] }), '*');
});

test('cashier forbidden routes redirect to POS, not a blank page', () => {
  assert.equal(unauthorizedNavRedirect('/inventory', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/inventory?tab=products', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/purchasing', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/accounting', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/reports', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/users', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/stores#branches', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/security', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/sales', 'cashier', CASHIER_NAV_MODULES), null);
  assert.equal(unauthorizedNavRedirect('/customers', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/credit?kind=payable', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/pos', 'cashier', CASHIER_NAV_MODULES), null);
  assert.equal(unauthorizedNavRedirect('/dashboard', 'cashier', CASHIER_NAV_MODULES), '/pos');
});

test('route guard does not lock tenant admins or hotel cashier POS', () => {
  assert.equal(unauthorizedNavRedirect('/inventory', 'company_admin', '*'), null);
  assert.equal(unauthorizedNavRedirect('/users', 'company_admin', '*'), null);
  assert.equal(unauthorizedNavRedirect('/pos', 'hotel_cashier', HOTEL_CASHIER_NAV_MODULES), null);
  assert.equal(unauthorizedNavRedirect('/hotel', 'hotel_cashier', HOTEL_CASHIER_NAV_MODULES), null);
  assert.equal(
    unauthorizedNavRedirect('/inventory', 'hotel_cashier', HOTEL_CASHIER_NAV_MODULES),
    '/hotel',
  );
});

test('pharmacy grouped nav has no Pharmacy sidebar group', () => {
  const groups: NavGroup[] = [
    {
      id: 'inventory',
      label: 'Inventory',
      items: [
        ['Expiry', '/inventory?tab=expiry', 'inventory'],
        ['Batches', '/inventory?tab=batches', 'inventory'],
      ],
    },
    {
      id: 'sales',
      label: 'Sales and POS',
      items: [['POS', '/pos', 'pos']],
    },
    {
      id: 'industry',
      label: 'Industry-specific features',
      items: [
        ['Hotel Dashboard', '/hotel', 'hotel'],
        ['FMCG overview', '/fmcg', 'fmcg'],
        ['Pharmacy', '/pharmacy', 'inventory'],
      ],
    },
  ];
  const visible: NavItem[] = [
    ['Expiry', '/inventory?tab=expiry', 'inventory'],
    ['Batches', '/inventory?tab=batches', 'inventory'],
    ['POS', '/pos', 'pos'],
    ['Rx-only products', '/inventory?tab=products&rx=1', 'inventory'],
    ['Prescriptions', '/prescriptions', 'inventory'],
    ['Pharmacy', '/pharmacy', 'inventory'],
  ];
  const out = groupedTenantNav(groups, visible, 'pharmacy');
  assert.equal(
    out.some((g) => g.label === 'Pharmacy' || g.id === 'industry'),
    false,
  );
  assert.equal(
    out.some((g) =>
      g.items.some(([label, href]) => label === 'Pharmacy' || href === '/pharmacy' || href.startsWith('/pharmacy/')),
    ),
    false,
  );
  const inventory = out.find((g) => g.id === 'inventory');
  assert.ok(inventory);
  assert.deepEqual(
    inventory.items.map(([, href]) => href),
    ['/inventory?tab=expiry', '/inventory?tab=batches'],
  );
  assert.equal(
    out.some((g) => g.items.some(([, href]) => href === '/pos')),
    false,
  );
  assert.equal(
    out.some((g) => g.items.some(([, href]) => href.startsWith('/hotel'))),
    false,
  );
});

test('wholesale grouped nav is quotes/orders/credit without hotel or pharmacy Rx', () => {
  const groups: NavGroup[] = [
    {
      id: 'industry',
      label: 'Industry-specific features',
      items: [
        ['Hotel Dashboard', '/hotel', 'hotel'],
        ['Prescriptions', '/prescriptions', 'inventory'],
      ],
    },
  ];
  const visible: NavItem[] = [
    ['Quotations', '/sales?tab=quotations', 'sales'],
    ['Sales orders', '/sales?tab=orders', 'sales'],
    ['B2B credit', '/credit', 'credit'],
    ['Retail POS', '/pos', 'pos'],
  ];
  const wholesale = groupedTenantNav(groups, visible, 'wholesale');
  assert.equal(wholesale.some((g) => g.id === 'industry'), false);
  assert.equal(
    wholesale.some((g) => g.items.some(([, href]) => href.startsWith('/hotel') || href === '/prescriptions')),
    false,
  );
  const combo = groupedTenantNav(groups, visible, 'retail_wholesale');
  assert.equal(combo.some((g) => g.id === 'industry'), false);
  assert.equal(
    combo.some((g) => g.items.some(([, href]) => href === '/pos' || href.startsWith('/hotel'))),
    false,
  );
});

test('mart grouped nav has no pharmacy or hotel industry group', () => {
  const groups: NavGroup[] = [
    {
      id: 'industry',
      label: 'Industry-specific features',
      items: [['Hotel Dashboard', '/hotel', 'hotel']],
    },
    {
      id: 'inventory',
      label: 'Inventory',
      items: [
        ['Products', '/inventory?tab=products', 'inventory'],
        ['Expiry', '/inventory?tab=expiry', 'inventory'],
      ],
    },
  ];
  const visible: NavItem[] = [
    ['Products', '/inventory?tab=products', 'inventory'],
    ['Expiry', '/inventory?tab=expiry', 'inventory'],
  ];
  const mart = groupedTenantNav(groups, visible, 'mart');
  assert.equal(mart.some((g) => g.id === 'industry'), false);
  const restaurant = groupedTenantNav(groups, visible, 'restaurant');
  assert.equal(restaurant.some((g) => g.id === 'industry'), false);
  assert.equal(
    restaurant.some((g) => g.items.some(([, href]) => href.startsWith('/hotel'))),
    false,
  );
});

test('restaurant company admin keeps the sales ledger and multi-store branches', () => {
  const items: NavItem[] = [
    ['Dashboard', '/dashboard', 'dashboard'],
    ['Sales', '/sales', 'sales'],
    ['Customers', '/customers', 'sales'],
    ['Gift cards', '/gift-cards', 'pos'],
    ['POS', '/pos', 'pos'],
    ['Expenses', '/expenses', 'expenses'],
    ['Accounting', '/accounting', 'accounting'],
    ['Reports', '/reports', 'reports'],
    ['Users', '/users', 'users'],
    ['Branch', '/stores#branches', 'stores'],
    ['Store', '/stores#stores', 'stores'],
    ['Departments', '/departments', 'users'],
    ['Company', '/company', 'company'],
    ['Products', '/inventory?tab=products', 'inventory'],
    ...RESTAURANT_NAV_ITEMS,
    ['Hotel Dashboard', '/hotel', 'hotel'],
  ];
  const kept = filterNavForIndustry(items, 'restaurant');
  const hrefs = kept.map(([, href]) => href);
  for (const href of [
    '/sales',
    '/customers',
    '/pos',
    '/expenses',
    '/accounting',
    '/reports',
    '/users',
    '/departments',
    '/company',
    '/inventory?tab=products',
    '/stores#branches',
    '/restaurant',
  ]) {
    assert.equal(hrefs.includes(href), true, href);
  }
  assert.equal(hrefs.includes('/gift-cards'), false);
  assert.equal(hrefs.some((href) => href.startsWith('/hotel')), false);
  assert.equal(industryNavHrefOk('/sales', 'restaurant'), true);
  assert.equal(industryNavHrefOk('/gift-cards', 'restaurant'), false);

  const groups: NavGroup[] = [
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
    PEOPLE_GROUP,
  ];
  const multi = groupedTenantNav(groups, kept, 'restaurant', true);
  const sales = multi.find((g) => g.id === 'sales');
  assert.ok(sales);
  assert.deepEqual(
    sales.items.map(([, href]) => href),
    ['/sales', '/customers', '/pos'],
  );
  const people = multi.find((g) => g.id === 'people');
  assert.ok(people);
  assert.equal(people.items.some(([, href]) => href === '/stores#branches'), true);
  const single = groupedTenantNav(groups, kept, 'restaurant', false);
  const peopleOne = single.find((g) => g.id === 'people');
  assert.ok(peopleOne);
  assert.equal(peopleOne.items.some(([, href]) => href.startsWith('/stores')), false);
});

test('hotel company admin keeps account pages on the hotel list', () => {
  const visible: NavItem[] = [
    ...[
      ['Sales', '/sales', 'sales'],
      ['Customers', '/customers', 'sales'],
      ['Expenses', '/expenses', 'expenses'],
      ['Accounting', '/accounting', 'accounting'],
      ['Reports', '/reports', 'reports'],
      ['Audit', '/audit', 'audit'],
      ['Security', '/security', 'security'],
      ['Users', '/users', 'users'],
      ['Departments', '/departments', 'users'],
      ['Company', '/company', 'company'],
      ['POS', '/pos', 'pos'],
    ] as NavItem[],
  ];
  const groups: NavGroup[] = [
    {
      id: 'finance',
      label: 'Finance and Accounts',
      items: [
        ['Expenses', '/expenses', 'expenses'],
        ['Accounting', '/accounting', 'accounting'],
      ],
    },
    {
      id: 'sales',
      label: 'Sales and POS',
      items: [
        ['Sales', '/sales', 'sales'],
        ['POS', '/pos', 'pos'],
      ],
    },
    { id: 'reports', label: 'Reports', items: [['Reports', '/reports', 'reports']] },
    PEOPLE_GROUP,
    {
      id: 'settings',
      label: 'Settings',
      items: [
        ['Company', '/company', 'company'],
        ['Security', '/security', 'security'],
      ],
    },
  ];
  const hotelVisible: NavItem[] = [
    ...visible,
    ['Hotel Dashboard', '/hotel', 'hotel'],
    ['Restaurant and POS', '/pos', 'pos'],
    ['Company profile', '/company', 'company'],
    ['Staff and Permissions', '/users', 'users'],
    ['Hotel Reports', '/hotel?tab=reports', 'hotel'],
    ['Pharmacy', '/pharmacy', 'inventory'],
  ];
  const out = groupedTenantNav(groups, hotelVisible, 'hotel', true);
  const labels = out.flatMap((g) => g.items.map(([label]) => label));
  for (const label of ['Sales', 'Expenses', 'Accounting', 'Reports', 'Staff and Permissions', 'Company profile', 'Restaurant and POS']) {
    assert.equal(labels.filter((item) => item === label).length, 1, label);
  }
  assert.equal(labels.includes('Pharmacy'), false);
  assert.equal(out.some((g) => ['finance', 'sales', 'reports', 'people', 'settings'].includes(g.id)), false);
  assert.equal(industryNavHrefOk('/sales', 'hotel'), true);
  assert.equal(industryNavHrefOk('/pos', 'hotel'), true);
  assert.equal(industryNavHrefOk('/gift-cards', 'hotel'), false);
});

test('restaurant nav shows floor and kitchen and hides hotel rooms', () => {
  const groups: NavGroup[] = [
    {
      id: 'industry',
      label: 'Industry-specific features',
      items: [['Hotel Dashboard', '/hotel', 'hotel']],
    },
  ];
  const restaurant = groupedTenantNav(groups, RESTAURANT_NAV_ITEMS, 'restaurant');
  const industry = restaurant.find((g) => g.id === 'industry');
  assert.ok(industry);
  assert.equal(industry.label, 'Restaurant');
  const hrefs = industry.items.map(([, href]) => href);
  assert.equal(hrefs.includes('/restaurant'), true);
  assert.equal(hrefs.includes('/restaurant?tab=tables'), true);
  assert.equal(hrefs.includes('/restaurant?tab=kitchen'), true);
  assert.equal(hrefs.some((href) => href.startsWith('/hotel')), false);
  const hotel = groupedTenantNav(groups, RESTAURANT_NAV_ITEMS, 'hotel');
  assert.equal(
    hotel.some((g) => g.items.some(([, href]) => href.startsWith('/restaurant'))),
    false,
  );
});

test('software owner sidebar keeps platform console items and role limits', () => {
  const kept = filterNavForIndustry(
    [
      ...PLATFORM_NAV_ITEMS,
      ['Sales', '/sales', 'sales'],
      ['POS', '/pos', 'pos'],
      ['Restaurant dashboard', '/restaurant', 'restaurant'],
      ['Hotel Dashboard', '/hotel', 'hotel'],
      ['Pharmacy', '/pharmacy', 'inventory'],
      ['Company', '/company', 'company'],
    ],
    'software',
  );
  const hrefs = kept.map(([, href]) => href);
  for (const href of [
    '/platform',
    '/platform/tenants',
    '/platform/billing',
    '/platform/staff',
    '/platform/reports',
    '/jobs',
    '/notifications',
    '/audit',
    '/security',
    '/platform/support',
    '/company',
  ]) {
    assert.equal(hrefs.includes(href), true, href);
  }
  assert.equal(hrefs.includes('/sales'), false);
  assert.equal(hrefs.includes('/pos'), false);
  assert.equal(hrefs.includes('/restaurant'), false);
  assert.equal(hrefs.includes('/hotel'), false);
  assert.equal(hrefs.includes('/pharmacy'), false);
  assert.equal(hrefs.some((href) => href.startsWith('/pharmacy')), false);

  const ownerPerms = { '*': ['*'] };
  const owner = platformNavItemsForRole('platform_owner', ownerPerms).map(([, href]) => href);
  const legacy = platformNavItemsForRole('super_admin', ownerPerms).map(([, href]) => href);
  for (const href of ['/platform/staff', '/platform/support', '/platform/tenants', '/jobs']) {
    assert.equal(owner.includes(href), true, href);
    assert.equal(legacy.includes(href), true, href);
  }

  const admin = platformNavItemsForRole('platform_admin', {
    platform: ['read', 'write'],
    platform_tenants: ['read', 'write'],
    platform_staff: ['read', 'write'],
    platform_reports: ['read'],
    notifications: ['read', 'write'],
    audit: ['read'],
    security: ['read', 'write'],
    support: ['view_all', 'assign', 'manage'],
  }).map(([, href]) => href);
  assert.equal(admin.includes('/platform/staff'), true);
  assert.equal(admin.includes('/platform/support'), true);
  assert.equal(admin.includes('/jobs'), true);
  assert.equal(admin.includes('/platform/reports'), true);

  const support = platformNavItemsForRole('platform_support', {
    platform: ['read'],
    platform_tenants: ['read', 'write'],
    platform_reports: ['read'],
    notifications: ['read'],
    audit: ['read'],
    security: ['read', 'write'],
    support: ['view_all', 'assign', 'manage'],
  }).map(([, href]) => href);
  assert.equal(support.includes('/platform/staff'), false);
  assert.equal(support.includes('/platform/support'), true);
  assert.equal(support.includes('/platform/reports'), true);
  assert.equal(support.includes('/jobs'), true);
  assert.equal(support.includes('/platform/billing'), true);

  const finance = platformNavItemsForRole('platform_finance', {
    platform: ['read'],
    platform_tenants: ['read'],
    platform_packages: ['read', 'write'],
    platform_reports: ['read'],
    notifications: ['read'],
    audit: ['read'],
    security: ['read', 'write'],
  }).map(([, href]) => href);
  assert.equal(finance.includes('/platform/staff'), false);
  assert.equal(finance.includes('/platform/support'), false);
  assert.equal(finance.includes('/platform/billing'), true);
  assert.equal(finance.includes('/platform/reports'), true);
  assert.equal(finance.includes('/platform/tenants'), true);
  assert.equal(finance.includes('/jobs'), true);

  // Platform settings are owner-only in the sidebar.
  assert.equal(owner.includes('/platform/settings'), true);
  assert.equal(legacy.includes('/platform/settings'), true);
  assert.equal(admin.includes('/platform/settings'), false);
  assert.equal(support.includes('/platform/settings'), false);
  assert.equal(finance.includes('/platform/settings'), false);
});
