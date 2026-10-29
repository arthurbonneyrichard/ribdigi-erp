import assert from 'node:assert/strict';
import test from 'node:test';
import {
  REPORT_CATALOG,
  REPORT_GROUP_ORDER,
  findReport,
  reportFromTabView,
  reportHasFilter,
  reportCopy,
  reportGroupLabel,
  reportVisible,
  reportsHref,
  reportsInGroup,
} from './reportGroups';

test('groups cover sales inventory purchases finance customers staff and email schedules', () => {
  assert.deepEqual(
    REPORT_GROUP_ORDER.map((g) => g.id),
    ['sales', 'inventory', 'purchases', 'finance', 'customers', 'staff', 'schedules'],
  );
  assert.equal(REPORT_GROUP_ORDER.find((g) => g.id === 'schedules')?.label, 'Email Schedules');
  for (const g of REPORT_GROUP_ORDER) {
    assert.ok(reportsInGroup(g.id).length > 0, `${g.id} should have reports`);
  }
});

test('staff is sales by staff; email schedules is its own group', () => {
  const staff = reportsInGroup('staff');
  assert.equal(staff.length, 1);
  assert.equal(staff[0].id, 'salesperson');
  assert.equal(staff[0].name, 'Sales by staff');
  const schedules = reportsInGroup('schedules');
  assert.equal(schedules.length, 1);
  assert.equal(schedules[0].tab, 'schedules');
  assert.equal(findReport('salesperson')?.group, 'staff');
});

test('catalog ids are unique and every report has a name and description', () => {
  const ids = REPORT_CATALOG.map((r) => r.id);
  assert.equal(ids.length, new Set(ids).size);
  for (const r of REPORT_CATALOG) {
    assert.ok(r.name.trim());
    assert.ok(r.description.trim());
    assert.ok(r.description.length < 140, `${r.id} description should stay short`);
  }
});

test('tab and view resolve to the selected report; missing view uses group default', () => {
  assert.equal(reportFromTabView('sales', null).id, 'sales_products');
  assert.equal(reportFromTabView('sales', 'returns').id, 'sales_returns');
  assert.equal(reportFromTabView('inventory', '').id, 'inventory_low_stock');
  assert.equal(reportFromTabView('inventory', 'expiry').id, 'inventory_expiry');
  assert.equal(reportFromTabView('purchases', null).id, 'purchases_overview');
  assert.equal(reportFromTabView('purchases', 'pending').id, 'purchases_pending');
  assert.equal(reportFromTabView('summary', null).id, 'summary');
  assert.equal(reportFromTabView('unknown', null).id, 'summary');
});

test('filters stay relevant: account statement needs account, not warehouse', () => {
  const stmt = findReport('accountstatement');
  assert.ok(stmt);
  assert.equal(reportHasFilter(stmt, 'account'), true);
  assert.equal(reportHasFilter(stmt, 'warehouse'), false);
  assert.equal(reportHasFilter(stmt, 'dates'), true);
  const expiry = findReport('inventory_expiry');
  assert.ok(expiry);
  assert.equal(reportHasFilter(expiry, 'expiryDays'), true);
  assert.equal(reportHasFilter(expiry, 'category'), false);
  const products = findReport('sales_products');
  assert.ok(products);
  assert.equal(reportHasFilter(products, 'category'), true);
  assert.equal(reportHasFilter(products, 'salesReturn'), false);
});

test('export is only listed when a report type exists; schedules and statement have none', () => {
  assert.equal(findReport('schedules')?.exportType, undefined);
  assert.equal(findReport('accountstatement')?.exportType, undefined);
  assert.equal(findReport('sales_products')?.exportType, 'sales_products');
  assert.equal(findReport('inventory_counts')?.exportType, 'inventory_stock_counts');
});

test('sales reports stay industry-specific and single-store hides store lists', () => {
  const pos = findReport('sales_pos');
  const quotes = findReport('sales_quotations');
  const stores = findReport('stores');
  assert.ok(pos && quotes && stores);
  assert.equal(reportVisible(pos, { industry: 'hotel', multiStore: false }), true);
  assert.equal(reportVisible(pos, { industry: 'wholesale', multiStore: true }), false);
  assert.equal(reportVisible(pos, { industry: 'fmcg', multiStore: true }), false);
  assert.equal(reportVisible(quotes, { industry: 'retail', multiStore: true }), true);
  assert.equal(reportVisible(quotes, { industry: 'hotel', multiStore: true }), false);
  assert.equal(reportVisible(quotes, { industry: 'restaurant', multiStore: true }), false);
  assert.equal(reportVisible(stores, { industry: 'retail', multiStore: false }), false);
  assert.equal(reportVisible(stores, { industry: 'retail', multiStore: true }), true);
  assert.equal(findReport('sales_products')?.name, 'Sales by product');
  assert.equal(findReport('inventory_value')?.name, 'Stock value');
  assert.equal(reportCopy(findReport('inventory_value')!, 'hotel').name, 'Supply value');
  assert.equal(reportCopy(findReport('inventory_value')!, 'retail').name, 'Stock value');
  assert.equal(reportCopy(findReport('inventory_movements')!, 'hotel').name, 'Supply movements');
  assert.equal(reportCopy(findReport('inventory_counts')!, 'hotel').name, 'Supply count variances');
  assert.equal(reportCopy(findReport('inventory_expiry')!, 'hotel').description, 'Lots nearing expiry or already expired.');
  assert.equal(reportCopy(findReport('sales_pos')!, 'hotel').name, 'Shop till sales');
  assert.equal(reportCopy(findReport('sales_pos')!, 'retail').name, 'POS sales');
  assert.equal(reportCopy(findReport('sales_pos')!, 'restaurant').name, 'Restaurant till sales');
  assert.equal(reportCopy(findReport('inventory_low_stock')!, 'restaurant').name, 'Low ingredients');
  assert.equal(reportCopy(findReport('inventory_low_stock')!, 'hotel').name, 'Low supplies');
  assert.equal(reportGroupLabel('inventory', 'Inventory', 'restaurant'), 'Ingredients');
  assert.equal(reportGroupLabel('inventory', 'Inventory', 'hotel'), 'Supplies');
  assert.equal(reportGroupLabel('inventory', 'Inventory', 'retail'), 'Inventory');
  assert.equal(reportGroupLabel('inventory', 'Inventory', 'hotel'), 'Supplies');
  assert.equal(reportGroupLabel('inventory', 'Inventory', 'retail'), 'Inventory');
  assert.equal(reportsInGroup('customers')[0].name, 'Sales by customer');
});

test('reportsHref keeps tab and optional view', () => {
  assert.equal(reportsHref(findReport('summary')!), '/reports?tab=summary');
  assert.equal(reportsHref(findReport('inventory_expiry')!), '/reports?tab=inventory&view=expiry');
});
