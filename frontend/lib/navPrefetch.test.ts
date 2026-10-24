import assert from 'node:assert/strict';
import test from 'node:test';
import { hrefPath, prefetchPathsForHref } from './navPrefetch';

test('hrefPath drops query and hash for sidebar destinations', () => {
  assert.equal(hrefPath('/inventory?tab=products'), '/inventory');
  assert.equal(hrefPath('/sales'), '/sales');
});

test('sales hover warms the lists the sales desk reads on first paint', () => {
  const paths = prefetchPathsForHref('/sales');
  assert.ok(paths.includes('/sales/invoices'));
  assert.ok(paths.includes('/sales/quotations'));
  assert.ok(paths.includes('/customers'));
  assert.ok(paths.includes('/products'));
});

test('inventory tab links share one catalog warm set', () => {
  const fromTab = prefetchPathsForHref('/inventory?tab=categories');
  const fromRoot = prefetchPathsForHref('/inventory');
  assert.deepEqual(fromTab, fromRoot);
  assert.ok(fromTab.includes('/products?limit=80'));
});

test('unknown hrefs do not invent API paths', () => {
  assert.deepEqual(prefetchPathsForHref('/not-a-desk'), []);
});
