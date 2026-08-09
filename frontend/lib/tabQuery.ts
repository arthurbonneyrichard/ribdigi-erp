'use client';

import { useSearchParams } from 'next/navigation';
import { useState } from 'react';

/** Initialize a tab from `?tab=` when the value is in `allowed` (Stage 1 F17 KPI click-through). */
export function useTabQuery<T extends string>(allowed: readonly T[], fallback: T): [T, (tab: T) => void] {
  const params = useSearchParams();
  const raw = (params.get('tab') || '').trim();
  const initial = (allowed as readonly string[]).includes(raw) ? (raw as T) : fallback;
  return useState<T>(initial);
}
