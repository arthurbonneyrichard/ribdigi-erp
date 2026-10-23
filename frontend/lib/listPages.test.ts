import assert from 'node:assert/strict';
import test from 'node:test';
import {
  LIST_PAGE_SIZE,
  PRODUCT_LIST_PAGE_SIZE,
  PRODUCT_LIST_PAGE_SIZES,
  displayProductName,
  matchesCustomerList,
  matchesProductList,
  paginate,
  sortCustomers,
  sortProducts,
} from './listPages';

test('paginate slices and clamps page', () => {
  const rows = Array.from({ length: 23 }, (_, i) => i + 1);
  const first = paginate(rows, 1);
  assert.equal(first.page, 1);
  assert.equal(first.pages, 3);
  assert.equal(first.total, 23);
  assert.deepEqual(first.rows, rows.slice(0, LIST_PAGE_SIZE));
  const last = paginate(rows, 99);
  assert.equal(last.page, 3);
  assert.equal(last.rows.length, 3);
});

test('product list pages 50 by default and accepts 25 or 100', () => {
  assert.equal(PRODUCT_LIST_PAGE_SIZE, 50);
  assert.deepEqual([...PRODUCT_LIST_PAGE_SIZES], [25, 50, 100]);
  const rows = Array.from({ length: 120 }, (_, i) => i + 1);
  const first = paginate(rows, 1, PRODUCT_LIST_PAGE_SIZE);
  assert.equal(first.pages, 3);
  assert.equal(first.rows.length, 50);
  assert.equal(paginate(rows, 2, 25).rows.length, 25);
  assert.equal(paginate(rows, 2, 100).rows[0], 101);
});

test('product filters search category brand and low stock', () => {
  const p = {
    name: 'Rice 5kg',
    sku: 'RC-1',
    barcode: '111',
    category: 'Grocery',
    brand: 'House',
    category_id: 'c1',
    brand_id: 'b1',
  };
  assert.equal(
    matchesProductList(p, { q: 'rice', categoryId: '', brandId: '', stock: 'all' }, 'green'),
    true,
  );
  assert.equal(
    matchesProductList(p, { q: '', categoryId: 'c2', brandId: '', stock: 'all' }, 'green'),
    false,
  );
  assert.equal(
    matchesProductList(p, { q: '', categoryId: '', brandId: 'b1', stock: 'low' }, 'green'),
    false,
  );
  assert.equal(
    matchesProductList(p, { q: '', categoryId: '', brandId: '', stock: 'low' }, 'red'),
    true,
  );
});

test('sort products by qty and name', () => {
  const rows = [
    { name: 'B', selling_price: 2, stock_qty: 1 },
    { name: 'A', selling_price: 1, stock_qty: 9 },
  ];
  assert.equal(sortProducts(rows, 'name', 1)[0].name, 'A');
  assert.equal(sortProducts(rows, 'qty', -1)[0].stock_qty, 9);
});

test('customer filters search status group and profile', () => {
  const c = {
    name: 'Ama Stores',
    code: 'C-1',
    email: 'ama@example.com',
    phone: '+233200000000',
    category: 'Retail',
    status: 'active',
    profile_type: 'registered',
    customer_group_id: 'g1',
    customer_group: { name: 'Gold' },
  };
  assert.equal(
    matchesCustomerList(c, { q: 'ama', status: 'all', groupId: '', profileType: 'all' }),
    true,
  );
  assert.equal(
    matchesCustomerList(c, { q: '', status: 'inactive', groupId: '', profileType: 'all' }),
    false,
  );
  assert.equal(
    matchesCustomerList(c, { q: '', status: 'all', groupId: 'g2', profileType: 'all' }),
    false,
  );
  assert.equal(
    matchesCustomerList(c, { q: '', status: 'all', groupId: '', profileType: 'walk_in' }),
    false,
  );
});

test('displayProductName shows the name as entered and leaves blanks', () => {
  assert.equal(displayProductName('Rice 5kg'), 'Rice 5kg');
  assert.equal(displayProductName('  sku-safe  '), 'sku-safe');
  assert.equal(displayProductName(''), '—');
  assert.equal(displayProductName(null), '—');
});

test('sort customers by name and balance', () => {
  const rows = [
    { name: 'B', balance: 2 },
    { name: 'A', balance: 9 },
  ];
  assert.equal(sortCustomers(rows, 'name', 1)[0].name, 'A');
  assert.equal(sortCustomers(rows, 'balance', -1)[0].balance, 9);
});
