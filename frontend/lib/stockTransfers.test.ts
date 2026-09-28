import assert from 'node:assert/strict';
import test from 'node:test';
import {
  matchesTransferSearch,
  sameWarehouseError,
  transferLineQtyError,
  transferOnDate,
  transferProductCount,
  transferQtyTotal,
  warehouseQtyMap,
} from './stockTransfers.ts';

test('transfer counts fall back to items', () => {
  const row = {
    id: '1',
    items: [
      { product_id: 'a', quantity: 2 },
      { product_id: 'b', quantity: 3 },
    ],
  };
  assert.equal(transferProductCount(row), 2);
  assert.equal(transferQtyTotal(row), 5);
});

test('search matches warehouse labels', () => {
  assert.equal(
    matchesTransferSearch({ id: '1', transfer_number: 'ST-9' }, 'st-9', { from: 'A', to: 'B' }),
    true,
  );
  assert.equal(
    matchesTransferSearch({ id: '1', transfer_number: 'ST-9' }, 'north', {
      from: 'North Zone',
      to: 'B',
    }),
    true,
  );
  assert.equal(
    matchesTransferSearch({ id: '1', transfer_number: 'ST-9' }, 'zzz', { from: 'A', to: 'B' }),
    false,
  );
});

test('date filter uses created_at day', () => {
  const row = { created_at: '2026-09-15T12:00:00Z' };
  assert.equal(transferOnDate(row, '2026-09-01', '2026-09-30'), true);
  assert.equal(transferOnDate(row, '2026-09-16', ''), false);
  assert.equal(transferOnDate(row, '', '2026-09-14'), false);
  assert.equal(transferOnDate({}, '2026-09-01', ''), false);
});

test('qty cannot exceed available; same warehouse blocked', () => {
  assert.equal(transferLineQtyError(0, 10), 'Each product line needs a positive quantity');
  assert.equal(transferLineQtyError(12, 10), 'Quantity exceeds available stock (10)');
  assert.equal(transferLineQtyError(4, 10), null);
  assert.equal(sameWarehouseError('wh-a', 'wh-a'), 'Source and destination must be different');
  assert.equal(sameWarehouseError('wh-a', 'wh-b'), null);
  assert.deepEqual(warehouseQtyMap([{ product_id: 'p1', quantity: 7 }]), { p1: 7 });
});
