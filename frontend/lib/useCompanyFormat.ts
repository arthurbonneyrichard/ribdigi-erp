'use client';

import { useEffect, useState } from 'react';
import { api } from './api';
import { rememberFormatPrefs, type FormatPrefs } from './format';

let cached: FormatPrefs | null | undefined;

/** Company date and number settings. A missing profile falls back to the defaults. */
export function useCompanyFormat(): FormatPrefs | null {
  const [prefs, setPrefs] = useState<FormatPrefs | null>(cached ?? null);

  useEffect(() => {
    if (cached !== undefined) {
      if (cached) rememberFormatPrefs(cached);
      return;
    }
    let cancelled = false;
    api('/tenants/me')
      .then((res) => {
        const row = (res.data || null) as FormatPrefs | null;
        cached = row;
        rememberFormatPrefs(row);
        if (!cancelled) setPrefs(row);
      })
      .catch(() => {
        cached = null;
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return prefs;
}
