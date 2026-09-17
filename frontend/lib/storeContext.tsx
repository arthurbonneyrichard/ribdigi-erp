'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api } from './api';

export type StoreOption = {
  id: string;
  code?: string;
  name?: string;
  is_active?: boolean;
};

type StoreContextValue = {
  stores: StoreOption[];
  storeId: string;
  setStoreId: (id: string) => void;
  activeStore: StoreOption | null;
  loading: boolean;
  refreshStores: () => Promise<void>;
};

const StoreContext = createContext<StoreContextValue | null>(null);

function storageKey(tenantId: string | null) {
  return tenantId ? `ribdigi.activeStoreId.${tenantId}` : 'ribdigi.activeStoreId';
}

export function StoreProvider({
  children,
  enabled = true,
}: {
  children: ReactNode;
  enabled?: boolean;
}) {
  const [stores, setStores] = useState<StoreOption[]>([]);
  const [storeId, setStoreIdState] = useState('');
  const [loading, setLoading] = useState(false);
  const [tenantId, setTenantId] = useState<string | null>(null);

  const refreshStores = useCallback(async () => {
    if (!enabled) {
      setStores([]);
      setStoreIdState('');
      return;
    }
    setLoading(true);
    try {
      const tid =
        typeof window !== 'undefined' ? localStorage.getItem('tenant') : null;
      setTenantId(tid);
      const r = await api('/stores');
      const list: StoreOption[] = (r.data || []).filter(
        (s: StoreOption) => s && s.is_active !== false,
      );
      setStores(list);
      const saved =
        typeof window !== 'undefined'
          ? localStorage.getItem(storageKey(tid)) || ''
          : '';
      if (saved && list.some((s) => s.id === saved)) {
        setStoreIdState(saved);
      } else if (list.length === 1) {
        setStoreIdState(list[0].id);
        if (typeof window !== 'undefined') {
          localStorage.setItem(storageKey(tid), list[0].id);
        }
      } else if (saved && !list.some((s) => s.id === saved)) {
        setStoreIdState('');
        if (typeof window !== 'undefined') {
          localStorage.removeItem(storageKey(tid));
        }
      }
    } catch {
      setStores([]);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    refreshStores().catch(() => undefined);
  }, [refreshStores]);

  const setStoreId = useCallback(
    (id: string) => {
      setStoreIdState(id || '');
      if (typeof window === 'undefined') return;
      const key = storageKey(tenantId || localStorage.getItem('tenant'));
      if (id) localStorage.setItem(key, id);
      else localStorage.removeItem(key);
    },
    [tenantId],
  );

  const activeStore = useMemo(
    () => stores.find((s) => s.id === storeId) || null,
    [stores, storeId],
  );

  const value = useMemo(
    () => ({
      stores,
      storeId,
      setStoreId,
      activeStore,
      loading,
      refreshStores,
    }),
    [stores, storeId, setStoreId, activeStore, loading, refreshStores],
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

/** Stable noops — POS/etc. call useStoreContext above Shell's StoreProvider;
 *  inline `() => undefined` in the fallback re-created every render and
 *  re-fired effects that listed `setStoreId` in deps (request storms). */
const NOOP_SET_STORE_ID = (_id: string) => undefined;
const NOOP_REFRESH_STORES = async () => undefined;

export function useStoreContext(): StoreContextValue {
  const ctx = useContext(StoreContext);
  if (!ctx) {
    return {
      stores: [],
      storeId: '',
      setStoreId: NOOP_SET_STORE_ID,
      activeStore: null,
      loading: false,
      refreshStores: NOOP_REFRESH_STORES,
    };
  }
  return ctx;
}
