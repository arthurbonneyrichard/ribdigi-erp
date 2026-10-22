import assert from 'node:assert/strict';
import test from 'node:test';

import { mergePlatformBillingStatus } from './billingStatus.ts';

test('connection test keeps configured status and nested secret flag', () => {
  const current = {
    provider: 'mock',
    configured: true,
    live_charges: false,
    gateway: {
      provider: 'mock',
      mode: 'sandbox',
      secret_configured: true,
      secret_hint: '…box',
      enabled: false,
      last_test_ok: false,
    },
  };
  const probe = {
    provider: 'mock',
    mode: 'sandbox',
    enabled: false,
    connected: false,
    secret_configured: true,
    secret_hint: '…box',
    last_test_ok: true,
    last_test_at: '2026-10-08T09:40:00',
    last_test_message: 'sandbox_ready',
    secret: 'must-not-stick',
  };
  const next = mergePlatformBillingStatus(current, probe) as {
    configured: boolean;
    live_charges: boolean;
    provider: string;
    gateway: {
      secret_configured: boolean;
      secret_hint: string;
      last_test_ok: boolean;
      last_test_at: string;
      last_test_message: string;
      enabled: boolean;
      secret?: string;
    };
  };
  assert.equal(next.configured, true);
  assert.equal(next.live_charges, false);
  assert.equal(next.provider, 'mock');
  assert.equal(next.gateway.secret_configured, true);
  assert.equal(next.gateway.secret_hint, '…box');
  assert.equal(next.gateway.last_test_ok, true);
  assert.equal(next.gateway.last_test_at, '2026-10-08T09:40:00');
  assert.equal(next.gateway.last_test_message, 'sandbox_ready');
  assert.equal(next.gateway.enabled, false);
  assert.equal(next.gateway.secret, undefined);
  assert.equal('secret' in next, false);
});

test('failed connection test keeps configuration and does not show success', () => {
  const current = {
    provider: 'mock',
    configured: true,
    live_charges: false,
    gateway: {
      provider: 'mock',
      mode: 'sandbox',
      secret_configured: true,
      secret_hint: '…box',
      enabled: false,
      last_test_ok: false,
    },
  };
  const probe = {
    provider: 'mock',
    mode: 'sandbox',
    enabled: false,
    connected: false,
    secret_configured: true,
    secret_hint: '…box',
    last_test_ok: false,
    last_test_at: '2026-10-08T09:41:00',
    last_test_message: 'paystack_rejected',
    secret: 'must-not-stick',
    webhook_secret: 'must-not-stick',
  };
  const next = mergePlatformBillingStatus(current, probe) as {
    configured: boolean;
    live_charges: boolean;
    gateway: {
      secret_configured: boolean;
      secret_hint: string;
      last_test_ok: boolean;
      last_test_at: string;
      last_test_message: string;
      enabled: boolean;
      secret?: string;
      webhook_secret?: string;
    };
    secret?: string;
  };
  assert.equal(next.configured, true);
  assert.equal(next.live_charges, false);
  assert.equal(next.gateway.secret_configured, true);
  assert.equal(next.gateway.secret_hint, '…box');
  assert.equal(next.gateway.last_test_ok, false);
  assert.equal(next.gateway.last_test_at, '2026-10-08T09:41:00');
  assert.equal(next.gateway.last_test_message, 'paystack_rejected');
  assert.equal(next.gateway.enabled, false);
  assert.equal(next.gateway.secret, undefined);
  assert.equal(next.gateway.webhook_secret, undefined);
  assert.equal(next.secret, undefined);
});
