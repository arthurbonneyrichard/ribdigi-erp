import assert from 'node:assert/strict';
import test from 'node:test';
import { hoursUntilValid, isOfflineAuthValid, partitionScope } from './posOffline';

test('offline partition isolates tenant/user/store', () => {
  assert.equal(partitionScope('t1', 'u1', 's1'), 't1::u1::s1');
  assert.notEqual(partitionScope('t1', 'u1', 's1'), partitionScope('t2', 'u1', 's1'));
  assert.notEqual(partitionScope('t1', 'u1', 's1'), partitionScope('t1', 'u2', 's1'));
});

test('offline duration default is 168 hours and clamps to 1–168', () => {
  assert.equal(hoursUntilValid(undefined), 168);
  assert.equal(hoursUntilValid(7), 7);
  assert.equal(hoursUntilValid(0), 1);
  assert.equal(hoursUntilValid(999), 168);
});

test('offline auth requires prior online envelope and rejects expiry', () => {
  assert.equal(isOfflineAuthValid(null), false);
  const future = new Date(Date.now() + 60_000).toISOString();
  const past = new Date(Date.now() - 60_000).toISOString();
  assert.equal(
    isOfflineAuthValid({
      tenant_id: 't1',
      store_id: 's1',
      user_id: 'u1',
      device_id: 'dev-1',
      permissions: ['pos:write'],
      issued_at: future,
      last_online_at: future,
      offline_valid_until: future,
      offline_auth_hours: 168,
      catalog_version: future,
      application_version: 'web-mvp',
      scope: 't1::u1::s1',
    }),
    true
  );
  assert.equal(
    isOfflineAuthValid({
      tenant_id: 't1',
      store_id: 's1',
      user_id: 'u1',
      device_id: 'dev-1',
      permissions: ['pos:write'],
      issued_at: past,
      last_online_at: past,
      offline_valid_until: past,
      offline_auth_hours: 168,
      catalog_version: past,
      application_version: 'web-mvp',
      scope: 't1::u1::s1',
    }),
    false
  );
  assert.equal(
    isOfflineAuthValid({
      tenant_id: '',
      store_id: null,
      user_id: '',
      device_id: 'dev-1',
      permissions: [],
      issued_at: future,
      last_online_at: future,
      offline_valid_until: future,
      offline_auth_hours: 168,
      catalog_version: future,
      application_version: 'web-mvp',
      scope: '::_::',
    }),
    false
  );
});
