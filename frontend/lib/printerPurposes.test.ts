import assert from 'node:assert/strict';
import test from 'node:test';
import {
  filterListedPrinterPurposes,
  printerPurposeLabel,
  printerPurposesForIndustry,
  printerRowVisible,
  resolvePrinterPurposes,
} from './printerPurposes';

test('retail and hotel hide kitchen and bar', () => {
  for (const industry of ['retail', 'hotel', 'pharmacy', 'bakery', 'mart', 'fmcg', null]) {
    const purposes = printerPurposesForIndustry(industry);
    assert.deepEqual(purposes, ['barcode', 'customer_receipt', 'invoice']);
    assert.equal(purposes.includes('kitchen'), false);
    assert.equal(purposes.includes('bar'), false);
  }
});

test('restaurant includes kitchen and bar', () => {
  assert.deepEqual(printerPurposesForIndustry('restaurant'), [
    'bar',
    'barcode',
    'customer_receipt',
    'invoice',
    'kitchen',
  ]);
  assert.deepEqual(printerPurposesForIndustry('food_service'), printerPurposesForIndustry('restaurant'));
});

test('stale API kitchen list is filtered for retail', () => {
  assert.deepEqual(
    resolvePrinterPurposes('retail', ['customer_receipt', 'kitchen', 'bar', 'invoice']),
    ['customer_receipt', 'invoice'],
  );
  assert.deepEqual(resolvePrinterPurposes('hotel', ['kitchen', 'bar']), [
    'barcode',
    'customer_receipt',
    'invoice',
  ]);
  assert.deepEqual(resolvePrinterPurposes('restaurant', ['kitchen', 'barcode']), ['kitchen', 'barcode']);
});

test('purpose labels are operator-facing', () => {
  assert.equal(printerPurposeLabel('customer_receipt'), 'Receipt');
  assert.equal(printerPurposeLabel('kitchen'), 'Kitchen');
});

test('retail hides leftover kitchen rows but keeps receipt printers', () => {
  const allowed = printerPurposesForIndustry('retail');
  assert.equal(printerRowVisible(['kitchen'], allowed), false);
  assert.equal(printerRowVisible(['bar'], allowed), false);
  assert.equal(printerRowVisible(['kitchen', 'bar'], allowed), false);
  assert.equal(printerRowVisible(['customer_receipt'], allowed), true);
  assert.equal(printerRowVisible(['kitchen', 'customer_receipt'], allowed), true);
  assert.deepEqual(filterListedPrinterPurposes(['kitchen', 'customer_receipt', 'bar'], allowed), [
    'customer_receipt',
  ]);
});

test('restaurant still shows kitchen and bar rows', () => {
  const allowed = printerPurposesForIndustry('restaurant');
  assert.equal(printerRowVisible(['kitchen'], allowed), true);
  assert.equal(printerRowVisible(['bar'], allowed), true);
  assert.deepEqual(filterListedPrinterPurposes(['kitchen', 'bar'], allowed), ['kitchen', 'bar']);
});
