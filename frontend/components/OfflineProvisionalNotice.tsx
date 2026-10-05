'use client';

import { useEffect, useState } from 'react';
import { api } from '../lib/api';

/** Server-side flag: another device still has offline sales that are not in these totals. */
export default function OfflineProvisionalNotice() {
  const [text, setText] = useState('');

  useEffect(() => {
    let cancelled = false;
    api('/pos/offline/provisional')
      .then((r: { data?: { provisional?: boolean; sales_pending?: number; devices_pending?: number } }) => {
        const data = r?.data;
        if (cancelled || !data?.provisional) return;
        const sales = Number(data.sales_pending) || 0;
        const devices = Number(data.devices_pending) || 0;
        setText(
          `Provisional. ${sales} offline sale(s) on ${devices} device(s) have not synced, so these figures do not include them yet.`
        );
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  if (!text) return null;
  return (
    <p className="muted" role="status">
      {text}
    </p>
  );
}
