import assert from 'node:assert/strict';
import test from 'node:test';
import { formatApiError, parseRetryAfterHeader } from './api';

test('429 uses Retry-After seconds and hides RATE_LIMIT_EXCEEDED', () => {
  assert.equal(parseRetryAfterHeader('3'), 3);
  assert.equal(parseRetryAfterHeader('0'), 1);
  assert.equal(
    formatApiError({ detail: 'RATE_LIMIT_EXCEEDED', message: 'Rate limit exceeded. Try again shortly.' }, 429),
    'Rate limit exceeded. Try again shortly.',
  );
  assert.equal(formatApiError({ detail: 'RATE_LIMIT_EXCEEDED' }, 429), 'Too many requests. Wait a moment, then retry.');
});

test('403 and 5xx are not session-expired copy', () => {
  assert.equal(formatApiError({}, 403), 'You do not have permission to do that.');
  assert.equal(formatApiError({}, 500), 'Could not complete that. Try again.');
  assert.match(formatApiError({}, 500, '/auth/login'), /try again/i);
  assert.equal(formatApiError({}, 500, '/auth/login').includes('Hotel extras'), false);
  assert.match(
    formatApiError({}, 500, '/hotel/services'),
    /Hotel extras may need a database update/,
  );
  assert.equal(formatApiError({}, 401), 'Your session expired. Please sign in again.');
});

test('isAbortError does not treat timeouts as user abort', async () => {
  const { isAbortError } = await import('./api');
  const aborted = new DOMException('The operation was aborted.', 'AbortError');
  assert.equal(isAbortError(aborted), true);
  assert.equal(isAbortError(new Error('The request timed out. Check your connection and try again.')), false);
  assert.equal(isAbortError(new Error('Request failed')), false);
});
