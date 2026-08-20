'use client';

import { useStoreContext } from '../lib/storeContext';

/** Header store context switcher (BR-13 / Phase 4 multi-store UX). */
export default function StoreSwitcher({ visible }: { visible: boolean }) {
  const { stores, storeId, setStoreId, loading } = useStoreContext();

  if (!visible || stores.length === 0) return null;

  return (
    <label
      className="store-switcher"
      title="Active store context for POS, sales, reports, and expenses"
    >
      <span className="store-switcher-label muted">Store</span>
      <select
        aria-label="Active store"
        data-testid="store-context-switcher"
        className="store-switcher-select"
        value={storeId}
        disabled={loading}
        onChange={(e) => setStoreId(e.target.value)}
      >
        {stores.length > 1 ? <option value="">All stores</option> : null}
        {stores.map((s) => (
          <option key={s.id} value={s.id}>
            {s.code ? `${s.code} — ` : ''}
            {s.name || s.id.slice(0, 8)}
          </option>
        ))}
      </select>
    </label>
  );
}
