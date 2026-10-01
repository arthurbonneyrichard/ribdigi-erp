import assert from 'node:assert/strict';
import test from 'node:test';
import {
  isIdleExpired,
  remainingIdleMs,
  shouldWarnIdle,
  warnLeadMs,
  IDLE_WARN_LEAD_MS,
} from './idleSession';

test('idle expires only after configured timeout', () => {
  const timeout = 30 * 60 * 1000;
  const last = 1_000_000;
  assert.equal(isIdleExpired(timeout, last + timeout - 1, last), false);
  assert.equal(isIdleExpired(timeout, last + timeout, last), true);
});

test('warn window is before logout and never after expiry', () => {
  const timeout = 30 * 60 * 1000;
  const last = 5_000_000;
  const lead = warnLeadMs(timeout);
  assert.equal(lead, IDLE_WARN_LEAD_MS);
  assert.equal(shouldWarnIdle(timeout, last + timeout - lead, last), true);
  assert.equal(shouldWarnIdle(timeout, last + 1_000, last), false);
  assert.equal(shouldWarnIdle(timeout, last + timeout, last), false);
});

test('remaining idle is last plus timeout minus now', () => {
  assert.equal(remainingIdleMs(1000, 400, 0), 600);
});
