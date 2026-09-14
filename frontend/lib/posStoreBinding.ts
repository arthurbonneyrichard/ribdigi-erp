/**
 * ADR-005 POS store bind helpers.
 * When STORE_MEMBERSHIP_SCOPE_ENABLED is on, cashiers/store_managers must open
 * shifts against a visible store (membership ∪ manager_id). Flag default OFF
 * keeps legacy optional store_id. Complete ≠ production default ON.
 */

export type PosStoreOption = {
  id: string;
  code?: string | null;
  name: string;
};

export type PosStoreBindInput = {
  selectedStoreId?: string | null;
  pickerStoreId?: string | null;
  storeMembershipScopeEnabled: boolean;
  storeVisibilityIds: string[] | null;
  availableStores: PosStoreOption[];
};

export type PosStoreBindResult = {
  store_id: string | null;
  blocked_reason?: 'no_membership' | 'store_required' | 'store_out_of_scope';
};

export function posStoreBindRequired(visibilityIds: string[] | null): boolean {
  return visibilityIds !== null;
}

export function resolvePosOpenStoreId(input: PosStoreBindInput): PosStoreBindResult {
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

export function defaultPosPickerStoreId(
  availableStores: PosStoreOption[],
  selectedStoreId?: string | null,
  visibilityIds?: string[] | null
): string {
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

export function posStoreBindBlockedMessage(reason?: PosStoreBindResult['blocked_reason']): string {
  switch (reason) {
    case 'no_membership':
      return 'No store membership assigned — ask a company admin to assign you at /stores#memberships before opening a shift.';
    case 'store_out_of_scope':
      return 'Selected store is outside your membership / managed store scope.';
    case 'store_required':
      return 'Select a store before opening a shift (membership scope is enabled).';
    default:
      return 'Cannot open shift for the selected store.';
  }
}

export function membershipRowsToStoreOptions(
  rows: Array<{
    store_id: string;
    store_code?: string | null;
    store_name?: string | null;
    is_active?: boolean;
  }>
): PosStoreOption[] {
  return (rows || [])
    .filter((r) => r.is_active !== false && r.store_id)
    .map((r) => ({
      id: r.store_id,
      code: r.store_code || null,
      name: r.store_name || r.store_code || r.store_id,
    }));
}
