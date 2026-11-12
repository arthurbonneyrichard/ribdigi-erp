import assert from 'node:assert/strict';
import { pbkdf2Sync, randomBytes } from 'node:crypto';
import test from 'node:test';

class MemoryStorage {
  private rows = new Map<string, string>();
  getItem(key: string) {
    return this.rows.has(key) ? (this.rows.get(key) as string) : null;
  }
  setItem(key: string, value: string) {
    this.rows.set(key, value);
  }
  removeItem(key: string) {
    this.rows.delete(key);
  }
  clear() {
    this.rows.clear();
  }
}

const win = { localStorage: new MemoryStorage(), sessionStorage: new MemoryStorage(), location: { pathname: '/pos' } };
(globalThis as unknown as { window: unknown }).window = win;

import { checkKioskCodeOffline, endKiosk, kioskCodeLength, kioskHomeFor, readKiosk, saveKioskVerifier, startKiosk } from './posKiosk';
import { isTillOnlyLocal, isTillOnlyRoute, noteTillOnlyResponse, setTillOnlyLocal, tillOnlyPendingServer } from './posLock';

function verifierFor(code: string, rounds = 1000) {
  const salt = randomBytes(16);
  return { salt: salt.toString('hex'), hash: pbkdf2Sync(code, salt, rounds, 32, 'sha256').toString('hex'), rounds, length: code.length };
}

test('till-only routes are the tills and Sales', () => {
  for (const ok of ['/pos', '/sales', '/sales/', '/restaurant/till', '/restaurant/till/x']) assert.equal(isTillOnlyRoute(ok), true, ok);
  for (const no of ['/users', '/dashboard', '/accounting', '/restaurant/staff', '/salesx', '/pos-settings']) assert.equal(isTillOnlyRoute(no), false, no);
});

test('till-only flag is set by an unlock and cleared by a full sign-in', () => {
  win.sessionStorage.clear();
  assert.equal(isTillOnlyLocal(), false);
  setTillOnlyLocal(true, { pendingServer: true });
  assert.equal(isTillOnlyLocal(), true);
  assert.equal(tillOnlyPendingServer(), true);
  setTillOnlyLocal(false);
  assert.equal(isTillOnlyLocal(), false);
  assert.equal(tillOnlyPendingServer(), false);
  noteTillOnlyResponse();
  assert.equal(isTillOnlyLocal(), true);
});

test('kiosk mode is remembered per company and only for till screens', () => {
  win.localStorage.clear();
  win.localStorage.setItem('tenant', 'tenant-a');
  assert.equal(kioskHomeFor('/pos'), '/pos');
  assert.equal(kioskHomeFor('/restaurant/till'), '/restaurant/till');
  assert.equal(kioskHomeFor('/users'), null);
  assert.equal(readKiosk(), null);
  startKiosk('/pos');
  assert.equal(readKiosk()?.home, '/pos');
  win.localStorage.setItem('tenant', 'tenant-b');
  assert.equal(readKiosk(), null);
  win.localStorage.setItem('tenant', 'tenant-a');
  endKiosk();
  assert.equal(readKiosk(), null);
});

test('offline close code check uses the saved verifier and locks after five wrong codes', async () => {
  win.localStorage.clear();
  assert.equal((await checkKioskCodeOffline('11223300')).known, false);
  saveKioskVerifier(verifierFor('11223300'));
  assert.equal(kioskCodeLength(), 8);
  assert.equal(JSON.stringify(win.localStorage).includes('11223300'), false);
  assert.equal((await checkKioskCodeOffline('11223300')).ok, true);
  for (let i = 0; i < 5; i += 1) assert.equal((await checkKioskCodeOffline('00000000', 1000)).ok, false);
  const locked = await checkKioskCodeOffline('11223300', 2000);
  assert.equal(locked.ok, false);
  assert.ok((locked.waitMs || 0) > 0);
  assert.equal((await checkKioskCodeOffline('11223300', 1000 + 5 * 60 * 1000 + 1)).ok, true);
});
