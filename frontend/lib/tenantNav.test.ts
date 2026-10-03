import assert from 'node:assert/strict';
import test from 'node:test';
import {
  ALWAYS_LIST_NAV_GROUP_IDS,
  CASHIER_NAV_MODULES,
  filterNavForStoreMode,
  groupedTenantNav,
  hideStoreUx,
  HOTEL_CASHIER_NAV_MODULES,
  HOTEL_OMIT_NAV_GROUP_IDS,
  navAllowlistFromPermissions,
  PEOPLE_NAV_ITEMS,
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

test('cashier nav allowlist is dashboard and POS only', () => {
  assert.deepEqual([...CASHIER_NAV_MODULES].sort(), ['dashboard', 'pos']);
  assert.equal(CASHIER_NAV_MODULES.includes('inventory'), false);
  assert.equal(CASHIER_NAV_MODULES.includes('sales'), false);
  assert.equal(CASHIER_NAV_MODULES.includes('users'), false);
  assert.equal(CASHIER_NAV_MODULES.includes('purchasing'), false);
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
  assert.equal(unauthorizedNavRedirect('/sales', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/customers', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/credit?kind=payable', 'cashier', CASHIER_NAV_MODULES), '/pos');
  assert.equal(unauthorizedNavRedirect('/pos', 'cashier', CASHIER_NAV_MODULES), null);
  assert.equal(unauthorizedNavRedirect('/dashboard', 'cashier', CASHIER_NAV_MODULES), null);
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

test('pharmacy grouped nav surfaces lots/batches, not hotel PMS', () => {
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
      id: 'industry',
      label: 'Industry-specific features',
      items: [
        ['Hotel Dashboard', '/hotel', 'hotel'],
        ['FMCG overview', '/fmcg', 'fmcg'],
      ],
    },
  ];
  const visible: NavItem[] = [
    ['Expiry', '/inventory?tab=expiry', 'inventory'],
    ['Batches', '/inventory?tab=batches', 'inventory'],
    ['Rx-only products', '/inventory?tab=products&rx=1', 'inventory'],
    ['Prescriptions', '/prescriptions', 'inventory'],
  ];
  const out = groupedTenantNav(groups, visible, 'pharmacy');
  const industry = out.find((g) => g.id === 'industry');
  assert.ok(industry);
  assert.equal(industry.label, 'Pharmacy management');
  assert.deepEqual(
    industry.items.map(([, href]) => href),
    [
      '/inventory?tab=expiry',
      '/inventory?tab=batches',
      '/inventory?tab=products&rx=1',
      '/prescriptions',
    ],
  );
  assert.equal(
    industry.items.some(([, href]) => href.startsWith('/hotel')),
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
  const industry = wholesale.find((g) => g.id === 'industry');
  assert.ok(industry);
  assert.equal(industry.label, 'Wholesale operations');
  assert.deepEqual(
    industry.items.map(([, href]) => href),
    ['/sales?tab=quotations', '/sales?tab=orders', '/credit'],
  );
  const combo = groupedTenantNav(groups, visible, 'retail_wholesale');
  const comboInd = combo.find((g) => g.id === 'industry');
  assert.ok(comboInd);
  assert.equal(comboInd.label, 'Retail + wholesale');
  assert.equal(comboInd.items[0][1], '/pos');
  assert.equal(
    comboInd.items.some(([, href]) => href.startsWith('/hotel') || href === '/prescriptions'),
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
