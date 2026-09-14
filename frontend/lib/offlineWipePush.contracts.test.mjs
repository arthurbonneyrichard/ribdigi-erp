/**
 * Contract tests for offline remote wipe + Web Push client helpers.
 * Run: node --test frontend/lib/offlineWipePush.contracts.test.mjs
 *
 * Does NOT claim Offline Complete / push-delivery Complete / 7-day VERIFIED.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const wipeSrc = readFileSync(join(__dirname, 'offlineRemoteWipe.ts'), 'utf8');
const pushSrc = readFileSync(join(__dirname, 'offlinePush.ts'), 'utf8');
const shellSrc = readFileSync(join(__dirname, '../components/Shell.tsx'), 'utf8');
const companySrc = readFileSync(join(__dirname, '../app/company/page.tsx'), 'utf8');

describe('offlineRemoteWipe contracts', () => {
  it('keeps Completes unclaimed and marks poll-path engineering-ready', () => {
    assert.match(wipeSrc, /wipePollPathEngineeringReady:\s*true/);
    assert.match(wipeSrc, /offlineCompleteClaimed:\s*false/);
    assert.match(wipeSrc, /sevenDayVerifiedClaimed:\s*false/);
    assert.match(wipeSrc, /pushDeliveryCompleteClaimed:\s*false/);
    assert.match(wipeSrc, /ribdigi-offline-queue/);
    assert.match(wipeSrc, /wipe\/ack/);
  });
});

describe('offlinePush contracts', () => {
  it('times out PushManager.subscribe and falls back to wipe poll', () => {
    assert.match(pushSrc, /OFFLINE_PUSH_SUBSCRIBE_TIMEOUT_MS/);
    assert.match(pushSrc, /pushmanager_subscribe_timeout/);
    assert.match(pushSrc, /subscribe_timeout/);
    assert.match(pushSrc, /wipePollFallback:\s*true/);
    assert.match(pushSrc, /offlineCompleteClaimed:\s*false/);
    assert.match(pushSrc, /sevenDayVerifiedClaimed:\s*false/);
    assert.match(pushSrc, /pushDeliveryCompleteClaimed:\s*false/);
  });
});

describe('Shell + Company wipe poll UX', () => {
  it('Shell periodically polls wipe while online', () => {
    assert.match(shellSrc, /WIPE_POLL_INTERVAL_MS/);
    assert.match(shellSrc, /processPendingRemoteWipeIfNeeded/);
    assert.match(shellSrc, /setInterval\(run,\s*WIPE_POLL_INTERVAL_MS\)/);
  });

  it('Company Bind browser surfaces subscribe_timeout and poll fallback', () => {
    assert.match(companySrc, /subscribe_timeout/);
    assert.match(companySrc, /wipe poll remains/);
    assert.match(companySrc, /registerOfflinePushSubscription/);
  });
});
