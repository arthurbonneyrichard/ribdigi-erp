'use client';

import { Suspense } from 'react';
import Shell from '../../components/Shell';

/**
 * Shared chrome for every signed-in dashboard page.
 * This layout stays mounted while navigating between dashboard routes
 * (Platform → Staff, Dashboard → Inventory, etc.), so the sidebar stays static.
 */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={null}>
      <Shell>{children}</Shell>
    </Suspense>
  );
}
