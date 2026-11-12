import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  applySyncResults,
  enqueueSale,
  isLinkDown,
  newOfflineRef,
  offlineBill,
  offlineLabel,
  pendingSales,
  readQueue,
  syncBody,
  type OfflineSale,
} from './restaurantOffline';

function memory() {
  const map = new Map<string, string>();
  return {
    getItem: (k: string) => (map.has(k) ? map.get(k)! : null),
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
  };
}

function sale(ref: string): OfflineSale {
  return {
    offline_ref: ref,
    created_at: '2026-11-12T10:00:00.000Z',
    service_mode: 'takeaway',
    payment_method: 'cash',
    store_id: null,
    table_id: null,
    shift_id: 'shift-1',
    customer_name: null,
    delivery_address: null,
    charged_total: 80,
    lines: [{ product_id: 'p1', quantity: 2, modifier_ids: [], name: 'Jollof', amount: 80 }],
  };
}

test('offline refs match the server pattern and are unique', () => {
  const a = newOfflineRef(1, 'aaaa1111');
  assert.match(a, /^[A-Za-z0-9_-]{8,64}$/);
  assert.notEqual(newOfflineRef(), newOfflineRef());
  assert.equal(offlineLabel('rt-x-abcd1234'), 'OFF-1234');
});

test('queue keeps one row per ref, per tenant', () => {
  const store = memory();
  enqueueSale(sale('ref-00000001'), store, 't1');
  enqueueSale(sale('ref-00000001'), store, 't1');
  enqueueSale(sale('ref-00000002'), store, 't2');
  assert.equal(readQueue(store, 't1').length, 1);
  assert.equal(readQueue(store, 't2').length, 1);
});

test('sync body leaves device-only names and prices behind', () => {
  const body = syncBody([sale('ref-00000001')], 'till-01');
  assert.equal(body.device_id, 'till-01');
  const line = body.sales[0].lines[0] as Record<string, unknown>;
  assert.equal('name' in line, false);
  assert.equal('unit_price' in line, false);
  assert.equal('amount' in line, false);
});

test('booked sales leave the queue, refusals stay with a reason', () => {
  const rows = [sale('a-00000001'), sale('b-00000002'), sale('c-00000003')];
  const out = applySyncResults(rows, [
    { offline_ref: 'a-00000001', status: 'booked' },
    { offline_ref: 'b-00000002', status: 'refused', reason: 'Too old' },
  ]);
  assert.deepEqual(out.map((r) => r.offline_ref), ['b-00000002', 'c-00000003']);
  assert.equal(out[0].refused_reason, 'Too old');
  assert.deepEqual(pendingSales(out).map((r) => r.offline_ref), ['c-00000003']);
});

test('only a missing status counts as the link being down', () => {
  assert.equal(isLinkDown({ status: 422 }), false);
  assert.equal(isLinkDown({ status: 409 }), false);
  assert.equal(isLinkDown(new Error('fetch failed')), true);
});

test('offline bill adds dish tax, service and tax on service like the server', () => {
  const bill = offlineBill([{ product_id: 'p1', amount: 100 }, { product_id: 'p2', amount: 50 }], {
    service_percent: 10,
    service_tax_percent: 20,
    items: { p1: { price: 50, added_tax_percent: 20 }, p2: { price: 50, added_tax_percent: 0 } },
  });
  assert.deepEqual(bill, { subtotal: 150, tax: 23, service: 15, total: 188 });
  assert.equal(offlineBill([{ product_id: 'p1', amount: 40 }], null).total, 40);
});
