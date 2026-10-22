import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
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
  assert.equal(
    formatApiError({}, 500, '/auth/login'),
    'Sign-in could not be completed because the server failed. Try again shortly.',
  );
  assert.notEqual(formatApiError({}, 500, '/auth/login'), formatApiError({}, 500));
  assert.equal(formatApiError({}, 500, '/auth/login').includes('Hotel extras'), false);
  assert.equal(formatApiError({ detail: 'traceback postgres sqlalchemy' }, 500, '/auth/login').includes('postgres'), false);
  assert.match(
    formatApiError({}, 500, '/hotel/services'),
    /Hotel extras may need a database update/,
  );
  assert.equal(formatApiError({}, 401), 'Your session expired. Please sign in again.');
});

test('sign-in errors stay distinct from connection and session copy', async () => {
  const { unreachableApiMessage } = await import('./api');
  assert.equal(
    formatApiError({ detail: 'Invalid credentials' }, 401, '/auth/login'),
    'The email or password is incorrect.',
  );
  assert.equal(
    formatApiError({ detail: 'Invalid 2FA code' }, 401, '/auth/login'),
    'Invalid 2FA code',
  );
  assert.equal(
    formatApiError({ detail: 'Tenant not found' }, 404, '/auth/login'),
    'That workspace was not found. Check the tenant slug or ID.',
  );
  assert.equal(
    formatApiError({ detail: 'Account temporarily locked' }, 423, '/auth/login'),
    'This account is temporarily locked. Try again later.',
  );
  assert.equal(formatApiError({}, 404), 'Not found.');
  const offline = unreachableApiMessage();
  assert.match(offline, /server did not respond/i);
  assert.match(offline, /Pending Point of Sale sales stay on this device/i);
  assert.doesNotMatch(offline, /API is running/i);
  assert.doesNotMatch(offline, /workspace slug/i);
  const signIn = unreachableApiMessage('/auth/login');
  assert.match(signIn, /Sign-in could not reach the server/i);
  assert.match(signIn, /Check the connection, then try again/i);
  assert.notEqual(offline, formatApiError({}, 500, '/auth/login'));
  assert.notEqual(offline, formatApiError({ detail: 'Invalid credentials' }, 401, '/auth/login'));
  assert.notEqual(signIn, formatApiError({}, 500, '/auth/login'));
});

test('browser sign-in posts to same-origin /api/v1', async () => {
  const { apiRoot } = await import('./api');
  const previous = globalThis.window;
  globalThis.window = {} as Window & typeof globalThis;
  try {
    assert.equal(apiRoot(), '/api/v1');
  } finally {
    if (previous === undefined) delete globalThis.window;
    else globalThis.window = previous;
  }
  const here = dirname(fileURLToPath(import.meta.url));
  const login = readFileSync(join(here, '../app/page.tsx'), 'utf8');
  const nextConfig = readFileSync(join(here, '../next.config.mjs'), 'utf8');
  assert.match(login, /api\('\/auth\/login'/);
  assert.match(nextConfig, /source: '\/api\/v1\/:path\*'/);
});

test('isAbortError does not treat timeouts as user abort', async () => {
  const { isAbortError } = await import('./api');
  const aborted = new DOMException('The operation was aborted.', 'AbortError');
  assert.equal(isAbortError(aborted), true);
  assert.equal(isAbortError(new Error('The request timed out. Check your connection and try again.')), false);
  assert.equal(isAbortError(new Error('Request failed')), false);
});
