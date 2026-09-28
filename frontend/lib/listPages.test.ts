import assert from 'node:assert/strict';
import test from 'node:test';
import {
  LIST_PAGE_SIZE,
  matchesProductList,
  paginate,
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
