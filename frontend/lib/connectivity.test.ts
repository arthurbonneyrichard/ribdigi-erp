import assert from 'node:assert/strict';
import test from 'node:test';
import {
  EXPIRED_OFFLINE,
  UNPREPARED_OFFLINE,
  classifyLink,
  explainOfflineAccess,
  linkStatusText,
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
  assert.equal(linkStatusText({ phase: 'online', pending: 0, lastSyncAt: null, syncError: '' }).label, 'Online');
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
