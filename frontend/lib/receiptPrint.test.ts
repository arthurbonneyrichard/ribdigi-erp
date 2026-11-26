import assert from 'node:assert/strict';
import test from 'node:test';
import { offlineReceiptText, receiptPhase } from './receiptPrint';

const job = (status: string, extra = {}) => ({ id: status, status, printer_name: 'Till', ...extra });

test('success is shown only when every direct printer reports printed', () => {
  assert.equal(receiptPhase([job('queued')], 0).phase, 'printing');
  assert.equal(receiptPhase([job('claimed')], 0).phase, 'printing');
  assert.equal(receiptPhase([job('printed'), job('queued')], 0).phase, 'printing');
  assert.equal(receiptPhase([job('printed'), job('failed')], 0).phase, 'failed');
  assert.equal(receiptPhase([job('printed')], 0).phase, 'printed');
});

test('no printer, dialog-only printer, sleeping agent and a silent printer are unavailable', () => {
  assert.equal(receiptPhase([], 0).phase, 'unavailable');
  assert.equal(receiptPhase([job('browser_pending')], 0).phase, 'unavailable');
  const asleep = job('queued', { agent_online: false });
  assert.equal(receiptPhase([asleep], 1_000).phase, 'printing');
  assert.equal(receiptPhase([asleep], 5_000).phase, 'unavailable');
  assert.equal(receiptPhase([job('claimed')], 30_000).phase, 'unavailable');
});

test('offline slip says it is not final and fits the roll', () => {
  const text = offlineReceiptText({
    company_name: 'Demo Mart',
    reference: 'OFF-1',
    currency: 'GHS',
    items: [{ name: 'A very long product name that will not fit', quantity: 2, line_total: 1234.5 }],
    total: 1234.5,
    payments: [{ payment_method: 'mobile_money', amount: 1234.5 }],
    cash_tendered: null,
  });
  assert.ok(text.includes('Not the final receipt.'));
  assert.ok(text.includes('1234.50'));
  assert.ok(text.split('\n').every((line) => line.length <= 32), text);
});
