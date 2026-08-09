/** Global store context for Multi-Store (Stage 4 M1 / BR-13.1). */

export const STORE_CONTEXT_KEY = 'selected_store_id';
export const STORE_CONTEXT_EVENT = 'ribdigi:store-context';

export function getSelectedStoreId(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(STORE_CONTEXT_KEY) || '';
}

export function setSelectedStoreId(storeId: string): void {
  if (typeof window === 'undefined') return;
  const next = (storeId || '').trim();
  if (next) localStorage.setItem(STORE_CONTEXT_KEY, next);
  else localStorage.removeItem(STORE_CONTEXT_KEY);
  window.dispatchEvent(new CustomEvent(STORE_CONTEXT_EVENT, { detail: { storeId: next } }));
}

export function subscribeStoreContext(listener: (storeId: string) => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const onCustom = (ev: Event) => {
    const detail = (ev as CustomEvent<{ storeId?: string }>).detail;
    listener(detail?.storeId || getSelectedStoreId());
  };
  const onStorage = (ev: StorageEvent) => {
    if (ev.key === STORE_CONTEXT_KEY || ev.key === null) {
      listener(getSelectedStoreId());
    }
  };
  window.addEventListener(STORE_CONTEXT_EVENT, onCustom);
  window.addEventListener('storage', onStorage);
  return () => {
    window.removeEventListener(STORE_CONTEXT_EVENT, onCustom);
    window.removeEventListener('storage', onStorage);
  };
}
