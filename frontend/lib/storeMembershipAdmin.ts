/**
 * ADR-005 store membership admin helpers (Complete — flag default OFF).
 * Default operational scope is stores.manager_id until ops enables
 * STORE_MEMBERSHIP_SCOPE_ENABLED. Complete = feature + automated soak;
 * Complete ≠ production default ON. Store-scoped RBAC Complete remains unclaimed.
 */

export type StoreMembershipRow = {
  id: string;
  user_id: string;
  store_id: string;
  is_active: boolean;
  user_email?: string | null;
  user_full_name?: string | null;
  user_role?: string | null;
  store_code?: string | null;
  store_name?: string | null;
  adr005_complete_claimed?: boolean;
  scope_wired_to_membership?: boolean;
  scaffold_status?: string;
  operational_scope?: string;
};

export type MembershipHonesty = {
  adr005_complete_claimed: boolean;
  store_scoped_rbac_complete_claimed: boolean;
  scope_wired_to_membership: boolean;
  store_membership_scope_enabled: boolean;
  cashier_membership_fail_closed?: boolean;
  scaffold_status: string;
  operational_scope: string;
  complete_means?: string;
};

/** Roles that may see company-level store membership mutation UI. */
const ADMIN_ROLES = new Set([
  'company_admin',
  'super_admin',
  'tenant_owner',
  'tenant_admin',
]);

/**
 * Client-side gate mirroring API denial for store_manager.
 * Final authority is the API (`assert_store_membership_admin_denied`).
 */
export function canShowStoreMembershipAdminUI(
  role: string | undefined | null,
  permissions?: Record<string, string[]> | null
): boolean {
  const r = (role || '').trim();
  if (!r || r === 'store_manager') return false;
  if (ADMIN_ROLES.has(r)) return true;
  const stores = permissions?.stores || [];
  const star = permissions?.['*'] || [];
  if (star.includes('*')) return true;
  return stores.includes('write') || stores.includes('*') || stores.includes('read');
}

/** Prefer mutation controls only when writes are plausible. */
export function canMutateStoreMemberships(
  role: string | undefined | null,
  permissions?: Record<string, string[]> | null
): boolean {
  if (!canShowStoreMembershipAdminUI(role, permissions)) return false;
  const r = (role || '').trim();
  if (ADMIN_ROLES.has(r)) return true;
  const stores = permissions?.stores || [];
  const star = permissions?.['*'] || [];
  if (star.includes('*')) return true;
  return stores.includes('write') || stores.includes('*');
}

export function membershipHonestyBanner(honesty?: Partial<MembershipHonesty> | null): string {
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

export function activeMembershipsOnly(rows: StoreMembershipRow[]): StoreMembershipRow[] {
  return (rows || []).filter((row) => row.is_active !== false);
}
