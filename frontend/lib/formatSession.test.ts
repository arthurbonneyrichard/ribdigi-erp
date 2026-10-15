import assert from 'node:assert/strict';
import test from 'node:test';
import {
  formatWhen,
  invalidateCompanyFormatCache,
  peekCompanyFormatCache,
  storeCompanyFormatCache,
  subscribeCompanyFormatRefresh,
} from './format';

test('company format cache reloads after invalidation and keeps the last separators', () => {
  storeCompanyFormatCache({
    date_format: 'YYYY-MM-DD',
    decimal_separator: '.',
    thousand_separator: ',',
    time_format: '24h',
  });
  assert.equal(peekCompanyFormatCache()?.date_format, 'YYYY-MM-DD');
  let hits = 0;
  const stop = subscribeCompanyFormatRefresh(() => {
    hits += 1;
  });
  invalidateCompanyFormatCache();
  assert.equal(hits, 1);
  assert.equal(peekCompanyFormatCache(), undefined);
  assert.equal(formatWhen('2026-10-14T15:04:00'), '2026-10-14 15:04');
  stop();
});
