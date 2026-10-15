'use client';

import { useEffect, useState } from 'react';
import { getMe } from './meCache';
import {
  peekCompanyFormatCache,
  rememberFormatPrefs,
  storeCompanyFormatCache,
  subscribeCompanyFormatRefresh,
  type FormatPrefs,
} from './format';

function formatFromMe(data: FormatPrefs | null): FormatPrefs | null {
  if (!data) return null;
  return {
    date_format: data.date_format,
    decimal_separator: data.decimal_separator,
    thousand_separator: data.thousand_separator,
    time_format: data.time_format,
  };
}

/** Company date and number settings from `/me`, so a cashier is not blocked by company admin profile. */
export function useCompanyFormat(): FormatPrefs | null {
  const [prefs, setPrefs] = useState<FormatPrefs | null>(peekCompanyFormatCache() ?? null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      getMe()
        .then((res) => {
          const row = formatFromMe((res.data || null) as FormatPrefs | null);
          storeCompanyFormatCache(row);
          if (!cancelled) setPrefs(row);
        })
        .catch(() => {
          if (!cancelled) setPrefs(peekCompanyFormatCache() ?? null);
        });
    };
    const existing = peekCompanyFormatCache();
    if (existing === undefined) load();
    else if (existing) rememberFormatPrefs(existing);
    const unsubscribe = subscribeCompanyFormatRefresh(load);
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  return prefs;
}
