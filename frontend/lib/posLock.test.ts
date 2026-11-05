import assert from 'node:assert/strict';
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

import {
  checkOfflinePasscode,
  getOperatorToken,
  holdOperatorToken,
  isTillLocked,
  isTillPath,
  offlineVerifierFor,
  parkForOwner,
  readTillSale,
  resumeHeldToken,
  saveCurrentSale,
  saveOfflineVerifier,
  setOperatorToken,
  takeParked,
  tillOperatorToken,
  wasLeftLocked,
  type TillSnapshot,
} from './posLock';

const sale = (owner: string, at = Date.now()): TillSnapshot => ({
  owner_id: owner,
  owner_name: owner.toUpperCase(),
  at,
  item_count: 2,
  total: 40,
  data: { cart: ['a', 'b'] },
});

test.beforeEach(() => {
  win.localStorage.clear();
  win.sessionStorage.clear();
  win.location.pathname = '/pos';
});

test('the cashier token is sent from till screens and nowhere else', () => {
  setOperatorToken('tok');
  assert.equal(tillOperatorToken(), 'tok');
  win.location.pathname = '/restaurant/till';
  assert.equal(tillOperatorToken(), 'tok');
  win.location.pathname = '/users';
  assert.equal(tillOperatorToken(), null);
  assert.equal(isTillPath('/restaurant/menu'), false);
});

test('locking stops sending the token and survives a refresh', () => {
  setOperatorToken('tok');
  holdOperatorToken();
  assert.equal(getOperatorToken(), null);
  assert.equal(isTillLocked(), true);
  assert.equal(wasLeftLocked(), true);
  resumeHeldToken();
  assert.equal(getOperatorToken(), 'tok');
  assert.equal(isTillLocked(), false);
  assert.equal(wasLeftLocked(), false);
});

test('a sale outlasts a refresh and a parked sale goes back only to its owner', () => {
  saveCurrentSale('retail', 't1', sale('ama'));
  assert.equal(readTillSale('retail', 't1').current?.owner_id, 'ama');
  parkForOwner('retail', 't1', sale('ama'));
  assert.equal(readTillSale('retail', 't1').current, null);
  assert.equal(takeParked('retail', 't1', 'kofi'), null);
  assert.equal(takeParked('retail', 't1', 'ama')?.owner_id, 'ama');
  assert.equal(takeParked('retail', 't1', 'ama'), null);
});

test('each company and each desk keeps its own sale', () => {
  saveCurrentSale('retail', 't1', sale('ama'));
  assert.equal(readTillSale('retail', 't2').current, null);
  assert.equal(readTillSale('restaurant', 't1').current, null);
});

test('a sale left overnight is not brought back', () => {
  saveCurrentSale('retail', 't1', sale('ama', Date.now() - 25 * 60 * 60 * 1000));
  assert.equal(readTillSale('retail', 't1').current, null);
});

test('offline unlock accepts only the last cashier, then locks out after wrong tries', async () => {
  await saveOfflineVerifier('t1', { id: 'ama', name: 'Ama' }, '482915');
  assert.equal(offlineVerifierFor('t1')?.id, 'ama');
  assert.equal(offlineVerifierFor('t2'), null);
  assert.equal((await checkOfflinePasscode('t1', '482915')).ok, true);
  assert.equal((await checkOfflinePasscode('t2', '482915')).ok, false);
  for (let tries = 4; tries >= 1; tries -= 1) {
    assert.equal((await checkOfflinePasscode('t1', '000111')).triesLeft, tries);
  }
  const locked = await checkOfflinePasscode('t1', '000111');
  assert.ok((locked.waitMs || 0) > 0);
  assert.equal((await checkOfflinePasscode('t1', '482915')).ok, false);
});

test('the passcode is not kept in the browser', async () => {
  await saveOfflineVerifier('t1', { id: 'ama', name: 'Ama' }, '482915');
  assert.equal(String(win.localStorage.getItem('ribdigi:pos:offline-verifier')).includes('482915'), false);
});
