import assert from 'node:assert/strict';
import test from 'node:test';
import { formatElapsed } from './format';

test('formatElapsed reads as minutes and hours', () => {
  assert.equal(formatElapsed(null), '');
  assert.equal(formatElapsed(0), 'under a minute');
  assert.equal(formatElapsed(59), 'under a minute');
  assert.equal(formatElapsed(60), '1 minute');
  assert.equal(formatElapsed(12 * 60), '12 minutes');
  assert.equal(formatElapsed(60 * 60), '1 hour');
  assert.equal(formatElapsed(2 * 60 * 60 + 5 * 60), '2 hours 5 minutes');
});
