'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/** Stage 232 R1 — Accounting → Accounts Payable surface → Credit engine. */
export default function AccountsPayablePage() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/credit?kind=payable');
  }, [router]);
  return (
    <main style={{ padding: 24 }}>
      <h1>Accounts Payable</h1>
      <p className="muted">Opening Credit payables…</p>
    </main>
  );
}
