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
        const saleLabel = `${sales} offline sale${sales === 1 ? '' : 's'}`;
        const tillLabel = `${devices} till${devices === 1 ? '' : 's'}`;
        setText(`These figures leave out ${saleLabel} still on ${tillLabel}. They are included after sync.`);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  if (!text) return null;
  return (
    <p className="offline-provisional" role="status">
      {text}
    </p>
  );
}
