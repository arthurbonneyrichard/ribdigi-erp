'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/** Stage 232 R1 — Accounting → Accounts Receivable surface → Credit engine. */
export default function AccountsReceivablePage() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/credit?kind=receivable');
  }, [router]);
  return (
    <main style={{ padding: 24 }}>
      <h1>Accounts Receivable</h1>
      <p className="muted">Opening Credit receivables…</p>
    </main>
  );
}
