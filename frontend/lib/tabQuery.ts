'use client';

import { useEffect, useState } from 'react';

/** Initialize a tab from `?tab=` when the value is in `allowed` (Stage 1 F17 KPI click-through).
 * Stage 95 P1 — also write `?tab=` on change so Shell deep-links stay honest.
 */
export function useTabQuery<T extends string>(allowed: readonly T[], fallback: T): [T, (tab: T) => void] {
  const [tab, setTabState] = useState<T>(fallback);

  useEffect(() => {
    // Prefer window over useSearchParams so static export / prerender does not require a Suspense boundary.
    const raw = new URLSearchParams(window.location.search).get('tab')?.trim() || '';
    if ((allowed as readonly string[]).includes(raw)) {
      setTabState(raw as T);
    }
  }, [allowed, fallback]);

  function setTab(next: T) {
    setTabState(next);
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    if (next === fallback) {
      url.searchParams.delete('tab');
    } else {
      url.searchParams.set('tab', next);
    }
    const qs = url.searchParams.toString();
    window.history.replaceState({}, '', qs ? `${url.pathname}?${qs}` : url.pathname);
  }

  return [tab, setTab];
}
