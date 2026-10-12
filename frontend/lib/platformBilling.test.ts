import assert from 'node:assert/strict';
import test from 'node:test';

import {
  canAssignSubscription,
  packageCodeFromName,
  gatewaySaveBody,
  packageCreateBody,
  packageUpdateBody,
  subscriptionAmountLabel,
  subscriptionAmountToSend,
  subscriptionTermLabel,
} from './platformBilling.ts';

test('subscription term uses short labels', () => {
  assert.equal(subscriptionTermLabel(null, null), '—');
  assert.equal(subscriptionTermLabel(1, 'months'), '1 month');
  assert.equal(subscriptionTermLabel(12, 'months'), '12 months');
  assert.equal(subscriptionTermLabel(1, 'years'), '1 year');
  assert.equal(subscriptionTermLabel(2, 'years'), '2 years');
  assert.equal(subscriptionTermLabel(3, 'weeks'), '—');
});

test('subscription amount keeps the currency and a blank price blank', () => {
  assert.equal(subscriptionAmountLabel(null, 'GHS', ''), '—');
  assert.equal(subscriptionAmountLabel(499, 'ghs', '499.00'), 'GHS 499.00');
  assert.equal(subscriptionAmountLabel(0, null, '0.00'), 'GHS 0.00');
});

test('assigned amount uses the company number format', () => {
  assert.deepEqual(subscriptionAmountToSend('1,234.50', 'starter', null), { amount: 1234.5 });
  assert.deepEqual(
    subscriptionAmountToSend('1.234,50', 'professional', {
      thousand_separator: '.',
      decimal_separator: ',',
    }),
    { amount: 1234.5 },
  );
  assert.deepEqual(subscriptionAmountToSend('0', 'trial', null), { amount: 0 });
  assert.equal('error' in subscriptionAmountToSend('', 'starter', null), true);
  assert.equal('error' in subscriptionAmountToSend('abc', 'starter', null), true);
  assert.equal('error' in subscriptionAmountToSend('-10', 'starter', null), true);
  assert.equal('error' in subscriptionAmountToSend('0', 'starter', null), true);
});

test('package code is a short slug from the name', () => {
  assert.equal(packageCodeFromName('  Hotel Yearly  '), 'hotel-yearly');
  assert.equal(packageCodeFromName('A'), 'a');
});

test('create package sends a paid plan and rejects a blank amount', () => {
  const ok = packageCreateBody(
    {
      name: 'Hotel yearly',
      code: 'hotel-yearly',
      packageCode: 'professional',
      interval: 'year',
      amount: '1,200',
      currency: 'ghs',
    },
    null,
  );
  assert.deepEqual('body' in ok ? ok.body.amount : null, 1200);
  assert.equal('body' in ok ? ok.body.currency : '', 'GHS');
  const bad = packageCreateBody(
    {
      name: 'X',
      code: 'x',
      packageCode: 'trial',
      interval: 'week',
      amount: '0',
      currency: 'EUR',
    },
    null,
  );
  assert.equal('error' in bad, true);
});

test('edit package sends the changed price without a new code', () => {
  const ok = packageUpdateBody(
    {
      name: 'Hotel yearly',
      packageCode: 'enterprise',
      interval: 'year',
      amount: '1500',
      currency: 'usd',
    },
    null,
  );
  assert.equal('body' in ok ? ok.body.name : '', 'Hotel yearly');
  assert.equal('body' in ok ? ok.body.package_code : '', 'enterprise');
  assert.equal('body' in ok ? ok.body.amount : 0, 1500);
  assert.equal('body' in ok ? 'code' in ok.body : true, false);
  assert.equal('error' in packageUpdateBody(
    { name: 'X', packageCode: 'trial', interval: 'week', amount: '0', currency: 'EUR' },
    null,
  ), true);
});

test('gateway save accepts Paystack or Flutterwave and omits a blank secret', () => {
  const flutterwave = gatewaySaveBody({
    provider: 'flutterwave',
    mode: 'sandbox',
    secret: ' FLWSECK_TEST-localkey ',
    webhookSecret: '',
  });
  assert.equal('body' in flutterwave ? flutterwave.body.provider : '', 'flutterwave');
  assert.equal('body' in flutterwave ? flutterwave.body.secret : '', 'FLWSECK_TEST-localkey');
  assert.equal('body' in flutterwave ? 'webhook_secret' in flutterwave.body : true, false);
  assert.equal(
    'error' in gatewaySaveBody({ provider: 'stripe', mode: 'sandbox', secret: '', webhookSecret: '' }),
    true,
  );
  assert.equal(
    'error' in gatewaySaveBody({
      provider: 'flutterwave',
      mode: 'live',
      secret: 'FLWSECK_TEST-localkey',
      webhookSecret: '',
    }),
    true,
  );
  assert.equal(
    'error' in gatewaySaveBody({ provider: 'mock', mode: 'live', secret: '', webhookSecret: '' }),
    true,
  );
});

test('only package write can assign a plan', () => {
  assert.equal(canAssignSubscription(null), false);
  assert.equal(canAssignSubscription({ platform_packages: ['read'] }), false);
  assert.equal(canAssignSubscription({ platform_packages: ['read', 'write'] }), true);
  assert.equal(canAssignSubscription({ '*': ['*'] }), true);
});
