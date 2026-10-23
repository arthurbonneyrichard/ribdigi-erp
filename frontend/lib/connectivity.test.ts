import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import {
  CATALOG_NOT_SAVED,
  EXPIRED_OFFLINE,
  OFFLINE_COMPLETE_MISSING,
  OFFLINE_READY,
  PREPARING_OFFLINE,
  UNPREPARED_OFFLINE,
  classifyLink,
  describePrepareFailure,
  explainOfflineAccess,
  linkStatusText,
  offlineSellingStatus,
} from './connectivity';

test('classifyLink does not treat navigator online as API up', () => {
  assert.equal(
    classifyLink({ navigatorOnline: true, apiReachable: false, syncing: false, syncFailed: false }),
    'api_down'
  );
  assert.equal(
    classifyLink({ navigatorOnline: false, apiReachable: null, syncing: false, syncFailed: false }),
    'offline'
  );
  assert.equal(
    classifyLink({ navigatorOnline: true, apiReachable: true, syncing: true, syncFailed: false }),
    'syncing'
  );
  assert.equal(
    classifyLink({ navigatorOnline: true, apiReachable: true, syncing: false, syncFailed: true }),
    'sync_failed'
  );
  assert.equal(
    classifyLink({ navigatorOnline: true, apiReachable: true, syncing: false, syncFailed: false }),
    'online'
  );
});

test('status text names the state and does not rely on color', () => {
  assert.equal(linkStatusText({ phase: 'offline', pending: 2, lastSyncAt: null, syncError: '' }).label, 'Offline');
  assert.match(linkStatusText({ phase: 'offline', pending: 2, lastSyncAt: null, syncError: '' }).detail, /2 saved sales/);
  assert.equal(
    linkStatusText({ phase: 'offline', pending: 1, lastSyncAt: null, syncError: '' }).detail,
    '1 saved sale waiting'
  );
  assert.equal(linkStatusText({ phase: 'api_down', pending: 0, lastSyncAt: null, syncError: '' }).label, 'Offline');
  assert.match(linkStatusText({ phase: 'api_down', pending: 0, lastSyncAt: null, syncError: '' }).detail, /server did not respond/i);
  assert.equal(linkStatusText({ phase: 'syncing', pending: 1, lastSyncAt: null, syncError: '' }).label, 'Syncing');
  assert.equal(linkStatusText({ phase: 'sync_failed', pending: 1, lastSyncAt: null, syncError: 'Price changed' }).label, 'Sync failed');
  assert.match(linkStatusText({ phase: 'sync_failed', pending: 1, lastSyncAt: null, syncError: 'Price changed' }).detail, /Price changed/);
  assert.match(
    linkStatusText({ phase: 'sync_failed', pending: 1, lastSyncAt: null, syncError: '' }).detail,
    /automatically/
  );
  assert.doesNotMatch(
    linkStatusText({ phase: 'sync_failed', pending: 1, lastSyncAt: null, syncError: '' }).detail,
    /Send saved sales/
  );
  assert.equal(linkStatusText({ phase: 'online', pending: 0, lastSyncAt: null, syncError: '' }).label, 'Online');
  assert.match(
    linkStatusText({ phase: 'online', pending: 2, lastSyncAt: '2026-10-13T00:00:00.000Z', syncError: '' }).detail,
    /2 saved sales waiting.*automatically/
  );
});

test('offline complete stays missing for the documented limits', () => {
  assert.match(OFFLINE_COMPLETE_MISSING, /not strong device binding/);
  assert.match(OFFLINE_COMPLETE_MISSING, /no till-agent journal on this PC cannot recover/);
  assert.match(OFFLINE_COMPLETE_MISSING, /Point of Sale page is open and signed in/);
  assert.match(OFFLINE_COMPLETE_MISSING, /live site has not been tested/);
  const root = process.env.RIBDIGI_FRONTEND_ROOT || path.resolve(__dirname, '..');
  const doc = fs.readFileSync(path.join(root, '..', 'docs', 'OFFLINE_POS.md'), 'utf8');
  assert.ok(doc.includes(OFFLINE_COMPLETE_MISSING));
  assert.match(doc, /Offline Complete remains \*\*MISSING\*\*/);
});

test('offline sign-in explains unprepared, expired, and prepared devices', () => {
  assert.equal(explainOfflineAccess(null).message, UNPREPARED_OFFLINE);
  assert.equal(explainOfflineAccess({ grant_id: '', user_id: 'u', tenant_id: 't' }).prepared, false);
  const expired = explainOfflineAccess({
    grant_id: 'g',
    user_id: 'u',
    tenant_id: 't',
    offline_valid_until: '2020-01-01T00:00:00.000Z',
  });
  assert.equal(expired.prepared, false);
  assert.equal(expired.message, EXPIRED_OFFLINE);
  const revoked = explainOfflineAccess({
    grant_id: 'g',
    user_id: 'u',
    tenant_id: 't',
    revoked_at: '2026-01-01T00:00:00.000Z',
    offline_valid_until: '2099-01-01T00:00:00.000Z',
  });
  assert.equal(revoked.prepared, false);
  const ready = explainOfflineAccess(
    {
      grant_id: 'g',
      user_id: 'u',
      tenant_id: 't',
      offline_valid_until: '2099-01-01T00:00:00.000Z',
    },
    Date.parse('2026-10-13T00:00:00.000Z')
  );
  assert.equal(ready.prepared, true);
});

test('signed-in online till does not keep the unprepared sentence after prepare', () => {
  assert.equal(
    offlineSellingStatus({ grantId: null, catalogSaved: false, valid: false, online: false }),
    UNPREPARED_OFFLINE
  );
  assert.equal(
    offlineSellingStatus({ grantId: null, catalogSaved: false, valid: false, online: true }),
    PREPARING_OFFLINE
  );
  assert.equal(
    offlineSellingStatus({
      grantId: 'g',
      catalogSaved: true,
      valid: true,
      online: true,
    }),
    OFFLINE_READY
  );
  const failed = describePrepareFailure(new Error('Offline access could not be prepared. 403'), false);
  assert.match(failed, /Offline access could not be prepared/);
  assert.ok(failed.endsWith(UNPREPARED_OFFLINE));
  assert.equal(
    offlineSellingStatus({ grantId: null, online: true, failure: failed }),
    failed
  );
  const catalogFail = describePrepareFailure(new Error('The product list could not be downloaded. 500'), true);
  assert.equal(catalogFail.includes(UNPREPARED_OFFLINE), false);
  assert.equal(
    offlineSellingStatus({
      grantId: 'g',
      catalogSaved: false,
      valid: true,
      online: true,
      failure: catalogFail,
    }),
    catalogFail
  );
  assert.equal(
    offlineSellingStatus({ grantId: 'g', catalogSaved: false, valid: true, online: true }),
    CATALOG_NOT_SAVED
  );
  assert.equal(
    offlineSellingStatus({
      grantId: 'g',
      catalogSaved: true,
      valid: false,
      revoked: false,
      online: true,
    }),
    `Not prepared. ${EXPIRED_OFFLINE}`
  );
  assert.match(
    offlineSellingStatus({
      grantId: 'g',
      catalogSaved: true,
      valid: false,
      revoked: true,
    }),
    /turned off on this device/
  );
  const root = process.env.RIBDIGI_FRONTEND_ROOT || path.resolve(__dirname, '..');
  const page = fs.readFileSync(path.join(root, 'app', '(dashboard)', 'pos', 'page.tsx'), 'utf8');
  assert.match(page, /if \(!online \|\| !tenantId \|\| !meId\) return/);
  assert.doesNotMatch(page, /!navigator\.onLine\) return/);
  assert.match(page, /describePrepareFailure/);
  assert.doesNotMatch(page, /catch \{\s*\/\* the panel shows offline access/s);
  const panel = fs.readFileSync(path.join(root, 'components', 'PosOfflinePanel.tsx'), 'utf8');
  assert.doesNotMatch(panel, /Not prepared\. Connect to the internet/);
  assert.match(panel, /offlineSellingStatus/);
  const login = fs.readFileSync(path.join(root, 'app', 'page.tsx'), 'utf8');
  assert.match(login, /prev === UNPREPARED_OFFLINE/);
  assert.match(login, /phase === 'online'/);
});

test('classifyLink trusts a server that answers even when the browser says offline', () => {
  assert.equal(
    classifyLink({ navigatorOnline: false, apiReachable: true, syncing: false, syncFailed: false }),
    'online'
  );
  assert.equal(
    classifyLink({ navigatorOnline: false, apiReachable: false, syncing: false, syncFailed: false }),
    'offline'
  );
});
