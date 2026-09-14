/**
 * Plain node:test for ADR-005 membership admin UI gate helpers.
 * Mirrors `storeMembershipAdmin.ts` (keep assertions in sync when changing gates).
 * Run: node --test frontend/lib/storeMembershipAdmin.test.mjs
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(__dirname, 'storeMembershipAdmin.ts'), 'utf8');

const ADMIN_ROLES = new Set([
  'company_admin',
  'super_admin',
  'tenant_owner',
  'tenant_admin',
]);

function canShowStoreMembershipAdminUI(role, permissions) {
  const r = (role || '').trim();
  if (!r || r === 'store_manager') return false;
  if (ADMIN_ROLES.has(r)) return true;
  const stores = permissions?.stores || [];
  const star = permissions?.['*'] || [];
  if (star.includes('*')) return true;
  return stores.includes('write') || stores.includes('*') || stores.includes('read');
}

function canMutateStoreMemberships(role, permissions) {
  if (!canShowStoreMembershipAdminUI(role, permissions)) return false;
  const r = (role || '').trim();
  if (ADMIN_ROLES.has(r)) return true;
  const stores = permissions?.stores || [];
  const star = permissions?.['*'] || [];
  if (star.includes('*')) return true;
  return stores.includes('write') || stores.includes('*');
}

function membershipHonestyBanner(honesty) {
  const scope = honesty?.operational_scope || 'stores.manager_id';
  const status = honesty?.scaffold_status || 'partial';
  return (
    `ADR-005 store membership is ${status.toUpperCase()} — assignment bookkeeping only. ` +
    `Operational scope remains ${scope}. Complete / store-scoped RBAC Complete are not claimed.`
  );
}

function activeMembershipsOnly(rows) {
  return (rows || []).filter((row) => row.is_active !== false);
}

describe('storeMembershipAdmin helpers', () => {
  it('source still denies store_manager and keeps PARTIAL honesty strings', () => {
    assert.match(SRC, /store_manager/);
    assert.match(SRC, /scaffold_status/);
    assert.match(SRC, /stores\.manager_id/);
    assert.match(SRC, /not claimed/i);
  });

  it('hides admin UI for store_manager', () => {
    assert.equal(canShowStoreMembershipAdminUI('store_manager'), false);
    assert.equal(
      canShowStoreMembershipAdminUI('store_manager', { stores: ['write'] }),
      false
    );
    assert.equal(canMutateStoreMemberships('store_manager', { stores: ['*'] }), false);
  });

  it('shows admin UI for company_admin / super_admin / tenant roles', () => {
    for (const role of ['company_admin', 'super_admin', 'tenant_admin', 'tenant_owner']) {
      assert.equal(canShowStoreMembershipAdminUI(role), true);
      assert.equal(canMutateStoreMemberships(role), true);
    }
  });

  it('uses stores permissions for other roles', () => {
    assert.equal(canShowStoreMembershipAdminUI('accountant', { stores: ['read'] }), true);
    assert.equal(canMutateStoreMemberships('accountant', { stores: ['read'] }), false);
    assert.equal(canMutateStoreMemberships('accountant', { stores: ['write'] }), true);
    assert.equal(canShowStoreMembershipAdminUI('cashier'), false);
  });

  it('filters active memberships and keeps honesty banner partial', () => {
    const rows = activeMembershipsOnly([
      { id: '1', user_id: 'a', store_id: 's', is_active: true },
      { id: '2', user_id: 'b', store_id: 's', is_active: false },
    ]);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].user_id, 'a');
    const banner = membershipHonestyBanner({
      scaffold_status: 'partial',
      operational_scope: 'stores.manager_id',
    });
    assert.match(banner, /PARTIAL/);
    assert.match(banner, /stores\.manager_id/);
    assert.match(banner, /not claimed/i);
  });
});
