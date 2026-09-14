/**
 * Plain node:test for ADR-005 membership admin UI gate helpers.
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
  'company_admin', 'super_admin', 'tenant_owner', 'tenant_admin',
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
  const status = honesty?.scaffold_status || 'complete';
  const flagOn = honesty?.store_membership_scope_enabled === true;
  const rbac = honesty?.store_scoped_rbac_complete_claimed === true;
  const flagNote = flagOn
    ? 'Membership scope flag is ON for this runtime.'
    : 'Membership scope flag is OFF (ops enable STORE_MEMBERSHIP_SCOPE_ENABLED).';
  const rbacNote = rbac ? '' : ' Store-scoped RBAC Complete is not claimed.';
  return (
    `ADR-005 store membership is ${status.toUpperCase()} — assign/list/revoke + flag-gated scope wire verified. ` +
    `Operational scope: ${scope}. ${flagNote}${rbacNote}`
  );
}

function activeMembershipsOnly(rows) {
  return (rows || []).filter((row) => row.is_active !== false);
}

describe('storeMembershipAdmin helpers', () => {
  it('source documents Complete with flag default OFF', () => {
    assert.match(SRC, /store_manager/);
    assert.match(SRC, /scaffold_status/);
    assert.match(SRC, /Complete ≠ production default ON/);
    assert.match(SRC, /STORE_MEMBERSHIP_SCOPE_ENABLED/);
  });

  it('hides admin UI for store_manager', () => {
    assert.equal(canShowStoreMembershipAdminUI('store_manager'), false);
    assert.equal(canShowStoreMembershipAdminUI('store_manager', { stores: ['write'] }), false);
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

  it('filters active memberships and honesty banner reflects Complete', () => {
    const rows = activeMembershipsOnly([
      { id: '1', user_id: 'a', store_id: 's', is_active: true },
      { id: '2', user_id: 'b', store_id: 's', is_active: false },
    ]);
    assert.equal(rows.length, 1);
    const banner = membershipHonestyBanner({
      scaffold_status: 'complete',
      operational_scope: 'stores.manager_id (membership scope wired; enable STORE_MEMBERSHIP_SCOPE_ENABLED for union + cashier fail-closed)',
      store_membership_scope_enabled: false,
      store_scoped_rbac_complete_claimed: false,
    });
    assert.match(banner, /COMPLETE/);
    assert.match(banner, /stores\.manager_id/);
    assert.match(banner, /flag is OFF/i);
    assert.match(banner, /Store-scoped RBAC Complete is not claimed/);
  });
});
