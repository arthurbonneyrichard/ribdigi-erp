'use client';

import { useEffect, useState, type InputHTMLAttributes } from 'react';
import { currencySign } from '../lib/format';
import { getMe } from '../lib/meCache';

type Props = InputHTMLAttributes<HTMLInputElement> & {
  currency?: string | null;
  /** Keep the box only as wide as the number, for a row of fields. */
  inline?: boolean;
};

/** Number box with the company currency sign already shown. The typed value stays a number. */
export function AmountField({ currency, inline, ...props }: Props) {
  const [sign, setSign] = useState(() => currencySign(currency));

  useEffect(() => {
    if (currency) {
      setSign(currencySign(currency));
      return;
    }
    let cancelled = false;
    getMe()
      .then((res) => {
        const code = (res as { data?: { currency?: string | null } } | null)?.data?.currency;
        if (!cancelled) setSign(currencySign(code));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [currency]);

  return (
    <span className={inline ? 'money-fill money-inline' : 'money-fill'}>
      <span className="money-sign" aria-hidden="true">
        {sign}
      </span>
      <input {...props} />
    </span>
  );
}
