/**
 * IndexedDB stand-in for reload and browser restart. fake-indexeddb keeps the
 * queue for the process; these tests reopen the database the way a reloaded page would.
 */
import 'fake-indexeddb/auto';
import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { beforeEach, test } from 'node:test';
import {
  buildRecoveryPackage,
  clearOfflineOnLogout,
  enqueueOfflineSale,
  flushOfflineQueue,
  getOfflineAuthEnvelope,
  importRecoveryPackage,
  listQueueSnapshots,
  listQueuedSales,
  migrateLegacyQueueStates,
  restoreQueuedSalesFromTill,
  saveOfflineGrant,
  type ApiFn,
  type OfflineAuthEnvelope,
} from './posOffline';
import { setOutsideJournalBase } from './posOfflineJournal';

const QUEUE_DB = 'ribdigi-pos-offline';
const KEY_DB = 'ribdigi-device-crypto';

function dropDb(name: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.deleteDatabase(name);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    req.onblocked = () => resolve();
  });
}

beforeEach(async () => {
  setOutsideJournalBase(null);
  await dropDb(QUEUE_DB);
  await dropDb(KEY_DB);
});

function envelope(over: Partial<OfflineAuthEnvelope> = {}): OfflineAuthEnvelope {
  const now = new Date().toISOString();
  const until = new Date(Date.now() + 3_600_000).toISOString();
  return {
    grant_id: 'grant-1',
    tenant_id: 't1',
    store_id: 's1',
    user_id: 'u1',
    device_id: 'dev-test-0001',
    permissions: ['pos_sale'],
    issued_at: now,
    last_online_at: now,
    offline_valid_until: until,
    offline_auth_hours: 168,
    allocations: [{ product_id: 'p1', allocated_qty: 2, sold_qty: 0 }],
    allocations_refreshed_at: now,
    catalog_version: now,
    application_version: 'web',
    scope: 't1::u1::s1',
    ...over,
  };
}

function payload(qty: number) {
  return {
    session_id: 'sess-1',
    payment_method: 'cash',
    items: [{ product_id: 'p1', quantity: qty, unit_price: 10 }],
    total: qty * 10,
  };
}

async function queueSale(qty = 1) {
  return enqueueOfflineSale({
    tenant_id: 't1',
    store_id: 's1',
    store_code: 'MAIN',
    user_id: 'u1',
    payload: payload(qty),
  });
}

test('prepare, sell offline, restart, then replay syncs the same request once', async () => {
  await saveOfflineGrant(envelope());
  const queued = await queueSale();
  assert.equal(queued.state, 'pending');
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.open(QUEUE_DB, 3);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => {
      req.result.close();
      resolve();
    };
  });
  const afterRestart = await listQueuedSales();
  assert.equal(afterRestart.length, 1);
  assert.equal(afterRestart[0].client_request_id, queued.client_request_id);
  assert.equal(afterRestart[0].state, 'pending');
  const seen: string[] = [];
  const api: ApiFn = async (_path, opts) => {
    const body = JSON.parse(String(opts?.body));
    seen.push(body.client_request_id);
    return { data: { id: 'srv-restart', reference: 'POS-RESTART' } };
  };
  const first = await flushOfflineQueue(api, { tenant_id: 't1', user_id: 'u1' });
  assert.equal(first.synced, 1);
  const replay = await flushOfflineQueue(api, { tenant_id: 't1', user_id: 'u1' });
  assert.equal(replay.synced, 0);
  assert.deepEqual(seen, [queued.client_request_id]);
  const rows = await listQueuedSales();
  assert.equal(rows.length, 1);
  assert.equal(rows[0].state, 'synced');
  assert.equal(rows[0].client_request_id, queued.client_request_id);
  assert.equal(rows[0].server_sale_id, 'srv-restart');
});

test('queued sale survives a fresh database read', async () => {
  await saveOfflineGrant(envelope());
  const queued = await queueSale();
  const again = await listQueuedSales();
  assert.equal(again.length, 1);
  assert.equal(again[0].id, queued.id);
  assert.equal(again[0].client_request_id, queued.client_request_id);
  assert.equal(again[0].state, 'pending');
  assert.equal(again[0].payload.offline_encrypted, undefined);
});

test('expired authorization blocks a new sale and keeps the queue', async () => {
  await saveOfflineGrant(envelope());
  const kept = await queueSale();
  await saveOfflineGrant(
    envelope({ offline_valid_until: new Date(Date.now() - 60_000).toISOString() })
  );
  await assert.rejects(() => queueSale(), /expired/);
  const rows = await listQueuedSales();
  assert.equal(rows.length, 1);
  assert.equal(rows[0].id, kept.id);
  assert.equal(rows[0].state, 'pending');
});

test('an expired grant still syncs a queued sale', async () => {
  await saveOfflineGrant(envelope());
  const queued = await queueSale();
  await saveOfflineGrant(
    envelope({ offline_valid_until: new Date(Date.now() - 60_000).toISOString() })
  );
  const seen: string[] = [];
  const api: ApiFn = async (_path, opts) => {
    const body = JSON.parse(String(opts?.body));
    seen.push(body.client_request_id);
    return { data: { id: 'srv-1', reference: 'POS-1' } };
  };
  const result = await flushOfflineQueue(api, { tenant_id: 't1', user_id: 'u1' });
  assert.equal(result.synced, 1);
  assert.deepEqual(seen, [queued.client_request_id]);
  const row = (await listQueuedSales())[0];
  assert.equal(row.state, 'synced');
  assert.equal(row.server_reference, 'POS-1');
});

test('a legacy expired queue row is pending again and can sync', async () => {
  await listQueuedSales();
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.open(QUEUE_DB, 3);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => {
      const db = req.result;
      const tx = db.transaction('sync_queue', 'readwrite');
      tx.objectStore('sync_queue').put({
        id: 'legacy-1',
        kind: 'sale',
        scope: 't1::u1::s1',
        client_request_id: 'cr-legacy',
        local_receipt_number: 'OFF-LEGACY',
        tenant_id: 't1',
        store_id: 's1',
        user_id: 'u1',
        device_id: 'dev-test-0001',
        grant_id: 'grant-old',
        payload: payload(1),
        state: 'expired',
        retry_count: 0,
        last_attempt_at: null,
        next_retry_at: null,
        last_error_code: 'OFFLINE_AUTH_EXPIRED',
        last_error_message: 'expired',
        created_at: new Date().toISOString(),
        server_sale_id: null,
        server_reference: null,
      });
      tx.oncomplete = () => {
        db.close();
        resolve();
      };
      tx.onerror = () => reject(tx.error);
    };
  });
  const changed = await migrateLegacyQueueStates();
  assert.equal(changed, 1);
  assert.equal((await listQueuedSales())[0].state, 'pending');
  const api: ApiFn = async () => ({ data: { id: 'srv-legacy', reference: 'POS-L' } });
  const result = await flushOfflineQueue(api, { tenant_id: 't1', user_id: 'u1' });
  assert.equal(result.synced, 1);
});

test('a 401 keeps the sale pending and a later retry reuses the request id', async () => {
  await saveOfflineGrant(envelope());
  const queued = await queueSale();
  let attempt = 0;
  const ids: string[] = [];
  const api: ApiFn = async (_path, opts) => {
    attempt += 1;
    const body = JSON.parse(String(opts?.body));
    ids.push(body.client_request_id);
    if (attempt === 1) {
      const err = new Error('sign in') as Error & { status?: number };
      err.status = 401;
      throw err;
    }
    if (attempt === 2) {
      const err = new Error('unavailable') as Error & { status?: number; detail?: unknown };
      err.status = 503;
      err.detail = { message: 'unavailable' };
      throw err;
    }
    return { data: { id: 'srv-2', reference: 'POS-2' } };
  };
  const first = await flushOfflineQueue(api, { tenant_id: 't1', user_id: 'u1' });
  assert.equal(first.authRequired, true);
  assert.equal((await listQueuedSales())[0].state, 'pending');
  const second = await flushOfflineQueue(api, { tenant_id: 't1', user_id: 'u1', force: true });
  assert.equal(second.retrying, 1);
  assert.equal((await listQueuedSales())[0].state, 'pending');
  const third = await flushOfflineQueue(api, { tenant_id: 't1', user_id: 'u1', force: true });
  assert.equal(third.synced, 1);
  assert.equal((await listQueuedSales())[0].state, 'synced');
  assert.deepEqual(ids, [queued.client_request_id, queued.client_request_id, queued.client_request_id]);
});

test('a server miss is sent again without a cashier, and a price conflict is not', async () => {
  await saveOfflineGrant(envelope());
  const queued = await queueSale();
  let attempt = 0;
  const api: ApiFn = async () => {
    attempt += 1;
    if (attempt === 1) {
      const err = new Error('unavailable') as Error & { status?: number; detail?: unknown };
      err.status = 503;
      err.detail = { message: 'unavailable' };
      throw err;
    }
    if (attempt === 2) {
      const err = new Error('price') as Error & { status?: number; detail?: unknown };
      err.status = 409;
      err.detail = { code: 'PRICE_CHANGED', message: 'Price changed', sync_event_id: 'evt-1' };
      throw err;
    }
    return { data: { id: 'srv-3', reference: 'POS-3' } };
  };
  const missed = await flushOfflineQueue(api, { tenant_id: 't1', user_id: 'u1' });
  assert.equal(missed.retrying, 1);
  assert.equal(missed.needsAttention, 0);
  const waiting = (await listQueuedSales())[0];
  assert.equal(waiting.state, 'pending');
  waiting.retry_count = 8;
  waiting.next_retry_at = new Date(Date.now() - 1000).toISOString();
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.open(QUEUE_DB, 3);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => {
      const db = req.result;
      const tx = db.transaction('sync_queue', 'readwrite');
      tx.objectStore('sync_queue').put(waiting);
      tx.oncomplete = () => {
        db.close();
        resolve();
      };
      tx.onerror = () => reject(tx.error);
    };
  });
  const conflict = await flushOfflineQueue(api, { tenant_id: 't1', user_id: 'u1' });
  assert.equal(conflict.needsAttention, 1);
  assert.equal((await listQueuedSales())[0].state, 'needs_attention');
  const held = await flushOfflineQueue(api, { tenant_id: 't1', user_id: 'u1' });
  assert.equal(held.synced, 0);
  assert.equal(held.needsAttention, 0);
  assert.equal((await listQueuedSales())[0].id, queued.id);
  assert.equal((await listQueuedSales())[0].state, 'needs_attention');
});

test('a sale cannot exceed this device allocation', async () => {
  await saveOfflineGrant(envelope());
  await assert.rejects(() => queueSale(3), /allocation/);
  const first = await queueSale(2);
  await assert.rejects(() => queueSale(1), /allocation/);
  const rows = await listQueuedSales();
  assert.equal(rows.length, 1);
  assert.equal(rows[0].id, first.id);
});

test('sign-out keeps the queue and drops the grant', async () => {
  await saveOfflineGrant(envelope());
  const queued = await queueSale();
  await clearOfflineOnLogout();
  assert.equal(await getOfflineAuthEnvelope(), null);
  const rows = await listQueuedSales();
  assert.equal(rows.length, 1);
  assert.equal(rows[0].client_request_id, queued.client_request_id);
});

test('backup import merges missing records and does not replace the queue', async () => {
  await saveOfflineGrant(envelope({ allocations: [{ product_id: 'p1', allocated_qty: 5, sold_qty: 0 }] }));
  const first = await queueSale(1);
  const second = await queueSale(1);
  const pkg = await buildRecoveryPackage('correct horse battery');
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.open(QUEUE_DB, 3);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => {
      const db = req.result;
      const tx = db.transaction('sync_queue', 'readwrite');
      tx.objectStore('sync_queue').delete(second.id);
      tx.oncomplete = () => {
        db.close();
        resolve();
      };
      tx.onerror = () => reject(tx.error);
    };
  });
  const imported = await importRecoveryPackage(pkg, {
    tenant_id: 't1',
    passphrase: 'correct horse battery',
  });
  assert.equal(imported.imported, 1);
  assert.equal(imported.skipped, 1);
  assert.ok(imported.safety_copy_id);
  const rows = await listQueuedSales();
  assert.equal(rows.length, 2);
  assert.ok(rows.some((row) => row.client_request_id === first.client_request_id));
  assert.ok(rows.some((row) => row.client_request_id === second.client_request_id));
  const snaps = await listQueueSnapshots();
  assert.ok(snaps.some((snap) => snap.id === imported.safety_copy_id));
  await assert.rejects(
    () => importRecoveryPackage(pkg, { tenant_id: 'other-tenant', passphrase: 'correct horse battery' }),
    /another workspace/
  );
});

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      const port = typeof address === 'object' && address ? address.port : 0;
      server.close(() => resolve(port));
    });
  });
}

function pythonExe(): string {
  const preferred =
    process.env.RIBDIGI_PYTHON ||
    'C:\\Users\\arthu\\AppData\\Local\\Programs\\Python\\Python312\\python.exe';
  return fs.existsSync(preferred) ? preferred : 'python';
}

async function waitForJournal(port: number, proc: ChildProcess, log: () => string): Promise<void> {
  const deadline = Date.now() + 8000;
  while (Date.now() < deadline) {
    if (proc.exitCode != null) {
      throw new Error(`till journal exited ${proc.exitCode}: ${log()}`);
    }
    try {
      const response = await fetch(`http://127.0.0.1:${port}/v1/offline-sales`);
      if (response.status === 422 || response.ok) return;
    } catch {
      /* listener not up yet */
    }
    await new Promise((resolve) => setTimeout(resolve, 40));
  }
  throw new Error(`till journal did not start: ${log()}`);
}

test('queued sale is read back from the till journal after IndexedDB is cleared', async () => {
  const repoRoot = path.resolve(process.env.RIBDIGI_FRONTEND_ROOT || path.resolve(__dirname, '..'), '..');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ribdigi-till-journal-'));
  const journalFile = path.join(dir, 'pos-offline-journal.json');
  const port = await freePort();
  let log = '';
  const proc = spawn(pythonExe(), [path.join(repoRoot, 'ops', 'print-agent', 'agent.py'), 'journal'], {
    cwd: path.join(repoRoot, 'ops', 'print-agent'),
    env: {
      ...process.env,
      RIBDIGI_OFFLINE_JOURNAL: journalFile,
      RIBDIGI_OFFLINE_PORT: String(port),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  proc.stdout?.on('data', (chunk) => {
    log += String(chunk);
  });
  proc.stderr?.on('data', (chunk) => {
    log += String(chunk);
  });
  try {
    await waitForJournal(port, proc, () => log);
    setOutsideJournalBase(`http://127.0.0.1:${port}`);
    await saveOfflineGrant(envelope());
    const queued = await queueSale();
    const savedTotal = queued.payload.total;
    const savedPrice = (queued.payload.items as Array<{ unit_price: number }>)[0].unit_price;
    await dropDb(QUEUE_DB);
    await dropDb(KEY_DB);
    const wrongCompany = await restoreQueuedSalesFromTill('other-company', 'u1');
    assert.equal(wrongCompany, 0);
    assert.equal((await listQueuedSales()).length, 0);
    const imported = await restoreQueuedSalesFromTill('t1', 'u1');
    assert.equal(imported, 1);
    const rows = await listQueuedSales();
    assert.equal(rows.length, 1);
    assert.equal(rows[0].client_request_id, queued.client_request_id);
    assert.equal(rows[0].state, 'pending');
    assert.equal(rows[0].server_sale_id, null);
    assert.equal(rows[0].payload.total, savedTotal);
    assert.equal((rows[0].payload.items as Array<{ unit_price: number }>)[0].unit_price, savedPrice);
    const outside = fs.readFileSync(journalFile, 'utf8');
    assert.ok(outside.includes(queued.client_request_id));
    assert.equal(outside.includes('password'), false);
  } finally {
    setOutsideJournalBase(null);
    proc.kill();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
