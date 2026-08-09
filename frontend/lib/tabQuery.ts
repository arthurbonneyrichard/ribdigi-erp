'use client';

import { useEffect, useState } from 'react';

/** Initialize a tab from `?tab=` when the value is in `allowed` (Stage 1 F17 KPI click-through). */
export function useTabQuery<T extends string>(allowed: readonly T[], fallback: T): [T, (tab: T) => void] {
  const [tab, setTab] = useState<T>(fallback);

  useEffect(() => {
    // Prefer window over useSearchParams so static export / prerender does not require a Suspense boundary.
    const raw = new URLSearchParams(window.location.search).get('tab')?.trim() || '';
    if ((allowed as readonly string[]).includes(raw)) {
      setTab(raw as T);
    }
  }, [allowed, fallback]);

  return [tab, setTab];
}
