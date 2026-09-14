'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../lib/api';
import {
  activeMembershipsOnly,
  canMutateStoreMemberships,
  canShowStoreMembershipAdminUI,
  membershipHonestyBanner,
  type MembershipHonesty,
  type StoreMembershipRow,
} from '../lib/storeMembershipAdmin';

type StoreOption = { id: string; code?: string; name: string };
type UserOption = {
  id: string;
  full_name?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
};

type Props = {
  stores: StoreOption[];
  users: UserOption[];
  meRole?: string | null;
  mePermissions?: Record<string, string[]> | null;
  initialStoreId?: string;
};

/**
 * Company/Admin UI for ADR-005 user↔store memberships (Complete; flag default OFF).
 * Hidden when the role is store_manager or the membership admin API returns 403.
 */
export default function StoreMembershipAdmin({
  stores,
  users,
  meRole,
  mePermissions,
  initialStoreId,
}: Props) {
  const showGate = canShowStoreMembershipAdminUI(meRole, mePermissions);
  const canMutate = canMutateStoreMemberships(meRole, mePermissions);

  const [storeId, setStoreId] = useState(initialStoreId || '');
  const [memberships, setMemberships] = useState<StoreMembershipRow[]>([]);
  const [honesty, setHonesty] = useState<Partial<MembershipHonesty> | null>(null);
  const [userId, setUserId] = useState('');
  const [expiresAtLocal, setExpiresAtLocal] = useState('');
  const [denied, setDenied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!storeId && stores.length) {
      setStoreId(initialStoreId && stores.some((s) => s.id === initialStoreId)
        ? initialStoreId
        : stores[0].id);
    }
  }, [stores, storeId, initialStoreId]);

  const load = useCallback(async (sid: string) => {
    if (!sid || !showGate) return;
    setError('');
    setMessage('');
    try {
      const res = await api<{
        data: {
          memberships?: StoreMembershipRow[];
        } & Partial<MembershipHonesty>;
      }>(`/stores/${sid}/memberships?active_only=true`);
      setDenied(false);
      const data = res.data || ({} as any);
      setMemberships(activeMembershipsOnly(data.memberships || []));
      setHonesty({
        adr005_complete_claimed: data.adr005_complete_claimed,
        store_scoped_rbac_complete_claimed: data.store_scoped_rbac_complete_claimed,
        scope_wired_to_membership: data.scope_wired_to_membership,
        store_membership_scope_enabled: data.store_membership_scope_enabled,
        temp_membership_expires_at_claimed: data.temp_membership_expires_at_claimed,
        elevation_break_glass_claimed: data.elevation_break_glass_claimed,
        scaffold_status: data.scaffold_status,
        operational_scope: data.operational_scope,
      });
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 403) {
        setDenied(true);
        setMemberships([]);
        setHonesty(null);
        return;
      }
      setError(err instanceof Error ? err.message : 'Failed to load store memberships');
    }
  }, [showGate]);

  useEffect(() => {
    if (storeId && showGate && !denied) {
      void load(storeId);
    }
  }, [storeId, showGate, denied, load]);

  if (!showGate || denied) {
    return null;
  }

  const assignedIds = new Set(memberships.map((m) => m.user_id));
  const assignableUsers = users.filter(
    (u) =>
      u.is_active !== false &&
      !assignedIds.has(u.id) &&
      (u.role || '') !== 'store_manager'
  );

  async function assignMember() {
    if (!storeId || !userId || !canMutate) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const body: { user_id: string; expires_at?: string | null } = { user_id: userId };
      if (expiresAtLocal.trim()) {
        // datetime-local is local wall time; send as ISO without forcing TZ shift issues
        const asDate = new Date(expiresAtLocal);
        if (Number.isNaN(asDate.getTime())) {
          setError('Invalid expires_at datetime');
          setBusy(false);
          return;
        }
        body.expires_at = asDate.toISOString();
      } else {
        body.expires_at = null;
      }
      await api(`/stores/${storeId}/memberships`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setUserId('');
      setExpiresAtLocal('');
      setMessage(
        'Store membership assigned (ADR-005 Complete — enable STORE_MEMBERSHIP_SCOPE_ENABLED for runtime scope; expires_at enforced when set)'
      );
      await load(storeId);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 403) {
        setDenied(true);
        setError('Membership admin denied for this role');
      } else {
        setError(err instanceof Error ? err.message : 'Assign failed');
      }
    } finally {
      setBusy(false);
    }
  }

  async function revokeMember(memberUserId: string) {
    if (!storeId || !canMutate) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api(`/stores/${storeId}/memberships/${memberUserId}`, { method: 'DELETE' });
      setMessage('Store membership revoked (ADR-005 Complete — rows retained; flag controls runtime scope)');
      await load(storeId);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 403) {
        setDenied(true);
        setError('Membership admin denied for this role');
      } else {
        setError(err instanceof Error ? err.message : 'Revoke failed');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" id="memberships" style={{ marginBottom: 16 }}>
      <h3>Store memberships (ADR-005)</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        {membershipHonestyBanner(honesty)}
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'grid', gap: 8, maxWidth: 560 }}>
        <label className="muted">
          Store
          <select
            value={storeId}
            onChange={(e) => setStoreId(e.target.value)}
            aria-label="Store for memberships"
            style={{ display: 'block', width: '100%', marginTop: 4 }}
          >
            {!stores.length && <option value="">No stores</option>}
            {stores.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code ? `${s.code} — ${s.name}` : s.name}
              </option>
            ))}
          </select>
        </label>

        {canMutate ? (
          <div style={{ display: 'grid', gap: 8 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <select
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                aria-label="User to assign to store"
                style={{ flex: 1, minWidth: 200 }}
              >
                <option value="">Select user (cashier / officer…)</option>
                {assignableUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {(u.full_name || u.email || u.id) + (u.role ? ` · ${u.role}` : '')}
                  </option>
                ))}
              </select>
              <button type="button" onClick={() => void assignMember()} disabled={busy || !userId || !storeId}>
                Assign
              </button>
            </div>
            <label className="muted">
              Expires at (optional — leave blank for permanent)
              <input
                type="datetime-local"
                value={expiresAtLocal}
                onChange={(e) => setExpiresAtLocal(e.target.value)}
                aria-label="Membership expires at"
                style={{ display: 'block', width: '100%', maxWidth: 280, marginTop: 4 }}
              />
            </label>
          </div>
        ) : (
          <p className="muted">Read-only — stores write permission required to assign or revoke.</p>
        )}

        <div>
          <strong>Active members</strong>
          {!memberships.length ? (
            <p className="muted">No active memberships for this store.</p>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0 0' }}>
              {memberships.map((row) => (
                <li
                  key={row.id || `${row.user_id}-${row.store_id}`}
                  style={{
                    display: 'flex',
                    gap: 8,
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 0',
                    borderBottom: '1px solid #e5e7eb',
                  }}
                >
                  <span>
                    {row.user_full_name || row.user_email || row.user_id}
                    {row.user_role ? (
                      <span className="muted">{` · ${row.user_role}`}</span>
                    ) : null}
                    {row.user_email && row.user_full_name ? (
                      <span className="muted">{` · ${row.user_email}`}</span>
                    ) : null}
                    {row.expires_at ? (
                      <span className="muted">
                        {row.is_expired
                          ? ` · expired ${row.expires_at}`
                          : ` · expires ${row.expires_at}`}
                      </span>
                    ) : (
                      <span className="muted"> · permanent</span>
                    )}
                  </span>
                  {canMutate ? (
                    <button
                      type="button"
                      onClick={() => void revokeMember(row.user_id)}
                      disabled={busy}
                    >
                      Remove
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
