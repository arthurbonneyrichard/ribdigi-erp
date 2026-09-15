/**
 * Plain node:test for ADR-005 POS store bind helpers.
 * Run: node --test frontend/lib/posStoreBinding.test.mjs
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(__dirname, 'posStoreBinding.ts'), 'utf8');

function posStoreBindRequired(visibilityIds) {
  return visibilityIds !== null;
}

function resolvePosOpenStoreId(input) {
  const candidate = (input.pickerStoreId || input.selectedStoreId || '').trim();
  const visibility = input.storeVisibilityIds;
  if (visibility === null) {
    return { store_id: candidate || null };
  }
  if (!visibility.length) {
    return { store_id: null, blocked_reason: 'no_membership' };
  }
  if (!candidate) {
    return { store_id: null, blocked_reason: 'store_required' };
  }
  if (!visibility.includes(candidate)) {
    return { store_id: null, blocked_reason: 'store_out_of_scope' };
  }
  return { store_id: candidate };
}

function defaultPosPickerStoreId(availableStores, selectedStoreId, visibilityIds) {
  const selected = (selectedStoreId || '').trim();
  if (selected) {
    if (visibilityIds === null || visibilityIds === undefined) {
      if (availableStores.some((s) => s.id === selected)) return selected;
    } else if (visibilityIds.includes(selected)) {
      return selected;
    }
  }
  if (availableStores.length === 1) return availableStores[0].id;
  return '';
}

describe('posStoreBinding', () => {
  it('source documents Complete ≠ prod default ON', () => {
    assert.match(SRC, /Complete ≠ production default ON/);
    assert.match(SRC, /STORE_MEMBERSHIP_SCOPE_ENABLED/);
  });

  it('flag OFF / admin bypass — store optional', () => {
    assert.equal(posStoreBindRequired(null), false);
    assert.deepEqual(
      resolvePosOpenStoreId({
        selectedStoreId: '',
        pickerStoreId: '',
        storeMembershipScopeEnabled: false,
        storeVisibilityIds: null,
        availableStores: [],
      }),
      { store_id: null }
    );
  });

  it('flag ON empty visibility — fail-closed no membership', () => {
    assert.equal(posStoreBindRequired([]), true);
    const r = resolvePosOpenStoreId({
      selectedStoreId: 's1',
      pickerStoreId: 's1',
      storeMembershipScopeEnabled: true,
      storeVisibilityIds: [],
      availableStores: [],
    });
    assert.equal(r.store_id, null);
    assert.equal(r.blocked_reason, 'no_membership');
  });

  it('flag ON requires in-scope store', () => {
    const ok = resolvePosOpenStoreId({
      selectedStoreId: 's1',
      pickerStoreId: '',
      storeMembershipScopeEnabled: true,
      storeVisibilityIds: ['s1', 's2'],
      availableStores: [{ id: 's1', name: 'A' }],
    });
    assert.equal(ok.store_id, 's1');
    const missing = resolvePosOpenStoreId({
      selectedStoreId: '',
      pickerStoreId: '',
      storeMembershipScopeEnabled: true,
      storeVisibilityIds: ['s1'],
      availableStores: [{ id: 's1', name: 'A' }],
    });
    assert.equal(missing.blocked_reason, 'store_required');
    const foreign = resolvePosOpenStoreId({
      selectedStoreId: 'sx',
      pickerStoreId: '',
      storeMembershipScopeEnabled: true,
      storeVisibilityIds: ['s1'],
      availableStores: [{ id: 's1', name: 'A' }],
    });
    assert.equal(foreign.blocked_reason, 'store_out_of_scope');
  });

  it('defaults picker to sole membership or Shell selection', () => {
    assert.equal(defaultPosPickerStoreId([{ id: 'only', name: 'One' }], '', ['only']), 'only');
    assert.equal(
      defaultPosPickerStoreId([{ id: 'a', name: 'A' }, { id: 'b', name: 'B' }], 'b', ['a', 'b']),
      'b'
    );
  });
});
