import assert from 'node:assert/strict';
import test from 'node:test';
import { cspHeaders, cspMode, legacyPolicy, newNonce, noncePolicy } from './csp';

const env = {};

test('default mode keeps today\'s behaviour in production, reports in development', () => {
  assert.equal(cspMode(undefined, true), 'legacy');
  assert.equal(cspMode('', false), 'report-only');
  assert.equal(cspMode('ENFORCE', true), 'enforce');
  assert.equal(cspMode('nonsense', true), 'legacy');
});

test('nonce policy has the nonce and no unsafe-inline in script-src', () => {
  const p = noncePolicy('abc123', env);
  const script = p.split(';').find((d) => d.trim().startsWith('script-src')) || '';
  assert.ok(script.includes("'nonce-abc123'"));
  assert.ok(!script.includes('unsafe-inline'));
  assert.ok(!script.includes('unsafe-eval'));
  assert.ok(p.includes("object-src 'none'") && p.includes("base-uri 'self'"));
});

test('dev adds eval only in development', () => {
  assert.ok(noncePolicy('n', env, { dev: true }).includes("'unsafe-eval'"));
  assert.ok(!noncePolicy('n', env, { dev: false }).includes("'unsafe-eval'"));
});

test('legacy keeps unsafe-inline', () => {
  assert.ok(legacyPolicy(env).includes("script-src 'self' 'unsafe-inline'"));
});

test('analytics host joins script-src only when fully configured', () => {
  assert.ok(!noncePolicy('n', {}).includes('umami'));
  const on = { NEXT_PUBLIC_UMAMI_SRC: 'https://stats.example.com/script.js', NEXT_PUBLIC_UMAMI_WEBSITE_ID: 'x' };
  assert.ok(noncePolicy('n', on).includes('https://stats.example.com'));
  assert.ok(!noncePolicy('n', { NEXT_PUBLIC_UMAMI_SRC: 'https://stats.example.com/s.js' }).includes('stats.example.com'));
});

test('modes send the right headers', () => {
  const legacy = cspHeaders('legacy', 'n1', env, false);
  assert.deepEqual(Object.keys(legacy.response), ['Content-Security-Policy']);
  assert.ok(legacy.response['Content-Security-Policy'].includes("'unsafe-inline'"));
  assert.deepEqual(legacy.request, {});

  // Report-only: Next.js must see only the strict policy on the request, or it cannot find the nonce.
  const ro = cspHeaders('report-only', 'n1', env, false);
  assert.ok(!('Content-Security-Policy' in ro.response));
  assert.ok(ro.response['x-csp-enforced'].includes("script-src 'self' 'unsafe-inline'"));
  assert.ok(ro.response['Content-Security-Policy-Report-Only'].includes("'nonce-n1'"));
  assert.ok(ro.response['Content-Security-Policy-Report-Only'].includes('report-uri /api/csp-report'));
  assert.deepEqual(Object.keys(ro.request), ['content-security-policy-report-only']);
  assert.ok(ro.request['content-security-policy-report-only'].includes("'nonce-n1'"));

  const en = cspHeaders('enforce', 'n1', env, false);
  assert.deepEqual(Object.keys(en.response), ['Content-Security-Policy']);
  assert.ok(!en.response['Content-Security-Policy'].includes("script-src 'self' 'unsafe-inline'"));
  assert.ok(en.request['content-security-policy'].includes("'nonce-n1'"));
});

test('each request gets a different nonce', () => {
  const seen = new Set(Array.from({ length: 50 }, () => newNonce()));
  assert.equal(seen.size, 50);
  assert.ok([...seen].every((n) => /^[A-Za-z0-9+/]{22}==$/.test(n)));
});
